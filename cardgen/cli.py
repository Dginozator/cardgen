"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cardgen.pipeline import process_directory
from cardgen.wb_catalog import download_query_to_folder

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cardgen",
        description="Improve product photos for marketplaces (folder in → folder out).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    proc = sub.add_parser("process", help="Process all images under --in into --out")
    proc.add_argument(
        "--in",
        dest="input_dir",
        type=Path,
        required=True,
        help="Input directory (recursive)",
    )
    proc.add_argument(
        "--out",
        dest="output_dir",
        type=Path,
        required=True,
        help="Output directory (mirrors relative paths)",
    )
    proc.add_argument(
        "--white-bg",
        action="store_true",
        help="Segment product and composite on white (#FFFFFF)",
    )
    proc.add_argument(
        "--min-long-edge",
        type=int,
        default=1600,
        metavar="PX",
        help="Upscale so the long edge is at least this many pixels (default: 1600)",
    )
    proc.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )

    wb = sub.add_parser(
        "wb-download",
        help="Download first catalog images from WB search (for local testing only)",
    )
    wb.add_argument(
        "--query",
        required=True,
        help='Search query (e.g. "бытовая техника")',
    )
    wb.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Directory to save .webp files",
    )
    wb.add_argument("--pages", type=int, default=1, help="Search pages to fetch (default: 1)")
    wb.add_argument(
        "--max",
        type=int,
        default=20,
        metavar="N",
        help="Max images to download (default: 20)",
    )
    wb.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Seconds between HTTP requests (default: 0.35)",
    )
    wb.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    # Avoid megabytes of DEBUG from onnx/rembg when -v is used
    for name in (
        "onnxruntime",
        "onnxruntime.capi",
        "rembg",
        "urllib3",
        "numba",
        "llvmlite",
        "PIL",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    if args.command == "process":
        def _log_ok(src: Path, dst: Path) -> None:
            logging.info("OK %s -> %s", src, dst)

        ok, fail = process_directory(
            args.input_dir,
            args.output_dir,
            min_long_edge=args.min_long_edge,
            white_bg=args.white_bg,
            on_file=_log_ok,
        )
        logging.info("Done: %d ok, %d failed", ok, fail)
        return 1 if fail and ok == 0 else (0 if fail == 0 else 2)

    if args.command == "wb-download":
        saved, err = download_query_to_folder(
            args.query,
            args.out,
            pages=args.pages,
            max_items=args.max,
            delay_s=args.delay,
        )
        logging.info("WB download: saved %s, errors/skips %s", saved, err)
        return 1 if saved == 0 and err > 0 else 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
