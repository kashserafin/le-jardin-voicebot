import os

from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "test-langfuse-public-key")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "test-langfuse-secret-key")
os.environ.setdefault("LANGFUSE_BASE_URL", "http://localhost")

from agent.graph import INITIAL_MESSAGE
from web.app import create_app
from web.paths import AUDIO_DIR


class FakeAudioClient:
    def __init__(self, transcript: str = "I would like a table for two.") -> None:
        self.transcript = transcript
        self.transcriptions = []
        self.syntheses = []

    def transcribe_bytes(self, audio_bytes: bytes, filename: str) -> str:
        self.transcriptions.append((audio_bytes, filename))
        return self.transcript

    def synthesize_to_url(self, text, audio_dir):
        self.syntheses.append((text, audio_dir))
        return f"/audio/fake-{len(self.syntheses)}.mp3"


def test_start_session_returns_initial_reply_and_audio(monkeypatch):
    fake_audio_client = FakeAudioClient()
    monkeypatch.setattr("web.routes.audio_client", fake_audio_client)

    response = TestClient(create_app()).post("/session/start")

    assert response.status_code == 200
    body = response.json()
    assert len(body["session_id"]) == 32
    assert body["reply"] == INITIAL_MESSAGE
    assert body["audio_url"] == "/audio/fake-1.mp3"
    assert fake_audio_client.syntheses == [(INITIAL_MESSAGE, AUDIO_DIR)]


def test_audio_turn_transcribes_runs_agent_and_synthesizes_reply(monkeypatch):
    fake_audio_client = FakeAudioClient(transcript="Book a table for four.")
    agent_calls = []

    def fake_run_next_turn(message: str, thread_id: str) -> str:
        agent_calls.append((message, thread_id))
        return "Great, we have availability! Can I have your name for the booking?"

    monkeypatch.setattr("web.routes.audio_client", fake_audio_client)
    monkeypatch.setattr("web.routes.run_next_turn", fake_run_next_turn)

    response = TestClient(create_app()).post(
        "/turn/audio",
        data={"session_id": "session-123"},
        files={"audio": ("turn.webm", b"fake audio bytes", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "Book a table for four."
    assert body["reply"] == "Great, we have availability! Can I have your name for the booking?"
    assert body["audio_url"] == "/audio/fake-1.mp3"
    assert set(body["timings"]) == {"transcribe_ms", "agent_ms", "tts_ms"}
    assert all(value >= 0 for value in body["timings"].values())
    assert fake_audio_client.transcriptions == [(b"fake audio bytes", "turn.webm")]
    assert fake_audio_client.syntheses == [(body["reply"], AUDIO_DIR)]
    assert agent_calls == [("Book a table for four.", "session-123")]


def test_audio_turn_skips_agent_when_transcript_is_empty(monkeypatch):
    fake_audio_client = FakeAudioClient(transcript="")
    agent_calls = []

    monkeypatch.setattr("web.routes.audio_client", fake_audio_client)
    monkeypatch.setattr("web.routes.run_next_turn", lambda *args: agent_calls.append(args))

    response = TestClient(create_app()).post(
        "/turn/audio",
        data={"session_id": "session-123"},
        files={"audio": ("turn.webm", b"silent audio", "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == ""
    assert body["reply"] == "I didn't catch that. Could you say it again?"
    assert body["audio_url"] == "/audio/fake-1.mp3"
    assert body["timings"]["agent_ms"] == 0
    assert fake_audio_client.transcriptions == [(b"silent audio", "turn.webm")]
    assert fake_audio_client.syntheses == [(body["reply"], AUDIO_DIR)]
    assert agent_calls == []
