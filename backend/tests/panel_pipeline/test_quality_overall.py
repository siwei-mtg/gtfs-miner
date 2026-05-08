"""Quality overall score + letter grade (Spec §5.1 G)."""
from __future__ import annotations

import pytest

from app.services.panel_pipeline.quality import compute_overall


def test_overall_perfect_data():
    """All dq_* indicate perfect data → score 100, grade A+."""
    dq = {
        "dq_validator_errors": 0,
        "dq_validator_warnings": 0,
        "dq_field_completeness": 100.0,
        "dq_coord_quality": 100.0,
        "dq_route_type_completeness": 100.0,
        "dq_freshness": 0,
    }
    score, grade = compute_overall(dq)
    assert score == pytest.approx(100.0, abs=0.5)
    assert grade == "A+"


def test_overall_terrible_data():
    """All dq_* indicate disaster → score near 0, grade F."""
    dq = {
        "dq_validator_errors": 200,
        "dq_validator_warnings": 100,
        "dq_field_completeness": 0.0,
        "dq_coord_quality": 0.0,
        "dq_route_type_completeness": 0.0,
        "dq_freshness": 1000,
    }
    score, grade = compute_overall(dq)
    assert score < 30
    assert grade == "F"


def test_overall_grade_bands():
    """Edge cases at each grade band boundary."""
    bands = [
        (95.0, "A+"), (90.0, "A+"),
        (89.0, "A"),  (85.0, "A"),
        (84.0, "A-"), (80.0, "A-"),
        (79.0, "B+"), (75.0, "B+"),
        (74.0, "B"),  (70.0, "B"),
        (69.0, "B-"), (65.0, "B-"),
        (64.0, "C+"), (60.0, "C+"),
        (59.0, "C"),  (55.0, "C"),
        (54.0, "C-"), (50.0, "C-"),
        (49.0, "D"),  (40.0, "D"),
        (39.0, "F"),  (0.0, "F"),
    ]
    from app.services.panel_pipeline.quality import _score_to_grade
    for score, expected_grade in bands:
        assert _score_to_grade(score) == expected_grade, \
            f"score={score} expected={expected_grade} got={_score_to_grade(score)}"


def test_overall_handles_none_components():
    """If validator unavailable (errors/warnings=None), reweight remaining components."""
    dq = {
        "dq_validator_errors": None,
        "dq_validator_warnings": None,
        "dq_field_completeness": 100.0,
        "dq_coord_quality": 100.0,
        "dq_route_type_completeness": 100.0,
        "dq_freshness": 0,
    }
    score, grade = compute_overall(dq)
    # 0.25 + 0.10 = 0.35 weight removed; remaining 0.65 reweighted to 1.0
    # All remaining components are perfect → score = 100
    assert score == pytest.approx(100.0, abs=0.5)
    assert grade == "A+"


def test_overall_freshness_penalty():
    """1000-day-old feed should significantly drop score."""
    dq = {
        "dq_validator_errors": 0,
        "dq_validator_warnings": 0,
        "dq_field_completeness": 100.0,
        "dq_coord_quality": 100.0,
        "dq_route_type_completeness": 100.0,
        "dq_freshness": 1000,
    }
    score, _grade = compute_overall(dq)
    # freshness_score = max(0, 100 - 1000*0.3) = 0
    # score = 0.25*100 + 0.20*100 + 0.15*100 + 0.15*100 + 0.15*0 + 0.10*100
    #       = 25 + 20 + 15 + 15 + 0 + 10 = 85
    assert score == pytest.approx(85.0, abs=0.5)
