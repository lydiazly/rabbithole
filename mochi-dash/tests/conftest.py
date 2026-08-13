"""Headless SDL, set once before any test module is imported.

Several tests open a window, and on a machine without a display -- a CI runner,
a container, an ssh session -- that fails unless SDL is told to use its dummy
backends first. This used to be a `setdefault` repeated inside each of those
tests, which worked only because a test that happened to run earlier had already
set it: reordering the suite, or running one test on its own with `-k`, was
enough to break it on any headless machine.

conftest is imported before the test modules are collected, so setting it here
is the one place that is guaranteed to be early enough.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
