# Known Level-2 limitations

- Results assist drawing review and never constitute engineering approval.
- Input remains PDF only; no native CAD geometry or model-to-drawing comparison is available.
- Supplier-original raster content is bounded but not OCR-interpreted. Internal supplier title blocks, BOMs, dimensions, tolerances, revisions, and standards remain unavailable.
- Revision triangles, balloons, SCC row symbols, hidden lines, hatching, and arrow direction are not extracted by Level 1.
- Complete dimension, view, datum, and feature-control-frame inventories are not present in the canonical Level-1 model. Related syntax checks remain not evaluated.
- Functional GD&T correctness, datum suitability, tolerance suitability, manufacturability, design intent, dimensional completeness, product safety, and change acceptability require an authorized engineer.
- Obsolete specification and obsolete part checks require authoritative, controlled master data; none is supplied.
- Required note phrases, supplier note numbers, part-number patterns, and description-length limits remain inactive until a source-authorized configuration is supplied.
- Part-name differences across sheets return manual review because page-specific descriptions may be intentional.
- Multiple-table reconstruction lacks a persistent table identifier. Structural logic recognizes assembly-header rows and separates common groups conservatively, but novel layouts may require review.
- Historical Level-1 processing time is not stored in `DrawingDocument`; the Level-2 evaluator measures Level-1, Level-2, and total wall time during a combined run. The validation API reports Level-2 time without reparsing the PDF.
- Manual ground truth currently covers 28 expectations across 14 of 108 rule IDs. BOM, Revision, Notes, Dimensions, Views, GD&T, Cross Reference, Part List, and Service Parts have no independent Level-2 truth labels.
- Persistence is local PoC filesystem storage without authentication, role-based review authorization, retention policy, malware scanning, or audit-trail immutability.
- Reviewer accept/reject/comment decisions are not implemented; automated evidence is never overwritten.
- The PDF.js production bundle remains large and Vite emits a non-fatal chunk-size warning.
