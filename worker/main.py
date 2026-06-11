"""FastAPI worker: accept generation tasks, orchestrate pipeline, return results."""

from __future__ import annotations

import asyncio
import io
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
from .svg_compositor import SVGCompositor, UserData

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

    if token:
        try:
            return await _get_directus(token).get_templates(is_active=True)
        except Exception:
            logger.warning("user token failed for templates, trying fallbacks")

    if DIRECTUS_TOKEN:
        try:
            return await _get_directus(DIRECTUS_TOKEN).get_templates(is_active=True)
        except Exception:
            logger.warning("static token also failed for templates, trying public access")

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


@app.post("/templates/upload")
async def upload_template(
    name: str = Form(...),
    slug: str = Form(...),
    svg_file: UploadFile = File(...),
    style_hints: str = Form(""),
    output_format: str = Form("PNG"),
    authorization: str | None = Header(None),
) -> dict:
    """
    Upload an SVG template file.

    1. Upload SVG to Directus as a file
    2. Parse SVG to extract width/height
    3. Create template record
    4. Generate preview with demo data
    """
    token = _extract_token(authorization)
    if not token and not DIRECTUS_TOKEN:
        raise HTTPException(status_code=401, detail="Authorization required")
    d = _get_directus(token or DIRECTUS_TOKEN)

    # Read SVG
    svg_bytes = await svg_file.read()
    if not svg_bytes:
        raise HTTPException(status_code=400, detail="Empty SVG file")

    # Validate SVG
    try:
        compositor = SVGCompositor(svg_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid SVG: {e}") from e

    warnings = compositor.validate()
    if warnings:
        logger.warning("Template validation warnings: %s", warnings)

    width, height = compositor.get_canvas_size()

    # Upload SVG file to Directus
    svg_filename = f"template_{slug}.svg"
    try:
        file_record = await d.upload_file(svg_bytes, svg_filename, "image/svg+xml")
        svg_file_id = file_record.get("id", "")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to upload SVG: {e}") from e

    # Create template record
    try:
        template = await d.create_template({
            "name": name,
            "slug": slug,
            "svg_file": svg_file_id,
            "width": width,
            "height": height,
            "output_format": output_format,
            "style_hints": style_hints,
            "is_active": True,
        })
        template_id = template.get("id", "")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to create template: {e}") from e

    # Generate preview in background
    async def _gen_preview():
        try:
            preview_bytes = _generate_preview(svg_bytes, output_format)
            preview_record = await d.upload_file(
                preview_bytes,
                f"preview_{slug}.png",
                "image/png",
            )
            await d.update_template(template_id, {
                "preview_image": preview_record.get("id", ""),
            })
            logger.info("preview generated for template %s", template_id)
        except Exception:
            logger.exception("failed to generate preview for template %s", template_id)

    bg_task = asyncio.create_task(_gen_preview())
    _track_task(bg_task)

    return {
        "ok": True,
        "template_id": template_id,
        "width": width,
        "height": height,
        "warnings": warnings,
    }


@app.post("/templates/{template_id}/regenerate-preview")
async def regenerate_preview(
    template_id: str,
    authorization: str | None = Header(None),
) -> dict:
    """Regenerate preview image for a template."""
    token = _extract_token(authorization)
    if not token and not DIRECTUS_TOKEN:
        raise HTTPException(status_code=401, detail="Authorization required")
    d = _get_directus(token or DIRECTUS_TOKEN)

    try:
        template = await d.get_template(template_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Template not found") from e

    svg_file_id = template.get("svg_file")
    if not svg_file_id:
        raise HTTPException(status_code=400, detail="Template has no SVG file")

    svg_bytes = await d.download_file(svg_file_id)
    output_format = template.get("output_format", "PNG")

    preview_bytes = _generate_preview(svg_bytes, output_format)
    preview_record = await d.upload_file(
        preview_bytes,
        f"preview_{template_id[:8]}.png",
        "image/png",
    )
    await d.update_template(template_id, {
        "preview_image": preview_record.get("id", ""),
    })

    return {"ok": True, "preview_image": preview_record.get("id", "")}


def _generate_preview(svg_bytes: bytes, output_format: str = "PNG") -> bytes:
    """Generate preview image from SVG with demo data."""
    compositor = SVGCompositor(svg_bytes)

    # Insert demo data
    demo_data = UserData(
        title="Demo Product",
        bullets=["Feature One", "Feature Two", "Feature Three"],
        product_image=_create_demo_image(),
    )

    if demo_data.product_image:
        compositor.insert_product_image(demo_data.product_image)
    compositor.insert_all_texts(demo_data)
    compositor.insert_all_bullets(demo_data)

    return compositor.render(output_format)


def _create_demo_image() -> bytes:
    """Create a simple placeholder product image."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (400, 400), (200, 200, 200, 255))
    draw = ImageDraw.Draw(img)
    # Draw a simple box with "PRODUCT" text
    draw.rectangle([50, 50, 350, 350], outline=(100, 100, 100), width=3)
    draw.line([50, 50, 350, 350], fill=(150, 150, 150), width=2)
    draw.line([350, 50, 50, 350], fill=(150, 150, 150), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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
    body = await product_image.read()
    if not body:
        raise HTTPException(status_code=400, detail="Пустой файл изображения.")
    if len(body) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой (макс. {MAX_UPLOAD_MB} МБ).")

    user_token = _extract_token(authorization)
    if not user_token:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")

    d = _get_directus(user_token)

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

    import json
    try:
        bullets = json.loads(bullets_json) if bullets_json else []
    except Exception:
        bullets = []

    try:
        file_record = await d.upload_file(body, product_image.filename or "product.png")
        file_id = file_record.get("id", "")
    except Exception as e:
        logger.exception("failed to upload product image")
        raise HTTPException(status_code=502, detail=f"Ошибка загрузки файла: {e}") from e

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

    d_admin = _get_directus(DIRECTUS_TOKEN or None)

    async def _run():
        await run_generation(task_id, d_admin)

    bg_task = asyncio.create_task(_run())
    _track_task(bg_task)

    return {"ok": True, "task_id": task_id}


@app.post("/process/{task_id}")
async def process_task(task_id: str) -> dict:
    """Trigger background processing for an existing task."""
    if not DIRECTUS_TOKEN:
        raise HTTPException(status_code=503, detail="Worker has no DIRECTUS_TOKEN configured.")

    d_admin = _get_directus(DIRECTUS_TOKEN)

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
    """Poll task status."""
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