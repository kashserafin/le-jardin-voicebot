from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from agent.graph import INITIAL_MESSAGE
from agent.service import run_next_turn
from ui.paths import AUDIO_DIR, STATIC_DIR
from voice.openai_client import OpenAIAudioClient


router = APIRouter()


@router.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@router.post("/session/start")
async def start_session():
    session_id = uuid4().hex
    audio_url = await run_in_threadpool(
        OpenAIAudioClient.synthesize_to_url,
        INITIAL_MESSAGE,
        AUDIO_DIR,
    )

    return {
        "session_id": session_id,
        "reply": INITIAL_MESSAGE,
        "audio_url": audio_url,
    }


@router.post("/turn/audio")
async def audio_turn(session_id: str = Form(...), audio: UploadFile = File(...)):
    try:
        timings = {}

        started = perf_counter()
        audio_bytes = await audio.read()
        transcript = await run_in_threadpool(
            OpenAIAudioClient.transcribe_bytes,
            audio_bytes,
            audio.filename or "recording.webm",
        )
        timings["transcribe_ms"] = round((perf_counter() - started) * 1000)

        if transcript:
            started = perf_counter()
            reply = await run_in_threadpool(run_next_turn, transcript, session_id)
            timings["agent_ms"] = round((perf_counter() - started) * 1000)
        else:
            reply = "I didn't catch that. Could you say it again?"
            timings["agent_ms"] = 0

        started = perf_counter()
        audio_url = await run_in_threadpool(OpenAIAudioClient.synthesize_to_url, reply, AUDIO_DIR)
        timings["tts_ms"] = round((perf_counter() - started) * 1000)

        return {
            "transcript": transcript,
            "reply": reply,
            "audio_url": audio_url,
            "timings": timings,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
