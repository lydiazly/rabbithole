# rabbithole

Small games. Each is a self-contained [uv](https://docs.astral.sh/uv/) project in
its own directory.

```sh
./play           # pick from a menu
./play snake     # start one directly
```

In every game, `R` plays again and `Q` quits.

## snake

Terminal. Steer with the arrow keys or `WASD`, eat the food to grow. Hitting a
wall or your own tail ends the run, and every meal makes you faster.

## breakout

Terminal. Slide the paddle with `←`/`→` or `A`/`D`, launch with `space`, and
clear all four rows of bricks. Hitting the ball with the outer third of the
paddle angles it that way. Three lives.

## slime-runner

A window. Endless runner: `space` or `W` jumps, and pressing again in mid-air
adds about half as much height again — the timing is forgiving. `S` flattens the
slime under low flyers, and `A`/`D` shift where it stands — further back buys
reaction time. It only gets faster; your best run is saved.
