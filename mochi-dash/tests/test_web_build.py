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

from mochi_dash import icon as game_icon
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


# Every shape trim() looks for, in the order pygbag's own template has them.
BUILT_LOADER = (
    '<html lang="en-us"><script src="cdn/pythons.js" data-os="vtx,snd,gui"></script>\n'
    '        msg  = "Ready to start ! Please click/touch page"\n'
    '    <script src="https://pygame-web.github.io/cdn/0.9.3//browserfs.min.js"></script>\n'
    "<head></head><body></body></html>"
)


def test_the_terminal_emulator_is_taken_out_of_the_loader():
    """The game draws to a canvas and never writes to a terminal.

    pygbag's template asks for the `vtx` feature, which pulls xterm.js, its image
    addon and its stylesheet from the CDN: 85 KiB over three cross-origin
    requests, on every first load, for a screen this game has no way to reach.
    """
    out = script("restyle").trim(BUILT_LOADER)
    assert 'data-os="snd,gui"' in out
    assert "vtx" not in out


def test_the_request_that_always_fails_is_taken_out_too():
    """browserfs.min.js is not on the CDN, at that path or any other.

    Measured: every load asks for it and every load is refused. A request that
    cannot succeed is not a fallback, it is just a request.
    """
    out = script("restyle").trim(BUILT_LOADER)
    assert "browserfs" not in out
    # And the tag it sat on is gone with it, rather than left as a blank line
    # inside the loader's markup.
    assert "<script src=\"cdn/pythons.js\"" in out.replace(
        ' data-os="snd,gui"', "")


def test_the_wait_for_a_gesture_says_it_in_four_words():
    """pygbag's own wording is nine, with a space before its exclamation mark.

    Most players never see this line at all, because page.js remembers a tap made
    while the runtime loads and replays it. What is left is somebody sitting there
    waiting to be told what to do, and the shorter sentence tells them.
    """
    restyle = script("restyle")
    out = restyle.trim(BUILT_LOADER)
    assert restyle.START_SAYS in out
    assert "Ready to start" not in out
    assert " !" not in out, "the space before the exclamation mark survived"
    assert len(restyle.START_SAYS.split()) <= 5, restyle.START_SAYS


def test_a_tap_made_while_it_loads_is_not_thrown_away():
    """The gate is armed after several megabytes have arrived, so a tap made
    during the wait lands on nothing and the player is asked for a second one.

    A gesture is a fact about the page, not about the moment, so the first one is
    remembered and replayed once there is something listening.
    """
    source = (ROOT / "web" / "page.js").read_text()
    assert "gestured" in source, "nothing remembers an early gesture"
    assert "setInterval" in source, "nothing retries once the gate is armed"
    assert "clearInterval" in source, "the retry never stops"


@pytest.mark.parametrize("page,missing", [
    ('<html><script src="x/browserfs.min.js"></script>msg = "Ready to start !"'
     "</html>", "data-os"),
    ('<html><script data-os="vtx,snd,gui"></script>msg = "Ready to start !"'
     "</html>", "browserfs"),
    ('<html><script data-os="snd,gui"></script>'
     '<script src="x/browserfs.min.js"></script>msg = "Ready to start !"</html>',
     "vtx"),
    ('<html><script data-os="vtx,snd,gui"></script>'
     '<script src="x/browserfs.min.js"></script></html>', "start prompt"),
])
def test_trimming_a_loader_it_does_not_recognise_is_an_error(page, missing):
    """Same reason the stylesheet raises: the failure to avoid is doing nothing
    quietly and shipping pygbag's default anyway.

    pygbag is pinned in the workflow, so any of these going missing means the
    template changed under a version bump and the saving needs re-measuring
    rather than assuming.
    """
    with pytest.raises(ValueError, match=missing):
        script("restyle").trim(page)


def test_the_page_script_refuses_the_context_menu():
    """Pinned by content: without this, every duck in a desktop browser opens a
    menu on top of the game.
    """
    source = (ROOT / "web" / "page.js").read_text()
    assert "contextmenu" in source and "preventDefault" in source


def test_a_tap_is_passed_on_as_the_click_the_start_gate_waits_for():
    """pygbag holds the game until a gesture is recorded, and on Safari -- which
    is what it calls any iPhone -- it waits for a `click` on `window` and nothing
    else. iOS only synthesises that click when WebKit thinks the thing under the
    finger is clickable, and a canvas and a message box are not, so the gesture
    happened and the gate never heard it.

    Both halves are pinned because either alone would look like it worked on a
    desktop, where the click arrives regardless.
    """
    source = (ROOT / "web" / "page.js").read_text()
    assert "touchend" in source, "nothing listens for the tap"
    assert 'MouseEvent("click")' in source, "the tap is not passed on as a click"
    assert "removeEventListener" in source, (
        "the listener never comes off, so it keeps firing into the running game"
    )

    style = STYLESHEET.read_text()
    assert "pointer: coarse" in style and "cursor: pointer" in style, (
        "the CSS half of the workaround is gone; page.js is then the only thing "
        "standing between an iPhone and a page that never starts"
    )


def test_the_favicon_is_a_square_of_momo():
    """Square because tabs are, and not blank -- a transparent icon is invisible."""
    icon = game_icon.build()
    assert icon.get_size() == (game_icon.SIZE, game_icon.SIZE)
    opaque = sum(
        icon.get_at((x, y)).a > 0
        for x in range(icon.get_width())
        for y in range(icon.get_height())
    )
    assert opaque > game_icon.SIZE**2 // 4, "Momo covers almost none of the icon"


def test_the_window_wears_the_same_icon_as_the_tab(monkeypatch):
    """The taskbar and the browser tab are one picture, built once.

    Set before `set_mode`, which is when SDL takes the icon the window will
    wear: afterwards it is a change to an existing window, which some window
    managers apply and some ignore. Ordering is the whole of this test, because
    getting it wrong looks exactly like getting it right on the machine that
    happened to work.
    """
    import pygame

    pygame.init()
    calls = []
    real_icon, real_mode = pygame.display.set_icon, pygame.display.set_mode
    monkeypatch.setattr(pygame.display, "set_icon",
                        lambda surf: calls.append(("icon", surf)))
    monkeypatch.setattr(pygame.display, "set_mode",
                        lambda *a, **k: (calls.append(("mode", None))
                                         or real_mode(*a, **k)))
    monkeypatch.setattr(game.storage, "BROWSER", False)
    game.Game()

    order = [what for what, _ in calls]
    assert order[:2] == ["icon", "mode"], order
    assert calls[0][1].get_size() == (game_icon.SIZE, game_icon.SIZE)

    # And not in a browser, where the tab's icon comes from the page and the
    # window this would dress does not exist.
    calls.clear()
    monkeypatch.setattr(game.storage, "BROWSER", True)
    game.Game()
    assert [what for what, _ in calls] == ["mode"]
    pygame.display.set_icon = real_icon
