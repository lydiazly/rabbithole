"""Put page.css, and the page's own script, into the page pygbag built.

pygbag offers no hook for styling its template, and `--template` would mean
vendoring all 438 lines of it and re-vendoring on every pygbag upgrade. Injecting
a stylesheet instead depends on one thing only -- that the page has a </head> --
and leaves the loader's markup and scripts untouched.

Inlined rather than linked, so the build output stays the four files pygbag
produced plus nothing, and the page needs no extra request before it can paint.

usage: python web/restyle.py build/web/index.html web/page.css [web/page.js]
"""

import sys
from pathlib import Path

ANCHOR = "</head>"


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
    page.write_text(restyle(
        page.read_text(),
        stylesheet.read_text(),
        script.read_text() if script else "",
    ))
    print(f"styled {page} with {stylesheet}"
          + (f" and {script}" if script else ""))


if __name__ == "__main__":
    main()
