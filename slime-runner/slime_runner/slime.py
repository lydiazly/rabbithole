"""The slime: jump physics, and a frame-clip animator in place of a simulation.

Nothing here computes a shape. The seven poses live in `sprites.py`; this module
only decides which one is on screen this tick. Squash and stretch are authored
sequences played on a timer — landing runs deep-squash, squash, part-squash,
overshoot-tall, round — so the bounce-back reads as deliberate animation rather
than as a decaying oscillation.

All units are low-resolution canvas pixels.
"""

import math

from .sprites import EAR_IDLE, SLIME_SIZES

# Snap up, drift down. This inverts the usual platformer convention of falling
# harder than you rise, which reads as weight but, at this jump height, mostly
# reads as being dragged back down before you have arrived. Getting to the top
# quickly and hanging on the way down leaves the arc under the player's control
# for longer, which matters more here because the second jump is spent mid-flight.
#
# Rise 0.23 s and fall 0.30 s, still peaking at 40 px and still totalling 0.53 s —
# airtime is what world.py keys the spawn-gap floor to, so the total is held
# fixed and only its distribution changes.
GRAVITY_UP = 1510.0
GRAVITY_DOWN = 890.0
JUMP_SPEED = 348.0
JUMP_CUT_SPEED = 120.0  # releasing early while rising clamps to this, giving a hop

# The mid-air second jump, expressed in height rather than in speed.
#
# Speed is the wrong currency here. Replacing the velocity means an early press
# does nothing or actively slows the ascent, so the height is only there for a
# frame-perfect apex press. Adding to the velocity is forgiving but unbounded in
# height: a press halfway up keeps most of the rise already banked *and* gets the
# full addition, which sends the slime clean off the top of the screen.
#
# Working in height fixes both. The second jump tops the flight up by
# DOUBLE_JUMP_RISE and the apex is clamped to MAX_APEX, so every press from
# takeoff to apex converges on the same ceiling and none of them can overshoot it.
MAX_JUMPS = 2
DOUBLE_JUMP_RISE = 18.0
MAX_APEX = 62.0

LATERAL_SPEED = 85.0

# Landing hard enough to be worth the long clip. A full-height jump comes down at
# about 257; a clipped hop at well under half that.
HARD_LANDING = 160.0

# How long either side of the apex the slime holds its round pose, before and
# after which it is stretched. A duration rather than a velocity: pinned to
# absolute speeds these do not survive a gravity retune, and the faster rise above
# would have cut the round window from four ticks to under two, leaving the whole
# arc reading as one continuous stretch.
APEX_ROUND_TIME = 0.045
RISING_FAST = -GRAVITY_UP * APEX_ROUND_TIME
FALLING_FAST = GRAVITY_DOWN * APEX_ROUND_TIME

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


_EAR_CYCLE = sum(ticks for _, ticks in EAR_IDLE)


def idle_body_frame(tick: int) -> str:
    """The resting two-frame breathe, as a function of a tick count."""
    return "round_b" if (tick // IDLE_TICKS) % 2 else "round"


def idle_ear_frame(tick: int) -> int:
    """Where the ear twitch has got to, as a function of a tick count.

    A plain function so the character-select previews animate off the same clock
    as the real thing, instead of a second copy of the timing drifting from it.
    """
    tick %= _EAR_CYCLE
    for frame, ticks in EAR_IDLE:
        if tick < ticks:
            return frame
        tick -= ticks
    return 0


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
        self.jumps_used = 0
        self.frame = "round"
        self._clip = None
        self._clip_i = 0
        self._clip_ticks = 0
        self._idle_ticks = 0
        self._idle_b = False
        self._ear_ticks = 0
        self.ear_frame = 0

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

    def jump(self) -> str | None:
        """Start a jump. Returns "ground", "air", or None if none was available."""
        if self.on_ground:
            self.vy = -JUMP_SPEED
            self.on_ground = False
            self.ducking = False
            self.jumps_used = 1
            self._play(TAKEOFF)
            return "ground"
        if self.jumps_used >= MAX_JUMPS:
            return None
        self.jumps_used += 1
        height = self.ground_y - self.y
        rise_left = self.vy**2 / (2.0 * GRAVITY_UP) if self.vy < 0.0 else 0.0
        # Never below rise_left: the second jump must not be able to slow you down.
        target = max(rise_left, min(rise_left + DOUBLE_JUMP_RISE, MAX_APEX - height))
        self.vy = -math.sqrt(2.0 * GRAVITY_UP * target)
        self._play(TAKEOFF)
        return "air"

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
                self.jumps_used = 0
                self.ducking = ducking
                self._play(LAND_HARD if impact >= HARD_LANDING else LAND_SOFT)

        self._advance_frame()
        self._advance_ears()
        return impact

    # -- animation --------------------------------------------------------

    def _play(self, clip) -> None:
        self._clip = clip
        self._clip_i = 0
        self._clip_ticks = 0
        self.frame = clip[0][0]

    @property
    def idle(self) -> bool:
        """Standing on the ground with no clip playing and not ducking."""
        return self._clip is None and self.on_ground and not self.ducking

    def _advance_ears(self) -> None:
        # Ears twitch only at rest: during a jump, a landing or a duck the body is
        # already carrying the motion and a second thing moving on top of it only
        # muddies the pose.
        #
        # The clock keeps running through those actions even though the ear is
        # pinned upright. Restarting it instead meant a player who jumps at a
        # normal rate never accumulated the idle ticks the first twitch needs, and
        # the ears sat dead for a whole run.
        self._ear_ticks += 1
        self.ear_frame = idle_ear_frame(self._ear_ticks) if self.idle else 0

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
