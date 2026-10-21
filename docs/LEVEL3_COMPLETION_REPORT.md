# Engineering Drawing Intelligence
## Level 3 Completion Report

### 1 Executive Summary

Level 3 adds a separate local visual-evidence layer, API, PDF overlays, review workflow, evaluation framework, and confidence-gated Level-2 cross-references without changing Level-1 extraction semantics or engineering-review boundaries. Traditional computer vision is implemented for several annotation families; no trained AI model or cloud service is used.

Acceptance status: **PASS WITH LIMITATIONS**. The architecture and workflow are complete, but supplied drawings have no independently reviewed visual ground truth, the current host has no Tesseract executable, and SCC detection correctly remains inactive without a controlled symbol reference. Detector precision/recall/F1 must not be claimed until ground truth is entered.

### 2 Level-3 Objective

The implementation turns observable page geometry, native tokens, targeted raster OCR, and spatial relationships into provenance-bearing `VisualObject` evidence. It does not determine full drawing correctness, functional GD&T correctness, manufacturing readiness, complete dimensioning, standards compliance, or engineering approval.

### 3 Architecture

The data flow is:

```text
PDF + Level-1 DrawingDocument
 -> shared cached PageRenderer
 -> detector registry
 -> DetectorResult[] / VisualObject[] / VisionSummary
 -> persisted VisionReport
 -> Visual Intelligence API and PDF overlays
 -> optional confidence-gated Level-2 cross-reference
```

Pages render once at 200 DPI for general detection. Small targeted crops can render at 400–450 DPI. Pixel boxes are converted back to original PDF coordinates. Each detector is fault-isolated. Reviewer actions are stored separately from detector output.

### 4 Visual Detectors

| Detector | Object Type | Method | Status | Ground Truth | Precision | Recall | F1 |
|---|---|---|---|---|---:|---:|---:|
| Revision triangle | REVISION_TRIANGLE | Edges + triangular contours + scale/context + nearby native token | Implemented, confidence-gated | None for supplied PDFs | — | — | — |
| Balloon | BOM_BALLOON | Enclosing circle/ellipse/polygon + mandatory internal item token | Implemented, confidence-gated | None for supplied PDFs | — | — | — |
| SCC | SCC_SYMBOL | Controlled-template boundary | Framework only; intentionally inactive | None | — | — | — |
| Datum | DATUM_SYMBOL | Compact box + internal identifier + attached line | Implemented, syntax only | None for supplied PDFs | — | — | — |
| GD&T frame | GDT_FRAME | Segmented rectangle + region rejection + native/targeted OCR tokens | Implemented, token set limited | None for supplied PDFs | — | — | — |
| View annotation | VIEW/SECTION/DETAIL | Native-first labels + adjacent identifier | Implemented, linkage limited | None for supplied PDFs | — | — | — |
| Flag note | FLAG_NOTE | Triangle + numeric token | Implemented, confidence-gated | None for supplied PDFs | — | — | — |
| Supplier raster OCR | SUPPLIER_RASTER_TEXT | Level-1 raster bbox + local high-DPI OCR | Implemented; provider unavailable on host | None | — | — | — |

Synthetic tests demonstrate expected behavior for controlled shapes and reject a large geometric triangle and an ordinary unnumbered hole. Synthetic behavior is not a substitute for client-sample detector metrics.

### 5 Level-2 Rules Upgraded

| Rule ID | Previous Status | Level-3 Evidence | New Automation Status |
|---|---|---|---|
| REV-012 | NOT_IMPLEMENTED | Revision triangle object/identifier | PARTIALLY_AUTOMATED |
| NOTE-012 | NOT_IMPLEMENTED | Flag-note number | PARTIALLY_AUTOMATED |
| BOM-011 | NOT_IMPLEMENTED | Balloon item number | PARTIALLY_AUTOMATED |
| BOM-012 | NOT_IMPLEMENTED | Balloon inventory | PARTIALLY_AUTOMATED; occurrence semantics manual |
| BOM-014 | NOT_IMPLEMENTED | SCC object/context | PARTIALLY_AUTOMATED framework; no template |
| SUP-010 | NOT_IMPLEMENTED | Targeted supplier raster OCR | PARTIALLY_AUTOMATED evidence; content review manual |
| XREF-006 | NOT_IMPLEMENTED | SCC object/context | PARTIALLY_AUTOMATED framework; no template |
| XREF-007 | NOT_IMPLEMENTED | Balloon item number | PARTIALLY_AUTOMATED |
| VIEW-001–005 | NOT_IMPLEMENTED | View/section/detail labels | PARTIALLY_AUTOMATED syntax; local scale unresolved |
| GDT-001–003 | NOT_IMPLEMENTED | Datum identifiers | PARTIALLY_AUTOMATED syntax |
| GDT-004–005 | NOT_IMPLEMENTED | GD&T frame tokens | PARTIALLY_AUTOMATED syntax |

Low-confidence evidence returns MANUAL_REVIEW or NOT_EVALUATED and cannot create automatic FAIL. Detector absence also does not prove object absence.

### 6 Sample Drawing Results

| Drawing | Visual Objects | Low Confidence | OCR Regions | Level-3 Time (ms) |
|---|---:|---:|---:|---:|
| `47789413_C_watermarked.pdf` | 49 | 21 | 0 | 4715.012 |
| `47789460_B_watermarked.pdf` | 51 | 49 | 0 | 3639.115 |
| `47789660_A_watermarked.pdf` | 4 | 4 | 0 | 1284.596 |

Per-type counts are stored in `data/output/evaluation/level3_results.json`. These are detector observations, not verified object counts. Debug overlays are under `data/output/vision_debug`.

### 7 Validation Impact

| Drawing | Stage | PASS | FAIL | WARNING | MANUAL | NOT EVALUATED | N/A |
|---|---|---:|---:|---:|---:|---:|---:|
| 47789413 | Before | 38 | 0 | 0 | 10 | 36 | 24 |
| 47789413 | After | 43 | 0 | 3 | 11 | 27 | 24 |
| 47789460 | Before | 34 | 0 | 1 | 9 | 31 | 33 |
| 47789460 | After | 38 | 0 | 1 | 11 | 25 | 33 |
| 47789660 | Before | 38 | 0 | 0 | 9 | 31 | 30 |
| 47789660 | After | 38 | 0 | 0 | 13 | 27 | 30 |

The first sample made NOTE-012, VIEW-001/003/004, and GDT-001 evaluable as PASS, with warnings for duplicate view/datum syntax. The second made datum syntax and GDT frame-token checks evaluable. The third exposed only lower-confidence visual candidates, so affected rules moved to manual review rather than automated results. All remain review-assistance outcomes because real-sample detector accuracy is ungrounded.

### 8 Test Results

| Check | Result |
|---|---|
| Level-1 regression | PASS: 37/37 evaluator expectations |
| Level-2 regression | PASS: 28/28 evaluator expectations |
| Backend suite | PASS: 113 tests |
| Level-3-specific tests | PASS: 8 tests within the full suite |
| Ruff | PASS |
| Frontend lint | PASS |
| Frontend build | PASS; non-fatal Vite chunk-size advisory |
| Level-3 evaluator | PASS; all 3 PDFs processed |
| Live API workflow | PASS: upload -> Level 3 -> Level 2 -> objects -> export |
| Interactive browser workflow | Unverified: browser-control trusted-path startup error |

### 9 Known Limitations

- No manually reviewed visual ground truth exists for supplied samples; all detector metrics are blank.
- Tesseract wrapper is installed, but the Tesseract executable is unavailable. OCR is disabled by default and sample OCR count is zero.
- SCC symbol shape was not supplied and is not guessed.
- Revision, view, and datum-like geometry can generate low-confidence candidates; reviewer confirmation is required.
- Leader-line feature endpoint association, hatching, hidden-line dimension relationships, local view scales, and complete view semantics remain incomplete.
- GD&T parsing is limited and syntactic. Functional correctness and full ASME Y14.5 compliance remain manual.
- No trained object detector was introduced.

### 10 Acceptance Status

**PASS WITH LIMITATIONS**

- [x] Separate vision engine, schema, rendering cache, coordinate mapping, preprocessing, confidence gates, API, persistence, exports, UI, overlays, and review audit layer exist.
- [x] Traditional-CV revision, balloon, datum, GD&T, view annotation, and flag-note implementations exist with synthetic tests.
- [x] SCC framework exists and does not guess an unknown client symbol.
- [x] Targeted supplier-raster OCR and offline provider abstraction exist and degrade safely.
- [x] Visual evidence is available to Level-2 rules without embedding CV inside validation logic.
- [x] Dataset export and independent ground-truth/evaluation frameworks exist.
- [x] Backend, frontend, evaluators, and live HTTP workflow pass.
- [ ] Real-sample detector precision/recall/F1 cannot be accepted until manually reviewed annotations exist.
- [ ] Live supplier OCR cannot be demonstrated on this host until a local Tesseract executable is installed and configured.
- [ ] Browser click/highlight interaction requires manual verification because the in-app browser controller could not attach in this environment.

### 11 Recommended Level 4

Do not implement Level 4 yet. First create independently reviewed sample annotations, calibrate class thresholds, define the SCC symbol from controlled client material, validate Tesseract on supplier crops, and decide whether remaining false positives justify a small local trainable detector. Any future model must remain modular, versioned, measured, and outside engineering-approval decisions.

## Run commands

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend
pnpm run dev
```

## Evaluation commands

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_level1.py
.\.venv\Scripts\python.exe scripts\evaluate_level2.py
.\.venv\Scripts\python.exe scripts\evaluate_level3.py
```
