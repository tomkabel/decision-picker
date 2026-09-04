"""Phase 3 (first line): reduce >4 rubric-ranked choices to a single pick via
chained AskUserQuestion rounds instead of silently pre-filtering to top 4.

Groups ranked choices into rounds of <=4, has the user pick a winner per
group each round, and repeats on the winners until <=4 remain for a final
pick. This module only computes the round groupings; the actual
AskUserQuestion calls and user picks happen in the skill workflow.
"""

from typing import Sequence

MAX_GROUP = 4


def build_round(ranked: Sequence[tuple[str, float]]) -> list[list[tuple[str, float]]]:
    """Chunk a score-sorted list into groups of <=MAX_GROUP, so each group
    mixes ranks evenly (best/worst distributed) instead of the first group
    being all top scorers and the last all bottom scorers."""
    n_groups = -(-len(ranked) // MAX_GROUP)  # ceil div
    groups: list[list[tuple[str, float]]] = [[] for _ in range(n_groups)]
    for i, item in enumerate(ranked):
        groups[i % n_groups].append(item)
    return groups


def needs_tournament(num_choices: int) -> bool:
    return num_choices > MAX_GROUP


def simulate_to_single_winner(
    ranked: Sequence[tuple[str, float]],
    pick_fn=lambda group: max(group, key=lambda pair: pair[1]),
) -> str:
    """Drive the round-by-round reduction to one winner. `pick_fn` chooses
    the winner of a group; defaults to highest score, but in real use this
    is the user's AskUserQuestion answer for that round."""
    current = list(ranked)
    while len(current) > MAX_GROUP:
        current = [pick_fn(group) for group in build_round(current)]
    if len(current) > 1:
        return pick_fn(current)[0]
    return current[0][0]


def demo() -> None:
    ranked = [(f"choice-{i}", 100 - i) for i in range(9)]  # choice-0 is best
    assert needs_tournament(len(ranked)) is True
    assert needs_tournament(4) is False

    round1 = build_round(ranked)
    assert len(round1) == 3
    assert all(len(g) <= MAX_GROUP for g in round1)
    assert sum(len(g) for g in round1) == 9

    winner = simulate_to_single_winner(ranked)
    assert winner == "choice-0", f"expected choice-0 to win, got {winner}"
    print("tournament self-check passed:", winner)


if __name__ == "__main__":
    demo()
