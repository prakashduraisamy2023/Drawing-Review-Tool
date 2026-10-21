# Level 4 test report

Test date: 2026-08-19

## Automated verification

| Check | Result |
|---|---|
| Full Python regression suite | 117 passed |
| Focused relationship/API tests | Included and passed in full suite |
| Ruff backend/tests/scripts | Passed |
| ESLint frontend | Passed |
| TypeScript + Vite production build | Passed |
| Level-4 evaluator on all supplied PDFs | Passed, 3/3 processed |

One non-failing dependency warning reports that the current Starlette TestClient
compatibility path for `httpx` is deprecated. The production frontend build also
reports a bundle-size advisory for the PDF.js-containing chunk; it is not a build
failure.

## Evaluation results

All 12 catalog rule IDs were observed during evaluation. The samples produced 20,
12, and 12 findings. Level-4 execution measured 2.440 ms, 1.600 ms, and 0.743 ms.
Complete pipeline time measured 11.528 s, 3.335 s, and 1.448 s on this workstation.

No manually reviewed Level-4 expectations currently exist. Accuracy, precision,
and recall are therefore null, not zero or 100%. Results are recorded in
`data/output/evaluation/level4_results.json` and `.csv`.

## Visual browser verification

The production UI compiled successfully. Automated interactive viewport testing
could not be completed because the Codex in-app browser service failed to initialize
its trusted RPC dependency. Consequently, 1920×1080 and 1366×768 visual acceptance
remain unclaimed and require a manual pass in the client browser. Responsive CSS,
wrapped tables, grouped tabs, minimum font sizing, and mobile breakpoints are
implemented, but that is not substituted for visual acceptance.

