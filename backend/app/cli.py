from __future__ import annotations

import argparse
import logging
from pathlib import Path

from backend.app.extraction import DrawingExtractionPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract engineering drawing PDFs to JSON")
    parser.add_argument("input", type=Path, help="A PDF file or a directory containing PDFs")
    parser.add_argument("--output-dir", type=Path, default=Path("data/output"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
    paths = [args.input] if args.input.is_file() else sorted(args.input.glob("*.pdf"))
    if not paths:
        raise SystemExit(f"No PDF files found at {args.input}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = DrawingExtractionPipeline()
    for path in paths:
        extraction = pipeline.extract(path)
        destination = args.output_dir / f"{path.stem}.json"
        destination.write_text(extraction.model_dump_json(indent=2), encoding="utf-8")
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
