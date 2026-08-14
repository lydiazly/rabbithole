"""Drives the real game loop and draws every frame.

The rest of the suite tests decisions -- what should score, how far a jump
reaches, when a dash may end. None of it draws anything, so until this existed
every rendering path in the game was covered only by running the game and
looking at it: `draw`, the HUD, the menu, the scenery, the character blitter and
the whole of the pixel font could raise on any frame and the suite stayed green.

It asserts coverage rather than appearance -- that every pose, every accessory
frame, every character, every scene and every step of the day/night ramp was
actually put on the canvas. What each one looks like is a question for eyes.
"""

import random

import pytest

import pygame

from mochi_dash import characters, scenes, sprites, storage
from mochi_dash import main as m
from mochi_dash import player as pl
from mochi_dash import world as wd
from mochi_dash.palette import STEPS, step_at


class Held(dict):
    """pygame's key state is a sequence of every scancode; this fakes it."""

    def __getitem__(self, key):
        return self.get(key, False)


@pytest.fixture
def game(tmp_path, monkeypatch):
    """A real Game on a dummy display, with its own throwaway high-score file."""
    pygame.init()
    monkeypatch.setattr(storage, "FILE", tmp_path / ".highscore")
    held = Held()
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: held)
    instance = m.Game()
    # `Game` seeds itself from the clock, which makes every assertion here a
    # coin toss: what gets spawned decides what gets drawn and when the player
    # dies. Seeded, so a failure is a real one and can be reproduced.
    instance.rng.seed(20250812)
    instance.held = held  # so a test can hold keys down
    return instance


def test_every_screen_draws(game):
    """Menu, title, playing and game over, plus moving the menu cursor.

    Each is a separate branch of `draw`, and three of them are only ever seen
    for a few seconds, which is exactly when a crash goes unnoticed until it is
    in front of a player.
    """
    game.draw()  # the character select, where a run starts
    for _ in range(len(characters.CHARACTERS) + 1):
        game.menu_key(m.RIGHT_KEYS[0])
        game.update(m.DT)
        game.draw()
    for row in m.MENU_ROWS:
        game.row = row
        game.menu_key(m.RIGHT_KEYS[0])
        game.draw()

    game.go_to_title()
    game.draw()
    game.start_run()
    game.draw()

    game.paused = True
    game.draw()
    game.paused = False

    game.end_run()
    assert game.state == m.GAME_OVER
    for _ in range(int(m.GAME_OVER_HOLD / m.DT) + 2):
        game.update(m.DT)
        game.draw()
    assert game.state == m.TITLE, "the game-over screen never handed back"


def test_a_played_run_exercises_every_pose_and_face(game):
    """Random input for a while, drawing every frame.

    Random rather than scripted because the point is to reach states no test
    author thought to name -- the second jump landing during a duck, a death
    mid-air. The assertions are on what got drawn, not on what happened.
    """
    # A character with ears, so the idle twitch is drawn at all: the default has
    # none, and the accessory frame is pinned at 0 for a character without one.
    game.character = characters.COCO
    game.start_run()
    rng = random.Random(7)
    seen = {"poses": set(), "ears": set(), "air_jumps": 0}

    for _ in range(60 * 45):
        game.held.clear()
        roll = rng.random()
        # Sparse on purpose: the idle breathe alternates only while the player
        # is standing still, so a constantly-input run never draws `round_b`.
        if roll < 0.12:
            game.held[m.JUMP_KEYS[0]] = True
            if game.state == m.PLAYING:
                game.jump_buffer = m.JUMP_BUFFER
        elif roll < 0.20:
            game.held[m.DUCK_KEYS[0]] = True
        elif roll < 0.24:
            game.held[m.LEFT_KEYS[1]] = True
        elif roll < 0.28:
            game.held[m.RIGHT_KEYS[1]] = True

        before = game.player.jumps_used
        game.update(m.DT)
        game.draw()
        if before == 1 and game.player.jumps_used == 2:
            seen["air_jumps"] += 1
        seen["poses"].add(game.player.frame)
        seen["ears"].add(game.accessory_frame(
            game.character, game.player.accessory_ticks, game.player.idle))

        if game.state == m.GAME_OVER:
            # The death pose only exists here, so it has to be sampled here.
            for _ in range(30):
                game.update(m.DT)
                game.draw()
                seen["poses"].add(game.player.frame)
            game.start_run()

    # Then a stretch of standing still. The resting breathe only alternates
    # after IDLE_TICKS uninterrupted idle frames, and random input effectively
    # never produces a run of those, so it has to be asked for. Collision is off
    # for it: the subject is the animation, not surviving a second of it.
    game.state = m.PLAYING
    game.player.reset()
    game.world.hits = lambda box: []
    game.held.clear()
    for _ in range(pl.IDLE_TICKS * 4):
        game.update(m.DT)
        game.draw()
        seen["poses"].add(game.player.frame)

    assert seen["air_jumps"] > 0, "the mid-air second jump never fired"
    assert seen["ears"] == set(range(len(sprites.EAR_LEFT))), seen["ears"]
    missing = set(sprites.SLIME_POSES) - seen["poses"]
    assert not missing, f"never drawn: {sorted(missing)}"


def test_the_late_game_draws_flyers_night_and_a_dash(game):
    """Top speed, every character, both scenes, the whole day/night ramp.

    Reaching any of this by playing takes minutes and surviving, so collision is
    switched off: the subject is the drawing, not the difficulty.
    """
    game.start_run()
    game.world.hits = lambda box: []
    seen = {"steps": set(), "chars": set(), "scenes": set(),
            "flyers": 0, "dash_frames": 0}
    rotate = 60 * 12

    for frame in range(60 * 120):
        cast = characters.CHARACTERS
        game.character = cast[(frame // rotate) % len(cast)]
        game.scene = scenes.SCENES[(frame // (rotate * len(cast))) % len(scenes.SCENES)]
        game.world.scene = game.scene

        game.held.clear()
        if frame % 37 == 0:
            game.held[m.JUMP_KEYS[0]] = True
            if game.player.on_ground:
                game.jump_buffer = m.JUMP_BUFFER
        elif frame % 53 == 0:
            game.held[m.DUCK_KEYS[0]] = True

        game.update(m.DT)
        game.draw()
        seen["steps"].add(step_at(game.world.phase))
        seen["chars"].add(game.character.key)
        seen["scenes"].add(game.scene.key)
        seen["flyers"] += sum(1 for ob in game.world.obstacles if ob.kind == "flyer")
        seen["dash_frames"] += game.dashing

    assert game.world.speed == wd.SPEED_MAX, "never reached top speed"
    assert seen["flyers"] > 0, "no flying obstacle was ever drawn"
    assert seen["dash_frames"] > 0, "the dash never drew"
    assert seen["chars"] == {c.key for c in characters.CHARACTERS}
    assert seen["scenes"] == {s.key for s in scenes.SCENES}
    assert seen["steps"] == set(range(STEPS)), (
        f"day/night steps never drawn: {sorted(set(range(STEPS)) - seen['steps'])}"
    )


def test_the_dash_handover_draws_end_to_end(game):
    """Prompt, warning, countdown and the smashing in between.

    All four are short, conditional and mutually exclusive, which is the shape
    of code that gets broken without anybody noticing.
    """
    game.start_run()
    game.world.speed = wd.SPEED_MAX
    game.start_dash()
    prompts = 0
    for _ in range(int((m.DASH_SECONDS + m.DASH_RECOVERY + 1.0) / m.DT)):
        game.held.clear()
        game.update(m.DT)
        game.draw()
        prompts += game.dashing or game.recovery > 0.0
    assert prompts > 0
    assert not game.dashing and game.recovery == 0.0, "the handover never finished"


def test_the_warning_stops_when_the_clock_does_rather_than_hanging(game, monkeypatch):
    """"GET READY" is only worth saying while there is time left to act on it.

    Once the clock is spent the dash stays up until the screen clears, and the
    prompt was drawn through the whole of that wait -- frozen, as it happens,
    because the beat it pulses on is measured from the clock, and the clock had
    stopped: `DASH_WARN_SECONDS - 0.0` is the same number every frame, so it sat
    at the swollen size for as long as the wait lasted. Held up to 1.47s, saying
    something was about to happen while it did not.
    """
    drawn = []
    real = m.Game.pulsed

    def record(self, line, elapsed, scales, ink, halo):
        drawn.append((self.dash_left if self.dashing else None, line))
        real(self, line, elapsed, scales, ink, halo)

    monkeypatch.setattr(m.Game, "pulsed", record)

    # Mid-ramp, and an obstacle far enough out that the exit has to wait for it.
    game.start_run()
    game.world.speed = wd.SPEED_START + wd.SPEED_RANGE * 0.3
    game.start_dash()
    game.world.hush(99.0)
    w, h = wd.SMALL_BOX
    game.world.obstacles = [
        wd.Obstacle(wd.WIDTH - w - 1.0, wd.GROUND_Y - h, w, h, "small")
    ]
    game.dash_left = m.DASH_WARN_SECONDS * 0.5  # part-way into the warning

    waited = 0.0
    while game.dashing and waited < 10.0:
        game.held.clear()
        game.update(m.DT)
        game.draw()
        if game.dashing and game.dash_left <= 0.0:
            waited += m.DT
    assert waited > m.DT * 3, "the exit never had to wait, so nothing was proved"

    warned = [left for left, line in drawn if line == m.DASH_OVER_PROMPT]
    assert warned, "the warning never appeared at all"
    assert all(left > 0.0 for left in warned), (
        f"the warning was still on screen with the clock at zero: {warned[-3:]}"
    )
