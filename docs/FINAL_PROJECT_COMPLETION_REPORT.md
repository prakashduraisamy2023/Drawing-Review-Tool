# Engineering Drawing Intelligence System

## Final PoC completion report

### 1. Executive summary

The existing Levels 1–3 application was extended with a modular Level-4 engineering
relationship layer, consolidated workflow/reporting, presentation-focused UI,
single-server demo packaging, evaluation tooling, tests, and deployment/user
documentation. The PoC is code-complete for controlled client demonstration. It is
not represented as production-qualified or as an engineering approval system.

### 2. Project objective

The system turns drawing evidence into a traceable review workspace: extract what
is present, evaluate controlled checklist rules, detect selected visual objects,
and relate those outputs without inventing absent values or design intent.

### 3. Four-level architecture

Level 1 performs evidence extraction; Level 2 performs independent deterministic
validation; Level 3 supplies independent visual evidence; Level 4 builds an entity
graph and evaluates evidence-backed relationships. Every boundary is maintained in
separate packages and persisted contracts.

### 4. Level 1 – implemented capabilities

The application extracts title blocks, revisions, notes, standards, BOM/part/service
tables, supplier evidence, page context, raster regions, provenance, confidence,
and JSON/CSV evidence exports from PDFs without filling missing fields.

### 5. Level 2 – implemented capabilities

The 108-entry checklist registry runs deterministic and conservative checks with
explicit pass, fail, warning, manual, not-applicable, and not-evaluated outcomes.
Rules remain separate from extraction and consume the canonical document model.

### 6. Level 3 – implemented capabilities

Local page rendering, traditional computer vision, confidence gates, optional
bounded Tesseract OCR, PDF-coordinate evidence, visual overlays, and separate human
review records support revision, balloon, note, datum/GD&T, supplier-raster, and
related candidate detection.

### 7. Level 4 – implemented capabilities

Twelve registered rules cover BOM/balloon links, orphan balloons, BOM quantity,
revision triangles, change traceability, note callouts, SCC semantics, datum/GD&T,
unused datums, supplier identity, part mapping, and cross-sheet consistency. The
engine also supplies stable entity graphs, correlations, priorities, explanations,
recommendations, provenance, persistence, APIs, and exports.

### 8. Checklist coverage

All existing Level-2 registry behavior remains covered by the passing regression
suite. Level 4 reuses selected Level-2 issue IDs for traceability without converting
Level-2 results into new extraction facts.

### 9. Visual detection coverage

Visual detection remains limited to the documented traditional-CV classes and
confidence policy. SCC template semantics and broad drawing understanding are not
claimed. Missing detection does not automatically establish absence.

### 10. Relationship coverage

All 12 catalog IDs were exercised across the supplied samples. Relationship output
is available through dedicated endpoints and UI workspaces, with evidence-linked
finding details and a filterable graph.

### 11. Ground-truth evaluation

The Level-4 evaluator processed all three PDFs and emitted JSON/CSV results. No
independently reviewed Level-4 expectations exist, so accuracy, precision, and recall
remain null. This prevents circular or fabricated accuracy claims.

### 12. Sample drawing results

The three inputs produced 20, 12, and 12 Level-4 findings and graphs of 80/14,
80/1, and 18/1 nodes/edges. Each report requires engineer review because some
relationships are warnings, manual review, or not evaluated.

### 13. Test results

The full Python suite passed 117 tests. Ruff, ESLint, TypeScript, and the production
build passed. The only reported warnings are a test-client deprecation and a Vite
bundle-size advisory. Interactive viewport automation was blocked by the local
browser runtime and is not claimed as passed.

### 14. Performance results

Measured Level-4 engine times were 2.440 ms, 1.600 ms, and 0.743 ms. Complete
pipeline times were 11.528 s, 3.335 s, and 1.448 s on the current workstation.

### 15. Client deployment requirement

The production UI can be served by FastAPI in one local process. `start_demo.bat`
checks prerequisites, builds the frontend if required, starts the service, waits for
health, and opens the browser. Detailed system and hardening requirements are in
`CLIENT_DEPLOYMENT_REQUIREMENTS.md`.

### 16. Known limitations

No level approves engineering correctness. The system does not prove geometry
changes, quantity occurrence, SCC meaning, supplier equivalence, functional GD&T,
manufacturability, safety, or causality. Current Level-4 accuracy is unmeasured due
to absent independent annotations. Manual visual viewport acceptance remains.

### 17. Final PoC acceptance status

**Code-complete and regression-verified for controlled demonstration, with
conditions.** Conditions are: complete manual viewport review at 1920×1080 and
1366×768, obtain engineering-reviewed Level-4 ground truth, and perform security/
operational qualification before production use. This is not final engineering
approval of any drawing.

### 18. Recommended production-phase enhancements

Add controlled SCC and supplier master data, domain-reviewed Level-3/4 annotation
sets, trained visual models where justified, authentication/authorization, audit
and retention controls, observability, signed releases, deployment automation,
performance/load testing, accessibility testing, and formal engineering validation.

