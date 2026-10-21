# Level 4 relationship catalog

The 12 rules below are production-generic. “Automatic” means deterministic when
the required evidence is available; it does not mean final engineering approval.

| Rule | Relationship | Evidence used | Conservative outcome when evidence is insufficient |
|---|---|---|---|
| REL-BOM-001 | BOM item to detected balloon | L1 BOM rows, L3 balloon text | Warning or not evaluated |
| REL-BOM-002 | Balloon to BOM item (orphan check) | L3 balloon text, L1 BOM rows | Warning or not applicable |
| REL-BOM-003 | BOM quantity to occurrence evidence | L1 quantity, L3 balloons | Manual review; quantity is not inferred |
| REL-REV-001 | Revision row to revision triangle | L1 revision values, L3 triangle text | Warning or not evaluated |
| REL-REV-002 | Revision row to described change | L1 revision description and explicit callout evidence | Manual review |
| REL-NOTE-001 | Numbered note to flag-note callout | L1 note number, L3 callout text | Warning or not evaluated |
| REL-SCC-001 | SCC symbol to controlled semantics | L3 SCC object, configured semantics | Not evaluated/manual review |
| REL-GDT-001 | GD&T frame reference to datum | L3 recognized frame/datum text | Fail only for reliable explicit missing reference |
| REL-GDT-002 | Duplicate or unused datum review | L3 datum and frame references | Warning/manual review |
| REL-SUP-001 | Supplier identity to supplier evidence | L1 supplier fields, bounded L3 raster OCR | Manual review/not evaluated |
| REL-PART-001 | Internal to supplier part mapping | L1 part values, authoritative configured mapping | Manual review until mapping exists |
| REL-DOC-001 | Cross-sheet document consistency | Existing L2 title/revision/sheet consistency evidence | Mirrors evidence-backed L2 status |

## Matching policy

Identifiers are compared after whitespace and punctuation normalization; the raw
evidence is retained. Matching never creates an absent identifier. Automatic
confidence is capped by the weakest participating evidence. Unrecognized visual
text does not establish a negative relationship.

## Review priority

P1 is reserved for critical/high-confidence failures, P2 for other high-impact
actionable or unavailable checks, P3 for warnings/manual review, and P4 for pass,
not applicable, and informational results. Priority is triage guidance only.

