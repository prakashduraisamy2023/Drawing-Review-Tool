# Current Implementation Audit

## Scope

This audit records the repository state before Level-1 completion work. It covers
production source, tests, documentation, frontend code, and the three PDFs in
`data/input`. Generated environments, dependency folders, caches, and compiled
frontend assets are excluded from the source inventory.

## Existing folder structure

```text
backend/
  app/
    extraction/       Native-text, coordinate, classification, and orchestration code
    models/           Evidence-preserving Pydantic drawing models
    pdf/              PDF diagnostic utility
    api_models.py     HTTP upload response model
    drawing_store.py  UUID-scoped PDF and JSON persistence
    main.py           FastAPI application and routes
  requirements*.txt
data/
  input/              Three supplied engineering drawing PDFs
  output/             Prior JSON and debug artifacts
docs/
  pdf_analysis.md     Detailed PDF layout and extraction analysis
frontend/
  src/                React dashboard, PDF.js preview, types, and styles
tests/                Backend, extractor, parser, and API tests
tmp/
  inspect_pdf_layout.py
```

The repository does not yet contain `backend/app/evaluation/`, `scripts/`, or
`tests/ground_truth/`.

## Backend modules

### Current canonical Level-1 path

- `models/drawing.py`: strict Pydantic models for extracted fields, title
  blocks, revisions, notes, BOM items, suppliers, standards, pages, documents,
  and warnings.
- `extraction/drawing_parser.py`: fault-isolated orchestration producing a
  `DrawingDocument`.
- `extraction/title_block.py`: normalized bottom-right Club Car title-block
  extraction for the 17 x 11 and 34 x 22 wrappers.
- `extraction/revision_table.py`: spatial revision-row extraction.
- `extraction/notes.py`: numbered and multiline note extraction with embedded
  standard references.
- `extraction/bom.py`: coordinate-first native table extraction with a cropped
  pdfplumber fallback.
- `extraction/classification.py`: evidence-only standard/supplier/unknown
  classification and native supplier metadata extraction.
- `extraction/supplier.py`: supplier extraction facade.
- `extraction/standards.py`: unique standard references collected from notes.
- `drawing_store.py`: UUID record directories, fixed internal filenames, and
  persisted Pydantic JSON.
- `main.py`: upload, retrieval, subresource, export, and legacy endpoints.

### Legacy path still present

- `schemas.py`, `extraction/pipeline.py`, `extraction/document.py`,
  `extraction/fields.py`, and `extraction/tables.py` implement an earlier flat
  `DrawingExtraction` response.
- `/api/v1/extractions` and `/api/v1/extractions/batch` still use this older
  pipeline.
- `cli.py` also targets the older schema and pipeline.

## Frontend modules

- `App.tsx`: upload and analysis views with Overview, Revisions, Notes, BOM,
  Standards, and Raw JSON tabs.
- `PdfPreview.tsx`: PDF.js canvas rendering, page navigation, zoom, and one
  selected bounding-box overlay.
- `types.ts`: TypeScript mirror of the current `DrawingDocument` contract.
- `styles.css`: responsive engineering-dashboard presentation.
- `vite.config.ts`: development API proxy to the local FastAPI service.

The frontend already displays per-field confidence and can navigate to and
highlight the bounding box for a selected field.

## Existing extractors and behavior

| Extractor | Implemented | Current gap |
|---|---|---|
| Document classification | Explicit supplier and positive standard evidence | Supplier metadata is parsed as part of classification and then parsed again by the supplier facade |
| Title block | Per-page wrapper extraction and conservative normalization | No shared evidence explanation or raw anchor text in the public field model |
| Revision table | Multirow, multiline, release states, page provenance | No explicit confidence rationale |
| Notes | Numbered multiline notes and standard references | No separate warning taxonomy for ambiguous reconstruction |
| BOM | Native coordinate reconstruction and cropped fallback | BOM, outer part list, and service parts are returned in one collection |
| Supplier information | Name, one or many part numbers, marker, imported-CAD statement | Manufacturer mappings are not structured separately; raster supplier region is not represented |
| Standards | Deduplicated note references | Re-runs note extraction rather than consuming shared page context/results |

## Existing API endpoints

- `POST /api/drawings/upload`
- `GET /api/drawings/{id}`
- `GET /api/drawings/{id}/pages`
- `GET /api/drawings/{id}/notes`
- `GET /api/drawings/{id}/bom`
- `GET /api/drawings/{id}/revisions`
- `GET /api/drawings/{id}/export/json`
- legacy `POST /api/v1/extractions`
- legacy `POST /api/v1/extractions/batch`
- `GET /health`

Missing final Level-1 endpoints are `/standards` and `/supplier`. CSV and
summary exports are also absent.

## Existing tests

The test suite covers:

- schema validation and null evidence;
- PDF diagnostics;
- title blocks and multisheet normalization;
- revision rows;
- numbered notes and standard references;
- native, partial-column, service-parts, and supplier wrapper tables;
- classification and supplier metadata;
- parser fault isolation;
- upload validation, persistence, subresources, export, and size limits;
- the older extraction pipeline and API.

Baseline result before Level-1 completion changes: **80 passed, 0 failed**.
The only warning is a Starlette test-client dependency deprecation. The frontend
TypeScript production build succeeds; Vite reports the expected large PDF.js
worker/chunk advisory.

## Sample PDF observations confirmed

| File | Pages | Wrapper | Native text | Images |
|---|---:|---|---|---:|
| `47789413_C_watermarked.pdf` | 5 | 1224 x 792 pt | All pages | 1, 0, 3, 0, 0 |
| `47789460_B_watermarked.pdf` | 1 | 2448 x 1584 pt | Wrapper native; supplier source raster | 3 |
| `47789660_A_watermarked.pdf` | 1 | 1224 x 792 pt | Wrapper native; supplier source raster | 2 |

The findings in `docs/pdf_analysis.md` remain accurate: wrapper anchors and
normalized zones are required; default full-page pdfplumber table detection is
unsafe; internal supplier raster content must not be treated as native text.

## Implemented functionality

- Safe PDF-only upload with extension, signature, structural, password, page,
  size, filename, and path controls.
- UUID-scoped source/result persistence.
- Per-extractor fault isolation and structured warnings.
- Multi-page processing and page-level structured results.
- Explicit standard/supplier/unknown classification.
- Title, revision, notes, combined table, supplier, and standards extraction.
- Native-text coordinate provenance and confidence values.
- JSON persistence and download.
- React upload/analysis dashboard and selected-region PDF highlighting.

## Incomplete functionality

- Final field provenance lacks `raw_text`, `evidence_anchor`, and a computed
  confidence category.
- `DrawingDocument` names/collections do not yet fully match the final contract:
  sheet number, total sheets, drawing date, separate revision/table collections,
  raster regions, and Level-1 summary are incomplete.
- No reusable `PageContext`, template/page-size model, or shared document
  context is passed to extractors.
- BOM, PART_LIST, and SERVICE_PARTS are not separated.
- Supplier-original raster regions are not detected/stored and do not produce
  the required informational warning.
- Confidence values are static per extraction path rather than calculated from
  an explicit evidence score/rationale.
- Ambiguous null fields generally do not generate field-specific warnings.
- No independent manual ground truth or accuracy evaluator exists.
- No error taxonomy, evaluation JSON/CSV, final summary object, performance
  report, architecture report, test report, known-limitations report, or
  completion report exists.
- Frontend lacks Supplier and Extraction Quality tabs, separate table sections,
  extraction detail display, and a Show Extracted Regions toggle.
- Direct refresh of a frontend drawing URL cannot reload the source PDF preview
  because no source-preview endpoint is exposed; the current session preview
  uses the locally uploaded `File`.

## Duplicated code

- Two public data-model systems: `models/drawing.py` and `schemas.py`.
- Two orchestration systems: `DrawingParser` and `DrawingExtractionPipeline`.
- Native word dataclasses, bounding-box unions, unknown-field factories, and
  evidence constructors are repeated across extractors.
- Notes are extracted once directly, again during classification, again through
  the supplier facade, and again by the standards facade.
- PDF files are reopened independently by most stages despite an initial text,
  word, and block inspection pass.

These are architectural debt, but working modules should not be rewritten only
for style. Completion work should consolidate the production path where needed
and preserve tested extractors.

## Broken imports and unused/debug code

- No broken production import was found; baseline tests and frontend build pass.
- `tmp/inspect_pdf_layout.py` is a useful requested diagnostic, not production
  parser code.
- No `TODO` or `FIXME` marker was found in production source during the audit.
- Generated TypeScript build metadata and compiled Vite configuration files are
  present in the frontend tree but do not affect runtime behavior.

## Hardcoded sample-specific values

The supplied drawing numbers, supplier names, and supplier part number occur in
tests and documentation as expected values. They were not found in production
backend or frontend extraction logic. Generic layout markers, table headers,
standard patterns, and document-classification phrases are appropriately
hardcoded as format vocabulary.

## Architectural concerns

1. The initial page text/block extraction is diagnostic only; downstream
   extractors reopen and reread the PDF.
2. The supplier facade wraps the classifier rather than owning a shared,
   independent supplier result.
3. Static confidence constants are reproducible but not sufficiently
   explainable under the final acceptance contract.
4. Combined table output allows service/part-list rows to be presented as BOM.
5. The older API/pipeline remains reachable and creates contract ambiguity.
6. Document classification evidence is an extracted field, but an UNKNOWN
   classification becomes a null `DrawingDocument.document_type`; this is
   evidence-safe but needs explicit documentation.
7. Warning codes and informational versus failure severity are not modeled.

## Current run commands

Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Frontend:

```powershell
cd frontend
pnpm run dev
```

Backend tests and lint:

```powershell
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\ruff.exe check backend tests
```

Frontend validation:

```powershell
cd frontend
pnpm run lint
pnpm run build
```

## Missing work to reach Level-1 acceptance

The minimum completion path is:

1. Extend the canonical models without breaking existing evidence contracts.
2. Add shared page context, table typing/separation, raster region detection,
   warning codes, explainable confidence metadata, and a summary object.
3. Stabilize `DrawingParser` around those additions while retaining extractor
   fault isolation.
4. Add supplier/standards APIs and suitable CSV export.
5. Complete Supplier, Extraction Quality, table separation, extraction details,
   and all-region highlighting in the frontend.
6. Create manual ground truth and an evaluator with JSON/CSV output and error
   taxonomy.
7. Add missing unit, integration, error-path, and three-sample production tests.
8. Measure performance, complete the requested documentation, run clean final
   verification, and issue the factual acceptance report.
