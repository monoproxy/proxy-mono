"""Arch joins on m n h r u, cut back to Geist Mono's proportions. Usage: joins.py <in> <out> <wght or stem>
Runs after az.py on each static master (and before vf.py). Proxy's lowercase is Geist Mono extrapolated past
its Bold to our stems, which left a heavy wedge where each arch leaves its stem (n at 700: join 0.70 of the
stem, Geist's own 0.41). Each join is cut until its neck, the widest stroke that still links stem and arch,
measured by erosion, equals Geist's ratio at that weight. Measuring the neck means a cut can never reach the
counter and leave a hairline. Only on-curve notch points and the arch's first off-curve move (n and h also
lower their second off-curve by 0.3 x the cut, or the arch top goes flat), so masters stay point-compatible.
Danny approved this 6 Oct 2026 (n/h 30% variant). m at 700-900 and r at 800-900 stop short of the target:
their counters are too narrow to cut further without redrawing."""
import sys
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union

# Geist Mono n: neck / stem, measured the same way from src/GeistMono.ttf instances
GEIST = {100: .587, 200: .510, 300: .472, 400: .475, 500: .439, 600: .418, 700: .409, 800: .401, 900: .397}
# notch on-curve points, arch off-curve, direction (-1 cut down from the top, +1 up from the baseline)
SPEC = {'m': ([3, 4], 5, -1), 'n': ([3, 4], 5, -1), 'h': ([3, 4], 5, -1), 'r': ([9, 10], 11, -1), 'u': ([17, 18], 19, +1)}
ROUND = {'n': 0.3, 'h': 0.3}


class _Flat(BasePen):
    def __init__(s, gs): super().__init__(gs); s.pts = []; s.c = []
    def _moveTo(s, p): s.c = [p]
    def _lineTo(s, p): s.c.append(p)
    def _qCurveToOne(s, a, b):
        p0 = s.c[-1]
        for t in np.linspace(0, 1, 24)[1:]:
            s.c.append(((1-t)**2*p0[0] + 2*t*(1-t)*a[0] + t*t*b[0], (1-t)**2*p0[1] + 2*t*(1-t)*a[1] + t*t*b[1]))
    def _closePath(s): s.pts.append(s.c)


def poly(f, g):
    gs = f.getGlyphSet(); p = _Flat(gs); gs[g].draw(p)
    return unary_union([Polygon(x).buffer(0) for x in p.pts])


def neck(pl, a, b):
    lo, hi = 0, 200
    for _ in range(25):
        r = (lo + hi) / 2; e = pl.buffer(-r)
        ok = not e.is_empty and any(c.buffer(r).contains(Point(a)) and c.buffer(r).contains(Point(b))
                                    for c in getattr(e, 'geoms', [e]))
        lo, hi = (r, hi) if ok else (lo, r)
    return 2 * lo


def probes(ch, c):
    # a point deep in the stem and one in the arch (or bowl), which the neck must connect
    if ch == 'u': return ((c[13][0] + c[14][0]) / 2, 250), (c[0][0] + 20, c[0][1] + 15)
    if ch == 'r': return ((c[3][0] + c[8][0]) / 2, 300), (c[13][0] - 30, c[13][1] - 15)
    top = max(y for x, y in c[4:10]); apex = [p for p in c[4:10] if p[1] == top][0][0]
    return ((c[1][0] + c[2][0]) / 2, 150), (apex, top - 15)


def cut(c0, ch, d):
    idx, off, s = SPEC[ch]; c = list(c0)
    for i in idx: c[i] = (c[i][0], c[i][1] + s * d)
    c[off] = (c[off][0], round(c[off][1] + s * d * 80 / 130))
    if ch in ROUND: c[6] = (c[6][0], round(c[6][1] + s * d * ROUND[ch]))
    return c


STEM2W = {46: 100, 68: 200, 96: 300, 110: 400, 126: 500, 144: 600, 162: 700, 180: 800, 197: 900}


def main(src, out, w):
    w = STEM2W.get(w, w)
    f = TTFont(src); f.flavor = None; cm = f.getBestCmap(); gl = f['glyf']
    cn = gl[cm[ord('n')]].getCoordinates(gl)[0]; target = GEIST[w] * (cn[2][0] - cn[1][0])
    for ch in SPEC:
        g = cm[ord(ch)]; c0 = list(gl[g].getCoordinates(gl)[0])
        idx, off, _ = SPEC[ch]
        if ch != 'u' and c0[idx[0]][0] != c0[idx[0] - 1][0]:
            sys.exit(f'joins.py: {ch} outline changed (notch point {idx[0]} is off the stem edge); update SPEC')
        a, b = probes(ch, c0)
        def setd(d):
            cc = gl[g].getCoordinates(gl)[0]
            for i, p in enumerate(cut(c0, ch, d)): cc[i] = p
            pl = poly(f, g); return pl, neck(pl, a, b)
        _, n0 = setd(0); best = 0
        if n0 > target:
            lo, hi = 0, 260
            for _ in range(9):
                m = (lo + hi) / 2; pl, nk = setd(m)
                lo, hi = (m, hi) if pl.is_valid and nk >= target else (lo, m)
            best = round(lo)
        _, nk = setd(best); gl[g].recalcBounds(gl); f['hmtx'][g] = (f['hmtx'][g][0], gl[g].xMin)
        print(f'{w} {ch}: neck {n0:.0f} -> {nk:.0f} (target {target:.0f}), cut {best}')
    f.save(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
