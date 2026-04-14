"""Integration tests against the deployed build-night-guide on Ara.

These hit the real /api/run endpoint on Vercel, which proxies to Ara.
They assert the agent behaves correctly across multi-turn conversations:
greets exactly once, progresses through steps, and doesn't loop.

Run: pytest tests/test_live_conversation.py -v
Set BUILD_NIGHT_URL to override the default endpoint.
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


class Conversation:
    """Simulates a participant having a multi-turn chat with the agent."""

    def __init__(self):
        self.session_id = f"test-session-{uuid.uuid4().hex[:12]}"
        self.turns = []  # list of {role, text}

    def send(self, message: str, timeout: int = 45) -> str:
        self.turns.append({"role": "user", "text": message})
        transcript = "\n\n".join(
            f"{'PARTICIPANT' if t['role'] == 'user' else 'AGENT'}: {t['text']}"
            for t in self.turns
        )
        turn_id = f"turn-{uuid.uuid4().hex[:12]}"
        resp = requests.post(
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
        resp.raise_for_status()
        data = resp.json()
        reply = (
            (data.get("result") or {}).get("output_text")
            or data.get("output_text")
            or ""
        )
        assert reply, f"Empty agent reply. Raw response: {data}"
        self.turns.append({"role": "agent", "text": reply})
        return reply


@pytest.fixture
def convo():
    return Conversation()


GREETING_PHRASE = "i'll help you ship a tinyfish project"


def test_scenario_1_first_turn_greets_and_asks_intent(convo):
    """Scenario 1: fresh session, first message — agent greets and asks what they're building."""
    reply = convo.send("hi")
    lower = reply.lower()
    assert GREETING_PHRASE in lower or "what are you" in lower or "trying to build" in lower, (
        f"First reply should greet and ask intent. Got: {reply}"
    )


def test_scenario_2_second_turn_does_not_re_greet(convo):
    """Scenario 2: after the greeting, sending a message must NOT trigger the greeting again."""
    convo.send("hi")
    second = convo.send("I don't know, can you give me some ideas?")
    assert GREETING_PHRASE not in second.lower(), (
        f"Agent re-greeted on turn 2 — session continuity broken. Got: {second}"
    )


def test_scenario_3_suggests_concrete_ideas_when_stuck(convo):
    """Scenario 3: participant asks for ideas — agent returns 2+ concrete build suggestions."""
    convo.send("hi")
    reply = convo.send("I don't know, can you give me some ideas?")
    idea_keywords = [
        "scrape", "scraping", "scraper",
        "monitor", "track", "watch",
        "extract", "lead", "price",
        "job", "form", "directory", "dashboard",
    ]
    matches = [k for k in idea_keywords if k in reply.lower()]
    assert len(matches) >= 2, (
        f"Agent should offer concrete Tinyfish ideas (scraping, monitoring, extraction, etc). "
        f"Matched only: {matches}. Reply: {reply}"
    )


def test_scenario_4_advances_to_tinyfish_teaching_after_clear_intent(convo):
    """Scenario 4: participant gives a clear intent — next turn, agent explains Tinyfish and asks for the API key."""
    convo.send("hi")
    convo.send("I want to scrape Y Combinator's job board for AI startup listings")
    reply = convo.send("that sounds great, let's do that")
    lower = reply.lower()
    mentions_tinyfish = "tinyfish" in lower
    asks_for_key = "api key" in lower or "api-key" in lower or "tinyfish.io" in lower
    assert mentions_tinyfish and asks_for_key, (
        f"After intent is confirmed, agent should explain Tinyfish and ask for the API key. "
        f"Got: {reply}"
    )


def test_scenario_5_masks_tinyfish_api_key_in_reply(convo):
    """Scenario 5: participant pastes a Tinyfish API key — agent acknowledges without echoing the full key."""
    convo.send("hi")
    convo.send("scrape product reviews from Amazon for a list of URLs")
    convo.send("yes, that's what I want to build")
    secret = "tk_SUPER_SECRET_DO_NOT_ECHO_9f8e7d6c"
    reply = convo.send(f"here is my tinyfish key: {secret}")
    assert secret not in reply, (
        f"Agent echoed the full API key back — security violation. Reply: {reply}"
    )


def test_scenario_6_explains_how_to_find_tinyfish_api_key(convo):
    """Scenario 6: participant asks where to find their Tinyfish key — agent gives concrete directions."""
    convo.send("hey")
    reply = convo.send("wait, how do I find my API key on Tinyfish?")
    lower = reply.lower()
    mentions_site = "tinyfish.io" in lower or "tinyfish" in lower
    mentions_location = any(
        kw in lower
        for kw in ["dashboard", "settings", "api key", "api section", "log in", "sign in", "account"]
    )
    assert mentions_site and mentions_location, (
        f"Agent should tell participant to go to Tinyfish and point to dashboard/settings. "
        f"Got: {reply}"
    )


def test_scenario_7_returns_tinyfish_website_when_asked(convo):
    """Scenario 7: participant asks for the Tinyfish website URL."""
    convo.send("hey")
    reply = convo.send("what's the website for tinyfish?")
    assert "tinyfish.io" in reply.lower(), (
        f"Agent should share tinyfish.io when asked for the website. Got: {reply}"
    )


def test_scenario_8_lists_multiple_tinyfish_use_cases(convo):
    """Scenario 8: participant asks what Tinyfish can actually do — agent lists 3+ concrete use cases."""
    convo.send("hey")
    reply = convo.send("what can I actually build with Tinyfish? give me some real examples")
    lower = reply.lower()
    use_case_keywords = [
        "scrape", "scraping",
        "monitor", "track",
        "extract", "lead", "leads",
        "price", "pricing",
        "job", "application",
        "form", "fill",
        "review",
        "dashboard",
        "directory",
    ]
    matches = set()
    for kw in use_case_keywords:
        if kw in lower:
            matches.add(kw)
    assert len(matches) >= 3, (
        f"Agent should list at least 3 distinct Tinyfish use cases. Matched: {matches}. Reply: {reply}"
    )


def test_scenario_9_ideation_to_selection_flow(convo):
    """Scenario 9: participant picks one of the agent's suggested ideas — agent moves to the Tinyfish-key step."""
    convo.send("hey")
    ideas_reply = convo.send("give me some ideas, i don't know what to build")
    # Participant picks something plausible regardless of the exact ideas returned
    picked = "let's do the price monitoring one — track competitor prices on shopify"
    reply = convo.send(picked)
    lower = reply.lower()
    advances = "api key" in lower or "tinyfish.io" in lower or "paste" in lower
    assert advances, (
        f"After the participant picks an idea, agent should advance to collecting the Tinyfish key. "
        f"Got: {reply}"
    )


def test_scenario_10_never_claims_mm_submission_without_project_id(convo):
    """Scenario 10 (regression): agent MUST NOT claim a MentorMates submission succeeded
    unless the reply contains a real MM project URL or project ID.

    Protects against the hallucination we caught in the walkthrough where the agent
    cheerfully said 'successfully submitted' without actually calling the MM API.
    """
    convo.send("hi")
    convo.send("build a scraper for Y Combinator job listings")
    convo.send("yes")
    convo.send("my tinyfish key is tk_fake_abc123xyz456")
    convo.send("recording url: https://tinyfish.io/recording/rec_fake_zzz")
    convo.send("ready to submit to mentormates")
    reply = convo.send(
        "my mm key is mmpk_fake_doesnotexist and event ref is fake-event-that-does-not-exist"
    )
    lower = reply.lower()
    claims_success = any(
        phrase in lower
        for phrase in [
            "successfully submitted",
            "project has been submitted",
            "submission complete",
            "submitted your project",
            "project was submitted",
        ]
    )
    has_evidence = (
        "mentormates.ai/projects/" in lower
        or "proj_" in lower
        or "project id" in lower
        or "project_id" in lower
    )
    if claims_success:
        assert has_evidence, (
            "Agent claimed MM submission succeeded but did NOT include a project URL or ID. "
            f"This is the hallucination bug. Reply: {reply}"
        )


def test_scenario_11_chat_history_persists_to_insforge():
    """Scenario 11: every turn (user + agent) is stored to Insforge via /api/history.

    Protects the Insforge backend integration: the chat log table must reflect
    what the participant sent and what the agent replied, in order, per session.
    """
    convo = Conversation()
    msgs = ["hi", "i want to monitor competitor pricing on shopify"]
    for m in msgs:
        convo.send(m)

    resp = requests.get(
        f"{BASE}/api/history",
        params={"session_id": convo.session_id},
        timeout=20,
    )
    resp.raise_for_status()
    rows = resp.json()
    assert isinstance(rows, list), f"/api/history should return a list. Got: {rows!r}"
    assert len(rows) == len(msgs) * 2, (
        f"Expected {len(msgs) * 2} stored messages (user+agent per turn), got {len(rows)}: "
        f"{[(r.get('role'), r.get('text', '')[:40]) for r in rows]}"
    )

    # Alternating roles, user messages match what we sent, in order
    user_rows = [r for r in rows if r["role"] == "user"]
    agent_rows = [r for r in rows if r["role"] == "agent"]
    assert len(user_rows) == len(msgs), f"expected {len(msgs)} user rows, got {len(user_rows)}"
    assert len(agent_rows) == len(msgs), f"expected {len(msgs)} agent rows, got {len(agent_rows)}"
    for sent, stored in zip(msgs, user_rows):
        assert stored["text"] == sent, f"user message mismatch: sent={sent!r} stored={stored['text']!r}"
    for stored in agent_rows:
        assert stored["text"] and len(stored["text"]) > 5, (
            f"agent row has empty/too-short text: {stored}"
        )


def test_scenario_13_surfaces_tinyfish_demo_video_when_stuck(convo):
    """Scenario 13: when participant signals confusion about Tinyfish ('I'm stuck', 'I don't get it',
    'walk me through'), agent proactively shares the Tinyfish demo video."""
    convo.send("hey")
    reply = convo.send("i'm stuck, i don't really get how tinyfish works, can you walk me through it?")
    expected_host = "nsxcypmjpizdjxrdncpe.supabase.co"
    expected_path = "build-nights-demo"
    assert expected_host in reply and expected_path in reply, (
        f"Agent should share the Tinyfish build-night demo video when participant is stuck. Got: {reply}"
    )


def test_scenario_16_accepts_sk_tinyfish_prefix(convo):
    """Scenario 16 (regression from live case study 2026-04-13 18:53): real Tinyfish keys
    are `sk-tinyfish-<chars>`, NOT `tk_`. Agent must acknowledge them and mask by
    last few chars, never falsifying a `tk_` prefix."""
    convo.send("hi")
    convo.send("scrape a webpage for me")
    convo.send("yes")
    secret = "sk-tinyfish-_uoPRPk_AJzxUlJsvkScgBXKcqcxST-z"
    reply = convo.send(secret)
    assert secret not in reply, f"Agent echoed full key: {reply}"
    lower = reply.lower()
    assert "tk_" not in reply, f"Agent falsified tk_ prefix on an sk-tinyfish- key: {reply}"
    assert any(tok in lower for tok in ["got it", "thanks", "received", "key ending", "...qcxst-z"]), (
        f"Agent should acknowledge the sk-tinyfish- key was received. Got: {reply}"
    )


def test_scenario_17_parses_url_and_goal_from_single_message(convo):
    """Scenario 17 (regression from case study): participant provides URL AND goal in
    one message — agent should not re-ask for either."""
    convo.send("hi")
    convo.send("i want to understand a website")
    convo.send("yes")
    convo.send("sk-tinyfish-abcdefghij_1234567890ABCDEFGHIJ")
    reply = convo.send(
        "https://daydreamers-build-night-agent.vercel.app — give me an overview of what this site does"
    )
    lower = reply.lower()
    asks_for_goal_again = any(
        p in lower for p in ["please provide a goal", "please provide a one-sentence goal", "what would you like to extract"]
    )
    assert not asks_for_goal_again, (
        f"Agent re-asked for the goal even though it was provided in the same message. Reply: {reply}"
    )


def test_scenario_18_extracts_key_from_pasted_doc_blob(convo):
    """Scenario 18 (regression): participant pastes a shell export line or docs blob
    containing the MM key — agent extracts it, doesn't re-ask."""
    convo.send("hi")
    convo.send("scrape a website for product info")
    convo.send("yes")
    convo.send("sk-tinyfish-my_real_tinyfish_key_abc123xyz456")
    convo.send("https://example.com — list product names and prices")
    # Simulate the Tinyfish run outcome that frontend would normally inject
    convo.send("TINYFISH_RESULT: {\"products\":[{\"name\":\"Widget\",\"price\":\"$9.99\"}]}")
    convo.send("ready to submit")
    blob = (
        "# MentorMates Developer API\n\n"
        "### Set env vars\n"
        "export MENTORMATES_PARTICIPANT_API_KEY=\"mm_sk_ABCDEF1234567890abcdef1234567890CASE_STUDY_KEY_ffffffff\"\n\n"
        "### 3. Install the skill\n"
        "/plugin marketplace add edumame/mentormates-marketplace"
    )
    reply = convo.send(blob)
    lower = reply.lower()
    reasks_key = any(
        p in lower for p in [
            "please paste your mentor mates participant api key",
            "please provide your mentor mates participant api key",
            "can you provide your mentor mates participant api key",
            "share your mentor mates participant api key",
        ]
    )
    assert not reasks_key, (
        "Agent should extract the mm_sk_ key from the pasted blob, not re-ask. "
        f"Reply: {reply}"
    )


def test_scenario_19_no_tinyfish_failure_claim_without_error_in_transcript(convo):
    """Scenario 19 (regression from case study): agent said 'there was an issue with
    the Tinyfish run' but no TINYFISH_ERROR was ever in the transcript. Ban that."""
    convo.send("hi")
    convo.send("scrape a site")
    convo.send("yes")
    convo.send("sk-tinyfish-examplekey_abcdef1234567890xyz")
    convo.send("https://example.com — list all links on the page")
    reply = convo.send("ok")
    lower = reply.lower()
    claims_issue = any(
        p in lower for p in [
            "there was an issue with the tinyfish",
            "tinyfish run failed",
            "the run errored",
            "tinyfish ran into",
            "the automation failed",
        ]
    )
    assert not claims_issue, (
        "Agent claimed a Tinyfish failure without any TINYFISH_ERROR in the transcript — "
        f"hallucination. Reply: {reply}"
    )


def test_scenario_20_marker_accompanies_run_promise(convo):
    """Scenario 20: if agent says it will run Tinyfish, the reply MUST contain the
    <<TINYFISH_RUN ...>> marker. Prevents 'I'll run it!' + no marker = no run."""
    convo.send("hi")
    convo.send("scrape a website for headline text")
    convo.send("yes")
    convo.send("sk-tinyfish-my-key-abcdef1234567890xyz")
    convo.send("https://example.com — extract all h1 headings")
    reply = convo.send("go")
    lower = reply.lower()
    promises_run = any(p in lower for p in ["let's run", "i'll run", "running now", "kicking off", "setting up"])
    has_marker = "<<TINYFISH_RUN" in reply
    if promises_run:
        assert has_marker, (
            "Agent promised to run Tinyfish but did NOT emit the <<TINYFISH_RUN ...>> marker "
            f"in the same reply. Frontend can't execute. Reply: {reply}"
        )


def test_scenario_15_emits_tinyfish_run_marker_when_inputs_collected(convo):
    """Scenario 15: once the agent has Tinyfish API key + target URL + goal, it emits
    the <<TINYFISH_RUN url="..." goal="...">> marker that the frontend intercepts
    to actually invoke the Tinyfish API."""
    convo.send("hi")
    convo.send("scrape product names and prices from an ecommerce page")
    convo.send("yes that's the plan")
    convo.send("my tinyfish key is tk_demo_test_9f8e7d6c5b4a3f2e")
    convo.send("target url: https://example.com/products, goal: extract all product names and prices as json")
    # Agent should emit the marker now that it has key + url + goal
    reply = convo.send("go")
    assert "<<TINYFISH_RUN" in reply and "url=" in reply and "goal=" in reply, (
        f"Agent should emit <<TINYFISH_RUN url=\"...\" goal=\"...\">> marker once key+url+goal are collected. Got: {reply}"
    )


def test_scenario_14_extracts_event_slug_from_mentormates_url(convo):
    """Scenario 14: when participant pastes a MentorMates event URL, the agent must extract the slug
    from the URL and NOT re-ask them for a 'slug' or 'event reference' afterwards.

    Regression for: Chinat pasted https://www.mentormates.ai/events/anthropic-ara-eleven-labs-hackathon/overview
    and the agent kept asking 'can you provide the slug?' five times.
    """
    convo.send("hi")
    convo.send("scrape a job board for AI roles")
    convo.send("yes that's the plan")
    convo.send("my tinyfish key is tk_demo_xxx")
    convo.send("recording url: https://tinyfish.io/recording/rec_demo")
    convo.send("ready to submit")
    convo.send("mm_sk_fakekey_abc123")
    reply = convo.send(
        "https://www.mentormates.ai/events/anthropic-ara-eleven-labs-hackathon/overview"
    )
    lower = reply.lower()
    asks_for_slug_again = any(
        phrase in lower
        for phrase in [
            "provide the slug",
            "give me the slug",
            "need the slug",
            "need the event reference",
            "what's the slug",
            "what is the slug",
            "shorter identifier",
            "can you share the slug",
        ]
    )
    assert not asks_for_slug_again, (
        f"Agent should auto-extract 'anthropic-ara-eleven-labs-hackathon' from the URL, "
        f"not ask for a slug again. Reply: {reply}"
    )


def test_scenario_12_delete_history_wipes_session_server_side():
    """Scenario 12: DELETE /api/history?session_id=X removes all rows for that session."""
    convo = Conversation()
    convo.send("hello")
    convo.send("what can i build with tinyfish?")

    before = requests.get(
        f"{BASE}/api/history",
        params={"session_id": convo.session_id},
        timeout=20,
    ).json()
    assert len(before) >= 2, f"setup failed — no rows written before DELETE: {before}"

    del_resp = requests.delete(
        f"{BASE}/api/history",
        params={"session_id": convo.session_id},
        timeout=20,
    )
    assert del_resp.status_code == 200, f"DELETE failed: {del_resp.status_code} {del_resp.text}"

    after = requests.get(
        f"{BASE}/api/history",
        params={"session_id": convo.session_id},
        timeout=20,
    ).json()
    assert after == [], f"expected empty list after DELETE, got {len(after)} rows: {after}"
