"""Export raw PyMuPDF page diagnostics and rendered page images.

This module intentionally performs no semantic engineering-drawing extraction.
It preserves PyMuPDF's native page text and geometry for inspection.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "input"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "output" / "debug"


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def resolve_input_path(raw_path: str | Path) -> Path:
    """Resolve a CLI path, including paths written relative to a nested repo folder."""
    path = Path(raw_path).expanduser()
    if path.exists():
        return path.resolve()

    project_relative = PROJECT_ROOT / path
    if project_relative.exists():
        return project_relative.resolve()

    parts = path.parts
    data_indexes = [index for index, part in enumerate(parts) if part.lower() == "data"]
    if data_indexes:
        data_relative = PROJECT_ROOT.joinpath(*parts[data_indexes[-1] :])
        if data_relative.exists():
            return data_relative.resolve()

    raise FileNotFoundError(f"PDF input does not exist: {raw_path}")


def discover_pdfs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {input_path}")
        return [input_path]
    if input_path.is_dir():
        return sorted(
            (
                path
                for path in input_path.iterdir()
                if path.is_file() and path.suffix.lower() == ".pdf"
            ),
            key=lambda path: path.name.lower(),
        )
    raise FileNotFoundError(f"PDF input does not exist: {input_path}")


def _bbox(values: Iterable[float]) -> list[float]:
    return [round(float(value), 4) for value in values]


def extract_words(page: pymupdf.Page) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for word in page.get_text("words", sort=True):
        x0, y0, x1, y1, text, block_number, line_number, word_number = word[:8]
        words.append(
            {
                "text": str(text),
                "bbox": _bbox((x0, y0, x1, y1)),
                "block_number": int(block_number),
                "line_number": int(line_number),
                "word_number": int(word_number),
            }
        )
    return words


def extract_text_blocks(page: pymupdf.Page) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for block in page.get_text("blocks", sort=True):
        x0, y0, x1, y1, text, block_number, block_type = block[:7]
        if int(block_type) != 0:
            continue
        blocks.append(
            {
                "text": str(text),
                "bbox": _bbox((x0, y0, x1, y1)),
                "block_number": int(block_number),
                "block_type": "text",
            }
        )
    return blocks


def _page_envelope(
    *,
    source_pdf: Path,
    page_number: int,
    page_count: int,
    page: pymupdf.Page,
) -> dict[str, Any]:
    return {
        "source_pdf": source_pdf.name,
        "page_number": page_number,
        "page_count": page_count,
        "width": round(float(page.rect.width), 4),
        "height": round(float(page.rect.height), 4),
        "rotation": int(page.rotation),
        "coordinate_system": "PDF points; origin at top-left; bbox order is [x0, y0, x1, y1]",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def inspect_pdf(
    pdf_path: str | Path,
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    dpi: int = 144,
) -> Path:
    """Write raw page diagnostics for one PDF and return its output directory."""
    source = resolve_input_path(pdf_path)
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError(f"Input file is not a PDF: {source}")
    if dpi < 1:
        raise ValueError("dpi must be at least 1")

    destination = Path(output_root).expanduser().resolve() / source.stem
    destination.mkdir(parents=True, exist_ok=True)

    with pymupdf.open(source) as document:
        page_count = document.page_count
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            prefix = destination / f"page_{page_number}"
            envelope = _page_envelope(
                source_pdf=source,
                page_number=page_number,
                page_count=page_count,
                page=page,
            )

            complete_text = page.get_text("text", sort=True)
            (prefix.parent / f"{prefix.name}_text.txt").write_text(
                complete_text,
                encoding="utf-8",
            )

            words = extract_words(page)
            _write_json(
                prefix.parent / f"{prefix.name}_words.json",
                {**envelope, "word_count": len(words), "words": words},
            )

            blocks = extract_text_blocks(page)
            _write_json(
                prefix.parent / f"{prefix.name}_blocks.json",
                {**envelope, "block_count": len(blocks), "blocks": blocks},
            )

            scale = dpi / 72.0
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(scale, scale),
                colorspace=pymupdf.csRGB,
                alpha=False,
            )
            pixmap.save(prefix.parent / f"{prefix.name}.png")

    return destination


def inspect_input(
    input_path: str | Path = DEFAULT_INPUT,
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    dpi: int = 144,
) -> list[Path]:
    """Inspect one PDF or every PDF immediately inside a directory."""
    resolved_input = resolve_input_path(input_path)
    pdfs = discover_pdfs(resolved_input)
    if not pdfs:
        raise ValueError(f"No PDF files found in: {resolved_input}")
    return [inspect_pdf(pdf, output_root=output_root, dpi=dpi) for pdf in pdfs]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        default=str(DEFAULT_INPUT),
        help="A PDF file or a directory of PDFs (default: data/input)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Destination root (default: data/output/debug)",
    )
    parser.add_argument(
        "--dpi",
        type=_positive_integer,
        default=144,
        help="PNG render resolution (default: 144)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destinations = inspect_input(args.input, output_root=args.output_root, dpi=args.dpi)
    for destination in destinations:
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
