# Proxy Mono: working rules

## Builds: parallel, cached, timed

- Use all 10 cores. Build the nine weights as parallel processes, and run any search inside a glyph
  (the a's stroke search in `sources/generator/wdth.py`) with a process pool: measure every candidate
  move at once and take the best, never one move at a time on one core.
- Cache slow results. The a's searched outline is kept in `build/cache/`, keyed by the outline it
  starts from, the weight and its targets, and reused. Delete the cache to force a fresh search.
- Say how long a build will take before starting it.

## Show every fix

- After ANY change to a letter, show Danny the result in high resolution (large render, every weight it
  affects) before moving on to anything else. Look at it first yourself; never send a render you have not
  checked, and never move on without showing.

## Measure before showing

- Before showing a redrawn or rebuilt letter, run `sources/generator/stem_gate.py` (thickness straight
  across every stroke, from the outline) and `measure.py`, and make the numbers match: the end of a
  stroke against the middle of its curve, upright strokes against the stem, level strokes against the
  o's ring. Show the numbers with the picture.
- Check every weight that is shown, and the masters either side of any in-between weight: one bad
  master breaks every weight blended from it. `weight_scan` (stroke thickness ÷ stem at all nine
  width-150 masters) finds letters that jump between weights.
- Measure joins too: no kinks where an edge meets a curve, no ink traps, no letter split in pieces.

## Width axis (wdth 100 to 150)

- The shipped font is `fonts/variable/ProxyMono[wdth,wght].ttf` (what Google Fonts gets; `make build`).
  Width 100 is the weight font (`build/variable/ProxyMono[wght].ttf`, an intermediate), unchanged.
  Width 150 masters: `wdth.py 150 <wght>` then `wide.py`, all weights in parallel; merged by
  `vf_wdth.py`, which also sets names, STAT (width names from Google's axis registry), weight-only
  named instances at width 100, and the Google Fonts post-pass.
- Test sweep (every width, weight and ASCII letter against the drawn letter, 10 cores, ~15 s):
  `python3 sources/generator/sweep.py`. Google checks: `make test`.
- Every width-150 letter keeps the drawn letter's points (same contours and point order), or it
  cannot interpolate with width 100. Even its strokes by moving its own edges (`edge_even`,
  `cross_x`), never by swapping in a differently built outline.
- Strictly monospace: no tracking. 150 is the widest width.
