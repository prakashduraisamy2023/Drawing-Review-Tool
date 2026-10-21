# Engineering Drawing Intelligence PoC

- Keep extraction evidence-only. Do not infer values that are absent from the PDF.
- Production extractors must be generic and must not contain sample drawing numbers or values.
- Preserve provenance (`page`, `confidence`, and `extraction_method`) for every output field.
- Keep extraction, checklist validation, visual detection, and relationship analysis as separate layers.
- Relationship results are review assistance, never engineering approval or root-cause proof.
