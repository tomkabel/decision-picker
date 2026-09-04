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
`label` + one-line `description` pairs. 2-4 options per question — `AskUserQuestion`
caps at 4. If there are more than 4, pre-filter to the top 4 by your own judgment
and say what got cut.

### 2. Score each choice

For each candidate, assign a confidence score (0-100%) yourself: how likely this
is the right call given the stated goal and constraints. Do this in one pass,
no subagents — it's your own estimate, not a panel verdict yet.

Sort descending. The top score is your **best-guess default**.

### 3. Escalate to a panel only when it's close or high-stakes

Skip this step by default. Run it only if:
- the top two scores are within ~15 points of each other, or
- the decision is expensive to reverse (architecture, public API, spend, irreversible data ops)

If escalating, invoke the `council` skill with the choice list as the decision
question. Take its verdict's recommendation and re-score: bump the panel's pick
up, note dissent in that option's description.

### 4. Present via AskUserQuestion

One call, one question (or up to 4 if there are independent sub-decisions).
- Order options by score, highest first.
- Put the score and a one-clause reason in each option's `description`, e.g.
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
- Inventing more than 4 options to fill the UI — `AskUserQuestion` supports 2-4,
  not "as many as exist."
- Deciding for the user and reporting the decision instead of asking, when the
  whole point was operator input.

## Related Skills

- `council` — the expert-panel escalation path used in step 3
- `ask-questions-if-underspecified` — for clarifying missing requirements, not
  choosing among known options
