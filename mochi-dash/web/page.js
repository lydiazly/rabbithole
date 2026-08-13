/*
 * The page's own behaviour, injected into the built index.html by restyle.py.
 *
 * One job: the right mouse button ducks, so the browser's context menu must not
 * open on top of the game every time the player crouches. There is no CSS for
 * this and no way to reach it from pygame -- the event is the document's, and
 * only the page can refuse it.
 *
 * On the whole document rather than the canvas, because the canvas is created by
 * the loader after this runs, and a menu opened just off its edge is just as
 * unwelcome. A game page has nothing a context menu is useful for.
 */
addEventListener("contextmenu", (event) => event.preventDefault());
