"""Strict, provenance-bearing Level-4 relationship contracts."""

# ruff: noqa: E501 - controlled client-facing wording remains readable.

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.drawing import BoundingBox


class RelationshipModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class SourceLevel(StrEnum):
    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"


class EntityType(StrEnum):
    DRAWING = "DRAWING"
    SHEET = "SHEET"
    TITLE_BLOCK = "TITLE_BLOCK"
    REVISION = "REVISION"
    REVISION_TRIANGLE = "REVISION_TRIANGLE"
    NOTE = "NOTE"
    NOTE_CALLOUT = "NOTE_CALLOUT"
    BOM_ITEM = "BOM_ITEM"
    PART_LIST_ITEM = "PART_LIST_ITEM"
    SERVICE_PART = "SERVICE_PART"
    BALLOON = "BALLOON"
    SCC_SYMBOL = "SCC_SYMBOL"
    DATUM = "DATUM"
    GDT_FRAME = "GDT_FRAME"
    SUPPLIER = "SUPPLIER"
    SUPPLIER_PART = "SUPPLIER_PART"
    STANDARD_REFERENCE = "STANDARD_REFERENCE"
    VISUAL_OBJECT = "VISUAL_OBJECT"


class RelationshipType(StrEnum):
    MATCHES = "MATCHES"
    REFERENCES = "REFERENCES"
    BELONGS_TO = "BELONGS_TO"
    CALLED_OUT_BY = "CALLED_OUT_BY"
    APPLIES_TO = "APPLIES_TO"
    REVISION_OF = "REVISION_OF"
    IDENTIFIES = "IDENTIFIES"
    LINKED_TO = "LINKED_TO"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    MISSING_LINK = "MISSING_LINK"


class RelationshipStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class RelationshipSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReviewPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class RelationshipEvidence(RelationshipModel):
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    source_level: SourceLevel
    source_reference: str
    value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: str | None = None


class EngineeringEntity(RelationshipModel):
    entity_id: str
    entity_type: EntityType
    value: Any = None
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    source_level: SourceLevel
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_reference: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class EngineeringRelationship(RelationshipModel):
    relationship_id: str
    relationship_type: RelationshipType
    source_entity_id: str
    target_entity_id: str | None = None
    status: RelationshipStatus
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[RelationshipEvidence] = Field(default_factory=list)
    explanation: str


class RelationshipResult(RelationshipModel):
    finding_id: str
    relationship_rule_id: str
    name: str
    description: str
    status: RelationshipStatus
    severity: RelationshipSeverity
    priority: ReviewPriority = ReviewPriority.P4
    confidence: float = Field(ge=0.0, le=1.0)
    expected_relationship: str
    actual_relationship: str
    source_entities: list[str] = Field(default_factory=list)
    target_entities: list[str] = Field(default_factory=list)
    evidence: list[RelationshipEvidence] = Field(default_factory=list)
    explanation: str
    recommendation: str
    related_validation_rule_ids: list[str] = Field(default_factory=list)


class IssueCorrelation(RelationshipModel):
    correlation_id: str
    category: str
    title: str
    priority: ReviewPriority
    finding_ids: list[str]
    related_validation_rule_ids: list[str] = Field(default_factory=list)
    explanation: str
    qualifier: str = "Probable relationship; not a definitive root-cause diagnosis."


class RelationshipGraph(RelationshipModel):
    nodes: list[EngineeringEntity] = Field(default_factory=list)
    edges: list[EngineeringRelationship] = Field(default_factory=list)


class RelationshipSummary(RelationshipModel):
    relationships_checked: int = Field(ge=0)
    passed: int = Field(ge=0)
    broken: int = Field(ge=0)
    warnings: int = Field(ge=0)
    manual_review: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    not_evaluated: int = Field(ge=0)
    high_priority_findings: int = Field(ge=0)
    overall_status: str


class RelationshipTiming(RelationshipModel):
    level4_relationship_ms: float = Field(ge=0.0)


class RelationshipReport(RelationshipModel):
    drawing_id: str | None = None
    source_filename: str
    level4_version: str = "1.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    graph: RelationshipGraph
    findings: list[RelationshipResult]
    correlations: list[IssueCorrelation] = Field(default_factory=list)
    summary: RelationshipSummary
    timing: RelationshipTiming
    disclaimer: str = (
        "Relationship intelligence is automated review assistance based on available "
        "Level-1, Level-2, and Level-3 evidence. Final engineering approval remains "
        "the responsibility of the authorized engineer."
    )


class CompleteAnalysisReport(RelationshipModel):
    drawing_id: str
    level1_status: str
    level2_status: str
    level3_status: str
    level4_status: str
    validation_summary: dict[str, Any]
    vision_summary: dict[str, Any]
    relationship_summary: RelationshipSummary
    level1_summary: dict[str, Any]
    top_findings: list[RelationshipResult]
    timing_ms: dict[str, float | None]
    final_system_status: str
    disclaimer: str = "AUTOMATED REVIEW COMPLETE. Engineer review is required; final approval remains human-controlled."
