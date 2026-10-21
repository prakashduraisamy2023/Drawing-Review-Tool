from backend.app.extraction.confidence import ConfidenceEvidence, calculate_confidence


def test_confidence_is_deterministic_and_evidence_driven():
    strong = ConfidenceEvidence(
        anchor_found=True,
        expected_region=True,
        format_match=True,
        relative_position=True,
    )
    weak = ConfidenceEvidence(anchor_found=True, ambiguous_parsing=True)

    assert calculate_confidence(strong) == calculate_confidence(strong)
    assert calculate_confidence(strong).score == 0.95
    assert calculate_confidence(strong).category == "HIGH"
    assert calculate_confidence(weak).score == 0.48
    assert calculate_confidence(weak).category == "LOW"
    assert "+anchor_found" in calculate_confidence(strong).reasons
    assert "-ambiguous_parsing" in calculate_confidence(weak).reasons


def test_confidence_category_boundaries_are_stable():
    medium = calculate_confidence(ConfidenceEvidence(anchor_found=True, expected_region=True))
    assert medium.score == 0.77
    assert medium.category == "MEDIUM"
