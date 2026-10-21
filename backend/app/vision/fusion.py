"""Explainable multi-evidence confidence fusion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceSignal:
    name: str
    present: bool
    weight: float
    explanation: str


def fuse_confidence(
    base_confidence: float, signals: list[EvidenceSignal]
) -> tuple[float, list[str]]:
    """Add bounded, declared signal weights and return an audit explanation."""
    score = base_confidence
    explanations = [f"shape/base={base_confidence:.3f}"]
    for signal in signals:
        if signal.present:
            score += signal.weight
            explanations.append(f"{signal.name}=+{signal.weight:.3f}: {signal.explanation}")
        else:
            explanations.append(f"{signal.name}=absent: {signal.explanation}")
    return min(0.99, max(0.0, score)), explanations
