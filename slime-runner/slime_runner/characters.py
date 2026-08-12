"""The playable characters.

A character is a recolour of the same seven poses plus, optionally, ears drawn
behind the head. Nothing about the motion or the frame timing changes between
them — swapping character must never swap difficulty.

Each carries its own day and night colours and interpolates between them on the
same quantised steps the world does, so a character stays lit consistently with
the sky it is standing under.
"""

from dataclasses import dataclass

from . import sprites
from .palette import Color, blend


@dataclass(frozen=True)
class Look:
    """The four tones the body art is drawn in."""

    body: Color
    sheen: Color
    spec: Color
    outline: Color


@dataclass(frozen=True)
class Character:
    key: str
    name: str
    day: Look
    night: Look
    # None, or art to draw behind the head. A type rather than a per-feature
    # flag, so a character with horns instead of ears is a different value here
    # and no new code anywhere.
    accessory: sprites.Accessory | None = None


SLIME = Character(
    key="slime",
    name="SLIME",
    day=Look(
        body=(92, 208, 168),
        sheen=(146, 236, 205),
        spec=(232, 255, 246),
        outline=(28, 94, 86),
    ),
    night=Look(
        body=(128, 156, 246),
        sheen=(176, 200, 255),
        spec=(240, 246, 255),
        outline=(46, 60, 130),
    ),
)

# Kept warm at night rather than shifted blue like the slime: an orange cat that
# turns blue after dark stops being an orange cat.
CAT = Character(
    key="cat",
    name="CAT",
    day=Look(
        body=(242, 152, 72),
        sheen=(255, 198, 126),
        spec=(255, 242, 214),
        outline=(146, 68, 20),
    ),
    night=Look(
        body=(226, 140, 66),
        sheen=(250, 186, 112),
        spec=(255, 232, 198),
        outline=(120, 56, 18),
    ),
    accessory=sprites.EARS,
)

CHARACTERS = (SLIME, CAT)
DEFAULT = SLIME


def by_key(key: str) -> Character:
    for character in CHARACTERS:
        if character.key == key:
            return character
    return DEFAULT


def look_for_step(character: Character, step: int) -> Look:
    """The character's colours at a quantised day/night step."""
    return blend(character.day, character.night, step)


_sheets: dict[tuple[str, int], sprites.CharacterSheet] = {}


def sheet_for(character: Character, step: int) -> sprites.CharacterSheet:
    """The cached art for a character at a day/night step, built once.

    Note what is *not* a parameter: the palette. A character's colours come from
    itself, so nothing about the world has to be threaded through here.
    """
    key = (character.key, step)
    if key not in _sheets:
        _sheets[key] = sprites.CharacterSheet(
            look_for_step(character, step), character.accessory
        )
    return _sheets[key]
