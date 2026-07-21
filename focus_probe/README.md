# Focus Probe

A tiny local page that watches the usual browser signals for "you left this
tab." Use it when you want to see whether Cloak's Keep selected active is
actually holding.

## Run it

From the Cloak repo root:

```
python focus_probe/server.py
```

Or:

```
python -m focus_probe.server
```

Then open http://127.0.0.1:8765/ in the browser you care about. Brave and Chrome
are the ones worth testing.

## A good test run

1. Start Cloak as admin (`python safe.py`).
2. Open the probe page and click inside it once so the tab is really focused.
3. In Cloak, select that browser window and press **Keep selected active**.
   Wait until the Active column says `KEEP`.
4. Hide some other window if you want, click it, type in it, alt tab around.
5. Watch the probe. With Keep selected active working, the verdict should stay
   **HERE** even while you are busy in the other window. Without it, the page
   flips to **AWAY** as soon as you leave.
6. Come back to the probe tab. It should read **HERE** again, not sit stuck on
   AWAY.

If you click **Unlock audio probe**, that only starts an AudioContext check. It
is not a leave by itself. Hard refresh the page (Ctrl+F5) if you still have an
old copy of the probe open from before.

## What the page watches

* window focus and blur
* visibility (`document.hidden`, `visibilityState`)
* `document.hasFocus()` on a short timer
* page lifecycle bits like pagehide, pageshow, freeze, resume
* timer throttling and requestAnimationFrame fps
* optional AudioContext state after you unlock it
* IdleDetector when the browser allows it

The live verdict cares about hasFocus and visibility. In page focus moves, like
clicking a button on the probe itself, should not mark you AWAY.
