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
    if not DIRECTUS_TOKEN:
        logger.warning(
            "DIRECTUS_TOKEN is not set — worker will have no service token "
            "for Directus API calls. Template listing may fail for expired user tokens. "
            "Set DIRECTUS_TOKEN in your .env file."
        )
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
    """List active templates from Directus.

    Tries in order: user token → static service token → no token (public access).
    This ensures templates are returned even when the user token has expired.
    """
    token = _extract_token(authorization)

    # 1. Try user token
    if token:
        try:
            return await _get_directus(token).get_templates(is_active=True)
        except Exception:
            logger.warning("user token failed for templates, trying fallbacks")

    # 2. Try static service token
    if DIRECTUS_TOKEN:
        try:
            return await _get_directus(DIRECTUS_TOKEN).get_templates(is_active=True)
        except Exception:
            logger.warning("static token also failed for templates, trying public access")

    # 3. Try without any token (public Directus access)
    try:
        return await _get_directus(token=None).get_templates(is_active=True)
    except Exception as e:
        logger.exception("all token fallbacks failed for templates")
        raise HTTPException(status_code=502, detail=f"Failed to list templates: {e}") from e


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

    1. Validate user token & get user_id
    2. Upload product image to Directus (as user)
    3. Create generation_task record (as user, with user_id)
    4. Run pipeline in background (as admin/service)
    5. Return task_id for polling
    """
    # Validate file
    body = await product_image.read()
    if not body:
        raise HTTPException(status_code=400, detail="Пустой файл изображения.")
    if len(body) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой (макс. {MAX_UPLOAD_MB} МБ).")

    user_token = _extract_token(authorization)
    if not user_token:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")

    # Use user token — Directus enforces per-user permissions
    d = _get_directus(user_token)

    # Verify token & get user_id
    try:
        me = await d.get_me()
        user_id = me.get("id", "") if isinstance(me, dict) else ""
        if not user_id:
            raise HTTPException(status_code=401, detail="Не удалось определить пользователя.")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("generate: user token invalid: %s", e)
        raise HTTPException(status_code=401, detail="Токен истёк. Обновите страницу и войдите заново.") from e

    # Parse bullets
    try:
        import json
        bullets = json.loads(bullets_json) if bullets_json else []
    except Exception:
        bullets = []

    # Upload product image to Directus (as user)
    try:
        file_record = await d.upload_file(body, product_image.filename or "product.png")
        file_id = file_record.get("id", "")
    except Exception as e:
        logger.exception("failed to upload product image")
        raise HTTPException(status_code=502, detail=f"Ошибка загрузки файла: {e}") from e

    # Create task (as user, with user_id)
    task_id = str(uuid.uuid4())
    try:
        task = await d.create_task({
            "id": task_id,
            "user_id": user_id,
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

    # Run pipeline in background — use admin/service token
    d_admin = _get_directus(DIRECTUS_TOKEN or None)

    async def _run():
        await run_generation(task_id, d_admin)

    bg_task = asyncio.create_task(_run())
    _track_task(bg_task)

    return {"ok": True, "task_id": task_id}


@app.post("/process/{task_id}")
async def process_task(task_id: str) -> dict:
    """Trigger background processing for an existing task.

    The task must already exist in Directus (created by the client directly).
    This endpoint starts the pipeline in the background using the admin/service token.
    """
    if not DIRECTUS_TOKEN:
        raise HTTPException(status_code=503, detail="Worker has no DIRECTUS_TOKEN configured.")

    d_admin = _get_directus(DIRECTUS_TOKEN)

    # Verify task exists and is pending
    try:
        task = await d_admin.get_task(task_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Task not found") from e

    status = task.get("status", "")
    if status not in ("pending",):
        raise HTTPException(status_code=409, detail=f"Task status is '{status}', expected 'pending'.")

    async def _run():
        await run_generation(task_id, d_admin)

    bg_task = asyncio.create_task(_run())
    _track_task(bg_task)

    return {"ok": True, "task_id": task_id}


@app.get("/task/{task_id}")
async def get_task(task_id: str, authorization: str | None = Header(None)) -> dict:
    """Poll task status. Uses user token so Directus enforces per-user access."""
    user_token = _extract_token(authorization)
    d = _get_directus(user_token)
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