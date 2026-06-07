"""FastAPI worker: accept generation tasks, orchestrate pipeline, return results."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import DIRECTUS_TOKEN, MAX_UPLOAD_MB, WORKER_HOST, WORKER_PORT
from .directus_client import DirectusClient
from .pipeline import run_generation
from .seed_directus import auto_seed

logger = logging.getLogger(__name__)

# Shared Directus client (for background tasks without user context)
_directus: DirectusClient | None = None


def _get_directus(token: str | None = None) -> DirectusClient:
    """Return Directus client. If token provided, use it; otherwise fall back to static token."""
    if token:
        return DirectusClient(token=token)
    global _directus
    if _directus is None:
        _directus = DirectusClient()
    return _directus


def _extract_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


# Background task tracker
_pending: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> None:
    _pending.add(task)
    task.add_done_callback(_pending.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    for name in ("httpx", "openai", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
    logger.info("worker started")
    auto_seed()
    yield
    logger.info("worker shutting down")


app = FastAPI(title="Cardgen Worker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Request body for generation."""
    template_id: str
    title: str = ""
    bullets: list[str] = []
    extra: dict[str, Any] = {}


class TaskResponse(BaseModel):
    id: str
    status: str
    result_image: str | None = None
    enhanced_prompt: str | None = None
    error_message: str | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    slug: str
    category: str | None = None
    width: int
    height: int
    preview: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    logger.info("HTTP %s %s -> %s %.3fs", request.method, request.url.path, response.status_code, time.perf_counter() - t0)
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/templates")
async def list_templates(authorization: str | None = Header(None)) -> list[dict]:
    """List active templates from Directus."""
    token = _extract_token(authorization)
    d = _get_directus(token)
    try:
        templates = await d.get_templates(is_active=True)
        return templates
    except Exception as e:
        logger.exception("failed to list templates")
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/templates/{template_id}")
async def get_template(template_id: str, authorization: str | None = Header(None)) -> dict:
    """Get a single template."""
    token = _extract_token(authorization)
    d = _get_directus(token)
    try:
        return await d.get_template(template_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Template not found") from e


@app.post("/generate")
async def generate(
    template_id: str = Form(...),
    title: str = Form(""),
    bullets_json: str = Form("[]"),
    product_image: UploadFile = File(...),
    authorization: str | None = Header(None),
) -> dict:
    """
    Start a generation task.

    1. Upload product image to Directus
    2. Create generation_task record (status=pending)
    3. Run pipeline in background
    4. Return task_id for polling
    """
    # Validate file
    body = await product_image.read()
    if not body:
        raise HTTPException(status_code=400, detail="Пустой файл изображения.")
    if len(body) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой (макс. {MAX_UPLOAD_MB} МБ).")

    user_token = _extract_token(authorization)
    d = _get_directus(user_token)

    # Upload product image to Directus
    try:
        import json
        bullets = json.loads(bullets_json) if bullets_json else []
    except Exception:
        bullets = []

    try:
        file_record = await d.upload_file(body, product_image.filename or "product.png")
        file_id = file_record.get("id", "")
    except Exception as e:
        logger.exception("failed to upload product image")
        raise HTTPException(status_code=502, detail=f"Ошибка загрузки файла: {e}") from e

    # Create task
    task_id = str(uuid.uuid4())
    try:
        task = await d.create_task({
            "id": task_id,
            "template": template_id,
            "status": "pending",
            "input_data": {
                "product_image_file_id": file_id,
                "title": title,
                "bullets": bullets,
            },
        })
        task_id = task.get("id", task_id)
    except Exception as e:
        logger.exception("failed to create task")
        raise HTTPException(status_code=502, detail=f"Ошибка создания задачи: {e}") from e

    # Run pipeline in background
    async def _run():
        await run_generation(task_id, d)

    bg_task = asyncio.create_task(_run())
    _track_task(bg_task)

    return {"ok": True, "task_id": task_id}


@app.get("/task/{task_id}")
async def get_task(task_id: str) -> dict:
    """Poll task status."""
    d = _get_directus()
    try:
        task = await d.get_task(task_id)
        return {
            "ok": True,
            "id": task.get("id"),
            "status": task.get("status"),
            "result_image": task.get("result_image"),
            "enhanced_prompt": task.get("enhanced_prompt"),
            "error_message": task.get("error_message"),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail="Task not found") from e


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import uvicorn
    uvicorn.run("worker.main:app", host=WORKER_HOST, port=WORKER_PORT, reload=False)


if __name__ == "__main__":
    main()