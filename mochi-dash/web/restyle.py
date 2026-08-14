"""Edit the page pygbag built: put this game's dressing in, take two things out.

pygbag offers no hook for either job, and `--template` would mean vendoring all
438 lines of its template and re-vendoring on every pygbag upgrade. Editing the
built page instead depends only on the shapes it is looking for still being
there, and every one of them raises if it is not: the failure worth avoiding is
doing nothing quietly and shipping pygbag's default anyway.

The stylesheet and script are inlined rather than linked, so the build output
stays the four files pygbag produced plus nothing, and the page needs no extra
request before it can paint.

usage: python web/restyle.py build/web/index.html web/page.css [web/page.js]
"""

import re
import sys
from pathlib import Path

ANCHOR = "</head>"

# The loader asks the CDN for two things this game has no use for. Measured on
# the built page, first load, cache empty: 88 KiB and four requests, one of which
# could never have succeeded.
#
# `vtx` is a terminal emulator -- xterm.js, its image addon and its stylesheet,
# 85 KiB over three cross-origin requests. This game draws to a canvas and has no
# way to reach a terminal. Dropped, the page still boots CPython, still fetches
# the game and still reaches the menu, which was checked by loading it rather
# than reasoned about.
#
# browserfs.min.js is not on the CDN at all -- not at the path the template asks
# for, not at that path without its doubled slash, not at the CDN root. Every
# load asks and every load is refused. A request that cannot succeed is not a
# fallback.
DATA_OS = re.compile(r'(data-os=")([^"]*)(")')
TERMINAL = "vtx"
BROWSERFS = re.compile(r'[ \t]*<script src="[^"]*browserfs[^"]*"></script>\n?')


def trim(html: str) -> str:
    """Return `html` with the terminal emulator and the dead request taken out."""
    found = DATA_OS.search(html)
    if not found:
        raise ValueError(
            "no data-os= in the built page, so there is no feature list to take "
            "the terminal out of -- pygbag's template has changed shape"
        )
    features = [f for f in found.group(2).split(",") if f.strip()]
    if TERMINAL not in features:
        raise ValueError(
            f"the loader no longer asks for {TERMINAL!r} ({found.group(2)!r}), so "
            "the 85 KiB this took out is already gone or has moved -- re-measure "
            "before trusting this"
        )
    kept = ",".join(f for f in features if f != TERMINAL)
    html = html[: found.start()] + f'data-os="{kept}"' + html[found.end():]

    if not BROWSERFS.search(html):
        raise ValueError(
            "no browserfs script tag in the built page -- pygbag has stopped "
            "asking for it, so this no longer has anything to remove"
        )
    return BROWSERFS.sub("", html, count=1)


def restyle(html: str, css: str, js: str = "") -> str:
    """Return `html` with `css`, and any `js`, inlined at the end of its head.

    Last, so these rules beat the template's own on equal specificity. The
    script goes in the same place and for the same reason as the stylesheet:
    pygbag offers no hook, and this depends on nothing but the page having a
    head to put things in.
    """
    if ANCHOR not in html:
        raise ValueError(
            f"no {ANCHOR} in the built page, so there is nowhere to put the "
            "stylesheet -- pygbag's template has changed shape"
        )
    injected = f"<style>\n{css.strip()}\n</style>\n"
    if js.strip():
        injected += f"<script>\n{js.strip()}\n</script>\n"
    return html.replace(ANCHOR, injected + ANCHOR, 1)


def main() -> None:
    if not 3 <= len(sys.argv) <= 4:
        raise SystemExit(
            f"usage: {Path(sys.argv[0]).name} <index.html> <page.css> [page.js]"
        )
    page, stylesheet = Path(sys.argv[1]), Path(sys.argv[2])
    script = Path(sys.argv[3]) if len(sys.argv) == 4 else None
    page.write_text(trim(restyle(
        page.read_text(),
        stylesheet.read_text(),
        script.read_text() if script else "",
    )))
    print(f"styled {page} with {stylesheet}"
          + (f" and {script}" if script else "")
          + ", and trimmed the terminal and the dead request out of its loader")


if __name__ == "__main__":
    main()
