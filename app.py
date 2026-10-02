"""
GehunGuru: AI wheat advisory chatbot for North-West India.
End-term project, AI Applications. Run:  streamlit run app.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import time
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

from core import crop_stage, guardrails, llm, prompts, ui, weather
from core import knowledge_base as kb

APP_DIR = Path(__file__).parent
IST = timezone(timedelta(hours=5, minutes=30))
MAX_QUESTIONS_PER_SESSION = 40
MIN_SECONDS_BETWEEN_CALLS = 2.0
HISTORY_TURNS = 10
MAX_IMAGE_MB = 8
MAX_AUDIO_MB = 5

st.set_page_config(page_title="GehunGuru: AI wheat advisor", page_icon="🌾", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(ui.CSS, unsafe_allow_html=True)


# ============================================================ configuration

def secret(name: str, default=None):
    try:
        return st.secrets.get(name, os.environ.get(name, default))
    except Exception:  # no secrets.toml at all
        return os.environ.get(name, default)


API_KEY = secret("GEMINI_API_KEY")
_custom = secret("GEMINI_MODEL")
MODELS = list(dict.fromkeys(([_custom] if _custom else []) + llm.DEFAULT_MODELS))
FAKE_LLM = os.environ.get("GG_FAKE_LLM") == "1"  # used only by automated tests / screenshots


@st.cache_resource(show_spinner=False)
def get_client(key: str):
    return llm.make_client(key)


def ai_client():
    if FAKE_LLM:
        from tests.fake_llm import FakeClient
        return FakeClient()
    if not API_KEY:
        return None
    return get_client(API_KEY)


@st.cache_data(ttl=1800, show_spinner=False)
def live_forecast(district: str):
    lat, lon, _, _ = weather.DISTRICTS[district]
    return weather.fetch_forecast(lat, lon)


def today_ist() -> date:
    return datetime.now(IST).date()


# ============================================================ sample data

def load_samples() -> dict[str, dict]:
    path = APP_DIR / "sample_data" / "farmer_profiles.csv"
    with open(path, encoding="utf-8") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


SAMPLES = load_samples()
VARIETIES = ["Not sure", "HD 3086", "DBW 187", "DBW 222", "DBW 303", "HD 3226", "PBW 826",
             "PBW 752 (late)", "DBW 173 (late)", "HD 3059 (late)", "Other"]
IRRIGATION = ["Tubewell", "Canal", "Canal + tubewell", "Limited water", "Rainfed"]
SOILS = ["Loam", "Sandy loam", "Clay loam", "Sandy", "Not sure"]
LANGS = {"Auto": "Auto (match my language)", "English": "English", "Hindi": "हिंदी (Hindi)",
         "Punjabi": "ਪੰਜਾਬੀ (Punjabi)", "Hinglish": "Hinglish"}
WX_MODES = {"live": "Live 7-day forecast (Open-Meteo)"} | {k: v["label"] for k, v in weather.SCENARIOS.items()}
INTENT_LABELS = {
    "sowing_varieties": "Sowing and varieties", "seed": "Seed", "nutrients": "Fertiliser", "irrigation": "Irrigation",
    "weeds": "Weeds", "pests": "Pests", "diseases": "Diseases", "weather": "Weather", "harvest_storage": "Harvest and storage",
    "stubble": "Stubble management", "schemes_helplines": "Help and schemes", "greeting": "Greeting",
    "out_of_scope": "Outside wheat (redirected)", "adversarial": "Blocked instruction", "other": "Other",
    "emergency": "Emergency (fixed reply)", "offline": "Offline knowledge base", "diagnosis": "Photo check",
    "handoff": "Hand-off to human",
}


# ============================================================ session state

def init_state():
    ss = st.session_state
    ss.setdefault("consented", False)
    ss.setdefault("messages", [])
    ss.setdefault("ticket", None)
    ss.setdefault("stats", {"intents": Counter(), "models": Counter(), "offline": 0, "pii": 0, "emergency": 0,
                            "injection": 0, "dose_redacted": 0, "handoffs": 0, "errors": []})
    ss.setdefault("last_call", 0.0)
    ss.setdefault("last_hash", "")
    ss.setdefault("pending", None)
    ss.setdefault("sample_pick", "(none)")
    defaults = {"p_name": "", "p_district": "Ludhiana", "p_sown": False,
                "p_sowing": date(today_ist().year, 11, 5), "p_adv": today_ist(), "p_variety": "Not sure",
                "p_irrigation": "Tubewell", "p_soil": "Loam", "p_acres": 5.0, "p_lang": "Auto", "p_wx": "live"}
    for k, v in defaults.items():
        ss.setdefault(k, v)


def apply_sample():
    key = st.session_state.sample_pick
    if key == "(none)" or key not in SAMPLES:
        return
    s = SAMPLES[key]
    ss = st.session_state
    ss.p_name = s["name"]
    ss.p_district = s["district"]
    ss.p_sown = bool(s["sowing_date"])
    if s["sowing_date"]:
        ss.p_sowing = date.fromisoformat(s["sowing_date"])
    ss.p_adv = today_ist() if s["advisory_date"] == "today" else date.fromisoformat(s["advisory_date"])
    ss.p_variety = s["variety"] if s["variety"] in VARIETIES else "Other"
    ss.p_irrigation = s["irrigation"]
    ss.p_soil = s["soil"]
    ss.p_acres = float(s["acres"])
    ss.p_lang = s["language"]
    ss.p_wx = s["weather_mode"]
    ss.messages = []
    ss.ticket = None


def new_ticket() -> str:
    if not st.session_state.ticket:
        st.session_state.ticket = f"GG-{today_ist():%y%m%d}-{uuid.uuid4().hex[:4].upper()}"
    return st.session_state.ticket


init_state()
ss = st.session_state


# ============================================================ sidebar: farm profile

with st.sidebar:
    st.markdown("### Your farm")
    st.selectbox("Load a sample farmer (demo)", ["(none)"] + list(SAMPLES), key="sample_pick",
                 format_func=lambda k: "Choose..." if k == "(none)" else SAMPLES[k]["label"], on_change=apply_sample)
    st.text_input("Name (optional)", key="p_name", max_chars=40)
    st.selectbox("District", list(weather.DISTRICTS), key="p_district",
                 format_func=lambda d: f"{d}, {weather.DISTRICTS[d][2]}")
    st.toggle("Wheat already sown", key="p_sown")
    if ss.p_sown:
        st.date_input("Sowing date", key="p_sowing", format="DD/MM/YYYY",
                      min_value=date(2024, 9, 1), max_value=date(2030, 12, 31))
    st.date_input("Advice for date", key="p_adv", format="DD/MM/YYYY",
                  min_value=date(2024, 9, 1), max_value=date(2030, 12, 31),
                  help="Keep today's date for real use. Change it only to preview advice for a later date "
                       "(useful for demos, since the 2026-27 crop is not sown yet).")
    c1, c2 = st.columns(2)
    c1.selectbox("Variety", VARIETIES, key="p_variety")
    c2.number_input("Area (acres)", min_value=0.5, max_value=200.0, step=0.5, key="p_acres")
    c1.selectbox("Irrigation", IRRIGATION, key="p_irrigation")
    c2.selectbox("Soil", SOILS, key="p_soil")

    st.markdown("### Settings")
    st.selectbox("Reply language", list(LANGS), key="p_lang", format_func=LANGS.get)
    st.selectbox("Weather data", list(WX_MODES), key="p_wx", format_func=WX_MODES.get,
                 help="Sample weeks are demo data that let you see each weather rule working.")

    st.markdown("### Help")
    if st.button("Talk to a human expert", width="stretch", type="primary"):
        t = new_ticket()
        ss.stats["handoffs"] += 1
        ss.messages.append({"role": "assistant", "kind": "handoff", "content": "", "meta": {
            "ticket": t, "reason": "You asked to speak with a person. Here is how to reach one."}})
    summary_slot = st.empty()
    if st.button("Start a new chat", width="stretch"):
        ss.messages = []
        ss.ticket = None
        st.rerun()


# ============================================================ consent gate

if not ss.consented:
    st.markdown(ui.header_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="gg-welcome"><h2>Before you start</h2>'
        '<p>GehunGuru is an <b>AI assistant</b> for wheat farmers in Punjab, Haryana, western UP, Delhi NCR and '
        'north Rajasthan. It is not a person, a doctor or a government officer, and it can be wrong.</p>'
        '<p><b>What happens to your data:</b> your questions, voice notes and photos are sent to Google\'s Gemini '
        'API to create answers. On the free Gemini tier Google may use this content to improve its products. '
        'Your district\'s location (not yours) is sent to Open-Meteo for the weather forecast. Nothing is saved '
        'by this app after you close the tab.</p>'
        '<p><b>Please do not share</b> Aadhaar, bank or phone numbers. The app removes numbers that look like '
        'these before sending.</p>'
        '<p>For pesticide doses always follow the product label or your KVK. In an emergency call 108 / 112.</p>'
        '</div>', unsafe_allow_html=True)
    st.write("")
    if st.button("I understand, start", type="primary"):
        ss.consented = True
        st.rerun()
    st.stop()


# ============================================================ compute farm situation

adv_date: date = ss.p_adv
sowing: date | None = ss.p_sowing if ss.p_sown else None
info = crop_stage.estimate(sowing, adv_date)
stage = info["stage"]
lat, lon, state_name, foothill = weather.DISTRICTS[ss.p_district]

wx_error = None
if ss.p_wx == "live":
    try:
        days = live_forecast(ss.p_district)
        wx_label = (f"Live forecast for {ss.p_district} from Open-Meteo, "
                    f"{days[0].date:%d %b} to {days[-1].date:%d %b}.")
        if abs((adv_date - today_ist()).days) > 3:
            wx_label += " Note: the advice date is not this week, so weather rules use this week's live forecast."
    except weather.WeatherUnavailable as exc:
        days, wx_error = [], str(exc)
        wx_label = "Live weather is unavailable right now, so weather-based alerts are switched off."
else:
    days = weather.scenario_days(ss.p_wx, adv_date)
    wx_label = f"{weather.SCENARIOS[ss.p_wx]['label']}: demo data, not a real forecast."

alerts = weather.evaluate_alerts(days, stage.key, info["status"], foothill)


def farm_context() -> str:
    lines = [f"Advice date: {adv_date:%d %b %Y} (today is {today_ist():%d %b %Y})"]
    if ss.p_name.strip():
        lines.append(f"Farmer name: {ss.p_name.strip()}")
    lines.append(f"District: {ss.p_district}, {state_name}" + (" (foothill yellow-rust hotspot)" if foothill else ""))
    if info["status"] == "not_sown":
        lines.append("Crop status: NOT SOWN YET. Give pre-sowing advice.")
    else:
        lines.append(f"Sowing date: {sowing:%d %b %Y} ({info['window'].replace('_', ' ')} sowing)")
        lines.append(f"Days after sowing (DAS): {info['das']}")
        lines.append(f"Current stage: {stage.name} [{stage.key}]")
        if info.get("next_stage"):
            lines.append(f"Next stage: {info['next_stage'].name} in {info['days_to_next']} days")
        irr = info.get("next_irrigation")
        if irr:
            lines.append(f"Next critical irrigation: about day {irr['das']} ({irr['label']}), in {irr['in_days']} days")
        lines.append(f"In weed-control window (30-35 DAS): {'yes' if info['in_weed_window'] else 'no'}")
    lines.append(f"Variety: {ss.p_variety}. Irrigation: {ss.p_irrigation}. Soil: {ss.p_soil}. Area: {ss.p_acres:g} acres")
    for w in info["warnings"]:
        lines.append(f"Warning: {w}")
    return "\n".join(lines)


def weather_context() -> str:
    if not days:
        return "Weather data unavailable. Do not make weather-based claims."
    alert_lines = "\n".join(f"- [{a.level.upper()}] {a.title}: {a.message}" for a in alerts) or "- none"
    return weather.summary_for_prompt(days, wx_label) + "\nAlerts:\n" + alert_lines


def system_prompt() -> str:
    return prompts.SYSTEM_TEMPLATE.format(
        language_instruction=prompts.LANGUAGE_INSTRUCTIONS[ss.p_lang],
        intents=", ".join(prompts.INTENTS),
        farm_context=farm_context(),
        weather_context=weather_context(),
        kb_text=kb.kb_as_prompt_text(),
    )


# ============================================================ main layout

st.markdown(ui.header_html(), unsafe_allow_html=True)
st.markdown(ui.ai_notice_html(), unsafe_allow_html=True)
if not API_KEY and not FAKE_LLM:
    st.info("Offline mode: no Gemini API key is configured, so answers come straight from the knowledge base "
            "and photo or voice checks are off. Add GEMINI_API_KEY in the app's secrets to switch the AI on.")

st.markdown(ui.track_html(info, ss.p_district), unsafe_allow_html=True)

col_w, col_a = st.columns([1.1, 1], gap="medium")
with col_w:
    st.markdown("**This week's weather**")
    if days:
        st.markdown(ui.weather_html(days, wx_label), unsafe_allow_html=True)
    else:
        st.caption(wx_label)
with col_a:
    st.markdown("**Field alerts**")
    if alerts:
        st.markdown(ui.alerts_html(alerts), unsafe_allow_html=True)
    else:
        st.caption("No alerts: weather data is unavailable.")


# ============================================================ chat helpers

def to_contents(history: list[dict]):
    from google.genai import types

    contents = []
    for m in history[-HISTORY_TURNS:]:
        if m["kind"] in ("handoff", "notice"):
            continue
        text = m.get("llm_text") or m.get("content") or ""
        if not text:
            continue
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents


def offline_reply(query: str) -> str:
    hits = kb.search(query, stage.key, k=2)
    if not hits:
        return ("The AI service is not available right now and I could not find this in the offline knowledge "
                "base. Please call the Kisan Call Centre at **1800-180-1551** (free) or try again in a minute.")
    parts = ["**The AI service is not available right now**, so here is what the checked knowledge base says:"]
    for e in hits:
        parts.append(f"**{e['title']}** [{e['id']}]\n\n{e['text']}")
    return "\n\n".join(parts)


def add_assistant(content: str, kind: str = "chat", meta: dict | None = None, llm_text: str | None = None):
    ss.messages.append({"role": "assistant", "kind": kind, "content": content, "meta": meta or {},
                        "llm_text": llm_text or content})


def prep_image(f) -> tuple[bytes | None, str | None]:
    if f.size > MAX_IMAGE_MB * 1024 * 1024:
        return None, f"That photo is larger than {MAX_IMAGE_MB} MB. Please send a smaller photo."
    try:
        img = Image.open(io.BytesIO(f.getvalue()))
        img = ImageOps.exif_transpose(img).convert("RGB")  # re-encoding also strips GPS/EXIF data
        img.thumbnail((1280, 1280))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), None
    except Exception:  # noqa: BLE001
        return None, "I could not open that file as a photo. Please send a JPG or PNG image."


def handle_turn(text: str, image_file=None, audio_file=None):
    """Guardrails -> AI (with fallbacks) -> store the reply. Everything is appended to ss.messages."""
    text = (text or "").strip()
    stats = ss.stats

    # --- session limits and double-submit protection
    n_questions = sum(1 for m in ss.messages if m["role"] == "user")
    if n_questions >= MAX_QUESTIONS_PER_SESSION:
        st.toast("Session limit reached. Press 'Start a new chat' in the sidebar.")
        return
    fingerprint = hashlib.sha256(
        (text + str(getattr(image_file, "size", "")) + str(getattr(audio_file, "size", ""))).encode()).hexdigest()
    if fingerprint == ss.last_hash and time.time() - ss.last_call < 15:
        st.toast("You already sent that. The answer is above.")
        return
    wait = MIN_SECONDS_BETWEEN_CALLS - (time.time() - ss.last_call)
    if wait > 0:
        time.sleep(wait)
    ss.last_hash, ss.last_call = fingerprint, time.time()

    if not text and not image_file and not audio_file:
        return
    if text:
        ok, msg = guardrails.validate_message(text)
        if not ok:
            st.toast(msg)
            return

    masked, pii = guardrails.mask_pii(text)
    if pii:
        stats["pii"] += 1

    # --- the user's message as shown in the chat
    image_bytes = None
    if image_file is not None:
        image_bytes, err = prep_image(image_file)
        if err:
            ss.messages.append({"role": "user", "kind": "chat", "content": masked or "(photo)", "meta": {}})
            add_assistant(err, meta={"intent": "other", "confidence": "high"})
            return
    user_msg = {"role": "user", "kind": "photo" if image_bytes else ("voice" if audio_file else "chat"),
                "content": masked or ("(voice message)" if audio_file else "(photo)"), "meta": {"pii": pii},
                "image": image_bytes}
    ss.messages.append(user_msg)

    # --- emergencies: fixed replies, the model is never asked to improvise
    emergency = guardrails.detect_emergency(text)
    if emergency:
        stats["emergency"] += 1
        stats["intents"]["emergency"] += 1
        add_assistant(guardrails.EMERGENCY_REPLIES[emergency],
                      meta={"intent": "emergency", "confidence": "high", "model": "fixed safety reply"})
        return
    if guardrails.looks_like_injection(text):
        stats["injection"] += 1

    explicit_human = guardrails.wants_human(text)
    client = ai_client()

    # --- no AI available: offline knowledge-base answer
    if client is None:
        stats["offline"] += 1
        stats["intents"]["offline"] += 1
        if image_bytes or audio_file:
            add_assistant("Photo and voice checks need the AI service, which is off right now. Please describe the "
                          "problem in words, or call the Kisan Call Centre at **1800-180-1551**.",
                          meta={"intent": "offline", "confidence": "high", "model": "offline"})
        else:
            add_assistant(offline_reply(masked), meta={"intent": "offline", "confidence": "medium", "model": "offline",
                                                       "attempts": ["no GEMINI_API_KEY found in the app's Secrets"]})
        if explicit_human:
            _handoff("You asked to speak with a person.")
        return

    from google.genai import types
    history = to_contents(ss.messages[:-1])
    parts = []
    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
        parts.append(types.Part(text=prompts.DIAGNOSIS_TASK.format(note=masked or "(no note)")))
        schema = llm.Diagnosis
    else:
        if audio_file is not None:
            if audio_file.size > MAX_AUDIO_MB * 1024 * 1024:
                add_assistant("That recording is too long. Please keep voice questions under about 2 minutes.")
                return
            parts.append(types.Part.from_bytes(data=audio_file.getvalue(), mime_type="audio/wav"))
            parts.append(types.Part(text="The farmer's question is in this audio recording. "
                                         "Transcribe it into `transcript`, then answer it."
                                    + (f" They also typed: {masked}" if masked else "")))
        else:
            parts.append(types.Part(text=masked))
        schema = llm.ChatReply
    contents = history + [types.Content(role="user", parts=parts)]

    result = llm.generate(client, MODELS, system_prompt(), contents, schema)
    if result.attempts:
        stats["errors"].extend(result.attempts[-3:])

    if not result.ok:
        stats["offline"] += 1
        stats["intents"]["offline"] += 1
        reason = result.error or "The AI service did not respond."
        if image_bytes or audio_file:
            body = (f"{reason} Photo and voice checks need the AI, so please describe the problem in words or call "
                    "the Kisan Call Centre at **1800-180-1551**.")
        else:
            body = offline_reply(masked)
        add_assistant(body, meta={"intent": "offline", "confidence": "medium", "model": "offline",
                                  "attempts": result.attempts})
        _handoff("The AI could not answer just now.")
        return

    stats["models"][result.model] += 1
    if schema is llm.Diagnosis:
        dx = llm.normalise_diagnosis(result.data)
        stats["intents"]["diagnosis"] += 1
        llm_text = "Photo check result. " + dx["summary"] + " Possible causes: " + "; ".join(
            f"{c['name']} ({c['likelihood']})" for c in dx["possible_causes"])
        add_assistant("", kind="diagnosis", llm_text=llm_text,
                      meta={"dx": dx, "intent": "diagnosis", "sources": dx["sources"], "model": result.model,
                            "latency": result.latency_ms, "confidence": dx["possible_causes"][0]["likelihood"]
                            if dx["possible_causes"] else "low"})
        if dx["is_wheat"] and dx["needs_expert"]:
            _handoff("A photo is not enough to confirm this. Please get an expert to look at the field.")
        return

    r = llm.normalise_chat(result.data)
    if not r["answer"]:
        add_assistant(offline_reply(masked), meta={"intent": "offline", "model": "offline"})
        return
    if audio_file is not None and r["transcript"]:
        user_msg["content"] = "🎤 " + guardrails.mask_pii(r["transcript"])[0]
        user_msg["llm_text"] = r["transcript"]
    stats["intents"][r["intent"]] += 1
    if r["dose_redacted"]:
        stats["dose_redacted"] += 1
    add_assistant(r["answer"], meta={**r, "model": result.model, "latency": result.latency_ms})
    if explicit_human or r["needs_human"]:
        _handoff(r["handoff_reason"] or "You asked to speak with a person.")


def _handoff(reason: str):
    t = new_ticket()
    ss.stats["handoffs"] += 1
    ss.stats["intents"]["handoff"] += 1
    ss.messages.append({"role": "assistant", "kind": "handoff", "content": "", "meta": {"ticket": t, "reason": reason}})


def render_message(m: dict, is_last: bool, idx: int):
    avatar = "🧑‍🌾" if m["role"] == "user" else "🌾"
    with st.chat_message(m["role"], avatar=avatar):
        meta = m.get("meta", {})
        if m["kind"] == "handoff":
            st.markdown(ui.handoff_html(meta["ticket"], meta["reason"]), unsafe_allow_html=True)
            return
        if m.get("image"):
            st.image(m["image"], width=240)
        if m["kind"] == "diagnosis":
            st.markdown(ui.diagnosis_html(meta["dx"]), unsafe_allow_html=True)
        else:
            st.markdown(m["content"])  # model output is rendered as Markdown only (no raw HTML)
        if m["role"] == "user" and meta.get("pii"):
            st.caption("For your privacy, a number that looked like " + ", ".join(meta["pii"]) +
                       " was removed before sending.")
        if m["role"] == "assistant":
            bits = []
            if meta.get("intent"):
                bits.append(f'Topic <b>{INTENT_LABELS.get(meta["intent"], meta["intent"])}</b>')
            if meta.get("confidence"):
                bits.append(f'Confidence <b>{meta["confidence"]}</b>')
            if meta.get("model"):
                lat = f' in {meta["latency"] / 1000:.1f} s' if meta.get("latency") else ""
                bits.append(f'Answered by <b>{meta["model"]}</b>{lat}')
            if meta.get("dose_redacted"):
                bits.append("<b>A chemical dose was removed</b> (follow the label / KVK)")
            if bits:
                st.markdown('<div class="gg-meta">' + "&nbsp;&nbsp;&nbsp;".join(bits) + "</div>",
                            unsafe_allow_html=True)
            if meta.get("attempts") and meta.get("model") == "offline":
                st.caption("Why the AI did not answer: " + " | ".join(meta["attempts"][-3:]))
            srcs = meta.get("sources") or []
            if srcs:
                with st.popover(f"Sources used ({len(srcs)})"):
                    for sid in srcs:
                        e = kb.KB_BY_ID[sid]
                        st.markdown(f"**[{sid}] {e['title']}**\n\n{e['text']}")
                    st.caption(kb.SOURCE_NOTE)
            if is_last and meta.get("follow_up"):
                if st.button(f"Ask: {meta['follow_up']}", key=f"fu_{idx}"):
                    ss.pending = meta["follow_up"]
                    st.rerun()


SUGGESTIONS = {
    "pre": ["Which variety should I sow, and when?", "How do I manage paddy straw without burning?",
            "How much seed and fertiliser per acre?", "How should I treat seed before sowing?"],
    "early": ["When should I give the first irrigation?", "When should I spray for weeds?",
              "When do I apply the remaining urea?", "Some plants are drying in patches. Why?"],
    "mid": ["Leaves are turning yellow. Is it rust?", "Is this week's weather risky for my crop?",
            "How many more irrigations will the crop need?", "Should I irrigate before the rain?"],
    "late": ["How do I protect the grains from heat?", "Should I irrigate before strong wind?",
             "Some ears have black powder. What is it?", "Aphids on the ears: do I need to spray?"],
    "harvest": ["When should I harvest?", "How do I store the grain safely?",
                "What is today's mandi rate for wheat?", "Can I burn the wheat stubble?"],
}


def suggestion_group() -> str:
    k = stage.key
    if info["status"] == "not_sown":
        return "pre"
    if k in ("germination", "seedling", "cri"):
        return "early"
    if k in ("tillering", "jointing"):
        return "mid"
    if k in ("booting", "heading", "milk", "dough"):
        return "late"
    return "harvest"


# ============================================================ chat area

st.markdown("**Ask GehunGuru**")
if not ss.messages:
    sample = SAMPLES.get(ss.sample_pick)
    opts = list(SUGGESTIONS[suggestion_group()])
    if sample and sample.get("demo_question"):
        opts = [sample["demo_question"]] + opts[:3]
    cols = st.columns(2)
    for i, q in enumerate(opts):
        if cols[i % 2].button(q, key=f"sug_{i}", width="stretch"):
            ss.pending = q
            st.rerun()

for i, m in enumerate(ss.messages):
    render_message(m, i == len(ss.messages) - 1, i)

value = st.chat_input("Type your question, attach a leaf photo (+) or record your voice",
                      accept_file=True, file_type=["jpg", "jpeg", "png", "webp"], accept_audio=True,
                      submit_mode="disable", max_chars=guardrails.MAX_CHARS)

incoming = None
if ss.pending:
    incoming = (ss.pending, None, None)
    ss.pending = None
elif value:
    files = value.files if hasattr(value, "files") else []
    audio = getattr(value, "audio", None)
    incoming = (value.text if hasattr(value, "text") else str(value), files[0] if files else None, audio)

if incoming:
    text_in, img_in, audio_in = incoming
    with st.chat_message("user", avatar="🧑‍🌾"):
        st.markdown(text_in or ("(voice message)" if audio_in else "(photo)"))
    with st.chat_message("assistant", avatar="🌾"):
        with st.spinner("Checking your crop stage, weather and the knowledge base..."):
            handle_turn(text_in, img_in, audio_in)
    st.rerun()


# ============================================================ sidebar extras (need final state)

def summary_text() -> str:
    lines = ["GehunGuru advisory summary (AI-generated, please verify with your KVK)",
             f"Created: {datetime.now(IST):%d %b %Y %H:%M} IST"]
    if ss.ticket:
        lines.append(f"Reference: {ss.ticket}")
    lines += ["", "FARM", farm_context(), "", "WEATHER ALERTS"]
    lines += [f"- {a.title}: {a.message}" for a in alerts] or ["- none"]
    lines += ["", "CONVERSATION"]
    for m in ss.messages:
        who = "Farmer" if m["role"] == "user" else "GehunGuru"
        if m["kind"] == "handoff":
            lines.append(f"[{who}] Hand-off: {m['meta']['reason']} Kisan Call Centre 1800-180-1551.")
        else:
            lines.append(f"[{who}] {m.get('llm_text') or m['content']}")
    lines += ["", "Kisan Call Centre: 1800-180-1551 (free). Find your KVK: https://kvk.icar.gov.in"]
    return "\n".join(lines)


with summary_slot:
    st.download_button("Download chat summary", summary_text(), file_name="gehunguru_summary.txt",
                       mime="text/plain", width="stretch", disabled=not ss.messages)

with st.sidebar:
    with st.expander("Session insights"):
        s = ss.stats
        q = sum(1 for m in ss.messages if m["role"] == "user")
        st.markdown(f"Questions this session: **{q}** of {MAX_QUESTIONS_PER_SESSION}")
        st.markdown("Gemini API key: **" + ("found" if API_KEY else "not found in Secrets") + "**")
        if s["intents"]:
            st.markdown("Topics detected:\n" + "\n".join(
                f"- {INTENT_LABELS.get(k, k)}: {v}" for k, v in s["intents"].most_common()))
        st.markdown(
            f"Hand-offs to a human: **{s['handoffs']}**  \nOffline answers: **{s['offline']}**  \n"
            f"Numbers masked: **{s['pii']}**  \nEmergency replies: **{s['emergency']}**  \n"
            f"Injection attempts flagged: **{s['injection']}**  \nDoses removed: **{s['dose_redacted']}**")
        if s["models"]:
            st.markdown("Models used: " + ", ".join(f"{k} ({v})" for k, v in s["models"].items()))
        if s["errors"]:
            st.caption("Recent fallbacks: " + "; ".join(s["errors"][-4:]))
        st.caption(f"Prompt {prompts.PROMPT_VERSION}. Knowledge base: {len(kb.KB)} entries.")
    with st.expander("About and privacy"):
        st.markdown(
            "GehunGuru combines a fixed crop calendar, rule-based weather alerts and Google Gemini, grounded on a "
            f"{len(kb.KB)}-entry wheat knowledge base. Questions and photos go to the Gemini API; the free tier may "
            "use them to improve Google's products. Only the district's coordinates go to Open-Meteo. Nothing is "
            "stored after the session ends; download the summary if you want a copy.\n\n"
            f"_{kb.SOURCE_NOTE}_")
