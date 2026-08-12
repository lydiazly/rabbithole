"""The world's two colour sets, quantised into a handful of day/night steps.

Everything downstream — sprites, the sky, the HUD — is cached against the step
index rather than against a continuous blend. Quantising is both cheaper and more
honest to the look: classic runners flip between a day and a night palette, they
do not cross-fade.
"""

from dataclasses import dataclass, fields

Color = tuple[int, int, int]

# Steps across the whole day->night ramp, endpoints included. Eight is enough to
# read as a gradual change at this resolution while keeping the sprite cache tiny.
STEPS = 8


@dataclass(frozen=True)
class Palette:
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
    text: Color


DAY = Palette(
    sky=(155, 209, 229),
    horizon=(190, 228, 240),
    hill_far=(137, 190, 209),
    hill_near=(106, 165, 190),
    ground=(206, 184, 145),
    ground_line=(150, 128, 96),
    speckle=(176, 154, 118),
    obstacle=(86, 130, 84),
    obstacle_dark=(52, 92, 58),
    dust=(190, 170, 134),
    cloud=(246, 252, 255),
    text=(44, 62, 74),
)

NIGHT = Palette(
    sky=(22, 26, 56),
    horizon=(44, 40, 82),
    hill_far=(38, 42, 80),
    hill_near=(26, 30, 60),
    ground=(58, 54, 78),
    # Both of these stay *darker* than their own ground, exactly as the day pair
    # does. Flipping the direction would make the two ramps cross mid-dusk and the
    # ground would go flat and detail-less for the whole transition.
    ground_line=(34, 30, 52),
    speckle=(42, 38, 60),
    # These, by contrast, deliberately flip: an obstacle has to stand out from the
    # background, and at night that means lighter, not darker. The hue difference
    # keeps them readable at the crossover steps too.
    obstacle=(146, 152, 180),
    obstacle_dark=(96, 102, 132),
    dust=(92, 88, 118),
    cloud=(88, 90, 124),
    text=(222, 228, 246),
)

STAR = (255, 255, 255)

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


def palette_for_step(step: int) -> Palette:
    """Return the palette for a quantised step."""
    step = min(STEPS - 1, max(0, step))
    if step == 0:
        return DAY
    if step == STEPS - 1:
        return NIGHT
    t = step / (STEPS - 1)
    return Palette(
        **{
            f.name: lerp_color(getattr(DAY, f.name), getattr(NIGHT, f.name), t)
            for f in fields(Palette)
        }
    )


def luminance(color: Color) -> float:
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]


def text_tones(step: int) -> tuple[Color, Color]:
    """Return (ink, shadow) for text drawn over the sky at this step.

    Keyed to how bright the sky actually is, not to whether it is night. Tying it
    to `is_night` left dark text on an already-dark sky for the steps in between:
    contrast bottomed out at 18 of 255, which is invisible. The shadow covers the
    one step either side of the switch, where whichever tone is chosen is closest
    to the background.
    """
    if luminance(palette_for_step(step).sky) > 128.0:
        return DAY.text, NIGHT.text
    return NIGHT.text, DAY.text


def is_night(step: int) -> bool:
    """Whether this step is dark enough for stars and the moon.

    Deliberately past the halfway point: at the middle steps the sky is still a
    daylight blue, and stars on it read as dirt on the screen.
    """
    return step * 4 >= STEPS * 3
