"""A minimal terminal snake game built on the curses standard library."""

import curses
import locale
import random
from collections import deque

CELL_W = 2  # each grid cell spans two columns so cells look roughly square
MIN_GRID_W = 20
MIN_GRID_H = 10

BASE_TICK_MS = 180  # delay between steps at the start of a game
MIN_TICK_MS = 60
SPEEDUP_MS = 4  # delay removed per food eaten

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)
KEY_TO_DIRECTION = {
    curses.KEY_UP: UP,
    curses.KEY_DOWN: DOWN,
    curses.KEY_LEFT: LEFT,
    curses.KEY_RIGHT: RIGHT,
    ord("w"): UP,
    ord("s"): DOWN,
    ord("a"): LEFT,
    ord("d"): RIGHT,
}
QUIT_KEYS = (ord("q"), ord("Q"), 27)  # 27 is Esc

BLOCK = "█" * CELL_W


def init_colors():
    """Return (snake_attr, food_attr), falling back to plain attributes."""
    if not curses.has_colors():
        return curses.A_REVERSE, curses.A_BOLD
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    return curses.color_pair(1), curses.color_pair(2)


def spawn_food(grid_w, grid_h, occupied):
    """Pick a random free cell, or None when the board is full."""
    free = [
        (x, y)
        for y in range(grid_h)
        for x in range(grid_w)
        if (x, y) not in occupied
    ]
    return random.choice(free) if free else None


def draw(stdscr, snake, food, score, snake_attr, food_attr):
    stdscr.erase()
    stdscr.border()
    stdscr.addstr(0, 2, f" Score: {score} ")
    fx, fy = food
    stdscr.addstr(fy + 1, fx * CELL_W + 1, BLOCK, food_attr)
    for x, y in snake:
        stdscr.addstr(y + 1, x * CELL_W + 1, BLOCK, snake_attr)
    stdscr.refresh()


def play(stdscr, grid_w, grid_h, snake_attr, food_attr):
    """Run one round. Returns (score, quit_requested)."""
    head = (grid_w // 2, grid_h // 2)
    snake = deque([head])
    occupied = {head}
    direction = RIGHT
    score = 0
    tick_ms = BASE_TICK_MS
    food = spawn_food(grid_w, grid_h, occupied)

    while True:
        draw(stdscr, snake, food, score, snake_attr, food_attr)

        stdscr.timeout(tick_ms)
        key = stdscr.getch()
        if key in QUIT_KEYS:
            return score, True
        new_direction = KEY_TO_DIRECTION.get(key)
        # Ignore a 180-degree turn: it would drive the head into the neck.
        if new_direction and new_direction != (-direction[0], -direction[1]):
            direction = new_direction

        nx, ny = head[0] + direction[0], head[1] + direction[1]
        if not (0 <= nx < grid_w and 0 <= ny < grid_h):
            return score, False

        grows = (nx, ny) == food
        if not grows:
            # Free the tail before the self-collision check so the head may
            # legally move into the cell the tail is vacating this step.
            occupied.discard(snake.pop())
        if (nx, ny) in occupied:
            return score, False

        head = (nx, ny)
        snake.appendleft(head)
        occupied.add(head)

        if grows:
            score += 1
            tick_ms = max(MIN_TICK_MS, tick_ms - SPEEDUP_MS)
            food = spawn_food(grid_w, grid_h, occupied)
            if food is None:  # board filled: nothing left to eat
                return score, True


def show_game_over(stdscr, score):
    """Draw the end-of-round banner. Returns True if the player wants another round."""
    max_y, max_x = stdscr.getmaxyx()
    lines = [f"Game over - score {score}", "r: play again    q: quit"]
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
    snake_attr, food_attr = init_colors()

    max_y, max_x = stdscr.getmaxyx()
    grid_w = (max_x - 2) // CELL_W
    grid_h = max_y - 2
    if grid_w < MIN_GRID_W or grid_h < MIN_GRID_H:
        raise SystemExit(
            f"Terminal too small: need at least "
            f"{MIN_GRID_W * CELL_W + 2}x{MIN_GRID_H + 2}, got {max_x}x{max_y}"
        )

    while True:
        score, quit_requested = play(stdscr, grid_w, grid_h, snake_attr, food_attr)
        if quit_requested or not show_game_over(stdscr, score):
            return


def main():
    locale.setlocale(locale.LC_ALL, "")  # required for the block-drawing character
    curses.wrapper(run)


if __name__ == "__main__":
    main()
