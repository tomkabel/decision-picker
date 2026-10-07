# Pull request checklist

Before requesting review, confirm each item:

- [ ] `python3 .claude/skills/tiltrank/scripts/test_rubric.py` passes locally
- [ ] `python3 .claude/skills/tiltrank/scripts/eval/check_trace.py` passes locally
- [ ] No new dependencies introduced (stdlib only — CI enforces this)
- [ ] New behavior has a labelled fixture in `.claude/skills/tiltrank/scripts/eval/fixtures.json`, including a deliberately-broken variant that goes red
- [ ] `claude plugin validate .claude/skills` passes (requires Claude Code installed)
- [ ] CI is green on **both** Python 3.10 and 3.13

## Summary

<!-- What does this PR change and why? -->

## Test evidence

<!-- Paste the tail of both test runs, or note if you couldn't run one (e.g. no Claude Code for plugin validate). -->
