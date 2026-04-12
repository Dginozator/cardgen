"""Image enhancement pipeline for product photos (MVP A)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def _read_image(path: Path) -> np.ndarray:
    data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot decode image: {path}")
    return img


def _write_image(path: Path, bgr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    elif ext == ".png":
        ok, buf = cv2.imencode(".png", bgr)
    else:
        ok, buf = cv2.imencode(ext if ext else ".png", bgr)
    if not ok:
        raise RuntimeError(f"Failed to encode: {path}")
    path.write_bytes(buf.tobytes())


def _upscale_long_edge(bgr: np.ndarray, min_long_edge: int) -> np.ndarray:
    h, w = bgr.shape[:2]
    long_edge = max(h, w)
    if long_edge >= min_long_edge:
        return bgr
    scale = min_long_edge / long_edge
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)


def _gray_world_white_balance(bgr: np.ndarray) -> np.ndarray:
    img = bgr.astype(np.float32)
    avg_b, avg_g, avg_r = cv2.mean(img)[:3]
    gray = (avg_b + avg_g + avg_r) / 3.0
    if gray < 1e-3:
        return bgr
    img[:, :, 0] *= gray / max(avg_b, 1e-3)
    img[:, :, 1] *= gray / max(avg_g, 1e-3)
    img[:, :, 2] *= gray / max(avg_r, 1e-3)
    return np.clip(img, 0, 255).astype(np.uint8)


def _lab_clahe(bgr: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    l2 = clahe.apply(l)
    lab2 = cv2.merge([l2, a, b])
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)


def _denoise_color(bgr: np.ndarray, h: int = 6) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(bgr, None, h, h, 7, 21)


def _unsharp_mask(bgr: np.ndarray, sigma: float = 1.2, amount: float = 0.35) -> np.ndarray:
    blur = cv2.GaussianBlur(bgr, (0, 0), sigma)
    return cv2.addWeighted(bgr, 1.0 + amount, blur, -amount, 0)


def enhance_product_photo(
    bgr: np.ndarray,
    *,
    min_long_edge: int = 1600,
    use_white_bg: bool = False,
    rembg_session: object | None = None,
) -> np.ndarray:
    """
    Main enhancement path. If use_white_bg, expects rembg session for segmentation.
    """
    if use_white_bg:
        if rembg_session is None:
            raise ValueError("rembg_session required when use_white_bg=True")
        return _composite_white_background(bgr, rembg_session)

    x = _upscale_long_edge(bgr, min_long_edge)
    x = _gray_world_white_balance(x)
    x = _lab_clahe(x)
    x = _denoise_color(x)
    x = _unsharp_mask(x)
    return x


def _composite_white_background(bgr: np.ndarray, session: object) -> np.ndarray:
    from rembg import remove

    # First enhance a bit before cutout so edges are cleaner
    prep = _upscale_long_edge(bgr, 1600)
    prep = _gray_world_white_balance(prep)
    prep = _lab_clahe(prep, clip_limit=1.8)
    rgb = cv2.cvtColor(prep, cv2.COLOR_BGR2RGB)

    rgba = remove(rgb, session=session)
    if rgba.shape[2] != 4:
        raise RuntimeError("rembg did not return RGBA")

    h, w = rgba.shape[:2]
    white = np.ones((h, w, 3), dtype=np.float32) * 255.0
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    rgb = rgba[:, :, :3].astype(np.float32)
    comp = rgb * alpha + white * (1.0 - alpha)
    comp_bgr = cv2.cvtColor(comp.astype(np.uint8), cv2.COLOR_RGB2BGR)
    comp_bgr = _unsharp_mask(comp_bgr, sigma=0.9, amount=0.25)
    return comp_bgr


def iter_images(directory: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(directory.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES:
            out.append(p)
    return out


def process_directory(
    input_dir: Path,
    output_dir: Path,
    *,
    min_long_edge: int = 1600,
    white_bg: bool = False,
    on_file: Callable[[Path, Path], None] | None = None,
) -> tuple[int, int]:
    """
    Returns (ok_count, fail_count).
    """
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    files = iter_images(input_dir)
    if not files:
        logger.warning("No supported images under %s", input_dir)

    rembg_session = None
    if white_bg:
        from rembg.session_factory import new_session

        rembg_session = new_session("u2net")

    ok, fail = 0, 0
    for src in files:
        rel = src.relative_to(input_dir)
        dst = output_dir / rel
        try:
            bgr = _read_image(src)
            out = enhance_product_photo(
                bgr,
                min_long_edge=min_long_edge,
                use_white_bg=white_bg,
                rembg_session=rembg_session,
            )
            _write_image(dst, out)
            ok += 1
            if on_file:
                on_file(src, dst)
        except Exception as e:
            logger.exception("Failed %s: %s", src, e)
            fail += 1
    return ok, fail
