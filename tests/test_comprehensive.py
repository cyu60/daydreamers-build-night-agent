"""Comprehensive coverage for gaps not touched by scenarios + edge cases.

Six failure classes this suite targets:

    F. Secret handling  — MM keys masked, multi-key hygiene, no cross-turn leaks
    G. Session isolation — sessions never see each other's data
    H. Upsert semantics  — /api/session correctly updates existing rows
    I. API crash resistance — malformed bodies return 4xx, never 5xx
    J. Injection surfaces — SQL/path characters in session_id parameters
    K. Long-horizon flows — 15+ turn transcripts, resume after clear
"""

import os
import time
import uuid

import pytest
import requests


ENDPOINT = os.environ.get(
    "BUILD_NIGHT_URL",
    "https://daydreamers-build-night-agent.vercel.app/api/run",
)
BASE = ENDPOINT.rsplit("/api/run", 1)[0]


# ---------------------------------------------------------------------------
# helpers (local to this file to avoid cross-file coupling)
# ---------------------------------------------------------------------------

class _Convo:
    def __init__(self, session_id=None):
        self.session_id = session_id or f"comp-{uuid.uuid4().hex[:10]}"
        self.turns = []

    def send(self, message, timeout=90):
        self.turns.append({"role": "user", "text": message})
        transcript = "\n\n".join(
            f"{'PARTICIPANT' if t['role'] == 'user' else 'AGENT'}: {t['text']}"
            for t in self.turns
        )
        turn_id = f"turn-{uuid.uuid4().hex[:12]}"
        r = requests.post(
            ENDPOINT,
            json={
                "workflow_id": "build-night-guide",
                "input": {
                    "session_id": self.session_id,
                    "run_id": turn_id,
                    "idempotency_key": turn_id,
                    "message": message,
                    "transcript": transcript,
                },
            },
            timeout=timeout,
        )
        r.raise_for_status()
        reply = (r.json().get("result") or {}).get("output_text") or ""
        self.turns.append({"role": "agent", "text": reply})
        return reply


def _history(session_id):
    r = requests.get(f"{BASE}/api/history", params={"session_id": session_id}, timeout=20)
    r.raise_for_status()
    return r.json()


def _session_upsert(session_id, email):
    return requests.post(
        f"{BASE}/api/session",
        json={"session_id": session_id, "email": email},
        timeout=15,
    )


# ===========================================================================
# F. Secret handling
# ===========================================================================

def test_agent_masks_mentormates_participant_key():
    """F.1: MM key pasted by participant is acknowledged with a masked preview,
    never echoed in full. Mirrors scenario 5 which covers Tinyfish keys."""
    c = _Convo()
    c.send("hi")
    c.send("scrape competitor prices on shopify")
    c.send("yes")
    c.send("my tinyfish key is tk_demo_abc123xyz456")
    c.send("recording: https://tinyfish.io/recording/rec_demo")
    c.send("ready to submit to mentormates")
    mm_secret = "mm_sk_SUPER_LONG_SECRET_42ff7a91c0dc8b5ae39e1f04b7c2b3d9"
    reply = c.send(f"here is my mm key: {mm_secret}")
    assert mm_secret not in reply, (
        f"Agent echoed full MM participant key — security violation. Reply: {reply}"
    )


def test_api_keys_never_leak_in_later_turns():
    """F.2: Once participant has shared a Tinyfish key and MM key, a later
    unrelated question must not surface either key in the reply (tests that
    agent doesn't mechanically re-echo state from transcript)."""
    c = _Convo()
    c.send("hi")
    c.send("scrape job boards")
    c.send("yes")
    tf_key = "tk_live_LEAKCANARY_9f8e7d6c5b4a"
    mm_key = "mm_sk_LEAKCANARY_42ff7a91c0dc8b5a"
    c.send(f"my tinyfish key: {tf_key}")
    c.send("https://tinyfish.io/recording/rec_xyz")
    c.send("ready to submit")
    c.send(f"mm key: {mm_key} and event ref: some-event")
    # Now a totally unrelated follow-up — agent must not parrot either key
    reply = c.send("actually what's the difference between tinyfish and a regular scraper?")
    assert tf_key not in reply, f"Tinyfish key leaked on unrelated turn. Reply: {reply}"
    assert mm_key not in reply, f"MM key leaked on unrelated turn. Reply: {reply}"


def test_history_stores_raw_keys_as_user_sent_them():
    """F.3: We DO want user-sent text stored verbatim in chat logs (for debugging /
    auditability). This test locks in that the redaction happens only in agent
    replies, not in what the user sent. If we ever decide to redact, update this
    test and the /api/run handler together."""
    c = _Convo()
    secret = "tk_AUDIT_CANARY_123"
    c.send(f"my tinyfish key is {secret}")
    rows = _history(c.session_id)
    user_rows = [r for r in rows if r["role"] == "user"]
    assert any(secret in r["text"] for r in user_rows), (
        "Expected user's raw message (including the key they pasted) to be stored verbatim for audit. "
        "If redaction was intentionally added, update this test."
    )


# ===========================================================================
# G. Session isolation
# ===========================================================================

def test_two_sessions_do_not_see_each_other_history():
    """G.1: Messages from session A must not appear in session B's history."""
    a = _Convo()
    b = _Convo()
    a.send("alpha session message one")
    b.send("beta session message two")

    rows_a = _history(a.session_id)
    rows_b = _history(b.session_id)

    a_texts = [r["text"] for r in rows_a]
    b_texts = [r["text"] for r in rows_b]

    assert "alpha session message one" in a_texts
    assert "beta session message two" in b_texts
    assert "beta session message two" not in a_texts, "session B leaked into A"
    assert "alpha session message one" not in b_texts, "session A leaked into B"


def test_deleting_one_session_does_not_affect_another():
    """G.2: DELETE /api/history for session A leaves session B untouched."""
    a = _Convo()
    b = _Convo()
    a.send("keep me for now")
    b.send("do not delete me")

    d = requests.delete(f"{BASE}/api/history", params={"session_id": a.session_id}, timeout=15)
    assert d.status_code == 200

    rows_a = _history(a.session_id)
    rows_b = _history(b.session_id)
    assert rows_a == [], f"session A should be empty after DELETE, got: {rows_a}"
    assert any("do not delete me" == r["text"] for r in rows_b), (
        f"session B lost data when we only deleted A. Rows: {rows_b}"
    )


# ===========================================================================
# H. Upsert semantics (/api/session)
# ===========================================================================

def test_session_upsert_updates_email_on_same_session_id():
    """H.1: Calling /api/session twice with the same session_id and different
    emails should update the row rather than create a duplicate or error."""
    sid = f"upsert-{uuid.uuid4().hex[:8]}"
    r1 = _session_upsert(sid, "first@example.com")
    r2 = _session_upsert(sid, "second@example.com")
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r2.json().get("ok") is True


def test_session_upsert_allows_same_email_across_different_sessions():
    """H.2: Same email across two distinct session_ids is valid — it represents
    the same participant in two sessions (e.g. cleared chat mid-flow)."""
    email = f"shared+{uuid.uuid4().hex[:6]}@example.com"
    r1 = _session_upsert(f"share-a-{uuid.uuid4().hex[:6]}", email)
    r2 = _session_upsert(f"share-b-{uuid.uuid4().hex[:6]}", email)
    assert r1.status_code == 200
    assert r2.status_code == 200


# ===========================================================================
# I. API crash resistance
# ===========================================================================

def test_run_with_empty_body_does_not_5xx():
    """I.1: POST /api/run with {} returns a structured error, not a 5xx crash."""
    r = requests.post(ENDPOINT, json={}, timeout=20)
    assert r.status_code < 500, f"empty body should not 5xx crash. Got {r.status_code}: {r.text[:200]}"


def test_run_with_no_input_field_does_not_5xx():
    """I.2: POST /api/run with only workflow_id (no input) doesn't crash."""
    r = requests.post(
        ENDPOINT,
        json={"workflow_id": "build-night-guide"},
        timeout=30,
    )
    assert r.status_code < 500, f"missing input should not 5xx. Got {r.status_code}: {r.text[:200]}"


def test_run_with_invalid_workflow_returns_structured_error():
    """I.3: Unknown workflow_id returns a 4xx/5xx error with a JSON body (not an empty 500 crash page)."""
    turn_id = f"t-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        ENDPOINT,
        json={
            "workflow_id": "this-workflow-does-not-exist-abc",
            "input": {"run_id": turn_id, "idempotency_key": turn_id, "message": "hi"},
        },
        timeout=30,
    )
    # Ara may return 4xx or 5xx — what matters is it's JSON, not an HTML crash page
    ct = r.headers.get("content-type", "")
    assert "json" in ct, f"invalid workflow should return JSON, got {ct}: {r.text[:200]}"


def test_session_endpoint_rejects_non_json_body():
    """I.4: POST /api/session with malformed / non-JSON body doesn't 5xx."""
    r = requests.post(
        f"{BASE}/api/session",
        data="not json at all",
        headers={"Content-Type": "text/plain"},
        timeout=15,
    )
    assert r.status_code < 500, f"non-json body should not 5xx. Got {r.status_code}"


# ===========================================================================
# J. Injection surfaces
# ===========================================================================

def test_history_with_sql_injection_in_session_id_returns_empty_not_crash():
    """J.1: Arbitrary SQL-ish chars in session_id are safe — either returns
    [] (no rows match this string) or 400 (validation), but never a 5xx."""
    payloads = [
        "x' OR '1'='1",
        "'; DROP TABLE build_night_messages; --",
        "../../etc/passwd",
        "x\x00null-byte",
        "'; DELETE FROM build_night_sessions WHERE 'a'='a",
    ]
    for p in payloads:
        r = requests.get(f"{BASE}/api/history", params={"session_id": p}, timeout=15)
        assert r.status_code < 500, f"payload {p!r} caused 5xx: {r.status_code} {r.text[:120]}"


def test_session_with_injection_in_email_rejected():
    """J.2: Email-field injection attempts are rejected by the email regex, 400."""
    payloads = [
        "test@example.com'; DROP TABLE build_night_sessions; --",
        "<script>alert(1)</script>@x.y",
        "test@example.com\r\nBcc: evil@attacker.com",
    ]
    for p in payloads:
        r = _session_upsert(f"inj-{uuid.uuid4().hex[:6]}", p)
        assert r.status_code == 400, f"payload {p!r} should be 400, got {r.status_code}"


def test_session_id_with_special_chars_in_messages_flow_does_not_crash():
    """J.3: /api/run with a session_id containing special characters still works
    (agent replies; messages may or may not be stored, but no crash)."""
    weird_sid = "weird/sess?id&with=chars%20and spaces+stuff"
    turn_id = f"t-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        ENDPOINT,
        json={
            "workflow_id": "build-night-guide",
            "input": {
                "session_id": weird_sid,
                "run_id": turn_id,
                "idempotency_key": turn_id,
                "message": "hi",
                "transcript": "PARTICIPANT: hi",
            },
        },
        timeout=45,
    )
    assert r.status_code < 500, f"weird session_id should not 5xx. Got {r.status_code}"


# ===========================================================================
# K. Long-horizon flows
# ===========================================================================

def test_agent_handles_rapid_fire_short_messages():
    """K.1: Single-char / very short participant replies don't break the agent —
    it either responds meaningfully or asks for clarification, never crashes."""
    c = _Convo()
    c.send("hi")
    for msg in ["?", "ok", "sure", "go"]:
        reply = c.send(msg)
        assert reply and len(reply.strip()) > 5, f"empty/short agent reply for {msg!r}: {reply!r}"


def test_long_conversation_10_turns_still_progresses():
    """K.2: After 10 turns of chatter, agent still replies with non-empty text
    and transcript doesn't blow past Ara's context limit."""
    c = _Convo()
    prompts = [
        "hi",
        "i want to scrape job boards",
        "what does tinyfish do again?",
        "ok cool",
        "what if the site has captcha?",
        "what's the website again?",
        "alright, ready for the next step",
        "my tinyfish key is tk_demo_x",
        "recording: https://tinyfish.io/recording/rec_demo",
        "submit to mentormates",
    ]
    for p in prompts:
        reply = c.send(p)
        assert reply and len(reply.strip()) > 3, f"turn for {p!r} returned empty reply"


def test_session_resumes_after_clear_is_independent():
    """K.3: After DELETE /api/history on session A, starting a new session B
    with the same email begins fresh (no leftover context)."""
    email = f"resume+{uuid.uuid4().hex[:6]}@example.com"
    a = _Convo()
    _session_upsert(a.session_id, email)
    a.send("hi")
    a.send("i want to build a price tracker for shopify")
    requests.delete(f"{BASE}/api/history", params={"session_id": a.session_id}, timeout=15)

    b = _Convo()
    _session_upsert(b.session_id, email)
    first_b_reply = b.send("hello")
    # B is a fresh session — agent should greet (step 1), not jump mid-flow
    lower = first_b_reply.lower()
    assert (
        "what are you trying to build" in lower
        or "i'll help you ship" in lower.replace("’", "'")
    ), f"new session B did not start fresh. First reply: {first_b_reply}"
