"""Deterministic, explainable confidence scoring for Level-1 evidence."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.models.drawing import ConfidenceCategory


@dataclass(frozen=True)
class ConfidenceEvidence:
    anchor_found: bool = False
    expected_region: bool = False
    format_match: bool = False
    relative_position: bool = False
    repeated_consistent: bool = False
    competing_candidates: bool = False
    reconstructed_across_blocks: bool = False
    unusual_position: bool = False
    weak_anchor: bool = False
    ambiguous_parsing: bool = False


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    category: ConfidenceCategory
    reasons: tuple[str, ...]


POSITIVE_WEIGHTS = {
    "anchor_found": 0.16,
    "expected_region": 0.11,
    "format_match": 0.09,
    "relative_position": 0.09,
    "repeated_consistent": 0.05,
}
NEGATIVE_WEIGHTS = {
    "competing_candidates": 0.16,
    "reconstructed_across_blocks": 0.06,
    "unusual_position": 0.10,
    "weak_anchor": 0.12,
    "ambiguous_parsing": 0.18,
}
BASE_SCORE = 0.50


def confidence_category(score: float) -> ConfidenceCategory:
    if score >= 0.90:
        return ConfidenceCategory.HIGH
    if score >= 0.75:
        return ConfidenceCategory.MEDIUM
    return ConfidenceCategory.LOW


def calculate_confidence(evidence: ConfidenceEvidence) -> ConfidenceResult:
    """Score declared evidence features; no random or drawing-specific inputs."""
    score = BASE_SCORE
    reasons: list[str] = []
    for name, weight in POSITIVE_WEIGHTS.items():
        if getattr(evidence, name):
            score += weight
            reasons.append(f"+{name}")
    for name, weight in NEGATIVE_WEIGHTS.items():
        if getattr(evidence, name):
            score -= weight
            reasons.append(f"-{name}")
    score = round(max(0.01, min(0.99, score)), 2)
    return ConfidenceResult(score, confidence_category(score), tuple(reasons))
