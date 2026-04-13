"""Live walkthrough of the full build-night flow against the deployed agent.

Simulates the conversation Chinat described: participant is lost, agent teaches
Tinyfish, collects keys + recording, runs it, then submits to MentorMates.

Run: python tests/walkthrough.py
"""

import sys
import time
import uuid

import requests


ENDPOINT = "https://daydreamers-build-night-agent.vercel.app/api/run"


def send(session_id: str, transcript_turns: list, message: str) -> str:
    transcript_turns.append({"role": "user", "text": message})
    transcript_str = "\n\n".join(
        f"{'PARTICIPANT' if t['role'] == 'user' else 'AGENT'}: {t['text']}"
        for t in transcript_turns
    )
    turn_id = f"turn-{uuid.uuid4().hex[:12]}"
    r = requests.post(
        ENDPOINT,
        json={
            "workflow_id": "build-night-guide",
            "input": {
                "session_id": session_id,
                "run_id": turn_id,
                "idempotency_key": turn_id,
                "message": message,
                "transcript": transcript_str,
            },
        },
        timeout=90,
    )
    r.raise_for_status()
    data = r.json()
    reply = (data.get("result") or {}).get("output_text") or "<no reply>"
    transcript_turns.append({"role": "agent", "text": reply})
    return reply


def pretty(role: str, text: str, width: int = 88):
    prefix = "👤 PARTICIPANT" if role == "user" else "🤖 AGENT"
    print(f"\n{prefix}")
    print("-" * width)
    print(text)
    print()


def main():
    session = f"walk-{uuid.uuid4().hex[:10]}"
    turns = []

    script = [
        "hey",
        "honestly i don't know, i've never used tinyfish before. what is it?",
        "oh cool, ok i want to build something that tracks competitor pricing on shopify stores",
        "here is my tinyfish key: tk_live_fake_9f8e7d6c5b4a3f2e1d0c",
        "here's the recording url: https://tinyfish.io/recording/rec_demo_abc123",
        "cool, ready to submit to mentormates now",
        "my mm key is mmpk_live_fake_4a3b2c1d0e9f8e7d and the event ref is build-night-april-2026",
    ]

    print(f"\n=== Build Night Agent Walkthrough ===\nSession: {session}\n")

    for i, msg in enumerate(script, 1):
        print(f"\n{'=' * 88}\nTurn {i}")
        pretty("user", msg)
        try:
            reply = send(session, turns, msg)
            pretty("agent", reply)
        except requests.HTTPError as e:
            print(f"HTTP ERROR: {e}")
            print(f"Body: {e.response.text[:500] if e.response else 'none'}")
            sys.exit(1)
        time.sleep(1)

    print(f"\n{'=' * 88}\nWalkthrough complete. Total turns: {len(script)}")


if __name__ == "__main__":
    main()
