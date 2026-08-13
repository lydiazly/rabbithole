"""Record the README's screenshots and animations from the game itself.

Same reason the favicon is drawn rather than stored (see mochi_dash/icon.py):
art that is hand-captured drifts the moment anything is recoloured or retimed,
and nobody notices, because a stale picture still looks like a picture. These
are produced by driving the real `Game` -- the same update and draw the player
runs -- so re-running this after a change produces media that matches it.

Everything here is deterministic: the RNG is seeded, and input is scripted per
frame rather than sampled from a clock. The same command twice gives the same
bytes.

usage: python tools/record.py ../media
"""

import os
import sys
from pathlib import Path

# Before pygame: these draw to a Surface and must never open a window.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from mochi_dash import characters, scenes, storage  # noqa: E402
from mochi_dash import main as m  # noqa: E402
from mochi_dash import world as wd  # noqa: E402

# The game runs at 60; a GIF frame delay is stored in hundredths of a second, so
# only divisors of 100 are honoured exactly. Every third frame is 20fps and a
# 5cs delay -- smooth enough for a pixel game, and a third of the frames to ship.
EVERY = 3
FPS = 60 // EVERY
DELAY_CS = 100 // FPS

# Half the desktop window. The art is integer-scaled either way, so this stays
# crisp; it is the width a README column actually gets, and a quarter of the
# pixels of the 3x window.
SCALE = 2


class Held(dict):
    """pygame's key state is a sequence over every scancode; this fakes it."""

    def __getitem__(self, key):
        return self.get(key, False)


class Recorder:
    """A Game with scripted input, collecting frames as it goes."""

    def __init__(self, seed=7):
        self.held = Held()
        pygame.key.get_pressed = lambda: self.held
        self.game = m.Game()
        self.game.rng.seed(seed)
        self.frames = []
        self.tick = 0

    def step(self, count=1, capture=True):
        for _ in range(count):
            self.game.update(m.DT)
            self.game.draw()
            if capture and self.tick % EVERY == 0:
                self.frames.append(self.grab())
            self.tick += 1

    def grab(self):
        canvas = self.game.canvas
        size = (canvas.get_width() * SCALE, canvas.get_height() * SCALE)
        big = pygame.transform.scale(canvas, size)
        return Image.frombytes("RGB", size, pygame.image.tobytes(big, "RGB"))

    def save(self, path: Path):
        """Write the frames as a looping GIF.

        Quantised against one palette taken from the first frame rather than a
        fresh one per frame: the scenes use a couple of dozen flat colours, so a
        shared palette is both exact and far smaller, and it stops the sky
        shimmering between frames as the encoder picks slightly different
        approximations of the same blue.
        """
        palette = self.frames[0].quantize(colors=256, method=Image.MEDIANCUT)
        frames = [f.quantize(palette=palette, dither=Image.Dither.NONE)
                  for f in self.frames]
        path.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            path, save_all=True, append_images=frames[1:],
            duration=DELAY_CS * 10, loop=0, optimize=True, disposal=2,
        )
        kb = path.stat().st_size / 1024
        print(f"  {path.name:24} {len(frames):3} frames  {kb:6.0f} KB")


def menu_cycle(row: int, options: int, out: Path, seed=7):
    """The select screen, stepping once through every option on one row."""
    rec = Recorder(seed)
    rec.game.go_to_menu()
    rec.game.row = row
    rec.step(24)  # rest on the first one long enough to be seen
    for _ in range(options):
        rec.game.menu_key(m.RIGHT_KEYS[0])
        rec.step(30)
    rec.save(out)


def a_run(out: Path, seed=3):
    """A run: clear a few obstacles, earn a dash, smash through the rest.

    The dash is granted rather than played for -- earning one takes twenty
    points, which is far longer than anybody watches a README. Everything after
    that is the real thing: the same boost, the same smashing, the same handover
    at the end.
    """
    rec = Recorder(seed)
    rec.game.start_run()
    # Near the top of the ramp, which is where the game is worth showing: the
    # opening is deliberately empty while a newcomer finds the jump, and an
    # empty desert is a poor advertisement for an obstacle course.
    rec.game.world.speed = wd.SPEED_MAX - 20.0
    rec.game.score, rec.game.highscore = 138, 431
    hold = 0

    def frame():
        nonlocal hold
        rec.held.clear()
        if hold > 0:
            rec.held[m.JUMP_KEYS[0]] = True
            hold -= 1
        left, _, width, _ = rec.game.player.hitbox()
        front = left + width
        ahead = [o for o in rec.game.world.obstacles
                 if not o.launched and o.x + o.w > front]
        if ahead and not rec.game.dashing:
            ob = min(ahead, key=lambda o: o.x)
            eta = (ob.x - front) / max(1.0, rec.game.world.scroll)
            ducks = ob.y + ob.h < wd.GROUND_Y - 1
            if ducks:
                if eta < 0.4:
                    rec.held[m.DUCK_KEYS[0]] = True
            elif eta < 0.42 and rec.game.player.on_ground and hold == 0:
                rec.game.jump_buffer = m.JUMP_BUFFER
                hold = 18  # held, or the jump is only the smallest hop
        rec.step(1)

    for _ in range(110):          # a few obstacles cleared on foot
        frame()
    rec.game.toward_dash = rec.game.dash_target
    rec.game.dash_cooldown = 0.0
    while not rec.game.dashing:   # granted on the next update
        frame()
    while rec.game.dashing:       # the whole dash, smashing as it goes
        frame()
    for _ in range(190):          # the countdown, and the next obstacle arriving
        frame()
    rec.save(out)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <out-dir>")
    out = Path(sys.argv[1])
    storage.FILE = out / ".unused-highscore"  # never read, never written to $HOME

    pygame.init()
    try:
        print("recording:")
        menu_cycle(m.CHARACTER_ROW, len(characters.CHARACTERS),
                   out / "menu-characters.gif")
        menu_cycle(m.SCENE_ROW, len(scenes.SCENES), out / "menu-scenes.gif")
        a_run(out / "dash.gif")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
