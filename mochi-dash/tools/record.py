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

# A hard ceiling on a clip, enforced where frames are appended rather than
# trusted to the caller. This is not tidiness: an earlier version waited on a
# condition with an unbounded loop, the scripted player died so the condition
# never came true, and the recorder grew to 22GB and was OOM-killed -- taking
# the terminal it was started from with it. Twenty seconds is already far longer
# than a README clip; anything past it is a bug, and it should say so while it
# still fits in memory.
MAX_FRAMES = 400

# The shape of the run clip, in game ticks at 60/s.
ON_FOOT = 330     # 5.5s of ordinary play, which is what the clip is mostly for
AFTER_DASH = 30   # half a second past the boost dropping, then cut


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
        self.frame = lambda: self.step(1)  # a clip with input replaces this

    def step(self, count=1, capture=True):
        for _ in range(count):
            self.game.update(m.DT)
            self.game.draw()
            if capture and self.tick % EVERY == 0:
                if len(self.frames) >= MAX_FRAMES:
                    raise RuntimeError(
                        f"clip ran past {MAX_FRAMES} frames "
                        f"({MAX_FRAMES / FPS:.0f}s) -- something is not ending"
                    )
                self.frames.append(self.grab())
            self.tick += 1

    def until(self, ready, limit: int, what: str):
        """Step until `ready()`, or fail saying what never happened.

        Every wait in here is bounded. The condition being waited on depends on
        a scripted player staying alive, and a player that dies satisfies
        nothing, ever.
        """
        for _ in range(limit):
            if ready():
                return
            self.frame()
        raise RuntimeError(f"waited {limit / 60:.0f}s and {what}")

    def alive(self) -> bool:
        return self.game.state == m.PLAYING

    def grab(self):
        canvas = self.game.canvas
        size = (canvas.get_width() * SCALE, canvas.get_height() * SCALE)
        big = pygame.transform.scale(canvas, size)
        return Image.frombytes("RGB", size, pygame.image.tobytes(big, "RGB"))

    def save(self, path: Path):
        """Write the frames as a looping GIF.

        One palette for the whole clip, built from the colours every frame
        actually uses. Two things this must not be: a fresh palette per frame,
        which makes the sky shimmer as the encoder re-approximates the same blue;
        and -- the mistake this replaces -- a palette taken from the *first*
        frame, which held 14 of the 29 colours the menu goes on to draw, so every
        character after the first was rendered in the nearest wrong colour.

        These scenes are flat pixel art, a few dozen colours in total, so the
        union fits inside a GIF's 256 and the result is exact rather than
        approximate. The fallback matters only if that ever stops being true.
        """
        used = sorted({c for f in self.frames for c in f.get_flattened_data()})
        if len(used) <= 256:
            palette = Image.new("P", (1, 1))
            flat = [channel for colour in used for channel in colour]
            palette.putpalette(flat + [0] * (768 - len(flat)))
        else:
            print(f"  note: {len(used)} colours, more than a GIF can hold exactly")
            tall = Image.new("RGB", (len(used), 1))
            tall.putdata(used)
            palette = tall.quantize(colors=256, method=Image.MEDIANCUT)
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


def a_run(out: Path, seed=2):
    """A run: obstacles cleared on foot, then a dash smashing through them.

    Recorded at two thirds of the speed ramp, which is where the scripted player
    can actually survive -- at the top it dies on every seed tried, and a clip
    that ends in a death is not the advertisement. It costs nothing in density:
    spawn gaps are specified in seconds, so the traffic here is within a tenth
    of a second of the traffic at top speed.

    The dash is granted rather than played for, since earning one takes twenty
    points and far longer than anybody watches a README. Everything after that
    is the real thing -- the same boost, the same smashing.
    """
    rec = Recorder(seed)
    rec.game.start_run()
    rec.game.world.speed = 150.0
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
            if ob.y + ob.h < wd.GROUND_Y - 1:
                if eta < 0.4:
                    rec.held[m.DUCK_KEYS[0]] = True
            elif eta < 0.46 and rec.game.player.on_ground and hold == 0:
                rec.game.jump_buffer = m.JUMP_BUFFER
                hold = 18  # held, or the jump is only the smallest hop
        rec.step(1)

    rec.frame = frame

    # On foot first, and long enough to read as the ordinary game: several
    # things jumped and ducked before anything special happens.
    for _ in range(ON_FOOT):
        frame()
        if not rec.alive():
            raise RuntimeError(
                f"the scripted player died {rec.tick} ticks in -- pick another "
                f"seed or a slower speed, do not record a clip that ends badly"
            )

    rec.game.toward_dash = rec.game.dash_target
    rec.game.dash_cooldown = 0.0
    rec.until(lambda: rec.game.dashing, 120, "the dash never started")

    smashed, seen = 0, {id(o) for o in rec.game.world.obstacles if o.launched}
    def count():
        nonlocal smashed
        for ob in rec.game.world.obstacles:
            if ob.launched and id(ob) not in seen:
                seen.add(id(ob))
                smashed += 1

    rec.until(lambda: (count(), not rec.game.dashing)[1], 700, "the dash never ended")

    # Cut here rather than playing out the handover. Its three seconds of empty
    # screen counting down are the right design in the game and dead air in a
    # loop -- and the loop point is better on the dash than on nothing.
    rec.step(AFTER_DASH)

    if smashed < 4:
        raise RuntimeError(
            f"only {smashed} obstacles smashed on camera -- the dash is the "
            f"point of this clip, so a retune that empties it should fail here"
        )
    print(f"  ({smashed} obstacles smashed on camera)")
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
