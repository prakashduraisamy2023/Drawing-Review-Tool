# Level-3 visual architecture

## Boundary

Level 3 is an independent evidence layer. It consumes the saved PDF and canonical `DrawingDocument`, emits provenance-bearing `VisualObject` records, and optionally supplies those records to Level-2 cross-reference rules. It does not modify Level-1 extraction, place computer-vision logic inside validation rules, infer absent engineering values, or approve a drawing.

```text
PDF + DrawingDocument
        |
        v
shared PyMuPDF PageRenderer (cached 200-DPI pages, high-DPI targeted crops)
        |
        v
detector registry -> DetectorResult[] -> VisualObject[]
        |                                  |
        |                                  +-> PDF page + PDF bounding box + confidence
        v
VisionReport / vision.json
        |
        +-> Visual Intelligence API and labelled PDF overlays
        +-> confidence-gated ValidationContext visual evidence
        +-> reviewer decisions stored separately in vision_reviews.json
```

## Components

- `backend/app/vision/models.py`: object types, objects, detector results, summary, timing, report, and reviewer-action contracts.
- `page_renderer.py`: one open PyMuPDF document, cached general renders, 400–450-DPI targeted crops, native words, and bidirectional PDF/pixel coordinate mapping.
- `preprocessing.py`: grayscale, CLAHE contrast normalization, adaptive/binary thresholding, edges, morphology, components, contours, deskew, and upscale functions.
- `registry.py` and `engine.py`: controlled detector order, per-detector fault isolation, timings, summary, and optional debug overlays.
- `detectors/`: detector-specific CV and targeted-OCR strategies.
- `ocr.py`: offline provider boundary with disabled and Tesseract providers. It never performs full-page OCR.
- `confidence.py`: per-class automatic thresholds and partial/manual gates.
- `spatial.py` and `fusion.py`: deterministic spatial operations and explainable additive evidence signals.
- `providers.py`: future trainable object-detector interface; no implementation or model is bundled.

## Coordinates and caching

All public boxes use original PDF points `(x0, y0, x1, y1)`, top-left origin. A rendered page stores independent x/y scale factors and converts detector pixel boxes back to PDF coordinates before model construction. Each `(page, DPI)` general render is cached. Detectors share one `PageRenderer`; only small OCR/GD&T crops are rendered at higher DPI.

## Evidence and confidence

Every visual object contains `page_number`, `bounding_box`, `confidence`, `detector`, and `extraction_method`. Optional text, normalized text, polygons, attributes, and source crop provenance remain attached to the same object. Automatic thresholds are class-specific. Evidence below an automatic threshold can be displayed and reviewed but cannot drive an automatic FAIL.

## OCR and data locality

Supplier OCR receives only Level-1 `SupplierRasterRegion` bounding boxes. It renders those clips locally, preprocesses them, invokes the configured offline provider, maps word boxes back to PDF coordinates, and labels the result `TARGETED_OCR`. Native wrapper evidence is never overwritten. No drawing or crop is sent to an external service.

## Level-2 integration

`ValidationContext` accepts an optional `VisionReport`. Visual evaluators are syntax/cross-reference checks only. With no report they retain `NOT_EVALUATED`; with lower-confidence evidence they return `MANUAL_REVIEW`; reliable discrepancies are generally `WARNING` until detector recall has independent ground truth. Functional GD&T, datum selection, dimension completeness, view completeness, and engineering approval remain manual.

## Configuration

- `LEVEL3_ENABLED` / `DRAWING_LEVEL3_ENABLED`
- `OCR_ENABLED` / `DRAWING_OCR_ENABLED`
- `OCR_PROVIDER` / `DRAWING_OCR_PROVIDER`
- `DRAWING_VISION_DPI`
- `DRAWING_VISION_DEBUG_OVERLAYS`

The upload path does not automatically run Level 3. `POST /api/drawings/{id}/vision/analyze` performs the explicit local analysis; the frontend then refreshes validation so visual cross-references become visible.
