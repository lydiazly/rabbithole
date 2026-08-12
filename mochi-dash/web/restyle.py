"""Put page.css into the page pygbag built.

pygbag offers no hook for styling its template, and `--template` would mean
vendoring all 438 lines of it and re-vendoring on every pygbag upgrade. Injecting
a stylesheet instead depends on one thing only -- that the page has a </head> --
and leaves the loader's markup and scripts untouched.

Inlined rather than linked, so the build output stays the four files pygbag
produced plus nothing, and the page needs no extra request before it can paint.

usage: python web/restyle.py build/web/index.html web/page.css
"""

import sys
from pathlib import Path

ANCHOR = "</head>"


def restyle(html: str, css: str) -> str:
    """Return `html` with `css` inlined as the last thing in its head.

    Last, so these rules beat the template's own on equal specificity.
    """
    if ANCHOR not in html:
        raise ValueError(
            f"no {ANCHOR} in the built page, so there is nowhere to put the "
            "stylesheet -- pygbag's template has changed shape"
        )
    style = f"<style>\n{css.strip()}\n</style>\n"
    return html.replace(ANCHOR, style + ANCHOR, 1)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <index.html> <page.css>")
    page, stylesheet = Path(sys.argv[1]), Path(sys.argv[2])
    page.write_text(restyle(page.read_text(), stylesheet.read_text()))
    print(f"styled {page} with {stylesheet}")


if __name__ == "__main__":
    main()
