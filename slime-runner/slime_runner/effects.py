"""Landing dust: a three-frame puff sprite, played once where the slime hit.

The physics-particle version this replaces looked wrong once everything else was
on a pixel grid — a cloud of independently falling dots reads as smoke, not as a
sprite. A short authored animation is both cheaper and more in keeping.
"""

from .sprites import PUFF

PUFF_TICKS = 4  # per frame
HARD_OFFSET = 2  # a hard landing throws the puff a little wider


class Puffs:
    def __init__(self):
        self.items: list[list] = []

    def clear(self) -> None:
        self.items.clear()

    def burst(self, x: float, y: float, hard: bool) -> None:
        spread = HARD_OFFSET if hard else 0
        self.items.append([x - spread, y, 0, 0])
        if hard:
            # Frame -1 draws nothing, so this one starts a beat behind the first.
            self.items.append([x + spread, y, -1, 0])

    def update(self, dt: float, scroll: float) -> None:
        alive = []
        for item in self.items:
            item[0] -= scroll * dt  # the puff sits on the ground, so it scrolls
            item[3] += 1
            if item[3] >= PUFF_TICKS:
                item[3] = 0
                item[2] += 1
            if item[2] < len(PUFF) and item[0] > -12:
                alive.append(item)
        self.items = alive

    def draw(self, canvas, sheet) -> None:
        for x, y, frame, _ in self.items:
            if frame < 0:
                continue
            surf = sheet.puff[frame]
            canvas.blit(surf, (round(x - surf.get_width() / 2),
                               round(y - surf.get_height())))
