# Level 4 architecture

## Scope and boundary

Level 4 is a deterministic relationship-analysis layer. It consumes the persisted
`DrawingDocument` from Level 1, `ValidationReport` from Level 2, and `VisionReport`
from Level 3. It does not reopen the PDF, modify earlier outputs, call external
services, or decide engineering correctness.

```text
Level 1 evidence ─┐
Level 2 results  ─┼─> RelationshipContext ─> Entity graph ─> Rule registry
Level 3 objects  ─┘                                      │
                                                         v
                          Report/API/UI <─ priorities/correlations/findings
```

## Modules

- `models.py` defines strict entities, relationships, evidence, results, graph,
  summaries, correlations, timing, and consolidated-report contracts.
- `context.py` converts only available Level 1–3 outputs to canonical entities and
  provenance. Empty evidence remains empty.
- `graph.py` stores deterministic nodes and edges and generates stable hashed IDs.
- `rules/` contains one fault-isolated class per relationship family.
- `registry.py` controls rule registration and rejects duplicate IDs.
- `scoring.py`, `prioritization.py`, and `explanation.py` keep policy separate from
  extraction and matching.
- `engine.py` executes every rule independently, summarizes status, and groups
  related findings. A rule exception becomes `NOT_EVALUATED`, never a drawing fail.

## Data and provenance

Every entity records its type, value, source level, source reference, page,
bounding box where available, and confidence. Every finding contains expected and
actual relationship descriptions, entity IDs, evidence, explanation,
recommendation, severity, priority, and related Level-2 rule IDs. Stable IDs are
derived from generic relationship content, not sample filenames or drawing values.

## Status policy

- `PASS`: explicit evidence satisfies the relationship.
- `FAIL`: reliable evidence explicitly contradicts the relationship.
- `WARNING`: a likely broken link exists but detector completeness is insufficient
  for a definitive fail.
- `MANUAL_REVIEW`: the relationship needs engineering judgment or controlled data.
- `NOT_APPLICABLE`: the source drawing has no applicable entity family.
- `NOT_EVALUATED`: required reliable evidence or semantics are unavailable.

Level 4 correlations are review groupings and always carry the qualifier that they
are probable relationships, not proven root causes.

## Persistence and API

The drawing store writes `relationships.json` atomically beside existing Level
outputs. API routes expose analysis, the report, summary, findings, graph, and JSON
export. Complete analysis performs Level 2, Level 3, vision-enriched Level 2, Level
4, and final-report assembly in that order. The optional production SPA mount lets
FastAPI serve `frontend/dist` from the same process.

## Configuration and security

`config/relationships.yaml` controls version, confidence floors, missing-link
status, authoritative mapping placeholders, and correlation families. Mappings are
empty by default. Processing is local and no drawing data leaves the workstation.

