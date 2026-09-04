# Adversarial design review: `decision-picker` (a Claude Code skill)

You are a principal-level engineer specializing in decision-support systems, LLM
evaluation/calibration, and agent tooling. Be harsh, specific, and concrete.
Do not be agreeable. If a critique point below is wrong or overstated, say so
plainly and explain why.

## What the system is

A "skill" for a coding agent (Claude Code). A skill is a markdown file of
instructions the agent reads and follows; it is NOT executed code. The agent
also has a native `AskUserQuestion` tool that renders a terminal multi-choice
menu (max 4 options per question, each option has a `label` and a one-line
`description`, plus a free-text "Other" escape hatch).

Purpose: user provides N candidate options; the skill scores each, shows a
recommended default, optionally escalates to an "expert panel", and asks the
user to pick via `AskUserQuestion`.

## Full current source

### `.claude/skills/decision-picker/SKILL.md` (the actual behavior; prose)

Workflow steps:
1. **Normalize choice list** into label + one-line description. If >4 candidates,
   run rubric on all, then use `tournament.py build_round()` to split into groups
   of <=4 (ranks spread evenly across groups), one `AskUserQuestion` per group,
   winners feed into next round until <=4 remain, then final pick.
2. **Score each choice** on 4 criteria (0-100 each), get weighted total from
   `score_choice()`. Sort desc. Top = best-guess default. Keep sub-scores visible.
3. **Escalate to panel** via `should_escalate()`: true if top two totals within 15
   points, OR high_stakes flag, OR user message contains a force phrase. If
   escalating, invoke the `council` skill (a 4-voice panel:
   Architect/Skeptic/Pragmatist/Critic — all four voices are the SAME underlying
   model role-playing). Fold panel arguments back into sub-scores and re-total.
4. **Present via AskUserQuestion**: order by total desc, put total + one-clause
   reason in description, e.g. `"78% confidence — fastest to ship, weakest test
   coverage"`. Label top option `(Recommended)`. Prefix with `Panel pick — ` if
   step 3 ran.
5. **Act on the answer** — user's pick, not necessarily the top score.

### `scripts/rubric.py`

```python
"""Claude still assigns each sub-score by judgment (0-100 per criterion) — this
module only fixes the criteria and weights so the total is reproducible."""
from typing import Mapping

CRITERIA_WEIGHTS = {
    "fit_to_constraints": 0.40,
    "reversibility": 0.25,
    "evidence_strength": 0.20,
    "precedent": 0.15,
}

def score_choice(sub_scores: Mapping[str, float]) -> float:
    """Weighted total (0-100) from per-criterion sub-scores (0-100 each)."""
    missing = CRITERIA_WEIGHTS.keys() - sub_scores.keys()
    if missing:
        raise ValueError(f"missing sub-scores: {sorted(missing)}")
    return round(sum(sub_scores[k] * w for k, w in CRITERIA_WEIGHTS.items()), 1)

def rank_choices(choices: Mapping[str, Mapping[str, float]]) -> list[tuple[str, float]]:
    scored = [(label, score_choice(sub)) for label, sub in choices.items()]
    return sorted(scored, key=lambda pair: pair[1], reverse=True)

def demo() -> None:
    # asserts "Redis" ranks first on hardcoded fixture sub-scores
    ...
```

### `scripts/panel_trigger.py`

```python
CLOSE_CALL_MARGIN = 15.0
FORCE_PHRASES = ("run the panel", "second opinion", "get the panel", "convene the council")

def user_forced_panel(user_message: str) -> bool:
    text = user_message.lower()
    return any(phrase in text for phrase in FORCE_PHRASES)

def should_escalate(ranked_scores: list[float], high_stakes: bool = False,
                    user_message: str = "") -> bool:
    if user_forced_panel(user_message): return True
    if high_stakes: return True
    if len(ranked_scores) >= 2:
        if abs(ranked_scores[0] - ranked_scores[1]) <= CLOSE_CALL_MARGIN: return True
    return False
```

### `scripts/tournament.py`

```python
MAX_GROUP = 4

def build_round(ranked):
    """Chunk score-sorted list into groups of <=4, round-robin so each group
    mixes ranks evenly instead of first group being all top scorers."""
    n_groups = -(-len(ranked) // MAX_GROUP)
    groups = [[] for _ in range(n_groups)]
    for i, item in enumerate(ranked):
        groups[i % n_groups].append(item)
    return groups

def simulate_to_single_winner(ranked, pick_fn=lambda g: max(g, key=lambda p: p[1])):
    """Round-by-round reduction to one winner. pick_fn is the user's
    AskUserQuestion answer for that round in real use."""
    current = list(ranked)
    while len(current) > MAX_GROUP:
        current = [pick_fn(group) for group in build_round(current)]
    if len(current) > 1: return pick_fn(current)[0]
    return current[0][0]
```

Each module has a `demo()` with asserts, run manually via `python3 scripts/X.py`.
There is no test runner, no CI, no packaging (no pyproject.toml, no __init__.py).

## The 7 critique points to validate or refute

1. **False precision.** The rubric is a correct weighted sum over
   *uncalibrated* LLM self-assigned sub-scores. No anchor definitions per
   criterion/band, no few-shot calibration, no self-consistency check. Presenting
   "82% confidence" to a user invites automation bias on a number with no error
   bars. Proposed fix: add per-criterion behavioral anchors, or drop percentages
   for ordinal bands.

2. **Panel is not independent.** `council` is one model role-playing 4 personas.
   Shared blind spots, shared priors. Multi-agent debate literature suggests gains
   come from diversified *information/tools*, not self-role-play. Presenting a
   "panel verdict" launders a single opinion.

3. **Force-phrase substring matching is worse than nothing.** Hand-built keyword
   NLU inside a system whose host IS an NLU. "Can you get someone else to weigh
   in?" silently fails to match. Fix: delete the list, let the model judge intent.

4. **Tournament seeding defect.** Round-robin spreads ranks across groups, then
   keeps only ONE winner per group. True #1 and #2 land in different groups by
   design, so #2 can die in round 1 to a weaker field. Single-elimination
   without seeding/byes/consolation. Fix: don't eliminate; carry top-K by score
   forward and use groups only to shrink the user-facing question size.

5. **No enforcement, only demos.** `score_choice()` never validates 0-100 range;
   a 0-1 fraction or a 150 silently corrupts the total. Range checks live only
   inside `demo()`, which only ever sees its own fixture.

6. **Zero integration testing.** All "self-checks" test pure functions in
   isolation. Nothing tests whether the agent actually FOLLOWS the 5-step
   protocol in a live session — which is the only failure mode that matters for
   a prose-driven skill.

7. **Packaging/portability.** SKILL.md references `scripts/rubric.py` by relative
   path with no declared interpreter/version. Install instructions symlink the
   skill elsewhere, so cwd won't be the skill dir and `python3 scripts/rubric.py`
   breaks.

## What to produce

Answer in markdown, tight and concrete. No preamble.

### A. Verdict per critique point
For each of the 7: `VALID` / `PARTIALLY VALID` / `INVALID`, severity
(Critical/High/Medium/Low), one-paragraph justification, and the **final
correct fix** you would ship (concrete: name the mechanism, not "consider
adding X"). Where relevant cite specific state-of-the-art practice, papers, or
industry standards by name.

### B. What the critique MISSED
The most important problems in this design that the 7 points do not name.
Rank by severity. Be specific to THIS system.

### C. Is the premise sound?
Should this system exist in this shape at all? If you would restructure it
fundamentally rather than patch 7 issues, say what and why. If the current
shape is right, say that.

### D. Minimum viable fix set
If only 3 changes could ship, which 3, and what does each buy?
