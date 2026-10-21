# Level-3 baseline

## Baseline boundary

This snapshot was captured on 2026-08-18 before any Level-3 source changes. Level 1 remains the evidence-producing extraction layer and Level 2 remains the deterministic validation layer. Level 3 must consume their outputs without changing existing extraction or validation semantics.

## Level-1 status

| Check | Baseline result |
|---|---:|
| Complete backend test suite | 105 passed, 0 failed |
| Level-1 grounded expectations | 37 |
| Correct / incorrect / missing / false extraction | 37 / 0 / 0 / 0 |
| Accuracy / coverage | 1.000 / 1.000 |

The grounded Level-1 set currently covers 34 Title Block values and 3 Supplier Information values. Revision, Notes, BOM, Part Lists, Service Parts, and Standards have no independent field-level ground truth and therefore have no reported accuracy.

## Level-2 status

| Check | Baseline result |
|---|---:|
| Grounded expectations | 28 |
| Correct | 28 |
| Accuracy / precision / recall | 1.000 / 1.000 / 1.000 |
| Rule catalog size | 108 |
| Automated | 56 |
| Partially automated | 18 |
| Manual | 7 |
| Not implemented | 27 |

Sample validation results before Level 3:

| Drawing | PASS | FAIL | WARNING | MANUAL_REVIEW | NOT_EVALUATED | NOT_APPLICABLE |
|---|---:|---:|---:|---:|---:|---:|
| `47789413_C_watermarked.pdf` | 38 | 0 | 0 | 10 | 36 | 24 |
| `47789460_B_watermarked.pdf` | 34 | 0 | 1 | 9 | 31 | 33 |
| `47789660_A_watermarked.pdf` | 38 | 0 | 0 | 9 | 31 | 30 |

Observed Level-1 / Level-2 processing times were 12502.084 / 5.199 ms, 1260.776 / 3.963 ms, and 691.641 / 5.470 ms respectively. These are single-run observations, not benchmarks.

## Current rule catalog

The authoritative pre-Level-3 catalog is [level2_rule_catalog.md](level2_rule_catalog.md). It contains 108 stable rule IDs across Title Block, Revision, Notes, Standards, BOM, Part List, Service Parts, Supplier, Cross Reference, Dimensions, Views, and GD&T.

## Rules blocked by unavailable visual evidence

The following catalogued rules are `NOT_IMPLEMENTED` primarily because visual objects are absent from the Level-1 evidence model:

| Rule ID | Requirement | Missing visual evidence |
|---|---|---|
| REV-012 | Revision triangle check | Revision triangles and identifiers |
| NOTE-012 | Note callout relationship | Flag-note callouts and note numbers |
| BOM-011 | BOM balloon relationship | Balloon objects and item numbers |
| BOM-012 | BOM balloon quantity | Reliable balloon inventory and semantics |
| BOM-014 | SCC symbol beside BOM item | SCC symbol locations and BOM-row proximity |
| SUP-010 | Supplier internal data validation | Text inside supplier raster regions |
| XREF-006 | SCC title block to note or BOM | SCC symbols and spatial context |
| XREF-007 | BOM to balloon | Balloon objects and item numbers |
| DIM-007 | Hidden-line dimension | Visual line/dimension relationships |
| VIEW-008 | Hatching | Visual hatch regions |
| VIEW-009 | Arrow direction | View/section arrows and linked labels |
| GDT-001 | Datum identifier detected | Datum feature symbols and identifiers |
| GDT-002 | Datum duplicate identifier | Reliable datum inventory |
| GDT-003 | Datum sequence | Reliable datum inventory |
| GDT-004 | Feature control frame token recognized | Frame cells and recognized tokens |
| GDT-005 | Position tolerance recognized | GD&T characteristic/tolerance tokens |

The following remain `MANUAL` because they require engineering judgment, even if Level 3 later provides relevant visual evidence: DIM-005, DIM-008, DIM-009, VIEW-007, GDT-006, GDT-007, and GDT-008.

## Candidate Level-2 rules Level 3 can unlock

The first safe candidates are REV-012, NOTE-012, BOM-011, BOM-014, XREF-006, XREF-007, GDT-001 through GDT-005, VIEW-001 through VIEW-005, and supplier-raster evidence for SUP-010. BOM-012 is only eligible when balloon semantics and confidence are sufficient. Functional dimensioning, datum selection, full ASME Y14.5 compliance, view completeness, and manufacturing readiness remain human decisions.

## Current PDF types and raster regions

| Drawing | Pages | Type | Supplier raster regions |
|---|---:|---|---:|
| `47789413_C_watermarked.pdf` | 5 | STANDARD_DRAWING | 0 |
| `47789460_B_watermarked.pdf` | 1 | SUPPLIER_DRAWING | 1 |
| `47789660_A_watermarked.pdf` | 1 | SUPPLIER_DRAWING | 1 |

Supplier raster regions are currently detected as image-region evidence only. Their content is not semantically OCR-extracted at baseline.

## Available page render and debug pipeline

`backend/app/pdf/inspect_pdf.py` uses PyMuPDF to extract text, words, text blocks, and RGB page PNGs. Its default render resolution is 144 DPI, and it records original PDF page dimensions and PDF-coordinate bounding boxes. Existing debug artifacts live under `data/output/debug/<drawing>/page_<n>.*`.

The baseline has no shared in-memory rendered-page cache, detector-specific high-resolution crops, OpenCV preprocessing layer, visual object schema, visual ground truth, Level-3 evaluator, or visual-to-validation context.

## Commands used

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\evaluate_level1.py
.\.venv\Scripts\python.exe scripts\evaluate_level2.py
```

The test run emitted one non-fatal upstream Starlette/httpx deprecation warning.
