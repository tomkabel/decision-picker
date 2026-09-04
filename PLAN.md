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

## Phase 3a — chained AskUserQuestion rounds for >4 candidates ✅ done
Problem was: more than 4 candidates got silently pre-filtered to top 4.

- [x] `scripts/tournament.py`: `build_round()` splits N ranked choices into
      groups of <=4 (ranks spread evenly, not top-group-vs-bottom-group);
      `simulate_to_single_winner()` drives repeated rounds down to one pick.
- [x] SKILL.md step 1 now runs a tournament round per group instead of
      cutting to top 4 silently — every candidate gets seen by the user.
- [x] Self-check: `scripts/tournament.py` demo() feeds 9 candidates and
      asserts the flow ends on the true best one — `python3 scripts/tournament.py`.

## Phase 3b — custom terminal picker UI (not yet built)
Only build this if the chained-rounds approach above proves insufficient in
a real case — e.g. the user needs to compare all N options side-by-side at
once rather than round-by-round. No known case has hit this yet.

- [ ] If needed: scope a minimal paginated terminal list (no new dependency —
      plain ANSI, arrow-key nav via existing TTY handling).
- [ ] Self-check: given 9 candidates, the flow ends with one clear pick and the
      user can see why the other 8 were cut or ranked lower, in a single view.

## Non-goals (still YAGNI after all three phases)
- A persistent scoring database or history of past decisions — add only if a
  real need for "what did we pick last time" shows up.
- A GUI/web version — this is a terminal-agent tool by design.
