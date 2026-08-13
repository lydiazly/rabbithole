"""Key dispatch: which key does what, on which screen.

`handle_events` is a flat chain of elifs whose order carries most of the meaning
-- quit before everything, pause before the keys pause is meant to suppress --
and nothing else in the suite exercises it, so the whole of it could be reordered
without a test noticing.
"""

import pytest

import pygame

from mochi_dash import characters, scenes, sfx, storage
from mochi_dash import main as m


@pytest.fixture
def game(tmp_path, monkeypatch):
    pygame.init()
    monkeypatch.setattr(storage, "FILE", tmp_path / ".highscore")

    class Held(dict):
        def __getitem__(self, key):
            return self.get(key, False)

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: Held())
    pygame.event.clear()
    return m.Game()


def press(game, key):
    """Deliver one keypress through the real event path."""
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    return game.handle_events()


def test_quit_works_from_every_screen(game):
    """Including the game-over banner, where any other key means "carry on".

    Quit is checked before the state machine for exactly this reason, so it is
    the one binding that must not depend on where the player is.
    """
    for enter in (game.go_to_menu, game.go_to_title, game.start_run, game.end_run):
        enter()
        for key in m.QUIT_KEYS:
            assert press(game, key) is False, (enter.__name__, key)

    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    assert game.handle_events() is False


def test_the_menu_key_returns_from_anywhere_except_the_menu(game):
    for enter in (game.go_to_title, game.start_run, game.end_run):
        enter()
        assert press(game, m.MENU_KEYS[0]) is True
        assert game.state == m.MENU, enter.__name__


def test_pause_toggles_and_swallows_everything_underneath(game):
    """A paused game that still buffers jumps would unpause into a stale one."""
    game.start_run()
    press(game, m.PAUSE_KEYS[0])
    assert game.paused

    game.jump_buffer = 0.0
    press(game, m.JUMP_KEYS[0])
    assert game.jump_buffer == 0.0, "a jump got through the pause"
    press(game, m.RESTART_KEYS[0])
    assert game.state == m.PLAYING and game.paused, "restart got through the pause"

    press(game, m.PAUSE_KEYS[0])
    assert not game.paused
    press(game, m.JUMP_KEYS[0])
    assert game.jump_buffer > 0.0, "jumping did not come back"


def test_the_title_screen_starts_a_run_and_playing_buffers_a_jump(game):
    game.go_to_title()
    press(game, m.JUMP_KEYS[0])
    assert game.state == m.PLAYING
    game.jump_buffer = 0.0
    press(game, m.JUMP_KEYS[0])
    assert game.jump_buffer == m.JUMP_BUFFER


def test_restart_only_works_while_playing(game):
    game.start_run()
    game.score = 99
    press(game, m.RESTART_KEYS[0])
    assert game.state == m.PLAYING and game.score == 0


def test_game_over_ignores_the_key_that_probably_killed_you(game):
    """The lockout exists because the press is often still in flight: without it
    the banner can be gone before it has been read.
    """
    game.start_run()
    game.end_run()
    press(game, m.JUMP_KEYS[0])
    assert game.state == m.GAME_OVER, "the banner was dismissed instantly"

    game.over_timer = m.GAME_OVER_LOCKOUT
    press(game, m.JUMP_KEYS[0])
    assert game.state == m.TITLE


def test_the_menu_moves_rows_wraps_and_confirms(game):
    game.go_to_menu()
    assert game.row == m.CHARACTER_ROW

    press(game, m.ROW_DOWN_KEYS[0])
    assert game.row == m.SCENE_ROW
    press(game, m.ROW_UP_KEYS[0])
    assert game.row == m.CHARACTER_ROW
    press(game, m.ROW_UP_KEYS[0])
    assert game.row == m.MENU_ROWS[-1], "rows do not wrap"

    game.row = m.CHARACTER_ROW
    for _ in range(len(characters.CHARACTERS)):
        press(game, m.RIGHT_KEYS[0])
    assert game.picks[m.CHARACTER_ROW] == 0, "the cast does not wrap"
    press(game, m.LEFT_KEYS[0])
    assert game.picks[m.CHARACTER_ROW] == len(characters.CHARACTERS) - 1

    press(game, m.PICK_KEYS[1])
    assert game.picks[m.CHARACTER_ROW] == 1

    game.row = m.SCENE_ROW
    press(game, m.RIGHT_KEYS[0])
    assert game.picks[m.SCENE_ROW] == 1 % len(scenes.SCENES)

    press(game, m.CONFIRM_KEYS[0])
    assert game.state == m.TITLE
    assert game.character is characters.CHARACTERS[1]
    assert game.scene is scenes.SCENES[1 % len(scenes.SCENES)]


def test_the_sound_row_actually_switches_the_sound(game):
    game.go_to_menu()
    game.row = m.SOUND_ROW
    press(game, m.RIGHT_KEYS[0])
    assert game.picks[m.SOUND_ROW] == 1
    assert sfx.enabled is False, "picking OFF left the sound on"
    press(game, m.RIGHT_KEYS[0])
    assert sfx.enabled is True


def test_an_unbound_key_changes_nothing(game):
    game.go_to_menu()
    before = (dict(game.picks), game.row, game.state)
    press(game, pygame.K_F13)
    assert (dict(game.picks), game.row, game.state) == before
