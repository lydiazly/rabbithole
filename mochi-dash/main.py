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
