# decision-picker — phased plan

Origin: `decision-picker` skill (symlinked from `~/.claude/skills/decision-picker`)
started as a thin wrapper around native `AskUserQuestion` + the `council` skill.
Three things were deliberately skipped at v1. This plan builds them in order of
payoff, each phase shippable and useful on its own.

## Phase 0 — repo bootstrap ✅ done (commit `4b57bb3`)
- [x] `git init`, commit the symlinked skill as a real file (git doesn't follow
      symlinks portably across clones) — copy `SKILL.md` into this repo, keep
      `~/.claude/skills/decision-picker` as a symlink *back* to this repo instead.
- [x] `README.md`: what this is, how to install (symlink into `~/.claude/skills/`
      or a project's `.claude/skills/`).
- [x] No test framework yet — one `test_decision_picker.py`-style smoke check
      per phase below (ponytail rule: non-trivial logic needs one runnable check).

## Phase 1 — real confidence scoring (replace single-pass self-estimate) ✅ done
Problem was: step 2 was "assign a number, trust yourself." No calibration, no
reproducibility, no reason trail.

- [x] Defined a scoring rubric as explicit weighted criteria (`scripts/rubric.py`:
      fit_to_constraints 0.40, reversibility 0.25, evidence_strength 0.20, precedent 0.15).
- [x] `score_choice()` / `rank_choices()` keep sub-scores visible, not just the
      total — SKILL.md step 2 now points here instead of a vibe percentage.
- [x] Self-check: `scripts/rubric.py` demo() asserts the rubric ranks the
      known winner first — `python3 scripts/rubric.py`.

## Phase 2 — always-available panel mode (not just close-call escalation) ✅ done
Problem was: the senior-expert-panel path only fired when scores were within
~15 points or the decision was flagged high-stakes — no way for the user to force it.

- [x] `scripts/panel_trigger.py`: explicit force phrases ("run the panel",
      "second opinion", "get the panel", "convene the council") escalate to
      `council` unconditionally, regardless of score gap.
- [x] SKILL.md step 3 now tells Claude to fold panel arguments back into the
      Phase 1 sub-scores and re-total, instead of a cosmetic "Panel pick" prefix.
- [x] Self-check: `scripts/panel_trigger.py` demo() asserts the forced path
      escalates even with a wide score gap — `python3 scripts/panel_trigger.py`.

## Phase 3 — custom picker UI beyond AskUserQuestion's 4-option cap
Problem today: more than 4 candidates get silently pre-filtered.

- [ ] Only build this if a real case hits the 4-option ceiling — check first
      whether chaining two `AskUserQuestion` calls (round 1: narrow 8→4, round 2:
      pick from 4) covers it before writing a custom terminal UI. That's stdlib-tier
      reuse vs. a new rung on the ladder.
- [ ] If chaining is insufficient (e.g. need to see all N with scores at once,
      not two hops), then and only then scope a minimal paginated terminal list
      (no new dependency — plain ANSI, arrow-key nav via existing TTY handling).
- [ ] Self-check: given 9 candidates, the flow ends with one clear pick and the
      user can see why the other 8 were cut or ranked lower.

## Non-goals (still YAGNI after all three phases)
- A persistent scoring database or history of past decisions — add only if a
  real need for "what did we pick last time" shows up.
- A GUI/web version — this is a terminal-agent tool by design.
