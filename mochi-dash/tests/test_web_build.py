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

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_ENTRY = ROOT / "main.py"
MANIFEST = ROOT / "pyproject.toml"

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
