"""Backup-provider tests with a simulated Groq API (no network needed)."""
import json
from types import SimpleNamespace

from core import llm
from core import knowledge_base as kb

OK_REPLY = {"answer": "Give the first irrigation now, after the rain.", "intent": "irrigation", "confidence": "high",
            "sources": ["KB-08"], "needs_human": False, "handoff_reason": "", "follow_up": "", "transcript": ""}


def fake_post(plan):
    """plan: model -> list of (status, payload) returned in order."""
    calls = []

    def post(url, json=None, headers=None, timeout=None, files=None, data=None):
        if url.endswith("/audio/transcriptions"):
            calls.append(("whisper", None))
            return SimpleNamespace(status_code=200, text="", json=lambda: {"text": "pehla paani kab lagana hai"})
        model = json["model"]
        calls.append((model, "response_format" in json))
        status, payload = plan[model].pop(0)
        body = {"choices": [{"message": {"content": payload}}]} if status == 200 else {"error": {"message": payload}}
        return SimpleNamespace(status_code=status, text=__import__("json").dumps(body), json=lambda: body)
    return post, calls


def test_groq_falls_back_on_429_then_succeeds(monkeypatch):
    post, calls = fake_post({"a": [(429, "rate limit")], "b": [(200, json.dumps(OK_REPLY))]})
    monkeypatch.setattr("requests.post", post)
    res = llm.groq_generate("k", ["a", "b"], "sys", [{"role": "user", "content": "q"}], llm.ChatReply)
    assert res.ok and res.model == "groq/b" and "rate limit" in res.attempts[0]


def test_groq_bad_key_is_fatal(monkeypatch):
    post, calls = fake_post({"a": [(401, "invalid api key")], "b": [(200, "{}")]})
    monkeypatch.setattr("requests.post", post)
    res = llm.groq_generate("k", ["a", "b"], "sys", [], llm.ChatReply)
    assert not res.ok and res.fatal and [c[0] for c in calls] == ["a"]


def test_groq_retries_without_json_mode(monkeypatch):
    post, calls = fake_post({"a": [(400, "json_validate_failed"), (200, "Sure:\n" + json.dumps(OK_REPLY))]})
    monkeypatch.setattr("requests.post", post)
    res = llm.groq_generate("k", ["a"], "sys", [], llm.ChatReply)
    assert res.ok and calls == [("a", True), ("a", False)]


def test_groq_whisper(monkeypatch):
    post, calls = fake_post({})
    monkeypatch.setattr("requests.post", post)
    text, err = llm.groq_transcribe("k", b"RIFF....")
    assert text == "pehla paani kab lagana hai" and err is None


def test_select_for_is_small_and_relevant():
    picked = kb.select_for("पत्तों पर पीली धारियां", "jointing")
    ids = [e["id"] for e in picked]
    assert "KB-10" in ids and "KB-23" in ids and len(ids) <= 9
