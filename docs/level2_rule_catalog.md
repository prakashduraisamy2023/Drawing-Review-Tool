# Level-2 rule catalog

Rule-set version 1.0.0. Stable IDs are independent of drawing numbers. Severity can be overridden only by controlled repository configuration.

| Rule ID | Requirement | Category | Automation type | Severity | Automation status | Applicability | Version |
|---|---|---|---|---|---|---|---|
| TB-001 | Drawing number present | Title Block | RULE_BASED | HIGH | AUTOMATED | always | 1.0.0 |
| TB-002 | Drawing number consistent across sheets | Title Block | RULE_BASED | HIGH | AUTOMATED | multi_page | 1.0.0 |
| TB-003 | Revision present | Title Block | RULE_BASED | HIGH | AUTOMATED | always | 1.0.0 |
| TB-004 | Revision consistent across sheets | Title Block | RULE_BASED | HIGH | AUTOMATED | multi_page | 1.0.0 |
| TB-005 | Part name consistent where required | Title Block | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | multi_page | 1.0.0 |
| TB-006 | Units present | Title Block | RULE_BASED | HIGH | AUTOMATED | always | 1.0.0 |
| TB-007 | Units consistent across sheets | Title Block | RULE_BASED | HIGH | AUTOMATED | multi_page | 1.0.0 |
| TB-008 | Sheet number valid | Title Block | RULE_BASED | HIGH | AUTOMATED | always | 1.0.0 |
| TB-009 | Sheet sequence | Title Block | RULE_BASED | HIGH | AUTOMATED | multi_page | 1.0.0 |
| TB-010 | Total sheet count matches PDF page count | Title Block | RULE_BASED | MEDIUM | AUTOMATED | always | 1.0.0 |
| TB-011 | Weight present for applicable supplier part | Title Block | RULE_BASED | MEDIUM | AUTOMATED | supplier | 1.0.0 |
| TB-012 | Scale present | Title Block | RULE_BASED | MEDIUM | AUTOMATED | always | 1.0.0 |
| TB-013 | Drawing size present | Title Block | RULE_BASED | MEDIUM | AUTOMATED | always | 1.0.0 |
| TB-014 | Part number format | Title Block | RULE_BASED | LOW | PARTIALLY_AUTOMATED | always | 1.0.0 |
| REV-001 | ECN present on revision record | Revision | RULE_BASED | HIGH | AUTOMATED | always | 1.0.0 |
| REV-002 | Revision date present | Revision | RULE_BASED | MEDIUM | AUTOMATED | always | 1.0.0 |
| REV-003 | Changed by present | Revision | RULE_BASED | MEDIUM | AUTOMATED | always | 1.0.0 |
| REV-004 | Approved by present | Revision | RULE_BASED | HIGH | AUTOMATED | always | 1.0.0 |
| REV-005 | Revision description present | Revision | RULE_BASED | HIGH | AUTOMATED | always | 1.0.0 |
| REV-006 | Initial release text recognized | Revision | TEXT_RULE | MEDIUM | AUTOMATED | always | 1.0.0 |
| REV-007 | Production release text recognized | Revision | TEXT_RULE | INFO | AUTOMATED | always | 1.0.0 |
| REV-008 | Not released text recognized | Revision | TEXT_RULE | INFO | AUTOMATED | always | 1.0.0 |
| REV-009 | See sheet 1 for revisions resolves | Revision | CROSS_REFERENCE | HIGH | AUTOMATED | multi_page | 1.0.0 |
| REV-010 | Revision sequence | Revision | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | always | 1.0.0 |
| REV-011 | Revision table versus title revision | Revision | CROSS_REFERENCE | HIGH | PARTIALLY_AUTOMATED | always | 1.0.0 |
| REV-012 | Revision triangle check | Revision | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| NOTE-001 | Notes section detected | Notes | RULE_BASED | MEDIUM | AUTOMATED | notes | 1.0.0 |
| NOTE-002 | Note number sequence | Notes | RULE_BASED | MEDIUM | AUTOMATED | notes | 1.0.0 |
| NOTE-003 | Duplicate note number | Notes | RULE_BASED | HIGH | AUTOMATED | notes | 1.0.0 |
| NOTE-004 | Empty note | Notes | RULE_BASED | HIGH | AUTOMATED | notes | 1.0.0 |
| NOTE-005 | Configured technical spelling | Notes | RULE_BASED | LOW | PARTIALLY_AUTOMATED | notes | 1.0.0 |
| NOTE-006 | Standard note presence | Notes | RULE_BASED | MEDIUM | AUTOMATED | notes | 1.0.0 |
| NOTE-007 | PES references detected | Notes | RULE_BASED | INFO | AUTOMATED | notes | 1.0.0 |
| NOTE-008 | Obsolete specification | Notes | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | notes | 1.0.0 |
| NOTE-009 | Note deleted format | Notes | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | notes | 1.0.0 |
| NOTE-010 | Part number in note | Notes | RULE_BASED | LOW | PARTIALLY_AUTOMATED | notes | 1.0.0 |
| NOTE-011 | Torque unit format | Notes | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | notes | 1.0.0 |
| NOTE-012 | Note callout relationship | Notes | CROSS_REFERENCE | MEDIUM | NOT_IMPLEMENTED | notes | 1.0.0 |
| STD-001 | ASME reference detected | Standards | RULE_BASED | INFO | AUTOMATED | standards | 1.0.0 |
| STD-002 | Standard identifier format | Standards | RULE_BASED | MEDIUM | AUTOMATED | standards | 1.0.0 |
| STD-003 | Duplicate standard references | Standards | RULE_BASED | LOW | AUTOMATED | standards | 1.0.0 |
| STD-004 | Required standard reference | Standards | RULE_BASED | MEDIUM | AUTOMATED | standards | 1.0.0 |
| STD-005 | Unknown standard reference | Standards | RULE_BASED | LOW | PARTIALLY_AUTOMATED | standards | 1.0.0 |
| BOM-001 | BOM item number present | BOM | RULE_BASED | HIGH | AUTOMATED | bom | 1.0.0 |
| BOM-002 | BOM quantity present | BOM | RULE_BASED | HIGH | AUTOMATED | bom | 1.0.0 |
| BOM-003 | BOM part number present | BOM | RULE_BASED | HIGH | AUTOMATED | bom | 1.0.0 |
| BOM-004 | BOM description present | BOM | RULE_BASED | MEDIUM | AUTOMATED | bom | 1.0.0 |
| BOM-005 | BOM item sequence | BOM | RULE_BASED | MEDIUM | AUTOMATED | bom | 1.0.0 |
| BOM-006 | Duplicate BOM item number | BOM | RULE_BASED | HIGH | AUTOMATED | bom | 1.0.0 |
| BOM-007 | Duplicate BOM part number | BOM | RULE_BASED | LOW | AUTOMATED | bom | 1.0.0 |
| BOM-008 | Positive BOM quantity | BOM | RULE_BASED | HIGH | AUTOMATED | bom | 1.0.0 |
| BOM-009 | BOM part number format | BOM | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | bom | 1.0.0 |
| BOM-010 | BOM description length | BOM | RULE_BASED | LOW | PARTIALLY_AUTOMATED | bom | 1.0.0 |
| BOM-011 | BOM balloon relationship | BOM | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | bom | 1.0.0 |
| BOM-012 | BOM balloon quantity | BOM | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | bom | 1.0.0 |
| BOM-013 | Obsolete part | BOM | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | bom | 1.0.0 |
| BOM-014 | SCC symbol beside BOM item | BOM | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | bom | 1.0.0 |
| PL-001 | Part-list part number present | Part List | RULE_BASED | HIGH | AUTOMATED | part_list | 1.0.0 |
| PL-002 | Part-list description present | Part List | RULE_BASED | MEDIUM | AUTOMATED | part_list | 1.0.0 |
| PL-003 | Duplicate part-list part number | Part List | RULE_BASED | LOW | AUTOMATED | part_list | 1.0.0 |
| PL-004 | Part-list part-number format | Part List | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | part_list | 1.0.0 |
| SP-001 | Service part number present | Service Parts | RULE_BASED | HIGH | AUTOMATED | service_parts | 1.0.0 |
| SP-002 | Service part description present | Service Parts | RULE_BASED | MEDIUM | AUTOMATED | service_parts | 1.0.0 |
| SP-003 | Duplicate service part number | Service Parts | RULE_BASED | LOW | AUTOMATED | service_parts | 1.0.0 |
| SP-004 | Service part-number format | Service Parts | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | service_parts | 1.0.0 |
| SUP-001 | Supplier drawing identified | Supplier | RULE_BASED | HIGH | AUTOMATED | supplier | 1.0.0 |
| SUP-002 | Supplier drawing banner | Supplier | RULE_BASED | HIGH | AUTOMATED | supplier | 1.0.0 |
| SUP-003 | Supplier drawing not to scale | Supplier | RULE_BASED | MEDIUM | AUTOMATED | supplier | 1.0.0 |
| SUP-004 | Supplier name or manufacturer | Supplier | RULE_BASED | MEDIUM | AUTOMATED | supplier | 1.0.0 |
| SUP-005 | Supplier part number | Supplier | RULE_BASED | MEDIUM | AUTOMATED | supplier | 1.0.0 |
| SUP-006 | Required supplier notes | Supplier | RULE_BASED | MEDIUM | PARTIALLY_AUTOMATED | supplier | 1.0.0 |
| SUP-007 | Supplier wrapper units consistency | Supplier | RULE_BASED | MEDIUM | AUTOMATED | supplier | 1.0.0 |
| SUP-008 | Supplier weight present | Supplier | RULE_BASED | MEDIUM | AUTOMATED | supplier | 1.0.0 |
| SUP-009 | Supplier drawing raster region | Supplier | RULE_BASED | INFO | AUTOMATED | supplier | 1.0.0 |
| SUP-010 | Supplier internal data validation | Supplier | RULE_BASED | MEDIUM | NOT_IMPLEMENTED | supplier | 1.0.0 |
| XREF-001 | Title revision to revision table | Cross Reference | CROSS_REFERENCE | HIGH | PARTIALLY_AUTOMATED | always | 1.0.0 |
| XREF-002 | Sheet number to PDF page count | Cross Reference | CROSS_REFERENCE | MEDIUM | AUTOMATED | always | 1.0.0 |
| XREF-003 | Supplier classification to supplier label | Cross Reference | CROSS_REFERENCE | HIGH | AUTOMATED | supplier | 1.0.0 |
| XREF-004 | Standard reference to notes | Cross Reference | CROSS_REFERENCE | MEDIUM | AUTOMATED | standards | 1.0.0 |
| XREF-005 | Part number to part list | Cross Reference | CROSS_REFERENCE | MEDIUM | PARTIALLY_AUTOMATED | always | 1.0.0 |
| XREF-006 | SCC title block to note or BOM | Cross Reference | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| XREF-007 | BOM to balloon | Cross Reference | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| DIM-001 | Metric leading zero | Dimensions | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| DIM-002 | Metric trailing zero | Dimensions | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| DIM-003 | Decimal place limit | Dimensions | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| DIM-004 | Reference dimension parentheses | Dimensions | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| DIM-005 | Tolerance present | Dimensions | ENGINEERING_REVIEW | MEDIUM | MANUAL | always | 1.0.0 |
| DIM-006 | Dimension units to title units | Dimensions | CROSS_REFERENCE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| DIM-007 | Hidden-line dimension | Dimensions | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| DIM-008 | Redundant dimension | Dimensions | ENGINEERING_REVIEW | MEDIUM | MANUAL | always | 1.0.0 |
| DIM-009 | Complete dimensioning | Dimensions | ENGINEERING_REVIEW | MEDIUM | MANUAL | always | 1.0.0 |
| VIEW-001 | View label sequence | Views | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| VIEW-002 | Duplicate view identifier | Views | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| VIEW-003 | Section label pair format | Views | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| VIEW-004 | Detail label format | Views | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| VIEW-005 | Local scale detected | Views | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| VIEW-006 | Isometric view label | Views | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| VIEW-007 | Required view completeness | Views | ENGINEERING_REVIEW | MEDIUM | MANUAL | always | 1.0.0 |
| VIEW-008 | Hatching | Views | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| VIEW-009 | Arrow direction | Views | VISION_ASSISTED | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| GDT-001 | Datum identifier detected | GD&T | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| GDT-002 | Datum duplicate identifier | GD&T | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| GDT-003 | Datum sequence | GD&T | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| GDT-004 | Feature control frame token recognized | GD&T | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| GDT-005 | Position tolerance recognized | GD&T | TEXT_RULE | MEDIUM | NOT_IMPLEMENTED | always | 1.0.0 |
| GDT-006 | GD&T functional correctness | GD&T | ENGINEERING_REVIEW | MEDIUM | MANUAL | always | 1.0.0 |
| GDT-007 | Datum functional correctness | GD&T | ENGINEERING_REVIEW | MEDIUM | MANUAL | always | 1.0.0 |
| GDT-008 | ASME Y14.5 full compliance | GD&T | ENGINEERING_REVIEW | MEDIUM | MANUAL | always | 1.0.0 |

