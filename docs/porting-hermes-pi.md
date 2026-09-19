# Porting decision-picker to Hermes and pi

Analysis of what `claude-select` depends on, and how to build the equivalent
for Hermes Agent (Nous Research) and pi (badlogic's pi-mono coding agent,
v0.84.4, verified installed at `~/.pi`).

The core finding up front: **the porting surface is small and exactly
identifiable.** `rubric.py` is stdlib-only Python with a stdin-JSON/stdout
contract, a `--json` mode, and a self-logging `--log` mode — it is
platform-independent; the port required exactly one field addition to it
(`timed_out`, see below). `fixtures.json` and the protocol assertions in
`check_trace.py` are platform-neutral (they assert on the decision log and the
composed ask, not on any Claude-specific structure). Only three things are
actually Claude-coupled:

1. **The interactive ask tool** (`AskUserQuestion`) — used once, in step 4.
2. **Skill-relative script paths** (`${CLAUDE_SKILL_DIR}`) and the
   `allowed-tools` pre-approval pattern.
3. **The live eval driver** (`claude -p --output-format stream-json`).

Everything else — framing, hard-constraint exclusion, anchor bands, per-
criterion scoring order, escalation rules, anti-laundering (`RESCORE_TO_
DISMISS`), the audit log — is prose and Python that carry over verbatim.

**Status of this document:** v2, post-remediation. The rubric change, the
union SKILL.md, the eval adapter layer, and the scoped driver commands
described here are **implemented and verified** in this repo. The remaining
open items are marked **[unverified]** — they name the exact check that must
run before the claim becomes fact.

---

## Platform-by-platform mapping

| Claude Code construct | Hermes equivalent | pi equivalent |
|---|---|---|
| Skills dir `.claude/skills/` | `$HERMES_HOME/skills/<category>/<name>/` (user-local via `skill_manage create`; in-repo via `write_file` per hardline standard) | `~/.pi/agent/skills/<name>/` (global, trusted by default); project `.pi/skills/` loads only after project trust |
| `${CLAUDE_SKILL_DIR}` | No env var; SKILL.md resolves its scripts from the skill's own reported base dir (Hermes surfaces `skill_dir` when the skill loads); the touchdesigner peer uses `${HERMES_HOME:-$HOME/.hermes}/skills/<category>/<name>/scripts/...` | `{baseDir}` placeholder as used by installed pi skills (e.g. `burpsuite-project-parser`), or a stable absolute path: `$HOME/.pi/agent/skills/decision-picker/scripts/rubric.py` — global skills live at a fixed path |
| `AskUserQuestion` (≤4 options, `(Recommended)`, `Other` row, `multiSelect`) | **`clarify` tool** — structural match: 1–5 questions, ≤4 choices, first choice is auto-marked `(Recommended)`, an `Other` free-text row is auto-appended, `multi_select` supported | **None built-in.** pi ships only read/bash/edit/write/powershell(+grep/find/ls). Requires a small **pi extension** (TypeScript) registering a custom tool that renders via `ctx.ui` (`select` / `confirm` / `input` / `custom`) — the extensions doc lists "interactive tools (questions, wizards, custom dialogs)" as a first-class use case |
| `allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/rubric.py:*)` | No per-skill tool pre-approval in frontmatter; Hermes gates tools via global approval modes. Drop the field; keep the exact heredoc invocation form so any prefix-based permission rule the user sets still matches | `allowed-tools` exists but is experimental and is a **space-delimited tool-name list** — it can pre-approve `bash`, not a specific command. Weaker granularity; acceptable |
| `claude -p --output-format stream-json` | `hermes chat -q "<prompt>" --oneshot --format stream-json` (verified flags; verified live: one-shot stream-json emits JSONL on **stdout** as FLAT events — `{"type":"text","text":...}` and `{"type":"tool_use","name":...,"input":...}` — ending with a `{"type":"result"}` event carrying `text` and `session_id`; captured 2026-09-18, hermes 0.21.3. **Not** Claude-shaped assistant envelopes — the eval adapter must normalize). Session state persists in Hermes' SQLite store (`~/.hermes/state.db`), **not** `~/.hermes/sessions/*.jsonl` — that earlier claim was wrong. The eval parses stdout, not session files. **Pin cwd with `--in "$PWD"`** — one-shot Hermes does not inherit the invoking shell's cwd (known pitfall: wrong-repo commits) | `pi -p --mode json --no-session` per scenario, or `--session-dir <tmpdir>` + parse the session JSONL (format verified: `type: message`, `message.role`, `message.content[]` blocks; version 3) |
| Skill preloading for the eval | `hermes chat -s decision-picker` (the `-s/--skills` flag preloads, bypassing description-trigger unreliability) | `pi --skill <path>` (repeatable; additive even with `--no-skills`) — also `--tools`/`--exclude-tools` to pin the toolset deterministically |
| `/panel` slash opt-in | Hermes has in-session slash commands; a skill cannot register one. Treat the literal text `/panel` in the user message as the deterministic opt-in — it arrives as a normal user message either way | The **extension registers it properly**: `pi.registerCommand("panel", ...)` — cleanest mapping of the three |
| `council` skill (optional escalation) | `council` exists in Hermes' skill catalog — same caveat prose carries over unchanged | `council` exists in `~/.pi/agent/skills/` (ECC origin) — same |
| Headless ask-availability ceiling | `clarify` in headless `hermes chat -q` faces the same problem `AskUserQuestion` has in `claude -p` — the eval must keep using decision-log ground truth, exactly as the Claude eval already does (this ceiling is already documented and designed around in PLAN.md) | Same: in `-p` mode there is no TTY, so the extension's UI cannot render; eval ground truth stays `$DECISION_PICKER_LOG` |
| `claude plugin validate` | Hermes in-repo validation script (`tools/skill_manager_tool.py::_validate_frontmatter`) + hardline review (description ≤60 chars — see below) | pi validates leniently against the Agent Skills spec at load: warnings, not failures |

---

## Hermes port — design

**Target:** `~/.hermes/skills/productivity/decision-picker/` (user-local) or
`skills/productivity/decision-picker/` if contributed upstream to the
hermes-agent repo.

### What changes

1. **Frontmatter must be rewritten to the Hermes authoring standard.** The
   hardline rules are much stricter than Claude's: `description` ≤60 chars,
   one sentence, ends with a period, no marketing words (the current
   Claude description is ~400 chars of trigger prose — Hermes' system-prompt
   index truncates at 57 chars, so the long form buys nothing there anyway).
   Required union shape (this is the **implemented** frontmatter — validated
   against both `claude plugin validate .claude/skills` (passes) and the
   Hermes `_validate_frontmatter` logic (passes; description 55 chars, 5
   under the 60 limit — headroom matters, a description at exactly the
   limit breaks on the first copy edit):
   ```yaml
   ---
   name: decision-picker
   description: Choose between options with a scored, ask-first rubric.
   allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/rubric.py:*)
   version: 0.2.0
   author: Tom Kristian Abel (tkabel), Hermes Agent
   license: MIT
   platforms: [linux, macos, windows]
   metadata:
     origin: custom
     hermes:
       tags: [Decisions, MCDA, AskUser]
       related_skills: [council]
   ---
   ```
   Note the description leads with trigger words (choose/options), not
   mechanism vocabulary — the first ~57 chars are the routing signal.
   `related_skills` must resolve to skills that exist in the same tree —
   `council` does in the Hermes catalog (verified) and in
   `~/.pi/agent/skills/` (verified); re-verify in-repo before an upstream PR.

2. **Step 4 (presentation) swaps `AskUserQuestion` → `clarify`.** Direct
   structural mapping, with three adaptations:
   - Recommended option goes **first** in `choices[]` (position is the
     marker; there is no label field to edit).
   - The overflow line ("also available via Other: E, F, G") goes in the
     question body — `clarify` auto-appends the `Other` row, so the prose
     just names the candidates.
   - The steelman/fragility/self-generation disclosures go in the question
     text, same as the Claude version.

3. **Handle `clarify` timeouts.** This is not hypothetical: this user
   regularly times out on clarify prompts during autonomous runs. The
   default branch is **block and surface**: present the ranking, the band,
   and the runner-up case in the final message, state that you are waiting
   for a choice, and end the turn with the ask open. Never re-ask, and
   never proceed — proceeding with the recommendation is "deciding for the
   user and reporting the decision," the exact anti-pattern the skill's
   anti-patterns section forbids. The only exception is an explicitly
   autonomous run (headless eval, cron, pre-authorised "pick on
   timeout"): proceed with the recommendation, say plainly that no user
   answer existed, and log it as `pick: null, timed_out: true` so the
   `.decisions.log` record distinguishes *asked-and-never-answered* from
   *never asked*. **Implemented:** `rubric.py --log` now accepts and
   records `timed_out` in the payload (a timed-out run closes the record:
   `kind: decision` with `pick: null`), and SKILL.md's step 4 carries this
   policy. The earlier claim that the port needed zero rubric.py changes
   was wrong — this one field is the delta.

4. **Script invocation path.** Instruct the agent to resolve the skill's own
   directory (Hermes reports it when the skill loads) and run
   `python3 <skill-dir>/scripts/rubric.py` with the same heredoc payload
   contract. Alternatively pin the absolute path
   `${HERMES_HOME:-$HOME/.hermes}/skills/productivity/decision-picker/scripts/rubric.py`
   — user-local skills have a stable location, and profiles relocate via
   `$HERMES_HOME` automatically. Prefer the absolute form: it cannot be
   misresolved by a model guessing relative paths from the project cwd.

5. **Live eval driver.** Implemented in `check_trace.py` as
   `_hermes_adapter` behind `--driver hermes`:
   ```
   hermes chat -q "<scenario>" --oneshot --format stream-json \
     -s decision-picker -t terminal,file,clarify --in <scenario-cwd>
   ```
   Deliberately **no `--yolo`** and toolset-scoped via `-t`: the scenario set
   contains a literal `rm -rf /tmp/x` injection candidate, and the eval must
   be able to *observe restraint*, not depend on it — an unscoped agent that
   executes the injection is a FAIL the harness must survive to report.
   `--in` is mandatory for the same reason the memory entry exists: one-shot
   Hermes resolves cwd from its own session, not the invoking shell.
   Tool-call trace parsing reads the stdout JSONL (verified live; see the
   mapping table). The `$DECISION_PICKER_LOG` ground-truth mechanism is
   unchanged — that is the point of having built it around the script rather
   than the harness.

6. **Body conventions.** Hermes review requires commands framed through
   Hermes tools (`terminal`, `read_file`, `patch`), no machine-local paths,
   modern section order, and — for an upstream PR — a test file at
   `tests/skills/test_decision_picker_skill.py` plus the docs-generator
   regen with scope discipline.

### Hermes-specific risk

The `allowed-tools` pre-approval is a friction control the Claude version
explicitly ships. Hermes has no per-skill equivalent, so on permissioned
configurations every rubric call may prompt once. Mitigation: one line in
the skill telling the user how to allowlist the exact invocation, plus the
eval measuring call-count per decision (already assertable from the log).
Note the interaction with the eval driver: because the live driver pins
`-t terminal,file,clarify` rather than `--yolo`, the eval *can* observe
permission-related friction; under `--yolo` (the earlier proposal) it
structurally could not — nothing would ever prompt, so the "measure
call-count" mitigation would have been unmeasurable.

---

## pi port — design

**Target:** `~/.pi/agent/skills/decision-picker/` + one extension, installed
the way pi actually loads extensions: `pi install ./path/to/extension`
(registers it in pi's settings and tracks it for `pi update` / `pi list`),
**not** a magic auto-discovered `~/.pi/agent/extensions/` directory — that
directory does not exist on this machine and pi's docs describe no such
discovery mechanism (the earlier layout claimed it did). A git-hosted
source (`pi install git:github.com/<user>/<repo>`) is the long-term shape
once the extension has a repo of its own; the local-path form is fine for
development. Extension code lives in this repo at
`extensions/decision-picker.ts` (single file while it stays small;
directory with `index.ts` + `package.json` if it grows).

### What changes

1. **The ask tool must be built.** This is the largest single engineering
   item in either port (the eval adapters are the other; the earlier
   "only real engineering" framing undersold them). pi's extension API
   keeps it contained: register a tool
   (typebox schema mirroring the AskUserQuestion shape — `questions[]`,
   `label`, `description`, `multiSelect`), and in `execute` render with
   `ctx.ui.select()` for single-choice or a custom component for the full
   menu. Requirements the Claude version gets for free, which the extension
   must provide explicitly:
   - recommended marker (prefix the first option's label with
     `(Recommended)`, matching the convention across harnesses);
   - free-text `Other` path (`ctx.ui.input()` when Other is chosen) — the
     un-scored-candidate handling in step 5 depends on this escape hatch
     existing;
   - timeout behavior (define it — see Hermes above; pi's `ui.confirm`
     supports timeout/signal, and the timed-confirm example shows the
     pattern).

2. **`/panel` becomes a real command.** `pi.registerCommand("panel", ...)`
   in the same extension — the deterministic opt-in that the v2 plan insisted
   on keeping maps cleanly, better than the other two ports where it is just
   a recognized string.

3. **Script paths.** Use the `{baseDir}` placeholder convention observed in
   installed pi skills (`{baseDir}/scripts/burp-search.sh` in
   `burpsuite-project-parser`), falling back to the stable absolute path
   `$HOME/.pi/agent/skills/decision-picker/scripts/rubric.py` for global
   installs. pi's docs also bless "relative paths from the skill directory".
   pi loads skills from `~/.agents/skills/` too — if the skill is deployed
   there for multi-harness sharing, prefer `{baseDir}`.

4. **Frontmatter.** pi implements the Agent Skills standard leniently:
   `name` + `description` required, unknown fields ignored (so the Hermes
   fields and Claude's `allowed-tools` can coexist in one file). `allowed-
   tools: bash` is accepted but experimental and tool-name-granular — state
   in the skill that the rubric invocation is `bash`-based so users know
   what a tool allowlist means here.

5. **Live eval driver.** Implemented in `check_trace.py` as `_pi_adapter`
   behind `--driver pi`:
   ```
   pi -p --mode json --no-session --skill <skill-dir> --tools read,bash -- "<scenario>"
   ```
   Tool calls are read from the driver's JSON-mode stdout; ground truth is
   `$DECISION_PICKER_LOG`, identical division of labor to the other two
   drivers. `--tools read,bash` pins the toolset (rubric.py needs only bash
   + file reads) — same restraint rationale as the Hermes driver: the
   scenario set contains an `rm -rf` injection candidate and the eval must
   survive an agent that tries to execute it. `--skill` loads the SKILL.md
   content directly, bypassing description-trigger unreliability; the
   `/skill:decision-picker` interactive command exists for users and is
   worth a README line. **Pin the model** (`--model` / `PI_EVAL_MODEL`):
   pi's default-model resolution scans environment API keys, so inside a
   Hermes session it resolves `HERMES_CUSTOM_API_*` keys to a provider that
   errors instantly (`stopReason:"error"`, empty assistant content, exit 0)
   — observed live on the first full pass (0/45 rubric runs, vacuous
   "clean" verdicts).
   **Verified** (captured 2026-09-18, pi 0.84.4, `--mode json`): tool calls
   are `{"type":"tool_execution_start","toolCallId":...,"toolName":...,
   "args":{...}}`; assistant text arrives via `{"type":"message_end",
   "message":{"role":"assistant","content":[{"type":"text",...}]}}` (with
   `turn_end`/`agent_end` repeating the same messages — parse `message_end`
   only, 1:1). The adapter normalizes both to the Claude-shaped internal
   form and raises on a session-header-only stream (vacuous-trace guard).

6. **Skill loading reliability.** pi's docs warn models don't always read
   the SKILL.md even when the description matches; `/skill:decision-picker`
   forces it. The eval should therefore invoke with `--skill <path>` (loads
   content directly), and the README for the pi port should tell users the
   command exists.

### pi-specific risk

- Project-local deploys (`.pi/skills/`) are gated on project trust
  (`--approve`); recommend the global install for a decision aid.
- The extension runs with full system permissions; the skill's
  injection-hardening prose (candidate text is data) matters more, not less,
  because the extension adds a second executable surface. Keep the
  extension to rendering + returning the pick; no logic in TypeScript that
  rubric.py doesn't already own.

---

## Sharing one source across all three

The three frontmatter dialects are compatible enough for a **single
SKILL.md** with a union frontmatter — **verified on both validators**, not
assumed: `claude plugin validate .claude/skills` passes with the Hermes
fields present (run 2026-09-18), and Hermes' `_validate_frontmatter`
requires only `name`/`description` + non-empty body and tolerates the rest
(read from `tools/skill_manager_tool.py`; source-verified). Two things
prevent a fully literal single file:

1. **Presentation step** differs per harness (AskUserQuestion vs `clarify`
   vs the extension tool). Solve with one short "Present the ask" section
   containing a three-row harness matrix plus the shared invariants
   (≤4 options, first/recommended, Other is a new candidate, no numbers,
   disclosures in the body). All the harness-independent rules stay single-
   sourced.
2. **Hermes' 60-char description hardline** (if contributing upstream).
   A short description is fine on Claude and pi too — trigger richness can
   move to the body's "When to Use" section, which is where pi/Claude models
   read it anyway.

**Deployment layout** — one canonical repo; registration, not symlinks:

```
claude-select/.claude/skills/decision-picker        (source of truth, as now)
~/.hermes: skills.external_dirs -> .claude/skills   (config registration)
~/.pi/agent/skills/decision-picker                   (pi settings skills[] or copy)
pi extension: pi install <path-or-git-source>       (registered, not dropped in a dir)
```

**Why not symlinks** (this reverses the earlier draft, which claimed "Hermes
follows symlinks fine"): Hermes has *two* scanners with different semantics.
The runtime loader (`skill_utils.iter_skill_index_files`) uses
`os.walk(followlinks=True)` and does follow symlinks — but `skill_manage` /
`skill_view` discovery (`_iter_skill_dirs`) uses `Path.rglob("SKILL.md")`,
and pathlib `rglob` does **not** descend into symlinked directories
(verified empirically on Python 3.11 and 3.14). A symlinked skill would load
but be invisible to `skill_manage` patch/write_file — the "verify
skill_manage sees it" step of the old plan would have half-failed on
execution. `skills.external_dirs` registration (verified working:
`_find_skill('decision-picker')` resolves through it, and the live smoke
run below found and executed the skill) has no such split: one config entry,
all scanners see it, and the repo stays the single source of truth.

pi supports the equivalent: `settings.json` `skills[]` pointing at external
directories, which avoids a copy; a plain copy is acceptable if settings
sync is undesirable (the skill is small and rubric.py is the contract).

**Deployment verification (Hermes)** — run live, not assumed:
- `claude plugin validate .claude/skills` → passes (union frontmatter).
- Hermes `_validate_frontmatter` logic on the union file → passes; description 55 chars, 5 under the 60-char new-skill limit.
- `skills.external_dirs` registration → `_find_skill('decision-picker')` resolves.
- `check_trace.py --live --driver hermes --only clear-winner` → the driver ran
  end-to-end: skill invoked 1/1, rubric.py executed, decision log written,
  recommendation produced. The run surfaced a real protocol violation
  (`ESCALATION_WHEN_CONTESTED` — the model treated a clear-winner scenario
  as contested), which is the eval doing its job on a new harness, not a
  harness defect. A full gate pass across the scenario set is the remaining
  acceptance criterion (see "Acceptance gates" below).

**Eval harness**: one `check_trace.py`, harness-neutral protocol assertions
(they read the decision log and lint the composed ask — never a
harness-specific event shape), with the live driver factored into three
adapters behind `--driver claude|hermes|pi` (implemented: `_claude_adapter`,
`_hermes_adapter`, `_pi_adapter`; each is subprocess + parse, model
selectable via `CLAUDE_EVAL_MODEL` / `HERMES_EVAL_MODEL` / `PI_EVAL_MODEL`).
The protocol-break gate, Wilson interval, and `--repeat` self-agreement
logic are driver-independent. Adapters fail loudly on driver-level errors
(unknown skill, bad flags) instead of silently scoring an empty trace —
that silent-zero case occurred during development and read as a false
clean verdict before it was fixed.

## Acceptance gates (a port is DONE when these pass — not before)

Each driver earns trust by the same standard, enforced by the same script:

| gate | criterion | command |
|---|---|---|
| G1 offline | 26/26 fixture checks, unchanged | `check_trace.py` (already green) |
| G2 unit | rubric validation/gating/ranking incl. `timed_out` logging | `test_rubric.py` (already green, 26 tests) |
| G3 claude live | protocol-break rate Wilson-hi ≤ 10% over the full scenario set | `check_trace.py --live --driver claude --repeat 3` |
| G4 hermes live | same gate on the Hermes CLI, with skill registered via `skills.external_dirs` | `check_trace.py --live --driver hermes --repeat 3` |
| G5 pi live | same gate on the pi CLI, with extension installed via `pi install` | `check_trace.py --live --driver pi --repeat 3` |
| G6 union frontmatter | `claude plugin validate` + Hermes frontmatter check both pass on the one SKILL.md | (already green; re-run in CI) |
| G7 timeout honesty | a timed-out ask logs `pick: null, timed_out: true` and the record reads `kind: decision` | covered in G2; live-path spot-check with one deliberately unanswered run |

Current state (2026-09-18, live full passes): G1, G2, G6 green; G7
green (unit + live-path spot-check: `pick: null, timed_out: true, kind:
decision`). The pi extension is written and `pi install`ed; the pi
tool-call event shape is captured and the adapter rewritten to the real
shape.

Full-pass verdicts (45 runs each, genuine model deviations — the eval
doing its job, not harness bugs; three harness bugs were found and fixed
en route and the affected attempts voided, see above):

- **G3 claude (opus-4-5): FAIL 42.2%** [29.0%, 56.7%], 40/45 rubric
  invocations, 84.4% self-agreement. Dominated by `ESCALATION_WHEN_
  CONTESTED` — skipping escalation on `not-separable` /
  `unverified-evidence` verdicts. Model resolution was broken during
  this run (`--model` dead → opus default, not the documented sonnet);
  fixed, numbers stand as the opus run.
- **G4 hermes (glm-5.2:speed): FAIL 20.0%** [10.9%, 33.8%], 45/45 rubric
  invocations, 82.2% self-agreement. Previous run (glm-5.3:speed) was
  13.3%; the copy-paste finding is gone (placeholder fix landed in
  `0f459c5`), but glm-5.2 surfaces a different violation mix:
  `ESCALATION_WHEN_CONTESTED` (2), `NO_PERCENT` (2),
  `NO_INVENTED_OPTIONS` (1), `RECOMMENDED_MATCHES_TOP` (3),
  `RESCORE_TO_DISMISS` (1). The `RECOMMENDED_MATCHES_TOP` cluster is
  new — the model's rubric-payload recommended label doesn't match its
  own top-ranked candidate in the composed menu. 9/45 violations.
- **G5 pi (glm-5.2:speed): FAIL 8.9%** [3.5%, 20.7%], 45/45 rubric
  invocations, 88.9% self-agreement. Previous run (glm-5.3:speed) was
  15.6%; the copy-paste finding is gone (placeholder fix landed). 4/45
  violations: `ESCALATION_WHEN_CONTESTED` (2),
  `RESCORE_TO_DISMISS` (1), `NO_INVENTED_OPTIONS` (1), `NO_PERCENT` (1).
  Self-agreement improved (88.9% vs 93.3% — within noise).

The copy-paste finding that spanned G4+G5 on glm-5.3 is **resolved**:
the placeholder-ized examples in SKILL.md (`0f459c5`) eliminated it on
both harnesses. Both gates still FAIL the 10% CI gate, but on genuine
model deviations, not harness bugs.

Remaining: G3 re-run on the documented default model; investigate the
`RECOMMENDED_MATCHES_TOP` cluster (G4-only, 3 violations — the model's
rubric payload recommends one label but its composed menu ranks a
different one first).

## What does NOT port (documented, don't re-solve)

- The `claude plugin validate` CI step → Hermes: its validator script;
  pi: load-time warnings only.
- The `RESCORE_TO_DISMISS` anti-laundering rule, anchor bands, stability
  resampling, label sanitisation, `.decisions.log` schema — all live in
  rubric.py and are untouched by any of this.
- The headless "cannot observe a real ask" ceiling exists on **all three**
  harnesses; the decision-log ground-truth design already accounts for it.
