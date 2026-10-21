# PDF Structure and Extraction Analysis

## Scope and method

This analysis covers the three PDFs currently in `data/input`. It is an extraction study only. It does not validate dimensions, materials, approvals, compliance, or engineering correctness, and it does not infer values that are not explicitly present.

The files were inspected with:

- PyMuPDF page metadata, native text, words, text blocks, and bounding boxes;
- visual rendering of every page;
- pdfplumber table detection as a diagnostic; and
- PyMuPDF image-object bounding boxes to distinguish native page content from embedded raster supplier drawings.

No OCR was used. Every page has usable native text. Some subregions, however, are raster images and therefore have no native text of their own; those limitations are called out below.

PyMuPDF coordinates in this document are PDF points with origin at the top-left of the page. Normalized coordinates are expressed as fractions of page width and height.

## Corpus summary

| PDF | Pages | Page size | Native text | Page diagnostics |
|---|---:|---|---|---|
| `47789413_C_watermarked.pdf` | 5 | 1224 x 792 pt (17 x 11 in), landscape | Available on all pages | P1: 371 words / 38 blocks; P2: 526 / 40; P3: 210 / 27; P4: 265 / 78; P5: 327 / 83 |
| `47789460_B_watermarked.pdf` | 1 | 2448 x 1584 pt (34 x 22 in), landscape | Available for the Club Car wrapper; supplier-original drawing is raster | 585 words / 46 text blocks / 3 images |
| `47789660_A_watermarked.pdf` | 1 | 1224 x 792 pt (17 x 11 in), landscape | Available for the Club Car wrapper; supplier-original drawing is raster | 397 words / 44 text blocks / 2 images |

The native-text character counts are much larger than the visible text because some engineering fonts produce extra spacing and control characters. Word and block counts are better indicators of usable native content.

## Recurring Club Car layout

### 17 x 11 inch sheets

The five standard pages and `47789660_A_watermarked.pdf` use the same Club Car frame geometry:

- Release stamp: approximately `(513, 0, 711, 14)`.
- Main drawing area: approximately `(45, 27, 1180, 644)`.
- Legal notice: approximately `(855, 643, 1188, 679)`.
- Title block: approximately `(856, 679, 1188, 767)`, normalized to roughly `x=0.70-0.97`, `y=0.86-0.97`.
- Revision block: approximately `(54, 732, 510, 765)`, with the revision row itself at roughly `(56, 732, 400, 751)` and its headers at `(65, 753, 405, 764)`.

The title block is composed of many small, separately positioned text blocks. Labels and values are often not adjacent in normal reading order. Examples include `DRAWN`, `MODELED`, `DATE`, `PART NAME`, `SIZE DWG NO`, `REV`, `WEIGHT`, `SCALE`, `UNITS`, and `SHEET`.

### 34 x 22 inch sheet

`47789460_B_watermarked.pdf` uses a larger frame:

- Release stamp: `(1125, 0, 1323, 14)`.
- Supplier-original raster region: `(82, 54, 1847, 1301)`, normalized to approximately `x=0.033-0.754`, `y=0.034-0.822`.
- Club Car notes: approximately `(1886, 209, 2383, 784)`.
- Club Car drawing/view area: approximately the right-hand region below the notes and above the legal/title area.
- Club Car legal and critical-item text: approximately `x=1933-2401`, `y=1336-1434`.
- Club Car title block: approximately `x=1933-2401`, `y=1435-1555`.
- Revision block: approximately `(74, 1517, 600, 1549)`.

The larger sheet is not simply a uniformly scaled copy of the 17 x 11 layout. Extraction should use normalized zones plus anchor labels rather than fixed absolute coordinates alone.

## Per-file findings

## `47789413_C_watermarked.pdf`

### General structure

This is a five-sheet standard Club Car drawing. Every page is 1224 x 792 points and has usable native text. The release stamp and Club Car footer regions repeat at stable coordinates across all five pages.

### Page 1

- Notes region: upper-left, with the `NOTE:` label at `(69, 40, 99, 64)` and the principal notes block at approximately `(69, 61, 433, 272)`.
- BOM/part list: upper-right. Header block `QTY ITEM PART NO. DESCRIPTION` is at `(837, 27, 1064, 43)`. Two row groups occupy approximately `x=844-1146`, `y=38-133`.
- Drawing/view region: central page area. It contains an isometric part view, a clip assembled view, callouts, and local view scale text. One raster view image occupies `(589, 292, 928, 498)`; surrounding annotations remain native text.
- Revision block: bottom-left. The revision row is a single native block containing the ECN, description, date, changed-by, and approved-by values.
- Title block: bottom-right. Values are native but split across label and value blocks.

### Page 2

- Notes region: left side, approximately `x=55-449`, `y=35-545`, split across multiple text blocks.
- Part-number table: upper-right, with header at `(921, 28, 1055, 44)` and two part rows immediately below.
- Drawing/view region: center and right, containing orthographic and isometric views and several view-specific scales.
- The revision block says to see sheet 1 for revisions; the same ECN and approval identities are repeated.

### Page 3

- Texture specification: top-left at approximately `(56, 36, 413, 55)`.
- Drawing/view region: three large rendered views. These are raster image objects at approximately `(114, 132, 417, 639)`, `(518, 161, 577, 564)`, and `(765, 161, 900, 564)`.
- No page-specific BOM or numbered notes block.
- Standard title and revision blocks repeat at the bottom.

### Page 4

- Drawing/view region occupies nearly the entire main frame and contains datum setup, callouts, dimensions, and a side view.
- Most annotations are native text in many small coordinate blocks; this explains the high block count.
- No BOM or notes section.
- Standard title and revision blocks repeat at the bottom.

### Page 5

- Drawing/view region contains dimensions, detail views, section A-A, and local view scales.
- No BOM or notes section.
- Standard title and revision blocks repeat at the bottom.

### Extraction implications

The BOM on page 1 is native text, but pdfplumber's default table detection merges the outer drawing frame with the internal table. A cropped table region or word-coordinate row reconstruction is required. View labels and local scales must be excluded when extracting the overall drawing scale from the title block.

## `47789460_B_watermarked.pdf`

### General structure

This is a one-page supplier drawing in a 34 x 22 inch Club Car wrapper. Native text is available for the Club Car overlay, but the original supplier drawing on the left is a single raster image object at `(82, 54, 1847, 1301)`.

### Regions

- Outer part list: top-right. Drawing number/revision and three Club Car part rows are native text in blocks between approximately `x=1911-2392`, `y=13-100`.
- Club Car notes: right side, approximately `(1886, 209, 2383, 784)`. The notes explicitly contain manufacturer information, manufacturer part-number mappings, standards, and packaging requirements.
- Supplier-original drawing: left side raster image. It visually contains the supplier's views, dimensions, internal notes, BOM, and supplier title/revision tables. None of that internal image text is available through native PDF text extraction.
- Club Car view region: right-middle. Two raster isometric images occupy approximately `(1947, 861, 2105, 1155)` and `(2170, 890, 2338, 1138)`, with native callouts around them.
- Supplier drawing labels: `SUPPLIER DRAWING` at approximately `(2045, 1261, 2269, 1301)` and `SUPPLIER DRAWING NOT TO SCALE` at `(850, 1311, 1176, 1343)`.
- Critical-item statement: native text at approximately `(1933, 1336, 2401, 1369)`.
- Revision block: bottom-left, including the ECN/release row and column headers.
- Club Car title block: bottom-right. Its text is native but tightly packed and split among overlapping blocks.

### Extraction implications

The outer Club Car fields and notes are natively extractable. The supplier-original BOM and title block are image-only and cannot be extracted from native text. The outer three-row part list must not be assumed to be the supplier BOM. The manufacturer part-number note contains three mappings, so collapsing it to a single supplier part number would lose explicit structure.

## `47789660_A_watermarked.pdf`

### General structure

This is a one-page supplier drawing in the 17 x 11 Club Car wrapper. Native text is available for the Club Car overlay. The supplier-original drawing on the left is a raster image object at `(45, 27, 847, 595)`.

### Regions

- Supplier-original drawing: left and center raster region. It visually contains supplier views, a supplier BOM, supplier revision information, and a supplier title block. Those internal values are not present as native text.
- Outer part list: upper-right, header at `(921, 28, 1055, 44)` and one native part row immediately below.
- Club Car notes: upper-right, approximately `x=865-1199`, `y=64-296`. These notes explicitly identify the supplier and supplier P/N.
- Club Car drawing/view region: right-middle. A raster isometric image occupies `(897, 415, 1129, 493)` with a native callout.
- Service-parts table: lower-middle, approximately `x=595-829`, `y=587-731`. Its header and rows are native text, though the last rows overlap vertically with footer/title content in normal reading order.
- Supplier drawing labels: native text around `x=386-1149`, `y=587-634`, and in the title area.
- Revision block and title block: same geometry as the standard 17 x 11 sheets.

### Extraction implications

The outer notes, part row, service-parts table, revision row, and title block are natively extractable with spatial parsing. The supplier BOM visible inside the left raster region is not natively extractable. The native service-parts table is a separate entity and must not be labeled as the supplier BOM.

## Standard drawing versus supplier drawing

| Characteristic | Standard drawing | Supplier drawing |
|---|---|---|
| Club Car frame and title block | Present | Present as an outer wrapper |
| Main engineering content | Native/vector plus some rasterized views | Supplier-original drawing embedded as a large raster image |
| `SUPPLIER DRAWING` label | Absent | Explicitly present |
| Notes | Native Club Car notes | Native Club Car notes plus possible image-only supplier notes |
| BOM | Native text on the standard drawing page | Supplier BOM is inside the raster image; an outer part/service list may also exist |
| Drawing number/revision | Club Car title block | Club Car wrapper title block plus possible image-only supplier identifiers |
| Critical indicator | Empty/ambiguous title-block field | One sample has an explicit native critical-item statement |
| Extraction risk | Interleaved text order and view/title scale ambiguity | All standard risks plus two overlapping document systems and image-only supplier content |

The supplier classification can be supported by the explicit `SUPPLIER DRAWING` text. The absence of that text should not by itself be converted to a definitive false value without a documented classification rule.

## Fields reliably available from native text

The following evidence is explicitly present and generally recoverable without OCR:

- Filename, from file metadata.
- Page count and page size, from PDF metadata.
- Release stamp/date on every page.
- Notes in the Club Car wrapper.
- Referenced engineering standards in those native notes.
- Explicit supplier-drawing statements.
- Explicit supplier name and supplier P/N in `47789660_A_watermarked.pdf`.
- Explicit manufacturer name and manufacturer P/N mappings in `47789460_B_watermarked.pdf`; these should retain their original labels rather than be silently renamed.
- Explicit critical-item statement in `47789460_B_watermarked.pdf`.
- Part numbers and descriptions in the outer top-right part lists.
- Service-part numbers and descriptions in the native service-parts table of `47789660_A_watermarked.pdf`.
- Page-1 BOM text in `47789413_C_watermarked.pdf`, provided extraction is constrained to the correct coordinate region.

## Fields that require spatial or layout parsing

These values are native, but ordinary linear text extraction does not preserve their relationships reliably:

- Drawing number, revision, and drawing size in the Club Car title block.
- Part name in the title block.
- Drawn by, modeled by, and drawing date.
- Overall drawing scale, units, weight, sheet number, and total sheets.
- ECN, revision description, revision date, changed by, and approved by in the revision row.
- BOM columns and row associations.
- Note boundaries and numbering where blocks are split.
- Part-number/description row associations in top-right and service-parts lists.
- Distinguishing the overall title-block scale from local view scales.
- Distinguishing the Club Car wrapper from the embedded supplier-original drawing.
- Associating a local view label, local scale, or callout with its drawing view.

Anchor labels plus relative position should be preferred over fixed coordinates. Absolute coordinates differ between the 17 x 11 and 34 x 22 templates, while normalized regions and labels remain more stable.

## Fields not yet reliably extractable

The following should remain null or structurally unresolved until a separate, evidence-preserving method is established:

- Any BOM, revision, title-block, notes, dimensions, materials, or standards that exist only inside the raster supplier-original regions.
- A complete supplier BOM for either supplier drawing.
- A single supplier part number for `47789460_B_watermarked.pdf`; the PDF explicitly provides three manufacturer P/N mappings rather than one value.
- A false critical-component value based only on an empty title-block label, checkbox, triangle, or graphic symbol.
- A definitive standard/non-supplier document type based only on the absence of supplier wording.
- The meaning or state of graphical checkboxes and characteristic symbols when no explicit text statement is present.
- Complete internal supplier revision history and approval identities from the raster supplier title blocks.
- Complete line-item semantics when a row spans both native wrapper content and image-only supplier content.

Targeted OCR of the supplier raster regions may be evaluated later because native text is unavailable inside those regions. No OCR was run for this analysis, and OCR results would need lower confidence and exact region/page provenance.

## pdfplumber table observations

Default `find_tables()` is not reliable on these drawings because the outer drawing border and title-block lines are interpreted as one large table. Examples:

- On pages 1-4 of `47789413_C_watermarked.pdf`, the detected table often spans almost the full page and merges notes, views, title blocks, and the small BOM.
- On `47789460_B_watermarked.pdf`, the largest detected table spans nearly the complete sheet.
- On `47789660_A_watermarked.pdf`, a smaller service-parts table is detected, but cell text is clipped or merged because of scale and nearby footer content.

For future extraction, pdfplumber should be applied only after locating a table anchor and cropping to its bounding region. Word-coordinate reconstruction is likely more reliable for the small native part lists. pdfplumber cannot recover text from the embedded raster supplier drawings without OCR.

## Recommended extraction order based on this analysis

1. Read page metadata and native text with PyMuPDF.
2. Detect the Club Car template and page size.
3. Locate title and revision blocks using anchor labels and normalized zones.
4. Locate notes, part lists, BOMs, and service-parts tables by their headers and crop bounds.
5. Detect supplier drawings from explicit labels and record raster supplier-region bounding boxes.
6. Extract only native evidence in Level 1; leave image-only supplier fields null unless a separately authorized regional OCR fallback is used.
7. Preserve page, method, confidence, and region provenance for every extracted result.

## Diagnostic script

The temporary diagnostic script is `tmp/inspect_pdf_layout.py`. From the repository root, run:

```powershell
.\.venv\Scripts\python.exe .\tmp\inspect_pdf_layout.py .\data\input
```

For every PDF and page it prints page size, rotation, native-text availability, character count, usable-character count, word count, block count, image count, and every text block with absolute and normalized bounding boxes.
