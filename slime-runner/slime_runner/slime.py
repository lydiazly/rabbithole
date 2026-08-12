"""The slime: jump physics, and a frame-clip animator in place of a simulation.

Nothing here computes a shape. The seven poses live in `sprites.py`; this module
only decides which one is on screen this tick. Squash and stretch are authored
sequences played on a timer — landing runs deep-squash, squash, part-squash,
overshoot-tall, round — so the bounce-back reads as deliberate animation rather
than as a decaying oscillation.

All units are low-resolution canvas pixels.
"""

from .sprites import SLIME_SIZES

# Rising is gentler than falling: the arc hangs at the top and lands with weight.
GRAVITY_UP = 700.0
GRAVITY_DOWN = 1050.0
JUMP_SPEED = 210.0
JUMP_CUT_SPEED = 70.0  # releasing early while rising clamps to this, giving a hop

LATERAL_SPEED = 85.0

# Landing hard enough to be worth the long clip. A full-height jump comes down at
# about 257; a clipped hop at well under half that.
HARD_LANDING = 160.0

# Airborne pose thresholds, in vertical speed. Set well inside the launch speed of
# 210: pitched near it, the tall pose only shows for the handful of ticks the
# takeoff clip already covers, and the jump reads as round the whole way up.
RISING_FAST = -40.0
FALLING_FAST = 60.0

IDLE_TICKS = 26  # per idle frame, so the pair cycles a little under a second

# Clips are (frame name, ticks). They play once and then hand control back to the
# pose rules below.
LAND_HARD = (("squash3", 3), ("squash2", 3), ("squash1", 2), ("stretch1", 3),
             ("round", 2))
LAND_SOFT = (("squash2", 3), ("squash1", 3))
TAKEOFF = (("stretch2", 4), ("stretch1", 3))
DUCK_IN = (("squash1", 2), ("squash2", 2))
DUCK_OUT = (("squash1", 2), ("stretch1", 3))

HITBOX_INSET_X = 1
HITBOX_INSET_Y = 1


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def rects_overlap(a, b) -> bool:
    """Overlap test for (left, top, width, height) tuples."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


class Slime:
    """The player character. `x` is its centre, `y` is its feet."""

    def __init__(self, x: float, ground_y: float):
        self.ground_y = ground_y
        self.home_x = x
        self.reset()

    def reset(self) -> None:
        self.x = self.home_x
        self.y = self.ground_y
        self.vy = 0.0
        self.on_ground = True
        self.ducking = False
        self.frame = "round"
        self._clip = None
        self._clip_i = 0
        self._clip_ticks = 0
        self._idle_ticks = 0
        self._idle_b = False

    # -- shape ------------------------------------------------------------

    @property
    def size(self) -> tuple[int, int]:
        return SLIME_SIZES[self.frame]

    def hitbox(self):
        """Return (left, top, width, height), inset so grazes are forgiven."""
        w, h = self.size
        return (
            self.x - w / 2.0 + HITBOX_INSET_X,
            self.y - h + HITBOX_INSET_Y,
            w - HITBOX_INSET_X * 2,
            h - HITBOX_INSET_Y,
        )

    def blit_pos(self) -> tuple[int, int]:
        w, h = self.size
        return (round(self.x - w / 2.0), round(self.y - h))

    # -- motion -----------------------------------------------------------

    def jump(self) -> None:
        if not self.on_ground:
            return
        self.vy = -JUMP_SPEED
        self.on_ground = False
        self.ducking = False
        self._play(TAKEOFF)

    def splat(self) -> None:
        """The game-over flop."""
        self._play(LAND_HARD)

    def update(self, dt: float, holding_jump: bool, ducking: bool, lateral: int,
               x_min: float, x_max: float) -> float:
        """Advance one fixed step. Returns the landing impact speed, else 0."""
        if lateral:
            self.x = clamp(self.x + lateral * LATERAL_SPEED * dt, x_min, x_max)

        impact = 0.0
        if self.on_ground:
            if ducking and not self.ducking:
                self._play(DUCK_IN)
            elif self.ducking and not ducking:
                self._play(DUCK_OUT)
            self.ducking = ducking
        else:
            gravity = GRAVITY_UP if (self.vy < 0.0 and holding_jump) else GRAVITY_DOWN
            if self.vy < -JUMP_CUT_SPEED and not holding_jump:
                self.vy = -JUMP_CUT_SPEED
            self.vy += gravity * dt
            self.y += self.vy * dt
            if self.y >= self.ground_y:
                impact = self.vy
                self.y = self.ground_y
                self.vy = 0.0
                self.on_ground = True
                self.ducking = ducking
                self._play(LAND_HARD if impact >= HARD_LANDING else LAND_SOFT)

        self._advance_frame()
        return impact

    # -- animation --------------------------------------------------------

    def _play(self, clip) -> None:
        self._clip = clip
        self._clip_i = 0
        self._clip_ticks = 0
        self.frame = clip[0][0]

    def _advance_frame(self) -> None:
        if self._clip is not None:
            self._clip_ticks += 1
            if self._clip_ticks >= self._clip[self._clip_i][1]:
                self._clip_ticks = 0
                self._clip_i += 1
                if self._clip_i >= len(self._clip):
                    self._clip = None
                else:
                    self.frame = self._clip[self._clip_i][0]
            if self._clip is not None:
                return

        if self.ducking:
            self.frame = "squash3"
        elif not self.on_ground:
            if self.vy < RISING_FAST:
                self.frame = "stretch2"
            elif self.vy > FALLING_FAST:
                self.frame = "stretch1"
            else:
                self.frame = "round"
        else:
            self._idle_ticks += 1
            if self._idle_ticks >= IDLE_TICKS:
                self._idle_ticks = 0
                self._idle_b = not self._idle_b
            self.frame = "round_b" if self._idle_b else "round"
