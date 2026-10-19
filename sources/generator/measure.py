"""Stroke thickness of a glyph in font units, measured on a raster at 1 unit = 1 pixel.

    python3 measure.py <font.ttf> [glyph ...]      prints the a's end against the middle of its arch

The a's end and the middle of its arch are what a wide a gets wrong first, so they are measured the
same way and compared: the middle is the arch's thickness straight down through its top (where it runs
level, so that is the thickness across it), the end is the arch just before its cut, twice the distance
from its centre line to the nearer edge (the inscribed circle), the median over a stroke's length.
"""
import sys
import numpy as np
from scipy import ndimage
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageDraw


class _Flat(BasePen):
    def __init__(self, gs):
        super().__init__(gs); self.polys = []; self.cur = []
    def _moveTo(self, p): self.cur = [p]
    def _lineTo(self, p): self.cur.append(p)
    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, 17):
            t = i / 16; u = 1 - t
            self.cur.append((u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                             u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]))
    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, 17):
            t = i / 16; u = 1 - t
            self.cur.append((u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0], u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1]))
    def _closePath(self): self.polys.append(self.cur); self.cur = []
    _endPath = _closePath


def raster(glyph, glyf, scale=1):
    """The glyph as a boolean array, row 0 at the top, `scale` pixels per unit; returns (mask, x
    offset, y top) in pixels."""
    # overlapping contours (K's two pieces, Q's tail) are merged first, as the font fills them:
    # filling each contour by turns would cut a hole wherever two overlap
    import pathops
    path = pathops.Path(); glyph.draw(path.getPen(), glyf)
    path = pathops.simplify(path, fix_winding=True, keep_starting_points=False)
    pen = _Flat(None); path.draw(pen)
    pen.polys = [[(x * scale, y * scale) for x, y in p] for p in pen.polys]
    xs = [x for p in pen.polys for x, _ in p]; ys = [y for p in pen.polys for _, y in p]
    x0, y1 = int(min(xs)) - 4, int(max(ys)) + 4; W, H = int(max(xs)) - x0 + 5, y1 - int(min(ys)) + 5
    mask = np.zeros((H, W), bool)
    for p in pen.polys:                      # contours don't overlap here, so XOR gives the holes
        im = Image.new('1', (W, H), 0)
        ImageDraw.Draw(im).polygon([(x - x0, y1 - y) for x, y in p], fill=1)
        mask ^= np.array(im, bool)
    return mask, x0, y1


def a_end_and_middle(glyph, glyf):
    m, x0, y1 = raster(glyph, glyf)
    H, W = m.shape; dt = ndimage.distance_transform_edt(m)
    rows = np.where(m.any(axis=1))[0]; top, bot = rows.min(), rows.max(); xh = bot - top
    # middle: straight down through the arch's top, at the middle of the letter's ink
    cols = np.where(m.any(axis=0))[0]; cx = (cols.min() + cols.max()) // 2
    col = m[:, cx]; r = top
    while not col[r]: r += 1
    s = r
    while col[r]: r += 1
    middle = r - s
    # end: the arch's leftmost part in the upper part of the letter, one to two strokes in from the cut
    upper = np.zeros_like(m); upper[top: top + int(0.45 * xh)] = True
    region = m & upper
    left = np.where(region.any(axis=0))[0].min()
    ridge = (dt == ndimage.maximum_filter(dt, size=3)) & region
    band = np.zeros_like(m); band[:, left + int(0.5 * middle): left + int(1.5 * middle)] = True
    vals = 2 * dt[ridge & band]
    end = float(np.median(vals)) if len(vals) else 0.0
    return round(end), middle


if __name__ == '__main__':
    from fontTools.ttLib import TTFont
    for path in sys.argv[1:]:
        f = TTFont(path); gl = f['glyf']; n = f.getBestCmap()[ord('a')]
        e, mid = a_end_and_middle(gl[n], gl)
        print(f'{path.split("/")[-1]}: a end {e}, middle of arch {mid}, difference {e - mid}')


def profile(glyph, glyf):
    """Thickness all along the strokes: at each point of the centre line (the ridge of the distance to
    the nearest edge), twice that distance, split into level strokes (the run across is taller than
    wide... i.e. the stroke runs sideways) and upright ones. Returns {'level': [...], 'upright': [...]}."""
    m, _, _ = raster(glyph, glyf)
    dt = ndimage.distance_transform_edt(m)
    ridge = (dt == ndimage.maximum_filter(dt, size=3)) & (dt > 4)
    out = {'level': [], 'upright': []}
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
        out['level' if (d - u) < (r - l) else 'upright'].append(2 * dt[y, x])
    return out


def summary(glyph, glyf):
    p = profile(glyph, glyf)
    return {k: tuple(int(round(v)) for v in np.percentile(vs, [10, 50, 90])) if vs else None for k, vs in p.items()}


# the ten places marked on the a (fractions of its ink box, x from the left, y from the bottom)
A_STATIONS = [('arch top', 0.43, 0.92), ('arch upper left', 0.22, 0.88), ('arch end', 0.08, 0.69), ('shoulder', 0.78, 0.72),
              ('bowl top at stem', 0.76, 0.55), ('stem', 0.80, 0.38), ('bowl top left', 0.15, 0.44),
              ('bowl left', 0.05, 0.28), ('bowl bottom left', 0.12, 0.14), ('bowl bottom right', 0.60, 0.13),
              ('leg', 0.97, 0.05)]


# the bowl's top along its length, from just past the turn into its left side (0.15 is the corner,
# covered by 'bowl left') to the stem
BOWL_TOP = [('bowl top %.2f' % fx, fx, 0.44 + 0.16 * (fx - 0.15) / 0.6) for fx in (0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7)]


def at_stations_raster(glyph, glyf, stations=A_STATIONS, scale=2):
    """Thickness at each station, in units: twice the distance to the nearest edge at the centre-line
    point closest to it, on a raster at `scale` pixels per unit (2, so odd thicknesses can show)."""
    m, _, _ = raster(glyph, glyf, scale)
    dt = ndimage.distance_transform_edt(m)
    ridge = (dt == ndimage.maximum_filter(dt, size=3)) & (dt > 4 * scale)
    rows, cols = np.where(m.any(axis=1))[0], np.where(m.any(axis=0))[0]
    t, b, l, r = rows.min(), rows.max(), cols.min(), cols.max()
    ry, rx = np.where(ridge); out = []
    for name, fx, fy in stations:
        px, py = l + fx * (r - l), b - fy * (b - t)
        i = np.argmin((rx - px) ** 2 + (ry - py) ** 2)
        out.append((name, int(round(2 * dt[ry[i], rx[i]] / scale))))
    return out


def kinks(glyph, limit=2.0):
    """On-curve points between two handles where the curve should pass through smoothly: the angle
    (degrees) between the handle in and the handle out, listed when over `limit`."""
    import math
    c, f = glyph.coordinates, glyph.flags; out = []; s = 0
    for e in glyph.endPtsOfContours:
        n = e - s + 1
        for i in range(n):
            a, p, b = s + (i - 1) % n, s + i, s + (i + 1) % n
            if not (f[p] & 1) or (f[a] & 1) or (f[b] & 1): continue
            v1 = (c[p][0] - c[a][0], c[p][1] - c[a][1]); v2 = (c[b][0] - c[p][0], c[b][1] - c[p][1])
            ang = abs(math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1])))
            if ang > limit: out.append((p, round(ang, 1)))
        s = e + 1
    return out


def _segments(glyph, glyf):
    pen = _Flat(None); glyph.draw(pen, glyf)
    a, b = [], []
    for p in pen.polys:
        for i in range(len(p)): a.append(p[i]); b.append(p[(i + 1) % len(p)])
    return np.array(a, float), np.array(b, float)


def _edge_dist(pts, A, B):
    """Distance from each of pts (n, 2) to the nearest outline segment."""
    d = B - A; L2 = np.maximum((d ** 2).sum(1), 1e-12)
    v = pts[:, None, :] - A[None]; t = np.clip((v * d[None]).sum(2) / L2[None], 0, 1)
    q = A[None] + t[..., None] * d[None]
    return np.sqrt(((pts[:, None, :] - q) ** 2).sum(2)).min(1)


def at_stations(glyph, glyf, stations=A_STATIONS, scale=None):
    """Thickness at each station, exact: the centre-line point near it is found on a coarse raster,
    then the largest circle that fits between the edges there is found on the outline itself
    (searched to a quarter unit around that point); its diameter, rounded."""
    m, x0, y1 = raster(glyph, glyf, 2)
    dt = ndimage.distance_transform_edt(m)
    ridge = (dt == ndimage.maximum_filter(dt, size=3)) & (dt > 8)
    rows, cols = np.where(m.any(axis=1))[0], np.where(m.any(axis=0))[0]
    t, b, l, r = rows.min(), rows.max(), cols.min(), cols.max()
    ry, rx = np.where(ridge); A, B = _segments(glyph, glyf); out = []
    g = np.arange(-3, 3.01, 0.25); gx, gy = np.meshgrid(g, g); off = np.stack([gx.ravel(), gy.ravel()], 1)
    for name, fx, fy in stations:
        px, py = l + fx * (r - l), b - fy * (b - t)
        i = np.argmin((rx - px) ** 2 + (ry - py) ** 2)
        c = np.array([(x0 + rx[i]) / 2, (y1 - ry[i]) / 2])     # raster pixels (2 per unit) to units
        cand = c + off; d = _edge_dist(cand, A, B); k = d.argmax()   # widest within 3 units: no drifting
                                                                        # into a join, where circles grow
        out.append((name, int(round(2 * d[k]))))
    return out
