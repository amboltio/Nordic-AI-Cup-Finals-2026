"""Play the game in-process, without a server: to watch, to play, to train.

    python local_playground.py                       # watch example.py play
    python local_playground.py --keyboard            # steer robot 0 with the arrow keys
    python local_playground.py --headless --games 20 # score example.py over 20 maps

Headless runs skip HTTP and drawing, so they run far faster than the game
does on the server; that is the mode to train or tune in. The game is the same
one the service plays (``game/environment.py``), and the requests your agent
sees are built the same way, so an agent that does well here does well there -
provided it is fast enough, which only ``local_evaluator.py`` can tell you.
"""

import argparse
import secrets
import statistics
import sys

from dtos import N_TICKS, RobotRobbersPredictRequestDto
from example import predict
from game.environment import RobotRobbersEnv
from utils import validate_moves


def play_game(seed: int, n_ticks: int, render: bool = False,
              keyboard: bool = False) -> int:
    env = RobotRobbersEnv()
    state = env.reset(seed)
    reward = 0
    info = {'total_reward': 0, 'game_ticks': 0}

    for tick in range(n_ticks):
        request = RobotRobbersPredictRequestDto(
            state=state.tolist(),
            reward=reward,
            is_terminal=tick == n_ticks - 1,
            **info,
        )
        moves = list(predict(request).moves)
        validate_moves(moves)

        if keyboard:
            moves[0:2] = arrow_key_move()

        state, reward, _, info = env.step(moves)

        if render:
            env.render()
            if window_closed():
                break

    return int(info['total_reward'])


def arrow_key_move():
    import pygame

    keys = pygame.key.get_pressed()
    dx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
    dy = keys[pygame.K_DOWN] - keys[pygame.K_UP]
    return [int(dx), int(dy)]


def window_closed() -> bool:
    import pygame

    return any(event.type == pygame.QUIT for event in pygame.event.get())


def main() -> int:
    parser = argparse.ArgumentParser(description='Play Robot Robbers locally.')
    parser.add_argument('--seed', type=int, default=None,
                        help='Map seed for the first game. Default: random.')
    parser.add_argument('--ticks', type=int, default=N_TICKS,
                        help=f'Game length (default {N_TICKS}, as on the server).')
    parser.add_argument('--games', type=int, default=1,
                        help='Number of games to play, each on a new map.')
    parser.add_argument('--headless', action='store_true',
                        help='Do not draw anything. Much faster.')
    parser.add_argument('--keyboard', action='store_true',
                        help='Steer robot 0 with the arrow keys; example.py plays the rest.')
    args = parser.parse_args()

    if args.keyboard and args.headless:
        parser.error('--keyboard needs the window; drop --headless.')

    first_seed = args.seed if args.seed is not None else secrets.randbits(128)
    scores = []

    for game in range(args.games):
        seed = first_seed + game
        score = play_game(seed, args.ticks, render=not args.headless,
                          keyboard=args.keyboard)
        scores.append(score)
        print(f'game {game + 1}/{args.games}  seed {seed}  score {score}')

    if len(scores) > 1:
        print(f'\nmean {statistics.mean(scores):.1f}  '
              f'median {statistics.median(scores):.1f}  '
              f'min {min(scores)}  max {max(scores)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
