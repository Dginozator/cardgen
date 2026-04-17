"""Remote processing via RouterAI (OpenAI-compatible API).

Переменные из `.env` (после load_dotenv): ROUTERAI_API_KEY или OPENAI_API_KEY (обязательно);
опционально ROUTERAI_BASE_URL, CARDGEN_CHAT_MODEL, CARDGEN_IMAGE_MODEL.
Пустое значение в .env = использовать встроенный default.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)


def _load_dotenv_files() -> None:
    """Load .env from repo root (next to pyproject.toml) or walk up from cwd."""
    here = Path(__file__).resolve()
    for d in here.parents:
        if (d / "pyproject.toml").is_file() and (d / ".env").is_file():
            load_dotenv(d / ".env")
            return
    load_dotenv()


_load_dotenv_files()

DEFAULT_BASE_URL = "https://routerai.ru/api/v1"
DEFAULT_CHAT_MODEL = "openai/gpt-5.4"
DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image"


def _env_optional(key: str, default: str) -> str:
    """Read env; empty or whitespace-only string falls back to default."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    s = str(raw).strip()
    return s if s else default

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

PROMPT_ENHANCER_SYSTEM = (
    "Ты усиливаешь черновой текстовый запрос пользователя для модели генерации изображений "
    "(Nano Banana / Gemini Image). Сохрани намерение пользователя, добавь конкретику: композиция, свет, "
    "материалы, фон, стиль, соотношение сторон, детали кадра. "
    "Ты хорошо понимаешь сегментацию сцены: если нужен изолированный товар, чётко опиши границы объекта, "
    "отделение от фона, при необходимости -- нейтральный или белый фон #FFFFFF для маркетплейса. "
    "Ответь ОДНИМ готовым промптом для генератора, без преамбулы и пояснений."
)

REVIEWER_SYSTEM = (
    "Ты проверяешь результат генерации изображения по запросу. У тебя есть исходный запрос пользователя, "
    "промпт, который ушёл в генератор, и само изображение. "
    "Дай краткую оценку (2-4 предложения), затем нумерованный список из 3-7 конкретных предложений, "
    "что можно улучшить в следующей итерации (свет, композиция, фон, детали, артефакты, текст на товаре). "
    "В конце одна строка: готовность к публикации: да / с доработками / нет -- с пояснением в скобках. "
    "Пиши по-русски, деловым тоном."
)

PLANNER_SYSTEM = (
    "Ты помогаешь готовить фото товара для маркетплейса (Wildberries). "
    "По входному изображению товара напиши ТОЛЬКО краткую конкретную инструкцию (3–8 предложений) "
    "на русском для модели редактирования изображений: свет, нейтральный/белый фон #FFFFFF при необходимости, "
    "убрать шум и отвлекающий фон, сохранить форму и пропорции товара, не добавлять водяные знаки и текст. "
    "Без вступлений и пояснений — только текст инструкции."
)

WEB_MULTIMODAL_SYSTEM = (
    "Ты готовишь один цельный промпт для модели генерации изображений (Nano Banana / Gemini Image). "
    "Первое изображение — фото товара: сохрани узнаваемость объекта, материалы, цвет корпуса. "
    "Если дано второе изображение — это референс карточки с маркетплейса: опиши, как повторить структуру блоков, "
    "сетку, стиль инфографики, акцентные цвета, иерархию текста (без копирования чужих логотипов и торговых знаков). "
    "Текст пользователя задаёт задачу (например инфографика, главное фото, коллаж). "
    "Ответь ОДНИМ подробным промптом на русском: композиция, фон, соотношение сторон, что где разместить, "
    "как стилизовать итог. Без преамбулы."
)

MAX_FETCH_BYTES = 20 * 1024 * 1024
_FETCH_UA = "Mozilla/5.0 (compatible; Cardgen/0.1)"


def _env_api_key() -> str:
    key = os.environ.get("ROUTERAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key or not key.strip():
        raise RuntimeError(
            "Нет ключа RouterAI: задайте ROUTERAI_API_KEY в файле .env в корне проекта "
            "(скопируйте .env.example в .env) или в переменных окружения."
        )
    return key.strip()


def make_client() -> OpenAI:
    base = _env_optional("ROUTERAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return OpenAI(api_key=_env_api_key(), base_url=base)


def nn_chat_complete(client: OpenAI, operation: str, **kwargs: Any) -> Any:
    """Все вызовы chat.completions к RouterAI — с логом (операция, модель, время, usage)."""
    from cardgen.log_config import format_api_error, log_nn_prompt

    model = kwargs.get("model", "?")
    log_nn_prompt(operation, model, kwargs.get("messages"))
    logger.info("NN request op=%s model=%s", operation, model)
    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(**kwargs)
        dt = time.perf_counter() - t0
        usage = getattr(resp, "usage", None)
        if usage is not None:
            ud = usage.model_dump() if hasattr(usage, "model_dump") else str(usage)
            logger.info("NN ok op=%s model=%s %.3fs usage=%s", operation, model, dt, ud)
        else:
            logger.info("NN ok op=%s model=%s %.3fs", operation, model, dt)
        return resp
    except Exception as e:
        dt = time.perf_counter() - t0
        detail = format_api_error(e)
        logger.exception(
            "NN fail op=%s model=%s %.3fs | %s",
            operation,
            model,
            dt,
            detail,
        )
        raise


def chat_model_id() -> str:
    return _env_optional("CARDGEN_CHAT_MODEL", DEFAULT_CHAT_MODEL)


def image_model_id() -> str:
    return _env_optional("CARDGEN_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)


def infer_image_suffix(data: bytes) -> str:
    """Pick file suffix from magic bytes (for uploads without reliable filename)."""
    if len(data) >= 3 and data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 2 and data[:2] == b"BM":
        return ".bmp"
    return ".png"


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("image/"):
        return mime
    suf = path.suffix.lower()
    by_suf = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    if suf in by_suf:
        return by_suf[suf]
    if path.is_file():
        head = path.read_bytes()[:32]
        if head.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return "image/webp"
        if head.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
    return "image/jpeg"


def _image_data_url(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{_guess_mime(path)};base64,{b64}"


def _content_part_as_mapping(block: object) -> dict[str, Any] | None:
    """OpenAI SDK often returns content parts as Pydantic models, not dicts."""
    if isinstance(block, dict):
        return block
    dump = getattr(block, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="python")
        except TypeError:
            return dump()
    return None


def _strings_from_assistant_content_mapping(m: Mapping[str, Any]) -> list[str]:
    """Collect text lines and image payloads from one content block (dict-like)."""
    out: list[str] = []
    t = m.get("type")
    if t == "text" and isinstance(m.get("text"), str):
        out.append(m["text"])
    elif t == "image_url":
        iu = m.get("image_url")
        if isinstance(iu, dict) and isinstance(iu.get("url"), str):
            out.append(iu["url"])
        elif isinstance(iu, str):
            out.append(iu)
    elif t == "refusal" and isinstance(m.get("refusal"), str):
        out.append(m["refusal"])
    # DALL-E style (на случай прокси)
    if isinstance(m.get("b64_json"), str):
        out.append(m["b64_json"])
    inline = m.get("inline_data") or m.get("inlineData")
    if isinstance(inline, Mapping):
        mime = inline.get("mime_type") or inline.get("mimeType") or "image/png"
        data = inline.get("data")
        if isinstance(mime, str) and isinstance(data, str):
            out.append(f"data:{mime};base64,{data}")
    return out


def _message_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        m = _content_part_as_mapping(block)
        if m is not None:
            parts.extend(_strings_from_assistant_content_mapping(m))
            continue
        if hasattr(block, "text"):
            t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
            continue
        iurl = getattr(block, "image_url", None)
        if iurl is not None:
            u = getattr(iurl, "url", None)
            if isinstance(u, str):
                parts.append(u)
    return "\n".join(parts).strip()


def _assistant_visible_text(message: object) -> str:
    """Text or image URL(s) from assistant message (string or content parts)."""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return _message_text(content)
    return ""


def _get_message_field(message: object, name: str) -> Any:
    """Поле модели или из __pydantic_extra__ (RouterAI добавляет images, reasoning)."""
    if hasattr(message, name):
        v = getattr(message, name, None)
        if v is not None:
            return v
    extra = getattr(message, "__pydantic_extra__", None)
    if isinstance(extra, dict) and name in extra:
        return extra.get(name)
    return None


def _dict_image_payload_strings(d: Mapping[str, Any]) -> list[str]:
    """Вытащить data URL / http(s) / сырой base64 из одного объекта ответа."""
    out: list[str] = []
    for key in ("url", "uri", "src", "href", "b64_json", "base64_data"):
        v = d.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    iu = d.get("image_url")
    if isinstance(iu, dict) and isinstance(iu.get("url"), str):
        out.append(iu["url"].strip())
    elif isinstance(iu, str) and iu.strip():
        out.append(iu.strip())
    inline = d.get("inline_data") or d.get("inlineData")
    if isinstance(inline, Mapping):
        mime = inline.get("mime_type") or inline.get("mimeType") or "image/png"
        data = inline.get("data")
        if isinstance(mime, str) and isinstance(data, str) and data.strip():
            out.append(f"data:{mime};base64,{data.strip()}")
    data = d.get("data")
    mime = d.get("mime_type") or d.get("mimeType")
    if isinstance(data, str) and data.strip():
        if isinstance(mime, str) and mime.startswith("image/"):
            out.append(f"data:{mime};base64,{data.strip()}")
        elif mime is None and not any(d.get(k) for k in ("url", "uri", "image_url", "b64_json")):
            out.append(data.strip())
    return out


def _collect_image_payload_strings(node: object, depth: int = 0) -> list[str]:
    """Рекурсивно: строки с картинкой из ответа провайдера (поле images и вложения)."""
    if depth > 14:
        return []
    if node is None:
        return []
    if isinstance(node, str):
        s = node.strip()
        return [s] if s else []
    if isinstance(node, (list, tuple)):
        acc: list[str] = []
        for x in node:
            acc.extend(_collect_image_payload_strings(x, depth + 1))
        return acc
    if isinstance(node, dict):
        acc = _dict_image_payload_strings(node)
        for k, v in node.items():
            if k in ("text", "reasoning", "thought", "message") and isinstance(v, str):
                continue
            if isinstance(v, (dict, list, tuple)):
                acc.extend(_collect_image_payload_strings(v, depth + 1))
        return acc
    m = _content_part_as_mapping(node)
    if m is not None:
        return _strings_from_assistant_content_mapping(m)
    return []


def _all_image_try_strings_from_assistant_message(message: object) -> list[str]:
    """
    Все кандидаты для декодирования: content + поле images (Gemini/RouterAI).
    Порядок: сначала объединённый content, затем отдельные payloads из images.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def add(s: str) -> None:
        s = s.strip()
        if not s or s in seen:
            return
        seen.add(s)
        ordered.append(s)

    main = _assistant_visible_text(message)
    if main:
        add(main)

    raw_images = _get_message_field(message, "images")
    for s in _collect_image_payload_strings(raw_images, 0):
        add(s)

    return ordered


def _safe_debug_assistant_message(message: object, max_len: int = 1200) -> str:
    """Краткое описание ответа ассистента для логов (без длинных base64)."""
    bits: list[str] = []
    bits.append(f"role={getattr(message, 'role', None)!r}")
    rf = getattr(message, "refusal", None)
    if rf:
        bits.append(f"refusal={rf!r}")
    c = getattr(message, "content", None)
    bits.append(f"content_type={type(c).__name__}")
    if isinstance(c, str):
        bits.append(f"str_len={len(c)}")
    elif isinstance(c, list):
        bits.append(f"parts={len(c)}")
        for i, block in enumerate(c[:5]):
            m = _content_part_as_mapping(block)
            if m is not None:
                bits.append(f"[{i}]type={m.get('type')!r}")
            else:
                bits.append(f"[{i}]cls={type(block).__name__}")
    extra = getattr(message, "__pydantic_extra__", None) or {}
    if isinstance(extra, dict) and extra:
        bits.append(f"extra_keys={list(extra.keys())!r}")
    img = _get_message_field(message, "images")
    if img is not None:
        bits.append(f"images_type={type(img).__name__}")
        if isinstance(img, list):
            bits.append(f"images_n={len(img)}")
            for j, it in enumerate(img[:3]):
                bits.append(f"img[{j}]={type(it).__name__}")
    s = " ".join(bits)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _extract_image_bytes_from_assistant_message(message: object, *, operation: str) -> bytes:
    """
    Извлекает байты изображения из ответа chat.completions.
    Учитывает content, части SDK (image_url, inline_data) и поле images у RouterAI/Gemini.
    """
    candidates = _all_image_try_strings_from_assistant_message(message)
    if not candidates:
        logger.warning(
            "Нет данных изображения в ответе ассистента op=%s | %s",
            operation,
            _safe_debug_assistant_message(message),
        )
        raise RuntimeError("Пустой ответ модели изображений.")
    last_err: Exception | None = None
    for raw in candidates:
        try:
            return _extract_image_bytes(raw)
        except Exception as e:
            last_err = e
    logger.error(
        "Не удалось декодировать ни один кандидат op=%s n=%s | %s",
        operation,
        len(candidates),
        _safe_debug_assistant_message(message),
        exc_info=last_err,
    )
    if last_err is not None:
        raise last_err
    raise RuntimeError("Пустой ответ модели изображений.")


def enhance_prompt_for_generation(
    client: OpenAI,
    user_prompt: str,
    *,
    context: str | None = None,
) -> str:
    """Turn user draft into a strong prompt for Nano Banana (text-only generation)."""
    parts = ["Черновик запроса пользователя:", user_prompt.strip()]
    if context and context.strip():
        parts.extend(["", "Дополнительный контекст:", context.strip()])
    r = nn_chat_complete(
        client,
        "prompt_enhance_cli",
        model=chat_model_id(),
        messages=[
            {"role": "system", "content": PROMPT_ENHANCER_SYSTEM},
            {"role": "user", "content": "\n".join(parts)},
        ],
    )
    text = _assistant_visible_text(r.choices[0].message)
    if not text:
        raise RuntimeError("Пустой ответ при усилении промпта.")
    return text.strip()


def generate_image_from_prompt(client: OpenAI, prompt: str) -> bytes:
    """Text-to-image via Nano Banana (no reference image)."""
    r = nn_chat_complete(
        client,
        "image_t2i",
        model=image_model_id(),
        messages=[{"role": "user", "content": prompt.strip()}],
    )
    return _extract_image_bytes_from_assistant_message(r.choices[0].message, operation="image_t2i")


def _looks_like_image_bytes(data: bytes) -> bool:
    if len(data) < 12:
        return False
    if data.startswith(b"\xff\xd8\xff"):
        return True
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return True
    return False


def _extract_og_image_url(html: str) -> str | None:
    patterns = (
        r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
    )
    for pat in patterns:
        m = re.search(pat, html, re.I | re.DOTALL)
        if m:
            u = m.group(1).strip()
            if u.startswith("http"):
                return u
    return None


def fetch_image_bytes_from_url(url: str, *, _depth: int = 0) -> bytes:
    """
    Download image bytes. If URL returns HTML, try og:image once.
    """
    import urllib.error
    import urllib.request

    if _depth > 2:
        raise ValueError("Слишком много перенаправлений при загрузке по ссылке.")
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        raise ValueError("Нужна ссылка с http:// или https://")

    req = urllib.request.Request(u, headers={"User-Agent": _FETCH_UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise ValueError(f"HTTP {e.code} при загрузке ссылки") from e
    except OSError as e:
        raise ValueError(f"Не удалось загрузить URL: {e}") from e

    if len(data) > MAX_FETCH_BYTES:
        raise ValueError("Ответ по ссылке слишком большой.")

    if ct.startswith("image/"):
        return data
    if _looks_like_image_bytes(data):
        return data
    if "text/html" in ct or ct == "" or ct == "application/octet-stream":
        text = data.decode("utf-8", errors="replace")
        og = _extract_og_image_url(text)
        if og:
            return fetch_image_bytes_from_url(og, _depth=_depth + 1)
        raise ValueError(
            "Страница без og:image. Укажите прямую ссылку на картинку (.jpg, .png, .webp) "
            "или другую страницу карточки товара."
        )
    raise ValueError(f"Неожиданный Content-Type: {ct or 'unknown'}")


def enhance_prompt_web_multimodal(
    client: OpenAI,
    user_text: str,
    product_path: Path,
    reference_path: Path | None,
) -> str:
    """GPT sees product + optional style reference; returns one prompt for the image model."""
    parts: list[dict[str, object]] = [
        {"type": "text", "text": "Запрос пользователя:\n" + user_text.strip()},
        {"type": "text", "text": "Изображение 1 — фото товара (главный объект)."},
        {"type": "image_url", "image_url": {"url": _image_data_url(product_path)}},
    ]
    if reference_path is not None:
        parts.extend(
            [
                {
                    "type": "text",
                    "text": (
                        "Изображение 2 — референс карточки: повтори композицию, сетку и визуальный стиль "
                        "(инфографика, блоки, акценты), не воспроизводи чужие логотипы."
                    ),
                },
                {"type": "image_url", "image_url": {"url": _image_data_url(reference_path)}},
            ]
        )
    r = nn_chat_complete(
        client,
        "web_prompt_plan",
        model=chat_model_id(),
        messages=[
            {"role": "system", "content": WEB_MULTIMODAL_SYSTEM},
            {"role": "user", "content": parts},
        ],
    )
    text = _assistant_visible_text(r.choices[0].message)
    if not text:
        raise RuntimeError("Пустой ответ при подготовке промпта.")
    return text.strip()


def generate_image_multimodal(
    client: OpenAI,
    generation_prompt: str,
    product_path: Path,
    reference_path: Path | None,
) -> bytes:
    """Nano Banana: product image (+ optional reference) + text -> result image."""
    intro = (
        "Создай итоговое изображение по описанию. Сохрани узнаваемость товара с изображения A. "
        "Если есть изображение B — повтори структуру и стиль карточки (в т.ч. инфографику). "
        "Верни результат только как изображение.\n\nОписание:\n"
    )
    body = intro + generation_prompt.strip()
    msg: list[dict[str, object]] = [
        {"type": "text", "text": body},
        {"type": "text", "text": "A — товар:"},
        {"type": "image_url", "image_url": {"url": _image_data_url(product_path)}},
    ]
    if reference_path is not None:
        msg.extend(
            [
                {"type": "text", "text": "B — референс карточки (структура и стиль):"},
                {"type": "image_url", "image_url": {"url": _image_data_url(reference_path)}},
            ]
        )
    r = nn_chat_complete(
        client,
        "web_image_generate",
        model=image_model_id(),
        messages=[{"role": "user", "content": msg}],
    )
    return _extract_image_bytes_from_assistant_message(
        r.choices[0].message,
        operation="web_image_generate",
    )


def run_web_generate(
    user_text: str,
    product_path: Path,
    reference_path: Path | None,
    *,
    skip_enhance: bool = False,
    with_review: bool = False,
) -> tuple[bytes, str, str]:
    """
    Web pipeline: optional GPT prompt from images, multimodal generation, optional GPT review.
    Returns (png_bytes, enhanced_prompt, review_or_empty).
    """
    import tempfile

    logger.info(
        "pipeline[web] start product=%s ref=%s skip_enhance=%s with_review=%s chars=%d",
        product_path,
        reference_path,
        skip_enhance,
        with_review,
        len(user_text),
    )
    client = make_client()
    if skip_enhance:
        enhanced = user_text.strip()
        logger.info("pipeline[web] step=web_prompt_plan SKIPPED")
    else:
        logger.info("pipeline[web] step=web_prompt_plan START")
        try:
            enhanced = enhance_prompt_web_multimodal(client, user_text, product_path, reference_path)
        except Exception:
            logger.exception("pipeline[web] step=web_prompt_plan FAILED")
            raise
        logger.info("pipeline[web] step=web_prompt_plan OK chars=%d", len(enhanced))

    logger.info("pipeline[web] step=web_image_generate START")
    try:
        data = generate_image_multimodal(client, enhanced, product_path, reference_path)
    except Exception:
        logger.exception("pipeline[web] step=web_image_generate FAILED")
        raise
    logger.info("pipeline[web] step=web_image_generate OK bytes=%d", len(data))

    review = ""
    if with_review:
        logger.info("pipeline[web] step=review START")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(data)
            tmp = Path(f.name)
        try:
            try:
                review = review_generated_image(
                    client,
                    tmp,
                    user_prompt=user_text,
                    generation_prompt=enhanced,
                )
            except Exception:
                logger.exception("pipeline[web] step=review FAILED")
                raise
            logger.info("pipeline[web] step=review OK chars=%d", len(review))
        finally:
            tmp.unlink(missing_ok=True)
    else:
        logger.info("pipeline[web] step=review SKIPPED")

    logger.info("pipeline[web] done")
    return data, enhanced, review


def review_generated_image(
    client: OpenAI,
    image_path: Path,
    *,
    user_prompt: str,
    generation_prompt: str,
) -> str:
    """GPT-5.4 vision: critique + improvement ideas."""
    body = (
        "Исходный запрос пользователя:\n"
        f"{user_prompt.strip()}\n\n"
        "Промпт, отправленный в генератор изображений:\n"
        f"{generation_prompt.strip()}\n\n"
        "Оцени приложенное сгенерированное изображение."
    )
    r = nn_chat_complete(
        client,
        "image_review",
        model=chat_model_id(),
        messages=[
            {"role": "system", "content": REVIEWER_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": body},
                    {"type": "image_url", "image_url": {"url": _image_data_url(image_path)}},
                ],
            },
        ],
    )
    text = _assistant_visible_text(r.choices[0].message)
    if not text:
        raise RuntimeError("Пустой ответ ревьюера.")
    return text.strip()


@dataclass(frozen=True)
class GenerateOutcome:
    user_prompt: str
    enhanced_prompt: str
    image_path: Path
    review: str


def run_generate_pipeline(
    user_prompt: str,
    out_path: Path,
    *,
    context: str | None = None,
    skip_enhance: bool = False,
    skip_review: bool = False,
) -> GenerateOutcome:
    """
    1) GPT усиливает промпт (optional)
    2) Nano Banana генерирует изображение по тексту
    3) GPT проверяет картинку и предлагает улучшения (optional)
    """
    base = _env_optional("ROUTERAI_BASE_URL", DEFAULT_BASE_URL)
    logger.info(
        "pipeline[generate] start out=%s base_url=%s skip_enhance=%s skip_review=%s "
        "chat_model=%s image_model=%s user_prompt_chars=%d",
        out_path.resolve(),
        base,
        skip_enhance,
        skip_review,
        chat_model_id(),
        image_model_id(),
        len(user_prompt),
    )

    client = make_client()
    if skip_enhance:
        enhanced = user_prompt.strip()
        logger.info("pipeline[generate] step=enhance_prompt SKIPPED (using raw prompt)")
    else:
        logger.info("pipeline[generate] step=enhance_prompt START (prompt_enhance_cli)")
        try:
            enhanced = enhance_prompt_for_generation(client, user_prompt, context=context)
        except Exception:
            logger.exception("pipeline[generate] step=enhance_prompt FAILED")
            raise
        logger.info("pipeline[generate] step=enhance_prompt OK chars=%d", len(enhanced))

    logger.info("pipeline[generate] step=image_t2i START")
    try:
        data = generate_image_from_prompt(client, enhanced)
    except Exception:
        logger.exception("pipeline[generate] step=image_t2i FAILED")
        raise
    logger.info("pipeline[generate] step=image_t2i OK output_bytes=%d", len(data))

    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    logger.info("pipeline[generate] file written %s", out_path)

    if skip_review:
        review = ""
        logger.info("pipeline[generate] step=review SKIPPED")
    else:
        logger.info("pipeline[generate] step=review START")
        try:
            review = review_generated_image(
                client,
                out_path,
                user_prompt=user_prompt,
                generation_prompt=enhanced,
            )
        except Exception:
            logger.exception("pipeline[generate] step=review FAILED")
            raise
        logger.info("pipeline[generate] step=review OK chars=%d", len(review))

    logger.info("pipeline[generate] done")
    return GenerateOutcome(
        user_prompt=user_prompt.strip(),
        enhanced_prompt=enhanced,
        image_path=out_path,
        review=review,
    )


def plan_image_instruction(
    client: OpenAI,
    image_path: Path,
    *,
    brief: str | None = None,
) -> str:
    """Ask GPT-5.4 for an editing instruction (Russian) given the product image."""
    user_parts: list[dict[str, object]] = [
        {
            "type": "image_url",
            "image_url": {"url": _image_data_url(image_path)},
        },
    ]
    lines = ["Проанализируй фото товара и сформулируй инструкцию для редактирования (см. системное правило)."]
    if brief and brief.strip():
        lines.append("Дополнительный контекст от пользователя:")
        lines.append(brief.strip())
    user_parts.insert(0, {"type": "text", "text": "\n".join(lines)})

    r = nn_chat_complete(
        client,
        "process_planner",
        model=chat_model_id(),
        messages=[
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": user_parts},
        ],
    )
    choice = r.choices[0].message
    text = _assistant_visible_text(choice)
    if not text:
        raise RuntimeError("Пустой ответ планировщика (GPT).")
    return text.strip()


def _decode_single_image_payload(s: str) -> bytes:
    """Один фрагмент: markdown-картинка, data URL, http(s) или сырой base64."""
    s = s.strip()

    m = re.search(r"!\[[^\]]*\]\(([^)]+)\)", s)
    if m:
        s = m.group(1).strip()

    if s.startswith("data:image"):
        if ";base64," in s:
            rest = s.split(";base64,", 1)[1]
        else:
            _, _, rest = s.partition(",")
        if not rest:
            raise ValueError("Некорректный data URL изображения")
        b64 = re.sub(r"\s+", "", rest)
        return base64.standard_b64decode(b64)

    if s.startswith("http://") or s.startswith("https://"):
        import urllib.request

        req = urllib.request.Request(s, headers={"User-Agent": "cardgen/0.1"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()

    return base64.standard_b64decode(re.sub(r"\s+", "", s))


def _extract_image_bytes(content: str) -> bytes:
    """Parse image bytes from model reply: data URL, raw base64, http(s) URL, or markdown image."""
    s0 = content.strip()
    candidates: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        x = x.strip()
        if x and x not in seen:
            seen.add(x)
            candidates.append(x)

    add(s0)
    for line in s0.splitlines():
        add(line.strip())
    for m in re.finditer(r"data:image/[\w.+-]+;base64,[A-Za-z0-9+/=\s]+", s0):
        add(m.group(0))

    last_err: Exception | None = None
    for cand in candidates:
        try:
            return _decode_single_image_payload(cand)
        except Exception as e:
            last_err = e
    msg = "Пустой или нераспознанный ответ" if last_err is None else str(last_err)
    raise ValueError(f"Не удалось извлечь изображение из ответа модели: {msg}") from last_err


def run_image_model(
    client: OpenAI,
    image_path: Path,
    instruction: str,
) -> bytes:
    """Call Nano Banana (Gemini image) with source image + instruction; return image bytes."""
    url = _image_data_url(image_path)
    prompt = (
        "Отредактируй это фото товара согласно инструкции. Сохрани узнаваемость товара. "
        "Верни результат как изображение.\n\nИнструкция:\n"
        + instruction.strip()
    )
    r = nn_chat_complete(
        client,
        "process_image_edit",
        model=image_model_id(),
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            }
        ],
    )
    return _extract_image_bytes_from_assistant_message(
        r.choices[0].message,
        operation="process_image_edit",
    )


def iter_images(directory: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(directory.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES:
            out.append(p)
    return out


def output_png_path(input_dir: Path, output_dir: Path, src: Path) -> Path:
    rel = src.relative_to(input_dir.resolve())
    return (output_dir.resolve() / rel).with_suffix(".png")


def process_directory_remote(
    input_dir: Path,
    output_dir: Path,
    *,
    brief: str | None = None,
    fixed_instruction: str | None = None,
    on_file: Callable[[Path, Path], None] | None = None,
) -> tuple[int, int]:
    """
    For each image: optional GPT plan, then Nano Banana edit. Outputs are PNG.
    If fixed_instruction is set, GPT is skipped and the same instruction is used for all files.
    """
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    client = make_client()
    files = iter_images(input_dir)
    if not files:
        logger.warning("Нет поддерживаемых изображений в %s", input_dir)

    ok, fail = 0, 0
    for src in files:
        dst = output_png_path(input_dir, output_dir, src)
        try:
            if fixed_instruction is not None and fixed_instruction.strip():
                instruction = fixed_instruction.strip()
            else:
                instruction = plan_image_instruction(client, src, brief=brief)
                logger.debug("Instruction for %s: %s", src.name, instruction[:500])
            data = run_image_model(client, src, instruction)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            ok += 1
            if on_file:
                on_file(src, dst)
        except Exception as e:
            logger.exception("Ошибка %s: %s", src, e)
            fail += 1
    return ok, fail
