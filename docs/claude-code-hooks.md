# Letting Claude Code tell you when to play

Part of [rabbithole](../README.md).

The point of the whole thing is the wait, so Claude Code can run the game for
you: it nudges you when a turn is taking a while, and pauses the game the moment
your attention is wanted back.

Three hooks in `~/.claude/settings.json`, each pointing at a small script in
`~/.claude/hooks/`:

| hook | when it fires | what it does |
|---|---|---|
| `UserPromptSubmit` | you send a prompt | starts a 30-second timer, then says "still working — go play" |
| `Stop` | Claude finishes | cancels the timer; pauses the game if it has focus |
| `Notification` | Claude wants you | same, so a permission prompt is never left behind a game |

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "~/.claude/hooks/mochi-turn-watch", "timeout": 5 }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "~/.claude/hooks/mochi-turn-done", "timeout": 5 }] }
    ],
    "Notification": [
      { "hooks": [{ "type": "command", "command": "~/.claude/hooks/mochi-turn-done", "timeout": 5 }] }
    ]
  }
}
```

Nothing above binds the key the nudge names. Point a custom shortcut (GNOME:
Settings › Keyboard) at the full path of `play mochi-dash`. It names `Super+G`
unless `MOCHI_HOTKEY` says otherwise, so set that in the environment Claude Code
starts from. Naming the wrong key is worse than naming none.

Four things keep it out of the way:

- **The timer runs detached.** Claude Code reads a hook's output until every
  holder of the pipe is gone, so a plain background job would stall the turn for
  the whole 30 seconds. `setsid` with stdout closed keeps the turn moving.
- **Notifications are transient.** Each is true only for a moment, so none is
  filed in the desktop's list — otherwise an afternoon of work leaves one stale
  banner per long turn.
- **The pause is a toggle, so it only ever reaches a focused game.** Sent blind,
  `P` would just as happily unpause a game paused on purpose.
- **Every failure is silent.** No display, no `xdotool`, over SSH — each just
  means one of the two channels (desktop notification, tmux status line) is the
  live one. A convenience hook must never break a session.
