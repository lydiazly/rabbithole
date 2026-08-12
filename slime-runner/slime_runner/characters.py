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
    # Its own seven poses. They must match POSE_SIZES frame for frame -- a
    # character may look different but may never be a different size, because
    # the hitboxes come from that one table.
    poses: dict = None
    # None, or art to draw behind the head. A type rather than a per-feature
    # flag, so a character with horns instead of ears is a different value here
    # and no new code anywhere.
    accessory: sprites.Accessory | None = None
    accessory_anchors: dict = None

    def __post_init__(self):
        poses = self.poses if self.poses is not None else sprites.SLIME_POSES
        object.__setattr__(self, "poses", poses)
        if set(poses) != set(sprites.POSE_SIZES):
            raise ValueError(f"{self.key}: poses must cover exactly {sorted(sprites.POSE_SIZES)}")
        for name, rows in poses.items():
            sprites.validate(rows)
            if sprites.sprite_size(rows) != sprites.POSE_SIZES[name]:
                raise ValueError(
                    f"{self.key}: pose {name} is {sprites.sprite_size(rows)}, "
                    f"must be {sprites.POSE_SIZES[name]} -- a character cannot "
                    f"change a hitbox"
                )
        object.__setattr__(
            self,
            "accessory_anchors",
            self.accessory.anchors_for(poses) if self.accessory else {},
        )


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
    poses=sprites.CAT_POSES,
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
            look_for_step(character, step), character.poses, character.accessory
        )
    return _sheets[key]
