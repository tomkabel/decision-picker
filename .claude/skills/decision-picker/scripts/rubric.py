#!/usr/bin/env python3
"""Weighted multi-criteria scoring for decision-picker. Python >=3.10, stdlib only.

The number this produces is an internal sort key, NOT a confidence probability.
A weighted total is a multi-criteria *utility* score; `P(this option is correct)`
is a different quantity that nothing here estimates. Never render it to the user
as a percentage — see SKILL.md, which carries the behavioral anchors that make
the sub-scores mean anything at all.

This module is the single source of truth for the criteria and their weights.
Everything it does is deterministic; all the variance lives upstream in the
sub-scores the model assigns, which is why the anchors matter more than the math.

Usage:
    echo '{"choices": [{"label": "Redis", "scores": {...}}]}' | python3 rubric.py
    python3 rubric.py --json < decision.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from typing import Mapping

DEFAULT_WEIGHTS: dict[str, float] = {
    "fit_to_constraints": 0.40,
    "reversibility": 0.25,
    "evidence_strength": 0.20,
    "precedent": 0.15,
}

# Unanchored per-criterion ratings vary by roughly +/-15-20 between passes, which
# propagates to a total sigma on the order of 8-12 points. A top-two gap smaller
# than this is not a result, it is one noisy forward pass, so we call it a tie and
# let the caller escalate. Erring toward "contested" is the safe direction.
# ponytail: fixed constant, not a measured sigma. Replace with a real estimate
# once the eval harness records score variance across repeated passes.
NOISE_BAND = 12.0

# Below this, no option is actually good — the field is weak, not the winner strong.
WEAK_FIELD_TOTAL = 50.0


@dataclass(frozen=True)
class Score:
    """Point estimate plus the bounds implied by any `unknown` sub-scores."""

    point: float
    lo: float
    hi: float
    unknown: tuple[str, ...] = ()

    @property
    def certain(self) -> bool:
        return not self.unknown


@dataclass(frozen=True)
class Ranked:
    label: str
    score: Score | None  # None when the option was gated out as infeasible
    feasible: bool = True
    note: str = ""


@dataclass
class Verdict:
    ranked: list[Ranked] = field(default_factory=list)
    excluded: list[Ranked] = field(default_factory=list)
    gap: float | None = None
    band: str = ""
    separated: bool = False

    @property
    def recommended(self) -> Ranked | None:
        return self.ranked[0] if self.ranked else None


def _validate_weights(weights: Mapping[str, float]) -> dict[str, float]:
    if not weights:
        raise ValueError("weights must not be empty")
    for name, w in weights.items():
        if isinstance(w, bool) or not isinstance(w, (int, float)):
            raise ValueError(f"weight {name!r}: expected a number, got {w!r}")
        if not math.isfinite(w) or w < 0:
            raise ValueError(f"weight {name!r}: expected a finite non-negative number, got {w!r}")
    total = sum(weights.values())
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise ValueError(f"weights must sum to 1.0, got {total!r} from {sorted(weights)}")
    return dict(weights)


def _validate_sub_score(criterion: str, value: object) -> float | None:
    """One sub-score: 0-100, or None meaning 'not established'."""
    if value is None:
        return None
    # bool is an int subclass, so this check must come first.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{criterion!r}: expected a number 0-100 or null, got {value!r}")
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(f"{criterion!r}: expected a finite number, got {value!r}")
    if 0.0 < v < 1.0:
        raise ValueError(
            f"{criterion!r}: {value!r} looks like a 0-1 fraction; this scale is 0-100. "
            "Pass the intended value explicitly rather than relying on a rescale."
        )
    if not 0.0 <= v <= 100.0:
        raise ValueError(f"{criterion!r}: expected 0 <= score <= 100, got {value!r}")
    return v


def score_choice(
    sub_scores: Mapping[str, object],
    weights: Mapping[str, float] | None = None,
) -> Score:
    """Weighted total from per-criterion sub-scores (0-100 each, or None if unknown).

    An unknown sub-score is not silently treated as average. The point estimate
    renormalises over the criteria that *are* known, and `lo`/`hi` carry the
    bounds implied by the unknown ones — so a decision resting on something we
    never established shows up as an overlap instead of a confident total.
    """
    w = _validate_weights(weights if weights is not None else DEFAULT_WEIGHTS)

    unexpected = sorted(set(sub_scores) - set(w))
    if unexpected:
        raise ValueError(f"unknown criteria: {unexpected} (expected {sorted(w)})")
    missing = sorted(set(w) - set(sub_scores))
    if missing:
        raise ValueError(f"missing sub-scores: {missing}")

    clean = {k: _validate_sub_score(k, sub_scores[k]) for k in w}
    unknown = tuple(sorted(k for k, v in clean.items() if v is None))

    known_weight = sum(w[k] for k, v in clean.items() if v is not None)
    base = sum(v * w[k] for k, v in clean.items() if v is not None)
    unknown_weight = sum(w[k] for k in unknown)

    # Weights sum to 1, so `base` is already on the 0-100 scale; dividing by the
    # known weight renormalises when some criteria are unknown.
    point = base / known_weight if known_weight else 50.0
    return Score(
        point=round(point, 1),
        lo=round(base, 1),
        hi=round(base + unknown_weight * 100.0, 1),
        unknown=unknown,
    )


def rank_choices(
    choices: list[Mapping[str, object]],
    weights: Mapping[str, float] | None = None,
) -> Verdict:
    """Rank feasible choices; gate infeasible ones out *before* weighting.

    A hard constraint is not a criterion. An option that violates one cannot be
    compensated back into contention by scoring well on reversibility and
    precedent, so it never enters the ranking — it is reported separately.
    """
    ranked: list[Ranked] = []
    excluded: list[Ranked] = []
    seen: set[str] = set()

    for raw in choices:
        label = str(raw.get("label", "")).strip()
        if not label:
            raise ValueError(f"every choice needs a non-empty label: {raw!r}")
        if label in seen:
            raise ValueError(f"duplicate choice label: {label!r}")
        seen.add(label)

        note = str(raw.get("note", ""))
        if raw.get("feasible", True) is False:
            excluded.append(Ranked(label=label, score=None, feasible=False, note=note))
            continue

        scores = raw.get("scores")
        if not isinstance(scores, Mapping):
            raise ValueError(f"{label!r}: 'scores' must be an object of criterion -> 0-100 or null")
        ranked.append(Ranked(label=label, score=score_choice(scores, weights), note=note))

    ranked.sort(key=lambda r: r.score.point, reverse=True)  # type: ignore[union-attr]

    verdict = Verdict(ranked=ranked, excluded=excluded)
    if not ranked:
        verdict.band = "No feasible option"
    elif len(ranked) == 1:
        verdict.band = "Only feasible option"
        verdict.separated = True
    else:
        top, second = ranked[0].score, ranked[1].score
        assert top is not None and second is not None
        verdict.gap = round(top.lo - second.hi, 1)
        verdict.separated = verdict.gap >= NOISE_BAND
        if top.point < WEAK_FIELD_TOTAL:
            verdict.band = "Weak field"
        elif verdict.separated:
            verdict.band = "Separated"
        else:
            verdict.band = "Contested"
    return verdict


def format_table(verdict: Verdict) -> str:
    """Plain-text ranking for the agent to read. Deliberately no percent signs."""
    lines: list[str] = []
    for i, r in enumerate(verdict.ranked, 1):
        s = r.score
        assert s is not None
        bounds = "" if s.certain else f"  [{s.lo}-{s.hi}, unknown: {', '.join(s.unknown)}]"
        lines.append(f"{i}. {r.label}  score {s.point}/100{bounds}{('  — ' + r.note) if r.note else ''}")
    for r in verdict.excluded:
        why = r.note or "violates a stated hard constraint"
        lines.append(f"--. {r.label}  EXCLUDED — {why}")

    lines.append("")
    if verdict.gap is not None:
        lines.append(f"top-two gap: {verdict.gap} pts (noise band {NOISE_BAND})")
    lines.append(f"band: {verdict.band}")
    lines.append(
        "separated: yes — a recommendation is defensible"
        if verdict.separated
        else "separated: NO — treat the top two as tied and escalate"
    )
    lines.append(
        "NOTE: utility score, not a confidence probability. Never show it to the user as a percentage."
    )
    return "\n".join(lines)


def _verdict_to_dict(v: Verdict) -> dict:
    def one(r: Ranked) -> dict:
        d: dict = {"label": r.label, "feasible": r.feasible, "note": r.note}
        if r.score is not None:
            d |= {
                "point": r.score.point,
                "lo": r.score.lo,
                "hi": r.score.hi,
                "unknown": list(r.score.unknown),
            }
        return d

    return {
        "ranked": [one(r) for r in v.ranked],
        "excluded": [one(r) for r in v.excluded],
        "gap": v.gap,
        "band": v.band,
        "separated": v.separated,
        "recommended": v.recommended.label if v.recommended else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args(argv)

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"error: stdin is not valid JSON: {exc}", file=sys.stderr)
        return 2

    try:
        verdict = rank_choices(payload["choices"], payload.get("weights"))
    except (KeyError, ValueError) as exc:
        # Named, actionable errors: the agent reads this and corrects its own input.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(_verdict_to_dict(verdict), indent=2) if args.json else format_table(verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())
