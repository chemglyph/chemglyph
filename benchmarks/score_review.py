"""Score blind-review answer files against the local pair key.

Usage::

    python benchmarks/score_review.py answers1.json [answers2.json ...]

Each answer file is either JSON like ``{"answers": {"pair_001": "A", ...}}``
or plain text with one ``pair_NNN A|B|tie`` per line. The pair key lives in
``benchmarks/blind_review/pair_key.json`` and never leaves the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUT_DIR = _REPO_ROOT / "benchmarks" / "blind_review"
_PAIR_KEY_PATH = _OUT_DIR / "pair_key.json"

VALID_ANSWERS = {"A", "B", "tie", "neither"}


def score_grader(answers: dict[str, str], pair_key: dict) -> dict:
    """Per-grader score: share of scored pairs where they picked ChemGlyph."""
    picked = 0.0
    missing = 0
    scored = 0
    per_style: dict[str, dict] = {"acs": {"n": 0, "picked": 0.0}, "modern": {"n": 0, "picked": 0.0}}
    per_molecule: dict[str, dict] = {}
    for pair_id, info in pair_key.items():
        if not isinstance(info, dict):
            continue  # top-level fields such as seed/run_id
        if not info.get("scored", True):
            continue
        scored += 1
        answer = answers.get(pair_id)
        if answer not in VALID_ANSWERS:
            missing += 1
            value = 0.0
        else:
            chemglyph_side = "A" if info["a_engine"] == "chemglyph" else "B"
            # pick = 1, tie = 0.5, neither = 0 (ChemGlyph was not chosen)
            value = 1.0 if answer == chemglyph_side else (0.5 if answer == "tie" else 0.0)
        picked += value
        style = info["style"]
        per_style[style]["n"] += 1
        per_style[style]["picked"] += value
        molecule = info["molecule"]
        per_molecule.setdefault(molecule, {"n": 0, "picked": 0.0})
        per_molecule[molecule]["n"] += 1
        per_molecule[molecule]["picked"] += value
    return {
        "scored_pairs": scored,
        "picked": picked,
        "rate": picked / scored if scored else 0.0,
        "missing": missing,
        "per_style": {
            style: {"n": item["n"], "rate": item["picked"] / item["n"] if item["n"] else 0.0}
            for style, item in per_style.items()
        },
        "per_molecule": {
            name: {"n": item["n"], "rate": item["picked"] / item["n"] if item["n"] else 0.0}
            for name, item in per_molecule.items()
        },
    }


def aggregate(grader_scores: list[dict]) -> dict:
    """Average grader rates and apply the 40% pass criterion."""
    rate = sum(score["rate"] for score in grader_scores) / len(grader_scores)
    per_style = {}
    for style in ("acs", "modern"):
        rates = [score["per_style"][style]["rate"] for score in grader_scores]
        per_style[style] = sum(rates) / len(rates) if rates else 0.0
    return {
        "num_graders": len(grader_scores),
        "selection_rate": rate,
        "pass": rate >= 0.40,
        "per_style": per_style,
    }


def load_answer_file(path: Path) -> tuple[dict[str, str], str | None]:
    """Load an answer file and its deck run id (JSON only; text has none)."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        payload = json.loads(text)
        raw = payload.get("answers", payload)
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
    else:
        raw = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            pair_id, _, answer = stripped.partition(" ")
            raw[pair_id.strip()] = answer.strip()
        run_id = None
    return {str(key): str(value) for key, value in raw.items()}, run_id


def check_run_id(pair_key_run_id: str | None, answers_run_id: str | None) -> str | None:
    """Return an error message when the answer file belongs to another deck."""
    if not pair_key_run_id or not answers_run_id:
        return None
    if answers_run_id != pair_key_run_id:
        return (
            f"answers were produced for run {answers_run_id!r}, "
            f"but pair_key.json is run {pair_key_run_id!r}"
        )
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Score blind-review answer files")
    parser.add_argument("answer_files", nargs="+", type=Path)
    args = parser.parse_args()
    pair_key = json.loads(_PAIR_KEY_PATH.read_text(encoding="utf-8"))
    expected_run_id = pair_key.get("run_id")
    loaded: list[dict[str, str]] = []
    for path in args.answer_files:
        answers, run_id = load_answer_file(path)
        error = check_run_id(expected_run_id, run_id)
        if error:
            print(f"error: {path}: {error}", file=sys.stderr)
            raise SystemExit(1)
        if run_id is None:
            print(
                f"warning: {path} has no run id; assuming it belongs to this deck",
                file=sys.stderr,
            )
        loaded.append(answers)
    grader_scores = [score_grader(answers, pair_key) for answers in loaded]
    result = aggregate(grader_scores)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "answer_files": [str(path) for path in args.answer_files],
        "grader_scores": grader_scores,
        **result,
    }
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
