"""Play a full game against your endpoint, the way the evaluation service does.

This is the service's game loop: the same environment, the same request
payloads, the same tick count, the same per-request timeout and the same
total wait budget. A tick whose answer is late, malformed or illegal is played
with no moves, exactly as on the server. Use it to find out whether your
server holds up for a whole game before you spend your one evaluation attempt
finding out.

    python local_evaluator.py                      # a random map, like validation
    python local_evaluator.py --seed 30738956785357439708437121904581776564  # replay a validation game
    python local_evaluator.py --render             # watch it (needs pygame)
    python local_evaluator.py --simulate-latency-ms 60

Every validation attempt reports its seed in the attempt's error list, so you
can replay a game you did badly on. Given the same seed and the same moves,
this reproduces the server's game exactly, on any OS.

``--simulate-latency-ms`` adds a delay to every request and counts it against
the budget, which is the cheap way to find out how much network distance your
agent can afford.
"""

import argparse
import secrets
import statistics
import sys
import time
from typing import List, Optional

import requests

from dtos import (
    MAX_AGENT_WAIT_SECONDS, N_MOVES, N_TICKS, REQUEST_TIMEOUT_SECONDS,
    RobotRobbersPredictRequestDto,
)
from game.environment import RobotRobbersEnv
from utils import validate_moves

DEFAULT_URL = 'http://localhost:9055/predict'
# The service shows at most this many errors per attempt.
MAX_ERRORS_SHOWN = 15


def build_request(state, reward, is_terminal: bool, info: dict) -> dict:
    """The payload the service sends, field for field."""
    return RobotRobbersPredictRequestDto(
        state=state.tolist(),
        reward=reward,
        is_terminal=is_terminal,
        **info,
    ).model_dump()


def ask_agent(session: requests.Session, url: str, request: dict,
              simulate_latency: float) -> List[int]:
    """One request. Raises ValueError with the reason the tick was lost."""
    if simulate_latency:
        time.sleep(simulate_latency)
    try:
        response = session.post(url, json=request, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f'HTTP error: {exc}')

    try:
        body = response.json()
    except ValueError:
        raise ValueError('the response is not JSON')

    if not isinstance(body, dict) or 'moves' not in body:
        raise ValueError(f'the response has no "moves" field: {body!r:.200}')

    validate_moves(body['moves'])
    return body['moves']


def wait_for_endpoint(url: str, attempts: int = 30) -> bool:
    """Poll the server root until it answers."""
    root = url.rsplit('/', 1)[0] if url.count('/') > 2 else url
    for attempt in range(attempts):
        try:
            requests.get(root, timeout=2)
            return True
        except requests.RequestException:
            if attempt == 0:
                print(f'Waiting for {root} ...')
            time.sleep(1)
    return False


def play(url: str, seed: int, n_ticks: int, render: bool,
         simulate_latency: float, verbose: bool) -> int:
    env = RobotRobbersEnv()
    state = env.reset(seed)
    reward = 0
    info = {'total_reward': 0, 'game_ticks': 0}
    no_moves = [0] * N_MOVES

    errors: List[str] = []
    latencies: List[float] = []
    agent_wait = 0.0
    budget_spent_at: Optional[int] = None
    session = requests.Session()

    for tick in range(n_ticks):
        moves = no_moves

        if agent_wait < MAX_AGENT_WAIT_SECONDS:
            request = build_request(state, reward, tick == n_ticks - 1, info)
            started = time.perf_counter()
            try:
                moves = ask_agent(session, url, request, simulate_latency)
            except ValueError as exc:
                errors.append(f'Tick {tick}: {exc}')
            finally:
                elapsed = time.perf_counter() - started
                agent_wait += elapsed
                latencies.append(elapsed)

            if agent_wait >= MAX_AGENT_WAIT_SECONDS:
                budget_spent_at = tick
                errors.append(
                    f'Agent wait budget of {MAX_AGENT_WAIT_SECONDS} seconds '
                    f'exceeded at tick {tick}; remaining ticks played with '
                    f'no moves.'
                )

        state, reward, _, info = env.step(moves)

        if render:
            env.render()
        if verbose and reward:
            print(f'tick {tick}: reward {reward:+d}, total {info["total_reward"]}')
        elif tick % 500 == 0 and not verbose:
            print(f'tick {tick:>5}/{n_ticks}  total reward {info["total_reward"]:>5}  '
                  f'budget used {agent_wait:6.1f}/{MAX_AGENT_WAIT_SECONDS} s')

    score = int(info['total_reward'])
    report(score, seed, n_ticks, errors, latencies, agent_wait, budget_spent_at)
    return score


def report(score: int, seed: int, n_ticks: int, errors: List[str],
           latencies: List[float], agent_wait: float,
           budget_spent_at: Optional[int]) -> None:
    print()
    print(f'Score:        {score}')
    print(f'Seed:         {seed}')
    print(f'Ticks:        {n_ticks}')

    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        print(f'Round trip:   mean {statistics.mean(latencies) * 1000:.1f} ms, '
              f'p95 {p95 * 1000:.1f} ms, max {ordered[-1] * 1000:.1f} ms')

    print(f'Wait budget:  {agent_wait:.1f} of {MAX_AGENT_WAIT_SECONDS} s used')
    if budget_spent_at is not None:
        print(f'              RAN OUT at tick {budget_spent_at}: the rest of '
              f'the game was played with no moves.')
    elif agent_wait > 0.8 * MAX_AGENT_WAIT_SECONDS:
        print('              Close to the limit. The service is further away '
              'than localhost, so expect to run out there.')

    print(f'Errors:       {len(errors)}')
    for error in errors[:MAX_ERRORS_SHOWN]:
        print(f'  {error}')
    if len(errors) > MAX_ERRORS_SHOWN:
        print(f'  ... and {len(errors) - MAX_ERRORS_SHOWN} more. The service '
              f'only shows the first {MAX_ERRORS_SHOWN}.')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Play one game against your endpoint, like the evaluation service.'
    )
    parser.add_argument('--url', default=DEFAULT_URL, help='Your predict endpoint.')
    parser.add_argument('--seed', type=int, default=None,
                        help='Map seed. Default: a random one, like validation.')
    parser.add_argument('--ticks', type=int, default=N_TICKS,
                        help=f'Game length (default {N_TICKS}, as on the server).')
    parser.add_argument('--render', action='store_true',
                        help='Draw the game while it runs (needs pygame).')
    parser.add_argument('--simulate-latency-ms', type=float, default=0,
                        help='Extra delay per request, counted against the budget.')
    parser.add_argument('--verbose', action='store_true',
                        help='Print every tick that scored.')
    args = parser.parse_args()

    if not wait_for_endpoint(args.url):
        print(f'Could not reach {args.url}. Is `python api.py` running?')
        return 1

    seed = args.seed if args.seed is not None else secrets.randbits(128)
    play(args.url, seed, args.ticks, args.render,
         args.simulate_latency_ms / 1000, args.verbose)
    return 0


if __name__ == '__main__':
    sys.exit(main())
