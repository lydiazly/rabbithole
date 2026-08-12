"""The scrolling world, in low-resolution canvas pixels.

The player never moves forward — the world moves past it — so `distance` is the
single source of truth for score, difficulty and the day/night phase.

Scenery is drawn with plain shape calls rather than authored sprites: at canvas
resolution a filled circle already *is* pixel art, and hills are the one thing
whose exact silhouette nobody reads.
"""

import math
import random
from dataclasses import dataclass

import pygame

from . import player as player_mod
from . import sprites
from .palette import is_night

WIDTH = 300
HEIGHT = 108
GROUND_Y = 84

SPEED_START = 85.0
SPEED_GAIN = 2.1
SPEED_MAX = 205.0
SPEED_RANGE = SPEED_MAX - SPEED_START

# A full-hold jump is airborne for roughly this long. The spawn gap is floored at
# the distance covered in that time plus a margin, which is what keeps every gap
# clearable as the speed ramps up.
JUMP_AIRTIME = 0.60
GAP_MARGIN = 20.0

# Seconds of travel between spawns, early in a run and at top speed.
#
# The range is in *time*, so a fixed one keeps the obstacle density identical
# however fast the world is moving: measured, the mean interval was 1.14s at the
# opening crawl and 1.13s at top speed. All the late-game difficulty was coming
# from the shrinking reaction window, and none from anything getting denser.
# Closing the late range brings the interval down to about 0.92s -- enough to
# feel, while the floor above still guarantees every gap is jumpable.
GAP_RANGE_EARLY = (0.75, 1.50)
GAP_RANGE_LATE = (0.68, 1.15)

# Scoring. Every obstacle is worth at least a point, and taller ones are worth
# more: height stands in for how much of a jump a thing demands, where a short
# cactus takes a hop and a tall one takes a committed one. Read off the hitbox
# rather than a table of kinds, so a new obstacle scores correctly the day it is
# added. A cluster is several obstacles and so already scores several times.
SCORE_HEIGHT_STEP = 5


def points_for(ob) -> int:
    return 1 + max(0, int((ob.h - SMALL_BOX[1]) // SCORE_HEIGHT_STEP))


# How much of the launch a smashed obstacle gets, and how fast it falls away.
LAUNCH_SPEED = 190.0
LAUNCH_DRIFT = 90.0
LAUNCH_GRAVITY = 520.0
LAUNCH_SPIN = 9.0  # quarter-turns per second

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


def gap_range(speed: float) -> tuple[float, float]:
    """Seconds of travel to leave before the next spawn, at this speed."""
    t = difficulty(speed)
    return tuple(
        early + (late - early) * t
        for early, late in zip(GAP_RANGE_EARLY, GAP_RANGE_LATE)
    )


def ground_weights(speed: float) -> tuple[float, float, float]:
    """Relative weights of (small, large, cluster) for the next ground spawn."""
    t = difficulty(speed)
    return (
        1.0,
        unlocked(t, LARGE_FROM, LARGE_WEIGHT),
        unlocked(t, CLUSTER_FROM, CLUSTER_WEIGHT),
    )

# Bottom edge above the ground. Low clears a ducked player (6 tall) and catches a
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
    # Counted once, however the player got past it, so shuffling backwards with
    # A cannot farm the same cactus twice.
    scored: bool = False
    # Set when smashed during a dash. A launched obstacle stops colliding and
    # tumbles away under its own gravity.
    launched: bool = False
    vy: float = 0.0
    drift: float = 0.0

    def rect(self):
        return (self.x, self.y, self.w, self.h)


def min_gap(speed: float) -> float:
    """Shortest spawn gap that a full-height jump can still clear."""
    return JUMP_AIRTIME * speed + GAP_MARGIN


class World:
    def __init__(self, scene, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.scene = scene
        self.reset()

    def use_scene(self, scene) -> None:
        """Switch scene and start fresh. Layers differ, so scenery is rebuilt."""
        self.scene = scene
        self.reset()

    def reset(self) -> None:
        self.speed = SPEED_START
        self.boost = 1.0
        self.distance = 0.0
        self.obstacles: list[Obstacle] = []
        self.since_spawn = 0.0
        self.next_gap = min_gap(SPEED_START) * 1.4
        self._build_scenery()

    @property
    def scroll(self) -> float:
        """How fast the world actually moves past, dash boost included.

        Kept apart from `speed`, which stays on its own ramp and drives the
        difficulty curve. Boosting `speed` itself would jump the obstacle mix
        mid-dash and then drop it again, and the spawn floor would quietly start
        describing a speed the world was not travelling at.
        """
        return self.speed * self.boost

    @property
    def phase(self) -> float:
        return (self.distance / DAY_LENGTH) % 1.0

    # -- scenery ----------------------------------------------------------

    def _build_scenery(self) -> None:
        """Populate the layers this scene uses, and only those.

        A layer the scene has switched off generates nothing, so it also scrolls
        nothing and draws nothing -- one membership test rather than three.
        """
        r = self.rng
        has = self.scene.has
        self.clouds = [
            [r.uniform(0, WIDTH * 1.4), r.randrange(6, 40), r.randrange(2)]
            for _ in range(5 if has("clouds") else 0)
        ]
        # Fixed, so whole pixels and no wrap-around bookkeeping.
        self.stars = [
            (r.randrange(WIDTH), r.randrange(3, 46))
            for _ in range(16 if has("stars") else 0)
        ]
        self.far = [
            [r.uniform(0, WIDTH * 1.3), r.randrange(22, 40)]
            for _ in range(6 if has("hills_far") else 0)
        ]
        self.near = [
            [r.uniform(0, WIDTH * 1.3), r.randrange(22, 34)]
            for _ in range(7 if has("hills_near") else 0)
        ]
        self.speckles = [
            [r.uniform(0, WIDTH), r.randrange(GROUND_Y + 4, HEIGHT - 2),
             r.randrange(2, 5)]
            for _ in range(26 if has("speckles") else 0)
        ]

    def _scroll_layer(self, items, factor: float, dt: float, span: float) -> None:
        step = self.scroll * factor * dt
        for item in items:
            item[0] -= step
            if item[0] < -span:
                item[0] += WIDTH + span * 2.0

    # -- update -----------------------------------------------------------

    def update(self, dt: float, player_x: float) -> int:
        """Advance the world. Returns the points scored this step."""
        self.speed = min(SPEED_MAX, self.speed + SPEED_GAIN * dt)
        scroll = self.scroll
        step = scroll * dt
        self.distance += step

        cleared = 0
        for ob in self.obstacles:
            ob.x -= step
            ob.phase += dt
            if ob.launched:
                ob.vy += LAUNCH_GRAVITY * dt
                ob.y += ob.vy * dt
                ob.x -= ob.drift * dt
            elif not ob.scored and ob.x + ob.w < player_x:
                ob.scored = True
                cleared += points_for(ob)
        self.obstacles = [
            ob for ob in self.obstacles
            if ob.x + ob.w > -16.0 and ob.y < HEIGHT + 20
        ]

        self.since_spawn += step
        if self.since_spawn >= self.next_gap:
            self.since_spawn = 0.0
            self._spawn()
            self.next_gap = max(
                min_gap(scroll), scroll * self.rng.uniform(*gap_range(self.speed))
            )

        self._scroll_layer(self.clouds, CLOUD_SPEED, dt, 14.0)
        self._scroll_layer(self.far, FAR_SPEED, dt, 42.0)
        self._scroll_layer(self.near, NEAR_SPEED, dt, 36.0)
        self._scroll_layer(self.speckles, 1.0, dt, 6.0)
        return cleared

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

    def hits(self, box) -> list:
        """Obstacles overlapping the box. Launched ones are out of play."""
        return [
            ob for ob in self.obstacles
            if not ob.launched and player_mod.rects_overlap(box, ob.rect())
        ]

    def collides(self, box) -> bool:
        return bool(self.hits(box))

    def launch(self, ob: Obstacle) -> None:
        """Knock an obstacle out of the way, mid-dash."""
        ob.launched = True
        ob.scored = True
        ob.vy = -LAUNCH_SPEED
        ob.drift = LAUNCH_DRIFT

    # -- drawing ----------------------------------------------------------

    def draw(self, canvas, palette, step: int, sheet: sprites.WorldSheet) -> None:
        """Back to front. The order is fixed here: a scene chooses what is drawn,
        never what covers what.

        Layers the scene switched off generated no items, so their loops are
        empty and need no test of their own. The two that are single draws rather
        than loops are gated explicitly.
        """
        canvas.fill(palette.sky)
        if self.scene.has("horizon"):
            pygame.draw.rect(
                canvas, palette.horizon,
                (0, GROUND_Y - HORIZON_BAND, WIDTH, HORIZON_BAND),
            )

        if is_night(step):
            if self.scene.has("moon"):
                canvas.blit(sheet.moon, MOON_POS)
            for star in self.stars:
                canvas.set_at(star, palette.star)

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
        if ob.launched:
            self._draw_launched(canvas, sheet, ob)
            return
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

        surf = sheet.ground[ob.kind]
        canvas.blit(
            surf,
            (round(ob.x + ob.w / 2 - surf.get_width() / 2), GROUND_Y - surf.get_height()),
        )

    def _draw_launched(self, canvas, sheet, ob: Obstacle) -> None:
        """A smashed obstacle, tumbling away.

        Rotated in whole quarter-turns only: pygame rotates those exactly, where
        any other angle resamples and would put the one blurry, off-grid thing on
        an otherwise hard-edged screen.
        """
        surf = sheet.flyer[0] if ob.kind == "flyer" else sheet.ground[ob.kind]
        quarter = int(ob.phase * LAUNCH_SPIN) % 4
        if quarter:
            surf = pygame.transform.rotate(surf, 90 * quarter)
        canvas.blit(
            surf,
            (round(ob.x + ob.w / 2 - surf.get_width() / 2),
             round(ob.y + ob.h / 2 - surf.get_height() / 2)),
        )
