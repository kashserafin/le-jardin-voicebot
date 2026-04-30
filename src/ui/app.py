from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ui.paths import AUDIO_DIR, STATIC_DIR
from ui.routes import router


def create_app() -> FastAPI:
    api = FastAPI(title="Le Jardin Voicebot")
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    api.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
    api.include_router(router)

    return api


api = create_app()
