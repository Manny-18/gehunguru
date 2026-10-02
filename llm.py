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
import re
import time
from dataclasses import dataclass, field

from pydantic import BaseModel

from .knowledge_base import clean_sources
from .prompts import INTENTS

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
                if code in (401, 403):
                    attempts.append(f"{model}: API key rejected ({code})")
                    return LLMResult(False, attempts=attempts, error="The Gemini API key was rejected.",
                                     latency_ms=int((time.time() - t0) * 1000), fatal=True)
                label = {404: "model not available", 429: "rate limit / quota reached"}.get(code, f"error {code}")
                attempts.append(f"{model}: {label}")
                break
            except errors.ServerError as e:
                code = getattr(e, "code", None)
                if not server_retry_done:
                    server_retry_done = True
                    time.sleep(1.5)
                    continue
                attempts.append(f"{model}: server error {code}")
                break
            except Exception as e:  # noqa: BLE001 - network error, timeout, SDK bug
                attempts.append(f"{model}: {type(e).__name__}")
                break

            data, problem = _parse_response(resp)
            if data is None:
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
    if out["confidence"] == "low" and out["intent"] not in ("out_of_scope", "adversarial", "greeting"):
        out["needs_human"] = True
        out["handoff_reason"] = out["handoff_reason"] or "The assistant is not confident about this answer."
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
