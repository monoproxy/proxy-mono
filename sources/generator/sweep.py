"""Test sweep of the width-and-weight font, every width and weight, on all cores.

    python3 sweep.py ["fonts/variable/ProxyMono[wdth,wght].ttf"]

For each (width, weight) instance and every printable ASCII character, compared with the drawn letter
(width 100, same weight):
  cell      advance is exactly the cell, ink stays inside it
  pieces    the letter is in as many connected pieces as the drawn one
  kinks     no kink (a sharp corner where a curve should run smooth) the drawn letter does not have; a
            corner drawn as one (over 20 degrees) may change angle
  weight    upright strokes and level strokes (median thickness of each, / stem) each within 15% of the
            drawn letter's; split because a wide letter's longer bars would outvote its stems
  turns     no curve tighter than half the drawn letter's tightest
Prints one line per problem and a summary of letters by problem.
"""
import os, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
VF = os.path.join(HERE, '../../fonts/variable/ProxyMono[wdth,wght].ttf')
WIDTHS = [100, 112.5, 125, 137.5, 150]
WEIGHTS = list(range(100, 1000, 100))
CHARS = [chr(c) for c in range(0x21, 0x7f)]


def look(font, name):
    """What the checks need from one glyph of one instance."""
    import numpy as np
    from scipy import ndimage
    from measure import raster, kinks
    from curves import tight_turns
    g = font['glyf']; gl = g[name]
    if gl.isComposite() or gl.numberOfContours <= 0: return None
    m, _, _ = raster(gl, g, 1)
    dt = ndimage.distance_transform_edt(m)
    ridge = (dt == ndimage.maximum_filter(dt, size=3)) & (dt > 3)
    # each centre-line point: upright or level, by which way the stroke runs there (the longer run)
    up, lv = [], []
    H, W = m.shape
    for y, x in zip(*np.where(ridge)):
        l = x
        while l > 0 and m[y, l - 1]: l -= 1
        r = x
        while r < W - 1 and m[y, r + 1]: r += 1
        u = y
        while u > 0 and m[u - 1, x]: u -= 1
        d = y
        while d < H - 1 and m[d + 1, x]: d += 1
        (lv if (d - u) < (r - l) else up).append(2 * dt[y, x])
    gl.recalcBounds(g)
    turns = tight_turns(gl, g, unfold=True, curve_only=True)   # S's drawn folds and the y's trap corners aren't turns
    return {'adv': font['hmtx'][name][0], 'xmin': gl.xMin, 'xmax': gl.xMax,
            'pieces': ndimage.label(m)[1],
            'kinks': dict(kinks(gl, 8.0)),
            'up': float(np.median(up)) if len(up) > 20 else 0.0,
            'lv': float(np.median(lv)) if len(lv) > 20 else 0.0,
            'turn': min((r for r, *_ in turns), default=999.0)}


def instance(args):
    wd, w, vf = args                       # the font travels with the job: workers don't run main()
    sys.path.insert(0, HERE)
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    from wdth import stem_at
    f = instantiateVariableFont(TTFont(vf), {'wght': w, 'wdth': wd})
    cm = f.getBestCmap(); out = {}
    for ch in CHARS:
        n = cm.get(ord(ch))
        if n:
            r = look(f, n)
            if r: r['stem'] = stem_at(w); out[ch] = r
    return (wd, w), out


def main():
    global VF
    if len(sys.argv) > 1: VF = sys.argv[1]
    jobs = [(wd, w, VF) for wd in WIDTHS for w in WEIGHTS]
    with ProcessPoolExecutor(os.cpu_count()) as pool:
        res = dict(pool.map(instance, jobs))
    problems = {}
    def flag(kind, ch, wd, w, msg):
        problems.setdefault(kind, {}).setdefault(ch, []).append(f'{wd}/{w}')
        print(f'{kind:7s} {ch!r:5s} wdth {wd:>5} wght {w}: {msg}')
    for wd in WIDTHS:
        cell = round(700 * wd / 100)
        for w in WEIGHTS:
            here, base = res[(wd, w)], res[(100, w)]
            for ch, r in here.items():
                b = base.get(ch)
                if abs(r['adv'] - cell) > 1: flag('cell', ch, wd, w, f"advance {r['adv']} not {cell}")
                if r['xmin'] < -2 or r['xmax'] > r['adv'] + 2: flag('cell', ch, wd, w, f"ink {r['xmin']}..{r['xmax']} outside 0..{r['adv']}")
                if not b or wd == 100: continue
                if r['pieces'] != b['pieces']: flag('pieces', ch, wd, w, f"{r['pieces']} pieces, drawn {b['pieces']}")
                # a corner the drawn letter has on purpose (over 20 degrees, the &'s waist) may open or close
                # as the letter widens; only a curve that runs smooth as drawn must stay smooth
                new = {p: a for p, a in r['kinks'].items() if b['kinks'].get(p, 0) < 20 and a > b['kinks'].get(p, 0) + 4}
                if new: flag('kinks', ch, wd, w, ', '.join(f'point {p} {a:.0f} deg' for p, a in sorted(new.items())))
                for key, label in (('up', 'upright'), ('lv', 'level')):
                    if not r[key] or not b[key]: continue
                    rs, bs = r[key] / r['stem'], b[key] / b['stem']
                    if abs(rs - bs) / bs > 0.15: flag('weight', ch, wd, w, f"{label} strokes / stem {rs:.2f}, drawn {bs:.2f}")
                if b['turn'] < 900 and r['turn'] < 0.5 * b['turn']: flag('turns', ch, wd, w, f"tightest curve r{r['turn']:.1f}, drawn r{b['turn']:.1f}")
    print('\nsummary')
    for kind, chars in problems.items():
        print(f'  {kind:7s} ' + '  '.join(f'{ch}({len(v)})' for ch, v in sorted(chars.items())))
    if not problems: print('  nothing flagged')


if __name__ == '__main__':
    main()
