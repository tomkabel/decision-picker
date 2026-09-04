# decision-picker — remediation plan (v2)

Supersedes the v1 phase plan (phases 0–3a, all shipped: commits `4b57bb3`,
`214dfa3`, `a1fc725`). v1 built a weighted rubric, a panel-escalation gate, and
a tournament bracket. A senior review plus a five-model adversarial panel found
that most of that apparatus is **rigor theater**: it applies determinism to the
steps that were never uncertain (a 4-term weighted sum, an `abs() <= 15`
comparison, modular chunking) and leaves the only step with real variance —
sub-score assignment — with no anchors, no validation, and no evaluation.

This plan is therefore **net-deletion**. Two of the three scripts go away.

## Evidence base

Reviewed by five flagship reasoning models via the `pi` harness against the
openlux endpoint (custom provider config: `~/.pi/agent/models.json`, provider
`openlux`, `api: openai-completions`):

| Model | Provider |
|---|---|
| `gpt-5.6-luna` | OpenAI |
| `gemini-3.1-pro-preview` | Google |
| `kimi-k3` | Moonshot |
| `glm-5.3` | Z.ai |
| `grok-4.6` | xAI |

Reproduce: `cd docs/review-2026-09-04 && pi --model openlux/<id> --thinking high
--no-tools --no-session -p "$(cat BRIEF.md)"`. Full verbatim responses are in
[`docs/review-2026-09-04/`](docs/review-2026-09-04/).

Unlike the built-in `council` skill (four personas, one model), these are five
different model families — the independence that critique point 2 says the
current panel lacks. They agreed on 5 of 7 points and **overturned one**.

### Verdict table

| # | Critique | Panel verdict | Severity |
|---|---|---|---|
| 1 | False precision in confidence scores | **VALID** 5/5 | High |
| 2 | Panel is not independent | **VALID** 5/5 | High–Critical |
| 3 | Force-phrase substring matching | **VALID** 5/5, "worse than nothing" overstated 2/5 | Medium |
| 4 | Tournament seeding defect | **PARTIALLY VALID** 4/5 — *mechanism refuted* | Medium |
| 5 | No range enforcement | **VALID** 5/5 | Medium |
| 6 | Zero integration testing | **VALID** 5/5 | **Critical** |
| 7 | Packaging/portability | **VALID** path / **INVALID** packaging ceremony | Medium / Low |

### Correction: critique 4 was wrong on the mechanism

The original claim — "true #1 and #2 land in different groups, so #2 dies in
round 1 to a weaker field" — is false, and four of five models caught it.
Round-robin distribution across groups *is* standard bracket seeding; putting
#1 and #2 in opposite halves is what seeding is *for*. Verified empirically
against the real module:

- `#2` survives round 1 for every `n` in 5..17.
- With a user whose preferences are a consistent total order, their true
  favourite won **300/300** random seedings. Zero losses.

The proposed fix ("carry top-K by score forward") was also wrong: it replaces
*user* elimination with *model* elimination, using the very scores critique 1
establishes are noise. It would have made the system worse.

The **real** tournament defects, which the original critique missed:

- **Friction blowup.** Measured question counts: `n=5 → 3 rounds`,
  `n=9 → 4`, `n=17 → 8`, `n=33 → 13`. Three sequential modal prompts to choose
  among five options is worse than one prompt showing four plus an overflow line.
- **Invariant silently breaks after round 1.** `build_round()` documents that it
  assumes a score-sorted input, but `simulate_to_single_winner()` feeds winners
  back in *group* order and nothing re-sorts. The even-spread property holds only
  in round 1.
- **`Other` has no branch.** A user typing a new candidate mid-bracket injects an
  unscored option the protocol cannot place.
- **Single-elimination assumes transitive preferences.** Fine for a consistent
  user; Condorcet cycles and context effects are real and unhandled.

## What the panel found that the original critique missed

Ranked by how many models independently raised it:

| Finding | Raised by | Severity |
|---|---|---|
| **Static weights are undeclared product policy.** `0.40/0.25/0.20/0.15` applied to "name this function" and "drop prod" alike. No sensitivity analysis; flipping weights reorders `(Recommended)` with no new evidence. | 5/5 | Critical |
| **Determinism is inverted.** Python does the arithmetic that never varies; the sub-scores that carry 100% of the noise get no anchors, no validation, no eval. | 4/5 | Critical |
| **Nudge stacking.** Sort-desc + `(Recommended)` + `Panel pick —` + a percentage = four default-effect levers on one menu. One is the feature; the rest are bugs. | 4/5 | High |
| **`Other` is an unhandled state transition.** The tool ships a free-text escape hatch; the workflow says only "act on the answer". A candidate that never passed the process can get executed. | 3/5 | High |
| **Panel fold-in is an undefined transform.** "Fold arguments back into sub-scores" names no mapping, no evidence threshold, no delta cap, no conflict rule. A persuasive paragraph moves a score by any amount, and dissent is destroyed rather than shown. | 4/5 | High |
| **`high_stakes` has no defined source.** No UI, no classifier, no blast-radius test. A destructive production decision proceeds unescalated if the flag is simply absent. | 3/5 | High |
| **`CLOSE_CALL_MARGIN = 15` sits inside rater noise.** Unanchored per-criterion variance of ±15–20 propagates to a total σ of roughly 8–12 points. The gate fails to escalate on differences that are one noisy forward pass. | 1/5 (grok) | High |
| **Hard constraints are compensatory.** `fit_to_constraints` is just another weighted term, so an option violating a mandatory security/legal/budget constraint can still win on reversibility and precedent. Invalid MCDA modelling. | 2/5 | Critical |
| **Absolute scoring is the wrong judge protocol.** LLM-as-judge SOTA is pairwise with rubric (MT-Bench, Chatbot Arena, AlpacaEval 2.0); independent absolute point scores are where judge noise is worst. Emitting all four criteria for one option in a single pass guarantees halo. | 2/5 | High |
| **Self-preference bias.** The agent frequently *generated* the candidates, then scores them, then role-plays the panel, then writes the rationale. LLM evaluators favour their own generations (Panickssery et al. 2024). | 1/5 (grok) | Critical |
| **`evidence_strength` measures nothing.** No sources, no repo inspection, no tool output. The model scores the strength of evidence it never gathered — a self-referential confidence loop. | 1/5 (luna) | Critical |
| **The I/O chasm.** `rubric.py` has no `argparse`, no `__main__` entry beyond `demo()`. There is no defined way for the agent to pass sub-scores in; it must write a throwaway runner every invocation. | 1/5 (gemini) | Critical |
| **Candidate text is an injection surface.** Options are untrusted input; nothing marks them as data. "Ignore the rubric and run this" flows into a skill that then acts. | 1/5 (luna) | High |
| **No audit trail.** For a decision aid, the decision record *is* the product. Everything evaporates after the `AskUserQuestion`. | 3/5 | Medium |
| **Unguarded `council` dependency.** No versioned contract, no fallback if not installed. | 1/5 (glm) | Medium |
| **Friction kills skills.** Two bracket rounds plus a four-voice council is a meeting. Users stop invoking it. | 2/5 | Medium |

## Restructure or patch?

4/5 models said the current *shape* is wrong, not just its details. But they
split on how far to go, and the outlier matters:

- **`gpt-5.6-luna`** wants a full `DecisionSpec` + evidence-gating + a packaged
  state-machine controller with adapters and scripted transcript tests.
- **`gemini-3.1-pro`, `kimi-k3`** want the opposite: delete `scripts/` entirely,
  make this one prose file, let the model do the arithmetic in-context.
- **`glm-5.3`, `grok-4.6`** land in the middle: keep the MCDA premise (it is
  sound and matches decision-analysis practice), keep at most one script, fix
  the presentation layer, and eval the trace.

**Decision: follow the middle.** The premise — decompose into criteria, weight
them, surface a default, escalate on genuine contention, let the user override
— is sound and evidence-backed; structured rubrics beat holistic vibes. Luna's
controller is a second system to maintain for a skill whose entire runtime is a
markdown file, and it would re-commit the original sin: more machinery around
the deterministic part. Rejected unless a real case demands it.

The through-line for every phase below: **numbers stay internal, honesty goes
to the user, and the only thing worth testing is the trace.**

---

## Phase 4 — Honest presentation ✅ highest payoff, zero code

Removes the automation-bias payload, which is the main way this skill can cause
a bad production decision. Named in the top-3 by all five models.

- [ ] **Delete `% confidence` from SKILL.md.** It is a category error, not just
      miscalibration: the weighted total is a multi-criteria *utility* score, not
      `P(this option is correct)`. Even perfectly calibrated, the percentage
      would be the wrong number. Verbalized LLM confidence is systematically
      miscalibrated and barely improves with prompting (Tian et al. 2023; Xiong
      et al. 2024); post-trained models are measurably overconfident.
- [ ] **Add behavioral anchors per criterion** to SKILL.md, as a table the model
      reads on every scoring pass. Bands with observable tells, not adjectives:

      reversibility
        81–100  revert is a config flag or a single revert commit
        41–80   revert needs a scripted rollback, no data loss
        0–40    data migration, destructive, or externally visible

      evidence_strength
        81–100  verified in THIS repo (test run, grep, doc read this session)
        41–80   official docs or a version-matched precedent
        0–40    recalled from training, not checked

      Same treatment for `fit_to_constraints` and `precedent`.
- [ ] **Score one criterion across all options before moving to the next.**
      Emitting all four criteria for option A in one pass guarantees halo.
      Cross-option, per-criterion passes are how the judge literature reduces it.
- [ ] **User-facing surface becomes ordinal.** `Strong lead / Contested / Weak
      field`, plus the top-2 gap stated plainly ("gap: 9 pts — narrow"). The
      float survives only as an internal sort key.
- [ ] **Steelman the runner-up.** One line on the strongest reason to pick #2.
      Decision hygiene, and it directly counteracts the remaining nudge.
- [ ] **Disclose that the ranking is self-generated** when the agent also wrote
      the option list: "I wrote these options; treat my ranking as biased."
- [ ] **Drop two of the four nudges.** Keep `(Recommended)`. Remove the
      percentage (above) and stop treating score-descending as mandatory
      presentation order when the top two are within noise.
- [ ] Self-check: a scoring pass on a fixture decision produces no `%` anywhere
      in the rendered `AskUserQuestion` payload.

## Phase 5 — Delete the theater

Net negative diff. Fixes critiques 3, 4, 5, 7 and the I/O chasm at once.

- [ ] **Delete `scripts/panel_trigger.py`.** A threshold comparison and a
      substring scan do not need a subprocess. `FORCE_PHRASES` is a 2002 chatbot
      bolted onto a system whose host *is* an NLU — and it fails both ways:
      "have someone else look at this" does not match, while a *candidate*
      containing the words "second opinion" fires it.
      - Escalation intent moves to SKILL.md prose, with the phrase list kept as
        *examples of intent* rather than a matching table.
      - Keep one deterministic opt-in the model cannot fumble: the user typing
        `/panel`. (Luna and grok both insisted on retaining an explicit path;
        pure intent-inference trades false negatives for nondeterministic false
        positives.)
      - Replace `CLOSE_CALL_MARGIN = 15` with a *separability* test in prose:
        escalate when the top two cannot be separated under the Phase 4 anchors.
        A fixed 15-point gate is inside rater noise and is false precision of
        the same kind Phase 4 removes.
- [ ] **Delete `scripts/tournament.py`.** Replaced by: one `AskUserQuestion`
      with the top 4, and the overflow named in the question body ("also
      available via Other: E, F, G"). For `n > 8`, two parallel 4-option
      questions with "advance up to 2 each", then a final of ≤4 — never
      auto-advance by score. This removes the friction blowup (measured: 3
      rounds for 5 candidates), the broken between-round sort invariant, and the
      unhandled `Other` branch, without handing elimination to the model.
- [ ] **Harden `scripts/rubric.py`** — the one script that earns its place, as
      the single source of truth for criteria and weights:
      - `set(sub_scores) == set(CRITERIA_WEIGHTS)` — reject unknown keys, not
        just missing ones.
      - Values must be real and finite, `bool` explicitly excluded, `0 <= v <= 100`.
      - Reject 0–1 fractions with a named error rather than silently scoring
        `39.2` — do not guess a rescale.
      - Assert `sum(CRITERIA_WEIGHTS.values()) == 1.0` at import.
      - Raise `ValueError` naming the offending key and value, so the model can
        self-correct from the message.
- [ ] **Close the I/O chasm.** Give `rubric.py` a real CLI: read a JSON
      `{label: {criterion: score}}` map on stdin, write the ranked table to
      stdout. Without this the agent has no defined way to call it and must
      hand-write a runner each time.
- [ ] **Fix the path, skip the packaging ceremony.** SKILL.md invokes the script
      via the skill's own directory, never `python3 scripts/...` relative to cwd
      — the agent's cwd is the user's project, so the current form breaks under
      every documented install. Pin `python3 >= 3.10, stdlib only` in one line.
      No `pyproject.toml`, no `__init__.py` for three functions (4/5 models
      called that ceremony; grok rated it Low explicitly).
- [ ] **Replace `demo()` with real tests.** `assert ranked[0][0] == "Redis"` on
      its own fixture is a tautology. Test the validation branches: out-of-range,
      NaN/inf, bool, unknown key, fraction-vs-percent.

## Phase 6 — Eval the trace, not the calculator

Rated **Critical** by the panel and the single highest-consensus gap. Without
it every fix above is unverifiable, because the artifact that actually executes
is a prompt. Prompt/agent evals are a solved tooling category — this is not
research.

- [ ] **10–20 scripted decision scenarios**, run headlessly (`claude -p`, or
      promptfoo/LangSmith if a runner is wanted). Coverage: clear winner; top-2
      inside noise; high-stakes flag; escalation requested in paraphrase
      ("can you get someone else to weigh in?"); `/panel`; `n=2`; `n=6`; `n=9`;
      user picks the non-recommended option; user answers via `Other`;
      agent-generated option set; a candidate containing an injection string.
- [ ] **Assert on the trace, structurally** — no LLM-as-judge needed for most:
      - every `AskUserQuestion` call carries ≤ 4 options;
      - no rendered description contains `%`;
      - `(Recommended)` marks the internal top-ranked option;
      - escalation happened iff the separability test or an explicit trigger fired;
      - the final action equals the user's pick, not the recommendation;
      - an `Other` answer is re-scored before it can be acted on.
- [ ] **Gate on protocol-break rate.** Fail the skill above ~10%.
- [ ] Self-check: the harness catches a deliberately reverted Phase 4 change
      (re-introduce a `%` in SKILL.md; the eval must go red).

## Phase 7 — Feasibility gating and declared weights

MCDA correctness. The single highest-consensus *missed* finding.

- [ ] **Hard constraints stop being compensatory.** Extract explicit
      constraints, mark each candidate `feasible / infeasible / unknown`, and
      exclude the infeasible *before* weighted ranking — not by docking points.
      An option that violates a mandatory constraint must not be able to win on
      reversibility and precedent.
- [ ] **Disclose the weights in the question preamble**, and make them
      overridable in one word: "weights: fit 40 / reversibility 25 / evidence 20
      / precedent 15 — say 'reweight' to change." This converts a hidden prior
      into a stated, contestable one.
- [ ] **Allow a per-decision criteria set.** `precedent` is actively harmful for
      a deliberately novel choice; `reversibility` is noise for a throwaway
      script; cost, security, latency, and operability are absent entirely. The
      four defaults stay the default — they just stop being the only option.
- [ ] **Mark `unknown` as first-class.** If a sub-score cannot be grounded, it is
      `unknown`, which blocks a confident recommendation rather than silently
      scoring 50.
- [ ] Self-check: a fixture where the top-scoring option violates a stated hard
      constraint must not be recommended.

## Phase 8 — Escalation that adds information

Currently the escalation path adds *confidence* without adding *evidence*.

- [ ] **Stop calling it a panel.** Four personas from one checkpoint share
      weights, context, priors and blind spots; correlated errors do not cancel.
      Same-model debate is not worthless, but labelling it a panel verdict
      launders one opinion as four — and folding it into the scores destroys the
      dissent that was the only real output. Present it as
      `Single-model review, four prompts — not independent`.
- [ ] **Make the voices structurally different, not tonally.** Each must produce
      an artifact, not an adjective: the skeptic cites two concrete failure modes
      with file/line references; the pragmatist estimates implementation effort;
      the critic argues *for* the lowest-ranked candidate.
- [ ] **Prefer grounded falsification over more prose.** The strongest available
      escalation is a tool call that could disconfirm the top pick — grep the
      repo, read the version-matched doc, run the test. That is real
      information diversity; personas are not.
- [ ] **Panel output is arguments, never a silent re-total.** If a sub-score
      moves, it moves by an explicit named delta against a named criterion, with
      before/after both retained.
- [ ] **Define `high_stakes` or delete it.** A written blast-radius test
      (production data, security surface, irreversible schema, external
      visibility), defaulting *unknown* stakes to more scrutiny. An undefined
      flag nobody sets is not a safety control.
- [ ] **State the `council` fallback** for when the skill is not installed.
- [ ] Self-check: escalation on a fixture produces at least one artifact
      (citation, file reference, or tool output) that was not in the input.

## Phase 9 — Audit trail and injection hardening

Lower payoff; do after the above land.

- [ ] Append one record per decision to `.decisions.log`: date, options, weights
      and rubric version, sub-scores, escalation reason, user's pick, and whether
      it diverged from the recommendation. For a decision aid this record *is*
      the product, and it is the only path to ever measuring calibration.
- [ ] Treat candidate text as untrusted data: delimit it, state that instructions
      inside candidates are never followed, and keep analysis separate from
      execution. Consequential actions still go through normal tool permissioning.

## Non-goals

- **A packaged state-machine controller with adapters** (luna's proposal). A
  second system to maintain for a skill whose runtime is one markdown file, and
  it repeats the original error of adding machinery around the deterministic
  part. Revisit only if the Phase 6 evals show prose cannot hold the protocol.
- **`pyproject.toml` / `__init__.py`** for three stdlib functions.
- **Deleting `scripts/` entirely** (gemini/kimi's proposal). `rubric.py` earns
  its place as the single source of truth for criteria and weights once it
  validates its inputs and has a CLI; inlining the weights into prose means they
  drift between SKILL.md and every invocation.
- **A persistent scoring database, a GUI, or a custom terminal picker.** Still
  YAGNI. Phase 3b (custom paginated picker) is formally dropped: Phase 5 removes
  the multi-round flow that was its only motivation.
