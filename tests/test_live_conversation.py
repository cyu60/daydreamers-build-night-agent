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
