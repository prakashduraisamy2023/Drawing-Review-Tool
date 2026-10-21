"""Level-2 validation enums."""

from enum import StrEnum


class ValidationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ValidationSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AutomationType(StrEnum):
    RULE_BASED = "RULE_BASED"
    CROSS_REFERENCE = "CROSS_REFERENCE"
    LAYOUT_RULE = "LAYOUT_RULE"
    TEXT_RULE = "TEXT_RULE"
    VISION_ASSISTED = "VISION_ASSISTED"
    ENGINEERING_REVIEW = "ENGINEERING_REVIEW"


class OverallStatus(StrEnum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAIL = "FAIL"
