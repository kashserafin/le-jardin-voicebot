from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_openai import ChatOpenAI
from openai import OpenAI

from config import settings


class OpenAIClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        sdk_client: OpenAI | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self._sdk_client = sdk_client

    @property
    def sdk_client(self) -> OpenAI:
        if self._sdk_client is None:
            self._sdk_client = OpenAI(api_key=self.api_key)

        return self._sdk_client

    def chat_model(self, model: str, **kwargs: Any) -> ChatOpenAI:
        return ChatOpenAI(api_key=self.api_key, model=model, **kwargs)


class OpenAIAudioClient(OpenAIClient):
    def __init__(
        self,
        client: OpenAI | None = None,
        api_key: str | None = None,
        transcription_model: str = "gpt-4o-mini-transcribe",
        tts_model: str = "gpt-4o-mini-tts",
        tts_voice: str = "marin",
    ) -> None:
        super().__init__(api_key=api_key, sdk_client=client)
        self.transcription_model = transcription_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice

    def transcribe_bytes(self, audio_bytes: bytes, filename: str) -> str:
        audio_file = BytesIO(audio_bytes)
        audio_file.name = filename

        transcript = self.sdk_client.audio.transcriptions.create(
            model=self.transcription_model,
            file=audio_file,
            response_format="text",
        )

        return transcript.strip()

    def synthesize_to_file(self, text: str, output_path: Path) -> None:
        with self.sdk_client.audio.speech.with_streaming_response.create(
            model=self.tts_model,
            voice=self.tts_voice,
            input=text,
            instructions="Speak warmly and concisely as a restaurant booking assistant.",
        ) as response:
            response.stream_to_file(str(output_path))

    def synthesize_to_url(self, text: str, audio_dir: Path, url_prefix: str = "/audio") -> str:
        filename = f"{uuid4().hex}.mp3"
        output_path = audio_dir / filename
        self.synthesize_to_file(text, output_path)

        return f"{url_prefix}/{filename}"
