import json
from pathlib import Path

import pymupdf

from backend.app.pdf.inspect_pdf import inspect_input, inspect_pdf


def make_diagnostic_pdf(path: Path, page_count: int = 1) -> Path:
    document = pymupdf.open()
    for page_number in range(1, page_count + 1):
        page = document.new_page(width=300, height=200)
        page.insert_text((24, 36), f"Diagnostic page {page_number}")
        page.insert_text((24, 60), "Second text block")
    document.save(path)
    document.close()
    return path


def test_inspect_pdf_writes_complete_page_artifacts(tmp_path: Path):
    source = make_diagnostic_pdf(tmp_path / "sample.pdf", page_count=2)
    output_root = tmp_path / "debug"

    destination = inspect_pdf(source, output_root=output_root, dpi=72)

    assert destination == output_root / "sample"
    for page_number in (1, 2):
        prefix = destination / f"page_{page_number}"
        assert prefix.with_suffix(".png").is_file()
        assert (
            (destination / f"page_{page_number}_text.txt")
            .read_text(encoding="utf-8")
            .startswith(f"Diagnostic page {page_number}")
        )

        words = json.loads(
            (destination / f"page_{page_number}_words.json").read_text(encoding="utf-8")
        )
        assert words["width"] == 300
        assert words["height"] == 200
        assert words["page_number"] == page_number
        assert words["word_count"] == len(words["words"])
        assert all(len(word["bbox"]) == 4 for word in words["words"])
        assert all("text" in word for word in words["words"])

        blocks = json.loads(
            (destination / f"page_{page_number}_blocks.json").read_text(encoding="utf-8")
        )
        assert blocks["block_count"] == len(blocks["blocks"])
        assert all(len(block["bbox"]) == 4 for block in blocks["blocks"])
        assert all(block["block_type"] == "text" for block in blocks["blocks"])


def test_inspect_input_processes_every_pdf_in_directory(tmp_path: Path):
    input_directory = tmp_path / "input"
    input_directory.mkdir()
    make_diagnostic_pdf(input_directory / "drawing-b.PDF")
    make_diagnostic_pdf(input_directory / "drawing-a.pdf")
    (input_directory / "ignore.txt").write_text("not a PDF", encoding="utf-8")

    destinations = inspect_input(
        input_directory,
        output_root=tmp_path / "debug",
        dpi=72,
    )

    assert [path.name for path in destinations] == ["drawing-a", "drawing-b"]


def test_inspector_does_not_add_semantic_fields(tmp_path: Path):
    source = make_diagnostic_pdf(tmp_path / "sample.pdf")
    destination = inspect_pdf(source, output_root=tmp_path / "debug", dpi=72)
    words = json.loads((destination / "page_1_words.json").read_text(encoding="utf-8"))

    semantic_fields = {"drawing_number", "revision", "part_name", "bom", "notes"}
    assert semantic_fields.isdisjoint(words)
