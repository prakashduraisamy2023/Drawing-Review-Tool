# Review-corpus improvement report

Date: 2026-08-20

## Scope and evidence policy

All 16 supplied PDFs were copied unchanged into `data/training/pdfs` and audited
through the same Level-1 and Level-3 pipeline. The corpus contains 76 pages.
SHA-256 hashes, page metadata, extraction output, visual predictions, and debug
overlays are stored under `data/output/training_audit`.

The corpus is not independently labelled ground truth. The counts below are
detector observations, not precision, recall, completeness, or approval claims.

## Corrected systematic failures

1. Split balloons with touching leaders were usually missed because the leader
   merged with the circular contour. The balloon detector now proposes aligned
   upper/lower numeric text pairs and requires strong circumference evidence.
2. Dimension multipliers such as `2X` were accepted as item identifiers. Balloon
   identifiers now require numeric item text.
3. Square/rectangular table cells could satisfy the old circularity threshold.
   Closed-contour acceptance now also checks polygon complexity and stronger
   roundness constraints.
4. The lower split-balloon compartment was discarded. Both compartments are now
   preserved separately, while only the upper value is linked as the BOM item.
5. Quantity interpretation previously had no usable visual evidence. Level 2 and
   Level 4 now summarize explicit lower-compartment numerals, but matching remains
   `MANUAL_REVIEW`; mismatches are warnings and never proof of an engineering error.
6. A three-character part number was rejected, dropping its BOM row. The generic
   validator now accepts evidence-backed part numbers containing three or more
   permitted characters.

## Post-change corpus observations

- PDFs processed: 16/16
- Pages processed: 76
- Failures: 0
- BOM/parts-table rows emitted: 93
- Balloon candidates emitted: 71
- Split-balloon candidates: 71
- Extraction warnings: 4, all existing informational supplier-raster warnings

For the 37-sheet assembly, 27 split-balloon occurrences cover item identifiers
1 through 26. Item 25 has two explicit lower-compartment values, 18 and 4. The
Level-4 provisional totals agree numerically with all 26 extracted BOM quantities,
but every result remains manual review until the drawing convention is confirmed.

For drawing `47789798`, the visible BOM row for item 1 and part number `451` is
now preserved. Its visible balloon set is not forced to equal the entire BOM;
notes and drawing content explicitly leave some parts unshown.

## Verification

- Full backend suite: 120 tests passed.
- Focused balloon, BOM, validation, and relationship suite: 18 tests passed.
- Ruff checks on all modified Python files: passed.
- Corpus audit: 16 succeeded, 0 failed.

No trained neural model or cloud service was introduced. Reviewed labels can be
added later under `tests/vision_ground_truth`, but detector predictions must never
be copied there as ground truth.
