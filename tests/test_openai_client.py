import os

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "test-langfuse-public-key")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "test-langfuse-secret-key")
os.environ.setdefault("LANGFUSE_BASE_URL", "http://localhost")

from openai_client import OpenAIAudioClient, OpenAIClient


class FakeChatModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_sdk_client_is_created_lazily_and_reused(monkeypatch):
    created_clients = []
    fake_client = object()

    def create_openai(**kwargs):
        created_clients.append(kwargs)
        return fake_client

    monkeypatch.setattr("openai_client.OpenAI", create_openai)

    client = OpenAIClient(api_key="test-key")

    assert created_clients == []
    assert client.sdk_client is fake_client
    assert client.sdk_client is fake_client
    assert created_clients == [{"api_key": "test-key"}]


def test_chat_model_uses_shared_api_key(monkeypatch):
    monkeypatch.setattr("openai_client.ChatOpenAI", FakeChatModel)

    chat_model = OpenAIClient(api_key="test-key").chat_model(
        model="gpt-5.4-mini",
        temperature=0,
    )

    assert chat_model.kwargs == {
        "api_key": "test-key",
        "model": "gpt-5.4-mini",
        "temperature": 0,
    }


def test_audio_client_inherits_shared_openai_client():
    fake_client = object()

    audio_client = OpenAIAudioClient(client=fake_client, api_key="test-key")

    assert isinstance(audio_client, OpenAIClient)
    assert audio_client.api_key == "test-key"
    assert audio_client.sdk_client is fake_client
