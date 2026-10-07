"""The Robot Robbers game, exactly as the evaluation service runs it.

This is the same environment class the competition uses to play your agent,
minus the replay recording. Read it: every rule in the README comes from this
file, and where the two disagree this file wins.

    from game.environment import RobotRobbersEnv

    env = RobotRobbersEnv()
    state = env.reset(seed=42)
    state, reward, is_done, info = env.step([0] * 10)

``is_done`` is always False. The game itself never ends; the evaluator stops
after a fixed number of ticks (``dtos.N_TICKS``).
"""

import heapq
import numpy as np

from os import path

SPRITE_DIRECTORY = path.join(path.dirname(path.abspath(__file__)), 'sprites')

legal_moves = set((-1, 1, 0))

# The eight steps a scrooge can take, and what each costs in distance.
_STEPS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
_DIAGONAL = np.sqrt(2)


def _sign(v):
    return 1 if v > 0 else -1 if v < 0 else 0

class RobotRobbersEnv:
    def __init__(self) -> None:
        # Game settings
        self.width = 128
        self.height = 128

        self.n_element_types = 5
        self.max_n_elements_per_type = 10
        self.observation_shape = (
            self.n_element_types + 1,
            self.max_n_elements_per_type,
            4
        )

        self.n_robbers = 5
        self.max_n_scrooges = 7
        self.max_n_cashbags = 5
        self.max_n_dropspots = 3
        self.max_n_obstacles = 5
        self._max_obstacle_size = 20
        self._reward_multiplier = 2
        self._scrooge_radius = 15
        self._scrooges_move_interval = 2
        self._robber_cooldown_ticks = 100
        self._no_bag_cooldown_ticks = 33
        self._max_chasers_per_robber = 3

        # Empty world state
        self._robber_positions = np.ones(
            (self.n_robbers, 2), dtype=np.int16) * -1
        self._scrooge_positions = np.ones(
            (self.max_n_scrooges, 2), dtype=np.int16) * -1
        self._cashbag_positions = np.ones(
            (self.max_n_cashbags, 2), dtype=np.int16) * -1
        self._dropspot_positions = np.ones(
            (self.max_n_dropspots, 2), dtype=np.int16) * -1
        self._obstacles = np.ones(
            (self.max_n_obstacles, 4), dtype=np.int16) * -1
        self._cashbag_carriers = np.zeros((self.n_robbers, ), dtype=np.int16)

        self._robber_cooldown = np.zeros((self.n_robbers, ), dtype=np.int16)

        self._reward = 0
        self._total_reward = 0
        self._n_cashbags = 0
        self._n_dropspots = 0
        self._n_scrooges = 0
        self._n_obstacles = 0
        self._game_ticks = 0

        # Rendering
        self.scaling = 8
        self.clock = None
        self.screen = None
        self.surface = None
        self.gfxdraw = None
        self.font = None

        self.robot_sprite = None
        self.scrooge_sprite = None
        self.cashbag_sprite = None
        self.dropspot_sprite = None

        # Seeding
        self.random = None

    def reset(self, seed=None) -> tuple:
        # The map comes from the low 32 bits of the seed.
        # Everything during play (bag and drop spot spawns, scrooge wandering)
        # comes from a second, independent stream derived from the whole seed. 
        seed_sequence = np.random.SeedSequence(seed)
        self.random = np.random.RandomState(seed_sequence.entropy % 2 ** 32)

        # Clear anything left over from a previous game.
        self._robber_positions[:] = -1
        self._scrooge_positions[:] = -1
        self._cashbag_positions[:] = -1
        self._dropspot_positions[:] = -1
        self._obstacles[:] = -1
        self._cashbag_carriers[:] = 0
        self._robber_cooldown[:] = 0
        self._reward = 0
        self._total_reward = 0
        self._n_cashbags = 0
        self._n_dropspots = 0
        self._game_ticks = 0

        self._n_scrooges = self.max_n_scrooges
        self._n_obstacles = self.random.randint(2, self.max_n_obstacles)

        for i in range(self._n_obstacles):
            x, y = self._get_free_cell()
            w, h = self.random.randint(1, self._max_obstacle_size), self.random.randint(
                1, self._max_obstacle_size)
            self._obstacles[i, :] = (x, y, w, h)

        # Scrooges never share a cell, so they start on different ones.
        taken = set()
        for i in range(self._n_scrooges):
            cell = self._get_free_cell()
            while cell in taken:
                cell = self._get_free_cell()
            taken.add(cell)
            self._scrooge_positions[i, :] = cell

        for i in range(self.n_robbers):
            self._robber_positions[i, :] = self._get_free_cell()

        self._pending_dropspots = [
            self._get_free_cell() for _ in range(self.max_n_dropspots)]
        
        play_seed, bag_seed = seed_sequence.spawn(2)
        self._bag_random = np.random.RandomState(np.random.PCG64(bag_seed))
        self.random = np.random.RandomState(np.random.PCG64(play_seed))
        return self._get_observation()

    def is_valid_action(self, actions) -> bool:
        # bool is an int subclass, but True/False are not moves.
        return (
            isinstance(actions, (list, tuple))
            and len(actions) == self.n_robbers * 2
            and all(
                type(move) is int and move in legal_moves
                for move in actions
            )
        )

    def step(self, actions) -> tuple:
        assert self.is_valid_action(
            actions), f'Move instructions must be pairs of {{-1, 0, 1}} but was {actions}'
        self._move_robbers(actions)

        # Check if any robbers are in the same location as cashbags
        for i in range(self.n_robbers):
            rx, ry = self._robber_positions[i]
            for j in range(self.max_n_cashbags):
                cx, cy = self._cashbag_positions[j]

                if rx == cx and ry == cy:
                    self._n_cashbags -= 1
                    self._cashbag_carriers[i] += 1
                    self._cashbag_positions[j] = -1, -1

        # Check if any robbers are in the same location as dropspots
        for dx, dy in self._dropspot_positions:
            for i in range(self.n_robbers):
                rx, ry = self._robber_positions[i]

                if rx == dx and ry == dy:
                    self._reward += int(self._cashbag_carriers[i]) ** self._reward_multiplier
                    self._cashbag_carriers[i] = 0

        # Check if any robbers are in the same location as scrooges
        for sx, sy in self._scrooge_positions:
            for i in range(self.n_robbers):
                rx, ry = self._robber_positions[i]
                has_cashbags = self._cashbag_carriers[i] > 0

                # Give a penalty and take away the cashbag
                if rx == sx and ry == sy and self._robber_cooldown[i] <= 0:
                    self._robber_cooldown[i] = (
                        self._robber_cooldown_ticks if has_cashbags
                        else self._no_bag_cooldown_ticks)

                    if has_cashbags:
                        self._reward -= 3
                        self._cashbag_carriers[i] = 0

        # Move scrooges
        self._move_scrooges()

        n_cashbags_on_screen = int(self._n_cashbags + self._cashbag_carriers.sum())

        if n_cashbags_on_screen < self.max_n_cashbags:
            for ci in range(self.max_n_cashbags):
                cix, ciy = self._cashbag_positions[ci]
                if cix == -1:
                    self._cashbag_positions[ci, :] = self._get_free_cell(
                        self._bag_random)
                    self._n_cashbags += 1

        if self._n_dropspots < self.max_n_dropspots:
            self._dropspot_positions[self._n_dropspots, :] = \
                self._pending_dropspots[self._n_dropspots]
            self._n_dropspots += 1

        episode_reward = int(self._reward)
        self._total_reward = int(self._total_reward + episode_reward)
        self._reward = 0
        self._game_ticks += 1

        for i in range(self.n_robbers):
            if self._robber_cooldown[i] > 0:
                self._robber_cooldown[i] -= 1

        return (
            self._get_observation(),
            episode_reward,
            False,  # Never terminate
            {
                "total_reward": self._total_reward,
                "game_ticks": self._game_ticks
            }
        )

    def render(self, mode=None) -> None:
        try:
            import pygame
            from pygame import gfxdraw
            self.gfxdraw = gfxdraw
            self.pygame = pygame
        except ImportError:
            raise Exception("Please install pygame to use the render method")

        if self.screen is None:
            pygame.init()
            pygame.display.init()
            self.screen = pygame.display.set_mode((
                self.width * self.scaling,
                self.height * self.scaling
            ))

            self.robot_sprite = pygame.transform.scale(
                pygame.image.load(path.join(SPRITE_DIRECTORY, 'robot.png')),
                (self.scaling * 2, self.scaling * 2)
            )

            self.scrooge_sprite = pygame.transform.scale(
                pygame.image.load(path.join(SPRITE_DIRECTORY, 'scrooge.png')),
                (self.scaling * 2, self.scaling * 2)
            )

            self.cashbag_sprite = pygame.transform.scale(
                pygame.image.load(path.join(SPRITE_DIRECTORY, 'cashbag.png')),
                (self.scaling * 1.4, self.scaling * 1.4)
            )

            self.dropspot_sprite = pygame.transform.scale(
                pygame.image.load(path.join(SPRITE_DIRECTORY, 'dropspot.png')),
                (self.scaling * 2, self.scaling * 2)
            )

        if self.font is None:
            pygame.font.init()
            # Any PRs to change this will be rejected
            self.font = pygame.font.SysFont('Comic Sans MS', 30)

        if self.clock is None:
            self.clock = pygame.time.Clock()

        self.surface = pygame.Surface(
            (self.width * self.scaling, self.height * self.scaling))
        self.surface.fill((50, 50, 50))

        for i in range(self.max_n_obstacles):
            self._render_obstacle(i)

        for i in range(self.max_n_scrooges):
            self._render_scrooge(i)

        for i in range(self.n_robbers):
            self._render_robber(i)

        for i in range(self.max_n_cashbags):
            self._render_cashbag(i)

        for i in range(self.max_n_dropspots):
            self._render_dropspot(i)

        self.screen.blit(self.surface, (0, 0))

        # Draw the reward and game time in the top left of screen
        reward_txt = self.font.render(
            f'Reward: {self._total_reward}', False, (0, 0, 0))
        time_txt = self.font.render(
            f'Game ticks: {str(self._game_ticks)}', False, (0, 0, 0))

        self.screen.blit(reward_txt, (30, 30))
        self.screen.blit(time_txt, (30, 60))

        pygame.event.pump()
        self.clock.tick(60)
        pygame.display.flip()

    def _is_cell_free(self, cx, cy):
        # Out of bounds
        if cx < 0 or cx >= self.width or cy < 0 or cy >= self.height:
            return False

        # Inside obstacle
        for x, y, w, h in self._obstacles:
            if cx >= x and cx <= x + w and cy >= y and cy <= y + h:
                return False

        return True

    def _get_free_cell(self, rng=None):
        rng = rng or self.random
        x = rng.randint(0, self.width)
        y = rng.randint(0, self.height)

        while not self._is_cell_free(x, y):
            x = rng.randint(0, self.width)
            y = rng.randint(0, self.height)

        return x, y

    def _get_observation(self):
        observation = np.ones(self.observation_shape, dtype=np.int16) * -1

        for i, (x, y) in enumerate(self._robber_positions):
            observation[0, i, :] = [x, y, 1, 1]

        for i, (x, y) in enumerate(self._scrooge_positions):
            observation[1, i, :] = [x, y, 1, 1]

        for i, (x, y) in enumerate(self._cashbag_positions):
            observation[2, i, :] = [x, y, 1, 1]

        for i, (x, y) in enumerate(self._dropspot_positions):
            observation[3, i, :] = [x, y, 1, 1]

        for i, (x, y, w, h) in enumerate(self._obstacles):
            observation[4, i, :] = [x, y, w, h]

        for i, c in enumerate(self._cashbag_carriers):
            observation[5, i, :] = [c, 0, 0, 0]

        return observation

    def _render_obstacle(self, idx):
        x, y, w, h = self._obstacles[idx]
        gx = x * self.scaling
        gy = y * self.scaling
        gw = (w + 1) * self.scaling
        gh = (h + 1) * self.scaling

        self.gfxdraw.filled_polygon(
            self.surface,
            [(gx, gy), (gx + gw, gy), (gx + gw, gy + gh), (gx, gy + gh)],
            (0, 0, 0)
        )

    def _render_scrooge(self, idx):
        x, y = self._scrooge_positions[idx]
        gx = (x * self.scaling) - self.scaling * .5
        gy = (y * self.scaling) - self.scaling * .5

        self.surface.blit(self.scrooge_sprite, (gx, gy))

    def _render_robber(self, idx):
        x, y = self._robber_positions[idx]
        gx = (x * self.scaling) - self.scaling * .5
        gy = (y * self.scaling) - self.scaling * .5

        self.surface.blit(self.robot_sprite, (gx, gy))

        for i in range(self._cashbag_carriers[idx]):
            robber_cx, robber_cy = (
                gx + self.scaling // 2, gy + self.scaling // 2)
            w = i + 1
            self.gfxdraw.filled_polygon(
                self.surface,
                [(robber_cx - w, robber_cy - w), (robber_cx + w, robber_cy - w),
                 (robber_cx + w, robber_cy + w), (robber_cx - w, robber_cy + w)],
                (255, 255, 0)
            )

    def _render_cashbag(self, idx):
        x, y = self._cashbag_positions[idx]
        gx = (x * self.scaling) - self.scaling * .2
        gy = (y * self.scaling) - self.scaling * .2

        self.surface.blit(self.cashbag_sprite, (gx, gy))

    def _render_dropspot(self, idx):
        x, y = self._dropspot_positions[idx]
        gx = (x * self.scaling) - self.scaling * .5
        gy = (y * self.scaling) - self.scaling * .5

        self.surface.blit(self.dropspot_sprite, (gx, gy))

    def _dist(self, x1, y1, x2, y2):
        return np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    def _move_robbers(self, actions):
        for i in range(self.n_robbers):

            wait_ticks = self._cashbag_carriers[i] + 1
            if not self._game_ticks % wait_ticks == 0:
                continue

            dx, dy = actions[i * 2], actions[i * 2 + 1]
            x, y = self._robber_positions[i]
            x += dx
            y += dy

            if not self._is_cell_free(x, y):
                continue

            self._robber_positions[i] = x, y

    def _move_scrooges(self):
        if not self._game_ticks % self._scrooges_move_interval == 0:
            return

        targets = self._assign_scrooge_targets()

        for i in range(self._n_scrooges):

            x, y = self._scrooge_positions[i]

            if targets[i] is None:
                # Move randomly
                dx, dy = self.random.randint(-1, 2), self.random.randint(-1, 2)
            else:
                # Move towards the robber this scrooge chases
                dx, dy = self._chase_step(x, y, targets[i])

            x += dx
            y += dy

            if not self._is_cell_free(x, y) or self._is_scrooge_at(x, y, i):
                continue

            self._scrooge_positions[i] = x, y

    def _assign_scrooge_targets(self):
        """The robber each scrooge chases this move, or None to wander.

        A scrooge chases the nearest robber that is not immune and is closer
        than ``_scrooge_radius``, measured along the shortest way around the
        obstacles. At most ``_max_chasers_per_robber`` scrooges chase the same
        robber: the nearest ones get it, and the rest go for their next
        nearest robber in range, or wander.
        """
        self._path_fields = {}
        claims = []

        for i in range(self._n_scrooges):
            x, y = self._scrooge_positions[i]
            for r in range(self.n_robbers):
                if self._robber_cooldown[r] > 0:
                    continue
                distance = self._chase_distance(x, y, r)
                if distance < self._scrooge_radius:
                    claims.append((distance, i, r))

        targets = [None] * self._n_scrooges
        n_chasers = [0] * self.n_robbers
        for _, i, r in sorted(claims):
            if targets[i] is None and n_chasers[r] < self._max_chasers_per_robber:
                targets[i] = r
                n_chasers[r] += 1

        return targets

    def _chase_distance(self, x, y, robber):
        """Distance from (x, y) to a robber, the way a scrooge has to walk it.

        The straight-line distance when nothing is in the way, as before;
        otherwise the length of the shortest path around the obstacles, which
        is never shorter.
        """
        rx, ry = self._robber_positions[robber]
        distance = self._dist(x, y, rx, ry)

        if distance >= self._scrooge_radius or self._is_straight_path_clear(x, y, rx, ry):
            return distance

        return self._path_field(robber).get((int(x), int(y)), np.inf)

    def _chase_step(self, x, y, robber):
        """The step a scrooge at (x, y) takes towards a robber."""
        rx, ry = self._robber_positions[robber]
        straight = _sign(rx - x), _sign(ry - y)

        if self._is_straight_path_clear(x, y, rx, ry):
            return straight

        # Something is in the way: take the first step of the shortest path
        # around it, preferring the straight step when it is as good.
        field = self._path_field(robber)
        x, y = int(x), int(y)
        best, best_distance = (0, 0), np.inf

        for dx, dy in [straight] + _STEPS:
            distance = (_DIAGONAL if dx and dy else 1) + \
                field.get((x + dx, y + dy), np.inf)
            if distance < best_distance:
                best, best_distance = (dx, dy), distance

        return best

    def _is_straight_path_clear(self, x, y, tx, ty):
        """Whether stepping straight at (tx, ty) from (x, y) reaches it.

        The straight steps are the ones a scrooge takes when nothing is in the
        way: diagonally until level with the target on one axis, then along
        the other.
        """
        x, y, tx, ty = int(x), int(y), int(tx), int(ty)

        while (x, y) != (tx, ty):
            x += _sign(tx - x)
            y += _sign(ty - y)
            if not self._is_cell_free(x, y):
                return False

        return True

    def _path_field(self, robber):
        """Shortest walking distance from every cell near a robber to it.

        Steps cost 1 straight and sqrt(2) diagonally, like the straight-line
        distance they stand in for. Only cells within the chase radius (plus
        one step) are filled in; the rest are too far to chase from anyway.
        Computed once per robber per scrooge move.
        """
        if robber in self._path_fields:
            return self._path_fields[robber]

        start = tuple(int(v) for v in self._robber_positions[robber])
        limit = self._scrooge_radius + _DIAGONAL
        field = {start: 0.0}
        queue = [(0.0, start)]

        while queue:
            distance, (x, y) = heapq.heappop(queue)
            if distance > field[(x, y)]:
                continue

            for dx, dy in _STEPS:
                cell = x + dx, y + dy
                next_distance = distance + (_DIAGONAL if dx and dy else 1)
                if (next_distance < limit
                        and next_distance < field.get(cell, np.inf)
                        and self._is_cell_free(*cell)):
                    field[cell] = next_distance
                    heapq.heappush(queue, (next_distance, cell))

        self._path_fields[robber] = field
        return field

    def _is_scrooge_at(self, x, y, scrooge):
        """Whether a scrooge other than ``scrooge`` stands on (x, y)."""
        return any(
            j != scrooge
            and self._scrooge_positions[j, 0] == x
            and self._scrooge_positions[j, 1] == y
            for j in range(self._n_scrooges)
        )
