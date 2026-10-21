# Level-1 test report

Date: 2026-08-17

## Automated checks

| Check | Result |
|---|---|
| Backend pytest suite | 92 passed, 0 failed |
| Ruff (`backend tests scripts`) | Passed |
| Frontend ESLint | Passed |
| TypeScript + Vite production build | Passed |
| Accuracy evaluator | Passed; JSON and CSV written |
| Production-path API test for all three samples | Passed |
| Interactive browser upload and analysis | Passed |
| Clean Uvicorn startup and `/health` | Passed (`status: ok`, OCR disabled/unavailable) |

The Python suite produced one upstream `StarletteDeprecationWarning` concerning the installed httpx/TestClient compatibility layer. The Vite build produced a non-fatal warning for JavaScript/PDF.js chunks larger than 500 kB.

## Test coverage by capability

- Pydantic evidence consistency, null behavior, canonical serialization, and nested records
- diagnostic PDF output
- page-context dimensions, native text, known templates, unknown layout, and blank page
- per-page and multi-sheet title blocks
- revision rows and supported release descriptions
- numbered multiline notes and standard patterns
- BOM, part-list, and service-parts row separation
- supplier classification, names, part numbers, manufacturer mappings, and filename independence
- supplier raster-region detection without OCR
- deterministic confidence calculations and thresholds
- extractor failure isolation and invalid-PDF behavior
- API upload validation, size limit, MIME, extension, signature, readability, sanitization, storage, focused resources, JSON export, CSV export, and 404 behavior
- manual-ground-truth accuracy/coverage calculations and error taxonomy
- all three samples through upload, persistence, retrieval, and export

## Interactive end-to-end verification

The FastAPI application and Vite development server started cleanly. Using the production upload route with `47789660_A_watermarked.pdf` verified:

1. file selection and upload;
2. HTTP 201 extraction result;
3. PDF.js page rendering;
4. Overview, Revision, Notes, BOM / Parts, Supplier, Standards, Extraction Quality, and Raw JSON tabs;
5. separate one-row Part List and eight-row Service Parts sections;
6. supplier name, supplier part number, imported-CAD statement, and raster notice;
7. click-through from drawing number to page 1 and a visible bounding-box highlight;
8. evidence details including HIGH, 98%, coordinate text, anchor, and raw text;
9. **Show Extracted Regions**, which displayed 52 deduplicated page overlays plus one selected overlay;
10. no browser console warnings or errors.

JSON/CSV exports are additionally asserted by API tests. The browser itself was used for the interactive visualization checks; all three samples were exercised through the production API pathway by the integration test.

## Manual-ground-truth evaluation

The current truth set contains 37 independently entered expectations.

| Drawing | Expected | Correct | Incorrect | Missing | False | Accuracy | Coverage | Time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 47789413_C_watermarked.pdf | 15 | 15 | 0 | 0 | 0 | 100% | 100% | 7.594 s |
| 47789460_B_watermarked.pdf | 10 | 10 | 0 | 0 | 0 | 100% | 100% | 0.948 s |
| 47789660_A_watermarked.pdf | 12 | 12 | 0 | 0 | 0 | 100% | 100% | 0.465 s |
| **Overall** | **37** | **37** | **0** | **0** | **0** | **100%** | **100%** | — |

| Category | Expected | Accuracy | Coverage |
|---|---:|---:|---:|
| Title Block | 34 | 100% | 100% |
| Supplier Information | 3 | 100% | 100% |
| Revision | 0 | Not evaluated | Not evaluated |
| Notes | 0 | Not evaluated | Not evaluated |
| BOM | 0 | Not evaluated | Not evaluated |
| Part Lists | 0 | Not evaluated | Not evaluated |
| Service Parts | 0 | Not evaluated | Not evaluated |
| Standards | 0 | Not evaluated | Not evaluated |

The 100% result applies only to the 37 entered expectations. It must not be interpreted as independent accuracy evidence for empty categories. Extractor tests do verify the current sample counts and wording for those categories, but tests using parser outputs are not substitutes for manual truth.

## Sample extraction counts

| Drawing | Revisions | Notes | BOM | Part list | Service parts | Standards | Raster regions |
|---|---:|---:|---:|---:|---:|---:|---:|
| 47789413_C_watermarked.pdf | 5 | 15 | 6 | 2 | 0 | 4 | 0 |
| 47789460_B_watermarked.pdf | 1 | 14 | 0 | 3 | 0 | 7 | 1 |
| 47789660_A_watermarked.pdf | 1 | 6 | 0 | 1 | 8 | 2 | 1 |

## Warnings and performance

The standard five-page drawing completed without warnings. Each supplier drawing produced one informational `SUPPLIER_RASTER_CONTENT_NOT_EXTRACTED` notice; this is expected Level-1 behavior and does not mark processing as failed.

The five-page drawing is the slowest at approximately 7.6 seconds. The identifiable bottleneck is repeated PDF opening and repeated notes/classification passes retained to avoid unnecessarily rewriting stable extractors. Page context itself is single-pass. This is suitable for the current PoC; shared-context optimization is a future performance task.
