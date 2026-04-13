# DayDreamers Build Night Agent

> A chat agent that helps hackathon participants ship a Tinyfish project to MentorMates in a single conversation — no code editor, no repo push.

**Status:** Scaffolding. Design spec in progress.

## What it does

At a DayDreamers × MentorMates build night, a participant opens this web app and has a single conversation. The agent:

1. Asks what they're trying to build.
2. Teaches them what Tinyfish is (an AI browser agent that surfs the web for them).
3. Collects their Tinyfish API key and a Tinyfish browser recording URL.
4. Runs the Tinyfish task on their behalf.
5. Collects their MentorMates participant API key + event reference.
6. Submits the project to MentorMates on their behalf.

All orchestration runs on DayDreamers' Ara account, so DayDreamers eats zero per-participant LLM cost.

## Architecture

Frontend: single-page vanilla JS chat UI (Tailwind via CDN).
Backend: Vercel serverless proxy → Ara Cloud Runtime → four agents:

- `build-night-guide` — orchestrator
- `tinyfish-teacher` — onboarding + key-finding instructions
- `tinyfish-runner` — executes the Tinyfish recording
- `mm-submitter` — POSTs to the MentorMates participant-agent API

See the design spec for details.

## References

- Ara example agent: [cyu60/ara-ai-computer](https://github.com/cyu60/ara-ai-computer)
- "Powered by MentorMates" branding reference: `find-my-api-key`
- MentorMates participant-agent API: `edumame/MentorMates` → `app/api/agent/me/events/**`

Powered by [MentorMates](https://mentormates.ai).
