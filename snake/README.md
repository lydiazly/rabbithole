# snake

Terminal. Part of [rabbithole](../README.md).

```sh
../play snake     # or ./play snake from the repository root
```

Steer with the arrow keys or `WASD` and eat the food to grow. Hitting a wall or
your own tail ends the run, and every meal makes you faster.

`R` plays again, `Q` quits.

Pure standard library, so it also runs with nothing installed:

```sh
uvx --from "git+https://github.com/lydiazly/rabbithole#subdirectory=snake" snake
```
