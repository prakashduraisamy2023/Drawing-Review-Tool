from pathlib import Path

import pymupdf

from backend.app.models.drawing import (
    DrawingDocument,
    ExtractedField,
    ExtractionMethod,
    SupplierRasterRegion,
)
from backend.app.vision.detectors.balloon import BalloonDetector
from backend.app.vision.detectors.base import DetectorContext
from backend.app.vision.detectors.datum import DatumDetector
from backend.app.vision.detectors.gdt_frame import GDTFrameDetector
from backend.app.vision.detectors.revision_triangle import RevisionTriangleDetector
from backend.app.vision.detectors.supplier_raster_ocr import SupplierRasterOCRDetector
from backend.app.vision.ocr import DisabledOCRProvider, OCRProvider, OCRResult, OCRWord
from backend.app.vision.page_renderer import PageRenderer


def _document(path: Path) -> DrawingDocument:
    return DrawingDocument(
        source_filename=ExtractedField(
            value=path.name,
            confidence=1,
            extraction_method=ExtractionMethod.FILE_METADATA,
        ),
        page_count=ExtractedField(
            value=1,
            confidence=1,
            extraction_method=ExtractionMethod.PDF_METADATA,
        ),
    )


def _visual_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "visual-shapes.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=300)
    shape = page.new_shape()
    shape.draw_polyline(
        [pymupdf.Point(35, 55), pymupdf.Point(45, 35), pymupdf.Point(55, 55), pymupdf.Point(35, 55)]
    )
    shape.finish(width=1)
    shape.draw_polyline(
        [
            pymupdf.Point(65, 55),
            pymupdf.Point(75, 35),
            pymupdf.Point(85, 55),
            pymupdf.Point(65, 55),
        ]
    )
    shape.finish(width=1)
    shape.draw_circle(pymupdf.Point(100, 55), 14)
    shape.finish(width=1)
    shape.draw_circle(pymupdf.Point(150, 55), 14)  # ordinary hole: intentionally no number
    shape.finish(width=1)
    shape.draw_rect(pymupdf.Rect(35, 100, 105, 116))
    shape.draw_line(pymupdf.Point(55, 100), pymupdf.Point(55, 116))
    shape.draw_line(pymupdf.Point(80, 100), pymupdf.Point(80, 116))
    shape.finish(width=1)
    shape.draw_rect(pymupdf.Rect(205, 45, 221, 61))
    shape.draw_line(pymupdf.Point(221, 53), pymupdf.Point(240, 53))
    shape.finish(width=1)
    shape.commit()
    page.insert_text((42, 51), "A", fontsize=8)
    page.insert_text((72, 51), "B", fontsize=8)
    page.insert_text((94, 59), "14", fontsize=8)
    page.insert_text((39, 112), "P", fontsize=7)
    page.insert_text((60, 112), "0.1", fontsize=7)
    page.insert_text((86, 112), "A", fontsize=7)
    page.insert_text((210, 57), "C", fontsize=8)
    document.save(path)
    document.close()
    return path


def test_triangle_balloon_and_gdt_detectors_on_synthetic_geometry(tmp_path: Path):
    path = _visual_pdf(tmp_path)
    with PageRenderer(path, dpi=240) as renderer:
        context = DetectorContext(_document(path), renderer, DisabledOCRProvider())
        triangles = RevisionTriangleDetector().detect(context).objects
        balloons = BalloonDetector().detect(context).objects
        datums = DatumDetector().detect(context).objects
        frames = GDTFrameDetector().detect(context).objects

    assert {item.raw_text for item in triangles} >= {"A", "B"}
    assert any(item.attributes["item_number"] == "14" for item in balloons)
    assert len(balloons) == 1
    assert any(item.attributes["identifier"] == "C" for item in datums)
    assert any("0.1" in item.attributes["recognized_tokens"] for item in frames)


def test_triangle_detector_rejects_blank_and_large_geometry(tmp_path: Path):
    path = tmp_path / "false-triangles.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=300)
    shape = page.new_shape()
    shape.draw_polyline(
        [
            pymupdf.Point(20, 250),
            pymupdf.Point(150, 20),
            pymupdf.Point(280, 250),
            pymupdf.Point(20, 250),
        ]
    )
    shape.finish(width=1)
    shape.commit()
    document.save(path)
    document.close()
    with PageRenderer(path, dpi=200) as renderer:
        result = RevisionTriangleDetector().detect(
            DetectorContext(_document(path), renderer, DisabledOCRProvider())
        )
    assert result.objects == []


def test_balloon_detector_handles_split_circle_with_touching_leader(tmp_path: Path):
    path = tmp_path / "split-balloon.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=300)
    shape = page.new_shape()
    shape.draw_circle(pymupdf.Point(90, 90), 17)
    shape.draw_line(pymupdf.Point(73, 90), pymupdf.Point(107, 90))
    shape.draw_line(pymupdf.Point(107, 90), pymupdf.Point(150, 125))
    # Stacked table cells have similar text geometry but no circular boundary.
    shape.draw_rect(pymupdf.Rect(190, 45, 230, 115))
    shape.draw_line(pymupdf.Point(190, 80), pymupdf.Point(230, 80))
    shape.finish(width=1)
    shape.commit()
    page.insert_text((87, 89), "5", fontsize=12)
    page.insert_text((87, 99), "2", fontsize=12)
    page.insert_text((205, 76), "3", fontsize=12)
    page.insert_text((205, 111), "1", fontsize=12)
    document.save(path)
    document.close()

    with PageRenderer(path, dpi=240) as renderer:
        balloons = BalloonDetector().detect(
            DetectorContext(_document(path), renderer, DisabledOCRProvider())
        ).objects

    assert len(balloons) == 1
    assert balloons[0].attributes["item_number"] == "5"
    assert balloons[0].attributes["upper_compartment_text"] == "5"
    assert balloons[0].attributes["lower_compartment_text"] == "2"
    assert balloons[0].attributes["shape"] == "split_circle"


class FakeOCRProvider(OCRProvider):
    name = "fake-local"

    @property
    def available(self) -> bool:
        return True

    def recognize(self, _image):
        return OCRResult(
            words=(OCRWord("SUPPLIER", 0.82, (10, 10, 80, 30)),),
            raw_text="SUPPLIER",
            execution_time_ms=3.5,
        )


def test_supplier_ocr_is_limited_to_level1_raster_bbox(tmp_path: Path):
    path = tmp_path / "supplier-raster.pdf"
    pdf = pymupdf.open()
    pdf.new_page(width=300, height=300)
    pdf.save(path)
    pdf.close()
    drawing = _document(path)
    drawing.supplier_raster_regions = [
        SupplierRasterRegion(
            page_number=1,
            bounding_box=(30, 40, 250, 240),
            normalized_bounding_box=(0.1, 0.1333, 0.8333, 0.8),
            confidence=0.95,
        )
    ]
    with PageRenderer(path, dpi=200) as renderer:
        result = SupplierRasterOCRDetector().detect(
            DetectorContext(drawing, renderer, FakeOCRProvider())
        )

    assert len(result.objects) == 1
    assert result.objects[0].extraction_method == "TARGETED_OCR"
    assert result.objects[0].source_image_region.bounding_box == (30, 40, 250, 240)
    assert result.ocr_time_ms == 3.5
