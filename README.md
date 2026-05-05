# Le Jardin Voicebot

Le Jardin Voicebot is a small restaurant reservation voicebot demo. It is built to show how a voice-channel booking flow can be structured with explicit state, LLM extraction, deterministic validation, and recovery prompts.

The frontend is intentionally minimal. The main thing this project is meant to demonstrate is the backend conversation flow: how the bot gathers details, validates them, asks follow-up questions, confirms the booking, and keeps the LLM inside a narrow role.

<img width="798" height="892" alt="le_jardin_voicebot_v1" src="https://github.com/user-attachments/assets/9efb3a98-276d-4349-ac40-f64e950dd882" />

## What Works

The demo supports a turn-based voice reservation flow:

1. The browser starts a new voicebot session.
2. The assistant asks for booking details.
3. The user records an answer.
4. Audio is transcribed with OpenAI.
5. A LangGraph flow extracts reservation details with structured output.
6. Deterministic guardrails validate the extracted date, time, and party size.
7. The assistant asks only for missing or invalid details.
8. Availability is checked through a demo stub.
9. The assistant collects the customer's name.
10. The assistant reads back the booking and asks for confirmation.
11. The booking is confirmed or cancelled.
12. The reply is synthesized back to speech with OpenAI TTS.

The current booking guardrails are:

- Date must be today or within the next 14 days.
- Time must be between 12:00 and 22:00.
- Party size must be between 1 and 10.
- Missing details are asked for explicitly.
- Invalid details are rejected before the flow reaches availability or confirmation.

## Why It Is Built This Way

Voicebots need a different shape from chatbots. A user cannot skim a long answer, so prompts should be short, spoken-friendly, and easy to answer out loud. The bot asks focused follow-up questions instead of dumping all requirements into one message.

The LLM is used for narrow language tasks:

- Extract booking details from a spoken transcript.
- Extract the customer name.
- Classify the final confirmation response.

Business rules are not left to the LLM. Date windows, opening hours, and party-size limits are enforced in Python in `agent/booking_guardrails.py`. This makes the flow easier to test and easier to reason about.

LangGraph is used because the reservation flow is stateful. The bot needs to remember partially collected details, merge new details across turns, retry when something is missing, and resume from the right step after each user recording.

## Architecture

```text
Browser UI
  -> FastAPI routes
  -> OpenAI transcription
  -> LangGraph booking flow
  -> OpenAI text-to-speech
  -> Browser audio playback
```

Important files:

- `web/app.py` creates the FastAPI app.
- `web/routes.py` exposes the session and audio-turn endpoints.
- `web/static/` contains the minimal browser UI.
- `openai_client.py` centralizes OpenAI chat, transcription, and TTS client creation.
- `agent/graph.py` defines the LangGraph reservation flow.
- `agent/prompts.py` contains extraction and intent-classification prompts.
- `agent/booking_guardrails.py` contains deterministic booking validation.
- `agent/helpers.py` formats spoken follow-up and confirmation text.
- `agent/service.py` runs the next turn for a session.
- `tests/` covers guardrails, helper copy, graph behavior, routes, and OpenAI client wiring.

## Requirements

- Python `>=3.14`
- `uv`
- An OpenAI API key
- A browser with microphone support

The app uses these OpenAI capabilities:

- Audio transcription
- Text-to-speech
- Chat model calls through LangChain structured output

Langfuse environment variables are also present because the service is wired for tracing. For local demo runs, you can leave them blank unless you want tracing enabled.

## Setup

Install dependencies:

```bash
uv sync
```

Create a local environment file:

```bash
cp env.example .env
```

Set at least:

```bash
OPENAI_API_KEY="your-api-key"
```

Optional Langfuse values:

```bash
LANGFUSE_SECRET_KEY=""
LANGFUSE_PUBLIC_KEY=""
LANGFUSE_BASE_URL=""
```

## Run The Demo

Start the server:

```bash
uv run uvicorn web.app:api --reload
```

Open:

```text
http://127.0.0.1:8000
```

Click **Start voicebot**, allow microphone access, then answer the assistant by recording short spoken turns.

Example flow:

```text
Assistant: Welcome to Le Jardin! I can help you book a table. What day would you like to come in?
User: Tomorrow at seven for four people.
Assistant: Great, that time is available. Can I get a name for the reservation?
User: Ada Lovelace.
Assistant: I've got 4 guests on Wednesday, 6 May at 7 PM, under Ada Lovelace. Should I book it?
User: Yes.
Assistant: You're all set. See you then.
```

The exact date in the confirmation depends on the current date when you run the demo.

## Run Tests

```bash
uv run pytest -q
```

Run linting:

```bash
uv run ruff check .
```

The tests avoid real OpenAI calls by using fakes and monkeypatching. They focus on the flow, guardrails, helper text, API route contracts, and OpenAI client construction.

## Current Scope And Compromises

This is a focused demo, not a production reservation system.

Implemented:

- Turn-based browser voice interaction.
- OpenAI transcription and TTS.
- LangGraph state machine for the booking flow.
- Structured LLM extraction.
- Deterministic validation for booking details.
- Missing-detail and invalid-detail recovery.
- Customer-name retry.
- Final confirmation and cancellation.
- Tests for the core flow and guardrails.

Deliberate compromises:

- Availability always returns `True`; there is no real reservation inventory.
- Final booking creation is a stub; no external booking system is called.
- Session state uses in-memory LangGraph checkpointing.
- Restarting the server clears active conversations.
- The browser UI is intentionally simple and not the focus of the project.
- Audio is turn-based; there is no live streaming, barge-in, VAD, or interruption handling.
- There is no authentication, rate limiting, or deployment hardening.

Known flow gaps:

- Confirmation change requests are classified but not handled yet.
- Unclear confirmation replies fall back to a generic failure path.
- Name capture is basic; it does not spell back names or ask for spelling.
- Relative date handling is prompt-driven, then validated by code.
- Error handling is suitable for local demo work, not production operations.

## Good Demo Talking Points

This project is strongest when presented as a flow and guardrails demo:

- The LLM does not own the business rules.
- The graph controls what step the user is in.
- The bot can recover from missing and invalid slot values.
- Tests assert state transitions, validation behavior, and spoken response text.
- The voice channel changes the wording: short prompts, one question at a time, and confirmation before final action.

## Troubleshooting

If imports fail while running tests, make sure you are using the repository's `pyproject.toml`; pytest is configured there with the project root on `pythonpath`.

If the app fails on startup or the first voice turn, check `OPENAI_API_KEY` in `.env`.

If recording does not start, check browser microphone permissions. Localhost should work in modern browsers, but microphone APIs still require user permission.
