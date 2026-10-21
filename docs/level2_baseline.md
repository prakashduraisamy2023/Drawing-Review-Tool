# Level-2 baseline

## Baseline boundary

Level 1 is frozen as the evidence-producing layer for Level 2. Level 2 consumes the canonical `DrawingDocument`; it does not re-open the PDF, change extraction results, infer absent values, or convert extraction uncertainty into an engineering failure.

Baseline captured on 2026-08-17 from the current repository state.

## Level-1 verification

| Check | Result |
|---|---|
| Backend test suite | 92 passed, 0 failed |
| Level-1 evaluator | 37 correct of 37 entered expectations |
| Incorrect / missing / false extraction | 0 / 0 / 0 |
| Grounded Title Block values | 34 of 34 correct |
| Grounded Supplier Information values | 3 of 3 correct |
| Revision, Notes, BOM, Part Lists, Service Parts, Standards accuracy | Not evaluated; no independent field-level truth entered |
| OCR | Disabled; no full-page or supplier-raster OCR |

Command evidence:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\evaluate_level1.py
```

The test suite emits one non-fatal upstream Starlette/httpx deprecation warning.

## Current sample extraction coverage

| Drawing | Pages | Classification | Revisions | Notes | BOM | Part list | Service parts | Standards | Supplier raster regions |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `47789413_C_watermarked.pdf` | 5 | STANDARD_DRAWING | 5 | 15 | 6 | 2 | 0 | 4 | 0 |
| `47789460_B_watermarked.pdf` | 1 | SUPPLIER_DRAWING | 1 | 14 | 0 | 3 | 0 | 7 | 1 |
| `47789660_A_watermarked.pdf` | 1 | SUPPLIER_DRAWING | 1 | 6 | 0 | 1 | 8 | 2 | 1 |

These counts are regression observations, not independent proof that every extracted record is engineering-correct.

## Evidence available to Level 2

The canonical document supplies provenance-bearing values for:

- document identity, page count, document type, drawing number, revision, size, part name and part numbers;
- units, scale, weight, sheet number, total sheets, critical-component evidence, dates, and people;
- independent page title blocks, native-text availability, page dimensions, template name, word count, and text-block count;
- revision rows: revision, ECN, raw description, date, changed by, and approved by;
- numbered notes with original text and standard references;
- separately typed BOM, part-list, and service-parts rows;
- supplier flags, explicit markers, names, part numbers, manufacturer mappings, and imported-CAD statements;
- standard-reference designations;
- supplier-raster region locations; and
- Level-1 warnings and confidence/provenance for every extracted field.

Each `ExtractedField` can carry page number, PDF bounding box, raw text, evidence anchor, extraction method, numeric confidence, and confidence category. This permits deterministic validation evidence without reparsing the source PDF.

## Deterministic rules already supported

The present evidence supports high-confidence implementation of:

- required-field presence, subject to extraction confidence and applicability;
- drawing-number, revision, units, and selected title-field consistency across sheets;
- sheet-number bounds, sequence, and declared/PDF sheet-count comparison;
- revision-row structural presence and conservative cross-reference to the title revision;
- note number sequence, duplicate numbers, empty notes, configured phrases, standard-reference discovery, and syntax-only token checks;
- BOM/part-list/service-parts structural completeness, sequence, duplicates, positive numeric quantities, configured part-number patterns, and description length;
- supplier classification/marker/name/part-number/wrapper-note checks using explicit native evidence only;
- standard-reference syntax, duplicates, configured required references, and optional authoritative-master lookup; and
- cross-references between evidence already represented in `DrawingDocument`.

Applicable rules must downgrade to `MANUAL_REVIEW` or `NOT_EVALUATED` when required extraction is absent, ambiguous, or below the configured confidence threshold.

## Data unavailable or insufficient for automation

The following are blocked by the current evidence boundary:

- supplier-original title blocks, BOMs, dimensions, notes, revisions, tolerances, and standards that exist only inside raster regions;
- revision triangles, BOM balloons, SCC graphics beside rows, hatching, view arrows, and hidden-line relationships;
- reliable complete dimension-token, view-object, datum-frame, and feature-control-frame inventories;
- geometry, CAD-model relationships, design intent, functional datum selection, tolerance suitability, manufacturability, and dimensional completeness;
- authoritative obsolete-specification and obsolete-part decisions unless controlled master data is supplied; and
- checklist requirements whose applicability depends on product or part classifications not explicitly extracted.

Rules dependent on these inputs will remain visible in the registry and traceability matrix, but return `NOT_EVALUATED`, `MANUAL_REVIEW`, or `NOT_APPLICABLE` with an explicit reason. Supplier raster detection is informational and must not itself be treated as a failure.

## Known Level-1 constraints inherited by Level 2

- PDF-only inputs and local PoC persistence.
- Supported Club Car wrapper templates are currently 17 x 11 and 34 x 22 inches.
- No semantic OCR of embedded supplier originals.
- Graphical critical-component state may be unknown.
- Table recovery requires recognizable native headings.
- Confidence describes extraction evidence, not engineering correctness.
- Independent manual ground truth is currently limited to 37 Title Block/Supplier values.
- Existing stable extractors perform repeated PDF passes; Level 2 must not add another PDF parse.

## Checklist source

No separate client checklist document was present under project `docs` at baseline capture. The supplied Level-2 implementation specification is therefore the traceability source. Every listed requirement will be represented in `config/checklist_rules.yaml` and the Level-2 requirement traceability matrix; the absence of authoritative master data will be recorded rather than filled with invented policy.
