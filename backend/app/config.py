"""Centralized configuration for VisionGuard Backend API."""
from __future__ import annotations

import os

DEFAULT_SUPPORTED_MODELS: list[str] = [
    "fasterrcnn_resnet50_fpn",
    "fasterrcnn_resnet50_fpn_v2",
]

DEFAULT_CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

ALLOWED_CORS_METHODS: list[str] = [
    "GET",
    "POST",
    "OPTIONS",
    "HEAD",
]

ALLOWED_CORS_HEADERS: list[str] = [
    "Content-Type",
    "Accept",
    "Authorization",
    "X-Requested-With",
]

ALLOW_CORS_CREDENTIALS: bool = False


def configured_models() -> list[str]:
    """Parse comma-separated model identifiers from VISIONGUARD_SUPPORTED_MODELS."""
    values = os.getenv("VISIONGUARD_SUPPORTED_MODELS", "")
    parsed = sorted({value.strip() for value in values.split(",") if value.strip()})
    return parsed if parsed else list(DEFAULT_SUPPORTED_MODELS)


def parse_cors_origins(raw: str | None) -> list[str]:
    """Parse and clean comma-separated CORS origins.

    Strips leading/trailing whitespace and trailing slashes.
    """
    if raw is None or not raw.strip():
        return list(DEFAULT_CORS_ORIGINS)
    origins: list[str] = []
    for item in raw.split(","):
        cleaned = item.strip().rstrip("/")
        if cleaned:
            origins.append(cleaned)
    return origins if origins else list(DEFAULT_CORS_ORIGINS)


def configured_cors_origins() -> list[str]:
    """Return configured CORS origins from VISIONGUARD_CORS_ORIGINS or safe defaults."""
    return parse_cors_origins(os.getenv("VISIONGUARD_CORS_ORIGINS"))
