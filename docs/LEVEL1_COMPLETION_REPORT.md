# Engineering Drawing Intelligence PoC
## Level 1 Completion Report

### 1. Executive Summary

The Level-1 PoC is operational end to end for the three supplied Club Car PDF drawings. It validates and stores uploads, analyzes every page, classifies documents from explicit evidence, extracts structured title/revision/note/table/supplier/standards data, detects supplier-original raster regions without OCR, preserves field-level provenance and confidence, renders evidence in the React dashboard, exports JSON/CSV, and evaluates declared expectations against independently maintained ground truth.

Acceptance status: **PASS WITH LIMITATIONS**. All implemented tests and production-path checks pass. The limitation is evidence coverage, not a known failing extractor: only Title Block and Supplier Information currently have manually entered field-level truth. Accuracy for Revision, Notes, BOM, Part Lists, Service Parts, and Standards is therefore not yet independently measured. Supplier raster content also remains intentionally unparsed in Level 1.

### 2. Implemented Capabilities

- PDF extension, MIME, size, signature, password, page-count, and readability validation
- sanitized upload names, opaque UUID persistence, and atomic result files
- 17 × 11 and 34 × 22 page templates plus explicit unknown-layout handling
- native page text, words, blocks, dimensions, image regions, and per-page metadata
- evidence-only STANDARD_DRAWING / SUPPLIER_DRAWING / UNKNOWN classification
- independent per-page title blocks and conservative document normalization
- revision, multiline note, standard-reference, and supplier metadata extraction
- separate BOM, Part List, and Service Parts collections
- manufacturer names and source-to-manufacturer part-number mappings
- supplier raster bounding boxes and informational non-OCR warning
- deterministic HIGH / MEDIUM / LOW confidence categories
- value, page, score, category, method, bounding box, raw text, and anchor provenance
- fault-isolated extraction warnings and a Level-1 processing summary
- focused API resources, JSON export, and flattened evidence CSV export
- PDF.js preview, selected-field highlighting, global region overlays, extraction details, and quality dashboard
- independently maintained ground truth, evaluation metrics, CSV/JSON evaluation output, and error taxonomy

### 3. System Architecture

The system has three boundaries:

1. FastAPI validates/persists a PDF and invokes `DrawingParser`.
2. `DrawingParser` creates page context, runs modular fault-isolated extractors, and assembles the canonical Pydantic `DrawingDocument` plus warnings and `Level1Summary`.
3. React consumes the canonical response and uses PDF.js to render the unchanged uploaded file with coordinate-derived overlays.

Manual-ground-truth evaluation is separate from extraction and never changes parser behavior. Detailed architecture is in `docs/level1_architecture.md`.

### 4. Extraction Pipeline

PDF → document metadata → PageContext → template detection → classification → TitleBlockExtractor → RevisionTableExtractor → NotesExtractor → BOM/PartList/ServiceParts extraction → SupplierInfoExtractor → StandardsExtractor → supplier raster-region detection → DrawingDocument → warnings → JSON/CSV/UI.

Native PyMuPDF evidence is primary. Normalized regions select candidates; explicit anchors and relative positions identify values. pdfplumber is restricted to cropped header-established table areas. Full-page OCR and internal supplier-raster OCR are not used.

### 5. Sample Drawings Tested

- `47789413_C_watermarked.pdf`: five-page standard 17 × 11 wrapper drawing
- `47789460_B_watermarked.pdf`: one-page supplier 34 × 22 wrapper with manufacturer metadata and raster supplier original
- `47789660_A_watermarked.pdf`: one-page supplier 17 × 11 wrapper with supplier metadata, raster supplier original, outer part list, and service-parts table

### 6. Extraction Results

| Drawing | Pages | Type | Accuracy | Warnings | Processing Time |
|---|---:|---|---:|---:|---:|
| 47789413_C_watermarked.pdf | 5 | STANDARD_DRAWING | 100% (15/15 entered expectations) | 0 | 7.594 s |
| 47789460_B_watermarked.pdf | 1 | SUPPLIER_DRAWING | 100% (10/10 entered expectations) | 1 informational | 0.948 s |
| 47789660_A_watermarked.pdf | 1 | SUPPLIER_DRAWING | 100% (12/12 entered expectations) | 1 informational | 0.465 s |

All 37 entered expectations were correct and non-null: zero incorrect, zero missing, and zero declared false extractions. The two notices are `SUPPLIER_RASTER_CONTENT_NOT_EXTRACTED` and accurately describe intentionally unparsed supplier raster content.

### 7. Category Accuracy

- Title Block: **100%** (34/34; coverage 100%)
- Supplier Information: **100%** (3/3; coverage 100%)
- Revision: **not evaluated** (no manual field expectations yet)
- Notes: **not evaluated**
- BOM: **not evaluated**
- Part Lists: **not evaluated**
- Service Parts: **not evaluated**
- Standards: **not evaluated**

Automated extractor tests assert sample revision counts/descriptions, note counts/multiline wording, table types/rows, supplier mappings, and standards. Those tests confirm deterministic behavior but are not presented as independent manual accuracy.

### 8. Tests

Backend: **92 passed / 0 failed**. Ruff: passed. One upstream Starlette/httpx deprecation warning remains.

Frontend: ESLint passed; TypeScript and Vite production build passed. Vite reports a non-fatal large-chunk warning driven by PDF.js.

Integration: passed for all three sample PDFs through upload, persistence, structured response, retrieval, and JSON/CSV export. Interactive browser verification passed for file upload, all analysis tabs, PDF rendering, field navigation, one selected highlight, 52 global overlays on the tested page, supplier raster messaging, and zero browser console errors.

Clean Uvicorn startup also passed; `/health` returned `{"status":"ok","ocr_enabled":false,"ocr_available":false}`.

### 9. Known Limitations

- PDF only
- embedded supplier raster content not OCR-extracted
- no CAD-model validation
- no engineering correctness validation
- no Level-2 rule engine yet
- unsupported wrapper sizes remain UNKNOWN
- graphical critical-component state may remain null without reliable evidence
- tables without recognizable native headers may remain unextracted
- six extraction categories still need independently entered manual ground truth
- repeated PDF/notes passes make the five-page sample slower than the single-page samples

### 10. PoC Acceptance Status

**PASS WITH LIMITATIONS**

Every functional Level-1 acceptance item is implemented and verified: upload; all sample processing; multi-page support; title, revision, note, typed table, supplier, and standards extraction; provenance; confidence; PDF highlighting; warning display; JSON/CSV export; evaluation; clean startup; passing tests/build/lint; no sample-specific production rules; and no Level-2 logic.

The qualification is required because the initial manual truth cannot substantiate the recommended accuracy target for Revision, Notes, BOM, Part Lists, Service Parts, or Standards. These categories are reported as not evaluated rather than assigned a fabricated score. The supplier-raster non-OCR behavior is an explicit Level-1 design limitation, not a failure.

### 11. Recommended Level-2 Next Steps

1. Expand independently reviewed ground truth for every extraction category before adding engineering rules.
2. Build a separate review workflow for correcting ground truth and adjudicating ambiguous PDFs.
3. Optimize stable extractors to consume shared PageContext and reduce repeated PDF/notes passes.
4. Evaluate targeted OCR for explicitly bounded supplier-original raster regions as a separate, opt-in capability.
5. Define Level-2 engineering validation requirements, authoritative standards data, traceability, and human-approval controls independently of Level-1 extraction.

No Level-2 validation has been implemented by this work.
