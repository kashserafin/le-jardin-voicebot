import os

from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("DEMO_PASSCODE", "test-demo-passcode")

from config import Settings
from web.app import create_app
from web.auth import AUTH_CHALLENGE, is_authorized


def test_blank_demo_passcode_is_treated_as_disabled():
    settings = Settings(
        openai_api_key="test-openai-key",
        demo_passcode="   ",
        _env_file=None,
    )

    assert settings.demo_passcode is None


def test_demo_auth_is_disabled_without_passcode(monkeypatch):
    monkeypatch.setattr("web.app.settings.demo_passcode", None)

    response = TestClient(create_app()).get("/")

    assert response.status_code == 200


def test_demo_auth_rejects_missing_credentials_when_enabled(monkeypatch):
    monkeypatch.setattr("web.app.settings.demo_passcode", "let-me-in")

    response = TestClient(create_app()).get("/")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == AUTH_CHALLENGE
    assert response.headers["cache-control"] == "no-store"


def test_demo_auth_rejects_wrong_passcode(monkeypatch):
    monkeypatch.setattr("web.app.settings.demo_passcode", "let-me-in")

    response = TestClient(create_app()).get("/", auth=("demo", "wrong"))

    assert response.status_code == 401


def test_demo_auth_accepts_matching_passcode(monkeypatch):
    monkeypatch.setattr("web.app.settings.demo_passcode", "let-me-in")

    response = TestClient(create_app()).get("/", auth=("demo", "let-me-in"))

    assert response.status_code == 200


def test_demo_auth_compares_basic_auth_password_only():
    assert is_authorized("Basic ZGVtbzpsZXQtbWUtaW4=", "let-me-in") is True
    assert is_authorized("Basic ZGVtbzp3cm9uZw==", "let-me-in") is False
