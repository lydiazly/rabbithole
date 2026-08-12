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
    """The tones the body art is drawn in.

    `accent` is a second body colour for two-tone characters -- Bobo's white
    muzzle under a tan forehead. It defaults to the body, so a character with
    one colour never mentions it and its art simply never uses that character.
    """

    body: Color
    sheen: Color
    spec: Color
    outline: Color
    accent: Color | None = None

    def __post_init__(self):
        if self.accent is None:
            object.__setattr__(self, "accent", self.body)


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
    # A separate day/night pair for the accessory when it is not the same stuff
    # as the body -- Jojo's crest is grey feathers on a blue bird. Defaults to
    # the body's own colours, which is what ears want.
    accessory_day: Look | None = None
    accessory_night: Look | None = None
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
        object.__setattr__(self, "accessory_day", self.accessory_day or self.day)
        object.__setattr__(self, "accessory_night", self.accessory_night or self.night)
        object.__setattr__(
            self,
            "accessory_anchors",
            self.accessory.anchors_for(poses) if self.accessory else {},
        )


MOMO = Character(
    key="momo",
    name="MOMO",
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

# Kept warm at night rather than shifted blue like Momo: an orange cat that
# turns blue after dark stops being an orange cat.
COCO = Character(
    key="coco",
    name="COCO",
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

# Sky blue, with a grey crest that is deliberately not tinted by the body's
# colours -- feathers of a different colour are the point of it.
JOJO = Character(
    key="jojo",
    name="JOJO",
    day=Look(
        body=(120, 196, 240),
        sheen=(176, 224, 252),
        spec=(238, 250, 255),
        outline=(34, 100, 152),
    ),
    night=Look(
        body=(118, 152, 228),
        sheen=(166, 194, 250),
        spec=(228, 240, 255),
        outline=(40, 60, 130),
    ),
    poses=sprites.BIRD_POSES,
    accessory=sprites.CREST,
    accessory_day=Look(
        body=(112, 118, 128),
        sheen=(150, 156, 166),
        spec=(196, 202, 210),
        outline=(56, 60, 68),
    ),
    accessory_night=Look(
        body=(96, 104, 124),
        sheen=(132, 140, 160),
        spec=(180, 188, 206),
        outline=(44, 50, 64),
    ),
)

# A shiba: tan above, white muzzle below. The yellow is lighter than Coco's
# orange on purpose -- two warm characters that read the same would be a waste
# of one of them.
BOBO = Character(
    key="bobo",
    name="BOBO",
    day=Look(
        body=(240, 184, 104),
        sheen=(255, 214, 152),
        spec=(255, 246, 226),
        outline=(138, 82, 34),
        accent=(250, 248, 242),
    ),
    night=Look(
        body=(214, 162, 96),
        sheen=(240, 198, 142),
        spec=(255, 238, 214),
        outline=(110, 64, 26),
        accent=(214, 220, 230),
    ),
    poses=sprites.DOG_POSES,
    accessory=sprites.SHIBA_EARS,
)

CHARACTERS = (MOMO, COCO, JOJO, BOBO)
DEFAULT = MOMO


def by_key(key: str) -> Character:
    for character in CHARACTERS:
        if character.key == key:
            return character
    return DEFAULT


def look_for_step(character: Character, step: int) -> Look:
    """The character's colours at a quantised day/night step."""
    return blend(character.day, character.night, step)


def accessory_look_for_step(character: Character, step: int) -> Look:
    return blend(character.accessory_day, character.accessory_night, step)


_sheets: dict[tuple[str, int], sprites.CharacterSheet] = {}


def sheet_for(character: Character, step: int) -> sprites.CharacterSheet:
    """The cached art for a character at a day/night step, built once.

    Note what is *not* a parameter: the palette. A character's colours come from
    itself, so nothing about the world has to be threaded through here.
    """
    key = (character.key, step)
    if key not in _sheets:
        _sheets[key] = sprites.CharacterSheet(
            look_for_step(character, step),
            character.poses,
            character.accessory,
            accessory_look_for_step(character, step),
        )
    return _sheets[key]
