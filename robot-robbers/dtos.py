"""The request and response the evaluation service exchanges with your endpoint,
plus the protocol constants.

One request per game tick. The service sends you the current state, you answer
with one move for each of the five robots, and the service plays that move.

The models are deliberately as loose as the service's: a field you do not
expect will not break anything. ``utils.validate_moves`` holds the strict
rules the service applies to your answer.
"""

from typing import List, Optional

from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# Game-loop numbers
# --------------------------------------------------------------------------- #

# TODO(finals): NOT FINAL. These three numbers are still being tuned, and the
# finals will be played with whatever they are when the finals open. They will
# be updated here, in the README and in an announcement on Discord before then.

# Ticks per game. Every game is exactly this long, however fast or slow your
# endpoint is.
N_TICKS = 3000  # TODO(finals): not final

# How long the service waits for one response before it gives up on that tick
# and plays it with no moves.
REQUEST_TIMEOUT_SECONDS = 2  # TODO(finals): not final

# The total time the service will spend waiting for your endpoint over a game.
# Once it is used up, the remaining ticks are played with no moves. 300 s over
# 3000 ticks is 100 ms per tick on average, round trip included.
MAX_AGENT_WAIT_SECONDS = 300  # TODO(finals): not final

# --------------------------------------------------------------------------- #
# The game
# --------------------------------------------------------------------------- #

N_ROBBERS = 5
# moves holds one (dx, dy) pair per robot.
N_MOVES = N_ROBBERS * 2
LEGAL_MOVES = (-1, 0, 1)

GRID_WIDTH = 128
GRID_HEIGHT = 128

# The rows of ``state``, in order.
ROBBERS, SCROOGES, CASHBAGS, DROPSPOTS, OBSTACLES, CARRYING = range(6)
STATE_SHAPE = (6, 10, 4)


class RobotRobbersPredictRequestDto(BaseModel):
    # (6, 10, 4): six rows of ten [x, y, w, h] slots. See the README.
    state: List[List[List[int]]]
    # What the previous tick scored. Sent as a float, always a whole number.
    reward: Optional[float] = None
    # True only on the request for the last tick.
    is_terminal: bool
    # The score so far. Also sent as a float.
    total_reward: Optional[float] = None
    # How many ticks have been played before this one; 0 on the first request.
    game_ticks: int


class RobotRobbersPredictResponseDto(BaseModel):
    # Ten integers in {-1, 0, 1}: [dx0, dy0, dx1, dy1, ..., dx4, dy4].
    moves: List[int]
