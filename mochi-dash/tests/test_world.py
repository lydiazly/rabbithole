"""Tests for the spawner's fairness guarantees and for collision. No window needed."""

import random

import pytest

from mochi_dash import player as pl
from mochi_dash import scenes, sprites
from mochi_dash import world as wd

DT = 1.0 / 60.0
FIVE_MINUTES = int(300 / DT)
PLAYER_X = 42.0  # where main.py stands the runner


class RecordingWorld(wd.World):
    """A world that notes where and how fast it was at every spawn."""

    def reset(self):
        super().reset()
        self.spawns = []

    def _spawn(self):
        super()._spawn()
        self.spawns.append((self.distance, self.speed, self.scroll))


def settled(ducking: bool = False) -> pl.Player:
    s = pl.Player(0.0, wd.GROUND_Y)
    for _ in range(int(1.0 / DT)):
        s.update(DT, False, ducking, 0, -1e6, 1e6)
    return s


def measured_airtime() -> float:
    s = pl.Player(0.0, wd.GROUND_Y)
    s.jump()
    t = 0.0
    while not s.on_ground and t < 5.0:
        s.update(DT, True, False, 0, -1e6, 1e6)
        t += DT
    return t


def test_gap_constant_is_not_optimistic():
    """The spawn floor is only fair if a real jump fits inside it."""
    assert measured_airtime() <= wd.JUMP_AIRTIME


def test_spawn_gaps_always_leave_room_to_land_and_jump_again():
    w = RecordingWorld(scenes.DEFAULT, random.Random(1))
    for _ in range(FIVE_MINUTES):
        w.update(DT, PLAYER_X)
    assert len(w.spawns) > 100
    for (d0, *_), (d1, speed_end, _) in zip(w.spawns, w.spawns[1:]):
        # Speed at the *end* of the gap is the harshest reading: the world sped
        # up while the player was crossing it.
        assert (d1 - d0) / speed_end >= wd.JUMP_AIRTIME


def test_a_full_jump_clears_the_tallest_obstacle_at_top_speed():
    tallest = wd.LARGE_BOX[1]
    s = pl.Player(0.0, wd.GROUND_Y)
    s.jump()
    clear_time = 0.0
    widest = 0
    while not s.on_ground:
        s.update(DT, True, False, 0, -1e6, 1e6)
        if wd.GROUND_Y - s.y >= tallest:
            clear_time += DT
            widest = max(widest, s.size[0])
    # Horizontal room won while high enough, versus the room actually needed.
    assert clear_time * wd.SPEED_MAX > wd.LARGE_BOX[0] + widest


def test_low_flyers_demand_a_duck_and_admit_one():
    w, h = wd.AIR_BOX
    flyer = wd.Obstacle(-w / 2, wd.GROUND_Y - wd.AIR_LOW_CLEAR - h, w, h, "flyer")
    assert pl.rects_overlap(settled().hitbox(), flyer.rect())
    assert not pl.rects_overlap(settled(ducking=True).hitbox(), flyer.rect())


def test_high_flyers_are_safe_at_ground_level():
    w, h = wd.AIR_BOX
    flyer = wd.Obstacle(-w / 2, wd.GROUND_Y - wd.AIR_HIGH_CLEAR - h, w, h, "flyer")
    assert not pl.rects_overlap(settled().hitbox(), flyer.rect())


def test_ducking_takes_a_few_frames_so_it_cannot_be_a_reflex():
    """DUCK_IN has to actually pass through taller frames to be worth timing."""
    w, h = wd.AIR_BOX
    flyer = wd.Obstacle(-w / 2, wd.GROUND_Y - wd.AIR_LOW_CLEAR - h, w, h, "flyer")
    s = settled()
    s.update(DT, False, True, 0, -1e6, 1e6)
    assert pl.rects_overlap(s.hitbox(), flyer.rect())


def test_obstacle_sprites_fit_over_their_hitboxes():
    """The hitbox must never be wider than the art the player is reading."""
    for rows, box in (
        (sprites.CACTUS_SMALL, wd.SMALL_BOX),
        (sprites.CACTUS_LARGE, wd.LARGE_BOX),
        (sprites.FLYER_UP, wd.AIR_BOX),
    ):
        sw, sh = sprites.sprite_size(rows)
        assert box[0] <= sw and box[1] <= sh


def speed_at(t: float) -> float:
    """Speed at a given point along the difficulty ramp."""
    return wd.SPEED_START + t * wd.SPEED_RANGE


def test_a_run_opens_with_nothing_but_single_small_cacti():
    """The newcomer's runway: for a while the only thing to learn is the jump."""
    small, large, cluster = wd.ground_weights(wd.SPEED_START)
    assert small > 0 and large == 0.0 and cluster == 0.0
    assert wd.air_chance(wd.SPEED_START) == 0.0
    assert wd.low_flyer_share(wd.SPEED_START) == 0.0


def test_hazards_unlock_in_a_deliberate_order():
    """Tall, then wide, then something that has to be ducked."""
    order = [wd.AIR_FROM, wd.LARGE_FROM, wd.LOW_FLYER_FROM, wd.CLUSTER_FROM,
             wd.TRIPLE_FROM]
    assert order == sorted(order), order
    assert order[-1] < 1.0, "the last hazard never actually arrives"


def test_every_hazard_is_in_play_by_top_speed():
    _, large, cluster = wd.ground_weights(wd.SPEED_MAX)
    assert large > 0.0 and cluster > 0.0
    assert wd.air_chance(wd.SPEED_MAX) > 0.0
    assert wd.low_flyer_share(wd.SPEED_MAX) > 0.0


def test_difficulty_never_decreases_with_speed():
    speeds = range(int(wd.SPEED_START), int(wd.SPEED_MAX))
    for curve in (wd.air_chance, wd.low_flyer_share):
        values = [curve(s) for s in speeds]
        assert values == sorted(values), curve.__name__
    for i in (1, 2):  # large, then cluster
        weights = [wd.ground_weights(s)[i] for s in speeds]
        assert weights == sorted(weights), i


def test_ducking_is_never_demanded_before_it_is_unlocked():
    below = speed_at(wd.LOW_FLYER_FROM) - 1.0
    assert wd.low_flyer_share(below) == 0.0


def test_top_speed_still_leaves_time_to_react():
    """Reaction window: an obstacle appearing at the right edge versus the player."""
    window = (wd.WIDTH - 42.0) / wd.SPEED_MAX
    assert window > 1.1


def test_no_flyers_before_they_unlock():
    w = RecordingWorld(scenes.DEFAULT, random.Random(2))
    floor = speed_at(wd.AIR_FROM)
    while w.speed < floor:
        w.update(DT, PLAYER_X)
        assert not any(ob.kind == "flyer" for ob in w.obstacles)


def test_the_opening_of_a_real_run_spawns_only_small_cacti():
    """The weights are one thing; what actually reaches the screen is another."""
    w = wd.World(scenes.DEFAULT, random.Random(11))
    unlock_speed = speed_at(min(wd.LARGE_FROM, wd.AIR_FROM))
    while w.speed < unlock_speed:
        w.update(DT, PLAYER_X)
        assert all(ob.kind == "small" for ob in w.obstacles), [
            ob.kind for ob in w.obstacles
        ]


def test_stars_hold_still_while_the_clouds_drift():
    """The sky's two layers must not be confused for each other.

    Anything that moves reads as near scenery; the stars and the moon are the
    only things meant to sit further off than the hills.
    """
    w = wd.World(scenes.DEFAULT, random.Random(5))
    stars, clouds = list(w.stars), [c[0] for c in w.clouds]
    for _ in range(FIVE_MINUTES):
        w.update(DT, PLAYER_X)
    assert w.stars == stars
    # Vacuous otherwise: a world that scrolled nothing would also pass.
    assert [c[0] for c in w.clouds] != clouds


def test_obstacles_are_retired_once_offscreen():
    w = wd.World(scenes.DEFAULT, random.Random(3))
    for _ in range(FIVE_MINUTES):
        w.update(DT, PLAYER_X)
        assert all(ob.x + ob.w > -16.0 for ob in w.obstacles)
    assert len(w.obstacles) < 12


def test_speed_and_day_phase_stay_in_range():
    w = wd.World(scenes.DEFAULT, random.Random(4))
    for _ in range(FIVE_MINUTES):
        w.update(DT, PLAYER_X)
        assert wd.SPEED_START <= w.speed <= wd.SPEED_MAX
        assert 0.0 <= w.phase < 1.0
    assert w.speed == wd.SPEED_MAX


# -- scenes -----------------------------------------------------------------


def test_snow_no_longer_uses_the_snowman():
    """It was replaced by a smaller pine; the element is gone, not just unused."""
    assert not hasattr(sprites, "SNOWMAN")
    assert scenes.SNOW.ground["small"] is sprites.PINE_SMALL


def test_every_scene_supplies_art_for_every_role_the_spawner_uses():
    """A scene missing a role would crash on its first spawn of that kind."""
    for scene in scenes.SCENES:
        assert set(scene.ground) == {"small", "large"}, scene.key
        assert len(scene.flyer) == 2, scene.key


def test_scene_art_fits_the_same_hitboxes():
    """Picking a place must not pick a difficulty.

    Every scene's art has to cover the one set of hitboxes the spawner uses, or
    swapping scenery would quietly change how hard the game is -- the same rule
    that holds for characters.
    """
    for scene in scenes.SCENES:
        for kind, box in (("small", wd.SMALL_BOX), ("large", wd.LARGE_BOX)):
            sw, sh = sprites.sprite_size(scene.ground[kind])
            assert box[0] <= sw and box[1] <= sh, (scene.key, kind)
        for rows in scene.flyer:
            sw, sh = sprites.sprite_size(rows)
            assert wd.AIR_BOX[0] <= sw and wd.AIR_BOX[1] <= sh, scene.key


def test_scene_ground_art_has_a_solid_core_over_its_hitbox():
    """The box is narrower than the art, but it must not cover empty pixels.

    A hitbox column with no art behind it is a death the player could not have
    read off the screen.
    """
    for scene in scenes.SCENES:
        for kind, box in (("small", wd.SMALL_BOX), ("large", wd.LARGE_BOX)):
            rows = scene.ground[kind]
            sw, _ = sprites.sprite_size(rows)
            core = 3  # the trunk every ground obstacle is built around
            left = (sw - core) // 2
            for y, row in enumerate(rows):
                span = row[left:left + core]
                assert set(span) != {"."}, (scene.key, kind, y, row)


def test_a_scene_can_switch_a_layer_off():
    """The parameterisation is only real if absence works, not just recolouring."""
    assert not scenes.SNOW.has("clouds")
    w = wd.World(scenes.SNOW, random.Random(9))
    assert w.clouds == []
    for _ in range(600):
        w.update(DT, PLAYER_X)
    assert w.clouds == []
    # And the layers it does keep are still populated.
    assert w.stars and w.near and w.speckles


def test_unknown_layer_names_are_rejected():
    """A typo would silently switch a layer off rather than fail."""
    import dataclasses
    with pytest.raises(ValueError):
        dataclasses.replace(scenes.DESERT, layers=frozenset({"hils_far"}))


def test_switching_scene_rebuilds_the_scenery():
    w = wd.World(scenes.DESERT, random.Random(7))
    assert w.clouds
    w.use_scene(scenes.SNOW)
    assert w.clouds == []
    w.use_scene(scenes.DESERT)
    assert w.clouds


# -- scoring and the dash ---------------------------------------------------


def test_points_grow_with_obstacle_height():
    """Height stands in for how much of a jump a thing demands."""
    small = wd.Obstacle(0, 0, *wd.SMALL_BOX, "small")
    large = wd.Obstacle(0, 0, *wd.LARGE_BOX, "large")
    flyer = wd.Obstacle(0, 0, *wd.AIR_BOX, "flyer")
    assert wd.points_for(large) > wd.points_for(small)
    assert wd.points_for(small) >= 1 and wd.points_for(flyer) >= 1


def test_an_obstacle_scores_once_however_the_player_moves():
    """A and D shift where you stand, so a cleared cactus must not re-score."""
    w = wd.World(scenes.DEFAULT, random.Random(3))
    ob = wd.Obstacle(PLAYER_X - 8, wd.GROUND_Y - 11, *wd.SMALL_BOX, "small")
    w.obstacles = [ob]
    expected = wd.points_for(ob)
    first = w.update(DT, PLAYER_X)
    assert first == expected, (first, expected)
    total = first
    for _ in range(30):
        total += w.update(DT, PLAYER_X - 40)  # shuffle back over it
    assert total == expected, "scored more than once"


def test_the_spawn_floor_holds_at_the_boosted_speed():
    """The dash speeds the world up, and the gap guarantee is keyed to speed.

    Were the floor computed from the un-boosted ramp speed, gaps spawned during
    a dash would arrive faster than they were spaced for, and the moment the
    dash ended the player would inherit one that could not be jumped.
    """
    w = RecordingWorld(scenes.DEFAULT, random.Random(4))
    w.boost = 1.35
    for _ in range(FIVE_MINUTES):
        w.update(DT, PLAYER_X)
    assert len(w.spawns) > 100
    for (d0, *_), (d1, _, scroll_end) in zip(w.spawns, w.spawns[1:]):
        assert (d1 - d0) / scroll_end >= wd.JUMP_AIRTIME


def test_obstacles_get_denser_as_the_run_speeds_up():
    """A gap measured in seconds keeps the density flat however fast it goes.

    That is what it used to do: 1.14s between obstacles at the opening crawl and
    1.13s at top speed, so all the late difficulty came from the reaction window
    and none from the spacing.
    """
    early = wd.gap_range(wd.SPEED_START)
    late = wd.gap_range(wd.SPEED_MAX)
    assert late[0] < early[0] and late[1] < early[1]
    # Still never below what a jump needs.
    assert late[0] >= wd.JUMP_AIRTIME


def test_a_launched_obstacle_stops_being_dangerous():
    w = wd.World(scenes.DEFAULT, random.Random(5))
    ob = wd.Obstacle(PLAYER_X, wd.GROUND_Y - 11, *wd.SMALL_BOX, "small")
    w.obstacles = [ob]
    box = (PLAYER_X, wd.GROUND_Y - 12, 12, 11)
    assert w.hits(box), "should be a hit before it is launched"
    w.launch(ob)
    assert not w.hits(box)
    assert w.collides(box) is False
    start_y = ob.y
    for _ in range(20):
        w.update(DT, PLAYER_X)
    assert ob.y < start_y, "should be flying"
