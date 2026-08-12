"""Window, low-resolution canvas, fixed-timestep loop, and the game states.

Everything is drawn onto a small canvas and blown up to the window with a
nearest-neighbour integer scale at the very end, so every pixel on screen is a
whole number of canvas pixels and nothing is ever half-drawn between them.

The states form a loop rather than a chain: select a character, see its title
screen, run, die, and land back on that character's title screen ready to go
again. Getting back into a run is one key from anywhere.
"""

import random
import sys
from pathlib import Path

import pygame

from . import characters, effects, pixelfont, scenes, world
from .palette import step_at
from .slime import HARD_LANDING, Slime, idle_body_frame

SCALE = 3
DT = 1.0 / 60.0
MAX_FRAME = 0.25  # never simulate more than this per frame, however slow it got

START_X = 42.0
X_MIN = 22.0
X_MAX = 110.0

JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w, pygame.K_RETURN)
# On the select screen up/down change row, so only these confirm a choice.
CONFIRM_KEYS = (pygame.K_SPACE, pygame.K_RETURN)
DUCK_KEYS = (pygame.K_DOWN, pygame.K_s)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
QUIT_KEYS = (pygame.K_ESCAPE, pygame.K_q)
RESTART_KEYS = (pygame.K_r,)
SELECT_KEYS = (pygame.K_c,)
PICK_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)
ROW_UP_KEYS = (pygame.K_UP, pygame.K_w)
ROW_DOWN_KEYS = (pygame.K_DOWN, pygame.K_s)

# The select screen's two rows, top to bottom.
SCENE_ROW = 0
CHARACTER_ROW = 1

JUMP_BUFFER = 0.12  # a press just before landing still counts

# After dying, the run ends by itself. The lockout is there because the key that
# killed you is often still coming: without it the banner can be gone before it
# has been read.
GAME_OVER_LOCKOUT = 0.5
GAME_OVER_HOLD = 3.5

HIGHSCORE_PATH = Path(__file__).resolve().parent.parent / ".highscore"

SELECT = "select"
TITLE = "title"
PLAYING = "playing"
GAME_OVER = "over"


def preview_positions(count: int) -> list[int]:
    """Evenly spaced stands for the character previews.

    Computed rather than tabulated: a hardcoded pair of x values was an
    IndexError the moment a third character existed.
    """
    return [round(world.WIDTH * (i + 1) / (count + 1)) for i in range(count)]


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

        self.scene = scenes.DEFAULT
        self.world = world.World(self.scene, self.rng)
        self.slime = Slime(START_X, world.GROUND_Y)
        self.puffs = effects.Puffs()

        self.character = characters.DEFAULT
        self.picks = {SCENE_ROW: 0, CHARACTER_ROW: 0}
        self.row = CHARACTER_ROW
        self.preview_tick = 0
        self.highscore = load_highscore()
        self.over_timer = 0.0
        self.jump_buffer = 0.0
        self.state = SELECT

    # -- state transitions ------------------------------------------------

    @property
    def previewed_scene(self):
        """The scene under the cursor -- the select screen renders it live."""
        return scenes.SCENES[self.picks[SCENE_ROW]]

    @property
    def previewed_character(self):
        return characters.CHARACTERS[self.picks[CHARACTER_ROW]]

    def go_to_select(self) -> None:
        self.state = SELECT
        self.preview_tick = 0
        self.world.use_scene(self.previewed_scene)
        self.slime.reset()
        self.puffs.clear()

    def go_to_title(self) -> None:
        self.state = TITLE
        self.world.use_scene(self.scene)
        self.slime.reset()
        self.puffs.clear()
        self.jump_buffer = 0.0

    def start_run(self) -> None:
        self.go_to_title()
        self.state = PLAYING

    def end_run(self) -> None:
        self.state = GAME_OVER
        self.over_timer = 0.0
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
            # Checked before anything else, so quitting works from every screen
            # including the game-over banner, where any other key means "carry on".
            if event.key in QUIT_KEYS:
                return False
            if event.key in SELECT_KEYS and self.state != SELECT:
                self.go_to_select()
            elif self.state == SELECT:
                self.select_key(event.key)
            elif self.state == TITLE:
                if event.key in JUMP_KEYS:
                    self.start_run()
            elif self.state == PLAYING:
                if event.key in JUMP_KEYS:
                    self.jump_buffer = JUMP_BUFFER
                elif event.key in RESTART_KEYS:
                    self.start_run()
            elif self.state == GAME_OVER and self.over_timer >= GAME_OVER_LOCKOUT:
                self.go_to_title()
        return True

    def row_options(self, row: int):
        return scenes.SCENES if row == SCENE_ROW else characters.CHARACTERS

    def select_key(self, key: int) -> None:
        count = len(self.row_options(self.row))
        moved = True
        if key in LEFT_KEYS:
            self.picks[self.row] = (self.picks[self.row] - 1) % count
        elif key in RIGHT_KEYS:
            self.picks[self.row] = (self.picks[self.row] + 1) % count
        elif key in PICK_KEYS[:count]:
            self.picks[self.row] = PICK_KEYS.index(key)
        elif key in ROW_UP_KEYS:
            self.row = SCENE_ROW
        elif key in ROW_DOWN_KEYS:
            self.row = CHARACTER_ROW
        elif key in CONFIRM_KEYS:
            self.scene = self.previewed_scene
            self.character = self.previewed_character
            self.go_to_title()
            return
        else:
            moved = False
        if moved:
            # The backdrop is the previewed scene, so moving the scene cursor has
            # to rebuild it -- the layers it uses may differ.
            self.world.use_scene(self.previewed_scene)

    def update(self, dt: float) -> None:
        if self.state == SELECT:
            self.preview_tick += 1
            return

        if self.state != PLAYING:
            if self.state == GAME_OVER:
                self.over_timer += dt
                if self.over_timer >= GAME_OVER_HOLD:
                    self.go_to_title()
                    return
            # The idle breathe and the tail of the splat clip both keep running.
            self.slime.update(dt, False, False, 0, X_MIN, X_MAX)
            self.puffs.update(dt, 0.0)
            return

        keys = pygame.key.get_pressed()
        holding_jump = any(keys[k] for k in JUMP_KEYS)
        ducking = any(keys[k] for k in DUCK_KEYS)
        lateral = any(keys[k] for k in RIGHT_KEYS) - any(keys[k] for k in LEFT_KEYS)

        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.jump_buffer > 0.0:
            kind = self.slime.jump()
            if kind:
                self.jump_buffer = 0.0
            if kind == "air":
                # A puff under its feet in mid-air is the only signal that the
                # second jump has been spent.
                self.puffs.burst(self.slime.x, self.slime.y, False)

        self.world.update(dt)
        impact = self.slime.update(dt, holding_jump, ducking, lateral, X_MIN, X_MAX)
        if impact:
            self.puffs.burst(self.slime.x, world.GROUND_Y, impact >= HARD_LANDING)
        self.puffs.update(dt, self.world.speed)

        if self.world.collides(self.slime.hitbox()):
            self.end_run()

    # -- drawing ----------------------------------------------------------

    def draw(self) -> None:
        scene = self.previewed_scene if self.state == SELECT else self.scene
        step = step_at(self.world.phase)
        palette = scenes.palette_for_step(scene, step)
        ink, halo = scenes.text_tones(scene, step)

        scenery = scenes.sheet_for(scene, step)
        self.world.draw(self.canvas, palette, step, scenery)

        if self.state == SELECT:
            self.draw_select(step, ink, halo)
        else:
            self.puffs.draw(self.canvas, scenery)
            self.blit_character(
                self.character, step, self.slime.frame,
                self.accessory_frame(self.character, self.slime.accessory_ticks,
                                     self.slime.idle),
                self.slime.blit_pos(),
            )
            self.draw_hud(ink, halo)

        pygame.transform.scale(self.canvas, self.screen.get_size(), self.screen)
        pygame.display.flip()

    @staticmethod
    def accessory_frame(character, ticks: int, idle: bool) -> int:
        """Where the accessory's idle cycle is, or frame 0 while acting."""
        if character.accessory is None or not idle:
            return 0
        return character.accessory.frame_at(ticks)

    def blit_character(self, character, step, frame, accessory_frame, pos) -> None:
        """Draw one character, accessory first so the head overlaps its base."""
        sheet = characters.sheet_for(character, step)
        left, top = pos
        if character.accessory is not None:
            art_left, art_right = sheet.accessory[accessory_frame]
            dx_left, dx_right, dy = character.accessory.anchors[frame]
            self.canvas.blit(art_left, (left + dx_left, top + dy))
            self.canvas.blit(art_right, (left + dx_right, top + dy))
        self.canvas.blit(sheet.poses[frame], pos)

    def text(self, line: str, y: int, ink, halo, scale: int = 1, x=None) -> None:
        """Centred by default, with a one-pixel shadow so it survives any sky."""
        if x is None:
            x = (world.WIDTH - pixelfont.text_width(line, scale)) // 2
        pixelfont.draw(self.canvas, line, x + 1, y + 1, halo, scale)
        pixelfont.draw(self.canvas, line, x, y, ink, scale)

    def draw_hud(self, ink, halo) -> None:
        score = f"{int(self.world.score):05d}"
        if self.highscore:
            score = f"HI {self.highscore:05d}  {score}"
        self.text(score, 6, ink, halo, x=world.WIDTH - pixelfont.text_width(score) - 6)

        if self.state == PLAYING:
            self.text("R RETRY  C SELECT", 6, ink, halo, x=6)
        elif self.state == TITLE:
            self.text(self.character.name, 20, ink, halo, 2)
            self.text("SPACE OR W - JUMP", 38, ink, halo)
            self.text("JUMP AGAIN IN AIR TO DOUBLE", 47, ink, halo)
            self.text("S - DUCK   A/D - SHIFT", 56, ink, halo)
            self.text("C - CHARACTER   Q - QUIT", 65, ink, halo)
        elif self.state == GAME_OVER:
            self.text("GAME OVER", 30, ink, halo, 2)
            self.text(f"SCORE {int(self.world.score):05d}", 50, ink, halo)
            if self.over_timer >= GAME_OVER_LOCKOUT:
                self.text("ANY KEY TO CONTINUE", 62, ink, halo)

    def draw_select(self, step, ink, halo) -> None:
        # The backdrop already *is* the previewed scene, so the scene row needs
        # only names -- the preview is the whole screen behind them.
        self.text("SCENE", 8, ink, halo)
        scene_xs = preview_positions(len(scenes.SCENES))
        for i, (scene, x) in enumerate(zip(scenes.SCENES, scene_xs)):
            self.text(scene.name, 24, ink, halo,
                      x=x - pixelfont.text_width(scene.name) // 2)
            if i == self.picks[SCENE_ROW]:
                self.draw_marker(x, 17, ink, active=self.row == SCENE_ROW)

        self.text("CHARACTER", 50, ink, halo)
        frame = idle_body_frame(self.preview_tick)
        for i, (character, x) in enumerate(
            zip(characters.CHARACTERS, preview_positions(len(characters.CHARACTERS)))
        ):
            surf = characters.sheet_for(character, step).poses[frame]
            pos = (x - surf.get_width() // 2, world.GROUND_Y - surf.get_height())
            self.blit_character(
                character, step, frame,
                self.accessory_frame(character, self.preview_tick, True), pos,
            )
            self.text(character.name, 88, ink, halo,
                      x=x - pixelfont.text_width(character.name) // 2)
            if i == self.picks[CHARACTER_ROW]:
                self.draw_marker(x, 62, ink, active=self.row == CHARACTER_ROW)

        self.text("A/D PICK  W/S ROW  SPACE GO", 98, ink, halo)

    def draw_marker(self, x: int, y: int, ink, active: bool = True) -> None:
        """A downward wedge over the current pick.

        Both rows keep their marker so the chosen pair is always readable; the
        row the keys are driving gets the full wedge, the other a flat bar.
        """
        rows = 3 if active else 1
        for row in range(rows):
            width = 5 - row * 2
            self.canvas.fill(ink, (x - width // 2, y + row + (0 if active else 2),
                                   width, 1))


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
