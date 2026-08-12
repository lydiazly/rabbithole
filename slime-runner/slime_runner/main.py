"""Window, low-resolution canvas, fixed-timestep loop, and the game states.

Everything is drawn onto a small canvas and blown up to the window with a
nearest-neighbour integer scale at the very end, so every pixel on screen is a
whole number of canvas pixels and nothing is ever half-drawn between them.
"""

import random
import sys
from pathlib import Path

import pygame

from . import effects, pixelfont, sprites, world
from .palette import DAY, NIGHT, is_night, palette_for_step, step_at
from .slime import HARD_LANDING, Slime

SCALE = 3
DT = 1.0 / 60.0
MAX_FRAME = 0.25  # never simulate more than this per frame, however slow it got

START_X = 42.0
X_MIN = 22.0
X_MAX = 110.0

JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
DUCK_KEYS = (pygame.K_DOWN, pygame.K_s)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
QUIT_KEYS = (pygame.K_ESCAPE, pygame.K_q)
RESTART_KEYS = (pygame.K_r,)

JUMP_BUFFER = 0.12  # a press just before landing still counts

HIGHSCORE_PATH = Path(__file__).resolve().parent.parent / ".highscore"

TITLE = "title"
PLAYING = "playing"
GAME_OVER = "over"


def load_highscore() -> int:
    """Read the stored high score. A missing or corrupt file just means zero."""
    try:
        return int(HIGHSCORE_PATH.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def save_highscore(score: int) -> None:
    HIGHSCORE_PATH.write_text(f"{score}\n")


class Game:
    def __init__(self):
        self.rng = random.Random()
        self.screen = pygame.display.set_mode(
            (world.WIDTH * SCALE, world.HEIGHT * SCALE)
        )
        pygame.display.set_caption("Slime Runner")
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((world.WIDTH, world.HEIGHT))

        self.world = world.World(self.rng)
        self.slime = Slime(START_X, world.GROUND_Y)
        self.puffs = effects.Puffs()

        self.highscore = load_highscore()
        self.state = TITLE
        self.jump_buffer = 0.0

    def start_run(self) -> None:
        self.world.reset()
        self.slime.reset()
        self.puffs.clear()
        self.jump_buffer = 0.0
        self.state = PLAYING

    def end_run(self) -> None:
        self.state = GAME_OVER
        self.slime.splat()
        self.puffs.burst(self.slime.x, world.GROUND_Y, True)
        score = int(self.world.score)
        if score > self.highscore:
            self.highscore = score
            save_highscore(score)

    # -- loop -------------------------------------------------------------

    def run(self) -> None:
        accumulator = 0.0
        while True:
            if not self.handle_events():
                return
            accumulator += min(self.clock.tick(60) / 1000.0, MAX_FRAME)
            while accumulator >= DT:
                self.update(DT)
                accumulator -= DT
            self.draw()

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in QUIT_KEYS:
                return False
            if event.key in JUMP_KEYS:
                if self.state == TITLE:
                    self.start_run()
                else:
                    self.jump_buffer = JUMP_BUFFER
            elif event.key in RESTART_KEYS and self.state == GAME_OVER:
                self.start_run()
        return True

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        holding_jump = any(keys[k] for k in JUMP_KEYS)
        ducking = any(keys[k] for k in DUCK_KEYS)
        lateral = any(keys[k] for k in RIGHT_KEYS) - any(keys[k] for k in LEFT_KEYS)

        if self.state != PLAYING:
            # The slime keeps animating on the title and game-over screens: the
            # idle breathe loop and the tail of the splat clip both still run.
            self.slime.update(dt, False, False, 0, X_MIN, X_MAX)
            self.puffs.update(dt, 0.0)
            return

        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.jump_buffer > 0.0 and self.slime.on_ground:
            self.jump_buffer = 0.0
            self.slime.jump()

        self.world.update(dt)
        impact = self.slime.update(dt, holding_jump, ducking, lateral, X_MIN, X_MAX)
        if impact:
            self.puffs.burst(self.slime.x, world.GROUND_Y, impact >= HARD_LANDING)
        self.puffs.update(dt, self.world.speed)

        if self.world.collides(self.slime.hitbox()):
            self.end_run()

    # -- drawing ----------------------------------------------------------

    def draw(self) -> None:
        step = step_at(self.world.phase)
        palette = palette_for_step(step)
        sheet = sprites.sheet_for_step(step, palette)

        self.world.draw(self.canvas, palette, step, sheet)
        self.puffs.draw(self.canvas, sheet)
        self.canvas.blit(sheet.slime[self.slime.frame], self.slime.blit_pos())
        self.draw_hud(step)

        pygame.transform.scale(self.canvas, self.screen.get_size(), self.screen)
        pygame.display.flip()

    def draw_hud(self, step: int) -> None:
        # The text tone snaps between the two palettes rather than interpolating
        # with them: the blended value sits right on top of a mid-dusk sky and
        # would be unreadable for the whole transition.
        ink = NIGHT.text if is_night(step) else DAY.text

        text = f"{int(self.world.score):05d}"
        if self.highscore:
            text = f"HI {self.highscore:05d}  {text}"
        pixelfont.draw(
            self.canvas, text, world.WIDTH - pixelfont.text_width(text) - 6, 6, ink
        )

        if self.state == TITLE:
            pixelfont.draw_centered(self.canvas, "SLIME RUNNER", world.WIDTH, 28, ink, 2)
            pixelfont.draw_centered(self.canvas, "SPACE OR W - JUMP", world.WIDTH, 48, ink)
            pixelfont.draw_centered(self.canvas, "S - DUCK   A/D - SHIFT", world.WIDTH, 57, ink)
            pixelfont.draw_centered(self.canvas, "Q - QUIT", world.WIDTH, 66, ink)
        elif self.state == GAME_OVER:
            pixelfont.draw_centered(self.canvas, "GAME OVER", world.WIDTH, 30, ink, 2)
            pixelfont.draw_centered(
                self.canvas, "R - RUN AGAIN   Q - QUIT", world.WIDTH, 50, ink
            )


def main() -> None:
    pygame.init()
    try:
        game = Game()
    except pygame.error as exc:
        pygame.quit()
        raise SystemExit(
            f"Could not open a game window: {exc}\n"
            "Slime Runner needs a graphical display; over SSH, forward X11 or run "
            "it locally."
        ) from exc
    try:
        game.run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
