# Level 4 requirement traceability matrix

| Requirement | Implementation | Verification |
|---|---|---|
| Consume Levels 1–3 without reparsing | `relationships/context.py`, complete-analysis API | API and engine tests |
| Strict entity/edge/result models | `relationships/models.py` | serialization/model tests through API |
| Provenance on relationship evidence | context builders and all rules | `test_relationship_engine.py` |
| Engineering graph | `relationships/graph.py` | graph API test |
| BOM/balloon/orphan/quantity | `rules/bom_relationships.py` | synthetic relationship test |
| Revision triangle/change traceability | `rules/revision_relationships.py` | synthetic relationship test |
| Note/callout | `rules/note_relationships.py` | synthetic relationship test |
| SCC | `rules/scc_relationships.py` | safe missing-semantics path tested |
| Datum/GD&T/unused datum | `rules/datum_gdt_relationships.py` | synthetic relationship test |
| Supplier and part mapping | supplier/part relationship rules | full sample evaluation |
| Cross-sheet consistency | `rules/document_relationships.py` | full sample evaluation |
| Fault isolation | `relationships/engine.py` | existing engine isolation pattern and suite |
| Correlation and prioritization | engine/prioritization | relationship and API tests |
| Level 4 API and exports | `backend/app/main.py` | `test_api.py` |
| Complete analysis/report | `backend/app/main.py` | complete-analysis API test |
| Grouped, readable Level 4 UI | `frontend/src/App.tsx`, `styles.css` | TypeScript build and lint |
| Evidence navigation and graph filtering | relationship UI callbacks | TypeScript build and lint |
| Demo mode and single-server delivery | config, UI, SPA mount, `start_demo.bat` | production build and health/API tests |
| Independent evaluation | `scripts/evaluate_level4.py` | executed on all supplied PDFs |
| No production sample hard-coding | generic rules/config; hard-code audit | repository search documented in final report |

Browser viewport acceptance remains a manual/client-environment check if the local
automation browser cannot initialize; build success alone is not presented as
visual acceptance.

