"""Command-line interface (RouterAI: GPT-5.4 + Nano Banana)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cardgen.routerai import process_directory_remote, run_generate_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cardgen",
        description="Генерация и обзор изображений через RouterAI (GPT-5.4 + Nano Banana).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    gen = sub.add_parser(
        "generate",
        help="Промпт -> GPT усиливает -> Nano Banana рисует -> GPT проверяет и предлагает улучшения",
    )
    gen.add_argument(
        "--prompt",
        "-p",
        required=True,
        help="Ваш черновой запрос (что должно быть на изображении)",
    )
    gen.add_argument(
        "--out",
        "-o",
        type=Path,
        default=Path("out") / "generated.png",
        help="Куда сохранить PNG (по умолчанию: out/generated.png)",
    )
    gen.add_argument(
        "--context",
        "-c",
        type=str,
        default=None,
        help="Доп. контекст для шага усиления промпта (ниша, маркетплейс, формат)",
    )
    gen.add_argument(
        "--skip-enhance",
        action="store_true",
        help="Не вызывать GPT для усиления; в генератор уходит --prompt как есть",
    )
    gen.add_argument(
        "--skip-review",
        action="store_true",
        help="Не вызывать GPT-ревью сгенерированной картинки",
    )
    gen.add_argument(
        "--review-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Дополнительно сохранить текст ревью в файл (например report.md)",
    )
    gen.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробный лог",
    )

    proc = sub.add_parser(
        "process",
        help="Папка с фото: GPT по картинке -> инструкция -> Nano Banana редактирует (legacy)",
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
        help="Дополнительный контекст для планировщика",
    )
    proc.add_argument(
        "--instruction",
        type=str,
        default=None,
        metavar="TEXT",
        help="Если задано, шаг GPT по фото пропускается; эта строка идет в Nano Banana для всех файлов",
    )
    proc.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробный лог",
    )
    return p


def _print_report(outcome, *, skip_review: bool) -> None:
    sep = "=" * 60
    print(sep, flush=True)
    print("Enhanced prompt (after GPT)", flush=True)
    print(sep, flush=True)
    print(outcome.enhanced_prompt, flush=True)
    print(flush=True)
    print(sep, flush=True)
    print("Saved image", flush=True)
    print(sep, flush=True)
    print(str(outcome.image_path), flush=True)
    print(flush=True)
    if not skip_review:
        print(sep, flush=True)
        print("Review and improvement ideas (GPT)", flush=True)
        print(sep, flush=True)
        print(outcome.review, flush=True)
        print(flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    for name in ("httpcore", "httpx", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)

    if args.command == "generate":
        try:
            outcome = run_generate_pipeline(
                args.prompt,
                args.out,
                context=args.context,
                skip_enhance=args.skip_enhance,
                skip_review=args.skip_review,
            )
        except Exception:
            logging.exception("generate failed")
            return 1
        _print_report(outcome, skip_review=args.skip_review)
        if args.review_file and not args.skip_review:
            args.review_file.parent.mkdir(parents=True, exist_ok=True)
            args.review_file.write_text(
                f"# Review\n\n{outcome.review}\n\n# Prompt\n\n{outcome.enhanced_prompt}\n",
                encoding="utf-8",
            )
            logging.info("Review saved: %s", args.review_file)
        elif args.review_file and args.skip_review:
            logging.warning("--review-file ignored with --skip-review")
        return 0

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
        logging.info("Done: %d ok, %d failed", ok, fail)
        return 1 if fail and ok == 0 else (0 if fail == 0 else 2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
