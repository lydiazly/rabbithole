"""Window, low-resolution canvas, fixed-timestep loop, and the game states.

Everything is drawn onto a small canvas and blown up to the window with a
nearest-neighbour integer scale at the very end, so every pixel on screen is a
whole number of canvas pixels and nothing is ever half-drawn between them.

The states form a loop rather than a chain: select a character, see its title
screen, run, die, and land back on that character's title screen ready to go
again. Getting back into a run is one key from anywhere.
"""

import asyncio
import random
import sys

import pygame

from . import characters, effects, pixelfont, scenes, sfx, storage, world
from .palette import step_at
from .player import HARD_LANDING, Player, idle_body_frame

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
MENU_KEYS = (pygame.K_m,)
PAUSE_KEYS = (pygame.K_p,)
PICK_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)
ROW_UP_KEYS = (pygame.K_UP, pygame.K_w)
ROW_DOWN_KEYS = (pygame.K_DOWN, pygame.K_s)

# The menu's rows, top to bottom.
CHARACTER_ROW = 0
SCENE_ROW = 1
SOUND_ROW = 2
MENU_ROWS = (CHARACTER_ROW, SCENE_ROW, SOUND_ROW)
SOUND_CHOICES = ("ON", "OFF")

JUMP_BUFFER = 0.12  # a press just before landing still counts

# The dash: a stretch of invincibility earned by clearing obstacles, during which
# the world speeds up and anything in the way gets flattened instead of fatal.
# Mario's starman, with the score standing in for the item box.
#
# Smashed obstacles count for score *and* toward the next dash, which on its own
# would chain: a dash smashes enough to pay for the next one. The cooldown is
# what stops that, measured from the end of the last dash, so two dashes are
# always a real stretch of ordinary running apart.
DASH_EVERY = 20  # points
DASH_COOLDOWN = 12.0
DASH_SECONDS = 5.0
DASH_BOOST = 1.6
DASH_SHIMMER_TICKS = 3  # frames per palette step, while dashing

# The dash runs on a timer but must not end into a wall. Gaps spawned before it
# started arrive in 0.52s once boosted, under the 0.60s a jump needs, which is
# fine while invincible -- but nothing otherwise stops the clock running out with
# an obstacle already a few pixels away. That is a death the reward caused and
# the player could not have avoided, so the dash holds past zero, still smashing
# and so still clearing the way, until there is room to react.
# A jump's own airtime is the floor and 0.40 was under it: an obstacle that close
# is already inside the arc by the time the player commits, so the jump that
# looked available never was. On top of the airtime goes time to see the obstacle
# and decide, which is the part that was missing. 0.30 was still not enough in
# play -- coming off a dash the player is not reading the ground yet, so the
# margin has to cover looking up as well as reacting.
#
# 0.75 is as far as this is worth taking: the resulting 1.35s reaches 277px at
# top speed, against a 300px canvas, so past here the rule saturates into "no
# obstacle is on screen ahead of you" and asking for more changes nothing.
# Measured across eighty dashes, raising it further moves neither the worst case
# nor the hold. The hold stays bounded because obstacles spawn at the right edge:
# mean 0.67s, worst 3.55s, and it never fails to find an exit.
DASH_EXIT_REACTION = 0.75
DASH_EXIT_CLEARANCE = world.JUMP_AIRTIME + DASH_EXIT_REACTION

# The last stretch of a dash, where it starts telling you it is about to go: the
# shimmer doubles its rate and the meter blinks. Ending it silently was the one
# part of the dash the player could not see coming, and it is the part that
# matters, because the next obstacle stops being furniture.
DASH_WARN_SECONDS = 1.5
DASH_WARN_BLINK = 6
# Traffic thins out over that last stretch. Whatever spawns during it is what the
# player meets unaided a second later, so it is worth being generous exactly
# here, and thinner traffic also means the exit check finds its clear screen
# sooner rather than holding the dash open hunting for one.
DASH_WARN_GAP_SCALE = 1.8

# Then nothing at all for a moment. An ordinary gap can never leave the screen
# empty -- the spawner measures distance, so something is always on its way in --
# and an empty screen is the clearest possible statement that the dash is over
# and the next thing is the player's problem. Two seconds until the next obstacle
# appears at the right edge, and then the width of the canvas again before it
# arrives, which is the breather the boost was borrowing against.
DASH_RECOVERY = 3.0
DASH_OVER_PROMPT = "GET READY"
# Popped rather than blinked. A blink is only visible if you happen to be looking
# when it starts; something that grows is still obviously mid-growth a moment
# later, which is the whole problem with signalling the end of a dash. It grows
# and then goes, leaving the rest of the breather quiet -- the empty screen says
# the same thing, and words that outstayed the moment would just be furniture.
DASH_OVER_POP = ((1, 0.07), (2, 0.07), (3, 0.90))  # scale, seconds held

# Telling the player what a dash is for. Two words, blinked over the sky for the
# first stretch of it, then out of the way -- long enough to be read on the first
# dash of a first run, short enough not to sit on top of the game after that.
DASH_PROMPT = "SMASH THROUGH"
DASH_PROMPT_SECONDS = 1.6
DASH_PROMPT_BLINK = 14  # frames lit, frames dark: about two blinks a second

# Smashing something should feel like it cost the obstacle rather than the
# player. Three things at once, none of them expensive:
#
# Hit-stop -- the world holds still for two frames on impact. It is the oldest
# trick in the genre and the strongest: a hit that stops time reads as a hit that
# had mass. Two frames is 33ms, under the threshold where it registers as a
# stutter, and it does not stack when a cluster is struck in one frame.
#
# Shake -- the whole canvas offset by a pixel for a few frames. One pixel of 108
# is a lot of shake, which is why the pattern settles rather than repeating.
# Written out rather than randomised so it is the same shake every time, and so
# nothing has to own a random state to draw a frame.
SMASH_FREEZE = 2
SMASH_SHAKE = ((0, 1), (1, -1), (-1, 1), (0, -1), (0, 0))

# Speed lines. Their positions come out of the tick, so the whole effect is five
# fills and nothing to store, reset or tidy up when the dash ends. The rows dodge
# the HUD strip and the row the prompt is printed on, or they read as stray
# underlines beneath the text.
DASH_STREAK_ROWS = (20, 27, 45, 52, 63)
DASH_STREAK_LEN = 11

# After dying, the run ends by itself. The lockout is there because the key that
# killed you is often still coming: without it the banner can be gone before it
# has been read.
GAME_OVER_LOCKOUT = 0.5
GAME_OVER_HOLD = 3.5

MENU = "menu"
TITLE = "title"
PLAYING = "playing"
GAME_OVER = "over"


def pop_scale(elapsed: float) -> int:
    """The prompt's size this far into the pop, or 0 once it is over."""
    for scale, seconds in DASH_OVER_POP:
        if elapsed < seconds:
            return scale
        elapsed -= seconds
    return 0


class Game:
    def __init__(self):
        self.rng = random.Random()
        self.screen = pygame.display.set_mode(
            (world.WIDTH * SCALE, world.HEIGHT * SCALE)
        )
        pygame.display.set_caption("Mochi Dash")
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((world.WIDTH, world.HEIGHT))

        self.scene = scenes.DEFAULT
        self.world = world.World(self.scene, self.rng)
        self.player = Player(START_X, world.GROUND_Y)
        self.puffs = effects.Puffs()

        self.character = characters.DEFAULT
        self.picks = {CHARACTER_ROW: 0, SCENE_ROW: 0, SOUND_ROW: 0}
        self.row = CHARACTER_ROW
        self.preview_tick = 0
        self.highscore = storage.load()
        self.over_timer = 0.0
        self.jump_buffer = 0.0
        self.tick = 0
        self.paused = False
        self.score = 0
        self.toward_dash = 0
        self.dash_left = 0.0
        self.dash_on = False
        self.dash_cooldown = 0.0
        self.recovery = 0.0
        self.freeze = 0
        self.shake = 0
        self.state = MENU

    # -- state transitions ------------------------------------------------

    @property
    def previewed_scene(self):
        """The scene under the cursor -- the select screen renders it live."""
        return scenes.SCENES[self.picks[SCENE_ROW]]

    @property
    def previewed_character(self):
        return characters.CHARACTERS[self.picks[CHARACTER_ROW]]

    def go_to_menu(self) -> None:
        self.state = MENU
        self.preview_tick = 0
        self.world.use_scene(self.previewed_scene)
        self.player.reset()
        self.puffs.clear()

    def go_to_title(self) -> None:
        self.state = TITLE
        self.world.use_scene(self.scene)
        self.player.reset()
        self.puffs.clear()
        self.jump_buffer = 0.0
        self.paused = False
        self.score = 0
        self.toward_dash = 0
        self.dash_left = 0.0
        self.dash_on = False
        self.dash_cooldown = 0.0
        self.recovery = 0.0
        self.freeze = 0
        self.shake = 0

    def start_run(self) -> None:
        self.go_to_title()
        self.state = PLAYING

    def end_run(self) -> None:
        self.state = GAME_OVER
        self.over_timer = 0.0
        sfx.play("die")
        self.end_dash()
        self.player.die()
        self.puffs.burst(self.player.x, world.GROUND_Y, True)
        if self.score > self.highscore:
            self.highscore = self.score
            storage.save(self.score)

    # -- the dash ---------------------------------------------------------

    @property
    def dashing(self) -> bool:
        """Invincible. Tracked apart from the clock, which can run out while the
        dash is still being held open for a clear exit."""
        return self.dash_on

    def start_dash(self) -> None:
        self.dash_left = DASH_SECONDS
        self.dash_on = True
        self.dash_cooldown = DASH_COOLDOWN
        self.toward_dash = 0
        self.world.boost = DASH_BOOST
        sfx.play("dash")

    @property
    def dash_ending(self) -> bool:
        return self.dashing and self.dash_left < DASH_WARN_SECONDS

    def end_dash(self) -> None:
        # Dying calls this, and dying while dashing is the one thing that cannot
        # happen, so without the guard every death played the power-down over the
        # death sound and armed a breather for a run that was already over.
        if not self.dash_on:
            return
        self.dash_left = 0.0
        self.dash_on = False
        self.world.boost = 1.0
        self.world.gap_scale = 1.0
        self.world.hush(DASH_RECOVERY)
        self.recovery = DASH_RECOVERY
        sfx.play("power_down")

    def exit_is_clear(self) -> bool:
        """Whether there is room ahead to react once the boost drops."""
        left, _, width, _ = self.player.hitbox()
        front = left + width
        reach = DASH_EXIT_CLEARANCE * self.world.speed
        return not any(
            not ob.launched and front < ob.x < front + reach
            for ob in self.world.obstacles
        )

    # -- loop -------------------------------------------------------------

    async def run(self) -> None:
        """The loop.

        Async only because that is how a browser lets go: pygbag runs this same
        loop on the page's event loop, and without a yield inside it the tab
        would freeze rather than draw. On a desktop the await costs a trip
        through an event loop that has nothing else to do.
        """
        accumulator = 0.0
        while True:
            if not self.handle_events():
                return
            accumulator += min(self.clock.tick(60) / 1000.0, MAX_FRAME)
            while accumulator >= DT:
                self.update(DT)
                accumulator -= DT
            self.draw()
            await asyncio.sleep(0)

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
            if event.key in MENU_KEYS and self.state != MENU:
                self.go_to_menu()
            elif event.key in PAUSE_KEYS and self.state == PLAYING:
                self.paused = not self.paused
            elif self.paused:
                continue  # everything else is inert while held
            elif self.state == MENU:
                self.menu_key(event.key)
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
        return {
            CHARACTER_ROW: characters.CHARACTERS,
            SCENE_ROW: scenes.SCENES,
            SOUND_ROW: SOUND_CHOICES,
        }[row]

    def menu_key(self, key: int) -> None:
        count = len(self.row_options(self.row))
        moved = True
        if key in LEFT_KEYS:
            self.picks[self.row] = (self.picks[self.row] - 1) % count
        elif key in RIGHT_KEYS:
            self.picks[self.row] = (self.picks[self.row] + 1) % count
        elif key in PICK_KEYS[:count]:
            self.picks[self.row] = PICK_KEYS.index(key)
        elif key in ROW_UP_KEYS:
            self.row = (self.row - 1) % len(MENU_ROWS)
        elif key in ROW_DOWN_KEYS:
            self.row = (self.row + 1) % len(MENU_ROWS)
        elif key in CONFIRM_KEYS:
            self.scene = self.previewed_scene
            self.character = self.previewed_character
            self.go_to_title()
            return
        else:
            moved = False
        if moved:
            sfx.enabled = self.picks[SOUND_ROW] == 0
            sfx.play("blip")
            # The backdrop is the previewed scene, so moving the scene cursor has
            # to rebuild it -- the layers it uses may differ.
            self.world.use_scene(self.previewed_scene)

    def update(self, dt: float) -> None:
        if self.paused:
            return
        if self.state == MENU:
            self.preview_tick += 1
            return

        if self.state != PLAYING:
            if self.state == GAME_OVER:
                self.over_timer += dt
                if self.over_timer >= GAME_OVER_HOLD:
                    self.go_to_title()
                    return
            # The idle breathe and the tail of the death clip both keep running.
            self.player.update(dt, False, False, 0, X_MIN, X_MAX)
            self.puffs.update(dt, 0.0)
            return

        # Hit-stop. Everything holds except the counters that draw it, so the
        # shake keeps moving over a world that does not. A jump pressed during
        # these two frames is already in the buffer and survives.
        self.shake = max(0, self.shake - 1)
        if self.freeze > 0:
            self.freeze -= 1
            self.tick += 1
            return

        keys = pygame.key.get_pressed()
        holding_jump = any(keys[k] for k in JUMP_KEYS)
        ducking = any(keys[k] for k in DUCK_KEYS)
        lateral = any(keys[k] for k in RIGHT_KEYS) - any(keys[k] for k in LEFT_KEYS)

        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.jump_buffer > 0.0:
            kind = self.player.jump()
            if kind:
                self.jump_buffer = 0.0
            if kind == "ground":
                sfx.play("jump")
            elif kind == "air":
                sfx.play("double_jump")
                # A puff under its feet in mid-air is the only signal that the
                # second jump has been spent.
                self.puffs.burst(self.player.x, self.player.y, False)

        self.tick += 1
        self.award(self.world.update(dt, self.player.x))
        impact = self.player.update(dt, holding_jump, ducking, lateral, X_MIN, X_MAX)
        if impact:
            self.puffs.burst(self.player.x, world.GROUND_Y, impact >= HARD_LANDING)
        self.puffs.update(dt, self.world.scroll)

        if self.dashing:
            self.dash_left = max(0.0, self.dash_left - dt)
            self.world.gap_scale = DASH_WARN_GAP_SCALE if self.dash_ending else 1.0
            if self.dash_left <= 0.0 and self.exit_is_clear():
                self.end_dash()
        else:
            self.recovery = max(0.0, self.recovery - dt)
            self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
            if self.toward_dash >= DASH_EVERY and self.dash_cooldown <= 0.0:
                self.start_dash()

        struck = self.world.hits(self.player.hitbox())
        if not struck:
            return
        if not self.dashing:
            self.end_run()
            return
        for ob in struck:
            if not ob.scored:
                self.award(world.points_for(ob))
            self.world.launch(ob)
            # At the obstacle, not on the ground under it. A smashed flyer used
            # to puff at floor level, a body-length below where it was hit.
            self.puffs.burst(ob.x + ob.w / 2, ob.y + ob.h, True)
        # One of each per frame, however many were struck: a cluster is one
        # impact to the player, and stacked hit-stop would read as a hang.
        self.freeze = SMASH_FREEZE
        self.shake = len(SMASH_SHAKE)
        sfx.play("smash")

    def award(self, cleared: int) -> None:
        self.score += cleared
        self.toward_dash += cleared

    # -- drawing ----------------------------------------------------------

    def draw(self) -> None:
        scene = self.previewed_scene if self.state == MENU else self.scene
        step = step_at(self.world.phase)
        palette = scenes.palette_for_step(scene, step)
        ink, halo = scenes.text_tones(scene, step)

        scenery = scenes.sheet_for(scene, step)
        self.world.draw(self.canvas, palette, step, scenery)

        if self.state == MENU:
            self.draw_menu(step, ink, halo)
        else:
            self.puffs.draw(self.canvas, scenery)
            # Dashing strobes the character through the dash tints -- Mario's
            # starman palette flash. Deliberately not the day/night steps it used
            # to run through: those include the night look, so the flash was
            # indistinguishable from nightfall in one direction and from nothing
            # at all in the other.
            dash_tint = None
            if self.dashing:
                rate = 1 if self.dash_ending else DASH_SHIMMER_TICKS
                dash_tint = self.tick // rate
                # Not while paused: nothing is moving, so speed lines would be
                # lying, and they cross the overlay besides.
                if not self.paused:
                    self.draw_streaks(ink)
            self.blit_character(
                self.character, step, self.player.frame,
                self.accessory_frame(self.character, self.player.accessory_ticks,
                                     self.player.idle),
                self.player.blit_pos(),
                dash_tint,
            )
            self.draw_hud(ink, halo)

        if self.shake:
            # Shifted before the upscale, so the shake is a whole canvas pixel
            # and the nearest-neighbour blowup stays exact. `scroll` moves the
            # content in place and leaves the vacated edge holding its old
            # pixels, which smears rather than showing a black bar, and costs no
            # second surface.
            dx, dy = SMASH_SHAKE[len(SMASH_SHAKE) - self.shake]
            if dx or dy:
                self.canvas.scroll(dx, dy)
        pygame.transform.scale(self.canvas, self.screen.get_size(), self.screen)
        pygame.display.flip()

    @staticmethod
    def accessory_frame(character, ticks: int, idle: bool) -> int:
        """Where the accessory's idle cycle is, or frame 0 while acting."""
        if character.accessory is None or not idle:
            return 0
        return character.accessory.frame_at(ticks)

    def blit_character(self, character, step, frame, accessory_frame, pos,
                       dash_tint=None) -> None:
        """Draw one character, accessory first so the head overlaps its base.

        `dash_tint` replaces the day/night sheet with a charged one -- the dash
        overrides the sky rather than being lit by it.
        """
        sheet = (characters.sheet_for(character, step) if dash_tint is None
                 else characters.dash_sheet_for(character, dash_tint))
        left, top = pos
        if character.accessory is not None:
            facings = sheet.accessory[accessory_frame]
            dy, placements = character.accessory_anchors[frame]
            for dx, flipped in placements:
                self.canvas.blit(facings[flipped], (left + dx, top + dy))
        self.canvas.blit(sheet.poses[frame], pos)

    def text(self, line: str, y: int, ink, halo, scale: int = 1, x=None) -> None:
        """Centred by default, with a one-pixel shadow so it survives any sky."""
        if x is None:
            x = (world.WIDTH - pixelfont.text_width(line, scale)) // 2
        pixelfont.draw(self.canvas, line, x + 1, y + 1, halo, scale)
        pixelfont.draw(self.canvas, line, x, y, ink, scale)

    # The character runs between x=22 and x=110 of a 300-pixel canvas, so the
    # player's eye lives in the left third and the top-left corner is the
    # cheapest thing on screen to glance at. That corner should hold the thing
    # worth glancing at repeatedly, which is the score. The hotkeys are reference
    # text -- read once at the start of a first run and then permanent furniture
    # -- and they were sitting in the best seat while the number that changes sat
    # in the far corner. They are also the longer line by a good margin, so the
    # right-hand side is where there is room for them.
    HUD_MARGIN = 6

    def draw_hud(self, ink, halo) -> None:
        score = f"{self.score:04d}"
        if self.highscore:
            score = f"HI {self.highscore:04d}  {score}"
        self.text(score, 6, ink, halo, x=self.HUD_MARGIN)

        if self.state == PLAYING:
            keys = "P PAUSE  R RETRY  M MENU"
            self.text(keys, 6, ink, halo,
                      x=world.WIDTH - pixelfont.text_width(keys) - self.HUD_MARGIN)
            self.draw_dash_meter(ink, halo)
            if self.paused:
                self.text("PAUSED", 34, ink, halo, 2)
                self.text("P  RESUME", 52, ink, halo)
            elif self.dashing:
                # Blinked off the dash's own elapsed time, not the global tick:
                # phased against the tick the prompt starts wherever it happens
                # to land, and can open on its dark half.
                elapsed = DASH_SECONDS - self.dash_left
                lit = int(elapsed * 60) // DASH_PROMPT_BLINK % 2 == 0
                if elapsed < DASH_PROMPT_SECONDS and lit:
                    self.text(DASH_PROMPT, 34, ink, halo)
            elif self.recovery > 0.0:
                # Said in words on an empty screen, because everything else
                # about the ending was a change in something -- the strobe
                # stopping, the meter going, the speed dropping -- and a player
                # who was not watching for a change does not see one.
                scale = pop_scale(DASH_RECOVERY - self.recovery)
                if scale:
                    # Kept centred as it grows: the text is drawn from its top
                    # left, so a taller line would otherwise sink down the
                    # screen instead of swelling in place.
                    height = pixelfont.GLYPH_H * scale
                    self.text(DASH_OVER_PROMPT, 34 + (15 - height) // 2,
                              ink, halo, scale)
        elif self.state == TITLE:
            self.text(self.character.name, 20, ink, halo, 2)
            self.text("SPACE OR W - JUMP", 38, ink, halo)
            self.text("JUMP AGAIN IN AIR TO DOUBLE", 47, ink, halo)
            self.text("S - DUCK   A/D - SHIFT", 56, ink, halo)
            self.text("M - MENU   Q - QUIT", 65, ink, halo)
        elif self.state == GAME_OVER:
            self.text("GAME OVER", 30, ink, halo, 2)
            self.text(f"SCORE {self.score:04d}", 50, ink, halo)
            if self.over_timer >= GAME_OVER_LOCKOUT:
                self.text("ANY KEY TO CONTINUE", 62, ink, halo)

    # A plain list with a cursor, in the shape every pixel-era option screen
    # used. The chosen character stands below it in the chosen scene, so the
    # menu previews both without needing a swatch for either.
    MENU_LABEL_X = 76
    MENU_VALUE_X = 158
    MENU_TOP = 40
    MENU_PITCH = 11

    DASH_METER_W = 48
    DASH_METER_Y = 16
    DASH_STAR_BLINK = 8

    def draw_streaks(self, ink) -> None:
        """Speed lines across the sky while dashing."""
        span = world.WIDTH + 40
        for i, y in enumerate(DASH_STREAK_ROWS):
            x = span - (self.tick * (7 + i * 2) + i * 61) % span
            self.canvas.fill(ink, (x, y, DASH_STREAK_LEN, 1))

    def draw_dash_meter(self, ink, halo) -> None:
        """Either how much dash is left, or how much is owed before the next one.

        One gauge for both, because they are the same question asked from either
        side, and a second widget on a 300-pixel canvas is a widget too many.
        """
        if self.dashing:
            filled = self.dash_left / DASH_SECONDS
        else:
            owed = min(1.0, self.toward_dash / DASH_EVERY)
            waited = 1.0 if DASH_COOLDOWN <= 0 else min(
                1.0, 1.0 - self.dash_cooldown / DASH_COOLDOWN
            )
            filled = min(owed, waited)
        if self.dash_ending and (self.tick // DASH_WARN_BLINK) % 2:
            return  # blinked out: the dash is about to end
        # Under the score, sharing its margin: the meter and the number it fills
        # from are the same fact twice, and the top-left corner is the one the
        # player is already looking at.
        x = self.HUD_MARGIN
        y = self.DASH_METER_Y
        # A star, because an unlabelled bar in the corner of a first run is just
        # a bar. Mario's is the one everybody has already learned, and the code
        # was calling this a starman anyway. It flashes once the bar is full and
        # stays lit for the dash, so one cycle teaches what the bar is counting
        # towards without a word of tutorial.
        ready = self.dashing or filled >= 1.0
        if not ready or (self.tick // self.DASH_STAR_BLINK) % 2 == 0:
            pixelfont.draw(self.canvas, "*", x + 1, y - 1, halo)
            pixelfont.draw(self.canvas, "*", x, y - 2, ink)
        x += pixelfont.GLYPH_W + 3
        self.canvas.fill(halo, (x, y + 1, self.DASH_METER_W, 2))
        self.canvas.fill(ink, (x, y, self.DASH_METER_W, 1))
        width = round(self.DASH_METER_W * max(0.0, min(1.0, filled)))
        if width:
            self.canvas.fill(ink, (x, y, width, 2))

    def draw_menu(self, step, ink, halo) -> None:
        self.text("MOCHI DASH", 16, ink, halo, 2)

        rows = (
            ("CHARACTER", self.previewed_character.name),
            ("SCENE", self.previewed_scene.name),
            ("SOUND", SOUND_CHOICES[self.picks[SOUND_ROW]]),
        )
        for i, (label, value) in enumerate(rows):
            y = self.MENU_TOP + i * self.MENU_PITCH
            if i == self.row:
                self.draw_cursor(self.MENU_LABEL_X - 10, y, ink)
            self.text(label, y, ink, halo, x=self.MENU_LABEL_X)
            self.text(f"< {value} >", y, ink, halo, x=self.MENU_VALUE_X)

        self.text("W/S  ROW    A/D  CHANGE    SPACE  START", 98, ink, halo)

        # The character stands on the ground below the list, in the scene the
        # menu is currently showing.
        frame = idle_body_frame(self.preview_tick)
        character = self.previewed_character
        surf = characters.sheet_for(character, step).poses[frame]
        self.blit_character(
            character, step, frame,
            self.accessory_frame(character, self.preview_tick, True),
            (world.WIDTH // 2 - surf.get_width() // 2,
             world.GROUND_Y - surf.get_height()),
        )

    def draw_cursor(self, x: int, y: int, ink) -> None:
        """A right-pointing wedge beside the active row."""
        for row in range(5):
            width = 3 - abs(row - 2)
            self.canvas.fill(ink, (x, y + row, width, 1))


async def play() -> None:
    """Set up and run to the end. The web build awaits this directly.

    Kept apart from main() because pygbag needs an awaitable to hand to the
    page's event loop, while a console script needs something it can just call.
    """
    sfx.prepare()  # before pygame.init(), or the device is opened twice
    pygame.init()
    sfx.init()
    try:
        game = Game()
    except pygame.error as exc:
        pygame.quit()
        raise SystemExit(
            f"Could not open a game window: {exc}\n"
            "Mochi Dash needs a graphical display; over SSH, forward X11 or run "
            "it locally."
        ) from exc
    try:
        await game.run()
    finally:
        pygame.quit()


def main() -> None:
    """The [project.scripts] entry point, for playing on a desktop."""
    asyncio.run(play())


if __name__ == "__main__":
    sys.exit(main())
