"""The places a run happens: which elements are drawn, in which colours.

A scene is data, not code. It names the art for each obstacle role, the set of
background and terrain layers it wants, and a day and a night palette. Elements
are shared freely — snow reuses the desert's flyer and simply paints it a
different colour, while replacing the ground pair entirely.

Two rules hold a scene to being decoration only:

* the layer *order* is fixed, in `world.py`, back to front. A scene chooses what
  is drawn, never what covers what.
* obstacle art must fit the same hitboxes for every scene. Picking a place must
  not pick a difficulty, exactly as picking a character must not.
"""

from dataclasses import dataclass, field

from . import sprites
from .palette import Palette, blend, luminance

# Every optional layer, back to front. A scene lists the ones it wants; the sky,
# the ground and the obstacles are not optional and are not listed here.
LAYERS = (
    "horizon",
    "moon",
    "stars",
    "clouds",
    "hills_far",
    "hills_near",
    "speckles",
)


@dataclass(frozen=True)
class Scene:
    key: str
    name: str
    day: Palette
    night: Palette
    # Obstacle art by Obstacle.kind. The keys are the roles world.py spawns, so a
    # scene missing one would crash on the first spawn -- checked below instead.
    ground: dict
    flyer: tuple
    layers: frozenset = field(default_factory=lambda: frozenset(LAYERS))

    def __post_init__(self):
        unknown = self.layers - set(LAYERS)
        if unknown:
            # A typo here would silently switch a layer off rather than fail, and
            # the scene would just quietly be missing its hills.
            raise ValueError(f"{self.key}: unknown layers {sorted(unknown)}")
        for kind, rows in self.ground.items():
            sprites.validate(rows)
        for rows in self.flyer:
            sprites.validate(rows)

    def has(self, layer: str) -> bool:
        return layer in self.layers


DESERT = Scene(
    key="desert",
    name="DESERT",
    day=Palette(
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
        star=(255, 255, 255),
        moon=(246, 244, 222),
        text=(44, 62, 74),
    ),
    night=Palette(
        sky=(22, 26, 56),
        horizon=(44, 40, 82),
        hill_far=(38, 42, 80),
        hill_near=(26, 30, 60),
        ground=(58, 54, 78),
        # Both of these stay *darker* than their own ground, exactly as the day
        # pair does. Flipping the direction would make the two ramps cross
        # mid-dusk and the ground would go flat for the whole transition.
        ground_line=(34, 30, 52),
        speckle=(42, 38, 60),
        # These, by contrast, deliberately flip: an obstacle has to stand out
        # from the background, and at night that means lighter, not darker.
        obstacle=(146, 152, 180),
        # The edge stays dark at both ends while the fill flips. The two ramps
        # must not both track the background, or they cross it together and the
        # obstacle vanishes at dusk.
        obstacle_dark=(28, 36, 54),
        dust=(92, 88, 118),
        cloud=(88, 90, 124),
        star=(255, 255, 255),
        moon=(246, 244, 222),
        text=(222, 228, 246),
    ),
    ground={"small": sprites.CACTUS_SMALL, "large": sprites.CACTUS_LARGE},
    flyer=(sprites.FLYER_UP, sprites.FLYER_DOWN),
)

# Snow differs three ways on purpose, one per axis the parameterisation claims to
# cover: different ground art, the same flyer in a different colour, and a layer
# switched off entirely -- no clouds, for a hard cold sky.
SNOW = Scene(
    key="snow",
    name="SNOW",
    day=Palette(
        sky=(198, 226, 240),
        horizon=(224, 240, 248),
        hill_far=(176, 200, 218),
        hill_near=(146, 174, 198),
        ground=(238, 244, 250),
        ground_line=(184, 198, 214),
        speckle=(206, 218, 230),
        obstacle=(58, 96, 92),
        obstacle_dark=(34, 64, 62),
        dust=(214, 226, 238),
        cloud=(255, 255, 255),
        star=(255, 255, 255),
        moon=(246, 244, 222),
        text=(38, 56, 70),
    ),
    night=Palette(
        sky=(18, 24, 48),
        horizon=(36, 44, 76),
        hill_far=(44, 54, 88),
        hill_near=(30, 38, 66),
        ground=(96, 108, 134),
        ground_line=(62, 72, 96),
        speckle=(74, 86, 110),
        obstacle=(198, 210, 228),
        obstacle_dark=(26, 44, 46),
        dust=(124, 136, 162),
        cloud=(88, 90, 124),
        star=(226, 240, 255),
        moon=(232, 240, 255),
        text=(226, 234, 250),
    ),
    ground={"small": sprites.SNOWMAN, "large": sprites.PINE},
    # The same bird as the desert's, painted in this scene's obstacle colours.
    flyer=(sprites.FLYER_UP, sprites.FLYER_DOWN),
    layers=frozenset(LAYERS) - {"clouds"},
)

SCENES = (DESERT, SNOW)
DEFAULT = DESERT


def by_key(key: str) -> Scene:
    for scene in SCENES:
        if scene.key == key:
            return scene
    return DEFAULT


def palette_for_step(scene: Scene, step: int) -> Palette:
    return blend(scene.day, scene.night, step)


def text_tones(scene: Scene, step: int) -> tuple:
    """Return (ink, shadow) for text drawn over this scene's sky at this step.

    Keyed to how bright the sky actually is, not to whether it is night. Tying it
    to `is_night` left dark text on an already-dark sky for the steps in between:
    contrast bottomed out at 18 of 255, which is invisible. The shadow separates
    the glyphs from whatever else they overlap.
    """
    if luminance(palette_for_step(scene, step).sky) > 128.0:
        return scene.day.text, scene.night.text
    return scene.night.text, scene.day.text


_sheets: dict[tuple[str, int], sprites.WorldSheet] = {}


def sheet_for(scene: Scene, step: int) -> sprites.WorldSheet:
    """The cached art for a scene at a day/night step, built once."""
    key = (scene.key, step)
    if key not in _sheets:
        _sheets[key] = sprites.WorldSheet(
            palette_for_step(scene, step), scene.ground, scene.flyer
        )
    return _sheets[key]
