# Engineering Drawing Intelligence
## Level 2 Completion Report

### 1 Executive Summary

Level 2 is operational as a separate deterministic, evidence-based drawing-check layer over the stable Level-1 `DrawingDocument`. It provides a controlled 108-rule registry, applicability and dependency handling, fault isolation, traceable results, APIs, JSON/CSV exports, checklist mapping, evaluation, and a dashboard with multi-region PDF evidence navigation.

Acceptance: **PASS WITH LIMITATIONS**. The software path is complete and stable for the supplied PDFs, but engineering approval remains human, several visual/geometry categories are intentionally not evaluated, and independent truth coverage remains narrow.

### 2 Level-2 Objective

Level 2 determines whether explicit Level-1 evidence satisfies predefined drawing-check conditions. It does not infer absent information, validate CAD geometry, or decide complete engineering correctness.

### 3 Architecture

Persisted Level-1 evidence flows into a read-only validation context, applicability engine, stable registry, independent declarative rules, deterministic summary, separate persistence, APIs/exports, and dashboard. A rule exception becomes `NOT_EVALUATED` and cannot abort the drawing.

### 4 Rule Categories

Title Block, Revision, Notes, Standards, BOM, Part List, Service Parts, Supplier, Cross Reference, Dimensions, Views, and GD&T.

### 5 Automated Rules

| Rule population | Count | Status |
|---|---:|---|
| Automated | 56 | Deterministic when applicability and evidence gates pass |
| Partially automated | 18 | Controlled config, ambiguity, or master data may be required |
| Manual | 7 | Engineering judgment required |
| Not implemented | 27 | Required visual/geometry evidence unavailable |
| Total mapped rules | 108 | Stable versioned IDs |

The complete rule-by-rule table is in `docs/level2_rule_catalog.md`.

### 6 Checklist Coverage

- Source items mapped to a stable rule: 108/108, 100% traceability.
- Automated or partially automated assistance: 74/108, 68.5%.
- Manual: 7/108, 6.5%.
- Explicitly not implemented: 27/108, 25.0%.
- Independently grounded rule IDs: 14/108, 13.0%.

No source checklist item is silently omitted. Unavailable capabilities remain visible as `MANUAL_REVIEW` or `NOT_EVALUATED`.

### 7 Sample Drawing Results

| Drawing | Rules Run | Pass | Fail | Warnings | Manual Review | N/A | Not Evaluated |
|---|---:|---:|---:|---:|---:|---:|---:|
| `47789413_C_watermarked.pdf` | 108 | 38 | 0 | 0 | 10 | 24 | 36 |
| `47789460_B_watermarked.pdf` | 108 | 34 | 0 | 1 | 9 | 33 | 31 |
| `47789660_A_watermarked.pdf` | 108 | 38 | 0 | 0 | 9 | 30 | 31 |

All overall statuses are `REVIEW_REQUIRED` because manual/not-evaluated requirements remain. No sample is declared engineering-approved.

### 8 Level-2 Evaluation

The independent ground-truth set contains 28 expectations across 14 rule IDs. Accuracy, precision, and recall are 100% only for this grounded subset. Empty categories report zero coverage, not 100%. Detailed output is stored in `data/output/evaluation/level2_results.json` and `.csv`.

### 9 Test Results

- Validation model/rule/API focused suite: 31 passed.
- Ruff: passed.
- Frontend ESLint: passed.
- TypeScript/Vite production build: passed with existing PDF.js size warning.
- All three Level-1 to Level-2 sample integrations: passed.
- Live browser workflow: supplier upload, 108-rule summary, warning filter, explainable detail, seven evidence overlays, and zero console errors passed.
- Complete backend suite: 105 passed, 0 failed.
- Level-1 regression evaluator: 37/37 correct, with zero incorrect, missing, or declared false extractions.

### 10 Known Limitations

- PDF only; no CAD geometry.
- No complete supplier-raster interpretation.
- No functional GD&T approval.
- No manufacturability determination.
- No complete dimensional-completeness determination.
- No authoritative obsolete-spec/part masters.
- Human approval is required.
- Manual truth covers only a subset of rules.

### 11 Level-2 Acceptance

**PASS WITH LIMITATIONS**

The rule engine, controlled registry/config, applicability, dependency handling, evidence traceability, APIs, exports, UI, RTM, ground-truth framework, evaluator, and sample integration are implemented. Limitations are explicit and do not masquerade as automated approval.

### 12 Recommended Level-3 Scope

Define authoritative master-data connectors, reviewer identity/audit workflow, targeted supplier-region OCR with confidence adjudication, native dimension/view/GD&T token extraction, and separately governed visual models. Level 3 is not implemented.

---

Automated validation assists engineering drawing review. Final engineering approval remains the responsibility of the authorized reviewer.
