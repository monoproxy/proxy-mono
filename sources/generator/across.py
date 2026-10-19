"""Thickness straight across a stroke at a spot: from the outline point nearest the spot, a ray inward
along the edge's normal to the opposite edge (font units). Spots are given as fractions of the
letter's ink box (x from the left, y from the bottom).

    python3 across.py <font.ttf> <letter> fx,fy [fx,fy ...]
"""
import sys
import numpy as np


def across(gl, glyf, spots):
    import pathops
    from measure import _Flat, raster
    path = pathops.Path(); gl.draw(path.getPen(), glyf)
    path = pathops.simplify(path, fix_winding=True, keep_starting_points=False)
    pen = _Flat(None); path.draw(pen)
    polys = [np.array(p, float) for p in pen.polys]
    A = np.vstack(polys); B = np.vstack([np.roll(p, -1, 0) for p in polys]); D = B - A
    m, mx0, my1 = raster(gl, glyf, 1)
    def inside(q):
        r, c = int(round(my1 - q[1])), int(round(q[0] - mx0))
        return 0 <= r < m.shape[0] and 0 <= c < m.shape[1] and m[r, c]
    x0, x1, y0, y1 = A[:, 0].min(), A[:, 0].max(), A[:, 1].min(), A[:, 1].max()
    out = []
    for fx, fy in spots:
        s = np.array([x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)])
        best = None
        for P in polys:
            n = len(P)
            for i in range(n):
                d = np.hypot(*(P[i] - s))
                if best is None or d < best[0]: best = (d, P, i)
        _, P, i = best; n = len(P)
        t_ = P[(i + 1) % n] - P[(i - 1) % n]; L = np.hypot(*t_); nrm = np.array([t_[1], -t_[0]]) / L
        if not inside(P[i] + nrm * 2): nrm = -nrm
        den = nrm[0] * D[:, 1] - nrm[1] * D[:, 0]
        with np.errstate(divide='ignore', invalid='ignore'):
            tt = ((A[:, 0] - P[i][0]) * D[:, 1] - (A[:, 1] - P[i][1]) * D[:, 0]) / den
            uu = ((A[:, 0] - P[i][0]) * nrm[1] - (A[:, 1] - P[i][1]) * nrm[0]) / den
        hit = (tt > 4) & (uu >= 0) & (uu <= 1)
        out.append(float(tt[hit].min()) if hit.any() else None)
    return out


if __name__ == '__main__':
    from fontTools.ttLib import TTFont
    f = TTFont(sys.argv[1]); g = f['glyf']; n = f.getBestCmap()[ord(sys.argv[2])]
    spots = [tuple(float(v) for v in a.split(',')) for a in sys.argv[3:]]
    print([round(v) if v else None for v in across(g[n], g, spots)])
