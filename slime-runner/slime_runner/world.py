"""The scrolling world, in low-resolution canvas pixels.

The slime never moves forward — the world moves past it — so `distance` is the
single source of truth for score, difficulty and the day/night phase.

Scenery is drawn with plain shape calls rather than authored sprites: at canvas
resolution a filled circle already *is* pixel art, and hills are the one thing
whose exact silhouette nobody reads.
"""

import math
import random
from dataclasses import dataclass

import pygame

from . import slime as slime_mod
from . import sprites
from .palette import STAR, is_night

WIDTH = 300
HEIGHT = 108
GROUND_Y = 84

SPEED_START = 85.0
SPEED_GAIN = 2.1
SPEED_MAX = 205.0
SPEED_RANGE = SPEED_MAX - SPEED_START

SCORE_RATE = 0.18

# A full-hold jump is airborne for roughly this long. The spawn gap is floored at
# the distance covered in that time plus a margin, which is what keeps every gap
# clearable as the speed ramps up.
JUMP_AIRTIME = 0.60
GAP_MARGIN = 20.0
GAP_RANGE = (0.75, 1.5)  # seconds of travel

# Flyers are keyed to fractions of the speed ramp rather than to absolute speeds.
# Pinned to absolute values, retuning the speed silently moves both when ducking
# first appears and how common it ever gets — slowing the game down by a fifth
# pushed the first flyer from ten seconds into twenty-two and halved its rate at
# top speed, quietly sidelining the whole mechanic.
AIR_SPEED_FLOOR = SPEED_START + 0.18 * SPEED_RANGE  # no flyers until some pace
AIR_SPEED_SPAN = 1.10 * SPEED_RANGE
AIR_CHANCE_MAX = 0.35


def air_chance(speed: float) -> float:
    """Probability that the next spawn is a flyer, at this speed."""
    ramp = max(0.0, (speed - AIR_SPEED_FLOOR) / AIR_SPEED_SPAN)
    return min(AIR_CHANCE_MAX, ramp * AIR_CHANCE_MAX)

# Bottom edge above the ground. Low clears a ducked slime (6 tall) and catches a
# standing one (12); high is only a threat mid-jump.
AIR_LOW_CLEAR = 8
AIR_HIGH_CLEAR = 30
AIR_BOX = (9, 5)  # hitbox, deliberately smaller than the 13x7 sprite

# Trunks only — the arms are visual. Being narrower than the art the player reads
# is the forgiving direction to be wrong in.
SMALL_BOX = (3, 11)
LARGE_BOX = (5, 16)
CLUSTER_GAP = 8

DAY_LENGTH = 10000.0  # canvas units per full day/night cycle, about a minute

CLOUD_SPEED = 0.15
STAR_SPEED = 0.08
FAR_SPEED = 0.25
NEAR_SPEED = 0.5

HORIZON_BAND = 14  # pixels of lighter sky just above the ground

MOON_POS = (236, 20)  # clear of the score, which sits in the same corner


@dataclass
class Obstacle:
    x: float
    y: float
    w: float
    h: float
    kind: str
    phase: float = 0.0

    def rect(self):
        return (self.x, self.y, self.w, self.h)


def min_gap(speed: float) -> float:
    """Shortest spawn gap that a full-height jump can still clear."""
    return JUMP_AIRTIME * speed + GAP_MARGIN


class World:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.speed = SPEED_START
        self.distance = 0.0
        self.score = 0.0
        self.obstacles: list[Obstacle] = []
        self.since_spawn = 0.0
        self.next_gap = min_gap(SPEED_START) * 1.4
        self._build_scenery()

    @property
    def phase(self) -> float:
        return (self.distance / DAY_LENGTH) % 1.0

    # -- scenery ----------------------------------------------------------

    def _build_scenery(self) -> None:
        r = self.rng
        self.clouds = [
            [r.uniform(0, WIDTH * 1.4), r.randrange(6, 40), r.randrange(2)]
            for _ in range(5)
        ]
        self.stars = [
            [r.uniform(0, WIDTH), r.randrange(3, 46)] for _ in range(16)
        ]
        self.far = [[r.uniform(0, WIDTH * 1.3), r.randrange(22, 40)] for _ in range(6)]
        self.near = [[r.uniform(0, WIDTH * 1.3), r.randrange(22, 34)] for _ in range(7)]
        self.speckles = [
            [r.uniform(0, WIDTH), r.randrange(GROUND_Y + 4, HEIGHT - 2),
             r.randrange(2, 5)]
            for _ in range(26)
        ]

    def _scroll_layer(self, items, factor: float, dt: float, span: float) -> None:
        step = self.speed * factor * dt
        for item in items:
            item[0] -= step
            if item[0] < -span:
                item[0] += WIDTH + span * 2.0

    # -- update -----------------------------------------------------------

    def update(self, dt: float) -> None:
        self.speed = min(SPEED_MAX, self.speed + SPEED_GAIN * dt)
        step = self.speed * dt
        self.distance += step
        self.score += self.speed * dt * SCORE_RATE

        for ob in self.obstacles:
            ob.x -= step
            ob.phase += dt
        self.obstacles = [ob for ob in self.obstacles if ob.x + ob.w > -16.0]

        self.since_spawn += step
        if self.since_spawn >= self.next_gap:
            self.since_spawn = 0.0
            self._spawn()
            self.next_gap = max(
                min_gap(self.speed), self.speed * self.rng.uniform(*GAP_RANGE)
            )

        self._scroll_layer(self.clouds, CLOUD_SPEED, dt, 14.0)
        self._scroll_layer(self.stars, STAR_SPEED, dt, 2.0)
        self._scroll_layer(self.far, FAR_SPEED, dt, 42.0)
        self._scroll_layer(self.near, NEAR_SPEED, dt, 36.0)
        self._scroll_layer(self.speckles, 1.0, dt, 6.0)

    def _spawn(self) -> None:
        x = WIDTH + 8.0
        if self.rng.random() < air_chance(self.speed):
            clear = AIR_LOW_CLEAR if self.rng.random() < 0.6 else AIR_HIGH_CLEAR
            w, h = AIR_BOX
            self.obstacles.append(
                Obstacle(x, GROUND_Y - clear - h, w, h, "flyer",
                         phase=self.rng.uniform(0.0, math.tau))
            )
            return

        roll = self.rng.random()
        if roll < 0.45:
            w, h = SMALL_BOX
            self.obstacles.append(Obstacle(x, GROUND_Y - h, w, h, "small"))
        elif roll < 0.75:
            w, h = LARGE_BOX
            self.obstacles.append(Obstacle(x, GROUND_Y - h, w, h, "large"))
        else:
            w, h = SMALL_BOX
            for i in range(self.rng.choice((2, 3))):
                self.obstacles.append(
                    Obstacle(x + i * CLUSTER_GAP, GROUND_Y - h, w, h, "small")
                )

    def collides(self, box) -> bool:
        return any(slime_mod.rects_overlap(box, ob.rect()) for ob in self.obstacles)

    # -- drawing ----------------------------------------------------------

    def draw(self, canvas, palette, step: int, sheet: sprites.SpriteSheet) -> None:
        canvas.fill(palette.sky)
        pygame.draw.rect(
            canvas, palette.horizon, (0, GROUND_Y - HORIZON_BAND, WIDTH, HORIZON_BAND)
        )

        if is_night(step):
            canvas.blit(sheet.moon, MOON_POS)
            for x, y in self.stars:
                canvas.set_at((int(x) % WIDTH, y), STAR)

        for x, y, which in self.clouds:
            canvas.blit(sheet.clouds[which], (int(x), y))

        for x, r in self.far:
            pygame.draw.circle(canvas, palette.hill_far, (int(x), GROUND_Y + 14), r)
        for x, r in self.near:
            pygame.draw.circle(canvas, palette.hill_near, (int(x), GROUND_Y + 20), r)

        pygame.draw.rect(canvas, palette.ground, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        pygame.draw.line(canvas, palette.ground_line, (0, GROUND_Y), (WIDTH - 1, GROUND_Y))
        for x, y, w in self.speckles:
            pygame.draw.line(canvas, palette.speckle, (int(x), y), (int(x) + w, y))

        for ob in self.obstacles:
            self._draw_obstacle(canvas, sheet, ob)

    def _draw_obstacle(self, canvas, sheet, ob: Obstacle) -> None:
        if ob.kind == "flyer":
            surf = sheet.flyer[int(ob.phase * 9.0) % 2]
            # Integer bob, so the flyer stays on the pixel grid like everything else.
            bob = round(math.sin(ob.phase * 4.0) * 1.5)
            canvas.blit(
                surf,
                (round(ob.x + ob.w / 2 - surf.get_width() / 2),
                 round(ob.y + ob.h / 2 - surf.get_height() / 2 + bob)),
            )
            return

        surf = sheet.cactus_small if ob.kind == "small" else sheet.cactus_large
        canvas.blit(
            surf,
            (round(ob.x + ob.w / 2 - surf.get_width() / 2), GROUND_Y - surf.get_height()),
        )
