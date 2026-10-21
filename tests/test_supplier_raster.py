from pathlib import Path

from backend.app.extraction.supplier_raster import SupplierRasterRegionExtractor

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "input"


def test_detects_only_explicit_supplier_original_raster_regions():
    extractor = SupplierRasterRegionExtractor()

    standard = extractor.extract(SAMPLES / "47789413_C_watermarked.pdf")
    manufacturer = extractor.extract(SAMPLES / "47789460_B_watermarked.pdf")
    supplier = extractor.extract(SAMPLES / "47789660_A_watermarked.pdf")

    assert standard == []
    assert len(manufacturer) == 1
    assert len(supplier) == 1
    for region in [*manufacturer, *supplier]:
        assert region.extraction_method == "image_region"
        assert region.confidence >= 0.9
        assert region.bounding_box[2] > region.bounding_box[0]
        assert region.normalized_bounding_box[2] <= 1.0
