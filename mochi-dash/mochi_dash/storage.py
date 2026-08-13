"""Where the high score lives, on each desktop and in a browser.

It used to be a dotfile beside the package, which works exactly as long as the
game is run from a checkout. Installed properly -- `uv tool install`, a wheel in
site-packages, anything under Program Files -- that directory is not the user's
to write to, so the first run that beat the stored best would raise instead of
saving it. It is also shared: two accounts on one machine would overwrite each
other's score.

So the file goes where each platform keeps per-user application data:

    Windows   %APPDATA%\\Mochi Dash                 (roaming, so it follows a
                                                     domain profile between
                                                     machines, which is what a
                                                     high score should do)
    macOS     ~/Library/Application Support/Mochi Dash
    Linux     $XDG_DATA_HOME/mochi-dash, else ~/.local/share/mochi-dash

The names differ per platform on purpose: XDG directories are lowercase and
hyphenated by convention, and the other two are shown to users in a file
browser, where "mochi-dash" would look like a stray folder.

pygbag runs this same code under emscripten, where the filesystem is a throwaway
unpack of the app archive: a file written there is gone on the next load. The
browser keeps localStorage instead, so the backend is decided once, here, and
the rest of the game just asks for a number.

A missing or unreadable score means zero, which is what it meant when this was
two functions reading a file. Writing is deliberately left uncaught: a save that
fails is a bug worth seeing, not a score worth losing quietly.
"""

import os
import sys
from pathlib import Path

# Namespaced because localStorage is shared with everything else served from the
# same origin, and the games may well end up neighbours on one static site.
KEY = "mochi-dash.highscore"

# `sys.platform` is the check pygbag documents. Note that under emscripten
# `platform` is pygbag's own module rather than the standard library's, which is
# why that import sits inside the branches instead of at the top of the file.
BROWSER = sys.platform == "emscripten"


def data_dir() -> Path:
    """The per-user directory this platform keeps application data in."""
    if sys.platform == "win32":
        # APPDATA is set for any interactive session; the fallback covers a
        # service or a stripped environment rather than a normal login.
        roaming = os.environ.get("APPDATA")
        base = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
        return base / "Mochi Dash"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Mochi Dash"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "mochi-dash"


FILE = data_dir() / "highscore"

# Where it used to live. Read once if nothing is stored in the new place yet, so
# an existing player keeps their best instead of being silently reset by an
# upgrade. Never written to again.
LEGACY_FILE = Path(__file__).resolve().parent.parent / ".highscore"


def _parse(raw: str | None) -> int:
    """A stored score, or zero if it is not one.

    The file sits in the user's own directory, so anything may have touched it:
    a truncated write, an editor, another program with the same idea. None of
    that is worth taking the game down for, and none of it should be believed.
    """
    if raw is None:
        return 0
    try:
        return int(raw.strip())
    except ValueError:
        return 0


def load() -> int:
    """The stored high score, or zero if there isn't a usable one."""
    if BROWSER:
        from platform import window

        return _parse(window.localStorage.getItem(KEY))
    try:
        return _parse(FILE.read_text())
    except OSError:
        pass
    try:
        return _parse(LEGACY_FILE.read_text())
    except OSError:
        return 0


def save(score: int) -> None:
    if BROWSER:
        from platform import window

        window.localStorage.setItem(KEY, str(score))
        return
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(f"{score}\n")
