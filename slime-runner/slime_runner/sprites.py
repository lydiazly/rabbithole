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

SLIME_FRAMES = {
    "round": ROUND,
    "round_b": ROUND_B,
    "stretch1": STRETCH1,
    "stretch2": STRETCH2,
    "squash1": SQUASH1,
    "squash2": SQUASH2,
    "squash3": SQUASH3,
}

# -- obstacles ------------------------------------------------------------

# Three-pixel trunks. A one-pixel trunk is technically a cactus and reads on
# screen as a twig; at this resolution the silhouette needs the weight.
CACTUS_SMALL = (
    "..###..",
    "..###..",
    "..###..",
    "#.###..",
    "#.###.#",
    "#####.#",
    "..#####",
    "..###..",
    "..###..",
    "..###..",
    "..###..",
)

CACTUS_LARGE = (
    "...###...",
    "...###...",
    "...###...",
    "...###...",
    "#..###...",
    "#..###..#",
    "#..###..#",
    "######..#",
    "...######",
    "...###...",
    "...###...",
    "...###...",
    "...###...",
    "...###...",
    "...###...",
    "...###...",
)

FLYER_UP = (
    "###.......###",
    ".###.....###.",
    "..###...###..",
    "...#######...",
    "..o#######...",
    "...#######...",
    "....#####....",
)

FLYER_DOWN = (
    "....#####....",
    "...#######...",
    "..o#######...",
    "...#######...",
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
        "@..",
        "@@.",
        "@o@",
        "@@@",
    ),
    (  # half down
        "...",
        "@@.",
        "@o@",
        "@@@",
    ),
    (  # flicked
        "...",
        ".@.",
        "@o@",
        "@@@",
    ),
)

# Idle twitch, as (frame index, ticks). Kept short deliberately: the gaps between
# jumps in a real run are only a few dozen ticks, and a cycle that opens with a
# long upright hold would spend all of them holding still.
EAR_IDLE = ((0, 14), (1, 8), (0, 16), (1, 5), (2, 6), (1, 5))

EAR_W = 3
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


def _cap_span(rows) -> tuple[int, int]:
    """First and last filled column of a pose's top row."""
    top = rows[0]
    filled = [i for i, char in enumerate(top) if char != TRANSPARENT]
    return filled[0], filled[-1]


def _ear_anchor(rows) -> tuple[int, int, int]:
    """(left x, right x, y) for a pose's ears, relative to its top-left corner.

    Derived from the art rather than hand-authored per pose: the ears have to sit
    on the head's crown, and the crown moves and widens across all seven frames.
    """
    first, last = _cap_span(rows)
    return first - EAR_W + 1, last, EAR_SINK - EAR_H


EAR_ANCHORS = {name: _ear_anchor(rows) for name, rows in SLIME_FRAMES.items()}


class SpriteSheet:
    """Every sprite, coloured for one character at one day/night step."""

    def __init__(self, palette: Palette, look):
        body = {
            "@": look.outline,
            "#": look.body,
            "o": look.sheen,
            "*": look.spec,
        }
        obstacle = {
            "#": palette.obstacle,
            "o": palette.obstacle_dark,
            "@": palette.obstacle_dark,
            "*": palette.obstacle_dark,
        }
        cloud = dict.fromkeys("#o*@", palette.cloud)
        dust = dict.fromkeys("#o*@", palette.dust)
        moon = dict.fromkeys("#o*@", (246, 244, 222))

        self.slime = {n: build(r, body) for n, r in SLIME_FRAMES.items()}
        self.ears = tuple(
            (build(rows, body), build(mirrored(rows), body)) for rows in EAR_LEFT
        )
        self.cactus_small = build(CACTUS_SMALL, obstacle)
        self.cactus_large = build(CACTUS_LARGE, obstacle)
        self.flyer = (build(FLYER_UP, obstacle), build(FLYER_DOWN, obstacle))
        self.clouds = (build(CLOUD_BIG, cloud), build(CLOUD_SMALL, cloud))
        self.moon = build(MOON, moon)
        self.puff = tuple(build(rows, dust) for rows in PUFF)


_sheets: dict[tuple[str, int], SpriteSheet] = {}


def sheet_for(character, step: int, palette: Palette) -> SpriteSheet:
    """Return the cached sprite sheet for a character at a day/night step."""
    from .characters import look_for_step

    key = (character.key, step)
    if key not in _sheets:
        _sheets[key] = SpriteSheet(palette, look_for_step(character, step))
    return _sheets[key]


# Frame sizes are needed for hitboxes and placement before any sheet is built,
# so they come from the art itself rather than from a rendered surface.
SLIME_SIZES = {name: sprite_size(rows) for name, rows in SLIME_FRAMES.items()}

# Every piece of art in one place, for the validation test.
ALL_ART = {
    **{f"slime.{n}": r for n, r in SLIME_FRAMES.items()},
    "cactus_small": CACTUS_SMALL,
    "cactus_large": CACTUS_LARGE,
    "flyer_up": FLYER_UP,
    "flyer_down": FLYER_DOWN,
    "cloud_big": CLOUD_BIG,
    "cloud_small": CLOUD_SMALL,
    "moon": MOON,
    **{f"puff.{i}": r for i, r in enumerate(PUFF)},
    **{f"ear.{i}": r for i, r in enumerate(EAR_LEFT)},
}
