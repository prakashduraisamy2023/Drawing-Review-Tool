"""Traditional-CV and targeted-OCR detectors supplied with Level 3."""

from backend.app.vision.detectors.balloon import BalloonDetector
from backend.app.vision.detectors.datum import DatumDetector
from backend.app.vision.detectors.flag_note import FlagNoteDetector
from backend.app.vision.detectors.gdt_frame import GDTFrameDetector
from backend.app.vision.detectors.revision_triangle import RevisionTriangleDetector
from backend.app.vision.detectors.scc_symbol import SCCSymbolDetector
from backend.app.vision.detectors.supplier_raster_ocr import SupplierRasterOCRDetector
from backend.app.vision.detectors.view_arrow import ViewAnnotationDetector

__all__ = [
    "BalloonDetector",
    "DatumDetector",
    "FlagNoteDetector",
    "GDTFrameDetector",
    "RevisionTriangleDetector",
    "SCCSymbolDetector",
    "SupplierRasterOCRDetector",
    "ViewAnnotationDetector",
]
