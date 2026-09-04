#!/usr/bin/env python3
"""Tests for rubric.py. No framework: `python3 scripts/test_rubric.py`.

These test the validation branches and the gating rules — the places where a
malformed model output could silently corrupt a ranking. The old demo()
asserted that a hardcoded winner won on its own fixture, which is a tautology.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rubric import (  # noqa: E402
    DEFAULT_WEIGHTS,
    NOISE_BAND,
    rank_choices,
    score_choice,
)

HERE = Path(__file__).resolve().parent


def raises(fn, *, containing: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert containing in str(exc), f"expected {containing!r} in error, got: {exc}"
        return
    raise AssertionError(f"expected ValueError containing {containing!r}, nothing raised")


def full(**over) -> dict:
    base = {k: 50 for k in DEFAULT_WEIGHTS}
    base.update(over)
    return base


def test_weights_sum_to_one() -> None:
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9
    raises(lambda: score_choice(full(), weights={"a": 0.5, "b": 0.2}), containing="sum to 1.0")


def test_rejects_out_of_range() -> None:
    raises(lambda: score_choice(full(reversibility=150)), containing="0 <= score <= 100")
    raises(lambda: score_choice(full(reversibility=-20)), containing="0 <= score <= 100")


def test_rejects_fraction_instead_of_percent() -> None:
    # The headline silent-corruption bug: 0.9 used to score a confident-looking total.
    raises(lambda: score_choice(full(fit_to_constraints=0.9)), containing="0-1 fraction")
    # 0 and 1 are legitimate on a 0-100 scale and must still pass.
    assert score_choice(full(fit_to_constraints=0)).point == 30.0
    assert score_choice(full(fit_to_constraints=1)).point == 30.4


def test_rejects_non_numbers() -> None:
    raises(lambda: score_choice(full(precedent=True)), containing="expected a number")
    raises(lambda: score_choice(full(precedent="80")), containing="expected a number")
    raises(lambda: score_choice(full(precedent=float("nan"))), containing="finite")
    raises(lambda: score_choice(full(precedent=float("inf"))), containing="finite")


def test_rejects_wrong_keys() -> None:
    bad = full()
    bad["reversibilty"] = bad.pop("reversibility")  # typo'd duplicate
    raises(lambda: score_choice(bad), containing="unknown criteria")
    missing = {k: 50 for k in list(DEFAULT_WEIGHTS)[:3]}
    raises(lambda: score_choice(missing), containing="missing sub-scores")


def test_unknown_is_not_treated_as_average() -> None:
    s = score_choice(full(evidence_strength=None))
    assert s.unknown == ("evidence_strength",)
    assert not s.certain
    # bounds span exactly the unknown criterion's weight
    assert round(s.hi - s.lo, 6) == round(DEFAULT_WEIGHTS["evidence_strength"] * 100, 6)


def test_unknown_blocks_separation() -> None:
    """A decision resting on something never established must not look decisive."""
    v = rank_choices([
        {"label": "A", "scores": full(fit_to_constraints=90, evidence_strength=None)},
        {"label": "B", "scores": full(fit_to_constraints=40)},
    ])
    assert v.recommended is not None and v.recommended.label == "A"
    assert not v.separated, "unknown evidence should keep the call contested"
    assert v.band == "Contested"


def test_infeasible_is_gated_not_penalised() -> None:
    """The core MCDA fix: a hard-constraint violation cannot be outscored back in."""
    v = rank_choices([
        {"label": "Violates", "feasible": False, "note": "no on-prem build", "scores": full(fit_to_constraints=100)},
        {"label": "Ok", "scores": full(fit_to_constraints=10)},
    ])
    assert [r.label for r in v.ranked] == ["Ok"]
    assert [r.label for r in v.excluded] == ["Violates"]
    assert v.recommended is not None and v.recommended.label == "Ok"
    assert v.band == "Only feasible option"


def test_no_feasible_option() -> None:
    v = rank_choices([{"label": "X", "feasible": False, "scores": full()}])
    assert v.recommended is None
    assert v.band == "No feasible option"


def test_contested_inside_noise_band() -> None:
    v = rank_choices([
        {"label": "A", "scores": full(fit_to_constraints=60)},
        {"label": "B", "scores": full(fit_to_constraints=50)},
    ])
    assert v.gap is not None and 0 < v.gap < NOISE_BAND
    assert not v.separated and v.band == "Contested"


def test_separated_outside_noise_band() -> None:
    v = rank_choices([
        {"label": "A", "scores": full(fit_to_constraints=100, reversibility=100)},
        {"label": "B", "scores": full(fit_to_constraints=10, reversibility=10)},
    ])
    assert v.separated and v.band == "Separated"


def test_weak_field() -> None:
    v = rank_choices([
        {"label": "A", "scores": full(**{k: 20 for k in DEFAULT_WEIGHTS})},
        {"label": "B", "scores": full(**{k: 5 for k in DEFAULT_WEIGHTS})},
    ])
    assert v.band == "Weak field", "a weak winner must not read as a strong lead"


def test_duplicate_and_empty_labels() -> None:
    raises(lambda: rank_choices([{"label": "A", "scores": full()}, {"label": "A", "scores": full()}]),
           containing="duplicate")
    raises(lambda: rank_choices([{"label": "  ", "scores": full()}]), containing="non-empty label")


def test_custom_weights() -> None:
    """Phase 7: the default weights are a default, not a law."""
    w = {"fit_to_constraints": 0.7, "reversibility": 0.1, "evidence_strength": 0.1, "precedent": 0.1}
    v = rank_choices([{"label": "A", "scores": full(fit_to_constraints=100)}], weights=w)
    assert v.recommended is not None and v.recommended.score is not None
    assert v.recommended.score.point == 85.0


def test_cli_roundtrip_and_no_percent_in_output() -> None:
    payload = {"choices": [
        {"label": "Redis", "scores": full(fit_to_constraints=90, precedent=95)},
        {"label": "File-based", "scores": full(fit_to_constraints=20)},
    ]}
    for flags in ([], ["--json"]):
        out = subprocess.run(
            [sys.executable, str(HERE / "rubric.py"), *flags],
            input=json.dumps(payload), capture_output=True, text=True, check=True,
        ).stdout
        assert "Redis" in out
        if flags:
            assert json.loads(out)["recommended"] == "Redis"
        else:
            # Phase 4: the percent sign must never reach a rendered surface.
            assert "%" not in out, f"rubric output leaked a percent sign:\n{out}"


def test_cli_reports_bad_input_actionably() -> None:
    bad = {"choices": [{"label": "A", "scores": full(reversibility=150)}]}
    proc = subprocess.run(
        [sys.executable, str(HERE / "rubric.py")],
        input=json.dumps(bad), capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "reversibility" in proc.stderr and "0 <= score <= 100" in proc.stderr


def run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"rubric: {len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
