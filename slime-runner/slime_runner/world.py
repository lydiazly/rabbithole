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

# Difficulty is measured as progress along the speed ramp, not as wall-clock time
# or as absolute speed. Everything below is a fraction of it, so retuning the
# speed moves the whole curve together instead of silently resequencing it.
def difficulty(speed: float) -> float:
    """0.0 at the start of a run, 1.0 once the speed has topped out."""
    return min(1.0, max(0.0, (speed - SPEED_START) / SPEED_RANGE))


def unlocked(t: float, start: float, weight: float) -> float:
    """Zero until `start`, then ramping to `weight` at the end of the ramp."""
    if t <= start:
        return 0.0
    return weight * (t - start) / (1.0 - start)


# A run opens with nothing but single small cacti, so there is a stretch of it in
# which the only thing to learn is the jump. Each further hazard unlocks later and
# grows in, reaching roughly the mix the game used to start with.
LARGE_FROM = 0.22
LARGE_WEIGHT = 0.65
CLUSTER_FROM = 0.40
CLUSTER_WEIGHT = 0.55
TRIPLE_FROM = 0.65  # before this a cluster is two cacti, never three

AIR_FROM = 0.18
AIR_CHANCE_MAX = 0.35
# Flyers arrive high, where they only threaten a jump. The low ones that have to
# be ducked are a separate, later unlock: ducking is the one control that cannot
# be discovered by pressing jump harder.
LOW_FLYER_FROM = 0.35
LOW_FLYER_SHARE = 0.6


def air_chance(speed: float) -> float:
    """Probability that the next spawn is a flyer."""
    return unlocked(difficulty(speed), AIR_FROM, AIR_CHANCE_MAX)


def low_flyer_share(speed: float) -> float:
    """Of the flyers spawned, the fraction that sit low enough to demand a duck."""
    return unlocked(difficulty(speed), LOW_FLYER_FROM, LOW_FLYER_SHARE)


def ground_weights(speed: float) -> tuple[float, float, float]:
    """Relative weights of (small, large, cluster) for the next ground spawn."""
    t = difficulty(speed)
    return (
        1.0,
        unlocked(t, LARGE_FROM, LARGE_WEIGHT),
        unlocked(t, CLUSTER_FROM, CLUSTER_WEIGHT),
    )

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

# Canvas units per full day/night cycle: about 30 s of play at top speed, 75 s at
# the opening crawl. Much shorter and the sky starts visibly strobing.
DAY_LENGTH = 6500.0

CLOUD_SPEED = 0.15
FAR_SPEED = 0.25
NEAR_SPEED = 0.5
# Stars and the moon have no speed at all. They are the only things meant to read
# as further away than the hills, and any drift makes them look like near scenery.

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
        # Fixed, so whole pixels and no wrap-around bookkeeping.
        self.stars = [(r.randrange(WIDTH), r.randrange(3, 46)) for _ in range(16)]
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
        self._scroll_layer(self.far, FAR_SPEED, dt, 42.0)
        self._scroll_layer(self.near, NEAR_SPEED, dt, 36.0)
        self._scroll_layer(self.speckles, 1.0, dt, 6.0)

    def _spawn(self) -> None:
        x = WIDTH + 8.0
        if self.rng.random() < air_chance(self.speed):
            low = self.rng.random() < low_flyer_share(self.speed)
            clear = AIR_LOW_CLEAR if low else AIR_HIGH_CLEAR
            w, h = AIR_BOX
            self.obstacles.append(
                Obstacle(x, GROUND_Y - clear - h, w, h, "flyer",
                         phase=self.rng.uniform(0.0, math.tau))
            )
            return

        small_w, large_w, cluster_w = ground_weights(self.speed)
        roll = self.rng.random() * (small_w + large_w + cluster_w)
        if roll < small_w:
            w, h = SMALL_BOX
            self.obstacles.append(Obstacle(x, GROUND_Y - h, w, h, "small"))
        elif roll < small_w + large_w:
            w, h = LARGE_BOX
            self.obstacles.append(Obstacle(x, GROUND_Y - h, w, h, "large"))
        else:
            w, h = SMALL_BOX
            triple = (
                difficulty(self.speed) > TRIPLE_FROM and self.rng.random() < 0.5
            )
            for i in range(3 if triple else 2):
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
            for star in self.stars:
                canvas.set_at(star, STAR)

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
