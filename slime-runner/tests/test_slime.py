"""Tests for the art, the frame animator and the slime's motion. No window needed."""

import pytest

from slime_runner import pixelfont, sprites
from slime_runner import slime as sl
from slime_runner import world as wd
from slime_runner.palette import DAY, NIGHT, STEPS, is_night, palette_for_step, step_at

DT = 1.0 / 60.0
GROUND = 84.0


def make_slime() -> sl.Slime:
    return sl.Slime(0.0, GROUND)


def run(s: sl.Slime, ticks: int, ducking: bool = False, holding: bool = False):
    """Advance the slime, returning the frame shown on each tick."""
    frames = []
    for _ in range(ticks):
        s.update(DT, holding, ducking, 0, -1e6, 1e6)
        frames.append(s.frame)
    return frames


# -- the art ----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(sprites.ALL_ART))
def test_art_is_rectangular_and_uses_known_characters(name):
    sprites.validate(sprites.ALL_ART[name])


@pytest.mark.parametrize("step", range(STEPS))
def test_every_sheet_builds_for_every_day_night_step(step):
    """A sprite using a character its colour map lacks KeyErrors on build."""
    sheet = sprites.SpriteSheet(palette_for_step(step))
    assert set(sheet.slime) == set(sprites.SLIME_FRAMES)
    for name, surf in sheet.slime.items():
        assert surf.get_size() == sprites.SLIME_SIZES[name]


def test_squash_frames_are_wider_and_shorter_than_the_round_one():
    rw, rh = sprites.SLIME_SIZES["round"]
    for name in ("squash1", "squash2", "squash3"):
        w, h = sprites.SLIME_SIZES[name]
        assert w > rw and h < rh, name


def test_stretch_frames_are_taller_and_narrower_than_the_round_one():
    rw, rh = sprites.SLIME_SIZES["round"]
    for name in ("stretch1", "stretch2"):
        w, h = sprites.SLIME_SIZES[name]
        assert w < rw and h > rh, name


def test_deformation_frames_form_a_monotonic_ladder():
    """The frames only read as one blob deforming if they order consistently."""
    order = ["stretch2", "stretch1", "round", "squash1", "squash2", "squash3"]
    widths = [sprites.SLIME_SIZES[n][0] for n in order]
    heights = [sprites.SLIME_SIZES[n][1] for n in order]
    assert widths == sorted(widths)
    assert heights == sorted(heights, reverse=True)


def test_every_glyph_is_the_declared_size():
    for char, glyph in pixelfont._GLYPHS.items():
        assert len(glyph) == pixelfont.GLYPH_H, char
        for row in glyph:
            assert len(row) == pixelfont.GLYPH_W, char


def test_no_two_glyphs_are_identical():
    """O and 0 in particular have to be told apart in a score."""
    seen = {}
    for char, glyph in pixelfont._GLYPHS.items():
        if char == " ":
            continue
        assert glyph not in seen, f"{char} and {seen.get(glyph)} draw the same"
        seen[glyph] = char


def test_hud_and_title_strings_fit_the_canvas():
    """A long line would silently run off the edge, or set_at out of bounds."""
    lines = [
        ("HI 00000  00000", 1),
        ("SLIME RUNNER", 2),
        ("SPACE OR W - JUMP", 1),
        ("S - DUCK   A/D - SHIFT", 1),
        ("GAME OVER", 2),
        ("R - RUN AGAIN   Q - QUIT", 1),
    ]
    for text, scale in lines:
        assert pixelfont.text_width(text, scale) <= wd.WIDTH - 12, text


# -- the animator -----------------------------------------------------------


def test_a_hard_landing_plays_the_full_squash_and_overshoot():
    s = make_slime()
    s.jump()
    impact = 0.0
    while not s.on_ground:
        impact = s.update(DT, True, False, 0, -1e6, 1e6)
    assert impact >= sl.HARD_LANDING
    frames = [s.frame] + run(s, 16)
    # Flattest first, then part-way back, then past round, then settled.
    assert frames.index("squash3") < frames.index("squash1")
    assert frames.index("squash1") < frames.index("stretch1")
    assert "round" in frames[frames.index("stretch1"):]


def test_a_clipped_hop_lands_softly_without_the_deepest_frame():
    s = make_slime()
    s.jump()
    while not s.on_ground:
        s.update(DT, False, False, 0, -1e6, 1e6)  # released immediately
    frames = [s.frame] + run(s, 10)
    assert "squash3" not in frames
    assert "squash2" in frames


def test_takeoff_stretches_before_the_airborne_pose_takes_over():
    s = make_slime()
    s.jump()
    assert s.frame == "stretch2"


def test_the_apex_is_round():
    s = make_slime()
    s.jump()
    prev_vy = s.vy
    apex_frame = None
    while not s.on_ground:
        s.update(DT, True, False, 0, -1e6, 1e6)
        if apex_frame is None and prev_vy < 0.0 <= s.vy:
            apex_frame = s.frame
        prev_vy = s.vy
    assert apex_frame == "round"


def test_idle_alternates_between_the_two_resting_frames():
    s = make_slime()
    frames = set(run(s, sl.IDLE_TICKS * 3))
    assert frames == {"round", "round_b"}


def test_ducking_settles_on_the_flattest_frame_and_springs_back():
    s = make_slime()
    run(s, 4)
    down = run(s, 12, ducking=True)
    assert down[-1] == "squash3"
    up = run(s, 10)
    assert "stretch1" in up  # the overshoot on release
    assert up[-1] in ("round", "round_b")


def test_ducking_shortens_and_widens_the_hitbox():
    standing = make_slime()
    run(standing, 12)
    ducked = make_slime()
    run(ducked, 12, ducking=True)

    _, _, w_up, h_up = standing.hitbox()
    _, _, w_down, h_down = ducked.hitbox()
    assert h_down < h_up * 0.75
    assert w_down > w_up


def test_hitbox_sits_on_the_ground():
    s = make_slime()
    run(s, 12)
    _, top, _, height = s.hitbox()
    assert top + height == pytest.approx(GROUND)


def test_lateral_movement_is_clamped():
    s = make_slime()
    for _ in range(600):
        s.update(DT, False, False, 1, -50.0, 40.0)
    assert s.x == pytest.approx(40.0)
    for _ in range(600):
        s.update(DT, False, False, -1, -50.0, 40.0)
    assert s.x == pytest.approx(-50.0)


# -- the palette ------------------------------------------------------------


def test_palette_steps_hold_at_the_ends():
    assert step_at(0.0) == 0
    assert step_at(0.7) == STEPS - 1
    assert palette_for_step(0) is DAY
    assert palette_for_step(STEPS - 1) is NIGHT
    assert not is_night(0)
    assert is_night(STEPS - 1)


def test_ground_detail_keeps_its_contrast_direction_at_every_step():
    """Day and night both put the speckles darker than the ground.

    If one palette flipped the direction, the two would cross somewhere mid-dusk
    and the ground would go flat and detail-less for the whole transition.
    """
    for step in range(STEPS):
        p = palette_for_step(step)
        assert sum(p.speckle) < sum(p.ground), step
        assert sum(p.ground_line) < sum(p.ground), step


def test_obstacles_stay_distinguishable_from_the_ground_at_every_step():
    for step in range(STEPS):
        p = palette_for_step(step)
        diff = sum(abs(a - b) for a, b in zip(p.obstacle, p.ground))
        assert diff > 40, (step, p.obstacle, p.ground)
