"""Hand-authored pixel art, and the per-palette-step cache that colours it.

Every sprite is written as rows of characters so the shapes stay editable in
place:

    '.'  transparent      '#'  main tone
    'o'  secondary tone   '*'  highlight
    '@'  outline           '%'  second body tone, for two-tone characters

The player's deformation lives here rather than in any simulation: the poses
below *are* the squash and stretch, and `player.py` only decides which one is on
screen. They are anchored bottom-centre, so a wide flat frame spreads along
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
# and it is enough to keep a standing character from looking like a dead sprite.
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

# Also the held pose while ducking: the flattest pose there is.
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
# change a hitbox -- but its own face and chin.
#
# One-pixel eyes and an omega mouth, which read cuter here than the bigger,
# simpler face they briefly replaced.
#
# The silhouette is rounder than a dome: it tapers at the bottom as well as the
# top, so the widest part is the middle rather than everything below the brow.
#
# The row under the crown is a pixel wider each side than the shape strictly
# wants, and that is what sets the ears apart. Their anchor is derived from that
# row -- see Accessory.anchors_for -- so spreading them is a matter of the head
# they sit on, not an offset bolted onto the drawing code, which is what would
# put back the notch under the ears that the anchor rule exists to avoid.

CAT_ROUND = (
    "...@@@@@@@@...",
    ".@@oo######@@.",
    "@#o**o#######@",
    "@#ooo########@",
    "@#oo#########@",
    "@#o##########@",
    "@#o#@####@###@",
    "@###@####@###@",
    "@############@",
    "@###@#@@#@###@",
    ".@###@##@###@.",
    "..@@@@@@@@@@..",
)

CAT_ROUND_B = (
    "...@@@@@@@@...",
    ".@@oo######@@.",
    "@#o**o#######@",
    "@#ooo########@",
    "@#oo#########@",
    "@#o#@####@###@",
    "@###@####@###@",
    "@############@",
    "@###@#@@#@###@",
    ".@###@##@###@.",
    "..@@@@@@@@@@..",
)

CAT_STRETCH1 = (
    "...@@@@@@...",
    ".@@oo####@@.",
    "@#o**o#####@",
    "@#ooo######@",
    "@#oo#######@",
    "@#o########@",
    "@#o########@",
    "@#o@####@##@",
    "@##@####@##@",
    "@##########@",
    "@##@#@@#@##@",
    ".@##@##@##@.",
    ".@########@.",
    "..@@@@@@@@..",
)

CAT_STRETCH2 = (
    "...@@@@...",
    "@@oo####@@",
    "@#o**o###@",
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
    ".@######@.",
    ".@######@.",
    "..@@@@@@..",
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
    ".@####@##@####@.",
    "..@@@@@@@@@@@@..",
)

CAT_SQUASH2 = (
    "....@@@@@@@@@@....",
    "..@oo##########@..",
    ".@o**o##########@.",
    "@#ooo@######@####@",
    "@#o##@######@####@",
    "@#####@#@@#@#####@",
    ".@#####@##@#####@.",
    "..@@@@@@@@@@@@@@..",
)

CAT_SQUASH3 = (
    ".....@@@@@@@@@@.....",
    "..@o**o##########@..",
    "@#ooo#@######@#####@",
    "@########@@########@",
    ".@################@.",
    "..@@@@@@@@@@@@@@@@..",
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

# -- the bird --------------------------------------------------------------
#
# A rice ball rather than a dome: narrow at the crown and widening to a flat
# base. Eyes sit a row lower than the slime's but stay one pixel, and the beak is
# a two-row wedge. Same seven sizes as everybody else.
#
# The shoulders reach full width early on purpose. The hitbox is one rectangle
# shared by every character, so a sloping shape leaves air inside it -- which
# costs nothing in difficulty, since the box is identical either way, but makes
# a death look like it happened beside the bird rather than to it. Filling the
# middle and lower rows took that from 10% of the box down to 3%. The top row or
# two stay narrow: air up there is what keeps the rice ball a rice ball, and
# nothing about the collision changes.

BIRD_ROUND = (
    ".....@@@@.....",
    "...@o#####@...",
    "..@*o######@..",
    ".@ooo#######@.",
    ".@oo########@.",
    "@#oo#########@",
    "@#o#@####@###@",
    "@############@",
    "@####@@@@####@",
    "@#####@@#####@",
    "@############@",
    "@@@@@@@@@@@@@@",
)

BIRD_ROUND_B = (
    ".....@@@@.....",
    "...@o#####@...",
    "..@*o######@..",
    ".@ooo#######@.",
    "@#oo#########@",
    "@#o#@####@###@",
    "@############@",
    "@####@@@@####@",
    "@#####@@#####@",
    "@############@",
    "@@@@@@@@@@@@@@",
)

BIRD_STRETCH1 = (
    "....@@@@....",
    "...@o###@...",
    "..@*o####@..",
    "..@oo####@..",
    ".@ooo#####@.",
    ".@oo######@.",
    ".@o@####@#@.",
    ".@o#######@.",
    ".@########@.",
    "@###@@@@###@",
    "@####@@####@",
    "@##########@",
    "@##########@",
    "@@@@@@@@@@@@",
)

BIRD_STRETCH2 = (
    "...@@@@...",
    "..@o###@..",
    ".@*o####@.",
    ".@oo####@.",
    ".@oo####@.",
    ".@o#####@.",
    ".@o@##@#@.",
    ".@o#####@.",
    ".@o@@@@#@.",
    ".@o#@@##@.",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    "@########@",
    "@@@@@@@@@@",
)

BIRD_SQUASH1 = (
    ".....@@@@@@.....",
    "...@*o######@...",
    ".@ooo##########@",
    ".@o##@####@###@.",
    "@##############@",
    "@#####@@@@#####@",
    "@######@@######@",
    "@##############@",
    "@##############@",
    "@@@@@@@@@@@@@@@@",
)

BIRD_SQUASH2 = (
    ".....@@@@@@@@.....",
    "..@*o##########@..",
    ".@oo##@####@####@.",
    "@######@@@@######@",
    "@#######@@#######@",
    "@################@",
    "@################@",
    "@@@@@@@@@@@@@@@@@@",
)

BIRD_SQUASH3 = (
    ".....@@@@@@@@@@.....",
    ".@*o###@####@#####@.",
    "@#######@@@@#######@",
    "@########@@########@",
    "@##################@",
    "@@@@@@@@@@@@@@@@@@@@",
)

BIRD_POSES = {
    "round": BIRD_ROUND,
    "round_b": BIRD_ROUND_B,
    "stretch1": BIRD_STRETCH1,
    "stretch2": BIRD_STRETCH2,
    "squash1": BIRD_SQUASH1,
    "squash2": BIRD_SQUASH2,
    "squash3": BIRD_SQUASH3,
}

# -- the dog ---------------------------------------------------------------
#
# Coco's silhouette with a narrower chin, and a shiba's two-tone mask: tan above,
# white muzzle below, drawn with the '%' second body tone. Big dark nose, small
# mouth under it.

DOG_ROUND = (
    "....@@@@@@....",
    "..@@oo####@@..",
    ".@o**o######@.",
    ".@ooo#######@.",
    "@#ooo########@",
    "@#oo@####@###@",
    "@#o#@####@###@",
    "@%%%%%%%%%%%%@",
    "@%%%%%%%%%%%%@",
    ".@%%%@@@@%%%@.",
    ".@%%%@%%@%%%@.",
    "..@@@@@@@@@@..",
)

DOG_ROUND_B = (
    "....@@@@@@....",
    "..@@oo####@@..",
    ".@o**o######@.",
    "@#ooo########@",
    "@#oo@####@###@",
    "@#o#@####@###@",
    "@%%%%%%%%%%%%@",
    "@%%%%%%%%%%%%@",
    ".@%%%@@@@%%%@.",
    ".@%%%@%%@%%%@.",
    "..@@@@@@@@@@..",
)

DOG_STRETCH1 = (
    "...@@@@@@...",
    "..@@oo##@@..",
    ".@o**o####@.",
    ".@ooo#####@.",
    "@#ooo######@",
    "@#oo#######@",
    "@#o########@",
    "@#o@####@##@",
    "@##@####@##@",
    "@%%%%%%%%%%@",
    "@%%%%%%%%%%@",
    ".@%%@@@@%%@.",
    ".@%%@%%@%%@.",
    "..@@@@@@@@..",
)

DOG_STRETCH2 = (
    "...@@@@...",
    ".@@oo#@@@.",
    ".@o**o##@.",
    ".@ooo###@.",
    "@#ooo####@",
    "@#oo#####@",
    "@#o######@",
    "@#o@##@##@",
    "@##@##@##@",
    "@%%%%%%%%@",
    "@%%%%%%%%@",
    "@%%%%%%%%@",
    "@%%@@@@%%@",
    "@%%@%%@%%@",
    "@%%%%%%%%@",
    ".@%%%%%%@.",
    "..@@@@@@..",
)

DOG_SQUASH1 = (
    "....@@@@@@@@....",
    "..@@oo######@@..",
    ".@o**o########@.",
    "@#ooo##########@",
    "@#oo@######@###@",
    "@#o#@######@###@",
    "@%%%%%%%%%%%%%%@",
    ".@%%%%@@@@%%%%@.",
    ".@%%%%@%%@%%%%@.",
    "..@@@@@@@@@@@@..",
)

DOG_SQUASH2 = (
    "....@@@@@@@@@@....",
    "..@oo##########@..",
    ".@o**o##########@.",
    "@#ooo@######@####@",
    "@#o##@######@####@",
    "@%%%%%%%%%%%%%%%%@",
    ".@%%%%%@@@@%%%%%@.",
    "..@@@@@@@@@@@@@@..",
)

DOG_SQUASH3 = (
    ".....@@@@@@@@@@.....",
    "..@o**o##########@..",
    "@#ooo#@######@#####@",
    "@%%%%%%%%%%%%%%%%%%@",
    ".@%%%%%%@@@@%%%%%%@.",
    "..@@@@@@@@@@@@@@@@..",
)

DOG_POSES = {
    "round": DOG_ROUND,
    "round_b": DOG_ROUND_B,
    "stretch1": DOG_STRETCH1,
    "stretch2": DOG_STRETCH2,
    "squash1": DOG_SQUASH1,
    "squash2": DOG_SQUASH2,
    "squash3": DOG_SQUASH3,
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
# Five rows rather than four, with a lit inner ear: Stardew's cats have big
# ears, and the extra row all sits above the head where nothing collides.
EAR_LEFT = (
    (  # upright
        "@...",
        "@@..",
        "@o@.",
        "@oo@",
        "@@@@",
    ),
    (  # half down
        "....",
        "@@..",
        "@o@.",
        "@oo@",
        "@@@@",
    ),
    (  # folded
        "....",
        "....",
        "@@@.",
        "@oo@",
        "@@@@",
    ),
)

# Idle twitch, as (frame index, ticks). Kept short deliberately: the gaps between
# jumps in a real run are only a few dozen ticks, and a cycle that opens with a
# long upright hold would spend all of them holding still.
EAR_IDLE = ((0, 14), (1, 8), (0, 16), (1, 5), (2, 6), (1, 5))

# A shiba's ears are thicker and blunter than a cat's: a broad two-pixel tip on
# a wide base, where Coco's taper to a single pixel.
SHIBA_EAR_LEFT = (
    (  # upright
        "@@..",
        "@#@.",
        "@##@",
        "@@@@",
    ),
    (  # half down
        "....",
        "@@@.",
        "@##@",
        "@@@@",
    ),
    (  # flicked
        "....",
        ".@@.",
        "@##@",
        "@@@@",
    ),
)

# Rows of accessory tucked behind the head, so it reads as attached rather than
# as a hat balanced on top.
EAR_SINK = 1

# -- the bird's crest ------------------------------------------------------
#
# A single centred tuft rather than a mirrored pair, which is why `Accessory`
# takes a placement at all. Two pixels wide so it centres exactly: every pose is
# an even number of pixels across.
TUFT = (
    (  # leaning right
        "..@.",
        ".@#.",
        "@##.",
        "@@@@",
    ),
    (  # leaning left
        ".@..",
        ".#@.",
        ".##@",
        "@@@@",
    ),
)

TUFT_IDLE = ((0, 22), (1, 20))

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
VALID_CHARS = set(".#o*@%")


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

    def __init__(self, frames, idle, sink: int = 1, paired: bool = True):
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
        self.paired = paired
        self.width, self.height = sizes.pop()
        self.cycle = sum(ticks for _, ticks in self.idle)

    def anchors_for(self, poses) -> dict:
        """Per pose: (y, ((x, mirrored), ...)) relative to its top-left corner.

        A list of placements rather than a fixed left/right pair, because not
        every accessory is symmetric about the head: ears are two mirrored
        copies on the shoulders, a crest is one piece in the middle.

        Computed from the wearer's own art -- a character with its own poses has
        its own crowns, and reading them off somebody else's would put the
        accessory in the wrong place.

        A paired accessory aligns to the row *below* the crown rather than the
        crown itself. Its base is its widest row and sits level with the crown,
        so anchoring to the crown pushed it a pixel wider than the head
        immediately underneath: the outline pinched inward right below the ears
        and the triangle stopped reading as one.
        """
        anchors = {}
        for name, rows in poses.items():
            dy = self.sink - self.height
            if not self.paired:
                width = len(rows[0])
                if (width - self.width) % 2:
                    raise ValueError(
                        f"pose {name} is {width}px wide, which cannot centre a "
                        f"{self.width}px accessory on the pixel grid"
                    )
                anchors[name] = (dy, (((width - self.width) // 2, False),))
                continue
            first, last = _span(rows[1] if len(rows) > 1 else rows[0])
            left = first
            right = last - self.width + 1
            if left + self.width > right:
                raise ValueError(
                    f"pose {name} is too narrow for a {self.width}px accessory: "
                    f"the two sides would overlap"
                )
            anchors[name] = (dy, ((left, False), (right, True)))
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
SHIBA_EARS = Accessory(SHIBA_EAR_LEFT, EAR_IDLE, sink=EAR_SINK)
CREST = Accessory(TUFT, TUFT_IDLE, sink=1, paired=False)


class CharacterSheet:
    """One character's poses and accessory, at one day/night step."""

    def __init__(self, look, poses, accessory: Accessory | None, accessory_look=None):
        def tones_of(l):
            return {
                "@": l.outline,
                "#": l.body,
                "o": l.sheen,
                "*": l.spec,
                "%": l.accent,
            }

        self.poses = {n: build(r, tones_of(look)) for n, r in poses.items()}
        # Both facings are built even for a centred accessory: it is two tiny
        # surfaces, and it keeps the draw code from having to know which kind it
        # is holding. A character without one builds neither.
        extra = tones_of(accessory_look or look)
        self.accessory = tuple(
            (build(rows, extra), build(mirrored(rows), extra))
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
            "%": palette.obstacle,
        }
        cloud = dict.fromkeys("#o*@%", palette.cloud)
        dust = dict.fromkeys("#o*@%", palette.dust)
        moon = dict.fromkeys("#o*@%", palette.moon)

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
    **{f"bird.{n}": r for n, r in BIRD_POSES.items()},
    **{f"dog.{n}": r for n, r in DOG_POSES.items()},
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
    **{f"tuft.{i}": r for i, r in enumerate(TUFT)},
    **{f"shiba_ear.{i}": r for i, r in enumerate(SHIBA_EAR_LEFT)},
}
