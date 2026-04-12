"""
Fetch product list from Wildberries search JSON and download preview images.

Uses public search endpoint (same as the storefront). Automated access may be
rate-limited; images are copyrighted by sellers/WB — use only for local tests.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# vol (nm // 100_000) -> basket index 1..30 (empirical; WB CDN routing)
_basket_cache: dict[int, int] = {}


def _urlopen(req: urllib.request.Request, timeout: float = 30.0, retries: int = 4) -> object:
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 2.0 ** (attempt + 1)
                logger.warning("HTTP 429, retry in %ss (%s/%s)", wait, attempt + 1, retries)
                time.sleep(wait)
                continue
            raise
        except OSError:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("_urlopen: exhausted retries")


def _head_ok(url: str, timeout: float = 15.0) -> bool:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with _urlopen(req, timeout=timeout, retries=2) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code == 200
    except OSError:
        return False


def basket_for_nm(nm_id: int) -> int:
    """Return basket index (1..30) for image host. Cached by vol."""
    vol = nm_id // 100_000
    if vol in _basket_cache:
        return _basket_cache[vol]
    part = nm_id // 1000
    for b in range(1, 31):
        url = f"https://basket-{b:02d}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/big/1.webp"
        if _head_ok(url):
            _basket_cache[vol] = b
            logger.debug("vol=%s -> basket=%s", vol, b)
            return b
    raise RuntimeError(f"Could not resolve basket for nm={nm_id} (vol={vol})")


def image_url(nm_id: int, pic: int, basket: int) -> str:
    vol = nm_id // 100_000
    part = nm_id // 1000
    return f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/big/{pic}.webp"


def search_products(
    query: str,
    *,
    page: int = 1,
    dest: str = "-1257786",
) -> list[dict]:
    """Return list of product dicts from search.wb.ru exactmatch API."""
    params = {
        "appType": "1",
        "curr": "rub",
        "dest": dest,
        "query": query,
        "page": str(page),
        "resultset": "catalog",
        "sort": "popular",
        "suppressSpellcheck": "false",
    }
    url = "https://search.wb.ru/exactmatch/ru/common/v4/search?" + urllib.parse.urlencode(
        params, encoding="utf-8"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with _urlopen(req, timeout=45) as r:
        data = json.load(r)
    products = data.get("products") or []
    if not isinstance(products, list):
        return []
    return products


def download_first_image(
    nm_id: int,
    dest_path: Path,
    *,
    pic_index: int = 1,
    delay_s: float = 0.35,
) -> None:
    """Download one webp image (big) to dest_path."""
    time.sleep(delay_s)
    b = basket_for_nm(nm_id)
    url = image_url(nm_id, pic_index, b)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with _urlopen(req, timeout=60) as r:
        body = r.read()
    dest_path.write_bytes(body)


def download_query_to_folder(
    query: str,
    out_dir: Path,
    *,
    pages: int = 1,
    max_items: int | None = 30,
    dest: str = "-1257786",
    delay_s: float = 0.35,
    prefix: str = "wb",
) -> tuple[int, int]:
    """
    Search and save first catalog image per product as wb_{nm}_1.webp.
    Returns (saved_count, skipped_errors).
    """
    out_dir = out_dir.resolve()
    saved = 0
    errors = 0
    for page in range(1, pages + 1):
        try:
            products = search_products(query, page=page, dest=dest)
        except OSError as e:
            logger.error("Search failed page %s: %s", page, e)
            errors += 1
            break
        for p in products:
            if max_items is not None and saved >= max_items:
                return saved, errors
            nm = p.get("id")
            if not isinstance(nm, int):
                continue
            fname = f"{prefix}_{nm}_1.webp"
            path = out_dir / fname
            try:
                download_first_image(nm, path, pic_index=1, delay_s=delay_s)
                saved += 1
                logger.info("Saved %s", path.name)
            except Exception as e:
                logger.warning("Skip nm=%s: %s", nm, e)
                errors += 1
    return saved, errors
