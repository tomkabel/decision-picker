"""Phase 2: decide whether to escalate to the `council` expert panel.

Default is no escalation (single self-pass rubric score is enough). Escalate
when the top two scores are close, the decision is flagged high-stakes, or
the user explicitly forces it — the force flag overrides everything else.
"""

CLOSE_CALL_MARGIN = 15.0

FORCE_PHRASES = (
    "run the panel",
    "second opinion",
    "get the panel",
    "convene the council",
)


def user_forced_panel(user_message: str) -> bool:
    text = user_message.lower()
    return any(phrase in text for phrase in FORCE_PHRASES)


def should_escalate(
    ranked_scores: list[float],
    high_stakes: bool = False,
    user_message: str = "",
) -> bool:
    if user_forced_panel(user_message):
        return True
    if high_stakes:
        return True
    if len(ranked_scores) >= 2:
        top, second = ranked_scores[0], ranked_scores[1]
        if abs(top - second) <= CLOSE_CALL_MARGIN:
            return True
    return False


def demo() -> None:
    # close scores -> escalate even with no force phrase, not high-stakes
    assert should_escalate([80, 70]) is True
    # clear winner, low-stakes, no force phrase -> no escalation
    assert should_escalate([90, 40]) is False
    # clear winner but user explicitly asks for a second opinion -> override
    assert should_escalate([90, 40], user_message="can I get a second opinion?") is True
    # clear winner but flagged high-stakes -> escalate anyway
    assert should_escalate([90, 40], high_stakes=True) is True
    print("panel_trigger self-check passed")


if __name__ == "__main__":
    demo()
