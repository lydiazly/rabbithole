"""Mouse and touch: the only input a phone opening the web build has.

Every assertion here is about a device this machine does not have, so the events
are posted by hand. That is the honest limit of it: the shape of the handling is
tested, a real finger on a real phone is not.
"""

import pytest

import pygame

from mochi_dash import characters, storage
from mochi_dash import main as m
from mochi_dash import world as wd


@pytest.fixture
def game(tmp_path, monkeypatch):
    pygame.init()
    monkeypatch.setattr(storage, "FILE", tmp_path / "highscore")

    class Held(dict):
        def __getitem__(self, key):
            return self.get(key, False)

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: Held())
    pygame.event.clear()
    return m.Game()


def click(game, x, y, down=True, touch=False):
    """A mouse press at a canvas coordinate, delivered through the real path."""
    width, height = game.screen.get_size()
    pos = (x * width / wd.WIDTH, y * height / wd.HEIGHT)
    kind = pygame.MOUSEBUTTONDOWN if down else pygame.MOUSEBUTTONUP
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(kind, pos=pos, button=1, touch=touch))
    game.handle_events()


def tap(game, x, y, down=True):
    """A finger, whose coordinates arrive normalised rather than in pixels."""
    kind = pygame.FINGERDOWN if down else pygame.FINGERUP
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(
        kind, x=x / wd.WIDTH, y=y / wd.HEIGHT, finger_id=1, touch_id=1))
    game.handle_events()


def test_pressing_high_jumps_and_pressing_low_ducks(game):
    game.start_run()
    click(game, 150, 20)
    assert game.jump_buffer == m.JUMP_BUFFER
    assert game.pointer_jump and not game.pointer_duck

    click(game, 150, 20, down=False)
    assert not game.pointer_jump

    game.jump_buffer = 0.0
    click(game, 150, wd.HEIGHT - 4)
    assert game.pointer_duck and not game.pointer_jump
    assert game.jump_buffer == 0.0, "a press meant to duck also jumped"


def test_a_held_press_gives_a_full_jump_and_a_tap_gives_a_hop(game):
    """The jump is variable-height, and a finger has to reach both halves of
    that or a phone can only ever manage the smallest hop.
    """
    def rise(hold_frames):
        game.start_run()
        game.world.hits = lambda box: []
        click(game, 150, 20)
        best = 0.0
        for frame in range(60):
            if frame == hold_frames:
                click(game, 150, 20, down=False)
            game.update(m.DT)
            best = max(best, wd.GROUND_Y - game.player.y)
        return best

    tapped, held = rise(1), rise(40)
    assert held > tapped * 2, (tapped, held)


def test_a_touch_is_not_counted_twice(game):
    """SDL turns a touch into a mouse event as well, so a phone delivers each
    tap through both paths. The synthesised one carries a flag; acting on both
    would double every press.
    """
    game.start_run()
    seen = []
    game.start_run = lambda: seen.append(1)

    game.state = m.TITLE
    click(game, 150, 40, touch=True)   # the synthesised twin
    assert seen == [], "acted on the synthesised mouse event"

    tap(game, 150, 40)                 # the real touch
    assert seen == [1]


def test_the_title_screen_can_reach_the_menu_without_a_keyboard(game):
    """A phone has no M key, and the character select is behind it.

    The hint line that names the key is the target, so the thing you would press
    if you were looking for it is the thing that works.
    """
    game.go_to_title()
    click(game, 150, m.TITLE_MENU_ROW + 2)
    assert game.state == m.MENU

    game.go_to_title()
    click(game, 150, 30)
    assert game.state == m.PLAYING, "pressing elsewhere should still start a run"


def test_the_title_and_the_banner_take_a_press(game):
    game.go_to_title()
    click(game, 150, 30)
    assert game.state == m.PLAYING

    game.end_run()
    click(game, 150, 50)
    assert game.state == m.GAME_OVER, "the banner was dismissed inside the lockout"
    game.over_timer = m.GAME_OVER_LOCKOUT
    click(game, 150, 50)
    assert game.state == m.TITLE


def test_a_press_does_nothing_while_paused(game):
    game.start_run()
    game.paused = True
    click(game, 150, 20)
    assert game.jump_buffer == 0.0 and not game.pointer_jump


def test_the_menu_picks_the_row_and_the_arrow_under_the_press(game):
    game.go_to_menu()
    scene_row_y = m.Game.MENU_TOP + m.SCENE_ROW * m.Game.MENU_PITCH

    click(game, m.Game.MENU_LABEL_X, scene_row_y)
    assert game.row == m.SCENE_ROW, "pressing a row did not select it"

    before = game.picks[m.CHARACTER_ROW]
    char_row_y = m.Game.MENU_TOP + m.CHARACTER_ROW * m.Game.MENU_PITCH
    click(game, wd.WIDTH - 8, char_row_y)          # the ">" side
    assert game.row == m.CHARACTER_ROW
    assert game.picks[m.CHARACTER_ROW] == (before + 1) % len(characters.CHARACTERS)

    click(game, m.Game.MENU_VALUE_X, char_row_y)   # the "<" side
    assert game.picks[m.CHARACTER_ROW] == before


def test_pressing_below_the_menu_starts_the_game(game):
    game.go_to_menu()
    click(game, 150, m.MENU_START_FROM + 2)
    assert game.state == m.TITLE


def test_releasing_anywhere_lets_go(game):
    """A release outside the zone it was pressed in must still end the press,
    or a finger dragged up the screen leaves the character crouched forever.
    """
    game.start_run()
    click(game, 150, wd.HEIGHT - 4)
    assert game.pointer_duck
    click(game, 150, 4, down=False)
    assert not game.pointer_duck and not game.pointer_jump


def test_the_duck_half_is_the_character_and_the_ground_and_no_more():
    """The line is the standing crown, so the sky jumps and the character ducks.

    Written as a fraction of the canvas it would be a coincidence rather than a
    rule: two thirds lands on the same row today and would stop meaning anything
    the moment a pose changed height. What has to hold is that pressing the sky
    jumps -- the commonest action, and the biggest target -- and that the duck
    half stays large enough to hit with a thumb.
    """
    from mochi_dash import sprites

    standing = wd.GROUND_Y - sprites.POSE_SIZES["round"][1]
    assert m.POINTER_DUCK_FROM == standing

    sky = m.POINTER_DUCK_FROM
    duck_band = wd.HEIGHT - m.POINTER_DUCK_FROM
    assert sky > duck_band, "the commonest press has the smaller target"
    assert duck_band > wd.HEIGHT - wd.GROUND_Y, (
        "the duck half is no bigger than the ground strip, which is too small "
        "to hit on a phone"
    )
