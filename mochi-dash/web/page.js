/*
 * The page's own behaviour, injected into the built index.html by restyle.py.
 *
 * Two jobs, both of them things only the page can do: the events belong to the
 * document, and there is no way to reach them from pygame.
 */

/*
 * The right mouse button ducks, so the browser's context menu must not open on
 * top of the game every time the player crouches.
 *
 * On the whole document rather than the canvas, because the canvas is created by
 * the loader after this runs, and a menu opened just off its edge is just as
 * unwelcome. A game page has nothing a context menu is useful for.
 */
addEventListener("contextmenu", (event) => event.preventDefault());

/*
 * Let a tap get past pygbag's "ready to start" gate on iOS.
 *
 * pygbag will not start the game until a gesture has been recorded, because
 * audio needs one. How it waits for that gesture depends on the browser: on
 * anything that is not Safari it unlocks itself by playing a silent clip, but
 * for Safari -- and it treats any iPhone as Safari -- it puts a single listener
 * on `window` for a `click` and holds the loop until that listener fires. The
 * page then sits on "Ready to start ! Please click/touch page" for as long as no
 * click reaches the window object.
 *
 * On iOS a tap does not reliably get there. WebKit only synthesises the click
 * that bubbles to document and window when the thing under the finger is
 * something it considers clickable, and the thing under the finger here is a
 * message box, a canvas and the page behind them, none of which qualify. So the
 * gesture happens, the gate never hears about it, and the game never starts --
 * reported from an iPhone on iOS 17, where the page loads fully and then stops
 * on that message however many times it is tapped.
 *
 * A touch listener always fires, so the click is sent on from one. Sending it
 * rather than relying on the CSS workaround alongside this makes it independent
 * of which element was touched. The listener takes itself off once the gate is
 * through, so nothing is dispatched into the running game: pygbag's own handler
 * removes itself at the same moment, which would leave these as clicks with
 * nothing listening -- harmless, but this is not a thing worth doing forever.
 */
addEventListener("touchend", function unblock() {
    if (window.MM && window.MM.UME) {
        removeEventListener("touchend", unblock);
        return;
    }
    dispatchEvent(new MouseEvent("click"));
});
