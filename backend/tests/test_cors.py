from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from backend.app.config import (
    ALLOW_CORS_CREDENTIALS,
    ALLOWED_CORS_HEADERS,
    ALLOWED_CORS_METHODS,
    DEFAULT_CORS_ORIGINS,
    configured_cors_origins,
    parse_cors_origins,
)
from backend.app.database import RunDatabase, metadata
from backend.app.main import create_app


def test_cors_origin_parser() -> None:
    # Safe defaults when empty or None
    assert parse_cors_origins(None) == DEFAULT_CORS_ORIGINS
    assert parse_cors_origins("") == DEFAULT_CORS_ORIGINS
    assert parse_cors_origins("   ") == DEFAULT_CORS_ORIGINS

    # Strips whitespace and trailing slashes
    raw = " http://localhost:5173/ , https://visionguard.app/ , http://127.0.0.1:3000 "
    parsed = parse_cors_origins(raw)
    assert parsed == [
        "http://localhost:5173",
        "https://visionguard.app",
        "http://127.0.0.1:3000",
    ]


def test_cors_env_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISIONGUARD_CORS_ORIGINS", "http://app.local:8080, https://staging.visionguard.dev")
    origins = configured_cors_origins()
    assert origins == ["http://app.local:8080", "https://staging.visionguard.dev"]


def test_cors_preflight_allowed_origin(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'cors.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    app = create_app(database=db, cors_origins=["http://localhost:5173"])

    with TestClient(app) as client:
        resp = client.options(
            "/api/v1/runs",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        # Wildcard must not be used
        assert resp.headers.get("access-control-allow-origin") != "*"
        # Credentials must not be enabled
        assert resp.headers.get("access-control-allow-credentials") is None
        # Methods must match restricted set
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        for method in ["GET", "POST", "OPTIONS"]:
            assert method in allow_methods

    db.dispose()


def test_cors_unapproved_origin_rejected(tmp_path: Path) -> None:
    db = RunDatabase(f"sqlite:///{(tmp_path / 'cors_unapproved.sqlite3').as_posix()}")
    metadata.create_all(db.engine)
    app = create_app(database=db, cors_origins=["http://localhost:5173"])

    with TestClient(app) as client:
        # Preflight from malicious/unapproved origin
        resp = client.options(
            "/api/v1/runs",
            headers={
                "Origin": "http://evil-site.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        # Starlette CORS does not return access-control-allow-origin for unapproved origins
        assert "access-control-allow-origin" not in resp.headers

        # GET from unapproved origin
        resp_get = client.get("/api/v1/models", headers={"Origin": "http://evil-site.com"})
        assert "access-control-allow-origin" not in resp_get.headers

    db.dispose()


def test_cors_credentials_are_disabled() -> None:
    assert ALLOW_CORS_CREDENTIALS is False
