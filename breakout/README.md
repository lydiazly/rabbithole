# breakout

Terminal. Part of [rabbithole](../README.md).

```sh
../play breakout     # or ./play breakout from the repository root
```

Slide the paddle with `←`/`→` or `A`/`D`, launch with `space`, and clear all four
rows of bricks. Hitting the ball with the outer third of the paddle angles it
that way, which is the whole of the aiming. Three lives.

`R` plays again, `Q` quits.

Pure standard library, so it also runs with nothing installed:

```sh
uvx --from "git+https://github.com/lydiazly/rabbithole#subdirectory=breakout" breakout
```
