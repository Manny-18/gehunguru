"""
Deterministic guardrails that run BEFORE anything is sent to the AI model.

1. validate_message  - empty / too long input
2. mask_pii          - phone, Aadhaar, bank-account-like numbers are masked
3. detect_emergency  - pesticide poisoning or distress -> fixed, safe reply
                       (the model is NOT asked to improvise in an emergency)
4. wants_human       - farmer explicitly asks for a person -> handoff card
5. looks_like_injection - prompt-injection attempt (logged + shown in insights;
                       the system prompt also tells the model to refuse)
"""

from __future__ import annotations

import re

MAX_CHARS = 1000

# ---------------------------------------------------------------- validation


def validate_message(text: str) -> tuple[bool, str]:
    t = (text or "").strip()
    if not t:
        return False, "Please type a question, record your voice, or attach a leaf photo."
    if len(t) > MAX_CHARS:
        return False, f"Please keep your question under {MAX_CHARS} characters (yours has {len(t)})."
    return True, ""


# ---------------------------------------------------------------- PII masking

_AADHAAR = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_LONG_NUMBER = re.compile(r"(?<!\d)\d{9,18}(?!\d)")  # bank account numbers etc.
# numbers we publish ourselves must never be masked
_ALLOWED = {"18001801551", "1800-180-1551", "14416"}


def mask_pii(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def _sub(pattern: re.Pattern, label: str, s: str) -> str:
        def repl(m: re.Match) -> str:
            raw = m.group(0)
            if raw.replace(" ", "") in _ALLOWED or raw in _ALLOWED:
                return raw
            found.append(label)
            return f"[{label} removed]"
        return pattern.sub(repl, s)

    out = _sub(_AADHAAR, "ID number", text)
    out = _sub(_PHONE, "phone number", out)
    out = _sub(_LONG_NUMBER, "account number", out)
    return out, sorted(set(found))


# ---------------------------------------------------------------- emergencies

_POISON = [
    "poison", "poisoning", "swallowed", "drank pesticide", "drank the spray", "fainted after spray",
    "dizzy after spray", "vomiting after spray", "zeher", "zehar", "jahar", "जहर", "ज़हर", "ज़हरीला",
    "दवाई पी", "दवा पी ली", "dawai pi", "dawa pee", "spray ke baad chakkar", "छिड़काव के बाद चक्कर",
    "ਜ਼ਹਿਰ", "ਜ਼ਹਰ",
]
_DISTRESS = [
    "suicide", "kill myself", "end my life", "want to die", "no reason to live",
    "khudkushi", "khud kushi", "atmahatya", "aatmhatya", "jaan de dunga", "jaan de doonga", "mar jaunga",
    "आत्महत्या", "खुदकुशी", "जान दे दूंगा", "मर जाऊंगा", "ਖੁਦਕੁਸ਼ੀ", "ਆਤਮ ਹੱਤਿਆ",
]

EMERGENCY_REPLIES = {
    "poisoning": (
        "**This may be pesticide poisoning. Act now:**\n\n"
        "1. Call **108** (ambulance) or **112** immediately, or take the person to the nearest hospital/PHC.\n"
        "2. Take the pesticide bottle or label with you so the doctor knows the chemical.\n"
        "3. Move the person to fresh air, remove contaminated clothes, and wash the skin with soap and plenty of water.\n"
        "4. Do not make the person vomit unless a doctor tells you to.\n\n"
        "I am an AI farm assistant and cannot give medical treatment advice.\n\n"
        "**यह कीटनाशक ज़हर का मामला हो सकता है। तुरंत 108 या 112 पर फ़ोन करें और दवा की बोतल साथ लेकर अस्पताल जाएँ।**"
    ),
    "distress": (
        "I'm really sorry you're going through this. You don't have to face it alone.\n\n"
        "Please talk to someone right now: **Tele-MANAS 14416** (free, 24x7, in Hindi, Punjabi and other "
        "languages), or call **112** if you are in immediate danger. A family member, friend or sarpanch can "
        "also sit with you.\n\n"
        "Crop losses and debt feel crushing, but there is help, including crop insurance claims and relief "
        "schemes. When you're ready, I can help with the farm side, and the Kisan Call Centre (1800-180-1551) "
        "can connect you to officials.\n\n"
        "**आप अकेले नहीं हैं। अभी Tele-MANAS 14416 पर बात करें (मुफ़्त, 24 घंटे)। तुरंत खतरा हो तो 112 पर कॉल करें।**"
    ),
}


def detect_emergency(text: str) -> str | None:
    t = (text or "").lower()
    if any(k in t for k in _DISTRESS):
        return "distress"
    if any(k in t for k in _POISON):
        return "poisoning"
    return None


# ---------------------------------------------------------------- handoff intent

_HUMAN = [
    "talk to a human", "talk to human", "real person", "human expert", "speak to someone", "please call me",
    "agriculture officer", "talk to officer", "connect me", "insaan se baat", "kisi se baat", "officer se baat",
    "expert se baat", "इंसान से बात", "अधिकारी से बात", "विशेषज्ञ से बात", "ਕਿਸੇ ਨਾਲ ਗੱਲ", "ਅਫ਼ਸਰ ਨਾਲ ਗੱਲ",
]


def wants_human(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _HUMAN)


# ---------------------------------------------------------------- prompt injection

_INJECTION = [
    "ignore previous", "ignore all previous", "ignore your instructions", "ignore the above",
    "disregard your", "forget your instructions", "system prompt", "reveal your prompt", "you are now",
    "pretend to be", "developer mode", "jailbreak", "dan mode", "new instructions",
    "apne instructions bhool", "नियम भूल", "निर्देश भूल",
]


def looks_like_injection(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _INJECTION)
