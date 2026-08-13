"""Mouse and touch: the only input a phone opening the web build has.

Every assertion here is about a device this machine does not have, so the events
are posted by hand. That is the honest limit of it: the shape of the handling is
tested, a real finger on a real phone is not.
"""

import pytest

import pygame

from mochi_dash import characters, pixelfont, storage
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


def click(game, x, y, down=True, touch=False, button=m.MOUSE_JUMP_BUTTON):
    """A mouse press at a canvas coordinate, delivered through the real path."""
    width, height = game.screen.get_size()
    pos = (x * width / wd.WIDTH, y * height / wd.HEIGHT)
    kind = pygame.MOUSEBUTTONDOWN if down else pygame.MOUSEBUTTONUP
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(kind, pos=pos, button=button, touch=touch))
    game.handle_events()


def tap(game, x, y, down=True):
    """A finger, whose coordinates arrive normalised rather than in pixels."""
    kind = pygame.FINGERDOWN if down else pygame.FINGERUP
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(
        kind, x=x / wd.WIDTH, y=y / wd.HEIGHT, finger_id=1, touch_id=1))
    game.handle_events()


def test_the_mouse_jumps_on_the_left_button_and_ducks_on_the_right(game):
    """A mouse has buttons, so it is asked with buttons rather than by height.

    Height would make the action depend on where the cursor happened to be
    resting, which is not something a mouse player is tracking.
    """
    game.start_run()
    click(game, 150, 20, button=m.MOUSE_JUMP_BUTTON)
    assert game.pointer_jump and not game.pointer_duck
    assert game.jump_buffer == m.JUMP_BUFFER

    game.jump_buffer = 0.0
    # Deliberately in the low half: position must not matter to a mouse.
    click(game, 150, wd.HEIGHT - 4, button=m.MOUSE_DUCK_BUTTON)
    assert game.pointer_duck
    assert game.jump_buffer == 0.0, "the duck button also jumped"

    # And the reverse: the jump button low down still jumps.
    click(game, 150, wd.HEIGHT - 4, button=m.MOUSE_JUMP_BUTTON)
    assert game.jump_buffer == m.JUMP_BUFFER


def test_each_mouse_button_releases_only_itself(game):
    """Both can be held at once, and letting go of one must not free the other."""
    game.start_run()
    click(game, 150, 20, button=m.MOUSE_JUMP_BUTTON)
    click(game, 150, 20, button=m.MOUSE_DUCK_BUTTON)
    assert game.pointer_jump and game.pointer_duck

    click(game, 150, 20, down=False, button=m.MOUSE_JUMP_BUTTON)
    assert not game.pointer_jump and game.pointer_duck, "the right button let go too"
    click(game, 150, 20, down=False, button=m.MOUSE_DUCK_BUTTON)
    assert not game.pointer_duck


def test_a_middle_click_means_nothing(game):
    game.start_run()
    click(game, 150, 20, button=2)
    assert not game.pointer_jump and not game.pointer_duck
    assert game.jump_buffer == 0.0


def test_a_finger_jumps_high_and_ducks_low(game):
    """A finger has no buttons, so it is asked by position instead."""
    game.start_run()
    tap(game, 150, 20)
    assert game.pointer_jump and not game.pointer_duck
    assert game.jump_buffer == m.JUMP_BUFFER

    tap(game, 150, 20, down=False)
    assert not game.pointer_jump

    game.jump_buffer = 0.0
    tap(game, 150, wd.HEIGHT - 4)
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


@pytest.mark.parametrize("row", [38, 47, 56])
def test_the_title_hint_lines_above_the_menu_one_start_a_run(game, row):
    """The menu band must not reach up into the line above it.

    It used to: written as `abs(y - row) <= PAD + GLYPH_H` it was twice as tall
    as every other band and centred on the row rather than starting at it, so a
    press on "S - DUCK" opened the menu instead of starting a run.
    """
    game.go_to_title()
    click(game, 150, row)
    assert game.state == m.PLAYING, f"y={row} was swallowed by the menu band"


def test_every_pressable_line_uses_the_same_band(game):
    """Four call sites, one rule -- which is how the odd one out was found."""
    for row in (m.TITLE_MENU_ROW, m.OVER_MENU_ROW, game.HUD_ROW):
        assert game.on_text_row(row, row), "the row itself must be inside"
        assert game.on_text_row(row + pixelfont.GLYPH_H - 1, row)
        assert not game.on_text_row(row - m.MENU_HIT_PAD - 1, row)
        assert not game.on_text_row(row + pixelfont.GLYPH_H + m.MENU_HIT_PAD, row)
    # And it stays clear of a neighbouring line at the title screen's pitch.
    assert not game.on_text_row(m.TITLE_MENU_ROW - 9, m.TITLE_MENU_ROW)


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


def test_only_the_left_button_works_the_menus(game):
    """Right-clicking a menu means duck, and duck means nothing on a menu.

    Left as "any button confirms", a player crouching as the run ended would
    dismiss the banner with the same press.
    """
    for enter, expected in ((game.go_to_title, m.TITLE), (game.go_to_menu, m.MENU)):
        enter()
        click(game, 150, 30, button=m.MOUSE_DUCK_BUTTON)
        assert game.state == expected, "the right button worked a menu"

    game.start_run()
    game.end_run()
    game.over_timer = m.GAME_OVER_LOCKOUT
    click(game, 150, 50, button=m.MOUSE_DUCK_BUTTON)
    assert game.state == m.GAME_OVER
    click(game, 150, 50, button=m.MOUSE_JUMP_BUTTON)
    assert game.state == m.TITLE


def hud_button(game, action):
    """The centre of one of the HUD hotkey buttons, in canvas pixels."""
    for name, left, width in game.hud_buttons()[1]:
        if name == action:
            return left + width / 2, game.HUD_ROW + 2
    raise AssertionError(f"no {action} button")


@pytest.mark.parametrize("action", [a for _, a in m.HUD_BUTTONS])
def test_every_hotkey_on_the_hud_is_pressable(game, action):
    """With no keyboard this row is the only way to pause, retry or get out.

    The labels are drawn from the same layout that decides what a press hits, so
    the thing named is the thing that happens -- but only if both sides really
    do come from that one place, which is what this checks by pressing the
    middle of each label in turn.
    """
    game.start_run()
    game.score = 42
    click(game, *hud_button(game, action))
    if action == "pause":
        assert game.paused
    elif action == "menu":
        assert game.state == m.MENU
    elif action == "retry":
        assert game.state == m.PLAYING and game.score == 0
    else:
        raise AssertionError(f"untested action {action}")


def test_the_hud_buttons_do_not_overlap_or_leave_the_canvas(game):
    spans = game.hud_buttons()[1]
    for (_, left, width), (_, next_left, _) in zip(spans, spans[1:]):
        assert left + width < next_left, "two buttons share pixels"
    action, left, width = spans[-1]
    assert left + width <= wd.WIDTH, (action, left + width)
    assert spans[0][1] > 0


def test_pausing_and_resuming_by_press(game):
    """The overlay names a key, and a phone has none."""
    game.start_run()
    click(game, *hud_button(game, "pause"))
    assert game.paused

    click(game, 150, 40)
    assert not game.paused, "a press did not resume"
    assert game.jump_buffer == 0.0, "the press that resumed also jumped"


def test_the_menu_is_reachable_while_paused(game):
    """Otherwise pausing on a phone is a corner with no way out of it."""
    game.start_run()
    game.paused = True
    click(game, *hud_button(game, "menu"))
    assert game.state == m.MENU


def test_the_game_over_banner_has_its_own_way_to_the_menu(game):
    """Every other pixel of that screen means "carry on", so the menu needed a
    target of its own -- it is where you go to change character, and a run
    ending is when you would want to.
    """
    game.start_run()
    game.end_run()
    game.over_timer = m.GAME_OVER_LOCKOUT
    click(game, wd.WIDTH // 2, m.OVER_MENU_ROW + 2)
    assert game.state == m.MENU

    game.start_run()
    game.end_run()
    game.over_timer = m.GAME_OVER_LOCKOUT
    click(game, wd.WIDTH // 2, 40)
    assert game.state == m.TITLE, "pressing elsewhere should still carry on"


def test_the_game_over_menu_button_is_inside_the_lockout_too(game):
    """The press that killed you is often still coming."""
    game.start_run()
    game.end_run()
    click(game, wd.WIDTH // 2, m.OVER_MENU_ROW + 2)
    assert game.state == m.GAME_OVER


def test_a_press_does_nothing_else_while_paused(game):
    game.start_run()
    game.paused = True
    click(game, 150, 20, button=m.MOUSE_DUCK_BUTTON)
    assert game.jump_buffer == 0.0 and not game.pointer_jump
    assert not game.pointer_duck


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


def test_a_finger_lifted_anywhere_lets_go(game):
    """A release outside the zone it was pressed in must still end the press,
    or a finger dragged up the screen leaves the character crouched forever.
    """
    game.start_run()
    tap(game, 150, wd.HEIGHT - 4)
    assert game.pointer_duck
    tap(game, 150, 4, down=False)
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
