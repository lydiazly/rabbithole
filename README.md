# rabbithole

**摸鱼小游戏。** 等待 AI agent 的过程中轻松一下。

**Games for slacking off.** Something to do while an AI agent is thinking.

![Mochi Dash](mochi-dash.png)

推荐 **[mochi-dash](mochi-dash/README.md)**：比小恐龙丰富一丢丢的色彩和手感。不同角色、不同场景，
难度完全没有区别 —— 选什么看我心情！没有复杂的玩法，也没有终点。摸鱼时拒绝压力。

Start with **[mochi-dash](mochi-dash/README.md)**: a bit more colour and a bit
more feel than the dino. Four characters, two places to run, and not one of them
is any harder than another — pick whichever you are in the mood for. Nothing to
learn, nowhere to get to, and nothing at stake while you are meant to be working.

Play it in a browser, no install: <https://lydiazly.github.io/rabbithole/>

## Playing

Each game is a self-contained [uv](https://docs.astral.sh/uv/) project in its own
directory. `play` finds them, so nothing needs listing anywhere:

```sh
./play           # pick from a menu
./play snake     # start one directly
```

`R` plays again and `Q` quits, in all of them.

| game | | |
|---|---|---|
| [mochi-dash](mochi-dash/README.md) | a window | endless runner, jump and duck |
| [snake](snake/README.md) | terminal | eat, grow, don't bite yourself |
| [breakout](breakout/README.md) | terminal | clear the bricks, three lives |

## Playing without a checkout

The terminal games are pure standard library, so there is nothing to install:

```sh
uvx --from "git+https://github.com/lydiazly/rabbithole#subdirectory=snake" snake
```

Mochi Dash plays in the browser at the link above, built by
`.github/workflows/pages.yml` on every push to `main` (Pages source: GitHub
Actions). It carries no assets, so the download is small; the CPython and pygame
runtime comes from the pygame-web CDN at load time.

## Adding a game

Drop in a subdirectory with a `pyproject.toml` that declares a
`[project.scripts]` entry, and `play` picks it up with no edit. A game that draws
in a window says so, and is then started in the background so the terminal comes
straight back:

```toml
[tool.rabbithole]
launch = "windowed"
```

The default is the terminal, which is the screen for the curses games: they hold
it until they exit, because detaching one from its tty kills it. A backgrounded
game's output goes to `~/Library/Logs/rabbithole/` on macOS and
`$XDG_STATE_HOME/rabbithole/` (usually `~/.local/state`) elsewhere.
