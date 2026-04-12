"""Remote processing via RouterAI (OpenAI-compatible API)."""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Callable

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://routerai.ru/api/v1"
DEFAULT_CHAT_MODEL = "openai/gpt-5.4"
DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image"

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

PLANNER_SYSTEM = (
    "Ты помогаешь готовить фото товара для маркетплейса (Wildberries). "
    "По входному изображению товара напиши ТОЛЬКО краткую конкретную инструкцию (3–8 предложений) "
    "на русском для модели редактирования изображений: свет, нейтральный/белый фон #FFFFFF при необходимости, "
    "убрать шум и отвлекающий фон, сохранить форму и пропорции товара, не добавлять водяные знаки и текст. "
    "Без вступлений и пояснений — только текст инструкции."
)


def _env_api_key() -> str:
    key = os.environ.get("ROUTERAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key or not key.strip():
        raise RuntimeError(
            "Задайте переменную окружения ROUTERAI_API_KEY (или OPENAI_API_KEY) с ключом RouterAI."
        )
    return key.strip()


def make_client() -> OpenAI:
    base = os.environ.get("ROUTERAI_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    return OpenAI(api_key=_env_api_key(), base_url=base)


def chat_model_id() -> str:
    return os.environ.get("CARDGEN_CHAT_MODEL", DEFAULT_CHAT_MODEL).strip()


def image_model_id() -> str:
    return os.environ.get("CARDGEN_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip()


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("image/"):
        return mime
    suf = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(suf, "image/jpeg")


def _image_data_url(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{_guess_mime(path)};base64,{b64}"


def _message_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
            if block.get("type") == "image_url":
                url = block.get("image_url")
                if isinstance(url, dict) and isinstance(url.get("url"), str):
                    parts.append(url["url"])
        elif hasattr(block, "text"):
            t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
    return "\n".join(parts).strip()


def _assistant_visible_text(message: object) -> str:
    """Text or image URL(s) from assistant message (string or content parts)."""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return _message_text(content)
    return ""


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

    r = client.chat.completions.create(
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


def _extract_image_bytes(content: str) -> bytes:
    """Parse image bytes from model reply: data URL, raw base64, http(s) URL, or markdown image."""
    s = content.strip()

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

    # Whole string base64
    try:
        return base64.standard_b64decode(re.sub(r"\s+", "", s))
    except Exception as e:
        raise ValueError(f"Не удалось извлечь изображение из ответа модели: {e}") from e


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
    r = client.chat.completions.create(
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
    raw = _assistant_visible_text(r.choices[0].message)
    if not raw:
        raise RuntimeError("Пустой ответ модели изображений.")
    return _extract_image_bytes(raw)


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
