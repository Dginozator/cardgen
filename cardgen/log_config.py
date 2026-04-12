"""Файловые логи и журнал промптов (RouterAI)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_PROMPT_CHARS = 500_000

_file_setup_done = False


def log_dir() -> Path:
    return Path(os.environ.get("CARDGEN_LOG_DIR", "data/logs")).resolve()


def format_api_error(err: BaseException) -> str:
    """
    Сжатое описание ошибки HTTP/API (OpenAI SDK, httpx) для логов — без ключей.
    """
    bits: list[str] = [f"{type(err).__name__}: {err}"]
    sc = getattr(err, "status_code", None)
    if sc is not None:
        bits.append(f"http_status={sc}")
    code = getattr(err, "code", None)
    if code is not None and code != sc:
        bits.append(f"code={code}")
    typ = getattr(err, "type", None)
    if typ:
        bits.append(f"type={typ}")
    rid = getattr(err, "request_id", None)
    if rid:
        bits.append(f"request_id={rid}")

    body = getattr(err, "body", None)
    if body is not None:
        if isinstance(body, (dict, list)):
            try:
                s = json.dumps(body, ensure_ascii=False)[:4000]
            except Exception:
                s = repr(body)[:4000]
        else:
            s = repr(body)[:4000]
        bits.append(f"body={s}")

    resp = getattr(err, "response", None)
    if resp is not None:
        try:
            txt = getattr(resp, "text", None)
            if txt:
                bits.append(f"raw_response={txt[:4000]}")
        except Exception:
            pass

    return " | ".join(bits)


def ensure_file_logging() -> None:
    """Один раз: cardgen.log (всё под cardgen.*) и prompts.log (только строки промптов)."""
    global _file_setup_done
    if _file_setup_done:
        return

    d = log_dir()
    d.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main_log = d / "cardgen.log"
    fh = logging.FileHandler(main_log, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    root_cardgen = logging.getLogger("cardgen")
    root_cardgen.addHandler(fh)
    root_cardgen.setLevel(logging.INFO)

    pj = logging.getLogger("cardgen.prompts_journal")
    pj.setLevel(logging.INFO)
    pj.propagate = False
    pl_path = d / "prompts.log"
    if not pj.handlers:
        ph = logging.FileHandler(pl_path, encoding="utf-8")
        ph.setLevel(logging.INFO)
        ph.setFormatter(logging.Formatter("%(message)s"))
        pj.addHandler(ph)

    _file_setup_done = True


def flatten_messages_for_log(messages: Any) -> str:
    """Текст запроса к API: роли, текстовые части; картинки как [image]."""
    if not messages:
        return ""
    parts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "?")
        content = msg.get("content")
        parts.append(f"<<{role}>>")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                bt = block.get("type")
                if bt == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif bt == "image_url":
                    parts.append("[image]")
        parts.append(" ")
    out = " ".join(parts).strip()
    if len(out) > _MAX_PROMPT_CHARS:
        out = out[:_MAX_PROMPT_CHARS] + "\n...[truncated]"
    return out


def log_nn_prompt(operation: str, model: str, messages: Any) -> None:
    """
    Одна строка в prompts.log — три поля через таб:
    время (UTC ISO) \\t модель \\t промпт (op=... и текст запроса, картинки как [image]).
    """
    ensure_file_logging()
    body = flatten_messages_for_log(messages)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe = body.replace("\t", " ").replace("\n", "\\n")
    prompt = f"op={operation} | {safe}"
    line = f"{ts}\t{model}\t{prompt}"
    logging.getLogger("cardgen.prompts_journal").info(line)
