"""A greedy baseline: it plays the game sensibly, and it is beatable.

Each robot walks to the nearest cash bag no other robot has claimed, or to the
nearest drop spot once it is carrying anything. When a scrooge gets within
three cells it steps away instead, and when an obstacle is in the way it tries
sliding along one axis. Not always in time - you will see it score and get
caught.

What it does not do, and where your points are:

* plan ahead. It looks one step at a time and only at the nearest target.
* think about how many bags to carry. Drop-offs score n squared, but every bag
  carried slows a robot down. The baseline drops off as soon as it has one.
* route around obstacles. Sliding along one axis gets it stuck in corners.
* coordinate, beyond not sending two robots after the same bag.
* use the immunity a robot gets after it is caught: 100 ticks if it was
  carrying bags, 33 if it was not. The state does not include it, so you have
  to track it yourself.

It is stateless and cheap, so it never comes near the time budget. Replace
``predict`` with your own agent; keep the signature and api.py will serve it.

Run ``python local_playground.py`` to watch it play, and
``python local_playground.py --headless --games 20`` to see what it scores.
"""

from typing import List

from dtos import (
    N_ROBBERS, RobotRobbersPredictRequestDto, RobotRobbersPredictResponseDto,
)
from utils import is_cell_free, parse_state


### CALL YOUR CUSTOM AGENT VIA THIS FUNCTION ###

def predict(request: RobotRobbersPredictRequestDto) -> RobotRobbersPredictResponseDto:
    """Answer one tick with a move for each robot."""
    return RobotRobbersPredictResponseDto(moves=greedy_moves(request.state))


def greedy_moves(state) -> List[int]:
    game = parse_state(state)
    claimed = set()
    moves: List[int] = []

    for index, (x, y) in enumerate(game.robbers):
        carrying = game.carrying[index] > 0

        if carrying and game.dropspots:
            candidates = game.dropspots
        else:
            # Prefer a bag nobody else is heading for; fall back to sharing.
            candidates = [c for c in game.cashbags if c not in claimed] or game.cashbags

        # At tick 0 there are no bags or drop spots yet, so stand still.
        if not candidates:
            moves += [0, 0]
            continue

        target = min(candidates, key=lambda c: abs(c[0] - x) + abs(c[1] - y))
        if candidates is not game.dropspots:
            claimed.add(target)

        dx, dy = _sign(target[0] - x), _sign(target[1] - y)

        # Step away from the nearest scrooge if it is within 3 cells
        # (Chebyshev distance: the number of diagonal-capable moves away).
        threat = min(
            game.scrooges, default=None,
            key=lambda s: max(abs(s[0] - x), abs(s[1] - y))
        )
        if threat is not None and max(abs(threat[0] - x), abs(threat[1] - y)) <= 3:
            dx, dy = _sign(x - threat[0]) or dy, _sign(y - threat[1]) or -dx

        # A move into an obstacle is ignored entirely, so try alternatives.
        for option in ((dx, dy), (dx, 0), (0, dy), (dy, dx), (-dy, -dx)):
            if option != (0, 0) and is_cell_free(x + option[0], y + option[1], game.obstacles):
                dx, dy = option
                break

        moves += [dx, dy]

    assert len(moves) == N_ROBBERS * 2
    return moves


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)
