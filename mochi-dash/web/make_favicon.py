"""Draw the browser tab icon from the game's own art.

Momo is a few rows of characters in sprites.py, built into a Surface by the same
code the game draws with, so the icon cannot drift from the character: recolour
Momo and the tab follows. That is the same reason there are no image files in
this project -- see the note at the top of sfx.py about the sound.

usage: python web/make_favicon.py build/favicon.png
"""

import os
import sys
from pathlib import Path

# Before pygame is imported: this draws to a Surface and never opens a window,
# and asking for a real one fails on a build machine.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from mochi_dash import characters  # noqa: E402

# 64 square because tab icons are square and Momo is not: the pose is 14x12, so
# it is scaled by a whole number and centred, leaving a little air. A fractional
# scale would blur the one thing a pixel character cannot afford to lose.
SIZE = 64
SCALE = 4
POSE = "round"  # the resting shape, the one that reads as Momo at any size
DAY = 0  # the daylight end of the palette ramp


def build() -> pygame.Surface:
    sheet = characters.sheet_for(characters.DEFAULT, DAY)
    momo = sheet.poses[POSE]
    scaled = pygame.transform.scale_by(momo, SCALE)

    icon = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    icon.blit(
        scaled,
        (
            (SIZE - scaled.get_width()) // 2,
            (SIZE - scaled.get_height()) // 2,
        ),
    )
    return icon


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <out.png>")
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)

    pygame.init()
    try:
        pygame.image.save(build(), out)
    finally:
        pygame.quit()
    print(f"wrote {out} ({SIZE}x{SIZE})")


if __name__ == "__main__":
    main()
