"""Export local rendered pages and empty labeling files for Level-3 annotation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from backend.app.vision.models import VisualObjectType  # noqa: E402
from backend.app.vision.page_renderer import PageRenderer  # noqa: E402


def export_dataset(input_dir: Path, output_dir: Path, *, dpi: int) -> dict[str, int]:
    images = output_dir / "images"
    labels = output_dir / "labels"
    images.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    pages = 0
    for pdf in sorted(input_dir.glob("*.pdf")):
        with PageRenderer(pdf, dpi=dpi) as renderer:
            for page_number in range(1, renderer.page_count + 1):
                rendered = renderer.render_page(page_number)
                stem = f"{pdf.stem}_page_{page_number}"
                cv2.imwrite(str(images / f"{stem}.png"), rendered.image)
                annotation = labels / f"{stem}.json"
                if not annotation.exists():
                    annotation.write_text(
                        json.dumps(
                            {
                                "source_filename": pdf.name,
                                "page_number": page_number,
                                "pdf_width": rendered.pdf_width,
                                "pdf_height": rendered.pdf_height,
                                "review_status": "UNREVIEWED",
                                "objects": [],
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                pages += 1
    classes = [str(value) for value in VisualObjectType if value != VisualObjectType.UNKNOWN]
    (output_dir / "classes.yaml").write_text(
        json.dumps({"classes": classes}, indent=2) + "\n", encoding="utf-8"
    )
    return {"pdfs": len(list(input_dir.glob("*.pdf"))), "pages": pages}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "input")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "vision_dataset")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(export_dataset(args.input, args.output, dpi=args.dpi), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
