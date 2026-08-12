"""Tests for the spawner's fairness guarantees and for collision. No window needed."""

import random

from slime_runner import slime as sl
from slime_runner import sprites
from slime_runner import world as wd

DT = 1.0 / 60.0
FIVE_MINUTES = int(300 / DT)


class RecordingWorld(wd.World):
    """A world that notes where and how fast it was at every spawn."""

    def reset(self):
        super().reset()
        self.spawns = []

    def _spawn(self):
        super()._spawn()
        self.spawns.append((self.distance, self.speed))


def settled(ducking: bool = False) -> sl.Slime:
    s = sl.Slime(0.0, wd.GROUND_Y)
    for _ in range(int(1.0 / DT)):
        s.update(DT, False, ducking, 0, -1e6, 1e6)
    return s


def measured_airtime() -> float:
    s = sl.Slime(0.0, wd.GROUND_Y)
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
    w = RecordingWorld(random.Random(1))
    for _ in range(FIVE_MINUTES):
        w.update(DT)
    assert len(w.spawns) > 100
    for (d0, _), (d1, speed_end) in zip(w.spawns, w.spawns[1:]):
        # Speed at the *end* of the gap is the harshest reading: the world sped
        # up while the player was crossing it.
        assert (d1 - d0) / speed_end >= wd.JUMP_AIRTIME


def test_a_full_jump_clears_the_tallest_obstacle_at_top_speed():
    tallest = wd.LARGE_BOX[1]
    s = sl.Slime(0.0, wd.GROUND_Y)
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
    assert sl.rects_overlap(settled().hitbox(), flyer.rect())
    assert not sl.rects_overlap(settled(ducking=True).hitbox(), flyer.rect())


def test_high_flyers_are_safe_at_ground_level():
    w, h = wd.AIR_BOX
    flyer = wd.Obstacle(-w / 2, wd.GROUND_Y - wd.AIR_HIGH_CLEAR - h, w, h, "flyer")
    assert not sl.rects_overlap(settled().hitbox(), flyer.rect())


def test_ducking_takes_a_few_frames_so_it_cannot_be_a_reflex():
    """DUCK_IN has to actually pass through taller frames to be worth timing."""
    w, h = wd.AIR_BOX
    flyer = wd.Obstacle(-w / 2, wd.GROUND_Y - wd.AIR_LOW_CLEAR - h, w, h, "flyer")
    s = settled()
    s.update(DT, False, True, 0, -1e6, 1e6)
    assert sl.rects_overlap(s.hitbox(), flyer.rect())


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
    """Reaction window: an obstacle appearing at the right edge versus the slime."""
    window = (wd.WIDTH - 42.0) / wd.SPEED_MAX
    assert window > 1.1


def test_no_flyers_before_they_unlock():
    w = RecordingWorld(random.Random(2))
    floor = speed_at(wd.AIR_FROM)
    while w.speed < floor:
        w.update(DT)
        assert not any(ob.kind == "flyer" for ob in w.obstacles)


def test_the_opening_of_a_real_run_spawns_only_small_cacti():
    """The weights are one thing; what actually reaches the screen is another."""
    w = wd.World(random.Random(11))
    unlock_speed = speed_at(min(wd.LARGE_FROM, wd.AIR_FROM))
    while w.speed < unlock_speed:
        w.update(DT)
        assert all(ob.kind == "small" for ob in w.obstacles), [
            ob.kind for ob in w.obstacles
        ]


def test_stars_hold_still_while_the_clouds_drift():
    """The sky's two layers must not be confused for each other.

    Anything that moves reads as near scenery; the stars and the moon are the
    only things meant to sit further off than the hills.
    """
    w = wd.World(random.Random(5))
    stars, clouds = list(w.stars), [c[0] for c in w.clouds]
    for _ in range(FIVE_MINUTES):
        w.update(DT)
    assert w.stars == stars
    # Vacuous otherwise: a world that scrolled nothing would also pass.
    assert [c[0] for c in w.clouds] != clouds


def test_obstacles_are_retired_once_offscreen():
    w = wd.World(random.Random(3))
    for _ in range(FIVE_MINUTES):
        w.update(DT)
        assert all(ob.x + ob.w > -16.0 for ob in w.obstacles)
    assert len(w.obstacles) < 12


def test_speed_and_day_phase_stay_in_range():
    w = wd.World(random.Random(4))
    for _ in range(FIVE_MINUTES):
        w.update(DT)
        assert wd.SPEED_START <= w.speed <= wd.SPEED_MAX
        assert 0.0 <= w.phase < 1.0
    assert w.speed == wd.SPEED_MAX
