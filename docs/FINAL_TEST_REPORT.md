# Final test report

## Verification summary

The four-level application passed the full 117-test Python suite on 2026-08-19.
Backend/test/script Ruff checks, frontend ESLint, TypeScript compilation, and the
Vite production build also passed. API coverage includes upload/resources,
validation, visual analysis/review, Level-4 analysis/summary/findings/graph/export,
complete analysis, and consolidated report exports.

## Regression

Existing Level-1 extraction, Level-2 validation, and Level-3 visual tests all passed
without changing their evidence contracts. Level 4 reads their outputs and leaves
them intact. The evaluator successfully processed every PDF in `data/input`.

## Measured sample results

| Sample | Pages | L4 findings | Nodes | Edges | L4 ms | Complete ms |
|---|---:|---:|---:|---:|---:|---:|
| 47789413_C_watermarked.pdf | 5 | 20 | 80 | 14 | 2.440 | 11527.823 |
| 47789460_B_watermarked.pdf | 1 | 12 | 80 | 1 | 1.600 | 3335.347 |
| 47789660_A_watermarked.pdf | 1 | 12 | 18 | 1 | 0.743 | 1447.990 |

The three relationship reports returned `REVIEW_REQUIRED`, which is consistent with
unavailable/manual-review checks and is not engineering rejection. These counts are
engine outputs, not accuracy claims.

## Ground-truth policy

Level-1 and Level-2 retain their existing manually maintained reference sets. Level
3 and Level 4 report metrics only for independently reviewed annotations. There are
currently zero reviewed Level-4 expectations, so Level-4 accuracy, precision, and
recall are null. The schema and instructions for adding reviewed expectations are
under `tests/relationship_ground_truth`.

## Build observations

- Python tests: passed; one Starlette/httpx deprecation warning.
- Frontend: passed; one non-failing Vite chunk-size advisory caused primarily by
  PDF.js/worker delivery.
- Interactive browser automation: blocked by the local in-app browser runtime’s
  trusted dependency initialization failure. Manual 1920×1080 and 1366×768 viewport
  acceptance is still required.

## Acceptance boundary

Automated/code-level verification is complete. Client visual acceptance,
engineering-domain ground-truth review, and production security qualification are
explicitly outside the measured pass result.

