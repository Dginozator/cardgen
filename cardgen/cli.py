"""Command-line interface (RouterAI only: GPT-5.4 + Nano Banana)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cardgen.routerai import process_directory_remote


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cardgen",
        description="Обработка фото товаров через RouterAI (GPT-5.4 -> Nano Banana), без локального CV.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    proc = sub.add_parser(
        "process",
        help="Для каждого изображения: план (GPT) и редактирование (Nano Banana); PNG в --out",
    )
    proc.add_argument(
        "--in",
        dest="input_dir",
        type=Path,
        required=True,
        help="Входная папка (рекурсивно)",
    )
    proc.add_argument(
        "--out",
        dest="output_dir",
        type=Path,
        required=True,
        help="Выходная папка (те же относительные пути, расширение .png)",
    )
    proc.add_argument(
        "--brief",
        type=str,
        default=None,
        help="Дополнительный контекст для планировщика (ниша, требования к фону и т.д.)",
    )
    proc.add_argument(
        "--instruction",
        type=str,
        default=None,
        metavar="TEXT",
        help="Если задано, шаг GPT пропускается; эта инструкция передаётся в Nano Banana для всех файлов",
    )
    proc.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробный лог",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    for name in ("httpcore", "httpx", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)

    if args.command == "process":

        def _log_ok(src: Path, dst: Path) -> None:
            logging.info("OK %s -> %s", src, dst)

        ok, fail = process_directory_remote(
            args.input_dir,
            args.output_dir,
            brief=args.brief,
            fixed_instruction=args.instruction,
            on_file=_log_ok,
        )
        logging.info("Готово: %d ок, %d ошибок", ok, fail)
        return 1 if fail and ok == 0 else (0 if fail == 0 else 2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
