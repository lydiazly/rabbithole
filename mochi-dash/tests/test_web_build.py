"""The web build's one requirement that nothing else checks.

pygbag reads main.py to decide which WebAssembly wheels to fetch, so the PEP 723
block there is the only place the web build learns that it needs pygame. Getting
it wrong is silent: the build succeeds, the page loads, and the game dies on the
first line that touches a pygame attribute -- an AttributeError in a module that
was never the problem. Nothing about that symptom points at a missing dependency
list, so the list is asserted here instead.

Parsed with regexes rather than tomllib, which arrived in 3.11 while this project
still claims 3.10.
"""

import importlib.util
import re
from pathlib import Path

import pytest

from mochi_dash import main as game
from mochi_dash import world as wd

ROOT = Path(__file__).resolve().parent.parent
WEB_ENTRY = ROOT / "main.py"
MANIFEST = ROOT / "pyproject.toml"
STYLESHEET = ROOT / "web" / "page.css"


def script(name: str):
    """Import one of the web/ build scripts, which are not part of the package."""
    path = ROOT / "web" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"web_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

DEPENDENCIES = re.compile(r"dependencies\s*=\s*\[(.*?)\]", re.DOTALL)
QUOTED = re.compile(r'"([^"]+)"')


def bare_name(requirement: str) -> str:
    """'pygame-ce>=2.5' -> 'pygame-ce'."""
    return re.split(r"[<>=!~;\[\s]", requirement, maxsplit=1)[0].strip().lower()


def dependencies_in(text: str) -> set[str]:
    body = DEPENDENCIES.search(text)
    assert body, "no `dependencies = [...]` array here"
    return {bare_name(dep) for dep in QUOTED.findall(body.group(1))}


def project_section(text: str) -> str:
    """[project] alone, so the dev group and build-system are out of scope."""
    start = text.index("[project]") + len("[project]")
    rest = text[start:]
    end = rest.index("\n[")
    return rest[:end]


def pep723_block(text: str) -> str:
    """The block's body, with the comment prefix taken off each line."""
    lines = text.splitlines()
    assert "# /// script" in lines, (
        f"{WEB_ENTRY.name} has no PEP 723 block, so a pygbag build of it would "
        "fetch no wheels and the game would die on `import pygame`"
    )
    start = lines.index("# /// script")
    end = next(
        i for i in range(start + 1, len(lines)) if lines[i].rstrip() == "# ///"
    )
    return "\n".join(
        line.removeprefix("#").removeprefix(" ") for line in lines[start + 1 : end]
    )


def test_the_web_entry_point_declares_every_runtime_dependency():
    """What the game needs installed and what the web build fetches must agree."""
    for_the_web = dependencies_in(pep723_block(WEB_ENTRY.read_text()))
    for_a_desktop = dependencies_in(project_section(MANIFEST.read_text()))
    assert for_the_web == for_a_desktop


def test_the_web_entry_point_needs_pygame():
    """A guard on the guard: the comparison above passes if both sides go empty."""
    assert "pygame-ce" in dependencies_in(pep723_block(WEB_ENTRY.read_text()))


# -- the page around the game -----------------------------------------------


def css_length(name: str) -> int:
    """The pixel value of a custom property in page.css."""
    found = re.search(rf"{name}:\s*(\d+)px", STYLESHEET.read_text())
    assert found, f"page.css declares no {name}"
    return int(found.group(1))


def test_the_canvas_is_capped_at_the_size_the_desktop_window_opens():
    """The web canvas must not outgrow the window the game was drawn for.

    pygbag's template stretches the canvas to the viewport, so page.css caps it.
    That cap is the desktop window's size written out again, which is the kind of
    duplicate that goes stale the moment anyone touches SCALE.
    """
    assert css_length("--game-width") == wd.WIDTH * game.SCALE
    assert css_length("--game-height") == wd.HEIGHT * game.SCALE


def test_restyling_puts_the_stylesheet_last_in_the_head():
    """Last, or the template's own rules win on equal specificity."""
    restyle = script("restyle").restyle
    out = restyle("<head><style>a{}</style></head><body></body>", "b{color:red}")
    assert out.index("b{color:red}") > out.index("a{}")
    assert out.index("b{color:red}") < out.index("</head>")


def test_restyling_a_page_it_does_not_recognise_is_an_error():
    """The failure to avoid is doing nothing quietly and shipping the default."""
    with pytest.raises(ValueError, match="nowhere to put the stylesheet"):
        script("restyle").restyle("<html><body>no head</body></html>", "b{}")


def test_the_page_script_is_injected_and_stays_optional():
    """The right mouse button ducks, so the browser's own context menu has to be
    refused -- and only the page can refuse it, which is the whole reason there
    is a script. Optional because the stylesheet came first and the two-argument
    call still has to work.
    """
    restyle = script("restyle").restyle
    page = "<head></head><body></body>"
    assert "<script>" not in restyle(page, "b{}")
    out = restyle(page, "b{}", "addEventListener('contextmenu', f)")
    assert out.index("<style>") < out.index("<script>") < out.index("</head>")


def test_the_page_script_refuses_the_context_menu():
    """Pinned by content: without this, every duck in a desktop browser opens a
    menu on top of the game.
    """
    source = (ROOT / "web" / "page.js").read_text()
    assert "contextmenu" in source and "preventDefault" in source


def test_the_favicon_is_a_square_of_momo():
    """Square because tabs are, and not blank -- a transparent icon is invisible."""
    icon = script("make_favicon").build()
    assert icon.get_size() == (64, 64)
    opaque = sum(
        icon.get_at((x, y)).a > 0
        for x in range(icon.get_width())
        for y in range(icon.get_height())
    )
    assert opaque > 64 * 64 // 4, "Momo covers almost none of the icon"
