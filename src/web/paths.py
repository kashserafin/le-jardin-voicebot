import tempfile

from pathlib import Path


WEB_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_DIR.parent
STATIC_DIR = WEB_DIR / "static"
AUDIO_DIR = Path(tempfile.gettempdir()) / "le_jardin_voicebot_audio"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
