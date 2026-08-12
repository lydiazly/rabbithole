"""How day and night work — not what any particular place looks like.

This module owns the mechanism: the shape of a colour record, the quantised
steps, and the blend between a day set and a night set. The actual colours belong
to a scene, and characters carry their own; both blend through `blend` here so
they stay lit consistently with each other.

Quantising is both cheaper and more honest to the look: classic runners flip
between a day and a night palette, they do not cross-fade.
"""

from dataclasses import dataclass, fields

Color = tuple[int, int, int]

# Steps across the whole day->night ramp, endpoints included. Eight is enough to
# read as a gradual change at this resolution while keeping the sprite cache tiny.
STEPS = 8


@dataclass(frozen=True)
class Palette:
    """Every colour a scene draws with.

    A scene supplies one of these for day and one for night. Colours for layers
    the scene has switched off are never read, but are still required: a palette
    with holes in it would have to be checked everywhere it is used.
    """

    sky: Color
    horizon: Color
    hill_far: Color
    hill_near: Color
    ground: Color
    ground_line: Color
    speckle: Color
    obstacle: Color
    obstacle_dark: Color
    dust: Color
    cloud: Color
    star: Color
    moon: Color
    text: Color


# Fraction of a cycle spent moving between the two sets; the rest is held at one
# end or the other. The middle steps are where every pair of colours is closest
# together and hardest to read, so the ramp is kept brief and passed through
# quickly rather than lingered in.
_TRANSITION = 0.05
_DAY_END = 0.42
_NIGHT_END = 0.92


def night_blend(phase: float) -> float:
    """Return 0.0 for full day, 1.0 for full night, ramping in between."""
    phase %= 1.0
    if phase < _DAY_END:
        return 0.0
    if phase < _DAY_END + _TRANSITION:
        return (phase - _DAY_END) / _TRANSITION
    if phase < _NIGHT_END:
        return 1.0
    # Clamped, or the tail of the cycle keeps ramping past dawn into negative
    # blend and `step_at` returns negative steps. The longer transition this
    # replaced ran off the end of the cycle before it could go negative, so the
    # bug only appeared once the ramp got short enough to finish early.
    return max(0.0, 1.0 - (phase - _NIGHT_END) / _TRANSITION)


def step_at(phase: float) -> int:
    """Return the quantised day/night step, 0 (day) .. STEPS - 1 (night)."""
    return round(night_blend(phase) * (STEPS - 1))


def lerp_color(a: Color, b: Color, t: float) -> Color:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def blend(day, night, step: int):
    """Interpolate two matching colour records at a quantised step.

    Works on any frozen dataclass whose fields are all colours, which is how a
    scene's palette and a character's look share one implementation rather than
    two copies that could drift apart.
    """
    step = min(STEPS - 1, max(0, step))
    if step == 0:
        return day
    if step == STEPS - 1:
        return night
    t = step / (STEPS - 1)
    return type(day)(
        **{
            f.name: lerp_color(getattr(day, f.name), getattr(night, f.name), t)
            for f in fields(day)
        }
    )


def luminance(color: Color) -> float:
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def is_night(step: int) -> bool:
    """Whether this step is dark enough for stars and the moon.

    Deliberately past the halfway point: at the middle steps the sky is still a
    daylight blue, and stars on it read as dirt on the screen.
    """
    return step * 4 >= STEPS * 3
