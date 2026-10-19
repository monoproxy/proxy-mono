"""Stem gate: is every stroke of a letter one thickness? Run before showing any letter.

    python3 stem_gate.py <font.ttf> <weight> <letters>     (a static master, e.g. a width-150 master)

From every point of the outline, the thickness straight across the stroke (a ray inward along the
edge's normal to the opposite edge); rays longer than 1.6 targets run along a stroke, not across it,
and are left out. Split into upright and level by the ray's direction, and reported as
10th / 50th / 90th percentile against the target: the stem for upright strokes, the o's ring for level
ones. PASS when the 10th and 90th percentiles are both within 5% of the target. Points within half a stem of a
corner or join are left out (a ray from there cuts through the join, not across one stroke).
"""
import sys
import numpy as np
from scipy import ndimage
from measure import raster
from wdth import stem_at


def strokes(gl, glyf, near=50):
    """Thickness across the stroke from every point of the outline: a ray inward along the edge's
    normal to the opposite edge (the outline flattened; overlapping contours merged first, as the font
    fills them). Rays that run along a stroke rather than across it (from a cut end, into a join) come
    out much longer than any stroke and are dropped by the caller's limit. Level if the ray runs up or
    down, upright if it runs sideways."""
    import pathops
    from measure import _Flat
    path = pathops.Path(); gl.draw(path.getPen(), glyf)
    path = pathops.simplify(path, fix_winding=True, keep_starting_points=False)
    pen = _Flat(None); path.draw(pen)
    A = np.array([p for poly in pen.polys for p in poly], float)
    B = np.array([poly[(i + 1) % len(poly)] for poly in pen.polys for i in range(len(poly))], float)
    D = B - A; up, lv = [], []
    from measure import raster
    m, mx0, my1 = raster(gl, glyf, 1)
    def inside(q):
        r, cc = int(round(my1 - q[1])), int(round(q[0] - mx0))
        return 0 <= r < m.shape[0] and 0 <= cc < m.shape[1] and m[r, cc]
    # corners: outline points where the direction turns more than 25 degrees between neighbours; a ray
    # from within half a stroke of one cuts through a join or a corner, not straight across a stroke
    corners = []
    for poly in pen.polys:
        P = np.array(poly, float); n = len(P)
        for i in range(n):
            u, v = P[i] - P[i - 1], P[(i + 1) % n] - P[i]
            nu, nv = np.hypot(*u), np.hypot(*v)
            if nu > 1e-9 and nv > 1e-9 and np.dot(u, v) / (nu * nv) < np.cos(np.radians(25)): corners.append(P[i])
    corners = np.array(corners) if corners else np.zeros((0, 2))
    for poly in pen.polys:
        P = np.array(poly, float); n = len(P)
        for i in range(0, n, 1):
            if len(corners) and np.hypot(*(corners - P[i]).T).min() < near: continue
            a, b = P[(i - 1) % n], P[(i + 1) % n]; d = b - a; L = np.hypot(*d)
            if L < 1e-9: continue
            o = P[i]; nrm = np.array([d[1], -d[0]]) / L
            if not inside(o + nrm * 2): nrm = -nrm                # whichever way is into the ink
            # ray o + t*nrm against every segment
            den = nrm[0] * D[:, 1] - nrm[1] * D[:, 0]
            with np.errstate(divide='ignore', invalid='ignore'):
                t = ((A[:, 0] - o[0]) * D[:, 1] - (A[:, 1] - o[1]) * D[:, 0]) / den
                u = ((A[:, 0] - o[0]) * nrm[1] - (A[:, 1] - o[1]) * nrm[0]) / den
            hit = (t > 4) & (u >= 0) & (u <= 1) & np.isfinite(t)     # not the edge it starts on
            if not hit.any(): continue
            tt = t[hit].min()
            (lv if abs(nrm[1]) > abs(nrm[0]) else up).append(tt)
    return np.array(up), np.array(lv)


def report(gl, glyf, stem, ring):
    up, lv = strokes(gl, glyf, near=0.5 * stem); out = []; ok = True
    for name, vals, target in (('upright', up, stem), ('level', lv, ring)):
        vals = vals[vals < 1.6 * target]                     # along a stroke, not across it
        if len(vals) < 10: out.append(f'{name} -'); continue
        p10, p50, p90 = np.percentile(vals, [10, 50, 90])
        good = abs(p10 - target) <= 0.05 * target and abs(p90 - target) <= 0.05 * target
        ok &= good
        out.append(f'{name} {p10:.0f}/{p50:.0f}/{p90:.0f} vs {target:.0f}{"" if good else " FAIL"}')
    return ok, '  '.join(out)


if __name__ == '__main__':
    from fontTools.ttLib import TTFont
    f = TTFont(sys.argv[1]); g = f['glyf']; w = float(sys.argv[2]); cm = f.getBestCmap()
    o = g[cm[ord('o')]]; c = o.coordinates; e = o.endPtsOfContours[0]
    ring = max(y for x, y in c[:e + 1]) - max(y for x, y in c[e + 1:])
    for ch in sys.argv[3]:
        ok, txt = report(g[cm[ord(ch)]], g, stem_at(w), ring)
        print(f'{"PASS" if ok else "FAIL"} {ch}  {txt}')
