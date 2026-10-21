# Known Level-1 limitations

- Input is PDF only. Native CAD, model interrogation, and CAD-to-drawing comparison are out of scope.
- The semantic pipeline depends on native wrapper text. A page with no usable native text is reported with `E09 MISSING_NATIVE_TEXT`; full-page OCR is not performed.
- Embedded supplier-original raster content is detected and bounded but not OCR-extracted. Supplier drawings therefore include the informational `SUPPLIER_RASTER_CONTENT_NOT_EXTRACTED` notice when applicable.
- Supplier-original title blocks inside raster images are not parsed. Only explicit Club Car wrapper text is extracted.
- Template detection currently recognizes 17 × 11 and 34 × 22 Club Car wrappers. Other sizes remain `UNKNOWN` and may need new generic template support.
- Title-block extraction assumes recognizable English labels and a lower-right Club Car wrapper region. Unknown or ambiguous values remain null.
- Graphical checkbox/fill state cannot always be established from text. `critical_component` remains null unless reliable explicit positive or negative evidence is present.
- Document-level multi-sheet metadata is normalized only when values are identical or confidently resolvable. Per-page values remain available when sheet numbers or part-level values differ.
- pdfplumber is limited to cropped, header-established candidate areas. Tables without recognizable headings may remain unextracted.
- Table row reconstruction is geometric and may require tuning for unseen layouts, wrapped cells, or interleaved drawing annotations. Missing quantities and item numbers remain null.
- Confidence measures extraction evidence only. It does not express engineering correctness, compliance, release status validity, or design approval.
- The initial ground-truth set covers 37 explicit reference values in Title Block and Supplier Information. Revision, Notes, BOM, Part Lists, Service Parts, and Standards are present in the schema but have no manually entered field-level expectations yet; their evaluation accuracy is therefore null.
- PDF.js contributes a large production bundle/worker. Vite reports a chunk-size warning, but the build succeeds and the PoC remains functional.
- The test stack emits one upstream Starlette deprecation warning about its current httpx compatibility layer.
- Persistence is local filesystem storage suitable for a PoC. Authentication, multi-user authorization, retention policies, malware scanning, and distributed storage are not implemented.
- No engineering compliance validation, ASME/GD&T correctness validation, SCC validation, BOM approval, revision correctness decision, or Level-2 rule engine is implemented.
