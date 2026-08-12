"""Where the high score lives, on a desktop and in a browser.

pygbag runs this same code under emscripten, where the filesystem is a throwaway
unpack of the app archive: a file written there is gone on the next load. The
browser keeps localStorage instead, so the backend is decided once, here, and the
rest of the game just asks for a number.

A missing or unreadable score means zero, which is what it meant when this was
two functions reading a file. Writing is deliberately left uncaught: a save that
fails is a bug worth seeing, not a score worth losing quietly.
"""

import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / ".highscore"

# Namespaced because localStorage is shared with everything else served from the
# same origin, and the games may well end up neighbours on one static site.
KEY = "mochi-dash.highscore"

# `sys.platform` is the check pygbag documents. Note that under emscripten
# `platform` is pygbag's own module rather than the standard library's, which is
# why that import sits inside the branches instead of at the top of the file.
BROWSER = sys.platform == "emscripten"


def load() -> int:
    """The stored high score, or zero if there isn't a usable one."""
    if BROWSER:
        from platform import window

        raw = window.localStorage.getItem(KEY)
        if raw is None:
            return 0  # nothing stored yet
    else:
        try:
            raw = FILE.read_text()
        except FileNotFoundError:
            return 0
    try:
        return int(raw.strip())
    except ValueError:
        return 0  # written by something else, or truncated


def save(score: int) -> None:
    if BROWSER:
        from platform import window

        window.localStorage.setItem(KEY, str(score))
    else:
        FILE.write_text(f"{score}\n")
