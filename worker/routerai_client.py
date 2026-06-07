"""RouterAI (OpenAI-compatible) client for background generation and prompt enhancement."""

from __future__ import annotations

import base64
import logging
import re
import time
from typing import Any

import httpx
from openai import OpenAI

from .config import CHAT_MODEL, IMAGE_MODEL, ROUTERAI_API_KEY, ROUTERAI_BASE_URL

logger = logging.getLogger(__name__)

BG_GENERATOR_SYSTEM = """\
Ты — дизайнер товарных карточек для маркетплейсов (Ozon, Wildberries).
По описанию товара и стилю шаблона создай детализированный промпт для генерации фона инфографики.

Требования к фону:
- Без текста, логотипов, водяных знаков
- Не закрывать центральную зону (там будет товар)
- Гармоничные цвета, подходящие для чтения белого текста
- Чистый, профессиональный вид

Ответ: только промпт для генерации фона, без пояснений."""


def make_client() -> OpenAI:
    return OpenAI(api_key=ROUTERAI_API_KEY, base_url=ROUTERAI_BASE_URL)


def _image_data_url(image_bytes: bytes) -> str:
    """Encode image bytes to data URL."""
    if image_bytes[:4] == b"\x89PNG":
        mime = "image/png"
    elif image_bytes[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = "image/png"
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_image_bytes(response: Any) -> bytes:
    """Extract image bytes from chat completion response."""
    message = response.choices[0].message

    # Check content parts
    content = getattr(message, "content", None)
    if isinstance(content, list):
        for part in content:
            d = part if isinstance(part, dict) else getattr(part, "model_dump", lambda: None)()
            if d and d.get("type") == "image_url":
                url = d.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    _, _, b64 = url.partition(";base64,")
                    return base64.standard_b64decode(b64)

    # Check images field (Gemini/RouterAI specific)
    for attr in ("images", "__pydantic_extra__"):
        images = getattr(message, attr, None)
        if attr == "__pydantic_extra__" and isinstance(images, dict):
            images = images.get("images")
        if isinstance(images, list):
            for img in images:
                if isinstance(img, dict):
                    for key in ("b64_json", "base64_data", "data"):
                        val = img.get(key, "")
                        if isinstance(val, str) and len(val) > 100:
                            return base64.standard_b64decode(val)

    # Check inline data
    extra = getattr(message, "__pydantic_extra__", None) or {}
    if isinstance(extra, dict):
        for key in ("inline_data", "inlineData"):
            inline = extra.get(key)
            if isinstance(inline, dict):
                data = inline.get("data", "")
                if isinstance(data, str) and data:
                    return base64.standard_b64decode(data)

    # Try text content as base64
    text = content if isinstance(content, str) else ""
    if text and len(text) > 100:
        cleaned = re.sub(r"\s+", "", text)
        # Remove markdown image wrapper
        m = re.search(r"data:image/[\w.+-]+;base64,([A-Za-z0-9+/=]+)", cleaned)
        if m:
            return base64.standard_b64decode(m.group(1))
        try:
            return base64.standard_b64decode(cleaned)
        except Exception:
            pass

    raise RuntimeError("Не удалось извлечь изображение из ответа модели.")


def enhance_bg_prompt(
    client: OpenAI,
    product_image: bytes,
    title: str,
    bullets: list[str],
    style_hints: str = "",
) -> str:
    """Generate a background prompt based on product and template style."""
    parts: list[dict[str, Any]] = [
        {"type": "text", "text": (
            f"Сгенерируй промпт для фона инфографики.\n"
            f"Товар: {title}\n"
            f"Характеристики: {', '.join(bullets)}\n"
            f"Стиль: {style_hints or 'профессиональный, минималистичный'}"
        )},
        {"type": "image_url", "image_url": {"url": _image_data_url(product_image)}},
    ]
    t0 = time.perf_counter()
    logger.info("routerai: enhance_bg_prompt start")
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": BG_GENERATOR_SYSTEM},
            {"role": "user", "content": parts},
        ],
    )
    logger.info("routerai: enhance_bg_prompt ok %.2fs", time.perf_counter() - t0)
    text = resp.choices[0].message.content or ""
    return text.strip()


def generate_background(
    client: OpenAI,
    prompt: str,
    width: int = 900,
    height: int = 1200,
) -> bytes:
    """Generate a background image via Nano Banana (text-to-image)."""
    full_prompt = (
        f"Создай фон для инфографики {width}x{height}px. "
        f"Центр должен быть свободным (там будет товар). "
        f"Без текста и логотипов.\n\n{prompt}"
    )
    t0 = time.perf_counter()
    logger.info("routerai: generate_background start")
    resp = client.chat.completions.create(
        model=IMAGE_MODEL,
        messages=[{"role": "user", "content": full_prompt}],
    )
    logger.info("routerai: generate_background ok %.2fs", time.perf_counter() - t0)
    return _extract_image_bytes(resp)