"""A minimal terminal breakout game built on the curses standard library."""

import curses
import locale

MIN_FIELD_W = 40
MIN_FIELD_H = 16

# Input is polled far more often than the ball moves, so the paddle stays
# responsive while the ball itself travels slowly.
INPUT_TICK_MS = 30
BALL_TICK_STEPS = 4  # ball advances one cell every N polls (~120 ms)

PADDLE_W = 10
PADDLE_STEP = 1  # cells per input tick while gliding; speed comes from the tick rate
# A terminal never reports key release, so "held" has to be inferred from auto-repeat,
# which starts only after the OS initial delay (typically 500-660 ms). The first press
# therefore has to coast long enough to bridge that gap, or the paddle visibly stalls
# before the repeats arrive. Once repeats are flowing they are ~30 ms apart, so a much
# shorter window keeps the motion seamless while stopping promptly on release.
PADDLE_GLIDE_TICKS = 24  # ~720 ms, bridges the initial auto-repeat delay
PADDLE_REPEAT_GLIDE_TICKS = 4  # ~120 ms, used once auto-repeat is confirmed

BRICK_W = 5  # BRICK_W - 1 drawn columns plus a one-column gap
BRICK_DRAW_W = BRICK_W - 1
BRICK_ROWS = 4
BRICK_TOP = 1  # leave one empty row below the top wall

LIVES = 3

LEFT_KEYS = (curses.KEY_LEFT, ord("a"), ord("A"))
RIGHT_KEYS = (curses.KEY_RIGHT, ord("d"), ord("D"))
LAUNCH_KEYS = (ord(" "), curses.KEY_UP, ord("w"), ord("W"))
# Esc is deliberately not a quit key: arrow keys arrive as Esc-prefixed
# sequences, and a partially read one would look like a bare Esc while draining.
QUIT_KEYS = (ord("q"), ord("Q"))

BRICK_COLORS = (curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN, curses.COLOR_CYAN)
PADDLE_COLOR = curses.COLOR_MAGENTA  # unused by the bricks, and bright on either background


def init_colors():
    """Return (brick_palette, paddle_attr, ball_attr) for the current terminal.

    The ball keeps the terminal's default foreground so it stays legible on
    both dark and light backgrounds; the paddle gets its own colour, distinct
    from every brick row. Never use A_REVERSE on a solid block: reverse video
    paints the cell in the background colour, which makes the block invisible
    against that same background.
    """
    ball_attr = curses.A_BOLD
    if not curses.has_colors():
        return [curses.A_NORMAL] * BRICK_ROWS, curses.A_BOLD, ball_attr
    curses.start_color()
    curses.use_default_colors()
    for i, color in enumerate(BRICK_COLORS, start=1):
        curses.init_pair(i, color, -1)
    paddle_pair = len(BRICK_COLORS) + 1
    curses.init_pair(paddle_pair, PADDLE_COLOR, -1)
    palette = [curses.color_pair(i % len(BRICK_COLORS) + 1) for i in range(BRICK_ROWS)]
    return palette, curses.color_pair(paddle_pair) | curses.A_BOLD, ball_attr


def build_bricks(field_w):
    """Return the set of (row, col) bricks filling the top of the field."""
    cols = field_w // BRICK_W
    return {(row, col) for row in range(BRICK_ROWS) for col in range(cols)}


def brick_at(bricks, x, y):
    """Return the brick occupying field cell (x, y), or None."""
    row = y - BRICK_TOP
    if not 0 <= row < BRICK_ROWS:
        return None
    if x % BRICK_W == BRICK_W - 1:  # the gap column between two bricks
        return None
    brick = (row, x // BRICK_W)
    return brick if brick in bricks else None


def read_keys(stdscr):
    """Return every key waiting this frame, blocking at most INPUT_TICK_MS.

    Draining matters: auto-repeat can queue several events per frame, and
    handling only one of them per frame leaves the paddle drifting on long
    after the key was released.
    """
    key = stdscr.getch()
    if key == -1:
        return []
    keys = [key]
    stdscr.timeout(0)  # take whatever else already arrived, without waiting
    while (extra := stdscr.getch()) != -1:
        keys.append(extra)
    stdscr.timeout(INPUT_TICK_MS)
    return keys


def bounce_walls(x, y, nx, ny, dx, dy, field_w):
    """Reflect a step off the side walls and the ceiling.

    Runs again after a brick bounce: flipping dy next to the ceiling would
    otherwise push the ball straight through it.
    """
    if not 0 <= nx < field_w:
        dx = -dx
        nx = x + dx
    if ny < 0:
        dy = -dy
        ny = y + dy
    return nx, ny, dx, dy


def resolve_bricks(bricks, x, y, nx, ny, dx, dy):
    """Destroy bricks the step runs into. Returns (dx, dy, destroyed_count).

    Vertical and horizontal neighbours are tested separately so a ball skimming
    along a wall of bricks bounces off the face it actually touched; only when
    neither is occupied does the diagonal cell count as a corner hit.
    """
    destroyed = 0
    above = brick_at(bricks, x, ny)
    beside = brick_at(bricks, nx, y)
    if above:
        bricks.discard(above)
        destroyed += 1
        dy = -dy
    if beside:
        bricks.discard(beside)
        destroyed += 1
        dx = -dx
    if not destroyed:
        corner = brick_at(bricks, nx, ny)
        if corner:
            bricks.discard(corner)
            destroyed += 1
            dx, dy = -dx, -dy
    return dx, dy, destroyed


def draw(stdscr, state, attrs):
    """Repaint the whole field; it is small enough that partial updates buy nothing."""
    palette, paddle_attr, ball_attr = attrs
    stdscr.erase()
    stdscr.border()
    stdscr.addstr(0, 2, f" Score: {state['score']}   Lives: {state['lives']} ")

    for row, col in state["bricks"]:
        stdscr.addstr(
            BRICK_TOP + row + 1, col * BRICK_W + 1, "█" * BRICK_DRAW_W, palette[row]
        )

    field_h = state["field_h"]
    stdscr.addstr(field_h, state["paddle_x"] + 1, "█" * PADDLE_W, paddle_attr)

    ball_x, ball_y = state["ball"]
    stdscr.addstr(ball_y + 1, ball_x + 1, "O", ball_attr)

    if not state["launched"]:
        hint = " space: launch    left/right: move    q: quit "
        stdscr.addstr(field_h + 1, 2, hint[: state["field_w"] - 2])
    stdscr.refresh()


def play(stdscr, field_w, field_h, attrs):
    """Run one round. Returns (score, outcome) where outcome is won/lost/quit."""
    paddle_y = field_h - 1
    state = {
        "field_w": field_w,
        "field_h": field_h,
        "bricks": build_bricks(field_w),
        "paddle_x": (field_w - PADDLE_W) // 2,
        "ball": (0, 0),
        "score": 0,
        "lives": LIVES,
        "launched": False,
    }
    vel = (1, -1)
    countdown = BALL_TICK_STEPS
    glide_dir = 0
    glide_left = 0

    stdscr.timeout(INPUT_TICK_MS)
    while True:
        if not state["launched"]:
            # Park the ball on the paddle until the player launches it.
            state["ball"] = (state["paddle_x"] + PADDLE_W // 2, paddle_y - 1)

        draw(stdscr, state, attrs)
        for key in read_keys(stdscr):
            if key in QUIT_KEYS:
                return state["score"], "quit"
            if key in LEFT_KEYS or key in RIGHT_KEYS:
                direction = -1 if key in LEFT_KEYS else 1
                # Still gliding the same way means auto-repeat has kicked in, so the
                # long bridging window is no longer needed and would only overshoot.
                repeating = glide_left > 0 and direction == glide_dir
                glide_dir = direction
                glide_left = (
                    PADDLE_REPEAT_GLIDE_TICKS if repeating else PADDLE_GLIDE_TICKS
                )
            elif key in LAUNCH_KEYS and not state["launched"]:
                state["launched"] = True
                vel = (1, -1)
                countdown = BALL_TICK_STEPS

        if glide_left:
            glide_left -= 1
            state["paddle_x"] = min(
                field_w - PADDLE_W,
                max(0, state["paddle_x"] + glide_dir * PADDLE_STEP),
            )

        if not state["launched"]:
            continue
        countdown -= 1
        if countdown > 0:
            continue
        countdown = BALL_TICK_STEPS

        x, y = state["ball"]
        dx, dy = vel
        nx, ny = x + dx, y + dy

        nx, ny, dx, dy = bounce_walls(x, y, nx, ny, dx, dy, field_w)

        if ny >= paddle_y and dy > 0:
            if state["paddle_x"] <= nx < state["paddle_x"] + PADDLE_W:
                dy = -1
                ny = paddle_y - 1
                # The outer thirds of the paddle steer the ball sideways.
                offset = nx - state["paddle_x"]
                if offset < PADDLE_W // 3:
                    dx = -1
                elif offset >= PADDLE_W - PADDLE_W // 3:
                    dx = 1
            elif ny >= field_h:  # missed: the ball left the field
                state["lives"] -= 1
                if state["lives"] == 0:
                    return state["score"], "lost"
                state["launched"] = False
                continue

        dx, dy, destroyed = resolve_bricks(state["bricks"], x, y, nx, ny, dx, dy)
        if destroyed:
            state["score"] += destroyed
            nx, ny = x + dx, y + dy
            nx, ny, dx, dy = bounce_walls(x, y, nx, ny, dx, dy, field_w)
            if brick_at(state["bricks"], nx, ny):  # would land inside another brick
                nx, ny = x, y

        state["ball"] = (nx, ny)
        vel = (dx, dy)
        if not state["bricks"]:
            return state["score"], "won"


def show_result(stdscr, score, outcome):
    """Draw the end-of-round banner. Returns True if the player wants another round."""
    max_y, max_x = stdscr.getmaxyx()
    headline = "You cleared the board!" if outcome == "won" else "Game over"
    lines = [f"{headline}  score {score}", "r: play again    q: quit"]
    for i, line in enumerate(lines):
        y = max_y // 2 - len(lines) // 2 + i
        stdscr.addstr(y, max(0, (max_x - len(line)) // 2), line, curses.A_BOLD)
    stdscr.refresh()

    stdscr.timeout(-1)  # block until a key arrives
    curses.flushinp()  # drop keys buffered during play
    return stdscr.getch() in (ord("r"), ord("R"))


def run(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    attrs = init_colors()

    max_y, max_x = stdscr.getmaxyx()
    field_w = max_x - 2
    field_h = max_y - 2
    if field_w < MIN_FIELD_W or field_h < MIN_FIELD_H:
        raise SystemExit(
            f"Terminal too small: need at least "
            f"{MIN_FIELD_W + 2}x{MIN_FIELD_H + 2}, got {max_x}x{max_y}"
        )

    while True:
        score, outcome = play(stdscr, field_w, field_h, attrs)
        if outcome == "quit" or not show_result(stdscr, score, outcome):
            return


def main():
    locale.setlocale(locale.LC_ALL, "")  # required for the block-drawing character
    curses.wrapper(run)


if __name__ == "__main__":
    main()
