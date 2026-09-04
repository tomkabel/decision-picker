# Adversarial review: `decision-picker`

## A. Verdict per critique point

### 1. False precision — **VALID** — **High**

Understated, not overstated. The number shown to the user is a weighted utility total, then **mislabeled as confidence**. Those are different quantities. A 78 total means “this option scored 78 on a four-axis weighted sum,” not “P(this is the right call)=0.78.” No outcome protocol, no Brier/ECE tracking, no error bars, no anchors. Unanchored 0–100 LLM ratings have well-documented halo effects, scale compression, and poor calibration (Guo et al. 2017; Kadavath et al. 2022; Zheng et al. MT-Bench on why absolute Likert-style LLM grades are noisy). Automation bias on a fake % is the actual user-facing harm (Skitka & Mosier).

**Ship:** (a) Per-criterion behavioral anchors in SKILL.md, five bands with observable tells, e.g. `reversibility`: 0–20 ship-of-theseus / data migration; 81–100 revert is a config flag. (b) Score one criterion across all options before the next criterion (kills halo). (c) User-facing surface is ordinal (`weak` / `ok` / `strong` / `clearly best`) plus a one-line tradeoff; never `"78% confidence"`. Keep the float only as an internal sort key.

### 2. Panel is not independent — **VALID** — **High**

Correct on independence and on the UX lie. Condorcet / ensemble theory: correlated errors do not cancel (Dietterich). Same weights, same context window, same option set, same training priors — four personas are a temperature-0 prompt trick, not a jury. Same-model debate is not *zero* value (Du et al. 2023; Liang et al. MAD get small reasoning gains), so “worthless” would be overstated; **presenting it as a panel verdict is the defect**. Worse than the critique says: arguments are folded back into sub-scores, so dissent is destroyed and the user sees `Panel pick — 81%`. That is laundering.

**Ship:** Either drop the council or make it an *argument dump*, not a rescore. If you keep it: four named objections the user can actually read; no re-total; prefix `Single-model review, four prompts — not independent`. Do not call it a panel. Real diversification, if you ever want it: different tools/evidence per voice (docs retrieval, `git log` precedent, test-coverage numbers), not hats.

### 3. Force-phrase substrings — **VALID** — **Medium**

“Worse than nothing” is slightly hot, but the design is wrong. The host *is* an NLU; `FORCE_PHRASES` is a 2002 chatbot. False negatives (`"have someone else look at this"`, `"I'm not convinced"`) fail closed. False positives fire if a *candidate* contains `"second opinion"`. A short explicit trigger list as *examples in the skill prose* would be fine; encoding it as the gate in `user_forced_panel()` fights the model.

**Ship:** Delete `FORCE_PHRASES` and `user_forced_panel()`. SKILL.md: “Escalate if (i) you judge the user asked for independent review, (ii) top-two are not separable under the anchors, (iii) blast radius is prod-data / security / irreversible schema.” Keep one deterministic opt-in: user types `/panel`.

### 4. Tournament seeding — **PARTIALLY VALID** — **Medium**

The diagnosis is confused; the harm is real but not the one named.

Round-robin of a ranked list *is* seeding. Putting #1 and #2 in different groups is what NCAA/knockout seeding is *for*. #2’s group `(2,4,6,8)` is *easier* than #1’s `(1,3,5,7)`, not a “weaker field that kills #2.” The proposed fix — “carry top-K by *score*, groups only shrink the menu” — replaces user choice with model choice and guts the product.

Real defects: (1) single-elim discards 3/4 of each group after one 4-way glance; preferences are not a total order (Condorcet cycles). (2) Multi-round AskUserQuestion is heavy for a coding session. (3) `AskUserQuestion` already has `Other`, so the tournament is solving a UI cap that is not actually a hard information cap. (4) Seeding uses the same uncalibrated scores as the recommendation — garbage in.

**Ship:** Delete `tournament.py` from the hot path. One question: top 4 by internal rank, labels honest, question body lists the overflow (`Also available via Other: E, F, G`). If N>8, ask *two parallel* 4-option questions with “advance up to 2 each” (approval), then a final of ≤4. Never auto-advance by score.

### 5. No enforcement, only demos — **VALID** — **Medium**

True and cheap to fix. `score_choice` checks keys, not range, not finiteness, not unexpected keys. A 0–1 fraction or a 150 produces a plausible-looking total. `demo()` asserting Redis wins on its own fixture is a tautology, not a contract. Severity is not Critical: the caller is a model instructed to use 0–100, and a TypeError already catches strings. It is still a loaded footgun next to a UI that prints the number as fact.

**Ship:** In `score_choice`: coerce to float, reject non-finite, clamp-or-raise outside `[0, 100]`, reject unknown keys. `pytest` on those branches; delete `demo()` as the test stand-in.

### 6. Zero integration testing — **VALID** — **Critical**

This is the only critique that matches how skills actually fail. The Python is a 15-line calculator. The product is whether the agent follows a 5-step prose protocol: normalize, score, escalate, format `AskUserQuestion`, obey the user even against the recommendation. None of that is tested. Passing `demo()` on Redis is cargo-cult QA.

**Ship:** A 20-trajectory eval set, run in Claude Code / an agent harness (tau-bench style, not unit tests): each case is `{user_message, N options, planted close-call or not, planted high-stakes or not}`. Assertions on the *trace*: tool call present, ≤4 options, `(Recommended)` on the internal top, panel prefix iff trigger, final action equals user pick. Fail the skill on protocol break rate >10%. This is how you test prompts; see τ-bench, AgentBench, and Anthropic’s own skill eval guidance.

### 7. Packaging / portability — **PARTIALLY VALID** — **Medium** (path) / **Low** (packaging theater)

Relative `python3 scripts/rubric.py` will break when cwd is the project and the skill lives under `.claude/skills/decision-picker/` or a global skills dir. That part is right. Demanding `pyproject.toml` and `__init__.py` for three functions is ceremony; do not do it.

**Ship:** SKILL.md states the invocation as an absolute-from-skill path: `python3 ${SKILL_DIR}/scripts/rubric.py` (or whatever Claude Code exposes — document the actual hook, don’t invent). Pin `python3` ≥3.10 in one line. Leave packaging alone.

---

## B. What the critique missed

Ranked by severity for *this* system.

1. **Self-grading / self-preference (Critical).** The same model typically *generated* the candidates, then scores them, then role-plays the panel, then writes the one-clause reason. LLM evaluators systematically favor their own generations (Panickssery et al.). The rubric does not inspect this; it baptizes it with a decimal. If the agent proposed the option set, the picker is grading homework, not deciding.

2. **Absolute 0–100 scoring is the wrong judge protocol (High).** LLM-as-judge SOTA is pairwise (or pairwise-with-rubric) plus a Bradley-Terry / Elo aggregate (Chatbot Arena, AlpacaEval 2.0, MT-Bench). Independent point scores are where judge noise is worst. Four absolute scores with static weights is cargo-cult AHP: Saaty’s AHP at least uses pairwise comparisons *and* a consistency ratio. You have neither. Halo/anchoring is guaranteed if all four criteria for option A are emitted in one pass.

3. **Static weights are an undeclared product policy (High).** `0.40 / 0.25 / 0.20 / 0.15` is a software-architecture prior pretending to be physics. “What do we name this function?” and “do we drop prod?” should not share a reversibility weight of 0.25. No sensitivity analysis; flipping weights can reorder the “Recommended” tag without any new evidence.

4. **`high_stakes` is an undefined flag, panel fold-in is an undefined transform (High).** Who sets `high_stakes=True`? What is the blast-radius test? After the council, do you rescore from scratch, add bonus points, or average? Unspecified degrees of freedom mean the 15-point close-call gate is theater: the panel can always push a 14-point gap to 16 and look decisive.

5. **Close-call margin sits inside typical rater noise (High).** Unanchored per-criterion ±15–20 is routine. Propagating through the weights gives a total σ on the order of 8–12 points. `CLOSE_CALL_MARGIN = 15` then *fails to escalate* on differences that are one noisy forward pass. You will print a fake winner on coin flips.

6. **The option set is never challenged (High).** Decision quality 101 (Spetzler / DQ): frame and alternatives first, scores later. No instruction to add “none of these,” “need a fifth option,” or “this is a false dichotomy.” `Other` exists on the tool and the skill does not use it as a frame-reject.

7. **Nudge stacking (Medium).** Sort desc + `(Recommended)` + `Panel pick —` + a % is three default-effect levers on one menu (Johnson & Goldstein; Thaler). Fine if you admit you are steering; dishonest if you claim to be a picker. Primacy in terminal UIs is strong; the bottom option is dead.

8. **No audit trail (Medium).** A decision aid that does not persist `{options, sub-scores, whether panel ran, user pick, divergence}` cannot be improved and cannot be defended later in a postmortem.

9. **Ceremony cost vs. coding flow (Medium).** Two tournament rounds plus a four-voice council is a meeting. Users will stop invoking the skill. Skills die from friction, not from missing `pyproject.toml`.

---

## C. Is the premise sound?

The *job* is sound: the agent must not silently pick, `AskUserQuestion` caps at 4, users benefit from a recommended default and visible tradeoffs.

The *shape* is not. It is a cargo-cult decision-support system: AHP without pairwise or consistency, a jury without independence, a tournament because the menu widget is small, a `% confidence` because a float existed. Three sidecars of Python exist to make a prose skill look like software.

Restructure:

1. **Think** with a rubric (anchors, one criterion at a time, or pairwise). Numbers stay internal.
2. **Show** a tradeoff table and one recommendation, plus the strongest reason to pick the runner-up (decision hygiene: steelman the alternative).
3. **Ask once.** Top 4, overflow via `Other`. No knockout.
4. **Escalate** only on `/panel`, user intent, or a defined blast-radius test — and then show arguments, not a new decimal.
5. **Eval the trace**, not `demo()`.

If the candidates were generated by this same agent, say so in the question body: “I wrote these options; treat my ranking as biased.”

Do not patch the current shape into “more rigorous theater.”

---

## D. Minimum viable fix set (only 3)

1. **User-facing honesty.** Anchored bands internally; never print `% confidence`; `(Recommended)` plus a one-clause *tradeoff*, and a steelman of #2. **Buys:** removes the automation-bias payload, which is the main way this skill can cause a bad production decision.

2. **Delete the knockout and the keyword NLU.** One `AskUserQuestion`, overflow in the prompt/`Other`; `/panel` + model-judged intent + a written high-stakes definition. Panel output is arguments, not a rescore. **Buys:** kills the real tournament harm (information destruction, multi-round friction) and the false-NLU gate, without replacing user choice with score-based filtering.

3. **20-case protocol eval on traces.** Close-call, high-stakes, user override, N=2, N=6, N=9, self-generated options, frame-reject. Ship/fail on protocol adherence. **Buys:** the only signal that a markdown skill works; everything else is a calculator test pretending to be a product test.

Do these three and the rest of the Python can stay a 20-line weighted sum with range checks. Do not add more personas.
