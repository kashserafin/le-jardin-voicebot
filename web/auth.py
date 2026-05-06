import base64
import binascii
from secrets import compare_digest

from fastapi import FastAPI, Request
from starlette.responses import Response


AUTH_CHALLENGE = 'Basic realm="Le Jardin Voicebot Demo", charset="UTF-8"'


def add_demo_auth_middleware(api: FastAPI, *, passcode: str | None) -> None:
    if not passcode:
        return

    @api.middleware("http")
    async def require_demo_auth(request: Request, call_next):
        if is_authorized(request.headers.get("authorization"), passcode):
            return await call_next(request)

        return unauthorized_response()


def is_authorized(authorization: str | None, passcode: str) -> bool:
    if not authorization:
        return False

    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "basic" or not credentials:
        return False

    try:
        decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False

    _, separator, password = decoded.partition(":")
    if not separator:
        return False

    return compare_digest(password, passcode)


def unauthorized_response() -> Response:
    return Response(
        "Authentication required",
        status_code=401,
        headers={
            "WWW-Authenticate": AUTH_CHALLENGE,
            "Cache-Control": "no-store",
        },
    )
