"""A stand-in for the Gemini client, used ONLY in automated tests (GG_FAKE_LLM=1).

It returns canned, schema-shaped JSON so the UI and guardrails can be tested
without network access or an API key. It is never used when a real key exists.
"""

from __future__ import annotations

import json
from types import SimpleNamespace


def _last_user_text(contents) -> str:
    for c in reversed(contents):
        role = getattr(c, "role", None)
        if role == "user":
            texts = [getattr(p, "text", None) for p in c.parts]
            return " ".join(t for t in texts if t)
    return ""


def _has_image(contents) -> bool:
    c = contents[-1]
    for p in c.parts:
        inline = getattr(p, "inline_data", None)
        if inline is not None and str(getattr(inline, "mime_type", "")).startswith("image/"):
            return True
    return False


class _Models:
    def __init__(self, fail_models=()):
        self.fail_models = set(fail_models)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if model == "bad-key":
            from google.genai import errors
            raise errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                                     "message": "API key not valid. Please pass a valid API key."}})
        if model in self.fail_models:
            from google.genai import errors
            raise errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
        text = _last_user_text(contents).lower()
        if _has_image(contents):
            data = {
                "is_wheat": True, "image_quality": "good",
                "possible_causes": [
                    {"name": "Yellow (stripe) rust", "likelihood": "medium",
                     "visible_signs": "Yellow stripes along the veins on upper leaves.", "kb_id": "KB-10"},
                    {"name": "Nitrogen deficiency", "likelihood": "low",
                     "visible_signs": "General pale colour on older leaves.", "kb_id": "KB-21"},
                ],
                "field_checks": ["Rub a leaf on a white cloth: yellow powder means rust.",
                                 "Check whether lower leaves or upper leaves are affected first."],
                "actions": ["Walk the whole field today and mark patches.", "Call the KVK to confirm before any spray."],
                "urgency": "soon", "needs_expert": True,
                "summary": "The stripes could be yellow rust, but a photo alone cannot confirm it.",
                "sources": ["KB-10", "KB-21"],
            }
        elif "ignore" in text and "instruction" in text:
            data = {"answer": "I can only help with wheat farming questions.", "intent": "adversarial",
                    "confidence": "high", "sources": [], "needs_human": False, "handoff_reason": "",
                    "follow_up": "", "transcript": ""}
        elif "mandi" in text or "price" in text or "rate" in text:
            data = {"answer": "I don't give market prices. Please check agmarknet.gov.in or enam.gov.in.",
                    "intent": "out_of_scope", "confidence": "high", "sources": ["KB-24"], "needs_human": False,
                    "handoff_reason": "", "follow_up": "", "transcript": ""}
        elif "spray" in text or "dose" in text:
            data = {"answer": "For weeds, a herbicide such as clodinafop at 160 g per acre is used at 30-35 DAS.",
                    "intent": "weeds", "confidence": "medium", "sources": ["KB-09", "KB-99"],
                    "needs_human": False, "handoff_reason": "", "follow_up": "Which weeds do you see?",
                    "transcript": ""}
        else:
            data = {"answer": "Give the first irrigation at crown root initiation, about **21-25 days after sowing**. "
                              "Rain is forecast, so wait until after the rain.",
                    "intent": "irrigation", "confidence": "high", "sources": ["KB-08"], "needs_human": False,
                    "handoff_reason": "", "follow_up": "Do you want to know when to apply urea?", "transcript": ""}
        return SimpleNamespace(parsed=None, text=json.dumps(data), candidates=[])


class FakeClient:
    def __init__(self, fail_models=()):
        self.models = _Models(fail_models)
