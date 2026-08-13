"""A 5x5 uppercase pixel font, drawn straight onto the low-resolution canvas.

Rendering text with a real font and then scaling it up would leave the only
smooth, oddly-sized thing on an otherwise chunky screen, so the HUD gets glyphs
authored at the same resolution as everything else.

Five columns rather than three: at three, M, N, V and W have no room for a
diagonal and collapse into an H with a bar at varying heights — "RUNNER" comes
out as "RUHHER". The extra two columns are what make those strokes possible.
"""

import pygame

GLYPH_W = 5
GLYPH_H = 5
ADVANCE = GLYPH_W + 1

_GLYPHS = {
    "A": (".###.", "#...#", "#####", "#...#", "#...#"),
    "B": ("####.", "#...#", "####.", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "####.", "#....", "#####"),
    "F": ("#####", "#....", "####.", "#....", "#...."),
    "G": (".####", "#....", "#..##", "#...#", ".####"),
    "H": ("#...#", "#...#", "#####", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "#####"),
    "J": ("....#", "....#", "....#", "#...#", ".###."),
    "K": ("#...#", "#..#.", "###..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "####.", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "####.", "#..#.", "#...#"),
    "S": (".####", "#....", ".###.", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", ".#.#.", "..#..", ".#.#.", "#...#"),
    "Y": ("#...#", ".#.#.", "..#..", "..#..", "..#.."),
    "Z": ("#####", "...#.", "..#..", ".#...", "#####"),
    # The slash through the zero is what keeps a score legible next to an O.
    "0": (".###.", "#..##", "#.#.#", "##..#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "...#.", "..#..", "#####"),
    "3": ("####.", "....#", ".###.", "....#", "####."),
    "4": ("#..#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "####."),
    "6": (".###.", "#....", "####.", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#.."),
    "8": (".###.", "#...#", ".###.", "#...#", ".###."),
    "9": (".###.", "#...#", ".####", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", "..#.."),
    ":": (".....", "..#..", ".....", "..#..", "....."),
    "-": (".....", ".....", ".###.", ".....", "....."),
    "/": ("....#", "...#.", "..#..", ".#...", "#...."),
    "!": ("..#..", "..#..", "..#..", ".....", "..#.."),
    "<": ("...#.", "..#..", ".#...", "..#..", "...#."),
    ">": (".#...", "..#..", "...#.", "..#..", ".#..."),
    # Not a letter: the dash meter's lightning bolt. It lives in the font because
    # the font already owns the per-colour, per-scale glyph cache and the shadow
    # pass, and a five-by-five sprite needing its own copy of all that would be a
    # second implementation of the same thing.
    #
    # Down-left, a kink jutting left, then down-left again. Chosen over five
    # other five-pixel bolts by drawing them: the ones that keep a full-width
    # middle row read as a blocky arrow, and the ones that taper to single
    # pixels vanish at this size.
    "*": ("..##.", ".##..", "####.", "..##.", ".##.."),
}

_UNKNOWN = ("#####", "#####", "#####", "#####", "#####")


def text_width(text: str, scale: int = 1) -> int:
    """Width in canvas pixels, without the trailing inter-glyph gap."""
    return max(0, (len(text) * ADVANCE - 1) * scale)


# Glyphs are rendered pixel by pixel in Python, which is fine once and far too
# slow every frame: with a drop shadow doubling every string, drawing the HUD
# this way cost more than drawing the entire rest of the game. Cached per glyph
# rather than per string, so the set stays bounded no matter what the score
# reads -- a few dozen glyphs times the two text tones and two scales.
_cache: dict[tuple[str, tuple, int], pygame.Surface] = {}


def _glyph(char: str, color, scale: int) -> pygame.Surface:
    key = (char, color, scale)
    surface = _cache.get(key)
    if surface is None:
        surface = pygame.Surface((GLYPH_W * scale, GLYPH_H * scale), pygame.SRCALPHA)
        for row, bits in enumerate(_GLYPHS.get(char, _UNKNOWN)):
            for col, bit in enumerate(bits):
                if bit == "#":
                    surface.fill(color, (col * scale, row * scale, scale, scale))
        _cache[key] = surface
    return surface


def draw(surface, text: str, x: int, y: int, color, scale: int = 1) -> None:
    """Draw uppercase text with its top-left corner at (x, y).

    `scale` blows each glyph pixel up into a square block, which keeps headings
    on the same grid as the rest of the art instead of introducing a second,
    finer resolution.
    """
    color = tuple(color)
    for i, char in enumerate(text.upper()):
        surface.blit(_glyph(char, color, scale), (x + i * ADVANCE * scale, y))
