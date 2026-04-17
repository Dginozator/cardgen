"""FastAPI: форма генерации (товар + текст + референс файлом или URL)."""

from __future__ import annotations

import base64
import logging
import os
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from cardgen.log_config import ensure_file_logging, format_api_error, log_dir
from cardgen.routerai import (
    SUPPORTED_SUFFIXES,
    fetch_image_bytes_from_url,
    infer_image_suffix,
    run_web_generate,
)

logger = logging.getLogger(__name__)

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    logging.getLogger("cardgen.routerai").setLevel(logging.INFO)
    logging.getLogger("cardgen.web").setLevel(logging.INFO)
    for name in ("httpcore", "httpx", "openai", "urllib3", "watchfiles", "multipart"):
        logging.getLogger(name).setLevel(logging.WARNING)
    ensure_file_logging()


_configure_logging()

MAX_UPLOAD = 15 * 1024 * 1024


def _save_upload(td: Path, prefix: str, body: bytes, original_name: str | None) -> Path:
    """Write image with a real extension so data: URLs get correct MIME for the API."""
    suf = Path(original_name or "").suffix.lower()
    if suf not in SUPPORTED_SUFFIXES:
        suf = infer_image_suffix(body)
    path = td / f"{prefix}{suf}"
    path.write_bytes(body)
    return path

_BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

app = FastAPI(title="Cardgen", description="Генерация визуала по товару и референсу")
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")


@app.middleware("http")
async def log_http(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    logger.info("HTTP %s %s -> %s %.3fs", request.method, request.url.path, resp.status_code, time.perf_counter() - t0)
    return resp


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    # Starlette 1.x: (request, name, context?)
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/generate")
async def api_generate(
    prompt: str = Form(...),
    product: UploadFile = File(...),
    reference: UploadFile | None = File(None),
    reference_url: str = Form(""),
    skip_enhance: str | None = Form(default=None),
    with_review: str | None = Form(default=None),
) -> JSONResponse:
    if not prompt or not prompt.strip():
        return JSONResponse({"ok": False, "error": "Введите текст запроса."}, status_code=400)

    skip_flag = skip_enhance in ("true", "on", "1")
    review_flag = with_review in ("true", "on", "1")

    if not product.filename:
        return JSONResponse({"ok": False, "error": "Нужно загрузить изображение товара."}, status_code=400)

    prod_body = await product.read()
    if len(prod_body) > MAX_UPLOAD:
        return JSONResponse({"ok": False, "error": "Файл товара слишком большой (макс. 15 МБ)."}, status_code=400)

    ref_path: Path | None = None
    tmpdir = tempfile.TemporaryDirectory(prefix="cardgen-")
    try:
        td = Path(tmpdir.name)
        product_path = _save_upload(td, "product", prod_body, product.filename)

        if reference and reference.filename:
            ref_body = await reference.read()
            if len(ref_body) > MAX_UPLOAD:
                return JSONResponse(
                    {"ok": False, "error": "Файл референса слишком большой (макс. 15 МБ)."},
                    status_code=400,
                )
            ref_path = _save_upload(td, "reference", ref_body, reference.filename)
        elif reference_url and reference_url.strip():
            try:
                ref_bytes = fetch_image_bytes_from_url(reference_url.strip())
                if len(ref_bytes) > MAX_UPLOAD:
                    return JSONResponse(
                        {"ok": False, "error": "Картинка по ссылке слишком большая."},
                        status_code=400,
                    )
                ref_path = _save_upload(td, "reference", ref_bytes, None)
            except ValueError as e:
                return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

        try:
            data, enhanced, review = run_web_generate(
                prompt.strip(),
                product_path,
                ref_path,
                skip_enhance=skip_flag,
                with_review=review_flag,
            )
        except Exception as e:
            detail = format_api_error(e)
            logger.exception("api/generate failed | %s", detail)
            msg = str(e)
            if len(msg) > 2000:
                msg = msg[:2000] + "…"
            return JSONResponse(
                {
                    "ok": False,
                    "error": msg,
                    "log_hint": f"Полный traceback и pipeline[web] — в {log_dir() / 'cardgen.log'}",
                },
                status_code=500,
            )

        b64 = base64.standard_b64encode(data).decode("ascii")
        suf = infer_image_suffix(data)
        mime = _MIME_BY_SUFFIX.get(suf, "image/png")
        return JSONResponse(
            {
                "ok": True,
                "image_base64": b64,
                "mime": mime,
                "enhanced_prompt": enhanced,
                "review": review,
            }
        )
    finally:
        tmpdir.cleanup()


def main() -> None:
    import uvicorn

    _configure_logging()
    host = os.environ.get("CARDGEN_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("CARDGEN_WEB_PORT", "8765"))
    uvicorn.run("cardgen.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
