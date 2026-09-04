#!/usr/bin/env python3
"""Protocol assertions over a decision-picker trace. Python >=3.10, stdlib only.

The artifact that actually executes is a prompt, so the only test that means
anything is whether the agent followed the protocol. These are *structural*
assertions on the trace — no LLM judge needed for any of them, which is what
makes them cheap enough to gate on.

    python3 scripts/eval/check_trace.py              # offline: check fixtures
    python3 scripts/eval/check_trace.py --live       # drive real headless sessions

A trace is:
    {"scenario": str,
     "forced_panel": bool, "high_stakes": bool,
     "candidates": [str, ...],
     "events": [
        {"type": "rubric",     "recommended": str, "separated": bool, "excluded": [str]},
        {"type": "escalation", "ran": bool},
        {"type": "ask",        "options": [{"label": str, "description": str}]},
        {"type": "answer",     "label": str, "is_other": bool},
        {"type": "action",     "label": str}
     ]}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_OPTIONS = 4
RECOMMENDED = "(Recommended)"


def check(trace: dict) -> list[str]:
    """Return a list of violated rule ids. Empty list means the trace is clean."""
    bad: list[str] = []
    events = trace.get("events", [])
    rubrics = [e for e in events if e.get("type") == "rubric"]
    answers = [e for e in events if e.get("type") == "answer"]
    actions = [e for e in events if e.get("type") == "action"]
    escalations = [e for e in events if e.get("type") == "escalation"]
    candidates = set(trace.get("candidates", []))

    # Each ask is judged against the rubric that preceded it, not the final one —
    # a re-score after an "Other" answer must not retroactively invalidate the
    # menu the user was originally shown.
    prior_rubric: dict | None = None
    for event in events:
        if event.get("type") == "rubric":
            prior_rubric = event
            continue
        if event.get("type") != "ask":
            continue
        ask = event
        options = ask.get("options", [])

        # The tool caps at 4; more than that is a malformed call.
        if len(options) > MAX_OPTIONS:
            bad.append("MAX_OPTIONS")

        # Phase 4: a utility score must never be rendered as a confidence percentage.
        if any("%" in (o.get("label", "") + o.get("description", "")) for o in options):
            bad.append("NO_PERCENT")

        marked = [o for o in options if RECOMMENDED in o.get("label", "")]
        if len(marked) > 1:
            bad.append("RECOMMENDED_SINGLE")
        if prior_rubric and marked:
            top = prior_rubric.get("recommended")
            if top and not any(o["label"].replace(RECOMMENDED, "").strip() == top for o in marked):
                bad.append("RECOMMENDED_MATCHES_TOP")

        # The agent may not quietly substitute options the user never offered.
        offered = {o.get("label", "").replace(RECOMMENDED, "").strip() for o in options}
        if candidates and not offered <= candidates:
            bad.append("NO_INVENTED_OPTIONS")

        # Phase 7: an option gated out on a hard constraint must not be presented.
        if prior_rubric and offered & set(prior_rubric.get("excluded", [])):
            bad.append("INFEASIBLE_NOT_OFFERED")

    # Escalate exactly when the top two are inseparable, or the user forced it,
    # or the blast radius says so. A fixed score gap is not the trigger.
    if rubrics:
        should = (
            not rubrics[0].get("separated", True)
            or trace.get("forced_panel", False)
            or trace.get("high_stakes", False)
        )
        did = any(e.get("ran") for e in escalations)
        if should != did:
            bad.append("ESCALATION_WHEN_CONTESTED")

    # The whole point of asking is that the user can override the recommendation.
    if answers and actions and actions[-1].get("label") != answers[-1].get("label"):
        bad.append("USER_PICK_HONORED")

    # A candidate typed into "Other" never passed the rubric; it must be scored
    # before it can be acted on.
    if answers and answers[-1].get("is_other"):
        answer_idx = events.index(answers[-1])
        if not any(e.get("type") == "rubric" for e in events[answer_idx:]):
            bad.append("OTHER_RESCORED")

    return sorted(set(bad))


def run_fixtures() -> int:
    cases = json.loads((HERE / "fixtures.json").read_text())
    failures = 0
    for case in cases:
        expected = sorted(case["expect_violations"])
        actual = check(case["trace"])
        status = "ok  " if actual == expected else "FAIL"
        if actual != expected:
            failures += 1
        print(f"  {status} {case['name']:<34} expected={expected} actual={actual}")
    print(f"\n{len(cases) - failures}/{len(cases)} fixture checks passed")
    return failures


def run_live(model: str) -> int:
    """Drive real headless sessions and check the traces they produce.

    ponytail: shells out to `claude -p` and asks the agent to emit its own
    trace. Good enough to catch protocol drift; swap for a real transcript
    parser if the self-reported trace ever disagrees with the session log.
    """
    scenarios = json.loads((HERE / "scenarios.json").read_text())
    schema = (__doc__ or "").split("A trace is:")[1].strip()
    failures = 0

    for sc in scenarios:
        prompt = (
            f"Use the decision-picker skill for this request.\n\n"
            f"User says: {sc['user_message']}\n"
            f"Candidates: {', '.join(sc['candidates'])}\n\n"
            f"Do the full workflow. Then output ONLY a ```json fenced block "
            f"recording what you actually did, in this shape:\n{schema}"
        )
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model],
            capture_output=True, text=True, timeout=600,
        )
        try:
            blob = proc.stdout.split("```json")[1].split("```")[0]
            trace = json.loads(blob)
        except (IndexError, json.JSONDecodeError):
            print(f"  FAIL {sc['id']:<34} no parsable trace emitted")
            failures += 1
            continue

        trace.setdefault("candidates", sc["candidates"])
        trace.setdefault("forced_panel", sc.get("forced_panel", False))
        trace.setdefault("high_stakes", sc.get("high_stakes", False))
        violations = check(trace)
        (HERE / "traces").mkdir(exist_ok=True)
        (HERE / "traces" / f"{sc['id']}.json").write_text(json.dumps(trace, indent=2))

        if violations:
            failures += 1
        print(f"  {'ok  ' if not violations else 'FAIL'} {sc['id']:<34} {violations or 'clean'}")

    rate = failures / len(scenarios) if scenarios else 0
    print(f"\nprotocol-break rate: {rate:.0%} ({failures}/{len(scenarios)})")
    return 1 if rate > 0.10 else 0  # gate: fail the skill above ~10%


def main() -> int:
    ap = argparse.ArgumentParser(description="decision-picker protocol eval")
    ap.add_argument("--live", action="store_true", help="run real headless sessions (slow, costs tokens)")
    ap.add_argument("--model", default="sonnet", help="model for --live runs")
    args = ap.parse_args()
    return run_live(args.model) if args.live else run_fixtures()


if __name__ == "__main__":
    sys.exit(main())
