# decision-picker

A Claude Code skill that turns a list of candidate choices into an interactive
terminal selection: a confidence score per choice, an AI best-guess default,
and an optional senior-expert-panel final call for close or high-stakes
decisions.

Built on two things Claude Code already ships/has installed — no new
dependency:

- **`AskUserQuestion`** (native tool) — renders the terminal multi-choice UI,
  the "(Recommended)" marker, and the free-text "Other" escape hatch.
- **`council`** (skill) — a 4-voice expert panel (Architect/Skeptic/Pragmatist/
  Critic), used as the escalation path for close calls.

See [`.claude/skills/decision-picker/SKILL.md`](.claude/skills/decision-picker/SKILL.md)
for the full workflow, and [`PLAN.md`](PLAN.md) for what's left to build.

## Install

Symlink the skill directory into wherever Claude Code looks for skills:

```bash
# global
ln -s "$(pwd)/.claude/skills/decision-picker" ~/.claude/skills/decision-picker

# or project-local, from inside another project
ln -s /path/to/claude-select/.claude/skills/decision-picker .claude/skills/decision-picker
```

## Status

Phase 0 (repo bootstrap) done. See `PLAN.md` for phases 1-3 (real confidence
scoring, forceable panel mode, >4-option picker).
