# Level-3 test report

## Test scope

Level-3 tests cover model serialization, class-specific confidence gates, cached rendering, PDF/pixel coordinate round trips, revision triangles, multiple triangles, large-triangle rejection, balloon detection, ordinary-hole rejection, datum symbols, segmented GD&T frames and tokens, targeted supplier OCR with a local fake provider, visual-to-validation integration, API persistence/list/summary/export, and frontend compilation.

## Latest verified results

| Check | Result |
|---|---|
| Untouched baseline | 105 passed |
| Level-3 focused tests | Passed |
| Full backend suite | 113 passed, 0 failed |
| Ruff | Passed |
| Frontend lint | Passed |
| Frontend production build | Passed; Vite reports only its standard large-chunk advisory |
| Level-1 evaluator | 37/37 correct; no regression |
| Level-2 evaluator | 28/28 correct; no regression |
| Level-3 evaluator | Completed; three PDFs processed; metrics null because no reviewed sample ground truth exists |

## Sample observations

| Drawing | Pages | Visual objects | Low confidence | Targeted OCR regions | Level-3 time (ms) |
|---|---:|---:|---:|---:|---:|
| `47789413_C_watermarked.pdf` | 5 | 49 | 21 | 0 | 4821.810 |
| `47789460_B_watermarked.pdf` | 1 | 51 | 49 | 0 | 3595.864 |
| `47789660_A_watermarked.pdf` | 1 | 4 | 4 | 0 | 1245.584 |

These counts are not accuracy claims. Debug overlays and report JSON are under `data/output/vision_debug` and `data/output/vision`.

## Live workflow verification

The running FastAPI and Vite services were exercised through upload, Level-3 analyze, Level-2 validate, visual-object list, and visual JSON export. The live result was 1 page processed, 4 visual candidates, 108 validation rules, and HTTP 200 export. Frontend lint and production compilation passed.

Interactive in-app browser attachment could not start because the installed browser-control runtime rejected its own service module as outside the configured trusted code path. This is recorded as unverified rather than replaced with another browser surface. The browser-only click/highlight workflow therefore remains a manual acceptance check in this environment.
