"""Phase 1: weighted confidence rubric for decision-picker.

Claude still assigns each sub-score by judgment (0-100 per criterion) — this
module only fixes the criteria and weights so the total is reproducible and
the sub-scores stay visible, instead of one opaque gut-feel percentage.
"""

from typing import Mapping

CRITERIA_WEIGHTS = {
    "fit_to_constraints": 0.40,
    "reversibility": 0.25,
    "evidence_strength": 0.20,
    "precedent": 0.15,
}


def score_choice(sub_scores: Mapping[str, float]) -> float:
    """Weighted total (0-100) from per-criterion sub-scores (0-100 each)."""
    missing = CRITERIA_WEIGHTS.keys() - sub_scores.keys()
    if missing:
        raise ValueError(f"missing sub-scores: {sorted(missing)}")
    return round(
        sum(sub_scores[k] * w for k, w in CRITERIA_WEIGHTS.items()), 1
    )


def rank_choices(choices: Mapping[str, Mapping[str, float]]) -> list[tuple[str, float]]:
    """choices: {label: sub_scores}. Returns [(label, total)] sorted desc."""
    scored = [(label, score_choice(sub)) for label, sub in choices.items()]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


def demo() -> None:
    choices = {
        "Redis": {
            "fit_to_constraints": 90,
            "reversibility": 60,
            "evidence_strength": 85,
            "precedent": 95,
        },
        "In-memory LRU": {
            "fit_to_constraints": 50,
            "reversibility": 80,
            "evidence_strength": 60,
            "precedent": 40,
        },
        "File-based": {
            "fit_to_constraints": 20,
            "reversibility": 90,
            "evidence_strength": 30,
            "precedent": 20,
        },
    }
    ranked = rank_choices(choices)
    assert ranked[0][0] == "Redis", f"expected Redis to win, got {ranked}"
    assert all(0 <= total <= 100 for _, total in ranked)
    print("rubric self-check passed:", ranked)


if __name__ == "__main__":
    demo()
