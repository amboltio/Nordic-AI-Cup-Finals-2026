"""Helpers for reading the state and checking your moves.

``parse_state`` turns the raw (6, 10, 4) matrix into named lists with the
padding removed, ``is_cell_free`` is the game's own walkability rule, and
``validate_moves`` checks your answer at least as strictly as the evaluation
service does.
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from dtos import (
    CARRYING, CASHBAGS, DROPSPOTS, GRID_HEIGHT, GRID_WIDTH, LEGAL_MOVES,
    N_MOVES, N_ROBBERS, OBSTACLES, ROBBERS, SCROOGES,
)

Point = Tuple[int, int]
Box = Tuple[int, int, int, int]


@dataclass
class GameState:
    # Always five entries, in robot order: robbers[i] goes with carrying[i]
    # and with moves[2 * i], moves[2 * i + 1].
    robbers: List[Point]
    carrying: List[int]
    # Only the ones currently on the map; inactive slots are dropped.
    scrooges: List[Point]
    cashbags: List[Point]
    dropspots: List[Point]
    # (x, y, w, h). An obstacle covers x..x+w and y..y+h, both ends included.
    obstacles: List[Box]


def parse_state(state: Sequence[Sequence[Sequence[int]]]) -> GameState:
    """Read the raw state matrix. An inactive slot has x == -1."""
    def active(row: int) -> List[Point]:
        return [(x, y) for x, y, _, _ in state[row] if x != -1]

    return GameState(
        robbers=[(x, y) for x, y, _, _ in state[ROBBERS][:N_ROBBERS]],
        carrying=[slot[0] for slot in state[CARRYING][:N_ROBBERS]],
        scrooges=active(SCROOGES),
        cashbags=active(CASHBAGS),
        dropspots=active(DROPSPOTS),
        obstacles=[tuple(slot) for slot in state[OBSTACLES] if slot[0] != -1],
    )


def is_cell_free(x: int, y: int, obstacles: Sequence[Box]) -> bool:
    """The game's rule for whether a robot or scrooge may stand on (x, y)."""
    if x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT:
        return False
    return not any(
        ox <= x <= ox + w and oy <= y <= oy + h
        for ox, oy, w, h in obstacles
    )


def validate_moves(moves) -> None:
    """Raise ValueError unless moves is ten plain ints in {-1, 0, 1}.

    This is slightly stricter than the service, which may coerce a float or a
    bool into an int before checking. Do not rely on that: send ints.

    A rejected answer is not fatal - the service plays that tick with no moves
    and records an error - but it is a tick thrown away, and it is far easier
    to see why here than in the attempt's error list.
    """
    if not isinstance(moves, (list, tuple)):
        raise ValueError(f'moves must be a list, got {type(moves).__name__}')
    if len(moves) != N_MOVES:
        raise ValueError(
            f'moves must have {N_MOVES} values (dx, dy for each of '
            f'{N_ROBBERS} robots), got {len(moves)}'
        )
    for index, move in enumerate(moves):
        # bool is a subclass of int, but True/False are not moves.
        if isinstance(move, bool) or not isinstance(move, int):
            raise ValueError(
                f'moves[{index}] must be an int, got {type(move).__name__} '
                f'{move!r}'
            )
        if move not in LEGAL_MOVES:
            raise ValueError(
                f'moves[{index}] must be -1, 0 or 1, got {move}'
            )
