"""A 5x5 uppercase pixel font, drawn straight onto the low-resolution canvas.

Rendering text with a real font and then scaling it up would leave the only
smooth, oddly-sized thing on an otherwise chunky screen, so the HUD gets glyphs
authored at the same resolution as everything else.

Five columns rather than three: at three, M, N, V and W have no room for a
diagonal and collapse into an H with a bar at varying heights — "RUNNER" comes
out as "RUHHER". The extra two columns are what make those strokes possible.
"""

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
}

_UNKNOWN = ("#####", "#####", "#####", "#####", "#####")


def text_width(text: str, scale: int = 1) -> int:
    """Width in canvas pixels, without the trailing inter-glyph gap."""
    return max(0, (len(text) * ADVANCE - 1) * scale)


def draw(surface, text: str, x: int, y: int, color, scale: int = 1) -> None:
    """Draw uppercase text with its top-left corner at (x, y).

    `scale` blows each glyph pixel up into a square block, which keeps headings
    on the same grid as the rest of the art instead of introducing a second,
    finer resolution.
    """
    for i, char in enumerate(text.upper()):
        glyph = _GLYPHS.get(char, _UNKNOWN)
        gx = x + i * ADVANCE * scale
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit != "#":
                    continue
                if scale == 1:
                    surface.set_at((gx + col, y + row), color)
                else:
                    surface.fill(
                        color, (gx + col * scale, y + row * scale, scale, scale)
                    )


def draw_centered(surface, text: str, canvas_w: int, y: int, color,
                  scale: int = 1) -> None:
    draw(surface, text, (canvas_w - text_width(text, scale)) // 2, y, color, scale)
