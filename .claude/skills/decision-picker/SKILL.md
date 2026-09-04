---
name: decision-picker
description: Turn a list of candidate choices (or operator input options) into an interactive terminal selection via AskUserQuestion, annotated with a confidence score per choice, an AI best-guess default, and an optional senior-expert-panel final call for close/high-stakes decisions. Use when the user gives you several options and wants a scored pick, not just a picked-for-you answer.
metadata:
  origin: custom
---

# Decision Picker

Wraps the native `AskUserQuestion` tool (terminal multi-choice UI) with scoring and
an optional expert panel. Do not build a custom picker — `AskUserQuestion` already
renders the choice list, recommended-option marker, and free-text "Other" escape
hatch natively.

## When to Use

- User hands you a list of options (features, libraries, architectures, names,
  candidates) and wants to choose one interactively, not have you silently decide.
- You've generated several viable approaches yourself and want the user to pick,
  with your confidence in each visible.

## When NOT to Use

- Only one reasonable option exists — just do it, don't manufacture choices.
- The decision is reversible and low-stakes — pick the best-guess yourself and say so in one line, don't interrupt.

## Workflow

### 1. Normalize the choice list

Collect the candidates (from the user's message or your own analysis) into
`label` + one-line `description` pairs. 2-4 options per question —
`AskUserQuestion` caps at 4.

If there are more than 4, don't silently pre-filter — run the rubric (step 2)
on all of them first, then use `scripts/tournament.py`'s `build_round()` to
split them into groups of <=4 (ranks spread evenly across groups, not
best-group-vs-worst-group). Run one `AskUserQuestion` round per group, each
question's options carrying their rubric scores, top-of-group flagged
`(Recommended)`. Feed the round's winners back into `build_round()` and
repeat until <=4 remain, then do the final pick. Only reach for a custom
terminal UI (unbuilt — see PLAN.md phase 3) if this chaining proves
insufficient in a real case, e.g. the user needs to compare all N at once
rather than in rounds.

### 2. Score each choice against the rubric

Don't guess a single opaque percentage. Score each candidate on the four
criteria in `scripts/rubric.py` (0-100 each), then get the weighted total from
`score_choice()` / `rank_choices()`:

- `fit_to_constraints` (0.40) — how well it satisfies the stated goal/limits
- `reversibility` (0.25) — how cheap it is to undo if wrong
- `evidence_strength` (0.20) — how solid your basis is (docs, tests, precedent you've actually seen)
- `precedent` (0.15) — how proven this choice is elsewhere

Sort descending. The top score is your **best-guess default**. Keep the
sub-scores around — step 4 shows them, not just the total.

### 3. Escalate to a panel — auto on close calls, or whenever the user asks

Use `scripts/panel_trigger.py`'s `should_escalate()`: it returns true if the
top two totals are within 15 points, the decision is flagged high-stakes, OR
the user's message contains a force phrase ("run the panel", "second opinion",
"get the panel", "convene the council") — the force phrase always wins, even
on a clear-cut score gap.

If escalating, invoke the `council` skill with the choice list as the decision
question. Take its verdict's recommendation, and reflect what changed in the
rubric, not just a label prefix: if a voice's argument should move a
sub-score (e.g. Critic surfaces a reversibility problem you missed), adjust
that sub-score and re-total, so the visible numbers match the reasoning.

### 4. Present via AskUserQuestion

One call, one question (or up to 4 if there are independent sub-decisions).
- Order options by rubric total, highest first.
- Put the total and a one-clause reason in each option's `description`, e.g.
  `"78% confidence — fastest to ship, weakest test coverage"`.
- Label the top option's `label` with `(Recommended)` per the tool's own convention.
- If step 3 ran, prefix the recommended option's description with `Panel pick — `.

```text
AskUserQuestion({
  questions: [{
    question: "Which caching approach should we use?",
    header: "Caching",
    options: [
      { label: "Redis (Recommended)", description: "82% confidence — Panel pick — proven, adds infra dependency" },
      { label: "In-memory LRU",        description: "61% confidence — zero infra, lost on restart" },
      { label: "File-based",           description: "40% confidence — simplest, slowest, fine only for low traffic" }
    ],
    multiSelect: false
  }]
})
```

### 5. Act on the answer

Proceed with the user's pick, not necessarily your top score — the point of
asking is that they can override it.

## Anti-Patterns

- Running the full `council` panel for every choice — that's for close or
  high-stakes calls only; most picks are a one-pass self-score.
- Silently cutting candidates down to 4 without telling the user — use the
  tournament rounds (step 1) instead so every candidate gets seen.
- Deciding for the user and reporting the decision instead of asking, when the
  whole point was operator input.

## Related Skills

- `council` — the expert-panel escalation path used in step 3
- `ask-questions-if-underspecified` — for clarifying missing requirements, not
  choosing among known options
