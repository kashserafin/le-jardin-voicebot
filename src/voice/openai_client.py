from io import BytesIO
from pathlib import Path
from uuid import uuid4

from openai import OpenAI


class OpenAIAudioClient:
    def __init__(
        self,
        client: OpenAI | None = None,
        transcription_model: str = "gpt-4o-mini-transcribe",
        tts_model: str = "gpt-4o-mini-tts",
        tts_voice: str = "marin",
    ) -> None:
        self.client = client or OpenAI()
        self.transcription_model = transcription_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice

    def transcribe_bytes(self, audio_bytes: bytes, filename: str) -> str:
        audio_file = BytesIO(audio_bytes)
        audio_file.name = filename

        transcript = self.client.audio.transcriptions.create(
            model=self.transcription_model,
            file=audio_file,
            response_format="text",
        )

        return transcript.strip()

    def synthesize_to_file(self, text: str, output_path: Path) -> None:
        with self.client.audio.speech.with_streaming_response.create(
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
