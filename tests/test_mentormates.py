"""Tests for the MentorMates participant-agent API helper."""

import pytest
import responses

from lib import mentormates


MM_BASE = "https://www.mentormates.ai"
EVENT_REF = "build-night-2026-04"
API_KEY = "mmpk_test_abc123"


@responses.activate
def test_submit_project_returns_mentormates_project_url():
    """Given a valid MM key and event ref, submit_project joins the event
    (treating 200 as success), POSTs the project, and returns the project URL."""

    responses.add(
        responses.POST,
        f"{MM_BASE}/api/agent/me/events/{EVENT_REF}/join",
        json={"ok": True},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{MM_BASE}/api/agent/me/events/{EVENT_REF}/projects",
        json={"id": "proj_abc123"},
        status=201,
    )

    payload = {
        "name": "YC Jobs Scraper",
        "description": "Tinyfish automation that scrapes the Y Combinator jobs board.",
        "project_url": "https://tinyfish.io/recording/r_xyz",
        "video_url": "https://tinyfish.io/run/run_result",
    }

    result = mentormates.submit_project(
        api_key=API_KEY,
        event_ref=EVENT_REF,
        payload=payload,
    )

    assert result == {
        "project_id": "proj_abc123",
        "project_url": "https://mentormates.ai/projects/proj_abc123",
    }
    # Join call sends Bearer auth
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {API_KEY}"
    # Submit call sends the payload as JSON
    import json
    assert json.loads(responses.calls[1].request.body) == payload
