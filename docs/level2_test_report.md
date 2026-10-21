# Level-2 test report

## Automated checks

| Check | Result |
|---|---|
| Validation model/rule/API focused tests | 31 passed |
| Complete backend suite | 105 passed, 0 failed |
| Ruff | Passing |
| Frontend ESLint | Passing |
| Frontend TypeScript/Vite production build | Passing |
| Level-2 evaluator | 28/28 grounded expectations correct |
| Sample Level-1 to Level-2 integration | All three PDFs serialize without crashes |
| Browser dashboard | Upload, validation summary, warning filter, rule details, seven-region PDF overlay, zero console errors |

Synthetic tests cover presence, missing evidence, low confidence, cross-sheet agreement/conflict, ambiguity, applicability, technical exception isolation, registry uniqueness, structured explainability, and serialization. Sample integration asserts execution and evidence shape, not unreviewed engineering correctness.

## Independent metrics

The manually maintained files in `tests/validation_ground_truth` contain 28 expectations across 14 rule IDs. Accuracy, precision, and recall are 100% for that bounded subset. This is not a 100% claim for the 108-rule catalog. Category ground-truth coverage is Title Block 8/14, Supplier 5/10, Standards 1/5, and zero for all remaining categories.

## Sample execution

| Drawing | Rules | Pass | Fail | Warning | Manual | N/A | Not evaluated | L1 ms | L2 ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `47789413_C_watermarked.pdf` | 108 | 38 | 0 | 0 | 10 | 24 | 36 | 7308.076 | 4.392 | 7312.469 |
| `47789460_B_watermarked.pdf` | 108 | 34 | 0 | 1 | 9 | 33 | 31 | 893.369 | 2.946 | 896.315 |
| `47789660_A_watermarked.pdf` | 108 | 38 | 0 | 0 | 9 | 30 | 31 | 519.874 | 2.640 | 522.514 |

Times are one representative local evaluator run and will vary by host. Level 2 is millisecond-scale and does not re-open the PDF.

## Findings in supplied drawings

- No deterministic `FAIL` result was produced for the three samples.
- `47789460_B_watermarked.pdf` has `STD-002` warning because explicit `CAL 117` text is outside the currently configured identifier syntax families. The warning does not state that CAL 117 is invalid.
- All drawings require human review for dimension semantics/completeness, view completeness, functional GD&T/datum decisions, and ASME Y14.5 full compliance.
- `47789413_C_watermarked.pdf` also requires review for differing page-level part names.

The test stack retains one upstream Starlette/httpx deprecation warning. The frontend build retains the existing PDF.js chunk-size warning.

Level-1 regression evaluation remains 37/37 correct, with zero incorrect, missing, or declared false extractions.
