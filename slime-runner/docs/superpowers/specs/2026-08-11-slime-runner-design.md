# Slime Runner — Design

An endless runner in the shape of the Chrome dino game, with a jelly slime as the
player character. The point of the project is the slime's elasticity: it must read
as a soft, translucent blob that deforms continuously, not as a sprite that swaps
between a "squashed" and a "normal" frame.

## Scope

In scope: run, jump (variable height), duck, ground and air obstacles, speed ramp,
score and persisted high score, parallax background, day/night cycle, landing dust,
motion afterimages.

Out of scope: sound, sprites/art assets (everything is drawn procedurally),
menus beyond title and game-over, difficulty settings, multiplayer.

## Project layout

Sibling of `snake/` and `breakout/`, and like them a self-contained uv project.
Unlike them it is a package rather than a single file, because the elasticity
system, the world, and the effects are independently understandable pieces and each
is easier to tune in isolation.

```
slime-runner/
  pyproject.toml          # name = "slime-runner", dependency: pygame-ce
  uv.lock
  slime_runner/
    __init__.py
    main.py               # window, fixed-timestep loop, state machine, input, HUD
    slime.py              # spring-damper deformation + jelly rendering
    world.py              # obstacles, spawner, parallax layers, ground, speed ramp
    effects.py            # dust particles, afterimages
    palette.py            # named colors + day/night interpolation
  tests/
    test_slime.py         # spring behaviour, volume preservation
    test_world.py         # spawn-gap clearability, collision
```

Run with `uv run slime-runner` (a `[project.scripts]` entry pointing at
`slime_runner.main:main`).

Window is 900x320, logical pixels == screen pixels, ground line at y=250.
Update runs at a fixed 1/60 s timestep driven by an accumulator, so the spring
integration is deterministic and does not blow up when a frame is slow. Rendering
happens once per real frame.

## `palette.py`

Holds two complete color sets, `DAY` and `NIGHT`, each a dataclass with fields for
sky, far hills, near hills, ground, ground speckle, obstacle, slime body, slime
highlight, slime outline, and text. Exposes `palette_at(phase) -> Palette` which
interpolates every field component-wise between the two sets.

`phase` is derived from distance travelled, `(distance / 6000) % 1.0`, and mapped
through a smoothstep so the world sits in full day or full night most of the time
and transitions over a short window rather than drifting continuously.

## `slime.py` — the elasticity system

This is the core of the project.

### Deformation state

A single scalar `s` describes the deformation:

- `s > 0` — squashed: wider and shorter
- `s < 0` — stretched: narrower and taller

It is converted to axis scales with exact area preservation, which is what makes
the blob read as a constant volume of jelly being deformed rather than as an
object being scaled:

```
scale_x = 1 + s
scale_y = 1 / (1 + s)
```

`s` is clamped to `[-0.45, 0.75]` so the shape never degenerates. When the clamp
bites, the outward component of `s_dot` is zeroed too, otherwise the spring keeps
pushing against the limit and the blob sticks flat for a moment before releasing.

Every constant in this section is a starting value chosen to put the motion in the
right range. They are meant to be adjusted by feel once the thing is running, and
`slime.py` exists as its own module partly so that tuning them is a one-file edit.

### Spring integration

`s` is never set directly during play. It is the position of a damped harmonic
oscillator:

```
s_ddot = -K * (s - s_target) - C * s_dot
```

with `K = 260` (~2.6 Hz) and `C = 2 * ZETA * sqrt(K)` at `ZETA = 0.28`. Being
underdamped is the whole point: after an impact the blob overshoots, flattens,
springs past round into slightly-tall, settles back, and does this a few times over
roughly half a second. That decaying oscillation is the "QQ" feel, and it is
produced by the physics rather than authored frame by frame.

Integrated semi-implicitly (update `s_dot` from acceleration, then `s` from the new
`s_dot`), which is stable at the fixed timestep.

### What drives it

- **Airborne.** `s_target = -min(abs(vy) / 1600, 0.32)`. Motion in either vertical
  direction stretches the blob along its axis of travel; at the apex `vy` is zero
  so it rounds out. This is the classic squash-and-stretch rule and it comes for
  free from the velocity, with no state machine.
- **Takeoff.** A velocity impulse `s_dot -= 9.0` at the moment of the jump, so the
  slime visibly pulls itself tall as it leaves the ground.
- **Landing.** A velocity impulse `s_dot += clamp(impact_vy / 900, 0, 1.4) * 14.0`.
  A gentle landing barely wobbles; a fall from the top of a jump splats hard and
  rings for longer. Using an impulse on the *velocity* rather than snapping the
  position is what makes it feel like an impact instead of a cut.
- **Ducking.** `s_target = 0.55` while held, `0.0` when released. The slime squashes
  into the ground softly and springs back up on release — the duck reuses the same
  system, no separate animation.
- **Grounded and idle.** `s_target = 0.0`; the spring settles, and the residual
  perimeter wobble below keeps it from looking dead.

### Shape

Not a plain ellipse. The outline is a closed polygon of 48 vertices placed around
an ellipse of base radii `(RX, RY) = (26, 24)` scaled by `scale_x` / `scale_y`, with
each vertex's radius multiplied by a wobble term:

```
r_mult = 1 + A * sin(3*theta + t*4.0) + 0.6 * A * sin(5*theta - t*2.7)
A = 0.03 + 0.06 * min(1.0, abs(s_dot) / 12.0)
```

The constant part keeps a slow surface ripple alive at rest; the `s_dot`-driven part
makes the surface visibly slosh right after an impact and calm down as the spring
decays. The two different frequencies keep it from looking like a regular pulse.

The slime is anchored at its **feet**: the stored `y` is the bottom of the blob, so
the centre is `y - RY * scale_y`. Squashing therefore spreads the blob sideways
along the ground instead of sinking it through the ground.

### Rendering, back to front

Drawn onto a per-pixel-alpha surface so the body can be translucent like jelly.

1. Afterimages — the same polygon from the last few sampled frames, alpha fading
   from ~45 to ~10 (see `effects.py`).
2. Contact shadow — a flat dark ellipse on the ground line, its width tracking
   `scale_x` and its width and alpha shrinking as the slime rises.
3. Body — the wobbled polygon filled with the palette's body color at alpha ~225.
4. Inner sheen — the same polygon scaled to ~0.72 about a point offset up and left
   of centre, in a lighter tone, giving the blob depth.
5. Specular — a small white ellipse near the upper left, alpha ~150, its size and
   offset scaled by `scale_x` / `scale_y` so the highlight deforms with the body.
6. Outline — the body polygon stroked in the darker outline tone.
7. Face — two dark ellipse eyes at `(±0.35 * RX * scale_x, -0.15 * RY * scale_y)`
   from centre and a small mouth arc, all sized by the same scales, so the face is
   squeezed apart on impact along with everything else.

## `world.py`

### Motion

Speed starts at 320 px/s, gains 8 px/s per second, caps at 780 px/s. Score
accumulates as `speed * dt * 0.06` and is shown as an integer.

Gravity is asymmetric for feel: 2200 px/s² while rising with the jump key held,
3400 px/s² otherwise. Jump impulse is -900 px/s, giving a peak of roughly 184 px
and an airtime of about 0.8 s at a full hold. Releasing the key early while still
rising clamps `vy` to -300 px/s, so tapping gives a short hop.

### Obstacles

Ground obstacles: `small` (18x38), `large` (26x58), and `cluster` (two or three
smalls side by side). Air obstacles: `low`, whose bottom edge sits 34 px above the
ground — above a ducked slime (~31 px tall) but into a standing one (48 px) — and
`high` at 150 px, which only threatens a slime mid-jump.

The spawner picks the next gap as `speed * uniform(0.75, 1.5)` pixels, floored at
`0.85 * speed + 60` px, which is the distance covered during a full jump plus a
margin. The floor is what guarantees every gap is actually clearable at the current
speed; without it the difficulty ramp eventually spawns unavoidable pairs.

Collision is AABB against a hitbox inset a few pixels inside the slime's visual
bounds, so grazes are forgiven. The hitbox width and height derive from
`scale_x` / `scale_y`, which means ducking genuinely shrinks the box rather than
toggling a flag.

### Background

Three parallax layers scrolling at 0.15x, 0.35x, and 1.0x of the world speed:
drifting clouds, rolling hills drawn as overlapping circles, and speckles on the
ground. Each layer recycles its items when they leave the left edge.

## `effects.py`

**Dust.** On landing, emit `6 + int(12 * impact_norm)` particles from the contact
point with outward-and-upward random velocities, their own gravity, a 0.35–0.6 s
life, and a radius that shrinks to zero over that life. A soft landing puffs a
little; a hard one throws a proper cloud.

**Afterimages.** A bounded deque of the last 6 samples of
`(x, y, scale_x, scale_y)`, appended every other frame, drawn only while airborne
or above a speed threshold so the slime does not smear while trundling along.

## `main.py`

State machine over `TITLE`, `PLAYING`, `GAME_OVER`.

- `TITLE` — the slime idles on the ground, breathing via the resting wobble.
  Space/Up starts a run.
- `PLAYING` — the loop above. Space/Up jumps, Down ducks, Esc/Q quits.
- `GAME_OVER` — everything freezes except the slime, which gets one last hard splat
  impulse and wobbles to a stop. R restarts, Esc/Q quits.

High score is read at startup and written on any improvement, to a `.highscore`
file in the project directory holding a single integer. A missing, empty, or
malformed file is treated as a high score of zero and simply overwritten on the
next improvement — it is a convenience, not data worth failing a launch over.
Any other error (an unwritable directory, for instance) is allowed to surface.

## Errors

The only real failure mode is pygame being unable to open a display, e.g. over SSH
with no X server. That surfaces as pygame's own exception; it is caught at the top
of `main()` and re-raised as a `SystemExit` with a readable message naming the
likely cause, in the same spirit as breakout's "terminal too small" check.

## Testing

`pytest` in a dev dependency group. The tests cover pure logic only and never open
a window:

- the spring converges to its target and stays within the clamp after a maximal
  landing impulse
- `scale_x * scale_y == 1` across the full range of `s`
- the spawner's gap floor is never violated across the whole speed range
- a full-height jump clears the tallest ground obstacle at the gap floor
- the hitbox shrinks in height when ducking
- `palette_at` returns the exact endpoints at phase 0 and mid-cycle and stays in
  range in between
