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
 * Get the player past pygbag's start gate, and past it before they have seen it.
 *
 * pygbag will not start the game until a gesture has been recorded, because
 * audio needs one, and it cannot be talked out of that: the browsers require it.
 * How it waits depends on which browser it thinks it has. On anything that is
 * not Safari it unlocks itself by playing a silent clip. For Safari -- and
 * feat_snd() treats any iPhone as Safari -- it puts one listener on `window` for
 * a `click` and holds the loop until that fires, showing "Ready to start !
 * Please click/touch page" in the meantime.
 *
 * Two things go wrong with that, and one listener fixes both.
 *
 * On iOS the tap does not reliably arrive. WebKit synthesises the click that
 * bubbles to document and window only when it considers the thing under the
 * finger clickable, and here that is a message box, a canvas and the page behind
 * them. The gesture happens and the gate never hears it, so the page sits on
 * that message however many times it is tapped. Reported from an iPhone on iOS
 * 17; passing the tap on as a click is what fixed it.
 *
 * And the gate is armed late -- after several megabytes of runtime have loaded
 * -- so a tap made while waiting is thrown away, and the player is asked for a
 * second one to no purpose. Since a gesture is a fact about the page rather than
 * about the moment, the first one is remembered and replayed as soon as there is
 * something listening. Anyone who touches the page while it loads never sees the
 * message at all; anyone who does not still gets it, which is the point of it.
 *
 * The click is dispatched from the gesture as well as from the poll, so on iOS
 * the flag is set inside the handler rather than a tick later. What unlocks the
 * audio is the player's own tap either way: activation is sticky, and this only
 * ever sets a flag that pygbag is already watching.
 */
let gestured = false;

function release() {
    // MM is the loader's media manager. It exists before it is armed, so the
    // absent-UME case has to keep trying rather than give up on the first look.
    if (window.MM && !window.MM.UME) dispatchEvent(new MouseEvent("click"));
}

function remember() {
    gestured = true;
    release();
}

for (const type of ["pointerdown", "touchend", "keydown"]) {
    addEventListener(type, remember, { passive: true });
}

const waiting = setInterval(() => {
    if (window.MM && window.MM.UME) {
        clearInterval(waiting);
        for (const type of ["pointerdown", "touchend", "keydown"]) {
            removeEventListener(type, remember);
        }
        return;
    }
    if (gestured) release();
}, 100);
