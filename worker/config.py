"""Worker configuration via environment variables."""

from __future__ import annotations

import os


def _env(name: str, default: str = "") -> str:
    val = os.environ.get(name, "").strip()
    return val if val else default


# Directus
DIRECTUS_URL = _env("DIRECTUS_URL", "http://directus:8055")
DIRECTUS_TOKEN = _env("DIRECTUS_TOKEN", "")  # static admin/service token

# RouterAI
ROUTERAI_API_KEY = _env("ROUTERAI_API_KEY", "")
ROUTERAI_BASE_URL = _env("ROUTERAI_BASE_URL", "https://routerai.ru/api/v1")
CHAT_MODEL = _env("CARDGEN_CHAT_MODEL", "openai/gpt-5.4")
IMAGE_MODEL = _env("CARDGEN_IMAGE_MODEL", "google/gemini-2.5-flash-image")

# Worker
WORKER_HOST = _env("WORKER_HOST", "0.0.0.0")
WORKER_PORT = int(_env("WORKER_PORT", "8766"))
MAX_UPLOAD_MB = int(_env("MAX_UPLOAD_MB", "10"))