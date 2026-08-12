"""Hand-authored pixel art, and the per-palette-step cache that colours it.

Every sprite is written as rows of characters so the shapes stay editable in
place:

    '.'  transparent      '#'  main tone
    'o'  secondary tone   '*'  highlight
    '@'  outline

The slime's deformation lives here rather than in any simulation: the seven
frames below *are* the squash and stretch, and `slime.py` only decides which one
is on screen. They are anchored bottom-centre, so a wide flat frame spreads along
the ground instead of sinking through it.
"""

import pygame

from .palette import Palette

# -- the slime ------------------------------------------------------------

ROUND = (
    "....@@@@@@....",
    "..@@oo####@@..",
    ".@o**o######@.",
    ".@ooo#######@.",
    "@#ooo########@",
    "@#oo@####@###@",
    "@#o##########@",
    "@#####@@#####@",
    "@############@",
    "@############@",
    "@############@",
    "@@@@@@@@@@@@@@",
)

# One pixel squatter than ROUND. Alternating the two is the whole idle animation,
# and it is enough to keep a standing slime from looking like a dead sprite.
ROUND_B = (
    "....@@@@@@....",
    "..@@oo####@@..",
    ".@o**o######@.",
    "@#ooo########@",
    "@#oo@####@###@",
    "@#o##########@",
    "@#####@@#####@",
    "@############@",
    "@############@",
    "@############@",
    "@@@@@@@@@@@@@@",
)

STRETCH1 = (
    "...@@@@@@...",
    "..@@oo##@@..",
    ".@o**o####@.",
    ".@ooo#####@.",
    "@#ooo######@",
    "@#oo#######@",
    "@#o@####@##@",
    "@#o########@",
    "@####@@####@",
    "@##########@",
    "@##########@",
    "@##########@",
    "@##########@",
    "@@@@@@@@@@@@",
)

STRETCH2 = (
    "...@@@@...",
    "..@oo#@@..",
    ".@o**o##@.",
    ".@ooo###@.",
    "@#ooo####@",
    "@#oo#####@",
    "@#o@##@##@",
    "@#o######@",
    "@###@@###@",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    "@@@@@@@@@@",
)

SQUASH1 = (
    "....@@@@@@@@....",
    "..@@oo######@@..",
    ".@o**o########@.",
    "@#ooo##########@",
    "@#oo@######@###@",
    "@#o############@",
    "@######@@######@",
    "@##############@",
    "@##############@",
    "@@@@@@@@@@@@@@@@",
)

SQUASH2 = (
    "....@@@@@@@@@@....",
    "..@oo##########@..",
    ".@o**o##########@.",
    "@#ooo@######@####@",
    "@#######@@#######@",
    "@################@",
    "@################@",
    "@@@@@@@@@@@@@@@@@@",
)

# Also the held pose while ducking: the flattest the slime ever gets.
SQUASH3 = (
    ".....@@@@@@@@@@.....",
    "..@o**o##########@..",
    "@#ooo#@######@#####@",
    "@########@@########@",
    "@##################@",
    "@@@@@@@@@@@@@@@@@@@@",
)

SLIME_POSES = {
    "round": ROUND,
    "round_b": ROUND_B,
    "stretch1": STRETCH1,
    "stretch2": STRETCH2,
    "squash1": SQUASH1,
    "squash2": SQUASH2,
    "squash3": SQUASH3,
}

# -- the cat ---------------------------------------------------------------
#
# The same seven silhouettes at exactly the same sizes -- a character may not
# change a hitbox -- but its own face and chin. Eyes sit lower than the slime's
# and are two pixels tall rather than one, the mouth is an omega, and the bottom
# row is inset so the chin reads round where the slime's is flat.

CAT_ROUND = (
    "....@@@@@@....",
    "..@@oo####@@..",
    ".@o**o######@.",
    ".@ooo#######@.",
    "@#ooo########@",
    "@#oo#########@",
    "@#o#@####@###@",
    "@###@####@###@",
    "@############@",
    "@###@#@@#@###@",
    "@####@##@####@",
    ".@@@@@@@@@@@@.",
)

CAT_ROUND_B = (
    "....@@@@@@....",
    "..@@oo####@@..",
    ".@o**o######@.",
    "@#ooo########@",
    "@#oo#########@",
    "@#o#@####@###@",
    "@###@####@###@",
    "@############@",
    "@###@#@@#@###@",
    "@####@##@####@",
    ".@@@@@@@@@@@@.",
)

CAT_STRETCH1 = (
    "...@@@@@@...",
    "..@@oo##@@..",
    ".@o**o####@.",
    ".@ooo#####@.",
    "@#ooo######@",
    "@#oo#######@",
    "@#o########@",
    "@#o@####@##@",
    "@##@####@##@",
    "@##########@",
    "@##@#@@#@##@",
    "@###@##@###@",
    "@##########@",
    ".@@@@@@@@@@.",
)

CAT_STRETCH2 = (
    "...@@@@...",
    ".@@oo#@@@.",
    ".@o**o##@.",
    ".@ooo###@.",
    "@#ooo####@",
    "@#oo#####@",
    "@#o######@",
    "@#o@##@##@",
    "@##@##@##@",
    "@########@",
    "@#@#@@#@#@",
    "@##@##@##@",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    ".@@@@@@@@.",
)

CAT_SQUASH1 = (
    "....@@@@@@@@....",
    "..@@oo######@@..",
    ".@o**o########@.",
    "@#ooo##########@",
    "@#oo@######@###@",
    "@#o#@######@###@",
    "@##############@",
    "@####@#@@#@####@",
    "@#####@##@#####@",
    ".@@@@@@@@@@@@@@.",
)

CAT_SQUASH2 = (
    "....@@@@@@@@@@....",
    "..@oo##########@..",
    ".@o**o##########@.",
    "@#ooo@######@####@",
    "@#o##@######@####@",
    "@#####@#@@#@#####@",
    "@######@##@######@",
    ".@@@@@@@@@@@@@@@@.",
)

CAT_SQUASH3 = (
    ".....@@@@@@@@@@.....",
    "..@o**o##########@..",
    "@#ooo#@######@#####@",
    "@#####@######@#####@",
    "@######@#@@#@######@",
    ".@@@@@@@@@@@@@@@@@@.",
)

CAT_POSES = {
    "round": CAT_ROUND,
    "round_b": CAT_ROUND_B,
    "stretch1": CAT_STRETCH1,
    "stretch2": CAT_STRETCH2,
    "squash1": CAT_SQUASH1,
    "squash2": CAT_SQUASH2,
    "squash3": CAT_SQUASH3,
}

# -- obstacles ------------------------------------------------------------

# Three-pixel trunks. A one-pixel trunk is technically a cactus and reads on
# screen as a twig; at this resolution the silhouette needs the weight.
#
# The 'o' pixels are a dark edge along the top and one side, and they are not
# decoration. An obstacle's fill ramps from dark by day to light by night while
# the sky behind it ramps the other way, so the two must cross, and at the
# crossing the fill alone is invisible -- 46 of 255 at dusk, less in snow. The
# edge tone never flips, so it carries those steps exactly as a character's
# outline carries the ones where its body washes out.
CACTUS_SMALL = (
    "..ooo..",
    "..o##..",
    "..o##..",
    "#.o##..",
    "#.o##.#",
    "##o##.#",
    "..o####",
    "..o##..",
    "..o##..",
    "..o##..",
    "..o##..",
)

CACTUS_LARGE = (
    "...ooo...",
    "...o##...",
    "...o##...",
    "...o##...",
    "#..o##...",
    "#..o##..#",
    "#..o##..#",
    "###o##..#",
    "...o#####",
    "...o##...",
    "...o##...",
    "...o##...",
    "...o##...",
    "...o##...",
    "...o##...",
    "...o##...",
)

# Snow's ground pair. Same footprints as the cacti (7x11 and 9x16) with the same
# solid core, so they drop into the same hitboxes and the scene cannot change how
# hard the game is — the rule that holds for characters holds for scenery too.
PINE_SMALL = (
    "...o...",
    "..o#o..",
    ".o###o.",
    "..o#o..",
    ".o###o.",
    "o#####o",
    ".o###o.",
    "o#####o",
    "..ooo..",
    "..o#o..",
    "..ooo..",
)

PINE = (
    "....o....",
    "...o#o...",
    "..o###o..",
    "..o###o..",
    ".o#####o.",
    "..o###o..",
    ".o#####o.",
    "o#######o",
    ".o#####o.",
    "o#######o",
    "...ooo...",
    "...o#o...",
    "...o#o...",
    "...o#o...",
    "...o#o...",
    "...ooo...",
)

FLYER_UP = (
    "###.......###",
    ".###.....###.",
    "..###...###..",
    "...#######...",
    "..o#######...",
    "...ooooooo...",
    "....ooooo....",
)

FLYER_DOWN = (
    "....#####....",
    "...#######...",
    "..o#######...",
    "...ooooooo...",
    "..###...###..",
    ".###.....###.",
    "###.......###",
)

# -- ears -----------------------------------------------------------------
#
# Drawn *behind* the body, so only the part clearing the head shows and the base
# never paints over the head's own outline. Authored as the left ear; the right
# one is this mirrored.
EAR_LEFT = (
    (  # upright
        "@...",
        "@@..",
        "@o@.",
        "@@@@",
    ),
    (  # half down
        "....",
        "@@..",
        "@o@.",
        "@@@@",
    ),
    (  # flicked
        "....",
        ".@..",
        "@o@.",
        "@@@@",
    ),
)

# Idle twitch, as (frame index, ticks). Kept short deliberately: the gaps between
# jumps in a real run are only a few dozen ticks, and a cycle that opens with a
# long upright hold would spend all of them holding still.
EAR_IDLE = ((0, 14), (1, 8), (0, 16), (1, 5), (2, 6), (1, 5))

EAR_W = 4
EAR_H = 4
# Rows of ear tucked behind the head, so it reads as attached rather than as a
# hat balanced on top.
EAR_SINK = 1

# -- scenery and effects --------------------------------------------------

CLOUD_BIG = (
    "..####.....",
    ".########..",
    "###########",
    ".#########.",
)

CLOUD_SMALL = (
    "..###..",
    ".#####.",
    "#######",
)

MOON = (
    "..###..",
    ".##..#.",
    "##.....",
    "##.....",
    "##.....",
    ".##..#.",
    "..###..",
)

PUFF = (
    (
        "..#...#..",
        ".###.###.",
        "..#...#..",
    ),
    (
        ".#.....#.",
        "#.#...#.#",
        ".#.....#.",
    ),
    (
        "#.......#",
        ".........",
        "#.......#",
    ),
)

TRANSPARENT = "."
VALID_CHARS = set(".#o*@")


def sprite_size(rows) -> tuple[int, int]:
    return len(rows[0]), len(rows)


def validate(rows) -> None:
    """Raise if the art is ragged or uses an unknown character.

    Hand-authored ASCII is easy to get subtly wrong — one short row shifts every
    pixel after it — so this runs over every sprite in the test suite and again
    whenever one is built.
    """
    w, _ = sprite_size(rows)
    for y, row in enumerate(rows):
        if len(row) != w:
            raise ValueError(f"row {y} is {len(row)} wide, expected {w}")
        unknown = set(row) - VALID_CHARS
        if unknown:
            raise ValueError(f"row {y} uses unknown characters {sorted(unknown)}")


def build(rows, colors) -> pygame.Surface:
    """Turn character rows into a Surface."""
    validate(rows)
    w, h = sprite_size(rows)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char != TRANSPARENT:
                surf.set_at((x, y), colors[char])
    return surf


def mirrored(rows):
    return tuple(row[::-1] for row in rows)


def _span(row) -> tuple[int, int]:
    """First and last filled column of one row."""
    filled = [i for i, char in enumerate(row) if char != TRANSPARENT]
    return filled[0], filled[-1]


class Accessory:
    """Art drawn behind the head on both sides, with its own idle cycle.

    Ears are the only one so far. It is a type rather than a flag on the
    character so that the next one — horns, a cap, whatever — is art plus a
    timing table, with no branch to add in the drawing code.

    Anchors are derived from each pose's crown rather than authored per pose:
    the crown moves and widens across all seven frames, and an accessory has to
    follow it.
    """

    def __init__(self, frames, idle, sink: int = 1):
        if not frames:
            raise ValueError("an accessory needs at least one frame")
        sizes = set()
        for rows in frames:
            validate(rows)
            sizes.add(sprite_size(rows))
        if len(sizes) != 1:
            raise ValueError(f"accessory frames differ in size: {sorted(sizes)}")
        if {i for i, _ in idle} != set(range(len(frames))):
            raise ValueError("the idle cycle must use every frame, and only those")

        self.frames = tuple(frames)
        self.idle = tuple(idle)
        self.sink = sink
        self.width, self.height = sizes.pop()
        self.cycle = sum(ticks for _, ticks in self.idle)

    def anchors_for(self, poses) -> dict:
        """(left x, right x, y) per pose, relative to its top-left corner.

        Computed from the wearer's own art -- a character with its own poses has
        its own crowns, and reading them off somebody else's would put the ears
        in the wrong place.

        Aligned to the row *below* the crown rather than the crown itself. The
        accessory's base is its widest row and sits level with the crown, so
        anchoring to the crown pushed it a pixel wider than the head immediately
        underneath: the outline pinched inward right below the ears and the
        triangle stopped reading as one.
        """
        anchors = {}
        for name, rows in poses.items():
            first, last = _span(rows[1] if len(rows) > 1 else rows[0])
            left = first
            right = last - self.width + 1
            if left + self.width > right:
                raise ValueError(
                    f"pose {name} is too narrow for a {self.width}px accessory: "
                    f"the two sides would overlap"
                )
            anchors[name] = (left, right, self.sink - self.height)
        return anchors

    def frame_at(self, tick: int) -> int:
        """Where the idle cycle has got to, as a function of a tick count."""
        tick %= self.cycle
        for frame, ticks in self.idle:
            if tick < ticks:
                return frame
            tick -= ticks
        return 0


EARS = Accessory(EAR_LEFT, EAR_IDLE, sink=EAR_SINK)


class CharacterSheet:
    """One character's poses and accessory, at one day/night step."""

    def __init__(self, look, poses, accessory: Accessory | None):
        tones = {
            "@": look.outline,
            "#": look.body,
            "o": look.sheen,
            "*": look.spec,
        }
        self.poses = {n: build(r, tones) for n, r in poses.items()}
        # Left and right are built together so a character without an accessory
        # builds neither, rather than paying for ears it never wears.
        self.accessory = tuple(
            (build(rows, tones), build(mirrored(rows), tones))
            for rows in (accessory.frames if accessory else ())
        )


class WorldSheet:
    """Everything a scene draws, at one day/night step.

    Split from the character deliberately. These sprites do not depend on who is
    playing, and while they shared a sheet every one of them was rebuilt and held
    once per character.

    The obstacle art arrives as a parameter rather than being baked in: that is
    what lets two scenes share the flyer and differ on the ground, or share every
    shape and differ only in colour.
    """

    def __init__(self, palette: Palette, ground_art, flyer_art):
        obstacle = {
            "#": palette.obstacle,
            "o": palette.obstacle_dark,
            "@": palette.obstacle_dark,
            "*": palette.obstacle_dark,
        }
        cloud = dict.fromkeys("#o*@", palette.cloud)
        dust = dict.fromkeys("#o*@", palette.dust)
        moon = dict.fromkeys("#o*@", palette.moon)

        # Keyed by Obstacle.kind, so a new ground hazard is an entry here and a
        # spawn rule, not another branch in the draw code.
        self.ground = {kind: build(rows, obstacle) for kind, rows in ground_art.items()}
        self.flyer = tuple(build(rows, obstacle) for rows in flyer_art)
        self.clouds = (build(CLOUD_BIG, cloud), build(CLOUD_SMALL, cloud))
        self.moon = build(MOON, moon)
        self.puff = tuple(build(rows, dust) for rows in PUFF)


# Frame sizes are needed for hitboxes and placement before any sheet is built,
# so they come from the art itself rather than from a rendered surface.
POSE_SIZES = {name: sprite_size(rows) for name, rows in SLIME_POSES.items()}

# Every piece of art in one place, for the validation test.
ALL_ART = {
    **{f"slime.{n}": r for n, r in SLIME_POSES.items()},
    **{f"cat.{n}": r for n, r in CAT_POSES.items()},
    "cactus_small": CACTUS_SMALL,
    "cactus_large": CACTUS_LARGE,
    "pine_small": PINE_SMALL,
    "pine": PINE,
    "flyer_up": FLYER_UP,
    "flyer_down": FLYER_DOWN,
    "cloud_big": CLOUD_BIG,
    "cloud_small": CLOUD_SMALL,
    "moon": MOON,
    **{f"puff.{i}": r for i, r in enumerate(PUFF)},
    **{f"ear.{i}": r for i, r in enumerate(EAR_LEFT)},
}
