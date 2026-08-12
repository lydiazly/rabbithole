# /// script
# dependencies = [
#  "pygame-ce",
# ]
# ///
#
# That block is load-bearing, and its absence fails in a way that points nowhere
# near it. pygbag decides which WebAssembly wheels to fetch by reading this file:
# the dependencies here if they are declared, otherwise whatever this file itself
# imports. This file imports a package, not pygame, so with the block gone pygbag
# fetches no wheel, `import pygame` finds the empty placeholder it registers, and
# the game dies on the first line that touches a pygame attribute -- an
# AttributeError deep in sprites.py, on a line that has been correct all along.
"""Web entry point.

pygbag insists on a top-level main.py -- it is the script it hands to the page's
event loop -- so this exists to satisfy that and to be the one file that says
"the browser starts here". Everything it needs is in the package next to it.

Playing on a desktop goes through the `mochi-dash` console script instead; both
end up awaiting the same coroutine.
"""

import asyncio

from mochi_dash.main import play

asyncio.run(play())
