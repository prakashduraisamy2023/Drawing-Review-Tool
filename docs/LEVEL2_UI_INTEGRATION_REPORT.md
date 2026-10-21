# Engineering Drawing Intelligence
## Level-2 UI Integration Report

### Scope

This work verifies and completes browser usability for the existing Level-2 backend. No validation rule, evaluator, applicability condition, severity, or overall-status logic was changed.

## Root cause

Level 2 was implemented but difficult to discover:

- the only validation action was inside the second-to-last analysis tab;
- the tab strip is horizontally scrollable in the narrow analysis panel, so the late Validation tab could be outside the visible area;
- before validation, its badge displayed `0`, which looked like no Level-2 capability or no results rather than an action waiting to run;
- no prominent post-extraction action existed in the drawing header;
- the UI did not automatically open Validation or refresh the persisted report after triggering it;
- Not Evaluated, catalog coverage, exports, and integration diagnostics were not sufficiently visible.

There is no validation feature flag and no hidden validation component. Conditional rendering only selected the pre-run versus completed report state. The Level-1 and Level-2 clients use the current opaque drawing ID with `fetch`.

The frontend is served by Vite; FastAPI does not mount `frontend/dist`. Running only FastAPI will not display the React application. A pre-existing Vite process or cached browser tab can therefore show an older UI bundle until the development server and page are refreshed.

## Backend validation endpoints

The existing routes are registered directly in `backend/app/main.py`; no duplicate router or endpoint was added.

| Purpose | Method and path |
|---|---|
| Trigger validation | `POST /api/drawings/{drawing_id}/validate` |
| Complete report | `GET /api/drawings/{drawing_id}/validation` |
| Summary | `GET /api/drawings/{drawing_id}/validation/summary` |
| Controlled rule catalog | `GET /api/drawings/{drawing_id}/validation/rules` |
| Individual result | `GET /api/drawings/{drawing_id}/validation/results/{rule_id}` |
| JSON export | `GET /api/drawings/{drawing_id}/validation/export/json` |
| CSV export | `GET /api/drawings/{drawing_id}/validation/export/csv` |

The rule-catalog endpoint already supplies `automation_status`; the UI derives the coverage cards from that controlled catalog response, not from drawing applicability results. No new summary endpoint was necessary.

## Manual API verification

A fresh upload used the same `/api/drawings/upload` pathway as the browser, followed by the validation trigger and retrieval endpoints. The test drawing ID was `12e3ea1c-3428-4ae6-83a2-0acaa0f92359` on the isolated QA server at `http://127.0.0.1:8002`.

Observed summary:

```json
{
  "total_rules": 108,
  "passed": 38,
  "failed": 0,
  "warnings": 0,
  "manual_review": 10,
  "not_applicable": 24,
  "not_evaluated": 36,
  "critical_failures": 0,
  "high_failures": 0,
  "overall_status": "REVIEW_REQUIRED"
}
```

The report contained 108 complete `ValidationResult` objects. `TB-001` detail retrieval succeeded, and JSON and CSV exports both returned HTTP 200.

## Frontend integration completed

- Added a prominent `RUN LEVEL 2 VALIDATION` button beside the drawing summary immediately after Level-1 extraction.
- The button uses the current drawing ID, blocks repeat requests while loading, opens Validation, refreshes the persisted report, and changes to `RE-RUN VALIDATION`.
- Restyled the Validation tab with an `L2` marker; after execution it shows the 108-result count rather than a misleading failure/zero badge.
- Added explicit `RE-RUN VALIDATION`, `EXPORT VALIDATION JSON`, and `EXPORT VALIDATION CSV` controls in the Validation workspace.
- Added Summary, Checklist, Failures, Warnings, Manual Review, Not Evaluated, and Rule Details views.
- Added all requested result filters and all backend-driven category choices.
- Checklist columns now include Rule ID, Requirement, Category, Automation Type, Status, Severity, Expected, Actual, and Evidence.
- Rule details now show category, automation type, rule version, expected/actual conditions, explanation, recommendation, and evidence.
- Preserved single- and multi-region PDF evidence navigation with page, confidence, method, raw text, and status-labelled overlays.
- Added a non-error explanation for `REVIEW_REQUIRED`.
- Added catalog coverage cards sourced from `/validation/rules`: 56 fully automated, 18 partially automated, 7 manual, and 27 not implemented.
- Added development-only diagnostics for drawing ID, Level-1 state, Level-2 state, validation URL, and result count.
- No unqualified “system accuracy 100%” is displayed.

## Browser verification

### Standard drawing

`47789413_C_watermarked.pdf`:

- upload and Level-1 extraction passed;
- prominent Level-2 action was visible without opening a tab;
- validation automatically opened after the action;
- summary displayed 108 total, 38 passed, 0 failed, 0 warnings, 10 manual review, 24 not applicable, and 36 not evaluated;
- checklist displayed 108 rows;
- Not Evaluated filter displayed 36 rows;
- Manual Review displayed 10 rows;
- `GDT-006` detail explained that functional GD&T correctness requires engineering judgment;
- `TB-001` evidence navigated to page 1 and displayed its bounding box and raw value;
- JSON export initiated successfully.

### Supplier drawings

`47789460_B_watermarked.pdf` displayed 108 rows with 34 pass, 0 fail, 1 warning, 9 manual review, 33 not applicable, and 31 not evaluated.

`47789660_A_watermarked.pdf` displayed 108 rows with 38 pass, 0 fail, 0 warnings, 9 manual review, 30 not applicable, and 31 not evaluated.

No browser console errors or warnings were recorded.

## Screenshot descriptions

- `level2-validation-summary.png`: split engineering dashboard with the source PDF on the left and a clearly labelled Level-2 checklist on the right. It shows re-run/export controls, development diagnostics, Review Required status, the seven summary cards, and catalog coverage below.
- `level2-manual-review.png`: Manual Review view showing dedicated navigation, complete status filters, category filter, and engineering-review rows such as dimension and cross-reference checks. Manual review is visually distinct from failure.

Screenshots are stored under the Codex visualization output directory for this task.

## Build and regression results

| Check | Result |
|---|---|
| Frontend ESLint | Passed |
| TypeScript/Vite production build | Passed |
| Frontend tests | No test script is configured in `frontend/package.json` |
| Backend test suite | 105 passed, 0 failed |
| Ruff | Passed |
| Level-2 evaluator | 28/28 grounded expectations correct; 14/108 grounded rule IDs |
| Browser E2E | Passed for all three supplied PDFs |

The existing Vite warning about the large PDF.js bundle and the upstream Starlette/httpx deprecation warning remain non-fatal.

## Running and using Level 2

From the repository root, start FastAPI:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, restart Vite:

```powershell
cd frontend
npm.cmd run dev
```

Open `http://127.0.0.1:5173`, hard-refresh if an older dashboard was already open, upload a supplied PDF, and select **Analyze drawing**. When Level 1 completes, select **RUN LEVEL 2 VALIDATION** in the drawing header. The UI automatically opens **Validation**. Use **Manual Review** and **Not Evaluated** for transparent non-automated outcomes; select any rule ID for full details and any enabled evidence count to locate the source on the PDF.

Automated validation assists engineering drawing review. Final engineering approval remains the responsibility of the authorized reviewer.
