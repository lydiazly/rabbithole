"""Tests for the art, the frame animator and the slime's motion. No window needed."""

import pytest

from slime_runner import characters, pixelfont, sprites
from slime_runner import slime as sl
from slime_runner import world as wd
from slime_runner.palette import (
    DAY, NIGHT, STEPS, is_night, luminance, palette_for_step, step_at, text_tones,
)

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
@pytest.mark.parametrize("character", characters.CHARACTERS, ids=lambda c: c.key)
def test_every_sheet_builds_for_every_character_and_step(character, step):
    """A sprite using a character its colour map lacks KeyErrors on build."""
    sheet = sprites.SpriteSheet(
        palette_for_step(step), characters.look_for_step(character, step)
    )
    assert set(sheet.slime) == set(sprites.SLIME_FRAMES)
    for name, surf in sheet.slime.items():
        assert surf.get_size() == sprites.SLIME_SIZES[name]
    assert len(sheet.ears) == len(sprites.EAR_LEFT)


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
        ("JUMP AGAIN IN AIR TO DOUBLE", 1),
        ("S - DUCK   A/D - SHIFT", 1),
        ("GAME OVER", 2),
        ("R - RUN AGAIN   Q - QUIT", 1),
    ]
    for text, scale in lines:
        assert pixelfont.text_width(text, scale) <= wd.WIDTH - 12, text


# -- characters -------------------------------------------------------------


def test_character_keys_and_names_are_unique():
    keys = [c.key for c in characters.CHARACTERS]
    names = [c.name for c in characters.CHARACTERS]
    assert len(set(keys)) == len(keys)
    assert len(set(names)) == len(names)


def test_characters_are_a_recolour_and_nothing_more():
    """Picking a character must never pick a difficulty.

    Everything that decides how the game plays -- pose sizes, hitboxes, motion --
    lives outside the character, so this holds by construction; the test is here
    so it keeps holding when a third character is added.
    """
    for character in characters.CHARACTERS:
        for step in range(STEPS):
            sheet = sprites.SpriteSheet(
                palette_for_step(step), characters.look_for_step(character, step)
            )
            for name, surf in sheet.slime.items():
                assert surf.get_size() == sprites.SLIME_SIZES[name]


def test_every_pose_puts_its_ears_on_the_head():
    """Anchors are derived from each pose's crown, which moves across all seven.

    Ears floating off the side of a pancake, or buried inside a stretched one,
    would be the obvious failure of computing them rather than authoring them.
    """
    for name, rows in sprites.SLIME_FRAMES.items():
        w, h = sprites.SLIME_SIZES[name]
        left, right, dy = sprites.EAR_ANCHORS[name]
        # Horizontally: sitting on the crown, not out past the widest point.
        assert -1 <= left, name
        assert right + sprites.EAR_W <= w + 1, name
        assert left + sprites.EAR_W <= right, f"{name}: ears overlap each other"
        # Vertically: mostly above the head, but tucked in enough to touch it.
        assert dy < 0, name
        assert dy + sprites.EAR_H <= h, name
        assert dy + sprites.EAR_H > 0, f"{name}: ears float off the top"


def test_ears_are_symmetric_about_the_body():
    for name, rows in sprites.SLIME_FRAMES.items():
        w, _ = sprites.SLIME_SIZES[name]
        left, right, _ = sprites.EAR_ANCHORS[name]
        left_gap = left
        right_gap = w - (right + sprites.EAR_W)
        assert left_gap == right_gap, name


def test_the_ear_twitch_visits_every_ear_frame_and_loops():
    cycle = sum(ticks for _, ticks in sprites.EAR_IDLE)
    seen = {sl.idle_ear_frame(t) for t in range(cycle)}
    assert seen == set(range(len(sprites.EAR_LEFT)))
    assert sl.idle_ear_frame(cycle) == sl.idle_ear_frame(0)


def test_ears_are_still_while_the_body_is_doing_something():
    s = make_slime()
    run(s, 40)  # settle, ears twitching
    s.jump()
    while not s.on_ground:
        s.update(DT, True, False, 0, -1e6, 1e6)
        assert s.ear_frame == 0
    ducked = make_slime()
    run(ducked, 30, ducking=True)
    assert ducked.ear_frame == 0


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


# -- jumping ----------------------------------------------------------------


def jump_flight(second_jump_at=None):
    """Fly one jump, optionally pressing again on tick `second_jump_at`.

    Returns (peak height above the ground, airtime, highest sprite top edge).
    """
    s = make_slime()
    s.jump()
    peak, top, tick = 0.0, GROUND, 0
    while not s.on_ground:
        if tick == second_jump_at:
            s.jump()
        s.update(DT, True, False, 0, -1e6, 1e6)
        peak = max(peak, GROUND - s.y)
        top = min(top, s.blit_pos()[1])
        tick += 1
    return peak, tick * DT, top


APEX_TICK = round(sl.JUMP_SPEED / sl.GRAVITY_UP / DT)


def test_a_single_jump_clears_the_tallest_obstacle_with_room_to_spare():
    peak, _, _ = jump_flight()
    assert peak > wd.LARGE_BOX[1] + sprites.SLIME_SIZES["round"][1]


def test_a_second_jump_goes_meaningfully_higher():
    single, _, _ = jump_flight()
    double, _, _ = jump_flight(second_jump_at=APEX_TICK)
    assert double > single * 1.35


def test_double_jump_timing_is_forgiving():
    """A quick double tap and a patient apex press must reach similar heights.

    Topping the flight up to a clamped apex is what buys this; a second jump that
    replaced the velocity would only pay off within a few ticks of the apex.
    """
    tapped, _, _ = jump_flight(second_jump_at=1)
    apex, _, _ = jump_flight(second_jump_at=APEX_TICK)
    assert min(tapped, apex) / max(tapped, apex) > 0.9


def test_the_slime_never_leaves_the_top_of_the_canvas():
    """Swept over every tick of the ascent, not sampled.

    The worst case is not the apex press but a press partway up, which banks the
    height already climbed and then adds to it. Sampling a few timings missed it.
    """
    for when in range(0, APEX_TICK + 12):
        _, _, top = jump_flight(second_jump_at=when)
        assert top >= 0, when


def test_no_press_timing_beats_the_apex_ceiling():
    for when in range(0, APEX_TICK + 12):
        peak, _, _ = jump_flight(second_jump_at=when)
        assert peak <= sl.MAX_APEX + 1.0, (when, peak)


def test_only_two_jumps_are_available_per_flight():
    s = make_slime()
    assert s.jump() == "ground"
    assert s.jump() == "air"
    assert s.jump() is None


def test_landing_restores_the_second_jump():
    s = make_slime()
    s.jump()
    s.jump()
    while not s.on_ground:
        s.update(DT, True, False, 0, -1e6, 1e6)
    assert s.jump() == "ground"


def test_a_second_jump_never_slows_an_ascent():
    for when in range(0, APEX_TICK + 1, 3):
        s = make_slime()
        s.jump()
        for _ in range(when):
            s.update(DT, True, False, 0, -1e6, 1e6)
        before = s.vy
        s.jump()
        assert s.vy <= before, when


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


def test_text_stays_readable_against_the_sky_at_every_step():
    """The dusk steps are where this failed: contrast bottomed out at 18 of 255.

    Choosing the tone by whether it was night, rather than by how bright the sky
    actually was, left dark text on an already-dark sky for three whole steps.
    """
    for step in range(STEPS):
        sky = palette_for_step(step).sky
        ink, halo = text_tones(step)
        assert abs(luminance(ink) - luminance(sky)) > 60, (step, ink, sky)
        # The shadow exists to separate glyphs from whatever they overlap -- hills,
        # clouds, a cactus -- so it just has to be the opposite tone to the ink.
        assert {ink, halo} == {DAY.text, NIGHT.text}, step


def test_characters_stay_visible_against_the_sky_at_every_step():
    """Either the fill or the edge has to separate the character from the sky.

    Which one does the work changes over the ramp, and neither survives it alone:
    the slime's dark outline carries the bright daytime steps and washes out by
    dusk, exactly as its body brightens enough to take over. Measuring only one of
    them reports a failure at whichever end the other is covering.
    """
    for character in characters.CHARACTERS:
        for step in range(STEPS):
            sky = palette_for_step(step).sky
            look = characters.look_for_step(character, step)
            best = max(
                sum(abs(a - b) for a, b in zip(look.body, sky)),
                sum(abs(a - b) for a, b in zip(look.outline, sky)),
            )
            assert best > 140, (character.key, step, best)
