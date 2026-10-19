"""Apex thickness of a letter's curves: the stroke straight down through the top of its top curve and
straight up through the bottom of its bottom curve (s, S, o, c, e...), in font units.

    python3 apex.py <font.ttf> <letters>
"""
import sys
import numpy as np


def apexes(gl, glyf):
    """(top thickness, bottom thickness, x of top apex, x of bottom apex, inner y under the top, inner y
    over the bottom), measured on the outline: the top apex is the outline's highest point, the stroke
    there runs from it straight down to the next edge; likewise at the lowest point, straight up."""
    import pathops
    from measure import _Flat
    path = pathops.Path(); gl.draw(path.getPen(), glyf)
    path = pathops.simplify(path, fix_winding=True, keep_starting_points=False)
    pen = _Flat(None); path.draw(pen)
    pts = np.array([p for poly in pen.polys for p in poly], float)
    A = pts; B = np.array([poly[(i + 1) % len(poly)] for poly in pen.polys for i in range(len(poly))], float)
    def cross_y(x):                                          # every y where the outline crosses x
        ys = []
        for (ax, ay), (bx, by) in zip(A, B):
            if (ax - x) * (bx - x) <= 0 and ax != bx:
                ys.append(ay + (x - ax) * (by - ay) / (bx - ax))
        return sorted(ys)
    top = pts[pts[:, 1].argmax()]; bot = pts[pts[:, 1].argmin()]
    yt = cross_y(top[0]); yb = cross_y(bot[0])
    t_in = max(y for y in yt if y < top[1] - 1); b_in = min(y for y in yb if y > bot[1] + 1)
    return top[1] - t_in, b_in - bot[1], top[0], bot[0], t_in, b_in


if __name__ == '__main__':
    from fontTools.ttLib import TTFont
    f = TTFont(sys.argv[1]); g = f['glyf']; cm = f.getBestCmap()
    for ch in sys.argv[2]:
        t, b, *_ = apexes(g[cm[ord(ch)]], g)
        print(f'{ch}: top {t:.0f}  bottom {b:.0f}')


def side_apexes(gl, glyf):
    """(left, right): the stroke straight across at the outline's leftmost point (the upper curve's
    left side in s and S) and at its rightmost point below the middle (the lower curve's right side)."""
    import pathops
    from measure import _Flat
    path = pathops.Path(); gl.draw(path.getPen(), glyf)
    path = pathops.simplify(path, fix_winding=True, keep_starting_points=False)
    pen = _Flat(None); path.draw(pen)
    pts = np.array([p for poly in pen.polys for p in poly], float)
    A = pts; B = np.array([poly[(i + 1) % len(poly)] for poly in pen.polys for i in range(len(poly))], float)
    def cross_x(y):
        xs = []
        for (ax, ay), (bx, by) in zip(A, B):
            if (ay - y) * (by - y) <= 0 and ay != by:
                xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
        return sorted(xs)
    mid = (pts[:, 1].max() + pts[:, 1].min()) / 2
    up = pts[pts[:, 1] > mid]; lo = pts[pts[:, 1] < mid]
    L = up[up[:, 0].argmin()]; R = lo[lo[:, 0].argmax()]
    xl = cross_x(L[1]); xr = cross_x(R[1])
    return min(x for x in xl if x > L[0] + 1) - L[0], R[0] - max(x for x in xr if x < R[0] - 1), L[1], R[1]
