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

from . import (
    characters,
    effects,
    icon,
    pixelfont,
    scenes,
    sfx,
    sprites,
    storage,
    world,
)
from .palette import step_at
from .player import HARD_LANDING, Player, idle_body_frame

SCALE = 3
DT = 1.0 / 60.0
MAX_FRAME = 0.25  # never simulate more than this per frame, however slow it got

START_X = 42.0
X_MIN = 22.0
X_MAX = 110.0


def quit_keys_for(browser: bool) -> tuple:
    """The keys that end the game, which in a browser is none of them.

    Quitting is a desktop idea: the loop returns, the process ends, and the
    window goes with it. A page has neither half of that. pygbag replaces
    asyncio.run with one that schedules the loop as a task on the page's own
    event loop and returns, so a loop that ends runs pygame.quit() and then
    simply stops driving the canvas -- and a page cannot close a tab it did not
    open. The player would be left looking at a dead picture with no way back
    except a reload, which is worse than the key not being there at all.
    """
    return () if browser else (pygame.K_ESCAPE, pygame.K_q)


JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w, pygame.K_RETURN)
# On the select screen up/down change row, so only these confirm a choice.
CONFIRM_KEYS = (pygame.K_SPACE, pygame.K_RETURN)
DUCK_KEYS = (pygame.K_DOWN, pygame.K_s)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
# storage owns the emscripten check because it needed it first, and its note on
# why sys.platform is the right probe belongs with it rather than duplicated.
QUIT_KEYS = quit_keys_for(storage.BROWSER)
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

# Pointer input: a mouse on a desktop, a finger on a phone opening the web build.
#
# Both are handled, and the doubling that would otherwise cause is why. SDL turns
# a touch into a mouse event as well by default, so a phone delivers a tap twice;
# the synthesised one is flagged, and skipping it leaves exactly one press per
# press however the platform behaves. Handling only mouse events would be
# shorter and would rely on that synthesis being on, which is not something this
# code can check from here.
#
# A mouse is read by button and a finger by position, because each is asked the
# question it can answer. Left jumps, right ducks: two buttons for the two things
# the game asks for, with no cursor to aim. Reading a mouse by height instead
# would make the action depend on where the pointer happened to be resting,
# which is not something a mouse player is tracking.
MOUSE_JUMP_BUTTON = 1
MOUSE_DUCK_BUTTON = 3
# Holding matters as much as on the keyboard either way -- the jump is
# variable-height, so a click is a hop and a held button is the full arc.
#
# A finger has no buttons, so the screen splits in two for it: press low to duck,
# press anywhere above to jump, "down" being at the bottom needing no explaining.
# The line is the standing character's own crown, so the duck half is exactly the
# character and the ground beneath it and the jump half is the sky. Derived
# rather than picked: two thirds of the canvas happens to land on the same row
# today, and would stop meaning anything the moment a pose changed height. The
# ground band alone would be the tidier line to explain, and far too small a
# target -- 24 canvas rows is about five millimetres of a phone held upright.
POINTER_DUCK_FROM = world.GROUND_Y - sprites.POSE_SIZES["round"][1]

# The menu is a list, so a press there lands on whichever row it is nearest and
# on the arrow it is nearest, rather than meaning one global thing.
MENU_HIT_PAD = 4          # canvas rows either side of a row's text
MENU_START_FROM = 92      # below the list: the "SPACE START" line
TITLE_MENU_ROW = 65       # the title screen's "M - MENU" line

# The HUD's hotkey line, which is also its button row: with no keyboard these
# labels are the only way to pause, retry or reach the menu. Kept as parts rather
# than one string so the same layout draws them and decides what a press hits.
HUD_BUTTONS = (("P PAUSE", "pause"), ("R RETRY", "retry"), ("M MENU", "menu"))
HUD_BUTTON_GAP = 2  # spaces between them

# The banner's own menu button. Any press there already means "carry on", so
# without a target of its own the menu would be two screens away from the one
# place a run actually ends -- which on a phone is where you go to change
# character, and the only reason to leave the title screen at all.
OVER_MENU_LABEL = "M MENU"
OVER_MENU_ROW = 74

# Losing the window pauses a run. Minimising is included because it does not
# always come with a focus-lost event, and a run that carried on inside an
# iconified window would be over by the time it was reopened. Read through
# getattr so an older SDL that never defines them degrades to no auto-pause
# rather than to an import-time crash.
FOCUS_LOST_EVENTS = tuple(
    event for event in
    (getattr(pygame, name, None) for name in ("WINDOWFOCUSLOST", "WINDOWMINIMIZED"))
    if event is not None
)

# The dash: a stretch of invincibility earned by clearing obstacles, during which
# the world speeds up and anything in the way gets flattened instead of fatal.
# Mario's starman, with the score standing in for the item box.
#
# Smashed obstacles count for score *and* toward the next dash, which on its own
# would chain: a dash smashes enough to pay for the next one. The cooldown is
# what stops that, measured from the end of the last dash, so two dashes are
# always a real stretch of ordinary running apart.
DASH_EVERY = 20  # points for the first one
# And more for each one after it. The cooldown alone kept dashes from chaining
# but not from staying cheap: once the speed is up, twenty points come round
# quickly, and a reward that arrives on a fixed tariff stops being a reward.
# Additive rather than multiplied so the bar's pace degrades gently and the
# fourth dash is still reachable -- 20, 35, 50, 65 rather than 20, 30, 45, 68.
DASH_EVERY_STEP = 15
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
# nor the hold, and it never fails to find an exit.
#
# That saturation is only true *at* top speed, which is what made the screen
# clause a separate rule rather than a consequence of this one: at half the ramp
# the clearance stops around x=213, leaving most of the canvas free for an
# obstacle to be standing in when the dash ends. See exit_is_clear.
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
# and the next thing is the player's problem. Three seconds until the next
# obstacle appears at the right edge, and then the width of the canvas again
# before it arrives, which is the breather the boost was borrowing against.
#
# The hush is only half of that promise: it stops the world spawning, and cannot
# take away what is already on the canvas. The other half is the exit check,
# which is why that waits for an empty screen and not only for room to react.
DASH_RECOVERY = 3.0

# The warning starts before the dash does, not at the moment it ends: by then
# the player has no time left to do anything with it. "GET READY" rides the last
# stretch of the dash's clock, and the countdown then runs through the breather,
# so the handover is one piece of information rather than an event to be caught.
# Three seconds of breather, three numbers, one each.
#
# It rides the clock and not the dash, which are the same thing only until the
# clock runs out: past that the dash is still up, waiting for the screen to
# clear, and there is nothing left for the player to get ready with. The words
# stop at zero -- see draw_hud, which is also where the wait used to freeze them.
DASH_OVER_PROMPT = "GET READY"
DASH_COUNTDOWN_FROM = 3

# Everything above pulses rather than blinking or growing once. A blink is only
# visible if you happened to be looking when it started; a single grow is over
# before a glance lands. A pulse is always mid-pulse, so it reads as urgent
# whenever you look at it. Sizes are whole font scales, so the pulse is a swell
# to the big one and a settle back to the small -- integer steps are all this
# font has, and a two-step beat is enough to read as breathing.
PULSE_BEAT = 0.5      # seconds per swell
PULSE_SWELL = 0.35    # fraction of the beat spent at the larger size
PROMPT_SCALES = (2, 3)     # words: settle, swell
COUNT_SCALES = (4, 5)      # a single digit can afford to be enormous

# Telling the player what a dash is for. Two words over the sky for the first
# stretch of it, then out of the way -- long enough to be read on the first dash
# of a first run, short enough not to sit on top of the game after that.
DASH_PROMPT = "SMASH THROUGH"
DASH_PROMPT_SECONDS = 2.5

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


def hotkey_line() -> str:
    """The title screen's bottom row.

    Built from the bindings rather than written out, so the screen cannot go on
    offering a key after the key has gone. In a browser that is exactly what
    would happen: no quit is bound there, and a prompt for one is a promise the
    game has no way to keep.
    """
    hints = ["M - MENU"]
    if QUIT_KEYS:
        hints.append("Q - QUIT")
    return "   ".join(hints)


def pulse_scale(elapsed: float, scales=PROMPT_SCALES) -> int:
    """Swell to the larger size at the top of each beat, settle back after."""
    small, big = scales
    return big if (elapsed % PULSE_BEAT) < PULSE_BEAT * PULSE_SWELL else small


class Game:
    def __init__(self):
        self.rng = random.Random()
        # Before set_mode, which is when the window is created and when SDL
        # takes the icon it will wear. Set afterwards it is a change to a window
        # that already exists, which some window managers pick up and some do
        # not. Skipped in a browser: the tab's icon comes from the page, and the
        # window this would dress does not exist there.
        if not storage.BROWSER:
            pygame.display.set_icon(icon.build())
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
        self.pointer_jump = False
        self.pointer_duck = False
        self.dashes_taken = 0
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
        self.pointer_jump = False
        self.pointer_duck = False
        self.dashes_taken = 0

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

    @property
    def dash_target(self) -> int:
        """Points needed for the next dash. Grows with each one taken."""
        return DASH_EVERY + DASH_EVERY_STEP * self.dashes_taken

    def start_dash(self) -> None:
        self.dashes_taken += 1
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
        """Whether the dash may hand the run back: room to react, and an empty
        screen to read the countdown over.

        "Ahead" means anything not yet fully behind the player, not just
        anything past their nose. The difference is one frame wide and it was a
        death: an obstacle reaching the player stopped counting as ahead at the
        same tick it started counting as a collision.

        The canvas width is the second half of the rule, and it is not the same
        statement as the reaction clearance. That clearance is a length of time,
        so it shrinks with the speed: at top speed it already reaches past the
        right-hand edge, but at half the ramp it stops short of it and the dash
        would end with an obstacle plainly standing there -- which then walked
        into the player around a second and a half later, while the breather's
        countdown was still on the screen saying the run had not resumed.
        Measured before this clause existed: 47 of 400 dashes, arriving as early
        as 1.48s into a 3s breather.

        Waiting for the screen instead costs a fraction of a second, because the
        wait is spent still dashing and still smashing while nothing more spawns,
        so the canvas can only drain. Over the same 400 dashes, spread along the
        speed ramp: the hold goes from a mean of 0.20s and a worst of 0.83s to
        0.30s and 1.47s, none of them ends with anything on screen, and none of
        them fails to find an exit.
        """
        left, _, width, _ = self.player.hitbox()
        front = left + width
        reach = max(DASH_EXIT_CLEARANCE * self.world.speed, world.WIDTH)
        return not any(
            not ob.launched and ob.x + ob.w > left and ob.x < front + reach
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
            # Clicking away mid-run is not a decision to keep running. Note what
            # it does *not* do: resume on focus regained. Coming back to a window
            # that is already moving drops the player into whatever arrived while
            # they were gone, which is the same unavoidable death the dash
            # handover exists to prevent. The overlay already says "P RESUME",
            # so leaving is automatic and returning is deliberate.
            if event.type in FOCUS_LOST_EVENTS and self.state == PLAYING:
                self.paused = True
                continue
            if self.handle_pointer(event):
                continue
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

    # -- pointer ----------------------------------------------------------

    def canvas_point(self, event):
        """Where a pointer event landed, in canvas pixels, or None.

        Touches arrive normalised to 0..1 and mouse events in window pixels, and
        the two need different arithmetic to reach the same place. Normalised is
        the easier of the two in a browser, where CSS decides how big the canvas
        is drawn and the window size is no guide at all.
        """
        if event.type in (pygame.FINGERDOWN, pygame.FINGERUP):
            return event.x * world.WIDTH, event.y * world.HEIGHT
        width, height = self.screen.get_size()
        if not width or not height:
            return None
        x, y = event.pos
        return x * world.WIDTH / width, y * world.HEIGHT / height

    def handle_pointer(self, event) -> bool:
        """Returns whether the event was a pointer one, handled or not."""
        mouse = event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)
        finger = event.type in (pygame.FINGERDOWN, pygame.FINGERUP)
        if not (mouse or finger):
            return False
        # The synthesised twin of a real touch. Dropped rather than acted on, so
        # a phone gets one press per press.
        if mouse and getattr(event, "touch", False):
            return True

        if event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
            # A finger has no buttons to tell apart, so it lets go of both. A
            # mouse releases only the one it is releasing, which is what lets a
            # player hold both at once and have the release of one leave the
            # other alone.
            if finger or event.button == MOUSE_JUMP_BUTTON:
                self.pointer_jump = False
            if finger or event.button == MOUSE_DUCK_BUTTON:
                self.pointer_duck = False
            return True

        point = self.canvas_point(event)
        if point is None:
            return True
        x, y = point

        if self.state == PLAYING:
            # The hotkey row is a row of buttons before it is anything else, and
            # it works paused as well as running -- being unable to reach "menu"
            # while paused would be a corner with no way out of it on a phone.
            if not mouse or event.button == MOUSE_JUMP_BUTTON:
                action = self.hud_button_at(x, y)
                if action == "pause":
                    self.paused = not self.paused
                    return True
                if action == "menu":
                    self.go_to_menu()
                    return True
                if action == "retry":
                    self.start_run()
                    return True
                if self.paused:
                    # Anything else while paused resumes and is spent doing it.
                    # A press that both resumed and jumped would be a jump the
                    # player never saw coming.
                    self.paused = False
                    return True
            if not self.paused:
                self.press_in_play(event, mouse, y)
            return True
        # Everywhere else is a menu, and menus take the button a menu takes.
        if mouse and event.button != MOUSE_JUMP_BUTTON:
            return True
        if self.state == MENU:
            self.menu_point(x, y)
        elif self.state == TITLE:
            # The hint line that names the menu key doubles as the way there
            # without one. A phone has no keyboard at all, so without this the
            # character select is simply unreachable on the web build.
            if self.on_text_row(y, TITLE_MENU_ROW):
                self.go_to_menu()
            else:
                self.start_run()
        elif self.state == GAME_OVER and self.over_timer >= GAME_OVER_LOCKOUT:
            # Checked before the catch-all, which is every other pixel of this
            # screen and means "carry on".
            if self.over_menu_hit(x, y):
                self.go_to_menu()
            else:
                self.go_to_title()
        return True

    def press_in_play(self, event, mouse: bool, y: float) -> None:
        """A press during a run, which is the only place the two devices differ.

        A mouse has buttons and a finger has a position, so each is asked the
        question it can answer. Reading a mouse by height would make the two
        actions depend on where the cursor happened to be resting, which is not
        something a mouse player is thinking about; reading a finger by button
        is not possible at all.
        """
        if mouse:
            wants_duck = event.button == MOUSE_DUCK_BUTTON
            if not wants_duck and event.button != MOUSE_JUMP_BUTTON:
                return  # a middle click or a thumb button means nothing here
        else:
            wants_duck = y >= POINTER_DUCK_FROM
        if wants_duck:
            self.pointer_duck = True
        else:
            self.pointer_jump = True
            self.jump_buffer = JUMP_BUFFER

    def menu_point(self, x: float, y: float) -> None:
        """A press on the select screen: pick a row, an arrow, or start."""
        if y >= MENU_START_FROM:
            self.menu_key(CONFIRM_KEYS[0])
            return
        for row in MENU_ROWS:
            top = self.MENU_TOP + row * self.MENU_PITCH
            if not self.on_text_row(y, top):
                continue
            self.row = row
            # Left of the value means the "<" side of it, right means ">". The
            # midpoint is the value's own centre, so the arrows are what the
            # player is aiming at either way.
            printed = f"< {self.row_value(row)} >"
            middle = self.MENU_VALUE_X + pixelfont.text_width(printed) / 2
            if x >= self.MENU_LABEL_X:
                self.menu_key(RIGHT_KEYS[0] if x >= middle else LEFT_KEYS[0])
            return

    def row_value(self, row: int) -> str:
        """The option under the cursor on that row, spelled as it is printed."""
        option = self.row_options(row)[self.picks[row]]
        return option if isinstance(option, str) else option.name

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
        holding_jump = any(keys[k] for k in JUMP_KEYS) or self.pointer_jump
        ducking = any(keys[k] for k in DUCK_KEYS) or self.pointer_duck
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

        # Contact is resolved before the dash is allowed to expire, and the order
        # is the whole point. An obstacle stops blocking the exit at the exact
        # instant it starts touching the player -- the exit check looks ahead, and
        # something touching you is no longer ahead of you -- so ending the dash
        # first handed the collision to a player who had been invincible one line
        # earlier. Reproducible at every sub-frame offset of the crossing tick,
        # and worst on the last obstacle of a dash, which is the one the exit
        # hold was waiting on.
        struck = self.world.hits(self.player.hitbox())
        if struck:
            if not self.dashing:
                self.end_run()
                return
            for ob in struck:
                if not ob.scored:
                    self.award(world.points_for(ob))
                self.world.launch(ob)
                # At the obstacle, not on the ground under it. A smashed flyer
                # used to puff at floor level, a body-length below where it was
                # hit.
                self.puffs.burst(ob.x + ob.w / 2, ob.y + ob.h, True)
            # One of each per frame, however many were struck: a cluster is one
            # impact to the player, and stacked hit-stop would read as a hang.
            self.freeze = SMASH_FREEZE
            self.shake = len(SMASH_SHAKE)
            sfx.play("smash")

        if self.dashing:
            self.dash_left = max(0.0, self.dash_left - dt)
            if self.dash_left > 0.0:
                self.world.gap_scale = DASH_WARN_GAP_SCALE if self.dash_ending else 1.0
            else:
                # The clock is spent and the dash is only waiting for the screen
                # to clear, so the breather's hush starts here rather than at the
                # end of the wait. Anything spawned during the wait is by
                # definition still on the canvas when the dash ends, and so is
                # one more thing to wait for: left spawning, the wait fed itself
                # and ran to 5.15s at the bottom of the speed ramp, longer than
                # the dash. Silenced, the canvas can only drain, and the wait is
                # bounded by what it takes the far edge to cross the screen.
                # Re-armed every frame on purpose: the hush is a countdown, and
                # this is the phase that must not let it reach the end.
                self.world.hush(DASH_RECOVERY)
                if self.exit_is_clear():
                    self.end_dash()
        else:
            self.recovery = max(0.0, self.recovery - dt)
            self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
            if self.toward_dash >= self.dash_target and self.dash_cooldown <= 0.0:
                self.start_dash()

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

        def blit_accessory():
            facings = sheet.accessory[accessory_frame]
            dy, placements = character.accessory_anchors[frame]
            for dx, flipped in placements:
                self.canvas.blit(facings[flipped], (left + dx, top + dy))

        wears = character.accessory is not None
        if wears and not character.accessory.in_front:
            blit_accessory()
        self.canvas.blit(sheet.poses[frame], pos)
        if wears and character.accessory.in_front:
            blit_accessory()

    PULSE_MIDDLE = 41  # the row a pulsing prompt is centred on

    def pulsed(self, line: str, elapsed: float, scales, ink, halo) -> None:
        """A prompt that swells in place on the beat.

        Centred by hand because text is drawn from its top left, so a line that
        changed size would otherwise sink down the screen as it grew instead of
        breathing around one point.
        """
        scale = pulse_scale(elapsed, scales)
        self.text(line, self.PULSE_MIDDLE - pixelfont.GLYPH_H * scale // 2,
                  ink, halo, scale)

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
    HUD_ROW = 6

    def score_line(self) -> str:
        """The top-left text. Also sets how wide the meter under it is drawn."""
        if self.highscore:
            return f"HI {self.highscore:04d}  {self.score:04d}"
        return f"{self.score:04d}"

    def hud_buttons(self):
        """(action, x, width) for each hotkey on the HUD line, right-aligned.

        The same arithmetic draws the line and decides what a press on it hits,
        so a label cannot end up somewhere other than the thing it names. That
        matters more than it looks: on a phone this row is the only way to pause,
        retry or reach the menu, because there is no keyboard to press.
        """
        line = (" " * HUD_BUTTON_GAP).join(label for label, _ in HUD_BUTTONS)
        x = world.WIDTH - pixelfont.text_width(line) - self.HUD_MARGIN
        spans = []
        for label, action in HUD_BUTTONS:
            spans.append((action, x, pixelfont.text_width(label)))
            x += (len(label) + HUD_BUTTON_GAP) * pixelfont.ADVANCE
        return line, spans

    def on_text_row(self, y: float, row: int) -> bool:
        """Whether a press landed on the line of text drawn at `row`.

        One band for all of them, because they had drifted apart. The title
        screen's was written as `abs(y - row) <= PAD + GLYPH_H`: twice as tall
        as the others and centred on the row rather than starting at it, so it
        reached up and swallowed the hint line above -- pressing "S - DUCK"
        opened the menu instead of starting a run.
        """
        return row - MENU_HIT_PAD <= y < row + pixelfont.GLYPH_H + MENU_HIT_PAD

    def over_menu_hit(self, x: float, y: float) -> bool:
        """Whether a press landed on the game-over banner's menu button."""
        width = pixelfont.text_width(OVER_MENU_LABEL)
        left = (world.WIDTH - width) // 2
        return (left - MENU_HIT_PAD <= x < left + width + MENU_HIT_PAD
                and self.on_text_row(y, OVER_MENU_ROW))

    def hud_button_at(self, x: float, y: float):
        """Which HUD hotkey a press landed on, if any."""
        if not self.on_text_row(y, self.HUD_ROW):
            return None
        for action, left, width in self.hud_buttons()[1]:
            if left <= x < left + width:
                return action
        return None

    def draw_hud(self, ink, halo) -> None:
        self.text(self.score_line(), self.HUD_ROW, ink, halo, x=self.HUD_MARGIN)

        if self.state == PLAYING:
            line, spans = self.hud_buttons()
            self.text(line, self.HUD_ROW, ink, halo, x=spans[0][1])
            self.draw_dash_meter(ink, halo)
            if self.paused:
                self.text("PAUSED", 34, ink, halo, 2)
                self.text("P  RESUME", 52, ink, halo)
            elif self.dashing:
                # Timed off the dash's own clock, not the global tick: phased
                # against the tick, a prompt starts wherever it happens to land.
                elapsed = DASH_SECONDS - self.dash_left
                if self.dash_ending and self.dash_left > 0.0:
                    # The handover begins while the dash is still up, so the
                    # warning arrives with time left to act on it -- and it goes
                    # when that time does. Past zero the dash is only waiting for
                    # the screen to clear, which is not something the player has
                    # anything to do about, and the beat this pulses on is
                    # measured from the same clock: stopped, it froze the words
                    # at their swollen size for the whole of the wait.
                    self.pulsed(DASH_OVER_PROMPT,
                                DASH_WARN_SECONDS - self.dash_left, PROMPT_SCALES,
                                ink, halo)
                elif elapsed < DASH_PROMPT_SECONDS:
                    self.pulsed(DASH_PROMPT, elapsed, PROMPT_SCALES, ink, halo)
            elif self.recovery > 0.0:
                # Then the countdown, straight on from the warning, over an
                # empty screen. Everything else about the ending was a change in
                # something -- the strobe stopping, the meter going, the speed
                # dropping -- and a player who was not watching for a change does
                # not see one. A number counting down is a state, not a change.
                left = min(DASH_COUNTDOWN_FROM,
                           int(self.recovery / DASH_RECOVERY * DASH_COUNTDOWN_FROM) + 1)
                self.pulsed(str(left), DASH_RECOVERY - self.recovery,
                            COUNT_SCALES, ink, halo)
        elif self.state == TITLE:
            self.text(self.character.name, 20, ink, halo, 2)
            self.text("SPACE OR W - JUMP", 38, ink, halo)
            self.text("JUMP AGAIN IN AIR TO DOUBLE", 47, ink, halo)
            self.text("S - DUCK   A/D - SHIFT", 56, ink, halo)
            self.text(hotkey_line(), TITLE_MENU_ROW, ink, halo)
        elif self.state == GAME_OVER:
            self.text("GAME OVER", 30, ink, halo, 2)
            self.text(f"SCORE {self.score:04d}", 50, ink, halo)
            if self.over_timer >= GAME_OVER_LOCKOUT:
                self.text("ANY KEY TO CONTINUE", 62, ink, halo)
                self.text(OVER_MENU_LABEL, OVER_MENU_ROW, ink, halo)

    # A plain list with a cursor, in the shape every pixel-era option screen
    # used. The chosen character stands below it in the chosen scene, so the
    # menu previews both without needing a swatch for either.
    MENU_LABEL_X = 76
    MENU_VALUE_X = 158
    MENU_TOP = 40
    MENU_PITCH = 11

    DASH_METER_MIN = 48
    DASH_METER_Y = 16
    DASH_ICON_BLINK = 8

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
            owed = min(1.0, self.toward_dash / self.dash_target)
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
        # A bolt, because an unlabelled bar in the corner of a first run is just
        # a bar. It flashes once the bar is full and stays lit through the dash,
        # so one cycle teaches what the bar counts towards with no tutorial.
        ready = self.dashing or filled >= 1.0
        if not ready or (self.tick // self.DASH_ICON_BLINK) % 2 == 0:
            pixelfont.draw(self.canvas, "*", x + 1, y - 1, halo)
            pixelfont.draw(self.canvas, "*", x, y - 2, ink)
        x += pixelfont.GLYPH_W + 3
        # The bar runs to the far end of the score above it, so the two line up
        # at both margins and read as one block rather than two left-aligned
        # things of unrelated length. The floor is for a first-ever run, where
        # there is no high score yet and the line is only four digits wide.
        span = max(self.DASH_METER_MIN,
                   self.HUD_MARGIN + pixelfont.text_width(self.score_line()) - x)
        self.canvas.fill(halo, (x, y + 1, span, 2))
        self.canvas.fill(ink, (x, y, span, 1))
        width = round(span * max(0.0, min(1.0, filled)))
        if width:
            self.canvas.fill(ink, (x, y, width, 2))

    def draw_menu(self, step, ink, halo) -> None:
        self.text("MOCHI DASH", 16, ink, halo, 2)

        for i, label in enumerate(("CHARACTER", "SCENE", "SOUND")):
            value = self.row_value(i)
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
