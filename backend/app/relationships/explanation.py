"""Deterministic, non-generative finding wording."""

from backend.app.relationships.models import RelationshipResult


def concise_finding(result: RelationshipResult) -> str:
    return f"{result.name}: {result.actual_relationship}"
