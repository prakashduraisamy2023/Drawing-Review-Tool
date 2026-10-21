"""Controlled, stable Level-2 validation rule registry."""

# ruff: noqa: E501 - requirement text remains readable and traceable as complete sentences.

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.app.validation.models import RuleMetadata
from backend.app.validation.rules.base import ValidationRule
from backend.app.validation.rules.declarative import DeclarativeRule
from backend.app.validation.severity import AutomationType, ValidationSeverity

VISION_EVALUATORS = {
    "REV-012": "visual_revision",
    "NOTE-012": "visual_note_callouts",
    "BOM-011": "visual_balloons",
    "BOM-012": "visual_balloon_quantity",
    "BOM-014": "visual_scc",
    "SUP-010": "visual_supplier_ocr",
    "XREF-006": "visual_scc",
    "XREF-007": "visual_balloons",
    "VIEW-001": "visual_views",
    "VIEW-002": "visual_views",
    "VIEW-003": "visual_views",
    "VIEW-004": "visual_views",
    "VIEW-005": "visual_views",
    "GDT-001": "visual_datums",
    "GDT-002": "visual_datums",
    "GDT-003": "visual_datums",
    "GDT-004": "visual_gdt",
    "GDT-005": "visual_gdt",
}


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, ValidationRule] = {}

    def register(self, rule: ValidationRule) -> None:
        rule_id = rule.metadata.rule_id
        if rule_id in self._rules:
            raise ValueError(f"Duplicate validation rule ID: {rule_id}")
        self._rules[rule_id] = rule

    def get(self, rule_id: str) -> ValidationRule:
        return self._rules[rule_id]

    def all(self) -> list[ValidationRule]:
        return list(self._rules.values())

    def metadata(self) -> list[RuleMetadata]:
        return [rule.metadata for rule in self.all()]

    def __iter__(self) -> Iterable[ValidationRule]:
        return iter(self._rules.values())


def _spec(
    rule_id: str,
    name: str,
    category: str,
    evaluator: str,
    *,
    severity: str = "MEDIUM",
    automation_type: str = "RULE_BASED",
    applicability: str = "always",
    automation_status: str = "AUTOMATED",
    parameters: dict[str, Any] | None = None,
    source_requirement: str | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "name": name,
        "category": category,
        "evaluator": evaluator,
        "severity": severity,
        "automation_type": automation_type,
        "applicability": applicability,
        "automation_status": automation_status,
        "parameters": parameters or {},
        "source_requirement": source_requirement or name,
    }


RULE_SPECS: list[dict[str, Any]] = [
    _spec(
        "TB-001",
        "Drawing number present",
        "Title Block",
        "presence",
        severity="HIGH",
        parameters={"field": "drawing_number"},
    ),
    _spec(
        "TB-002",
        "Drawing number consistent across sheets",
        "Title Block",
        "consistency",
        severity="HIGH",
        applicability="multi_page",
        parameters={"field": "drawing_number"},
    ),
    _spec(
        "TB-003",
        "Revision present",
        "Title Block",
        "presence",
        severity="HIGH",
        parameters={"field": "revision"},
    ),
    _spec(
        "TB-004",
        "Revision consistent across sheets",
        "Title Block",
        "consistency",
        severity="HIGH",
        applicability="multi_page",
        parameters={"field": "revision"},
    ),
    _spec(
        "TB-005",
        "Part name consistent where required",
        "Title Block",
        "consistency",
        severity="MEDIUM",
        applicability="multi_page",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={"field": "part_name", "conflict_status": "MANUAL_REVIEW"},
    ),
    _spec(
        "TB-006",
        "Units present",
        "Title Block",
        "presence",
        severity="HIGH",
        parameters={"field": "units"},
    ),
    _spec(
        "TB-007",
        "Units consistent across sheets",
        "Title Block",
        "consistency",
        severity="HIGH",
        applicability="multi_page",
        parameters={"field": "units"},
    ),
    _spec("TB-008", "Sheet number valid", "Title Block", "sheet_bounds", severity="HIGH"),
    _spec(
        "TB-009",
        "Sheet sequence",
        "Title Block",
        "sheet_sequence",
        severity="HIGH",
        applicability="multi_page",
    ),
    _spec(
        "TB-010",
        "Total sheet count matches PDF page count",
        "Title Block",
        "sheet_count",
        severity="MEDIUM",
    ),
    _spec(
        "TB-011",
        "Weight present for applicable supplier part",
        "Title Block",
        "presence",
        severity="MEDIUM",
        applicability="supplier",
        parameters={"field": "weight"},
    ),
    _spec("TB-012", "Scale present", "Title Block", "presence", parameters={"field": "scale"}),
    _spec(
        "TB-013",
        "Drawing size present",
        "Title Block",
        "presence",
        parameters={"field": "drawing_size"},
    ),
    _spec(
        "TB-014",
        "Part number format",
        "Title Block",
        "part_pattern",
        severity="LOW",
        automation_status="PARTIALLY_AUTOMATED",
    ),
    _spec(
        "REV-001",
        "ECN present on revision record",
        "Revision",
        "revision_field",
        severity="HIGH",
        parameters={"field": "ecn"},
    ),
    _spec(
        "REV-002",
        "Revision date present",
        "Revision",
        "revision_field",
        parameters={"field": "revision_date"},
    ),
    _spec(
        "REV-003",
        "Changed by present",
        "Revision",
        "revision_field",
        parameters={"field": "changed_by"},
    ),
    _spec(
        "REV-004",
        "Approved by present",
        "Revision",
        "revision_field",
        severity="HIGH",
        parameters={"field": "approved_by"},
    ),
    _spec(
        "REV-005",
        "Revision description present",
        "Revision",
        "revision_field",
        severity="HIGH",
        parameters={"field": "revision_description"},
    ),
    _spec(
        "REV-006",
        "Initial release text recognized",
        "Revision",
        "revision_phrase",
        automation_type="TEXT_RULE",
        parameters={"phrase": "INITIAL RELEASE"},
    ),
    _spec(
        "REV-007",
        "Production release text recognized",
        "Revision",
        "revision_phrase",
        severity="INFO",
        automation_type="TEXT_RULE",
        parameters={"phrase": "PRODUCTION RELEASE"},
    ),
    _spec(
        "REV-008",
        "Not released text recognized",
        "Revision",
        "revision_phrase",
        severity="INFO",
        automation_type="TEXT_RULE",
        parameters={"phrase": "NOT RELEASED"},
    ),
    _spec(
        "REV-009",
        "See sheet 1 for revisions resolves",
        "Revision",
        "see_sheet1",
        severity="HIGH",
        automation_type="CROSS_REFERENCE",
        applicability="multi_page",
    ),
    _spec(
        "REV-010",
        "Revision sequence",
        "Revision",
        "revision_sequence",
        automation_status="PARTIALLY_AUTOMATED",
    ),
    _spec(
        "REV-011",
        "Revision table versus title revision",
        "Revision",
        "revision_xref",
        severity="HIGH",
        automation_type="CROSS_REFERENCE",
        automation_status="PARTIALLY_AUTOMATED",
    ),
    _spec(
        "REV-012",
        "Revision triangle check",
        "Revision",
        "framework",
        automation_type="VISION_ASSISTED",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "Revision triangle visual detection is not available in Level 1."},
    ),
    _spec("NOTE-001", "Notes section detected", "Notes", "note_detected", applicability="notes"),
    _spec("NOTE-002", "Note number sequence", "Notes", "note_sequence", applicability="notes"),
    _spec(
        "NOTE-003",
        "Duplicate note number",
        "Notes",
        "note_duplicates",
        severity="HIGH",
        applicability="notes",
    ),
    _spec("NOTE-004", "Empty note", "Notes", "empty_note", severity="HIGH", applicability="notes"),
    _spec(
        "NOTE-005",
        "Configured technical spelling",
        "Notes",
        "framework",
        severity="LOW",
        applicability="notes",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={
            "status": "NOT_EVALUATED",
            "reason": "No authoritative technical spelling dictionary and whitelist are configured.",
        },
    ),
    _spec("NOTE-006", "Standard note presence", "Notes", "required_phrases", applicability="notes"),
    _spec(
        "NOTE-007",
        "PES references detected",
        "Notes",
        "token_detected",
        severity="INFO",
        applicability="notes",
        parameters={"kind": "pes"},
    ),
    _spec(
        "NOTE-008",
        "Obsolete specification",
        "Notes",
        "standard_master",
        severity="MEDIUM",
        applicability="notes",
        automation_status="PARTIALLY_AUTOMATED",
    ),
    _spec(
        "NOTE-009",
        "Note deleted format",
        "Notes",
        "framework",
        applicability="notes",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={
            "status": "MANUAL_REVIEW",
            "reason": "A numbering gap alone does not prove that NOTE DELETED wording is required.",
        },
    ),
    _spec(
        "NOTE-010",
        "Part number in note",
        "Notes",
        "framework",
        severity="LOW",
        applicability="notes",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={
            "status": "NOT_EVALUATED",
            "reason": "No configured note class establishes where part numbers are prohibited.",
        },
    ),
    _spec(
        "NOTE-011",
        "Torque unit format",
        "Notes",
        "framework",
        severity="MEDIUM",
        applicability="notes",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={
            "status": "NOT_EVALUATED",
            "reason": "Reliable torque-token classification is not represented in Level-1 data.",
        },
    ),
    _spec(
        "NOTE-012",
        "Note callout relationship",
        "Notes",
        "framework",
        automation_type="CROSS_REFERENCE",
        applicability="notes",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "Note callout extraction is not available in Level 1."},
    ),
    _spec(
        "STD-001",
        "ASME reference detected",
        "Standards",
        "token_detected",
        severity="INFO",
        applicability="standards",
        parameters={"kind": "asme"},
    ),
    _spec(
        "STD-002",
        "Standard identifier format",
        "Standards",
        "standard_syntax",
        applicability="standards",
    ),
    _spec(
        "STD-003",
        "Duplicate standard references",
        "Standards",
        "standard_duplicates",
        severity="LOW",
        applicability="standards",
    ),
    _spec(
        "STD-004",
        "Required standard reference",
        "Standards",
        "required_phrases",
        applicability="standards",
    ),
    _spec(
        "STD-005",
        "Unknown standard reference",
        "Standards",
        "standard_master",
        severity="LOW",
        applicability="standards",
        automation_status="PARTIALLY_AUTOMATED",
    ),
    _spec(
        "BOM-001",
        "BOM item number present",
        "BOM",
        "table_field",
        severity="HIGH",
        applicability="bom",
        parameters={"family": "bom", "field": "item_no"},
    ),
    _spec(
        "BOM-002",
        "BOM quantity present",
        "BOM",
        "table_field",
        severity="HIGH",
        applicability="bom",
        parameters={"family": "bom", "field": "quantity"},
    ),
    _spec(
        "BOM-003",
        "BOM part number present",
        "BOM",
        "table_field",
        severity="HIGH",
        applicability="bom",
        parameters={"family": "bom", "field": "part_number"},
    ),
    _spec(
        "BOM-004",
        "BOM description present",
        "BOM",
        "table_field",
        applicability="bom",
        parameters={"family": "bom", "field": "description"},
    ),
    _spec(
        "BOM-005",
        "BOM item sequence",
        "BOM",
        "table_sequence",
        applicability="bom",
        parameters={"family": "bom"},
    ),
    _spec(
        "BOM-006",
        "Duplicate BOM item number",
        "BOM",
        "table_duplicates",
        severity="HIGH",
        applicability="bom",
        parameters={"family": "bom", "field": "item_no"},
    ),
    _spec(
        "BOM-007",
        "Duplicate BOM part number",
        "BOM",
        "table_duplicates",
        severity="LOW",
        applicability="bom",
        parameters={"family": "bom", "field": "part_number", "duplicate_status": "WARNING"},
    ),
    _spec(
        "BOM-008",
        "Positive BOM quantity",
        "BOM",
        "positive_quantity",
        severity="HIGH",
        applicability="bom",
        parameters={"family": "bom"},
    ),
    _spec(
        "BOM-009",
        "BOM part number format",
        "BOM",
        "part_pattern",
        applicability="bom",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={"family": "bom"},
    ),
    _spec(
        "BOM-010",
        "BOM description length",
        "BOM",
        "description_length",
        severity="LOW",
        applicability="bom",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={"family": "bom"},
    ),
    _spec(
        "BOM-011",
        "BOM balloon relationship",
        "BOM",
        "framework",
        automation_type="VISION_ASSISTED",
        applicability="bom",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "BOM balloon extraction is not available in Level 1."},
    ),
    _spec(
        "BOM-012",
        "BOM balloon quantity",
        "BOM",
        "framework",
        automation_type="VISION_ASSISTED",
        applicability="bom",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "Balloon and geometry extraction are not available in Level 1."},
    ),
    _spec(
        "BOM-013",
        "Obsolete part",
        "BOM",
        "framework",
        applicability="bom",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={"reason": "No authoritative part master is configured."},
    ),
    _spec(
        "BOM-014",
        "SCC symbol beside BOM item",
        "BOM",
        "framework",
        automation_type="VISION_ASSISTED",
        applicability="bom",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "SCC symbol extraction is not available in Level 1."},
    ),
    _spec(
        "PL-001",
        "Part-list part number present",
        "Part List",
        "table_field",
        severity="HIGH",
        applicability="part_list",
        parameters={"family": "part_list", "field": "part_number"},
    ),
    _spec(
        "PL-002",
        "Part-list description present",
        "Part List",
        "table_field",
        applicability="part_list",
        parameters={"family": "part_list", "field": "description"},
    ),
    _spec(
        "PL-003",
        "Duplicate part-list part number",
        "Part List",
        "table_duplicates",
        severity="LOW",
        applicability="part_list",
        parameters={"family": "part_list", "field": "part_number", "duplicate_status": "WARNING"},
    ),
    _spec(
        "PL-004",
        "Part-list part-number format",
        "Part List",
        "part_pattern",
        applicability="part_list",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={"family": "part_list"},
    ),
    _spec(
        "SP-001",
        "Service part number present",
        "Service Parts",
        "table_field",
        severity="HIGH",
        applicability="service_parts",
        parameters={"family": "service_parts", "field": "part_number"},
    ),
    _spec(
        "SP-002",
        "Service part description present",
        "Service Parts",
        "table_field",
        applicability="service_parts",
        parameters={"family": "service_parts", "field": "description"},
    ),
    _spec(
        "SP-003",
        "Duplicate service part number",
        "Service Parts",
        "table_duplicates",
        severity="LOW",
        applicability="service_parts",
        parameters={
            "family": "service_parts",
            "field": "part_number",
            "duplicate_status": "WARNING",
        },
    ),
    _spec(
        "SP-004",
        "Service part-number format",
        "Service Parts",
        "part_pattern",
        applicability="service_parts",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={"family": "service_parts"},
    ),
    _spec(
        "SUP-001",
        "Supplier drawing identified",
        "Supplier",
        "supplier_marker",
        severity="HIGH",
        applicability="supplier",
    ),
    _spec(
        "SUP-002",
        "Supplier drawing banner",
        "Supplier",
        "supplier_phrase",
        severity="HIGH",
        applicability="supplier",
        parameters={"phrase": "SUPPLIER DRAWING"},
    ),
    _spec(
        "SUP-003",
        "Supplier drawing not to scale",
        "Supplier",
        "supplier_phrase",
        applicability="supplier",
        parameters={"phrase": "SUPPLIER DRAWING NOT TO SCALE"},
    ),
    _spec(
        "SUP-004",
        "Supplier name or manufacturer",
        "Supplier",
        "supplier_identity",
        applicability="supplier",
    ),
    _spec("SUP-005", "Supplier part number", "Supplier", "supplier_part", applicability="supplier"),
    _spec(
        "SUP-006",
        "Required supplier notes",
        "Supplier",
        "required_phrases",
        applicability="supplier",
        automation_status="PARTIALLY_AUTOMATED",
    ),
    _spec(
        "SUP-007",
        "Supplier wrapper units consistency",
        "Supplier",
        "consistency",
        applicability="supplier",
        parameters={"field": "units"},
    ),
    _spec(
        "SUP-008",
        "Supplier weight present",
        "Supplier",
        "presence",
        applicability="supplier",
        parameters={"field": "weight"},
    ),
    _spec(
        "SUP-009",
        "Supplier drawing raster region",
        "Supplier",
        "supplier_raster",
        severity="INFO",
        applicability="supplier",
    ),
    _spec(
        "SUP-010",
        "Supplier internal data validation",
        "Supplier",
        "framework",
        applicability="supplier",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "Supplier-original raster content is not extracted in Level 1."},
    ),
    _spec(
        "XREF-001",
        "Title revision to revision table",
        "Cross Reference",
        "revision_xref",
        severity="HIGH",
        automation_type="CROSS_REFERENCE",
        automation_status="PARTIALLY_AUTOMATED",
    ),
    _spec(
        "XREF-002",
        "Sheet number to PDF page count",
        "Cross Reference",
        "sheet_count",
        automation_type="CROSS_REFERENCE",
    ),
    _spec(
        "XREF-003",
        "Supplier classification to supplier label",
        "Cross Reference",
        "xref_supplier",
        severity="HIGH",
        automation_type="CROSS_REFERENCE",
        applicability="supplier",
    ),
    _spec(
        "XREF-004",
        "Standard reference to notes",
        "Cross Reference",
        "xref_standards_notes",
        automation_type="CROSS_REFERENCE",
        applicability="standards",
    ),
    _spec(
        "XREF-005",
        "Part number to part list",
        "Cross Reference",
        "framework",
        automation_type="CROSS_REFERENCE",
        automation_status="PARTIALLY_AUTOMATED",
        parameters={
            "status": "MANUAL_REVIEW",
            "reason": "Part-number relationship semantics are not globally established.",
        },
    ),
    _spec(
        "XREF-006",
        "SCC title block to note or BOM",
        "Cross Reference",
        "framework",
        automation_type="VISION_ASSISTED",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "SCC symbol semantics are unavailable in Level 1."},
    ),
    _spec(
        "XREF-007",
        "BOM to balloon",
        "Cross Reference",
        "framework",
        automation_type="VISION_ASSISTED",
        automation_status="NOT_IMPLEMENTED",
        parameters={"reason": "BOM balloon extraction is unavailable in Level 1."},
    ),
]


def _framework_specs(
    prefix: str,
    category: str,
    items: list[tuple[str, str, str, str]],
) -> list[dict[str, Any]]:
    return [
        _spec(
            f"{prefix}-{index:03d}",
            name,
            category,
            "framework",
            automation_type=automation_type,
            automation_status="MANUAL" if status == "MANUAL_REVIEW" else "NOT_IMPLEMENTED",
            parameters={"status": status, "reason": reason},
        )
        for index, (name, status, reason, automation_type) in enumerate(items, start=1)
    ]


RULE_SPECS.extend(
    _framework_specs(
        "DIM",
        "Dimensions",
        [
            (
                "Metric leading zero",
                "NOT_EVALUATED",
                "Reliable dimension-token inventory is not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Metric trailing zero",
                "NOT_EVALUATED",
                "Reliable dimension-token inventory is not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Decimal place limit",
                "NOT_EVALUATED",
                "Reliable dimension-token inventory is not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Reference dimension parentheses",
                "NOT_EVALUATED",
                "Reference-dimension classification is unavailable in Level 1.",
                "TEXT_RULE",
            ),
            (
                "Tolerance present",
                "MANUAL_REVIEW",
                "Dimension semantics cannot distinguish every reference, basic, or tolerance-bearing dimension.",
                "ENGINEERING_REVIEW",
            ),
            (
                "Dimension units to title units",
                "NOT_EVALUATED",
                "Reliable dimension-token units are unavailable in Level 1.",
                "CROSS_REFERENCE",
            ),
            (
                "Hidden-line dimension",
                "NOT_EVALUATED",
                "Hidden-line geometry extraction is unavailable in Level 1.",
                "VISION_ASSISTED",
            ),
            (
                "Redundant dimension",
                "MANUAL_REVIEW",
                "Redundancy requires geometry and design-intent reasoning.",
                "ENGINEERING_REVIEW",
            ),
            (
                "Complete dimensioning",
                "MANUAL_REVIEW",
                "Dimensional completeness requires geometry and design intent.",
                "ENGINEERING_REVIEW",
            ),
        ],
    )
)
RULE_SPECS.extend(
    _framework_specs(
        "VIEW",
        "Views",
        [
            (
                "View label sequence",
                "NOT_EVALUATED",
                "A reliable view-label inventory is not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Duplicate view identifier",
                "NOT_EVALUATED",
                "A reliable view-label inventory is not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Section label pair format",
                "NOT_EVALUATED",
                "Section-label relationships are not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Detail label format",
                "NOT_EVALUATED",
                "Detail-label relationships are not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Local scale detected",
                "NOT_EVALUATED",
                "Local view scales are intentionally excluded from title-scale extraction.",
                "TEXT_RULE",
            ),
            (
                "Isometric view label",
                "NOT_EVALUATED",
                "Template-specific view-label requirements are not configured.",
                "TEXT_RULE",
            ),
            (
                "Required view completeness",
                "MANUAL_REVIEW",
                "No exact template-specific view requirement is supplied.",
                "ENGINEERING_REVIEW",
            ),
            (
                "Hatching",
                "NOT_EVALUATED",
                "Visual hatching analysis is unavailable in Level 1.",
                "VISION_ASSISTED",
            ),
            (
                "Arrow direction",
                "NOT_EVALUATED",
                "Visual arrow-object detection is unavailable in Level 1.",
                "VISION_ASSISTED",
            ),
        ],
    )
)
RULE_SPECS.extend(
    _framework_specs(
        "GDT",
        "GD&T",
        [
            (
                "Datum identifier detected",
                "NOT_EVALUATED",
                "Reliable datum-token extraction is unavailable in Level 1.",
                "TEXT_RULE",
            ),
            (
                "Datum duplicate identifier",
                "NOT_EVALUATED",
                "Reliable datum-token extraction is unavailable in Level 1.",
                "TEXT_RULE",
            ),
            (
                "Datum sequence",
                "NOT_EVALUATED",
                "Reliable datum-token extraction is unavailable in Level 1.",
                "TEXT_RULE",
            ),
            (
                "Feature control frame token recognized",
                "NOT_EVALUATED",
                "Feature-control-frame tokens are not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "Position tolerance recognized",
                "NOT_EVALUATED",
                "Position-tolerance tokens are not represented in Level-1 data.",
                "TEXT_RULE",
            ),
            (
                "GD&T functional correctness",
                "MANUAL_REVIEW",
                "Functional GD&T correctness requires engineering judgment.",
                "ENGINEERING_REVIEW",
            ),
            (
                "Datum functional correctness",
                "MANUAL_REVIEW",
                "Functional datum selection requires engineering judgment.",
                "ENGINEERING_REVIEW",
            ),
            (
                "ASME Y14.5 full compliance",
                "MANUAL_REVIEW",
                "Full standards compliance cannot be established by syntax checks.",
                "ENGINEERING_REVIEW",
            ),
        ],
    )
)


def build_default_registry(configuration: dict[str, Any]) -> RuleRegistry:
    registry = RuleRegistry()
    config_rules = configuration.get("rules", {})
    for spec in RULE_SPECS:
        override = config_rules.get(spec["rule_id"], {})
        if override.get("enabled", True) is False:
            continue
        metadata = RuleMetadata(
            rule_id=spec["rule_id"],
            name=spec["name"],
            category=spec["category"],
            description=override.get("description", spec["name"]),
            source_requirement=spec["source_requirement"],
            automation_type=AutomationType(spec["automation_type"]),
            severity=ValidationSeverity(str(override.get("severity", spec["severity"])).upper()),
            applicability=override.get("applicability", spec["applicability"]),
            version=str(override.get("version", configuration.get("rule_set_version", "1.0.0"))),
            automation_status=(
                "PARTIALLY_AUTOMATED"
                if spec["rule_id"] in VISION_EVALUATORS
                else spec["automation_status"]
            ),
            dependencies=list(override.get("dependencies", []))
            + (["level3_visual_evidence"] if spec["rule_id"] in VISION_EVALUATORS else []),
        )
        evaluator = VISION_EVALUATORS.get(spec["rule_id"], spec["evaluator"])
        registry.register(DeclarativeRule(metadata, evaluator, spec["parameters"]))
    return registry
