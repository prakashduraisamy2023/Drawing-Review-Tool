# Final user guide

## Start and upload

Run `start_demo.bat` and wait for the browser to open. Select a PDF engineering
drawing, upload it, and open the drawing analysis workspace. The application stores
the drawing under an opaque internal ID.

## Run analysis

Choose **RUN COMPLETE ANALYSIS** for the normal workflow. Progress is shown for
validation, visual analysis, relationship analysis, and final report preparation.
Level-2 and Level-3 actions remain available separately for investigation.

The primary navigation is:

- **DRAWING**: title block, revisions, notes, BOM, part/service lists, suppliers,
  standards, page context, and raw JSON.
- **VALIDATION**: checklist summary and results with filters and evidence.
- **VISUAL**: detected objects, confidence, overlays, and reviewer annotations.
- **RELATIONSHIPS**: summary, prioritized findings, correlations, traceability, and
  the filterable entity graph.
- **REPORT**: four-level status, key counts, top findings, final review status, and
  consolidated exports.

## Inspect evidence

Click an extracted field, validation result, relationship finding, graph node, or
top finding to navigate to the source PDF page. When coordinates exist, the viewer
highlights the evidence. Expand a relationship finding to see expected versus
actual links, confidence, explanation, recommendation, entity IDs, and Level-2
cross-references.

## Interpret statuses

- **PASS** means available evidence satisfied that controlled check.
- **FAIL** means reliable available evidence explicitly contradicted it.
- **WARNING** identifies a likely issue that deserves attention.
- **MANUAL REVIEW** requires engineering judgment or controlled reference data.
- **NOT APPLICABLE** means the rule does not apply to the available drawing type.
- **NOT EVALUATED** means reliable evidence or a required dependency was absent.

Priorities P1–P4 order review; they do not grant approval. Correlations are probable
issue groupings and are not root-cause diagnoses.

## Export and review

Use the Report workspace to download consolidated JSON or CSV. JSON preserves full
Level 1–4 structure; CSV is a flattened review aid. Use these files together with
the original PDF. The final system message is an automated-review status, never a
drawing approval. An authorized engineer remains responsible for acceptance.

## Troubleshooting

- If the launcher cannot find `.venv`, install backend dependencies.
- If the frontend is missing, install Node.js dependencies and run `npm run build`.
- If health times out, verify that port 8000 is free.
- If OCR is unavailable, raster OCR results remain unavailable while the other
  levels continue.
- If a relationship is not evaluated, inspect its evidence and limitation text;
  do not interpret the status as pass or fail.

