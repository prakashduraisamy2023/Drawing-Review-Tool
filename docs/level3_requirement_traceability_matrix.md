# Level-3 requirement traceability matrix

| Requirement | Level-2 rule | Level-3 detector/evidence | Before | After | Automatic threshold | Remaining limitation |
|---|---|---|---|---|---:|---|
| Revision triangle relationship | REV-012 | `revision_triangle` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Identifier and detector completeness need reviewed sample ground truth. |
| Note callout relationship | NOTE-012 | `flag_note` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Callout geometry varies; missing calls do not create automatic failure. |
| BOM balloon relationship | BOM-011 | `balloon` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Reliable identifiers can pass; differences are warnings pending recall evidence. |
| Balloon quantity | BOM-012 | `balloon` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Occurrence semantics and referenced-feature quantity remain manual. |
| SCC beside BOM item | BOM-014 | `scc_symbol` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED framework | 0.92 | No controlled SCC symbol reference is available; remains NOT_EVALUATED. |
| Supplier internal raster data | SUP-010 | `supplier_raster_ocr` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED evidence | 0.90 | Current host lacks Tesseract executable; OCR needs review and does not itself validate content. |
| SCC title block to note/BOM | XREF-006 | `scc_symbol` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED framework | 0.92 | No controlled SCC template; spatial semantics remain manual. |
| BOM to balloon | XREF-007 | `balloon` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Same conservative behavior as BOM-011. |
| View label sequence | VIEW-001 | `view_annotation` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.88 | Syntax only; view completeness is excluded. |
| Duplicate view identifier | VIEW-002 | `view_annotation` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.88 | Native reading order may not link every identifier. |
| Section label format | VIEW-003 | `view_annotation` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.88 | Arrow direction and paired cutting-plane geometry are not proven. |
| Detail label format | VIEW-004 | `view_annotation` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.88 | Detail-circle linkage is limited. |
| Local view scale | VIEW-005 | `view_annotation` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED framework | 0.88 | Local-scale classification remains NOT_EVALUATED. |
| Datum identifier | GDT-001 | `datum` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Syntax only; functional datum selection stays manual. |
| Duplicate datum | GDT-002 | `datum` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Detection recall is ungrounded. |
| Datum sequence | GDT-003 | `datum` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Sequence is syntactic, not functional precedence approval. |
| FCF token recognition | GDT-004 | `gdt_frame` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Symbol OCR/token set is deliberately limited. |
| Position tolerance recognition | GDT-005 | `gdt_frame` | NOT_IMPLEMENTED | PARTIALLY_AUTOMATED | 0.90 | Only explicitly recognized position tokens are populated. |

DIM-005, DIM-008, DIM-009, VIEW-007, GDT-006, GDT-007, and GDT-008 remain manual engineering checks. DIM-007, VIEW-008, and complete arrow-direction semantics remain outside the implemented acceptance scope.
