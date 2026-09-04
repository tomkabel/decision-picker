# decision-picker

A Claude Code skill that turns a list of candidate choices into an interactive
terminal selection: a transparent multi-criteria score per choice, a best-guess
default, and an adversarial review step for close or high-stakes calls.

Built on what Claude Code already ships — no new dependency, stdlib-only Python:

- **`AskUserQuestion`** (native tool) — renders the terminal multi-choice UI,
  the `(Recommended)` marker, and the free-text "Other" escape hatch.
- **`council`** (skill, optional) — one available escalation path, used with the
  caveat that four personas from one model is a single-model review, not an
  independent panel.

## What it deliberately does not do

The scores are a **utility ranking, not a confidence probability**, and the skill
never renders them as a percentage. A weighted total answers "how well does this
option satisfy these criteria", not "how likely is this to be right" — those are
different quantities, and showing the second one as a percentage invites anchoring
on a number that has no error bars behind it.

Everything else follows from that: behavioral anchors so the sub-scores mean
something, ordinal bands instead of decimals in the UI, hard constraints gated
out rather than weighed, `unknown` sub-scores tracked as a range instead of
silently scored 50, and a steelman of the runner-up to offset the fact that a
sorted, default-marked menu is already steering the user.

## Install

The skill directory is self-contained — the scripts live inside it, so a symlink
is all you need:

```bash
# global
ln -s "$(pwd)/.claude/skills/decision-picker" ~/.claude/skills/decision-picker

# or project-local, from inside another project
ln -s /path/to/claude-select/.claude/skills/decision-picker .claude/skills/decision-picker
```

Requires Python >= 3.10. No packages, no virtualenv, no build step.

## Layout

```
.claude/skills/decision-picker/
├── SKILL.md                  the workflow the agent follows — the actual product
└── scripts/
    ├── rubric.py             weighted scoring, feasibility gating, CLI
    ├── test_rubric.py        validation + gating tests
    └── eval/
        ├── check_trace.py    protocol assertions on decision traces
        ├── fixtures.json     labelled traces, including deliberate regressions
        └── scenarios.json    scenario specs for --live runs
```

## Tests

```bash
python3 .claude/skills/decision-picker/scripts/test_rubric.py
python3 .claude/skills/decision-picker/scripts/eval/check_trace.py
python3 .claude/skills/decision-picker/scripts/eval/check_trace.py --live   # slow, costs tokens
```

The unit tests cover `rubric.py`'s validation and gating. The more important
suite is `check_trace.py`: a skill is a prompt, so the only failure mode that
matters is whether the agent follows the protocol. It asserts structurally —
≤4 options per call, no `%` in rendered text, `(Recommended)` matching the
ranking, escalation firing exactly when it should, excluded options never
offered, `Other` answers re-scored before use, and the final action matching
the user's pick rather than the recommendation. `fixtures.json` includes
deliberately broken traces that must go red.

## Design history

[`PLAN.md`](PLAN.md) tracks the phases. The current shape came out of a senior
review followed by an adversarial review from five flagship reasoning models
across five different families; their verbatim responses, the brief, and the
harness config are in [`docs/review-2026-09-04/`](docs/review-2026-09-04/).
That review upheld most of the critique, **overturned one point outright**, and
turned the roadmap into a net deletion: two of the three original scripts are
gone, because they applied determinism to steps that were never uncertain while
the one genuinely uncertain step had no anchors at all.
