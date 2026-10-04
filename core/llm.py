"""
Gemini wrapper for GehunGuru.

Reliability design (see project report, Section B5):
* Model fallback chain: if the first model is rate-limited (429), missing or
  deprecated (404) or overloaded (5xx), the next model is tried.
* Structured JSON output (response_schema) so the app can read intent,
  confidence, sources and the hand-off flag instead of parsing free text.
* Output guardrails: invented knowledge-base ids are dropped, unknown intent
  and confidence values are normalised, and any pesticide dose that slips into
  an answer is redacted.
* If every model fails, the caller falls back to offline knowledge-base search.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

from pydantic import BaseModel

from .knowledge_base import clean_sources
from .prompts import INTENTS

log = logging.getLogger("gehunguru")

DEFAULT_MODELS = ["gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"]


# ------------------------------------------------------------------ schemas

class ChatReply(BaseModel):
    answer: str
    intent: str
    confidence: str
    sources: list[str]
    needs_human: bool
    handoff_reason: str
    follow_up: str
    transcript: str


class Cause(BaseModel):
    name: str
    likelihood: str
    visible_signs: str
    kb_id: str


class Diagnosis(BaseModel):
    is_wheat: bool
    image_quality: str
    possible_causes: list[Cause]
    field_checks: list[str]
    actions: list[str]
    urgency: str
    needs_expert: bool
    summary: str
    sources: list[str]


# ------------------------------------------------------------------ result


@dataclass
class LLMResult:
    ok: bool
    data: dict | None = None
    model: str | None = None
    attempts: list[str] = field(default_factory=list)
    latency_ms: int = 0
    error: str | None = None
    fatal: bool = False  # e.g. invalid API key: no point retrying


def make_client(api_key: str, timeout_ms: int = 45_000):
    from google import genai
    from google.genai import types

    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))


def _thinking_config(model: str):
    from google.genai import types

    if model.startswith("gemini-3"):
        return types.ThinkingConfig(thinking_level="low")
    if model.startswith("gemini-2.5-flash"):
        return types.ThinkingConfig(thinking_budget=0)
    return None


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE | re.MULTILINE).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(t[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _short(e: Exception, limit: int = 140) -> str:
    """One-line, readable version of an SDK error for the 'why' caption and the server log."""
    msg = getattr(e, "message", None) or str(e)
    return " ".join(str(msg).split())[:limit]


def _parse_response(resp) -> tuple[dict | None, str | None]:
    """Return (data, problem)."""
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, BaseModel):
        return parsed.model_dump(), None
    if isinstance(parsed, dict):
        return parsed, None
    text = None
    try:
        text = resp.text
    except Exception:  # noqa: BLE001 - SDK raises on blocked candidates in some versions
        text = None
    data = _extract_json(text or "")
    if data is not None:
        return data, None
    # find out why
    try:
        reason = str(resp.candidates[0].finish_reason)
    except Exception:  # noqa: BLE001
        reason = "no candidates"
    if "SAFETY" in reason.upper() or "BLOCK" in reason.upper():
        return None, "blocked by safety filter"
    return None, f"unreadable output ({reason})"


def generate(client, models: list[str], system: str, contents: list, schema: type[BaseModel],
             temperature: float = 0.2, max_output_tokens: int = 2048) -> LLMResult:
    from google.genai import errors, types

    t0 = time.time()
    attempts: list[str] = []
    for model in models:
        use_thinking = True
        server_retry_done = False
        while True:
            cfg_kwargs = dict(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
                response_schema=schema,
            )
            tc = _thinking_config(model) if use_thinking else None
            if tc is not None:
                cfg_kwargs["thinking_config"] = tc
            try:
                resp = client.models.generate_content(
                    model=model, contents=contents, config=types.GenerateContentConfig(**cfg_kwargs)
                )
            except errors.ClientError as e:
                code = getattr(e, "code", None)
                if "API_KEY_INVALID" in str(e) or "API key not valid" in str(e):
                    code = 401  # Gemini reports a bad key as HTTP 400; treat it as fatal
                if code == 400 and use_thinking and tc is not None:
                    use_thinking = False  # model may not support this thinking setting
                    continue
                log.warning("Gemini %s failed with %s: %s", model, code, _short(e, 500))
                if code in (401, 403):
                    attempts.append(f"{model}: API key rejected ({code}): {_short(e)}")
                    return LLMResult(False, attempts=attempts, error="The Gemini API key was rejected.",
                                     latency_ms=int((time.time() - t0) * 1000), fatal=True)
                label = {404: "model not available", 429: "rate limit / quota reached"}.get(code, f"error {code}")
                attempts.append(f"{model}: {label}: {_short(e)}")
                break
            except errors.ServerError as e:
                code = getattr(e, "code", None)
                if not server_retry_done:
                    server_retry_done = True
                    time.sleep(1.5)
                    continue
                log.warning("Gemini %s server error %s: %s", model, code, _short(e, 500))
                attempts.append(f"{model}: server error {code}: {_short(e)}")
                break
            except Exception as e:  # noqa: BLE001 - network error, timeout, SDK bug
                log.warning("Gemini %s raised %s: %s", model, type(e).__name__, _short(e, 500))
                attempts.append(f"{model}: {type(e).__name__}: {_short(e)}")
                break

            data, problem = _parse_response(resp)
            if data is None:
                log.warning("Gemini %s gave no usable answer: %s", model, problem)
                attempts.append(f"{model}: {problem}")
                break
            return LLMResult(True, data=data, model=model, attempts=attempts,
                             latency_ms=int((time.time() - t0) * 1000))
    return LLMResult(False, attempts=attempts, error="All AI models failed.",
                     latency_ms=int((time.time() - t0) * 1000))


# ------------------------------------------------------------------ output guardrails

_DOSE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:ml|mL|g|gm|gms|gram|grams|kg|l|litre|liter|litres|liters|मिली|मि\.ली\.|ग्राम|लीटर|ਮਿ\.ਲੀ\.|ਗ੍ਰਾਮ|ਲੀਟਰ)"
    r"\s*(?:/|per|प्रति|ਪ੍ਰਤੀ|प्रति\s*एकड़)\s*(?:acre|acres|ha|hectare|hectares|एकड़|हेक्टेयर|ਏਕੜ|kanal)",
    re.IGNORECASE,
)
_PESTICIDE_WORDS = re.compile(
    r"pesticide|herbicide|weedicide|fungicide|insecticide|spray|chhidkav|छिड़काव|दवा|दवाई|ਸਪਰੇਅ|ਦਵਾਈ|"
    r"propiconazole|tebuconazole|clodinafop|sulfosulfuron|pinoxaden|metsulfuron|carboxin|pendimethalin",
    re.IGNORECASE,
)


_SENTENCE = re.compile(r"[^.!?।\n]*[.!?।]?\n?")


def redact_doses(answer: str) -> tuple[str, bool]:
    """Remove '<number> ml/g/kg/L per acre' fragments, but ONLY inside sentences that mention a chemical.

    v1 redacted the whole answer whenever any chemical word appeared anywhere, which also erased a
    legitimate seed rate ("40 kg per acre") in an answer that mentioned seed-treatment fungicide.
    Testing caught this, so redaction now works sentence by sentence.
    """
    if not answer or not _PESTICIDE_WORDS.search(answer):
        return answer, False
    changed = False
    out = []
    for sentence in _SENTENCE.findall(answer):
        if sentence and _PESTICIDE_WORDS.search(sentence):
            sentence, n = _DOSE.subn("[dose removed: follow the product label or your KVK]", sentence)
            changed = changed or n > 0
        out.append(sentence)
    return "".join(out), changed


# Phrases that mark a question addressed TO the farmer ("Do you want...?", "Kya aapko...?"). The follow-up
# button sends its text as the farmer's own message, so such text must never become a button.
# Added after live testing: the prompt rule alone still produced "Kya aapko next irrigation ka exact samay
# chahiye?" in Hinglish, which the farmer then sent back to the bot.
_ASKS_FARMER = re.compile(
    r"\b(do you|did you|are you|have you|would you like|can you check|is your|are your|your (field|crop|soil))\b|"
    r"\bkya (aapko|aapne|aap ne|aapke|aapki|tumhe|tumne)\b|\baapk[eio] (khet|fasal|mitti)\b|"
    r"क्या आपको|क्या आपने|आपके खेत|आपकी फसल|ਕੀ ਤੁਹਾਨੂੰ|ਤੁਹਾਨੂੰ|ਕੀ ਤੁਸੀਂ|ਤੁਹਾਡੇ ਖੇਤ|ਤੁਹਾਡੀ ਫਸਲ",
    re.IGNORECASE,
)


def follow_up_is_farmer_voice(text: str) -> bool:
    return bool(text) and not _ASKS_FARMER.search(text)


def normalise_chat(data: dict) -> dict:
    out = {
        "answer": str(data.get("answer") or "").strip(),
        "intent": str(data.get("intent") or "other").strip().lower(),
        "confidence": str(data.get("confidence") or "medium").strip().lower(),
        "sources": clean_sources(data.get("sources") or []),
        "needs_human": bool(data.get("needs_human")),
        "handoff_reason": str(data.get("handoff_reason") or "").strip(),
        "follow_up": str(data.get("follow_up") or "").strip(),
        "transcript": str(data.get("transcript") or "").strip(),
        "dose_redacted": False,
    }
    if out["intent"] not in INTENTS:
        out["intent"] = "other"
    if out["confidence"] not in ("high", "medium", "low"):
        out["confidence"] = "medium"
    # Suspected rust, smut or Karnal bunt must always reach a human: enforced here, not left to the model
    # (live testing showed the model suspecting yellow rust without setting needs_human).
    serious = {"KB-10": "yellow rust", "KB-11": "brown rust", "KB-12": "loose smut", "KB-13": "Karnal bunt"}
    hits = [serious[i] for i in out["sources"] if i in serious]
    if hits and out["intent"] in ("diseases", "other", "weather") and not out["needs_human"]:
        out["needs_human"] = True
        out["handoff_reason"] = (f"Suspected {hits[0]}: please get it confirmed by your KVK or agriculture officer "
                                 "before buying or spraying any fungicide.")
    if out["confidence"] == "low" and out["intent"] not in ("out_of_scope", "adversarial", "greeting"):
        out["needs_human"] = True
        out["handoff_reason"] = out["handoff_reason"] or "The assistant is not confident about this answer."
    if not follow_up_is_farmer_voice(out["follow_up"]):
        out["follow_up"] = ""  # a question to the farmer belongs in the answer, not on the button
    out["answer"], out["dose_redacted"] = redact_doses(out["answer"])
    return out


def normalise_diagnosis(data: dict) -> dict:
    causes = []
    for c in (data.get("possible_causes") or [])[:3]:
        if not isinstance(c, dict):
            continue
        lk = str(c.get("likelihood") or "low").lower()
        causes.append({
            "name": str(c.get("name") or "Unknown").strip(),
            "likelihood": lk if lk in ("high", "medium", "low") else "low",
            "visible_signs": str(c.get("visible_signs") or "").strip(),
            "kb_id": (clean_sources([c.get("kb_id")]) or [""])[0],
        })
    urgency = str(data.get("urgency") or "soon").lower()
    quality = str(data.get("image_quality") or "fair").lower()
    out = {
        "is_wheat": bool(data.get("is_wheat")),
        "image_quality": quality if quality in ("good", "fair", "poor") else "fair",
        "possible_causes": causes,
        "field_checks": [str(x) for x in (data.get("field_checks") or [])][:4],
        "actions": [redact_doses(str(x))[0] for x in (data.get("actions") or [])][:4],
        "urgency": urgency if urgency in ("routine", "soon", "urgent") else "soon",
        "needs_expert": bool(data.get("needs_expert")),
        "summary": redact_doses(str(data.get("summary") or "").strip())[0],
        "sources": clean_sources((data.get("sources") or []) + [c["kb_id"] for c in causes if c["kb_id"]]),
    }
    top = causes[0]["likelihood"] if causes else "low"
    if out["is_wheat"] and (top != "high" or out["image_quality"] == "poor"):
        out["needs_expert"] = True
    return out


# ======================================================================
# Backup provider: Groq (free tier, OpenAI-compatible API, no SDK needed)
# Used when Gemini is unavailable, e.g. Google blocks the project (403).
# ======================================================================

GROQ_URL = "https://api.groq.com/openai/v1"
# Used only if the live model list cannot be fetched. Groq retires models often (two of our first
# fallbacks, llama-3.3-70b-versatile and llama-3.1-8b-instant, disappeared mid-project), so the app
# normally asks Groq which models exist right now and picks from that list (see pick_groq_models).
GROQ_TEXT_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
GROQ_VISION_MODELS = ["meta-llama/llama-4-scout-17b-16e-instruct", "qwen/qwen3.8-27b"]
GROQ_WHISPER = "whisper-large-v3"
GROQ_MAX_OUTPUT = 1400  # Groq counts reserved output tokens against the 8K tokens/minute free limit

_TEXT_PREFERENCE = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/", "meta-llama/llama-4", "llama-3.3", "llama"]
_SKIP = ("guard", "whisper", "tts", "playai", "orpheus", "compound", "distil", "embed")
_VISION_HINTS = ("scout", "maverick", "vision", "-vl", "qwen")


def groq_list_models(api_key: str, timeout: float = 10) -> list[str]:
    """Live list of model ids this key can use; [] if the call fails."""
    import requests

    try:
        r = requests.get(f"{GROQ_URL}/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
        if r.status_code != 200:
            return []
        return sorted(m["id"] for m in r.json().get("data", []) if m.get("active", True) and m.get("id"))
    except Exception:  # noqa: BLE001
        return []


def pick_groq_models(available: list[str], kind: str) -> list[str]:
    """Choose models in preference order from what Groq offers today."""
    if not available:
        return {"text": GROQ_TEXT_MODELS, "vision": GROQ_VISION_MODELS, "whisper": [GROQ_WHISPER]}[kind]
    if kind == "whisper":
        w = [m for m in available if "whisper" in m]
        return sorted(w, key=lambda m: (0 if "turbo" in m else 1, m))[:2] or [GROQ_WHISPER]
    usable = [m for m in available if not any(x in m.lower() for x in _SKIP)]
    if kind == "vision":
        return [m for m in usable if any(h in m.lower() for h in _VISION_HINTS)][:3]
    ordered = []
    for pref in _TEXT_PREFERENCE:
        ordered += [m for m in usable if m.startswith(pref) and m not in ordered]
    return ordered[:4] or usable[:3]


def _retry_after(text: str) -> float | None:
    """Seconds from Groq's 'Please try again in 1m2.5s' / '7.5s' message."""
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", text or "")
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2))

_SKELETONS = {
    "ChatReply": {
        "answer": "markdown text for the farmer", "intent": "one of the listed intents",
        "confidence": "high | medium | low", "sources": ["KB-08"], "needs_human": False,
        "handoff_reason": "", "follow_up": "", "transcript": "",
    },
    "Diagnosis": {
        "is_wheat": True, "image_quality": "good | fair | poor",
        "possible_causes": [{"name": "", "likelihood": "high | medium | low", "visible_signs": "", "kb_id": "KB-10"}],
        "field_checks": [""], "actions": [""], "urgency": "routine | soon | urgent", "needs_expert": True,
        "summary": "", "sources": ["KB-10"],
    },
}


def json_instruction(schema: type[BaseModel]) -> str:
    return ("\n\n## JSON format\nReturn ONLY one JSON object, no markdown fences, with exactly these keys "
            "(values here are examples of the type):\n" + json.dumps(_SKELETONS[schema.__name__], ensure_ascii=False))


def groq_transcribe(api_key: str, wav: bytes, models: list[str] | None = None,
                    timeout: float = 60) -> tuple[str | None, str | None]:
    import requests

    errs = []
    for model in models or [GROQ_WHISPER]:
        try:
            r = requests.post(f"{GROQ_URL}/audio/transcriptions", headers={"Authorization": f"Bearer {api_key}"},
                              files={"file": ("question.wav", wav, "audio/wav")},
                              data={"model": model, "response_format": "json"}, timeout=timeout)
            if r.status_code == 200:
                return (r.json().get("text") or "").strip(), None
            errs.append(f"{model}: error {r.status_code}: {_short(Exception(r.text), 90)}")
        except Exception as e:  # noqa: BLE001
            errs.append(f"{model}: {type(e).__name__}: {_short(e, 90)}")
    return None, " | ".join(errs)


def groq_generate(api_key: str, models: list[str], system: str, messages: list[dict], schema: type[BaseModel],
                  temperature: float = 0.2, timeout: float = 60) -> LLMResult:
    """Same contract as generate(), but over Groq's OpenAI-compatible chat API."""
    import requests

    t0 = time.time()
    attempts: list[str] = []
    full_system = system + json_instruction(schema)
    for model in models:
        use_json_mode, server_retry_done, waited = True, False, False
        while True:
            body = {"model": model, "temperature": temperature, "max_completion_tokens": GROQ_MAX_OUTPUT,
                    "messages": [{"role": "system", "content": full_system}] + messages}
            if use_json_mode:
                body["response_format"] = {"type": "json_object"}
            if model.startswith("openai/gpt-oss"):
                body["reasoning_effort"] = "low"
            try:
                r = requests.post(f"{GROQ_URL}/chat/completions", json=body, timeout=timeout,
                                  headers={"Authorization": f"Bearer {api_key}"})
            except Exception as e:  # noqa: BLE001
                log.warning("Groq %s raised %s: %s", model, type(e).__name__, _short(e, 500))
                attempts.append(f"groq {model}: {type(e).__name__}: {_short(e)}")
                break
            code, text = r.status_code, r.text
            if code == 200:
                try:
                    content = r.json()["choices"][0]["message"].get("content") or ""
                except Exception:  # noqa: BLE001
                    content = ""
                data = _extract_json(content)
                if data is None:
                    attempts.append(f"groq {model}: unreadable output")
                    break
                return LLMResult(True, data=data, model=f"groq/{model}", attempts=attempts,
                                 latency_ms=int((time.time() - t0) * 1000))
            log.warning("Groq %s failed with %s: %s", model, code, _short(Exception(text), 500))
            if code == 401:
                attempts.append(f"groq {model}: API key rejected (401)")
                return LLMResult(False, attempts=attempts, error="The Groq API key was rejected.", fatal=True,
                                 latency_ms=int((time.time() - t0) * 1000))
            if code == 400 and use_json_mode and ("json" in text.lower() or "response_format" in text):
                use_json_mode = False  # model rejected JSON mode or failed to validate: ask in plain text
                continue
            if code == 429 and not waited:
                wait = _retry_after(text)
                if wait is not None and wait <= 8:  # per-minute limit: a short pause is enough
                    waited = True
                    time.sleep(wait + 0.5)
                    continue
            if code >= 500 and not server_retry_done:
                server_retry_done = True
                time.sleep(1.5)
                continue
            label = {404: "model not available", 413: "request too large for free limit",
                     429: "rate limit / quota reached"}.get(code, f"error {code}")
            if code == 400 and ("does not exist" in text or "decommissioned" in text):
                label = "model not available"
            attempts.append(f"groq {model}: {label}: {_short(Exception(text), 90)}")
            break
    return LLMResult(False, attempts=attempts, error="All backup models failed.",
                     latency_ms=int((time.time() - t0) * 1000))
