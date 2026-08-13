# rabbithole

Small games. Each is a self-contained [uv](https://docs.astral.sh/uv/) project in
its own directory.

```sh
./play           # pick from a menu
./play snake     # start one directly
```

`R` plays again and `Q` quits, in all of them.

A game that draws in a window says so in its `pyproject.toml`, and `play` starts
it in the background, hands the terminal straight back, and sends anything it
prints to `$TMPDIR/rabbithole-<game>.log`:

```toml
[tool.rabbithole]
launch = "windowed"
```

The default is the terminal, which is the screen for the curses games: they hold
it until they exit, because detaching one from its tty kills it.

## Playing without a checkout

The terminal games are pure standard library, so there is nothing to install:

```sh
uvx --from "git+https://github.com/lydiazly/rabbithole#subdirectory=snake" snake
```

Mochi Dash plays in a browser at <https://lydiazly.github.io/rabbithole/>, built
by `.github/workflows/pages.yml` on every push to `main` (Pages source: GitHub
Actions). It carries no assets, so the download is small; the CPython and pygame
runtime comes from the pygame-web CDN at load time.

## snake

Terminal. Steer with the arrow keys or `WASD`, eat the food to grow. Hitting a
wall or your own tail ends the run, and every meal makes you faster.

## breakout

Terminal. Slide the paddle with `←`/`→` or `A`/`D`, launch with `space`, and
clear all four rows of bricks. Hitting the ball with the outer third of the
paddle angles it that way. Three lives.

## mochi-dash

A window. Endless runner, named for how the characters move. The menu picks a
character and a place to run through — Momo the slime, Coco the cat, Jojo the
bird or Bobo the shiba, in a desert or a snowfield; both choices are looks
only, and neither changes the difficulty. Then `space` or `W` to jump, and again in mid-air for a
second jump worth about half as much height on top; the timing is forgiving,
and the arc flattens at the top so clearing something is not a matter of one
frame. `S` flattens you under low flyers, and `A`/`D` shift where you stand,
further back buying reaction time. `P` pauses — clicking away from the window
pauses too, though coming back does not un-pause, so you land where you left
off. `M` reopens the menu, which also switches the sound off.

It also plays by mouse or touch, which is how the web build works on a phone:
press the sky to jump and hold for a higher one, press the character or the
ground to duck, and press anywhere to get through the menus.

It opens easy — nothing but single cacti while you find the jump — and adds
taller ones, clusters and flyers as it speeds up, spacing them a little tighter
as it goes. Scoring pays for what an obstacle asked of you: a point for a
cactus and two for a tall one, two for a flyer low enough to duck, and nothing
at all for one that sails past overhead. Every twenty points earns a **dash** —
a few seconds of running much faster and flattening whatever is in the way
instead of dying to it. It warns you before it goes, thins the traffic out as it
does, and leaves you a clear screen for two seconds afterwards to find your
footing again. Your best run is saved.
