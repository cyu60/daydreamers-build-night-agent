# Roadmap

## Known gaps (discovered during testing)

### 1. Agent hallucinates tool-call success (HIGH)

The orchestrator sometimes claims a Tinyfish run or MM submission succeeded when it didn't — no real HTTP call was made. `tinyfish-runner` and `mm-submitter` are declared as sub-agents but aren't being invoked as callable tools; they're just prose context for the LLM.

**Fix options (pick one):**

- **A. Ara tool wiring** — figure out how ara-sdk exposes subagent handoff as a function call the LLM can invoke, re-prompt the orchestrator to use it. Requires reading more of the ara-sdk source.
- **B. Vercel proxy parses agent output for command markers** — agent emits `<<RUN_TINYFISH recording_url=... >>` or `<<SUBMIT_MM ...>>` in its text; proxy strips the marker, executes the real HTTP call, injects result back into the next turn's transcript. Hacky but hackathon-reliable.
- **C. Frontend orchestration** — frontend detects flow state by pattern-matching agent replies + participant input format; when it sees a Tinyfish key + recording URL both captured, frontend calls dedicated `/api/tinyfish/run` endpoint directly. Least "agentic" but most deterministic.

**Recommendation:** Start with C for build-night reliability; move to A later if Ara exposes the pattern.

## Planned — not started

### 2. Insforge backend (chat logs + auth) — ASK B deferred

User asked 2026-04-13 to set up Insforge as the backend for:
- **Chat log storage:** persist every turn `{session_id, user_id, role, text, ts}` to an Insforge table, write-through from the Vercel `/api/run` proxy. Enables post-event review of participant conversations for debugging + content.
- **Authentication:** magic-link sign-in on the chat page so every participant has a persistent identity. Session_id becomes `{user_id}_{event_ref}` instead of random localStorage.

**Open questions before implementing:**
- Which Insforge project/instance to use? (check `~/insforge-proposal/` and memory `project_mentormates_agentic_skills`)
- Do we need a participants table or just reuse Insforge's built-in auth.users?
- Build-night is 1-shot — is auth actually needed or is random session_id fine for MVP?

**Suggested schema:**
```
sessions(id uuid pk, user_id uuid fk, event_ref text, created_at timestamptz)
messages(id bigserial pk, session_id uuid fk, role text, text text, turn_id text, created_at timestamptz)
```

**Out of scope for Phase 1:** rate limiting, credit tracking, admin dashboard.

### 3. Real Tinyfish API integration

Once gap #1 is fixed, we need the actual Tinyfish endpoint contract:
- Auth header format
- POST body to start a run from a recording URL
- Polling endpoint shape + timeout behavior
- Result payload shape

Use the `tinyfish` skill to gather this.

### 4. Real MentorMates submission

`mm-submitter` prompt is correct, but the actual HTTP call isn't being executed. Verify against a real MM event ref + participant API key, smoke-test against the staging MM instance before build night.

### 5. Deploy pipeline

Currently `python app.py deploy --on-existing update` is manual. Add a script or GitHub Action so pushing to master also re-deploys the Ara app.

## Recently shipped

- 2026-04-13: Scaffold repo, Vercel deployment, iGotsIt invited as collaborator
- 2026-04-13: 5 live integration tests passing against Ara
- 2026-04-13: Fixed multi-turn dedup bug (unique run_id + idempotency_key per turn)
- 2026-04-13: Chat bubble CSS fix (bubbles hug content)
