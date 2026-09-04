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
never renders one to the user — not as `82%`, not as `82/100`, not as `0.82`, not
as "high confidence". A weighted total answers "how well does this option satisfy
these criteria", not "how likely is this to be right"; those are different
quantities, and showing the second one invites anchoring on a number with no
error bars behind it.

Four design consequences, each of which exists because the obvious version was
wrong:

- **Ignorance costs you.** Ranking is on the conservative bound, so an unscored
  criterion contributes nothing. Imputing unknowns at the mean — the obvious
  implementation — meant an all-unknown option scored 50 and outranked a
  fully-grounded 45, rewarding the model for declining to look.
- **Sub-scores are three anchor bands, not free 0-100.** Three anchors describe
  three levels. Accepting `87` invents resolution nothing can justify, and false
  precision at the input lands straight in the sort order.
- **Evidence is not weighted.** How much *you* verified is a fact about your
  knowledge, not about the option. In the sum it made options better for having
  been researched; separated out, it gates escalation — weak evidence means go
  get evidence, not dock points.
- **Separation is measured, not asserted.** The script resamples the weights and
  jitters each sub-score by one band a few hundred times and reports how often
  the top option stays on top. That replaces a hardcoded noise margin that was,
  by its own comment, a guess.

Plus: hard constraints gated out rather than weighed, so a violation cannot be
outscored back into contention; a steelman of the runner-up to offset the fact
that a sorted, default-marked menu is already steering the user; and one JSONL
line per decision, because for a decision aid the record is the product.

## Install

The skill directory is self-contained — the scripts live inside it and address
themselves through `${CLAUDE_SKILL_DIR}`, so a symlink is all you need:

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
    ├── rubric.py             scoring, feasibility gating, stability, decision log
    ├── test_rubric.py        validation, gating and ranking tests
    └── eval/
        ├── check_trace.py    protocol assertions on decision traces
        ├── fixtures.json     labelled traces, including deliberate regressions
        └── scenarios.json    scenario specs for --live runs
```

## Tests

```bash
python3 .claude/skills/decision-picker/scripts/test_rubric.py
python3 .claude/skills/decision-picker/scripts/eval/check_trace.py
python3 .claude/skills/decision-picker/scripts/eval/check_trace.py --live --repeat 3
```

The unit tests cover validation, gating, and the two ranking bugs above. The
more important suite is `check_trace.py`: a skill is a prompt, so the failure
mode that matters is the agent not following the protocol. It asserts
structurally — ≤4 options per call, no score-shaped number in rendered text,
`(Recommended)` matching the ranking, escalation firing exactly when the rubric's
reasons say it should, excluded options never offered, `Other` answers re-scored
before use, injection-shaped candidates surfaced and never executed, and the
final action matching the user's pick. `fixtures.json` includes deliberately
broken traces that must go red.

### What `--live` can and cannot prove

**`AskUserQuestion` is not available in headless `claude -p` sessions** — the
tool is absent from the tool list and the session is flagged non-interactive.
Verified, not assumed. So a live run cannot observe a real ask, and a harness
that says otherwise is reading a self-report.

What it does get, labelled by evidence class in every saved trace:

| | source |
|---|---|
| sub-scores, evidence levels, feasibility gating, weights, verdict | **ground truth** — the script's own decision log, via `$DECISION_PICKER_LOG` |
| which tools ran | **ground truth** — `--output-format stream-json` |
| the `AskUserQuestion` arguments | **self-reported** — linted, never called an executed ask |

The step with all the variance in it is the one that is fully observable, which
is the part worth having. `--repeat` runs each scenario k times and reports how
often the recommendation agrees with itself, and the protocol-break rate comes
with a Wilson interval so the gate cannot overclaim its own resolution.

## Design history

[`PLAN.md`](PLAN.md) tracks the phases. The current shape came out of a senior
review, an adversarial review from five flagship reasoning models across five
families (verbatim responses, brief and harness config in
[`docs/review-2026-09-04/`](docs/review-2026-09-04/)), and a second senior review
that reproduced its findings against the code rather than reading it — which is
how the ranking bugs, a percent check that matched one character, and an eval
built on an unavailable tool were all found.
