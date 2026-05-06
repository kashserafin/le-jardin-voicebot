from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import settings
from web.auth import add_demo_auth_middleware
from web.paths import AUDIO_DIR, STATIC_DIR
from web.routes import router


def create_app() -> FastAPI:
    api = FastAPI(title="Le Jardin Voicebot")
    add_demo_auth_middleware(api, passcode=settings.demo_passcode)
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    api.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
    api.include_router(router)

    return api


api = create_app()
