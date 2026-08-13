"""Write the browser tab icon to a PNG for the built page.

The picture itself is mochi_dash.icon, which the desktop window also uses -- see
the note there. This file is only the part the page build needs and the game does
not: a file on disk.

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

from mochi_dash.icon import SIZE, build  # noqa: E402


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
