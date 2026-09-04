# decision-picker — phased plan

Origin: `decision-picker` skill (symlinked from `~/.claude/skills/decision-picker`)
started as a thin wrapper around native `AskUserQuestion` + the `council` skill.
Three things were deliberately skipped at v1. This plan builds them in order of
payoff, each phase shippable and useful on its own.

## Phase 0 — repo bootstrap
- [ ] `git init`, commit the symlinked skill as a real file (git doesn't follow
      symlinks portably across clones) — copy `SKILL.md` into this repo, keep
      `~/.claude/skills/decision-picker` as a symlink *back* to this repo instead.
- [ ] `README.md`: what this is, how to install (symlink into `~/.claude/skills/`
      or a project's `.claude/skills/`).
- [ ] No test framework yet — one `test_decision_picker.py`-style smoke check
      per phase below (ponytail rule: non-trivial logic needs one runnable check).

## Phase 1 — real confidence scoring (replace single-pass self-estimate)
Problem today: step 2 is "assign a number, trust yourself." No calibration, no
reproducibility, no reason trail.

- [ ] Define a scoring rubric as explicit weighted criteria (fit-to-constraints,
      reversibility, evidence strength, precedent) instead of a vibe number.
- [ ] Score each choice against the rubric, show the sub-scores, not just the
      total — this is the "confidence rating visible for each choice" capability
      done properly instead of a single opaque percentage.
- [ ] Self-check: a script/test that feeds a known choice set with an obvious
      winner and asserts the rubric ranks it first.

## Phase 2 — always-available panel mode (not just close-call escalation)
Problem today: the senior-expert-panel path only fires when scores are within
~15 points or the decision is flagged high-stakes — user has no way to force it.

- [ ] Add an explicit trigger: user says "run the panel" / "get a second opinion"
      → invoke `council` unconditionally, regardless of score gap.
- [ ] Surface the panel's per-voice confidence deltas (did Skeptic/Critic move
      the score, and by how much) back into the rubric from Phase 1, not just a
      one-line "Panel pick" prefix.
- [ ] Self-check: verify the forced-panel path runs `council` even when scores
      are identical or far apart (i.e., the override actually overrides).

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
