"""Momo as an application icon, for the window and for the browser tab.

Built from the game's own art rather than an image file, by the same code the
game draws with, so the icon cannot drift from the character: recolour Momo and
both the taskbar and the tab follow. That is the same reason there are no image
assets in this project -- see the note at the top of sfx.py about the sound.

In the package rather than beside the build script that first needed it, because
two callers want the same picture and neither should own it: `web/make_favicon`
writes it to a PNG for the page, and the desktop window hands it to SDL.
"""

import pygame

from . import characters

# Square because icons are and Momo is not: the pose is 14x12, so it is scaled by
# a whole number and centred, leaving a little air. A fractional scale would blur
# the one thing a pixel character cannot afford to lose.
SIZE = 64
SCALE = 4
POSE = "round"  # the resting shape, the one that reads as Momo at any size
DAY = 0  # the daylight end of the palette ramp


def build() -> pygame.Surface:
    """Momo, centred on a transparent square."""
    sheet = characters.sheet_for(characters.DEFAULT, DAY)
    scaled = pygame.transform.scale_by(sheet.poses[POSE], SCALE)

    icon = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    icon.blit(
        scaled,
        (
            (SIZE - scaled.get_width()) // 2,
            (SIZE - scaled.get_height()) // 2,
        ),
    )
    return icon
