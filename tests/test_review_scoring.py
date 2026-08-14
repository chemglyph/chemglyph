"""Tests for the blind-review scoring logic in benchmarks/score_review.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "benchmarks" / "score_review.py"

_PAIR_KEY = {
    "pair_001": {
        "molecule": "benzoic-acid",
        "style": "acs",
        "a_engine": "chemglyph",
        "b_engine": "rdkit",
        "scored": True,
    },
    "pair_002": {
        "molecule": "benzoic-acid",
        "style": "modern",
        "a_engine": "rdkit",
        "b_engine": "chemglyph",
        "scored": True,
    },
    "pair_003": {
        "molecule": "caffeine",
        "style": "acs",
        "a_engine": "chemglyph",
        "b_engine": "rdkit",
        "scored": True,
    },
    "pair_004": {
        "molecule": "ferrocene",
        "style": "acs",
        "a_engine": "rdkit",
        "b_engine": "chemglyph",
        "scored": False,
    },
}


def _load_module():
    spec = importlib.util.spec_from_file_location("score_review", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["score_review"] = module
    spec.loader.exec_module(module)
    return module


def _grader(rate: float) -> dict:
    return {"rate": rate, "per_style": {"acs": {"rate": rate}, "modern": {"rate": rate}}}


def test_score_grader_counts_picks_and_ties() -> None:
    score_review = _load_module()
    answers = {"pair_001": "A", "pair_002": "B", "pair_003": "tie"}
    score = score_review.score_grader(answers, _PAIR_KEY)
    assert score["scored_pairs"] == 3
    assert score["picked"] == pytest.approx(2.5)
    assert score["rate"] == pytest.approx(2.5 / 3)
    assert score["per_style"]["acs"]["rate"] == pytest.approx(1.5 / 2)
    assert score["per_style"]["modern"]["rate"] == pytest.approx(1.0)


def test_score_grader_neither_counts_zero_but_stays_in_denominator() -> None:
    score_review = _load_module()
    answers = {"pair_001": "neither", "pair_002": "B", "pair_003": "A"}
    score = score_review.score_grader(answers, _PAIR_KEY)
    assert score["scored_pairs"] == 3
    assert score["missing"] == 0
    assert score["rate"] == pytest.approx(2 / 3)


def test_score_grader_missing_answers_count_zero() -> None:
    score_review = _load_module()
    score = score_review.score_grader({"pair_001": "A"}, _PAIR_KEY)
    assert score["missing"] == 2
    assert score["rate"] == pytest.approx(1 / 3)


def test_aggregate_applies_pass_threshold() -> None:
    score_review = _load_module()
    passing = score_review.aggregate([_grader(0.5), _grader(0.3)])
    assert passing["selection_rate"] == pytest.approx(0.4)
    assert passing["pass"] is True
    failing = score_review.aggregate([_grader(0.39)])
    assert failing["pass"] is False
