# Level-3 detector catalog

No trainable AI model is introduced. All implemented detection is native-text association, traditional OpenCV geometry/layout analysis, or optional targeted offline OCR.

| Detector | Object types | Method | Status | Ground truth / metrics |
|---|---|---|---|---|
| `revision_triangle` | REVISION_TRIANGLE | Canny edges, triangular contour/scale filters, title-block exclusion, nearby native identifier | Implemented; confidence-gated | Synthetic geometry tests pass. Supplied samples are ungrounded; precision/recall/F1 are not reported. |
| `balloon` | BOM_BALLOON | Closed circle/polygon contours plus native item text; split-circle detection uses vertically stacked numeric text and circumference evidence that remains valid when a leader touches the boundary | Implemented; confidence-gated | Synthetic single/split balloon, touching-leader, table-cell, and hole rejection tests pass. Supplied samples are ungrounded. |
| `scc_symbol` | SCC_SYMBOL | Controlled template boundary only | Framework present; detection intentionally inactive | No client checklist symbol or manually verified example was supplied. No metric. |
| `datum` | DATUM_SYMBOL | Small rectangular symbol geometry, attached-line evidence, internal native identifier | Implemented; confidence-gated | Synthetic datum test passes. Supplied samples are ungrounded. |
| `gdt_frame` | GDT_FRAME | Rectangular segmented-frame morphology, table/border exclusion, native tokens, optional targeted OCR | Implemented; syntax only | Synthetic segmented-frame/token test passes. Supplied samples are ungrounded. |
| `view_annotation` | VIEW_ARROW, SECTION_ARROW, DETAIL_CALLOUT | Native-first VIEW/SECTION/DETAIL label detection and adjacent identifier association | Implemented; geometry linkage limited | Supplied samples are ungrounded. |
| `flag_note` | FLAG_NOTE | Triangle contour plus mandatory numeric token | Implemented; confidence-gated | Synthetic triangle behavior is covered; no independent sample metric. |
| `supplier_raster_ocr` | SUPPLIER_RASTER_TEXT | Level-1 raster bbox -> 400-DPI crop -> contrast/deskew/upscale -> offline OCR -> PDF word boxes | Implemented; runtime provider unavailable in current environment | Fake-local provider integration test passes. Tesseract executable is not installed, so sample OCR output is zero and no OCR accuracy is reported. |

## Rejection controls

- Ordinary holes are rejected unless a larger enclosing boundary contains an item token.
- Dimension multipliers such as `2X` are not accepted as balloon item identifiers.
- Split balloons require both aligned numeric compartments and strong circular-boundary coverage; stacked BOM table cells and revision triangles are rejected.
- Large component triangles, page-border triangles, and lower-right wrapper graphics are excluded from revision candidates.
- GD&T candidates require a segmented rectangle and recognized tokens; BOM regions and page-border zone grids are excluded.
- Datum candidates require a compact boxed identifier and a nearby attached line.
- SCC shape is not guessed.

Low-confidence candidates remain visible for review. Detection counts are observations, not proof that every candidate is correct or that every visual object was found.
