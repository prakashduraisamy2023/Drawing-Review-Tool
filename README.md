# Engineering Drawing Intelligence PoC – Levels 1 through 4

## Purpose

This repository extracts explicit, structured evidence from engineering-drawing PDFs, applies a separate deterministic Level-2 checklist, supplies a Level-3 visual-evidence layer, and evaluates evidence-backed Level-4 engineering relationships. Level 4 links revisions, balloons, BOM rows, notes, SCC symbols, datums, GD&T frames, suppliers, and document-control findings without asserting design intent or engineering approval. No level fills absent values or asks an LLM to decide whether a drawing is correct.

## Architecture

The FastAPI backend validates and stores an uploaded PDF under an opaque drawing ID, generates page context from native PDF content, and runs fault-isolated extractors. The React dashboard renders the original PDF with PDF.js and projects extraction bounding boxes over it. See [docs/level1_architecture.md](docs/level1_architecture.md) for the detailed data flow.

Primary extraction order:

1. PyMuPDF native text, words, blocks, page dimensions, and image metadata.
2. Normalized regions, explicit labels, and relative coordinates.
3. Cropped pdfplumber table extraction only where a table header establishes a candidate region.
4. No full-page OCR. Embedded supplier-original raster content is located but not OCR-extracted in Level 1.

## Tech stack

- Python 3.11+, FastAPI, Pydantic v2
- PyMuPDF, pdfplumber, OpenCV, Pillow, and optional local Tesseract OCR
- pytest and Ruff
- React, Vite, TypeScript, PDF.js, ESLint

## Project structure

```text
backend/app/
  evaluation/           manual-ground-truth evaluation engine
  extraction/           orchestrator and modular extractors
  models/drawing.py     canonical Level-1 Pydantic schema
  vision/               independent Level-3 engine, models, rendering, OCR, and detectors
  relationships/        independent Level-4 entity graph and relationship rules
  pdf/inspect_pdf.py    non-semantic PDF diagnostics
  main.py               FastAPI application
frontend/src/           upload and Drawing Analysis dashboard
backend/app/validation/ separate deterministic Level-2 rule engine
config/                 controlled rule and checklist mapping
tests/                  backend, API, integration, and extractor tests
tests/ground_truth/     manually maintained expected values
tests/vision_ground_truth/ independently reviewed visual-object annotations
tests/relationship_ground_truth/ independently reviewed Level-4 expectations
data/input/             sample input PDFs
data/output/            drawing records, diagnostics, and evaluation output
docs/                   architecture, audit, analysis, and reports
scripts/                evaluation command
```

## Installation

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
cd frontend
pnpm install
cd ..
```

`npm install` can be used instead of pnpm if desired.

## Start the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Health is available at `http://127.0.0.1:8000/health`; OpenAPI documentation is at `/docs`.

For a client demonstration after installation, run `start_demo.bat`. It builds the UI if needed, starts one local server for the API and production frontend, waits for health, and opens the browser at `http://127.0.0.1:8000`.

## Start the frontend

In another terminal:

```powershell
cd frontend
pnpm run dev
```

Open `http://localhost:5173`. Select a PDF, choose **Analyze Drawing**, and use the analysis tabs. Clicking an evidenced field navigates to its source page and highlights its bounding box. **Show Extracted Regions** displays every located field on the current page.

## Supported Level-1 extraction

- source filename, page count, classification, and per-page context
- title-block identity, people, date, units, scale, weight, sheet sequence, and explicit critical-component evidence
- revision records, numbered multiline notes, and engineering-standard references
- separately typed BOM, part-list, and service-parts rows
- supplier/manufacturer names, part numbers, manufacturer mappings, marker text, and imported-CAD statements
- supplier-original raster region bounding boxes without internal OCR
- confidence category, source page, extraction method, bounding box, raw text, and evidence anchor
- non-fatal extraction warnings, Level-1 summary, JSON export, and evidence CSV export

## API

- `POST /api/drawings/upload`
- `GET /api/drawings/{id}`
- `GET /api/drawings/{id}/pages`
- `GET /api/drawings/{id}/notes`
- `GET /api/drawings/{id}/bom`
- `GET /api/drawings/{id}/revisions`
- `GET /api/drawings/{id}/standards`
- `GET /api/drawings/{id}/supplier`
- `GET /api/drawings/{id}/export/json`
- `GET /api/drawings/{id}/export/csv`
- `POST /api/drawings/{id}/validate`
- `GET /api/drawings/{id}/validation`
- `GET /api/drawings/{id}/validation/summary`
- `GET /api/drawings/{id}/validation/rules`
- `GET /api/drawings/{id}/validation/results/{rule_id}`
- `GET /api/drawings/{id}/validation/export/json`
- `GET /api/drawings/{id}/validation/export/csv`
- `POST /api/drawings/{id}/vision/analyze`
- `GET /api/drawings/{id}/vision`
- `GET /api/drawings/{id}/vision/summary`
- `GET /api/drawings/{id}/vision/objects`
- `GET /api/drawings/{id}/vision/objects/{object_id}`
- `POST /api/drawings/{id}/vision/objects/{object_id}/review`
- `GET /api/drawings/{id}/vision/reviews`
- `GET /api/drawings/{id}/vision/export/json`
- `POST /api/drawings/{id}/relationships/analyze`
- `GET /api/drawings/{id}/relationships`
- `GET /api/drawings/{id}/relationships/summary`
- `GET /api/drawings/{id}/relationships/findings`
- `GET /api/drawings/{id}/relationships/graph`
- `GET /api/drawings/{id}/relationships/export/json`
- `POST /api/drawings/{id}/analysis/complete`
- `GET /api/drawings/{id}/report`
- `GET /api/drawings/{id}/report/export/json`
- `GET /api/drawings/{id}/report/export/csv`

## Level-2 validation

The Level-2 engine consumes only the saved `DrawingDocument`; it does not reopen or reparse the PDF. Its 108 stable checklist entries cover title blocks, revisions, notes, standards, BOM/part/service tables, suppliers, cross-references, dimensions, views, and GD&T. Deterministic checks run when reliable evidence and explicit applicability exist. Checks that require raster interpretation, geometry, design intent, authoritative master data, or engineering judgment return `NOT_EVALUATED`, `MANUAL_REVIEW`, or `NOT_APPLICABLE` with a reason.

The dashboard keeps all Level-1 tabs and adds **VALIDATION** with summary, checklist, failures, warnings, manual review, rule details, filters, and multi-region source highlighting.

See [docs/level2_architecture.md](docs/level2_architecture.md), [docs/level2_rule_catalog.md](docs/level2_rule_catalog.md), and [docs/level2_requirement_traceability_matrix.md](docs/level2_requirement_traceability_matrix.md).

## Level-3 visual intelligence

Level 3 opens the saved PDF through one shared PyMuPDF renderer and reuses cached 200-DPI page images across detectors. Detector results are mapped back to original PDF coordinates and persisted separately as `vision.json`. The Visual Intelligence tab lists objects, provides type-labelled overlays, exposes confidence and detector provenance, records reviewer actions separately, and automatically refreshes Level-2 validation after visual analysis.

Traditional-CV implementations cover revision-triangle, balloon, datum, GD&T-frame, view/section/detail annotation, and flag-note candidates. SCC has a deliberately inactive template framework because no controlled symbol example was supplied. Supplier OCR is restricted to raster bounding boxes already detected by Level 1. Tesseract is the offline provider; the application reports it unavailable and continues normally when the executable is absent. No trained detector or cloud service is used.

Configuration accepts `LEVEL3_ENABLED=true|false`, `OCR_ENABLED=true|false`, and `OCR_PROVIDER=tesseract` (the `DRAWING_`-prefixed forms are also supported). Level 1 and Level 2 continue to operate when Level 3 or OCR is disabled.

See [docs/level3_architecture.md](docs/level3_architecture.md), [docs/level3_detector_catalog.md](docs/level3_detector_catalog.md), and [docs/LEVEL3_COMPLETION_REPORT.md](docs/LEVEL3_COMPLETION_REPORT.md).

## Level-4 relationship intelligence

Level 4 consumes saved outputs from Levels 1–3 and never reparses a PDF. A deterministic, fault-isolated engine builds a provenance-bearing entity graph and evaluates 12 controlled relationship rules across revision, BOM, note, SCC, datum/GD&T, supplier/part, and document-control families. Missing or ambiguous evidence is surfaced as warning, manual review, not applicable, or not evaluated; it is not converted into a fabricated failure. Correlations are explicitly described as probable relationship families, not root-cause diagnoses.

The dashboard adds grouped **RELATIONSHIPS** and **REPORT** workspaces, evidence navigation, a filterable graph, review priorities, consolidated JSON/CSV exports, and a visible **RUN COMPLETE ANALYSIS** sequence. Individual Level-2 and Level-3 controls remain available.

See [docs/level4_architecture.md](docs/level4_architecture.md), [docs/level4_relationship_catalog.md](docs/level4_relationship_catalog.md), and [docs/FINAL_USER_GUIDE.md](docs/FINAL_USER_GUIDE.md).

Uploads require a `.pdf` extension, `application/pdf` MIME type, a valid PDF signature, and a readable non-empty document. The default 50 MiB limit is configurable with `DRAWING_MAX_UPLOAD_BYTES`; storage is configurable with `DRAWING_STORAGE_DIR`.

The earlier `/api/v1/extractions` endpoints are preserved for compatibility, but `/api/drawings` returns the canonical Level-1 model.

## PDF diagnostics

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m app.pdf.inspect_pdf ..\..\data\input\47789413_C_watermarked.pdf
```

With no input argument, the utility inspects every PDF in `data/input`. It writes page PNGs, complete native text, word boxes, and text-block boxes under `data/output/debug/<drawing-name>/`; it performs no semantic extraction or OCR.

## Tests and quality checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check backend tests scripts
cd frontend
pnpm run lint
pnpm run build
```

## Accuracy evaluation and ground truth

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_level1.py
.\.venv\Scripts\python.exe scripts\evaluate_level2.py
.\.venv\Scripts\python.exe scripts\evaluate_level3.py
.\.venv\Scripts\python.exe scripts\evaluate_level4.py
```

To audit the separate 16-PDF review corpus without treating predictions as
labels:

```powershell
.\.venv\Scripts\python.exe scripts\audit_training_corpus.py --debug-overlays
```

Use `--reuse-vision` for a Level-1-only rerun; reuse is allowed only when the
source SHA-256 still matches the preceding corpus manifest. See
`data/training/README.md` for the corpus policy and output layout.

The evaluators read only manually maintained ground truth; they never derive expectations from parser or detector output. Level-3 metrics remain `null` for classes without independently reviewed annotations. Results are written to:

- `data/output/evaluation/level1_results.json`
- `data/output/evaluation/level1_results.csv`
- `data/output/evaluation/level2_results.json`
- `data/output/evaluation/level2_results.csv`
- `data/output/evaluation/level3_results.json`
- `data/output/evaluation/level3_results.csv`
- `data/output/evaluation/level4_results.json`
- `data/output/evaluation/level4_results.csv`

Add expectations by editing the applicable category’s `fields` mapping. Leave a category empty until it has been manually reviewed. Use `expected_null` only for fields manually confirmed to be absent. Accuracy for categories with no entered expectations is reported as `null`, not 100%.

## Current sample results

| Drawing | Pages | Type | Revisions | Notes | BOM | Part list | Service parts | Standards | Raster regions |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 47789413_C_watermarked.pdf | 5 | STANDARD_DRAWING | 5 | 15 | 6 | 2 | 0 | 4 | 0 |
| 47789460_B_watermarked.pdf | 1 | SUPPLIER_DRAWING | 1 | 14 | 0 | 3 | 0 | 7 | 1 |
| 47789660_A_watermarked.pdf | 1 | SUPPLIER_DRAWING | 1 | 6 | 0 | 1 | 8 | 2 | 1 |

The initial manual reference set contains 37 values: 34 Title Block expectations and 3 Supplier Information expectations. All currently match. Revision, Notes, BOM, Part Lists, Service Parts, and Standards do not yet have independently entered field-level ground truth and therefore remain unevaluated.

## Known limitations

See [docs/known_limitations.md](docs/known_limitations.md). In brief: PDF only; native wrapper text is required for semantic extraction; embedded supplier raster content is not OCR-extracted; graphical checkbox state may remain null; and no CAD-model or engineering-correctness validation is performed.

## Validation boundary

Level 2 is automated drawing-review assistance. It does not perform CAD comparison, full graphical reasoning, functional GD&T approval, manufacturability determination, tolerance suitability, dimensional-completeness approval, product-safety approval, or final engineering acceptance. See [docs/level2_known_limitations.md](docs/level2_known_limitations.md).

Level 4 identifies evidence-backed links and broken-link candidates; it does not prove engineering causality, changed geometry, supplier equivalence, SCC meaning, or final drawing correctness. Every result retains source-level provenance and remains subject to authorized engineer review.
