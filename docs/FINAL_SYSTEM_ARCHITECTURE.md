# Final system architecture

## Four independent levels

| Level | Responsibility | Persisted output | Boundary |
|---|---|---|---|
| 1 | Evidence-only PDF extraction | `drawing.json` | No absent-value inference |
| 2 | Deterministic checklist validation | `validation.json` | No visual/design judgment |
| 3 | Local visual detection and bounded OCR | `vision.json`, reviews | Detection is not correctness |
| 4 | Entity graph and relationship review | `relationships.json` | Relationship is not approval/root cause |

The FastAPI service owns upload validation, opaque drawing IDs, atomic persistence,
all four engines, exports, and the production SPA. The React/TypeScript client owns
workflow, PDF display, evidence overlays, filters, review presentation, and report
downloads. The browser receives structured evidence but does not compute findings.

## Complete-analysis sequence

```text
Upload → Level 1 → baseline Level 2 → Level 3 → visual-enriched Level 2
       → Level 4 → consolidated review report → engineer review
```

Each engine is modular and receives typed output from the preceding layers. Level 2
and Level 4 rules are individually fault-isolated. All IDs and rule decisions are
deterministic. The relationship graph contains drawing, sheet, title-block,
revision, note, BOM, balloon, SCC, datum, GD&T, supplier, part, standard, and visual
entities when evidence supports them.

## API and storage

`/api/drawings` provides upload and Level-1 resources. Child paths expose
validation, vision, relationships, complete analysis, report, and JSON/CSV exports.
The default filesystem store uses one opaque directory per drawing and atomic file
replacement. No external data transfer is performed.

## UI architecture

The analysis workspace uses grouped primary tabs for Drawing, Validation, Visual,
Relationships, and Report, plus secondary Drawing tabs. The PDF viewer remains
visible beside structured results on desktop. Evidence clicks select the source
page and bounding box. Demo mode hides development diagnostics while keeping
provenance available within finding details.

## Trust model

Source confidence propagates into downstream evidence. Missing or ambiguous input
uses explicit non-assertive statuses. The final status is review-oriented and the
application contains no engineering approval mechanism. See the Level-specific
architecture and limitations documents for rule boundaries.

