# Level 3 UI Integration Report

## Outcome

Level 3 visual engineering intelligence is integrated into the existing browser application without replacing the PDF viewer, Level-1 tabs, Level-2 checklist, drawing routes, evidence highlighting, or exports.

The implementation is review assistance only. It does not establish drawing approval, functional GD&T correctness, manufacturing readiness, standards compliance, or detector accuracy on the supplied drawings.

## Visual detectors

| Detector | Visual object | Implementation status |
|---|---|---|
| Revision triangle | `REVISION_TRIANGLE` | Implemented with contour, geometry, context, and nearby-token evidence; confidence-gated |
| BOM balloon | `BOM_BALLOON` | Implemented with enclosing geometry and an internal item token; confidence-gated |
| Datum symbol | `DATUM_SYMBOL` | Implemented for observable symbol and identifier syntax |
| GD&T frame | `GDT_FRAME` | Implemented for frame geometry and limited syntax tokens; no functional engineering judgment |
| Flag note | `FLAG_NOTE` | Implemented for flag geometry and numeric callout evidence |
| SCC symbol | `SCC_SYMBOL` | Controlled-template framework implemented; intentionally inactive until an approved symbol reference is supplied |
| Supplier raster OCR | `SUPPLIER_RASTER_TEXT` | Targeted OCR pipeline implemented; the configured Tesseract executable is unavailable on this host |
| View annotations | `VIEW_ARROW`, `SECTION_ARROW`, `DETAIL_CALLOUT` | Implemented for observable labels and annotation objects; completeness and local-scale semantics are not established |

Every emitted object preserves page number, bounding box, confidence, detector, extraction method, and available text or attributes. Production detectors contain no sample drawing numbers or sample-specific values.

## API endpoints

The existing valid Level-3 endpoints were retained; no duplicates were added.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/drawings/{id}/vision/analyze` | Run and persist Level-3 analysis for the current drawing ID |
| GET | `/api/drawings/{id}/vision` | Return the persisted `VisionReport` |
| GET | `/api/drawings/{id}/vision/summary` | Return dynamic object counts and detector notices |
| GET | `/api/drawings/{id}/vision/objects` | List detected visual objects |
| GET | `/api/drawings/{id}/vision/objects/{object_id}` | Return one visual object |

Existing review and export endpoints remain available at `/vision/objects/{object_id}/review`, `/vision/reviews`, and `/vision/export/json`.

## UI integration

- The header now identifies Level 1 extraction, Level 2 validation, and Level 3 visual intelligence.
- A drawing execution-state strip displays Level 1, Level 2, and Level 3 as `NOT RUN`, `RUNNING`, or `COMPLETE` where applicable.
- `RUN VISUAL ANALYSIS` / `RE-RUN VISUAL ANALYSIS` is available beside the drawing-level validation action and inside the Level-2 action row.
- The existing primary `Visual Intelligence` tab remains additive to all current tabs.
- The summary reads object totals dynamically from the backend for revision triangles, BOM balloons, datums, GD&T frames, SCC symbols, flag notes, supplier OCR regions, and low-confidence objects.
- The object table now shows Object Type, Detected Value, Page, Confidence, Detector, Linked Rule, and review actions.
- Table filters include All, Revision Triangles, BOM Balloons, Datum, GD&T, SCC, Flag Notes, and Supplier OCR.
- Category overlay toggles reuse the existing PDF viewer. Selecting an object navigates to its page and displays its bounding box, label, and confidence.
- Level-2 Rule Details marks visual results with `VISUAL EVIDENCE AVAILABLE`. Each located evidence entry is separately clickable and highlights its PDF region.
- Development mode displays drawing ID, Level-1/2/3 states, object count, vision API URL, and unlocked-rule count.

## Visual Upgrades

The Level-2 validation panel now includes a `Visual Upgrades` view. It compares the in-memory Level-2 report captured immediately before the first Level-3 run with the post-Level-3 validation report and displays:

- Not Evaluated Before Level 3;
- Rules Unlocked by Level 3;
- New Pass;
- New Fail;
- New Warning;
- Remaining Not Evaluated;
- the explicit IDs of unlocked rules.

If a page is reopened with only a previously persisted post-Level-3 report, no pre-Level-3 snapshot is fabricated; the UI asks for a fresh Level-2-before-Level-3 sequence before showing a delta.

## Confidence gating

Confidence bands are controlled by `config/vision.yaml`:

- at or above the object-specific automatic threshold (normally `0.90`): eligible for deterministic syntax or cross-reference validation;
- `0.75` up to the automatic threshold: `WARNING` / partially automated evidence;
- below `0.75`: `MANUAL_REVIEW` when an object is present.

Detector absence does not prove that an object is absent. Visual evidence cannot turn unresolved completeness or functional engineering semantics into an automatic failure.

## Level-2 rules upgraded

| Evidence | Rules |
|---|---|
| Revision triangles | `REV-012` |
| BOM balloons | `BOM-011`, `BOM-012`, `XREF-007` |
| Flag notes | `NOTE-012` |
| SCC symbols | `BOM-014`, `XREF-006` |
| Supplier raster OCR | `SUP-010` |
| Datum symbols | `GDT-001`, `GDT-002`, `GDT-003` |
| GD&T frames | `GDT-004`, `GDT-005` |
| View/section/detail annotations | `VIEW-001` through `VIEW-005` |

These upgrades are syntax, presence-of-evidence, or cross-reference assistance. Functional GD&T selection and correctness remain outside automated extraction.

## Supplied drawing observations

The following are detector outputs from the current run, not manually verified ground truth.

| Drawing | Objects | Per-type detector output | Low confidence | Time |
|---|---:|---|---:|---:|
| `47789413_C_watermarked.pdf` | 49 | Datum 9; Detail 10; Flag note 5; Revision triangle 16; Section 2; View 7 | 21 | 3881.8 ms |
| `47789460_B_watermarked.pdf` | 51 | Datum 1; GD&T frame 1; Revision triangle 47; Section 2 | 49 | 2790.3 ms |
| `47789660_A_watermarked.pdf` | 4 | Revision triangle 2; Section 1; View 1 | 4 | 1018.1 ms |

No BOM balloons, SCC symbols, or supplier OCR regions were emitted for these three PDFs in this run. Because there is no manually reviewed visual annotation set, class precision, recall, F1, IoU, count accuracy, and text-recognition accuracy remain `null` in the Level-3 evaluation output.

The unusually high revision-triangle candidate count on `47789460_B_watermarked.pdf` is not treated as a verified count; all 47 triangle candidates are below the automatic threshold and the affected revision rule remains a warning.

## Validation changes observed in evaluation

| Drawing | Before Level 3 | After Level 3 | Unlocked rules |
|---|---|---|---|
| `47789413_C` | PASS 38; WARNING 0; MANUAL 10; NOT EVALUATED 36 | PASS 43; WARNING 4; MANUAL 10; NOT EVALUATED 27 | `REV-012`, `NOTE-012`, `VIEW-001`–`004`, `GDT-001`–`003` |
| `47789460_B` | PASS 34; WARNING 1; MANUAL 9; NOT EVALUATED 31 | PASS 38; WARNING 3; MANUAL 9; NOT EVALUATED 25 | `REV-012`, `VIEW-003`, `GDT-001`, `GDT-002`, `GDT-003`, `GDT-004` |
| `47789660_A` | PASS 38; WARNING 0; MANUAL 9; NOT EVALUATED 31 | PASS 38; WARNING 4; MANUAL 9; NOT EVALUATED 27 | `REV-012`, `VIEW-001`, `VIEW-002`, `VIEW-003` |

All three reports retain overall status `REVIEW_REQUIRED`. There were no new automatic failures.

## Verification

| Check | Result |
|---|---|
| Full backend suite | PASS — 114 tests |
| Level-3-specific tests | PASS — 8 tests |
| Ruff | PASS |
| `python scripts/evaluate_level1.py` | PASS — 37/37 expectations; accuracy and coverage 1.0 |
| `python scripts/evaluate_level2.py` | PASS — 28/28 expectations; precision and recall 1.0 on available rule ground truth |
| `python scripts/evaluate_level3.py` | PASS — all 3 PDFs processed; ungrounded class metrics correctly remain `null` |
| `npm run lint` | PASS |
| `npm run build` | PASS; Vite emitted only its non-fatal large-chunk advisory |
| API integration | PASS — upload/analyze/persist/report/summary/object-list/export flow covered by tests |
| Interactive browser workflow | ENVIRONMENT-BLOCKED — the installed in-app browser runtime was rejected by its trusted-path configuration before a page could open; its troubleshooting surface also could not initialize |

The interactive sequence must be rerun after the browser runtime trust configuration is repaired. It is not reported as passed based solely on API or build tests.

## Remaining unsupported visual checks

- Complete, calibrated client-sample detection metrics until visual ground truth is manually annotated.
- Engineering correctness of GD&T characteristics, datum selection, tolerance values, modifier applicability, and manufacturing intent.
- Proof of balloon, revision marker, note callout, view, datum, or GD&T completeness from detector absence.
- SCC detection until an approved symbol template and labeled examples are supplied.
- Supplier raster OCR on this host until the configured OCR executable/provider is available; OCR output will still require review.
- Reliable interpretation of balloon occurrence quantity and local view-scale semantics.
- Full engineering drawing approval.
