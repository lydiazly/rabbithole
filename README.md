# rabbithole

Small games. Each is a self-contained [uv](https://docs.astral.sh/uv/) project in
its own directory.

```sh
./play           # pick from a menu
./play snake     # start one directly
```

`R` plays again and `Q` quits, in all of them.

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
further back buying reaction time. `M` reopens the menu, which also switches
the sound off.

It opens easy — nothing but single cacti while you find the jump — and adds
taller ones, clusters and flyers as it speeds up, spacing them a little tighter
as it goes. A point per obstacle cleared, more for the tall ones, and every
twenty points earns a **dash**: a few seconds of running faster and flattening
anything in the way instead of dying to it. Your best run is saved.
