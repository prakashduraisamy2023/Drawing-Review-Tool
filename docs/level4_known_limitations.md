# Level 4 known limitations

- Level 4 relates extracted/detected evidence; it does not validate design intent,
  geometry, manufacturability, tolerance suitability, safety, or CAD equivalence.
- A missing visual detection is not proof that a drawing object is absent. BOM,
  note, and revision missing links therefore default to warning or not evaluated.
- Quantity validation cannot count physical part occurrences reliably from the
  present 2D detector output and remains manual review.
- SCC semantics require a controlled symbol catalog. None is supplied by default.
- Supplier equivalence and internal/supplier part-number mapping require approved
  master data; the default mapping configuration is empty.
- Revision descriptions do not prove that geometry changed. Change traceability is
  manual unless an explicit reliable callout is present.
- GD&T checks use recognized text references only and do not assess functional
  datum schemes or tolerance correctness.
- Correlations identify related issue families; they do not establish causality.
- The current visual layer uses traditional computer vision and optional local
  Tesseract, not a trained domain detector. Low-confidence results remain review
  evidence.
- Level 4 has no independently reviewed ground-truth cases yet. Accuracy,
  precision, and recall are intentionally reported as null.
- Final acceptance always belongs to an authorized engineer. The application does
  not provide an approval action or approval wording.
