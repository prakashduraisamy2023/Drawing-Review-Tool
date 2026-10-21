"""Run evidence extraction and visual detection across the review corpus.

This script does not create ground truth and does not train a statistical model.
It produces a reproducible baseline that reviewers can use to find systematic
extraction and visual-detection errors without treating predictions as labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.extraction import DrawingParser  # noqa: E402
from backend.app.vision import VisionEngine  # noqa: E402
from backend.app.vision.models import VisionReport  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit extraction and visual detections across a PDF corpus."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        type=Path,
        default=ROOT / "data" / "training" / "pdfs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "output" / "training_audit",
    )
    parser.add_argument(
        "--debug-overlays",
        action="store_true",
        help="Write page overlays for human review.",
    )
    parser.add_argument(
        "--reuse-vision",
        action="store_true",
        help="Reuse an existing vision JSON when only Level-1 extraction changed.",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pdf_metadata(path: Path) -> tuple[int, list[dict[str, Any]]]:
    pages: list[dict[str, Any]] = []
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            pages.append(
                {
                    "page_number": page_number,
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                    "native_word_count": len(page.get_text("words")),
                }
            )
        return document.page_count, pages


def _field_value(field: object) -> object:
    return getattr(field, "value", None)


def audit(
    input_dir: Path,
    output_dir: Path,
    *,
    debug_overlays: bool = False,
    reuse_vision: bool = False,
) -> dict[str, Any]:
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {input_dir}")

    extraction_dir = output_dir / "extraction"
    vision_dir = output_dir / "vision"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    vision_dir.mkdir(parents=True, exist_ok=True)

    previous_hashes: dict[str, str] = {}
    previous_manifest = output_dir / "corpus_audit.json"
    if reuse_vision and previous_manifest.is_file():
        previous_payload = json.loads(previous_manifest.read_text(encoding="utf-8"))
        previous_hashes = {
            str(item["source_filename"]): str(item["sha256"])
            for item in previous_payload.get("samples", [])
            if item.get("source_filename") and item.get("sha256")
        }

    parser = DrawingParser()
    vision_engine = VisionEngine()
    samples: list[dict[str, Any]] = []

    for pdf in pdfs:
        started = time.perf_counter()
        page_count, pages = _pdf_metadata(pdf)
        sample: dict[str, Any] = {
            "source_filename": pdf.name,
            "sha256": _sha256(pdf),
            "size_bytes": pdf.stat().st_size,
            "page_count": page_count,
            "pages": pages,
            "status": "FAILED",
            "error": None,
        }
        try:
            drawing = parser.parse(pdf)
            extraction_path = extraction_dir / f"{pdf.stem}.json"
            extraction_path.write_text(drawing.model_dump_json(indent=2), encoding="utf-8")

            vision_path = vision_dir / f"{pdf.stem}.json"
            if (
                reuse_vision
                and vision_path.is_file()
                and previous_hashes.get(pdf.name) == sample["sha256"]
            ):
                report = VisionReport.model_validate_json(
                    vision_path.read_text(encoding="utf-8")
                )
            else:
                overlay_dir = output_dir / "overlays" / pdf.stem if debug_overlays else None
                report = vision_engine.analyze(pdf, drawing, debug_directory=overlay_dir)
                vision_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

            balloon_numbers = sorted(
                {
                    str(item.attributes.get("item_number"))
                    for item in report.objects
                    if str(item.object_type) == "BOM_BALLOON"
                    and item.attributes.get("item_number") is not None
                }
            )
            balloon_objects = [
                item for item in report.objects if str(item.object_type) == "BOM_BALLOON"
            ]
            sample.update(
                {
                    "status": "SUCCESS",
                    "drawing_number": _field_value(drawing.drawing_number),
                    "revision": _field_value(drawing.revision),
                    "part_name": _field_value(drawing.part_name),
                    "bom_item_count": len(drawing.bom_items),
                    "note_count": len(drawing.notes),
                    "extraction_warning_count": len(drawing.extraction_warnings),
                    "visual_object_count": report.summary.objects_detected,
                    "objects_by_type": report.summary.objects_by_type,
                    "balloon_object_count": len(balloon_objects),
                    "balloon_numbers": balloon_numbers,
                    "split_balloon_count": sum(
                        item.attributes.get("shape") == "split_circle"
                        for item in balloon_objects
                    ),
                    "low_confidence_visual_count": report.summary.low_confidence_count,
                }
            )
        except Exception as exc:  # keep the corpus audit fault-isolated
            sample["error"] = f"{type(exc).__name__}: {exc}"
        sample["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        samples.append(sample)
        print(
            f"{sample['status']:7} {pdf.name}: "
            f"pages={page_count}, balloons={sample.get('balloon_object_count', 0)}, "
            f"elapsed_ms={sample['elapsed_ms']}"
        )

    payload = {
        "corpus_policy": (
            "Predictions are audit evidence only. They are not manually reviewed labels "
            "and must not be used as ground truth."
        ),
        "input_directory": str(input_dir.resolve()),
        "pdf_count": len(pdfs),
        "successful_count": sum(item["status"] == "SUCCESS" for item in samples),
        "failed_count": sum(item["status"] == "FAILED" for item in samples),
        "samples": samples,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "corpus_audit.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )

    csv_fields = [
        "source_filename",
        "sha256",
        "size_bytes",
        "page_count",
        "status",
        "drawing_number",
        "revision",
        "part_name",
        "bom_item_count",
        "note_count",
        "extraction_warning_count",
        "visual_object_count",
        "balloon_object_count",
        "balloon_numbers",
        "split_balloon_count",
        "low_confidence_visual_count",
        "elapsed_ms",
        "error",
    ]
    with (output_dir / "corpus_audit.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_fields)
        writer.writeheader()
        for sample in samples:
            row = {key: sample.get(key) for key in csv_fields}
            row["balloon_numbers"] = ",".join(sample.get("balloon_numbers", []))
            writer.writerow(row)
    return payload


def main() -> int:
    args = parse_args()
    payload = audit(
        args.input_dir,
        args.output_dir,
        debug_overlays=args.debug_overlays,
        reuse_vision=args.reuse_vision,
    )
    print(
        f"Audited {payload['pdf_count']} PDFs: "
        f"{payload['successful_count']} succeeded, {payload['failed_count']} failed."
    )
    return 1 if payload["failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
