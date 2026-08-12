"""Tests for the art, the frame animator and the slime's motion. No window needed."""

import pytest

from slime_runner import characters, main, pixelfont, scenes, sprites
from slime_runner import slime as sl
from slime_runner import world as wd
from slime_runner.palette import STEPS, is_night, luminance, step_at

SCENE_STEPS = [(s, st) for s in scenes.SCENES for st in range(STEPS)]
SCENE_IDS = [f"{s.key}-{st}" for s, st in SCENE_STEPS]

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
    sheet = characters.sheet_for(character, step)
    assert set(sheet.poses) == set(sprites.SLIME_POSES)
    for name, surf in sheet.poses.items():
        assert surf.get_size() == sprites.POSE_SIZES[name]
    expected = len(character.accessory.frames) if character.accessory else 0
    assert len(sheet.accessory) == expected


@pytest.mark.parametrize("scene,step", SCENE_STEPS, ids=SCENE_IDS)
def test_the_world_sheet_builds_for_every_scene_and_step(scene, step):
    sheet = scenes.sheet_for(scene, step)
    assert set(sheet.ground) == set(scene.ground)
    assert len(sheet.flyer) == len(scene.flyer)


def test_squash_frames_are_wider_and_shorter_than_the_round_one():
    rw, rh = sprites.POSE_SIZES["round"]
    for name in ("squash1", "squash2", "squash3"):
        w, h = sprites.POSE_SIZES[name]
        assert w > rw and h < rh, name


def test_stretch_frames_are_taller_and_narrower_than_the_round_one():
    rw, rh = sprites.POSE_SIZES["round"]
    for name in ("stretch1", "stretch2"):
        w, h = sprites.POSE_SIZES[name]
        assert w < rw and h > rh, name


def test_deformation_frames_form_a_monotonic_ladder():
    """The frames only read as one blob deforming if they order consistently."""
    order = ["stretch2", "stretch1", "round", "squash1", "squash2", "squash3"]
    widths = [sprites.POSE_SIZES[n][0] for n in order]
    heights = [sprites.POSE_SIZES[n][1] for n in order]
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


UI_LINES = [
    ("HI 00000  00000", 1),
    ("SLIME RUNNER", 2),
    ("SPACE OR W - JUMP", 1),
    ("JUMP AGAIN IN AIR TO DOUBLE", 1),
    ("S - DUCK   A/D - SHIFT", 1),
    ("M - MENU   Q - QUIT", 1),
    ("GAME OVER", 2),
    ("SCORE 00000", 1),
    ("ANY KEY TO CONTINUE", 1),
    ("R RETRY  M MENU", 1),
    ("W/S  ROW    A/D  CHANGE    SPACE  START", 1),
    ("CHARACTER", 1),
    ("SCENE", 1),
] + [(f"< {c.name} >", 1) for c in characters.CHARACTERS] \
  + [(f"< {s.name} >", 1) for s in scenes.SCENES]


def test_hud_and_menu_strings_fit_the_canvas():
    """A long line would silently run off the edge, or set_at out of bounds."""
    for text, scale in UI_LINES:
        assert pixelfont.text_width(text, scale) <= wd.WIDTH - 12, text


def test_every_character_the_ui_prints_has_a_glyph():
    """Missing glyphs fall back to a solid block and print as garbage.

    "< CAT >" came out as a block, the name, and another block, because the
    angle brackets had never been drawn.
    """
    for text, _ in UI_LINES:
        for char in text.upper():
            assert char in pixelfont._GLYPHS, f"{char!r} in {text!r}"


# -- characters -------------------------------------------------------------


def test_character_keys_and_names_are_unique():
    keys = [c.key for c in characters.CHARACTERS]
    names = [c.name for c in characters.CHARACTERS]
    assert len(set(keys)) == len(keys)
    assert len(set(names)) == len(names)


def test_characters_may_differ_in_art_but_never_in_size():
    """Picking a character must never pick a difficulty.

    Characters own their poses now -- the cat has its own face and a rounder
    chin -- so this is no longer true by construction. Every pose of every
    character has to match the one size table the hitboxes come from.
    """
    for character in characters.CHARACTERS:
        for step in range(STEPS):
            sheet = characters.sheet_for(character, step)
            assert set(sheet.poses) == set(sprites.POSE_SIZES), character.key
            for name, surf in sheet.poses.items():
                assert surf.get_size() == sprites.POSE_SIZES[name], (
                    character.key, name)


ACCESSORIES = [c.accessory for c in characters.CHARACTERS if c.accessory]


@pytest.mark.parametrize("accessory", ACCESSORIES, ids=lambda a: f"{a.width}x{a.height}")
def test_every_pose_wears_its_accessory_on_the_crown(accessory):
    """Anchors are derived from each pose's crown, which moves across all seven.

    Ears floating off the side of a pancake, or buried inside a stretched one,
    would be the obvious failure of computing them rather than authoring them.
    """
    for name in sprites.SLIME_POSES:
        w, h = sprites.POSE_SIZES[name]
        left, right, dy = accessory.anchors[name]
        # Horizontally: sitting on the crown, not out past the widest point.
        assert -1 <= left, name
        assert right + accessory.width <= w + 1, name
        assert left + accessory.width <= right, f"{name}: the two sides overlap"
        # Vertically: mostly above the head, but tucked in enough to touch it.
        assert dy < 0, name
        assert dy + accessory.height <= h, name
        assert dy + accessory.height > 0, f"{name}: floats off the top"


@pytest.mark.parametrize("accessory", ACCESSORIES, ids=lambda a: f"{a.width}x{a.height}")
def test_accessories_sit_symmetrically(accessory):
    for name in sprites.SLIME_POSES:
        w, _ = sprites.POSE_SIZES[name]
        left, right, _ = accessory.anchors[name]
        assert left == w - (right + accessory.width), name


@pytest.mark.parametrize("accessory", ACCESSORIES, ids=lambda a: f"{a.width}x{a.height}")
def test_the_idle_cycle_visits_every_frame_and_loops(accessory):
    seen = {accessory.frame_at(t) for t in range(accessory.cycle)}
    assert seen == set(range(len(accessory.frames)))
    assert accessory.frame_at(accessory.cycle) == accessory.frame_at(0)


def test_an_accessory_must_use_every_frame_it_declares():
    """A frame authored but left out of the cycle would never appear on screen."""
    with pytest.raises(ValueError):
        sprites.Accessory(sprites.EAR_LEFT, ((0, 5), (1, 5)))
    with pytest.raises(ValueError):
        sprites.Accessory((sprites.EAR_LEFT[0], ("##", "##", "##", "##")), ((0, 5), (1, 5)))


def test_the_body_never_counts_as_idle_mid_action():
    """What suppresses the twitch is `idle`; the clock underneath keeps running."""
    s = make_slime()
    run(s, 40)
    assert s.idle
    s.jump()
    while not s.on_ground:
        s.update(DT, True, False, 0, -1e6, 1e6)
        assert not s.idle
    ducked = make_slime()
    run(ducked, 30, ducking=True)
    assert not ducked.idle
    # The clock advances every tick regardless, or a player who jumps at a normal
    # rate never reaches the first twitch.
    before = ducked.accessory_ticks
    run(ducked, 10, ducking=True)
    assert ducked.accessory_ticks == before + 10


# -- extensibility ----------------------------------------------------------


def test_a_new_character_needs_nothing_but_its_own_definition():
    """Stand a third character up and check every consumer copes.

    This is what the character/world split is for: a new face should be a value
    in CHARACTERS and no code anywhere else.
    """
    probe = characters.Character(
        key="probe",
        name="PROBE",
        day=characters.Look((200, 60, 60), (240, 120, 120), (255, 220, 220),
                            (90, 20, 20)),
        night=characters.Look((160, 50, 50), (210, 100, 100), (255, 210, 210),
                              (70, 16, 16)),
        poses=sprites.CAT_POSES,
        accessory=sprites.EARS,
    )
    for step in range(STEPS):
        sheet = characters.sheet_for(probe, step)
        assert set(sheet.poses) == set(sprites.SLIME_POSES)
        assert len(sheet.accessory) == len(sprites.EARS.frames)
        for name, surf in sheet.poses.items():
            assert surf.get_size() == sprites.POSE_SIZES[name]


@pytest.mark.parametrize("count", range(2, 6))
def test_the_menu_lays_out_any_number_of_options(count):
    """A hardcoded pair of x positions was an IndexError at three characters."""
    xs = main.preview_positions(count)
    assert len(xs) == count and xs == sorted(xs)
    assert all(0 < x < wd.WIDTH for x in xs)
    widest = max(w for w, _ in sprites.POSE_SIZES.values())
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    assert min(gaps) > widest, f"previews would overlap at {count}"


def test_world_art_is_shared_between_characters_not_copied_per_character():
    """World art is keyed on the scene and step, never on the character.

    While it was bundled into the character's sheet, every cactus, cloud, moon
    and puff was rebuilt and held once per character.
    """
    assert scenes.sheet_for(scenes.DESERT, 0) is scenes.sheet_for(scenes.DESERT, 0)
    assert scenes.sheet_for(scenes.SNOW, 0) is not scenes.sheet_for(scenes.DESERT, 0)
    slime_sheet = characters.sheet_for(characters.SLIME, 0)
    assert characters.sheet_for(characters.SLIME, 0) is slime_sheet
    assert characters.sheet_for(characters.CAT, 0) is not slime_sheet
    # A character sheet holds no world art at all any more.
    assert not hasattr(slime_sheet, "ground")
    assert not hasattr(slime_sheet, "flyer")


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
    assert peak > wd.LARGE_BOX[1] + sprites.POSE_SIZES["round"][1]


def test_the_apex_is_a_plateau_not_a_point():
    """Blunting the top of the arc is what stops it feeling like a clip.

    With one gravity the slime is at full height for a single tick, and grazing
    the top of an obstacle reads as unfair. Gravity is cut in a band around zero
    vertical speed so the peak is somewhere it arrives rather than passes
    through.
    """
    s = make_slime()
    s.jump()
    heights = []
    while not s.on_ground:
        s.update(DT, True, False, 0, -1e6, 1e6)
        heights.append(GROUND - s.y)
    peak = max(heights)
    near = sum(1 for h in heights if h > peak - 5.0)
    assert near >= 10, f"only {near} ticks within 5px of the peak"


def test_the_hang_is_paid_for_out_of_the_airtime_budget():
    """Hanging lengthens the flight, and the spawn-gap floor is keyed to it."""
    _, airtime, _ = jump_flight()
    assert airtime <= wd.JUMP_AIRTIME


def test_rise_and_speed_are_inverses_across_the_hang_band():
    """The second jump clamps its apex with these; a mismatch leaks the clamp."""
    for height in (0.0, 1.0, sl._HANG_RISE, sl._HANG_RISE + 0.5, 20.0, 60.0):
        assert sl.rise_from_speed(sl.speed_for_rise(height)) == pytest.approx(
            height, abs=1e-6), height


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
    assert not is_night(0)
    assert is_night(STEPS - 1)
    for scene in scenes.SCENES:
        assert scenes.palette_for_step(scene, 0) is scene.day
        assert scenes.palette_for_step(scene, STEPS - 1) is scene.night


@pytest.mark.parametrize("scene,step", SCENE_STEPS, ids=SCENE_IDS)
def test_ground_detail_keeps_its_contrast_direction(scene, step):
    """Day and night both put the speckles darker than the ground.

    If one palette flipped the direction, the two would cross somewhere mid-dusk
    and the ground would go flat and detail-less for the whole transition.
    """
    p = scenes.palette_for_step(scene, step)
    assert sum(p.speckle) < sum(p.ground), (scene.key, step)
    assert sum(p.ground_line) < sum(p.ground), (scene.key, step)


@pytest.mark.parametrize("scene,step", SCENE_STEPS, ids=SCENE_IDS)
def test_obstacles_stay_visible_against_everything_behind_them(scene, step):
    """Measured against the sky, horizon and hills -- not against the ground.

    Obstacles stand *on* the ground line and extend upward, so they never
    overlap the ground band at all. Checking them against the ground was
    checking a pair that never touches, and it hid a real fault: the fill ramps
    light towards night while every background ramps dark, so the two cross, and
    at the crossing the fill alone measured 46 of 255 in the desert and 17 in
    snow. The dark edge tone is what has to carry those steps.
    """
    p = scenes.palette_for_step(scene, step)
    for name in ("sky", "horizon", "hill_far", "hill_near"):
        if name in ("hill_far", "hill_near") and not scene.has(name):
            continue
        if name == "horizon" and not scene.has("horizon"):
            continue
        behind = getattr(p, name)
        best = max(
            sum(abs(a - b) for a, b in zip(p.obstacle, behind)),
            sum(abs(a - b) for a, b in zip(p.obstacle_dark, behind)),
        )
        assert best > 90, (scene.key, step, name, best)


@pytest.mark.parametrize("scene,step", SCENE_STEPS, ids=SCENE_IDS)
def test_text_stays_readable_against_the_sky(scene, step):
    """The dusk steps are where this failed: contrast bottomed out at 18 of 255.

    Choosing the tone by whether it was night, rather than by how bright the sky
    actually was, left dark text on an already-dark sky for three whole steps.
    A pale scene like snow is the other way a fixed choice would break.
    """
    sky = scenes.palette_for_step(scene, step).sky
    ink, halo = scenes.text_tones(scene, step)
    assert abs(luminance(ink) - luminance(sky)) > 60, (scene.key, step, ink, sky)
    # The shadow exists to separate glyphs from whatever they overlap -- hills,
    # clouds, an obstacle -- so it just has to be the opposite tone to the ink.
    assert {ink, halo} == {scene.day.text, scene.night.text}, (scene.key, step)


@pytest.mark.parametrize("scene,step", SCENE_STEPS, ids=SCENE_IDS)
def test_characters_stay_visible_against_every_sky(scene, step):
    """Either the fill or the edge has to separate the character from the sky.

    Which one does the work changes over the ramp, and neither survives it alone:
    the slime's dark outline carries the bright daytime steps and washes out by
    dusk, exactly as its body brightens enough to take over. Every character has
    to clear this against every scene, which is the cross-product a new scene
    could quietly break.
    """
    sky = scenes.palette_for_step(scene, step).sky
    for character in characters.CHARACTERS:
        look = characters.look_for_step(character, step)
        best = max(
            sum(abs(a - b) for a, b in zip(look.body, sky)),
            sum(abs(a - b) for a, b in zip(look.outline, sky)),
        )
        assert best > 140, (scene.key, character.key, step, best)
