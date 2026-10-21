# Level-3 known limitations

- The 16-drawing review corpus does not have independently and manually reviewed visual-object ground truth. Its object counts are observations only; precision, recall, F1, IoU, text accuracy, and count accuracy are `null`.
- Traditional-CV candidates can include drawing geometry that resembles annotation symbols. Confidence gates prevent lower-confidence candidates from driving automatic failure, but they still require review.
- Revision triangles without a reliably associated identifier cannot be cross-referenced automatically.
- Balloon detection requires a supported boundary and native numeric text. Common split circles with touching leaders are supported, but parenthesized leaders, unusual compartments, raster-only balloons, and leader-only callouts can still be missed.
- Split-balloon lower-compartment text is preserved as evidence. Quantity comparisons remain review assistance until an authorized reviewer confirms the drawing convention.
- Leader-line feature-endpoint association is reserved for later work; this Level 3 stores a zero/unknown association confidence.
- SCC detection is intentionally inactive until a controlled client symbol example or template is supplied. The system does not guess the SCC shape.
- Datum and GD&T parsing are syntax-oriented. Functional datum choice, tolerance suitability, semantic correctness, and full ASME Y14.5 compliance are not evaluated.
- View labels are native-text-first; complete view hierarchy, direction, coverage, hatching, and drawing-view correctness remain manual.
- Tesseract is the implemented offline OCR provider, but its executable is absent on the current host. OCR-disabled/unavailable operation is non-fatal. PaddleOCR and cloud OCR are not required or used.
- Targeted OCR evidence has lower confidence than native PDF text and remains separate from Club Car wrapper evidence.
- No YOLO or other trained model is included. No client files are uploaded externally.
- Reviewer actions are stored as an audit layer and do not silently rewrite detector output. They are not yet a full user/identity workflow.
- Performance figures are single local runs, not production capacity benchmarks.

The system must not be represented as establishing full drawing correctness, manufacturing readiness, complete dimensional sufficiency, functional GD&T correctness, standards compliance, product safety, or engineering approval.
