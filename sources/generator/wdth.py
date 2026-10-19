"""Width prototype: one narrower (or wider) master from the weight variable font, stems held.

    python3 wdth.py <wdth> <weight> <out.ttf>      e.g.  python3 wdth.py 75 400 ProxyMono-Condensed.ttf

A plain horizontal squash would thin every vertical stem by the same ratio. So x is taken from a heavier
instance, picked so its stem times the ratio is the target weight's stem, and y from the target weight
itself (horizontal bars keep their thickness). Both instances come from one variable font, so the points
match one to one. A prototype: m w M W and the joins are not yet tuned for the narrow cell.
"""
import os, sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

CELL = 700
STEMS = [46, 68, 96, 110, 126, 144, 162, 180, 197]   # stem at weight 100..900, as in the Makefile


def stem_at(w):
    i = min(int(w // 100) - 1, 7); k = w / 100 - 1 - i
    return STEMS[i] + k * (STEMS[i + 1] - STEMS[i])


def weight_for(stem):
    for i in range(8):
        if STEMS[i] <= stem <= STEMS[i + 1]:
            return (i + 1) * 100 + 100 * (stem - STEMS[i]) / (STEMS[i + 1] - STEMS[i])
    if stem < STEMS[0]:          # lighter than Thin: carry on the Thin-to-ExtraLight line (see inst_at)
        return 100 + 100 * (stem - STEMS[0]) / (STEMS[1] - STEMS[0])
    raise SystemExit(f'stem {stem:.1f} is outside the weight axis')


DEEP_V = {'M', 'W', 'uni0077'}
# the a at width 150, weight by weight: (station, points moved, axis, thickness). The arch's top is its
# inner edge (10 11 12, together so its top stays level), the bowl's left side its inner edge (47 48 49)
A_TARGETS = {400: [('arch top', (10, 11, 12), 1, 98)],
             700: [('arch top', (10, 11, 12), 1, 120), ('bowl left', (47, 48, 49), 0, 163)],
             900: [('arch top', (10, 11, 12), 1, 140)]}
# (the arch's upper left is set by sliding handle 12 sideways, which keeps the top level)
X_TOWARD_TARGET = {}   # (s used to take x part way toward the target weight: its sides came out up to 1.7 stems)
# drawn corners (an on-curve point between two handles) that the stretch opens up: the &'s notch at point
# 7, left of the waist, turns 92-97 degrees as drawn, but stretching x tips both handles toward level and
# it opened to 121-131 at width 150 (a kink at every in-between width). Bringing it back to the drawn turn
# pulled the curves in and left a dark wedge at the waist at the light weights (Danny), so it is off: the
# corner opening as the letter widens is how a wide & reads. keep_corner stays for a corner that needs it
KEEP_CORNERS = {}


def _quads(pts, on, closed):
    """TrueType quadratic pieces (p0, handle, p2) of a run of points (implied on-points between handles)."""
    n = len(pts); out = []
    for k in range(n) if closed else range(1, n - 1):
        if on[k]: continue
        a, b = (k - 1) % n, (k + 1) % n
        p0 = pts[a] if on[a] else (pts[a] + pts[k]) / 2
        p2 = pts[b] if on[b] else (pts[b] + pts[k]) / 2
        out.append((p0, pts[k], p2))
    return out


def keep_corner(gl, drawn, p, slack=2.0, share=0.5, weigh=30, even=3000):
    """Bring the corner at on-curve point p (between two handles) back to the drawn letter's turn.
    Turning only the handles next to p put an inflection in both curves (the stretch had flattened the
    rest of each curve), and the curves then can't end steep enough without bending into their strokes.
    So the corner itself and every handle from it back to the next on-curve point on either side may move,
    as little as possible, so that
      - the corner turns no more than `slack` degrees past the drawn letter's turn there,
      - each curve's handle polygon still turns one way only, every turn at least `share` of what it was
        (no inflection, the bend kept spread along the curve),
      - the strokes either side keep the drawn letter's thickness: from points along each curve, the
        distance to the counters (the other contours, which don't move) held to the drawn letter's
        (`weigh`: how much a thickness error counts against moving points, both in tens of units),
      - each curve bends as evenly as the stretched one did (`even`: how much a 3-degree miss in its
        tangent, against the stretched curve's plus the correction spread evenly along it, counts),
      - the handles beside the corner no shorter than 20.
    The handle next to each far on-curve point slides only along that point's tangent, so those ends
    keep their direction. Returns (drawn turn, turn now, solved, thickness drawn / before / after)."""
    import math
    import numpy as np
    from scipy.optimize import minimize
    c, d = gl.coordinates, drawn.coordinates; f = gl.flags
    s = 0
    for e in gl.endPtsOfContours:
        if p <= e: break
        s = e + 1
    n = e - s + 1
    def nb(i, k): return s + (i - s + k) % n
    def chain(step):                                  # p, its handles, the next on-curve point
        ix = [p, nb(p, step)]
        while not f[ix[-1]] & 1: ix.append(nb(ix[-1], step))
        return ix
    A, B = chain(-1)[::-1], chain(1)                  # far end ... p   and   p ... far end
    P0 = {i: np.array(c[i], float) for i in A + B}
    def turn(q, ix):                                  # signed turn at each inner point of ix
        out = []
        for i, j, k in zip(ix, ix[1:], ix[2:]):
            u, v = q[j] - q[i], q[k] - q[j]
            out.append(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u @ v)))
        return np.array(out)
    T = np.array([0.25, 0.5, 0.75])
    def along(q, ix):                                 # points along the curve through ix
        pts = []
        for p0, h, p2 in _quads([q[i] for i in ix], [f[i] & 1 for i in ix], False):
            pts += [(1 - t) ** 2 * p0 + 2 * t * (1 - t) * h + t * t * p2 for t in T]
        return np.array(pts)
    def counters(co):                                 # the other contours, flattened to segments
        segs = []; s0 = 0
        for e0 in gl.endPtsOfContours:
            if not s0 <= p <= e0:
                pts = [np.array(co[i], float) for i in range(s0, e0 + 1)]
                for p0, h, p2 in _quads(pts, [f[i] & 1 for i in range(s0, e0 + 1)], True):
                    t = np.linspace(0, 1, 9)[:, None]
                    segs.append((1 - t) ** 2 * p0 + 2 * t * (1 - t) * h + t * t * p2)
            s0 = e0 + 1
        L = np.vstack([np.c_[g[:-1], g[1:]] for g in segs]); return L[:, :2], L[:, 2:]
    def dist(pts, segs):
        a, b = segs; ab = b - a; L2 = np.maximum((ab ** 2).sum(1), 1e-9)
        v = pts[:, None] - a[None]; t = np.clip((v * ab[None]).sum(2) / L2, 0, 1)
        return np.sqrt(((v - t[..., None] * ab[None]) ** 2).sum(2)).min(1)
    def thick(q, segs): return np.r_[dist(along(q, A), segs), dist(along(q, B), segs)]
    want = turn({i: np.array(d[i], float) for i in A + B}, [A[-2], p, B[1]])[0]
    goal = thick({i: np.array(d[i], float) for i in A + B}, counters(d))
    held = counters(c); was = thick(P0, held)
    sw = np.sign(want); ta, tb = turn(P0, A), turn(P0, B)
    free = [p] + A[2:-1] + B[1:-2]                    # the corner and the handles that move freely
    ends = [(A[1], A[0]), (B[-2], B[-1])]             # handle on the far point's tangent, that point
    S = 10.0                                          # the solver works in tens of units
    def unpack(v):
        q = dict(P0); k = 0
        for i in free: q[i] = P0[i] + S * v[k:k + 2]; k += 2
        for h, o in ends:
            t = (P0[h] - P0[o]) / np.linalg.norm(P0[h] - P0[o]); q[h] = P0[h] + S * v[k] * t; k += 1
        return q
    F = np.linspace(0.1, 1, 10)
    def heading(q, ix):                               # tangent direction (degrees) at arc-length fractions F
        pts = []
        for p0, h, p2 in _quads([q[i] for i in ix], [f[i] & 1 for i in ix], False):
            t = np.linspace(0, 1, 21)[:-1, None]; pts.append((1 - t) ** 2 * p0 + 2 * t * (1 - t) * h + t * t * p2)
        pts = np.vstack(pts + [q[ix[-1]][None]]); dd = np.diff(pts, axis=0)
        ang = np.degrees(np.unwrap(np.arctan2(dd[:, 1], dd[:, 0])))
        s_ = np.cumsum(np.hypot(*dd.T)); s_ = (s_ - s_[0] / 2) / s_[-1]
        return np.interp(F, s_, ang)
    # the bend along each curve as the stretch left it, plus the corner's correction growing evenly from
    # none at the far end to half of it at the corner: the stretched curves bend evenly, and the fit
    # otherwise bunched the whole change up beside the corner (a straight run, then a tight turn)
    fix = want - turn(P0, [A[-2], p, B[1]])[0]
    aim = (heading(P0, A) - fix / 2 * F, heading(P0, B[::-1]) + fix / 2 * F)
    def bend(q): return np.r_[heading(q, A) - aim[0], heading(q, B[::-1]) - aim[1]]
    def cost(v):                                      # movement, thickness off the drawn letter's, bend
        q = unpack(v)
        return v @ v + weigh * (((thick(q, held) - goal) / S) ** 2).sum() + even * ((bend(q) / 3) ** 2).sum()
    nv = 2 * len(free) + len(ends)
    cons = [{'type': 'ineq', 'fun': lambda v: slack - sw * (turn(unpack(v), [A[-2], p, B[1]])[0] - want)},
            {'type': 'ineq', 'fun': lambda v: turn(unpack(v), A) * np.sign(ta) - share * np.abs(ta)},
            {'type': 'ineq', 'fun': lambda v: turn(unpack(v), B) * np.sign(tb) - share * np.abs(tb)},
            # handles beside the corner no shorter than 20 (rounding a short one swings its angle)
            {'type': 'ineq', 'fun': lambda v: np.array([np.linalg.norm(unpack(v)[i] - unpack(v)[p]) for i in (A[-2], B[1])]) - 20}]
    def fits(v): return all((c_['fun'](v) >= -0.05).all() for c_ in cons)
    # least movement first (the solver finds it reliably), then thickness weighed in from there; the
    # second is kept only if it still meets every condition
    r = minimize(lambda v: v @ v, np.zeros(nv), constraints=cons, method='SLSQP', options={'maxiter': 1000, 'ftol': 1e-9})
    r2 = minimize(cost, r.x, constraints=cons, method='SLSQP', options={'maxiter': 1000, 'ftol': 1e-9})
    if fits(r2.x): r = r2
    q = unpack(r.x)
    for i in A + B:
        if i not in (A[0], B[-1]): c[i] = (round(q[i][0]), round(q[i][1]))
    q = {i: np.array(c[i], float) for i in A + B}
    return (round(float(want), 1), round(float(turn(q, [A[-2], p, B[1]])[0]), 1), bool(r.success),
            np.round(goal).astype(int).tolist(), np.round(was).astype(int).tolist(),
            np.round(thick(q, held)).astype(int).tolist())


def hstem_of(o):
    """Thickness of the O's ring at the top: outer top minus the counter's top, at the centre line."""
    c = o.coordinates; e = o.endPtsOfContours[0]
    outer = max(y for x, y in c[:e + 1]); inner = max(y for x, y in c[e + 1:])
    return outer - inner


def strokes(pts, gl):
    """Each straight edge longer than 150 (on-curve to on-curve) paired with the nearest edge parallel
    to it (within 6 degrees) that it overlaps: (angle from vertical, thickness across). Sorted, so the
    same glyph measured in two instances gives matching lists."""
    import math
    E = []; s = 0
    for e in gl.endPtsOfContours:
        for i in range(s, e + 1):
            j = s if i == e else i + 1
            if gl.flags[i] & 1 and gl.flags[j] & 1:
                a, b = pts[i], pts[j]
                if math.dist(a, b) > 150: E.append((i, a, b))
        s = e + 1
    out = []
    for i, a, b in E:
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); ang = math.degrees(math.atan2(dy, dx)) % 180
        if min(ang, 180 - ang) < 10: continue            # horizontals keep the target's y; skip
        nx, ny = -dy / L, dx / L; best = None
        for i2, c, d in E:
            if i2 == i: continue
            a2 = math.degrees(math.atan2(d[1] - c[1], d[0] - c[0])) % 180
            if min(abs(a2 - ang), 180 - abs(a2 - ang)) > 6: continue
            mid = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
            t = abs((mid[0] - a[0]) * nx + (mid[1] - a[1]) * ny)
            u = ((mid[0] - a[0]) * dx + (mid[1] - a[1]) * dy) / L
            if 0 <= u <= L and t > 20 and (best is None or t < best): best = t
        if best: out.append((round(abs(90 - ang)), best))
    return sorted(out)


def set_diagonal(f, t):
    """The 4's diagonal flattens when stretched and comes out thinner than its stem (101 against 161 at
    150 Bold). Move the counter's diagonal edge (its last contour, points 0 and 2) along the outer
    edge's normal so the stroke is `t` thick: Bold's own diagonal is 0.76 of the stem."""
    import math
    c = f.coordinates; s = f.endPtsOfContours[-2] + 1
    a, b = c[3], c[4]                                   # outer diagonal edge
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); nx, ny = dy / L, -dx / L
    def dist(p): return (p[0] - a[0]) * nx + (p[1] - a[1]) * ny
    for i in (s, s + 2):
        d = dist(c[i]); m = t - d
        # slide along the counter's horizontal or vertical edge so the other edges stay square
        if i == s: c[i] = (round(c[i][0] + m / nx), c[i][1])
        else: c[i] = (c[i][0], round(c[i][1] + m / ny))


def thin_slash(z, t):
    """The zero's slash (its last contour, a parallelogram) stretched flat reads heavier than the ring
    (a shallow stroke is thicker across than its source). Squeeze it toward its centre line to `t`."""
    import math
    s = z.endPtsOfContours[-2] + 1; P = [list(p) for p in z.coordinates[s:]]
    edges = [(P[i], P[(i + 1) % 4]) for i in range(4)]
    (a, b) = max(edges, key=lambda e: math.dist(*e))
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy); nx, ny = -dy / L, dx / L
    cx = sum(p[0] for p in P) / 4; cy = sum(p[1] for p in P) / 4
    d = [(p[0] - cx) * nx + (p[1] - cy) * ny for p in P]
    cur = max(d) - min(d); f = min(1, t / cur)
    c = z.coordinates
    for i, (p, di) in enumerate(zip(P, d)):
        c[s + i] = (round(p[0] - nx * di * (1 - f)), round(p[1] - ny * di * (1 - f)))


def level_strokes(gl, glyf):
    """Heights of the strokes a vertical line through the glyph's middle crosses (top, spine, bottom)."""
    import pathops
    from fontTools.pens.pointPen import SegmentToPointPen
    gl.recalcBounds(glyf); cx = (gl.xMin + gl.xMax) / 2
    p = pathops.Path(); gl.draw(p.getPen(), glyf)
    cut = pathops.Path(); q = cut.getPen()
    q.moveTo((cx - 1, -1000)); q.lineTo((cx + 1, -1000)); q.lineTo((cx + 1, 2000)); q.lineTo((cx - 1, 2000)); q.closePath()
    r = pathops.op(p, cut, pathops.PathOp.INTERSECTION)
    spans = []
    for c in r.contours:
        ys = [pt[1] for seg in c.segments for pt in seg[1]]
        if ys: spans.append(max(ys) - min(ys))
    return spans


def thicken_y(gl, d):
    """Push every point up or down along its outline normal by d/2 (level strokes gain d, upright
    ones nothing), then squeeze back to the old height so the x-height and baseline hold."""
    import math
    c = list(gl.coordinates); s = 0; y0, y1 = min(y for x, y in c), max(y for x, y in c); out = c[:]
    for e in gl.endPtsOfContours:
        n = e - s + 1
        for i in range(n):
            (ax, ay), (bx, by) = c[s + (i - 1) % n], c[s + (i + 1) % n]
            dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1
            ny = dx / L                                   # outward for TrueType's clockwise outlines
            out[s + i] = (c[s + i][0], c[s + i][1] + ny * d / 2)
        s = e + 1
    z0, z1 = min(y for x, y in out), max(y for x, y in out)
    gl.coordinates = type(gl.coordinates)([(round(x), round(y0 + (y - z0) * (y1 - y0) / (z1 - z0))) for x, y in out])


def thicken_slope(gl, k):
    """The a keeps its drawn proportions (its bowl is lighter than the o on purpose, which keeps the
    bowl open at 900), but the top of its bowl, a straight slope, lies much flatter once stretched
    and reads thinner across. Its two edges (the straight on-curve segments rising to the stem) are
    pushed apart so the stroke is as thick across as it was at width 100."""
    import math
    c = list(gl.coordinates); f = gl.flags; segs = []
    s = 0
    for e in gl.endPtsOfContours:
        for i in range(s, e + 1):
            j = s if i == e else i + 1
            if f[i] & 1 and f[j] & 1:
                (x0, y0), (x1, y1) = c[i], c[j]
                if 5 < abs(math.degrees(math.atan2(y1 - y0, x1 - x0))) % 180 < 30 and math.dist(c[i], c[j]) > 150:
                    segs.append((i, j))
        s = e + 1
    if len(segs) != 2: return
    (a0, a1), (b0, b1) = sorted(segs, key=lambda p: -(c[p[0]][1] + c[p[1]][1]))   # upper edge first
    (x0, y0), (x1, y1) = c[a0], c[a1]; L = math.hypot(x1 - x0, y1 - y0)
    sin_now = abs(y1 - y0) / L; sin_was = abs(y1 - y0) / math.hypot((x1 - x0) / k, y1 - y0)
    cos_now, cos_was = math.sqrt(1 - sin_now ** 2), math.sqrt(1 - sin_was ** 2)
    v = abs((c[a0][1] + c[a1][1]) - (c[b0][1] + c[b1][1])) / 2       # vertical thickness, unchanged
    grow = v * cos_was / cos_now - v                                     # same thickness across as before
    for i in (a0, a1): c[i] = (c[i][0], c[i][1] + grow / 2)
    for i in (b0, b1): c[i] = (c[i][0], c[i][1] - grow / 2)
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])


def match_a_end(gl, glyf):
    """Make the a's end exactly as thick as the middle of its arch, measured (measure.py). The end's
    inner corner (point 14) and the curve into it (13, and 12 by half) slide along the cut, which
    makes the end thicker or thinner; a search finds the slide where the two numbers are equal."""
    from measure import a_end_and_middle
    base = list(gl.coordinates)
    (ox, oy), (ix, iy) = base[15], base[14]
    L = ((ix - ox) ** 2 + (iy - oy) ** 2) ** 0.5; ux, uy = (ix - ox) / L, (iy - oy) / L
    def at(sl):
        c = base[:]
        for i, w in ((14, 1), (13, 1), (12, 0.5)):
            c[i] = (round(base[i][0] + ux * sl * w), round(base[i][1] + uy * sl * w))
        gl.coordinates = type(gl.coordinates)(c)
        e, m = a_end_and_middle(gl, glyf); return e - m
    lo, hi = -120.0, 160.0
    for _ in range(14):
        mid = (lo + hi) / 2
        if at(mid) < 0: lo = mid
        else: hi = mid
    best = min((lo, hi, (lo + hi) / 2), key=lambda v: abs(at(v)))
    at(best)


def stem_width(gl, glyf):
    """The n's left stem, measured across on the rendered letter at a third of the x-height."""
    from measure import raster
    m, x0, y1 = raster(gl, glyf); row = m[y1 - 200]
    i = 0
    while not row[i]: i += 1
    j = i
    while row[j]: j += 1
    return j - i


def _flatten(gl, glyf):
    from measure import _Flat
    pen = _Flat(None); gl.draw(pen, glyf)
    return [(p[i], p[(i + 1) % len(p)]) for p in pen.polys for i in range(len(p))]


def _ray(p, d, segs):
    """Distance from p along d to the nearest outline segment (None if nothing within reach)."""
    best = None
    for (ax, ay), (bx, by) in segs:
        ex, ey = bx - ax, by - ay; den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-9: continue
        t = ((ax - p[0]) * ey - (ay - p[1]) * ex) / den
        u = ((ax - p[0]) * d[1] - (ay - p[1]) * d[0]) / den
        if t > 3 and 0 <= u <= 1 and (best is None or t < best): best = t
    return best


def even_strokes(gl, glyf, th, tv, rounds=12):
    """Make a letter as thick as the o everywhere. At every on-curve point the thickness straight
    across (a ray inward along the outline's normal to the far edge) is moved toward th where the
    stroke runs level and tv where it stands upright (blended by the normal's slope); each side takes
    half the difference, in half-steps so it settles. Off-curve points ride along with the on-curve
    points either side. Cut ends and open counters (no far edge within twice the target) are left
    alone. The letter is then set back on its baseline and x-height."""
    import math
    y0, y1 = min(y for x, y in gl.coordinates), max(y for x, y in gl.coordinates)
    on = [bool(f & 1) for f in gl.flags]
    for _ in range(rounds):
        segs = _flatten(gl, glyf); c = list(gl.coordinates); mv = [None] * len(c); s = 0
        for e in gl.endPtsOfContours:
            n = e - s + 1
            for i in range(n):
                if not on[s + i]: continue
                (ax, ay), (bx, by) = c[s + (i - 1) % n], c[s + (i + 1) % n]
                dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1
                nx, ny = -dy / L, dx / L                      # outward, TrueType outlines run clockwise
                p = c[s + i]; d = _ray((p[0] - nx, p[1] - ny), (-nx, -ny), segs)
                target = th * abs(ny) + tv * abs(nx)
                if d is None or d > 2 * target: mv[s + i] = (0, 0); continue
                m = max(-20, min(20, (target - d) / 4))
                mv[s + i] = (nx * m, ny * m)
            for i in range(n):                            # off-curve points: the mean of their neighbours
                if mv[s + i] is not None: continue
                j = i
                while mv[s + (j - 1) % n] is None: j -= 1
                k = i
                while mv[s + (k + 1) % n] is None: k += 1
                a_, b_ = mv[s + (j - 1) % n], mv[s + (k + 1) % n]
                mv[s + i] = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2)
            s = e + 1
        gl.coordinates = type(gl.coordinates)([(x + m[0], y + m[1]) for (x, y), m in zip(c, mv)])
    c = gl.coordinates; z0, z1 = min(y for x, y in c), max(y for x, y in c)
    gl.coordinates = type(gl.coordinates)([(round(x), round(y0 + (y - z0) * (y1 - y0) / (z1 - z0))) for x, y in c])


def smooth_a_bowl_top(gl):
    """The bowl's top is straight (7-8 above, 44-45 below) and runs into curves at its left end; the
    curve's handle next to it (6, 46) is put on the straight's own line so the join has no kink."""
    c = list(gl.coordinates)
    for a, b, h in ((8, 7, 6), (44, 45, 46)):
        (x1, y1), (x0, y0) = c[a], c[b]; sl = (y0 - y1) / (x0 - x1)
        c[h] = (c[h][0], round(y0 + (c[h][0] - x0) * sl))
    gl.coordinates = type(gl.coordinates)(c)


def set_station(gl, glyf, station, pts, axis, value):
    """Slide the given points along x (axis 0) or y (axis 1) until the measured thickness at the
    station is exactly `value` (measure.at_stations)."""
    from measure import at_stations
    base = list(gl.coordinates)
    def at(sh):
        c = base[:]
        for i in pts: c[i] = (c[i][0] + sh, c[i][1]) if axis == 0 else (c[i][0], c[i][1] + sh)
        gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
        return dict(at_stations(gl, glyf))[station] - value
    lo, hi = -80, 80
    if at(lo) > at(hi): lo, hi = hi, lo                      # make at() rise from lo to hi
    for _ in range(9):
        mid = (lo + hi) / 2
        if at(mid) < 0: lo = mid
        else: hi = mid
    best = min((lo, hi), key=lambda v: abs(at(v)))
    best = min((round(best) + d for d in range(-6, 7)), key=lambda v: (abs(at(v)), abs(v - best)))
    at(best)


def bowl_top_even(gl, glyf, T, left=None):
    """The a's bowl top as thick as the arch (T) all along. Its straight part: the lower edge (44-45)
    set parallel to the upper (7-8) at T across, its curve handle (46) kept on that line. Its left end,
    where it turns down into the bowl's side: the inner curve's handles (46 along the line, 47 up or
    down) searched until the measured thickness there is T as well."""
    import math
    from measure import at_stations, BOWL_TOP
    c = list(gl.coordinates)
    (x7, y7), (x8, y8) = c[7], c[8]; sl = (y8 - y7) / (x8 - x7); cos = 1 / math.sqrt(1 + sl * sl)
    off = T / cos                                             # T across, measured upright
    dy = round(y7 + (c[45][0] - x7) * sl - off) - c[45][1]
    for i in (44, 45): c[i] = (c[i][0], round(y7 + (c[i][0] - x7) * sl - off))
    for i in (46, 47, 48, 49): c[i] = (c[i][0], c[i][1] + dy)     # the curve after it moves with it
    gl.coordinates = type(gl.coordinates)(c)
    smooth_a_bowl_top(gl)
    from measure import kinks
    def spread():
        v = [x for _, x in at_stations(gl, glyf, BOWL_TOP)]
        e = sum(abs(x - T) for x in v) + 1000 * len(kinks(gl))           # a kink is never worth it
        if left: e += abs(dict(at_stations(gl, glyf))['bowl left'] - left)   # and the side's own target
        return e, v
    # the curve into the bowl's side keeps its drawn shape: when the straight's left end (45) moved,
    # the handles after it (46 47 48 49) move with it
    c = list(gl.coordinates)
    (xu, yu) = c[7]
    def nudge(i, kind, d):
        c = list(gl.coordinates); x, y = c[i]
        if kind == 'x': c[i] = (x + d, y)
        elif kind == 'y': c[i] = (x, y + d)
        elif kind == 'in': c[i] = (x + d, round(c[45][1] + (x + d - c[45][0]) * sl))
        elif kind == 'side':                                  # the bowl's inner left side, kept upright
            for j in (47, 48, 49): c[j] = (c[j][0] + d, c[j][1])
        elif kind == 'outside':                               # the bowl's outer left side, kept upright
            for j in (4, 5): c[j] = (c[j][0] + d, c[j][1])
        elif kind == 'drop':                                  # the whole inner curve up or down
            for j in (47, 48, 49): c[j] = (c[j][0], c[j][1] + d)
        else: c[i] = (x + d, round(yu + (x + d - xu) * sl))
        gl.coordinates = type(gl.coordinates)(c)
    # only moves that keep every smooth join smooth: 47 48 49 stay one upright line, 46 stays on the
    # straight's line, 6 on the upper straight's line, 4 and 5 stay one upright line
    moves = [(48, 'drop'), (48, 'side'), (46, 'in'), (6, 'out'), (5, 'outside'), (5, 'y'), (4, 'y')]
    err = spread()[0]
    for _ in range(80):
        if err == 0: break
        improved = False
        for i, kind in moves:
            for d in (1, -1, 2, -2, 4, -4):
                keep = list(gl.coordinates); nudge(i, kind, d); e = spread()[0]
                if e < err: err = e; improved = True; break
                gl.coordinates = type(gl.coordinates)(keep)
        if not improved:
            # stuck one point at a time: try two at once
            for x in range(len(moves)):
                for y in range(x + 1, len(moves)):
                    for dx in (1, -1, 2, -2):
                        for dy in (1, -1, 2, -2):
                            keep = list(gl.coordinates)
                            nudge(*moves[x], dx); nudge(*moves[y], dy); e = spread()[0]
                            if e < err: err = e; improved = True; break
                            gl.coordinates = type(gl.coordinates)(keep)
                        if improved: break
                    if improved: break
                if improved: break
            if not improved: break


A_MOVES = {'top': [(10, 0, 1), (11, 0, 1), (12, 0, 1)], 'ul': [(12, 1, 0)], 'end': [(13, 1, 0), (14, 1, 0)],
           'endy': [(14, 0, 1)], 'h13': [(13, 0, 1)], 'side': [(47, 1, 0), (48, 1, 0), (49, 1, 0)],
           'drop': [(47, 0, 1), (48, 0, 1), (49, 0, 1)], 'outside': [(4, 1, 0), (5, 1, 0)],
           'in': [(46, 1, 'sl')], 'out': [(6, 1, 'sl')], 'h47': [(47, 0, 1)], 'h49': [(49, 0, 1)],
           'h5': [(5, 0, 1)], 'h4': [(4, 0, 1)]}


def _a_moved(coords, sl, steps):
    c = list(coords)
    for kind, d in steps:
        for i, dx, dy in A_MOVES[kind]:
            dy = sl if dy == 'sl' else dy
            c[i] = (round(c[i][0] + dx * d), round(c[i][1] + dy * d))
    return c


def _a_err(job):
    """One candidate, measured in a worker process: the a rebuilt from plain data, its error."""
    coords, flags, ends, T, left, sl, steps = job
    from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates
    from measure import at_stations, BOWL_TOP, kinks
    g = Glyph(); g.numberOfContours = len(ends); g.endPtsOfContours = list(ends)
    g.flags = bytearray(flags); g.coordinates = GlyphCoordinates(_a_moved(coords, sl, steps)); g.program = None
    d = dict(at_stations(g, None))
    e = sum(abs(d[k] - T) for k in ('arch top', 'arch upper left', 'arch end'))
    e += sum(abs(v - T) for _, v in at_stations(g, None, BOWL_TOP))
    if left: e += abs(d['bowl left'] - left)
    return e + 1000 * len(kinks(g))


def polish_a(gl, glyf, T, left=None):
    """Last pass over the a, every target at once: the arch (top, upper left, end) and the bowl's top
    all T, the bowl's side its own target, no kinks. Only moves that keep curves smooth (handles
    beside a smooth point move together or along their line). Each step measures every candidate
    move at once on all cores and takes the best; single moves first, then pairs."""
    from concurrent.futures import ProcessPoolExecutor
    c0 = list(gl.coordinates); sl = (c0[8][1] - c0[7][1]) / (c0[8][0] - c0[7][0])
    flags, ends = bytes(gl.flags), list(gl.endPtsOfContours)
    kinds = list(A_MOVES)
    singles = [[(k, d)] for k in kinds for d in (1, -1, 2, -2)]
    pairs = [[(kinds[i], d1), (kinds[j], d2)] for i in range(len(kinds)) for j in range(i + 1, len(kinds))
             for d1 in (1, -1) for d2 in (1, -1)]
    with ProcessPoolExecutor(os.cpu_count()) as pool:
        def best(cands, coords):
            errs = list(pool.map(_a_err, [(coords, flags, ends, T, left, sl, st) for st in cands], chunksize=4))
            i = min(range(len(errs)), key=errs.__getitem__); return errs[i], cands[i]
        coords = [tuple(p) for p in gl.coordinates]
        e = _a_err((coords, flags, ends, T, left, sl, []))
        for _ in range(60):
            if e == 0: break
            e2, st = best(singles, coords)
            if e2 >= e: e2, st = best(pairs, coords)
            if e2 >= e: break
            e, coords = e2, _a_moved(coords, sl, st)
    gl.coordinates = type(gl.coordinates)(coords)


# the counters' turns of s and S: (start on-curve, handles, end on-curve, on-curve between the handles)
TURNS = {'uni0073': [(8, (9, 10), 11, None), (32, (33, 34), 35, None)],
         'S': [(23, (24, 26), 27, 25), (76, (77, 79), 80, 78)]}


def equal_turns(gl, glyf, turns):
    """Make a letter's inner turns equally round (measured: the tightest radius on each, curves.py).
    Each turn's handles sit on its two runs (the tangent lines at its ends), the same distance from
    where those lines meet; that distance sets how round it is, and the join stays smooth. All turns
    get the largest radius the tightest of them can reach (the stroke limits how far a handle can go)."""
    import math
    from curves import tight_turns
    c0 = [tuple(p) for p in gl.coordinates]
    def lines(t):
        a, (h1, h2), b, _ = t
        u1 = (c0[a][0] - c0[h1][0], c0[a][1] - c0[h1][1]); u2 = (c0[b][0] - c0[h2][0], c0[b][1] - c0[h2][1])
        p1, p2 = c0[a], c0[b]; den = u1[0] * u2[1] - u1[1] * u2[0]
        if abs(den) < 1e-9: return None
        k = ((p2[0] - p1[0]) * u2[1] - (p2[1] - p1[1]) * u2[0]) / den
        C = (p1[0] + u1[0] * k, p1[1] + u1[1] * k)
        n1, n2 = math.hypot(*u1), math.hypot(*u2)
        return C, (u1[0] / n1, u1[1] / n1), (u2[0] / n2, u2[1] / n2), math.dist(C, p1), math.dist(C, p2)
    geo = [lines(t) for t in turns]
    if None in geo: return
    def place(c, t, g, d):
        C, v1, v2, _, _ = g; (h1, h2) = t[1]
        c[h1] = (C[0] + v1[0] * d, C[1] + v1[1] * d); c[h2] = (C[0] + v2[0] * d, C[1] + v2[1] * d)
        if t[3] is not None: c[t[3]] = ((c[h1][0] + c[h2][0]) / 2, (c[h1][1] + c[h2][1]) / 2)
    def r_at(t, g, d):
        c = list(c0); place(c, t, g, d)
        gl.coordinates = type(gl.coordinates)(c)
        C = g[0]
        near = [r for r, x, y, _ in tight_turns(gl, glyf) if math.dist((x, y), C) < 3 * max(g[3], g[4])]
        return min(near) if near else float('inf')
    dmax = [0.95 * min(g[3], g[4]) for g in geo]
    R = min(r_at(t, g, d) for t, g, d in zip(turns, geo, dmax))
    c = list(c0)
    for t, g, d1 in zip(turns, geo, dmax):
        lo, hi = 0.0, d1
        for _ in range(30):
            mid = (lo + hi) / 2
            if r_at(t, g, mid) < R: lo = mid
            else: hi = mid
        place(c, t, g, (lo + hi) / 2)
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])


# the counters' hairpin tips of s and S at width 150. folds: points drawn as a tiny backwards step at
# the tip, merged; moves: (kind, points) where 'x'/'y' slide along that axis (keeping an upright or
# level run straight), 'free' moves a handle that sits between implied points (always smooth), and
# ('mid', m, a, b) keeps an on-curve point halfway between its handles
TIPS = {'uni0073': {'folds': [], 'tips': [
            {'at': 11, 'moves': [('x', (9, 10, 11, 12, 13)), ('x', (10, 11, 12)), ('x', (9,)), ('y', (10,)), ('y', (11,)), ('y', (12,)), ('free', (13,))], 'mids': []},
            {'at': 35, 'moves': [('x', (33, 34, 35, 36, 37)), ('x', (34, 35, 36)), ('x', (33,)), ('y', (34,)), ('y', (35,)), ('y', (36,)), ('free', (37,))], 'mids': []}]},
        'S': {'folds': [(27, 28), (80, 81)], 'tips': [
            {'at': 27, 'moves': [('x', (24, 26, 27, 28, 29)), ('x', (26, 27, 28, 29)), ('y', (26,)), ('y', (27, 28)), ('y', (29,)), ('x', (24,))], 'mids': [(25, 24, 26)]},
            {'at': 80, 'moves': [('x', (77, 79, 80, 81, 82)), ('x', (79, 80, 81, 82)), ('y', (79,)), ('y', (80, 81)), ('y', (82,)), ('x', (77,))], 'mids': [(78, 77, 79)]}]}}


def round_tips(gl, glyf, spec, reach=200):
    """Open up a letter's counter tips so they turn equally round, as round as they will go: the
    tightest radius at each tip measured (curves.py), the tip's handles moved only in ways that keep
    every join smooth, no point further than `reach` from where it was, no kink; the search raises the
    smaller tip radius and keeps the two equal."""
    import math
    from curves import tight_turns
    from measure import kinks
    c = [list(p) for p in gl.coordinates]
    for a, b in spec['folds']:                               # a backwards step at the tip: one point
        m = [(c[a][0] + c[b][0]) / 2, (c[a][1] + c[b][1]) / 2]; c[a], c[b] = list(m), list(m)
    base = [tuple(p) for p in c]
    centres = [tuple(base[t['at']]) for t in spec['tips']]
    def apply(params):
        cc = [list(p) for p in base]; k = 0
        for t in spec['tips']:
            for kind, pts in t['moves']:
                d = params[k]; k += 1
                for i in pts:
                    if kind == 'x': cc[i][0] += d
                    elif kind == 'y': cc[i][1] += d
                    else: cc[i][0] += d[0]; cc[i][1] += d[1]
            for m, a, b in t['mids']:
                cc[m] = [(cc[a][0] + cc[b][0]) / 2, (cc[a][1] + cc[b][1]) / 2]
        gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in cc])
    def radii():
        turns = tight_turns(gl, glyf)
        out = []
        for C in centres:
            near = [r for r, x, y, _ in turns if math.dist((x, y), C) < 90]
            out.append(min(near) if near else 999)
        return out
    apply([(0, 0) if kind == 'free' else 0 for t in spec['tips'] for kind, _ in t['moves']])
    had = dict(kinks(gl))                                    # kinks the stretch already left: allowed, not worse
    def score(params):
        apply(params); r = radii()
        if any(a > had.get(p, 0) + 0.5 for p, a in kinks(gl)): return -1e9
        return min(r) - 2 * abs(r[0] - r[1])
    params = []
    for t in spec['tips']:
        for kind, _ in t['moves']: params.append((0, 0) if kind == 'free' else 0)
    best = score(params)
    for step in (32, 16, 8, 4, 2, 1):
        improved = True
        while improved:
            improved = False
            for k in range(len(params)):
                opts = ([(params[k][0] + dx, params[k][1] + dy) for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step))]
                        if isinstance(params[k], tuple) else [params[k] + step, params[k] - step])
                for o in opts:
                    if (max(abs(o[0]), abs(o[1])) if isinstance(o, tuple) else abs(o)) > reach: continue
                    trial = params[:]; trial[k] = o; sc = score(trial)
                    if sc > best + 1e-6: best, params, improved = sc, trial, True; break
    apply(params)
    return radii()


# s and S: each counter ends in a point where its two sides meet. Per end: side1/side2 = (on-curve,
# handle) giving each side's line; move1/move2 = the handle put on that line next to the end; end =
# (handle, end point(s), handle), the end points merged where the drawing folds back on itself;
# mids = on-curve points kept halfway between their handles; dir = which way the end may move
ROUND_ENDS = {
    'uni0073': [{'side1': (8, 9), 'move1': 9, 'side2': (15, 14), 'move2': 13, 'end': (10, (11,), 12), 'mids': [], 'dir': -1},
                {'side1': (32, 33), 'move1': 33, 'side2': (39, 38), 'move2': 37, 'end': (34, (35,), 36), 'mids': [], 'dir': 1}],
    'S': [{'side1': (23, 24), 'move1': 24, 'side2': (32, 31), 'move2': 31, 'end': (26, (27, 28), 29),
           'mids': [(25, 24, 26), (30, 29, 31)], 'dir': -1},
          {'side1': (76, 77), 'move1': 77, 'side2': (85, 84), 'move2': 84, 'end': (79, (80, 81), 82),
           'mids': [(78, 77, 79), (83, 82, 84)], 'dir': 1}]}


STATS = {}


def equal_s_sides(gl, glyf):
    """The S's two bowl sides as thick as each other: its upper-left side (outside to the upper counter's
    left end, straight across at the end's height) came out 15-35% thicker than its lower-right side
    (to the lower counter's right end). The upper counter's left end (76-85, the two points either side
    half as far) slides outwards as one piece, curves and joins unchanged, until the two match."""
    import numpy as np
    from measure import raster
    c0 = [tuple(p) for p in gl.coordinates]
    def run(c, i, faces):
        gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
        m, x0, y1 = raster(gl, glyf, 1); xs = np.where(m[int(round(y1 - c[i][1]))])[0]
        o = (xs.max() if faces > 0 else xs.min()) + x0
        return abs(o - c[i][0])
    def moved(d):
        c = list(c0)
        for i in range(76, 86): c[i] = (c0[i][0] - d, c0[i][1])
        for i in (75, 86): c[i] = (c0[i][0] - d / 2, c0[i][1])
        return c
    lower = run(c0, 27, 1)                                   # the lower-right side, the reference
    upper = run(c0, 80, -1)
    if lower < 20 or upper <= lower:                         # no sound measurement, or nothing to thin
        gl.coordinates = type(gl.coordinates)(c0); return [upper, lower]
    lo, hi = 0.0, upper - lower
    for _ in range(14):
        mid = (lo + hi) / 2
        if run(moved(mid), 80, -1) > lower: lo = mid
        else: hi = mid
    c = moved((lo + hi) / 2); up = run(c, 80, -1)
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
    return [up, lower]


def round_ends(gl, glyf, ends, target, sides=None, side_weight=3, stem=None, tol=0.03):
    """Rebuild each counter end as a round end: at a chosen place along the counter, the gap between
    its two sides (their lines at that place) is the end's width; the end point sits halfway across,
    its handles upright either side, the sides' handles on their own lines, on-curve points next to
    them halfway between their handles, so every join stays smooth. Place and handle spacing are
    searched so every end turns as round as `target` (the drawn letter's own ends at width 100, averaged),
    so the wide letter keeps the drawn one's look (measured, curves.py). With `sides`, each end also goes as
    deep as it takes for the stroke around it (end point to the letter's outside, straight across at
    the end's height) to be as thick as the drawn letter's there: one side of the S came out 15-35%
    thicker than the other, and the ends read as dipped."""
    import math
    from curves import tight_turns
    from measure import kinks
    c0 = [tuple(p) for p in gl.coordinates]
    def line(on, h):
        (px, py), (qx, qy) = c0[on], c0[h]
        sl = (qy - py) / (qx - px) if abs(qx - px) > 1e-9 else 0
        return lambda x: py + (x - px) * sl
    L = [(line(*e['side1']), line(*e['side2'])) for e in ends]
    def build(c, e, f, xt, a, b):
        y1, y2 = f[0](xt), f[1](xt); R = abs(y2 - y1) / 2
        if R <= 2: return False
        vs = 1 if y2 > y1 else -1; sgn = -e['dir']          # the end faces away from where it moves
        h1, pts, h2 = e['end']
        c[e['move1']] = (xt - sgn * b * R, f[0](xt - sgn * b * R))
        c[e['move2']] = (xt - sgn * b * R, f[1](xt - sgn * b * R))
        c[h1] = (xt, y1 + vs * a * R); c[h2] = (xt, y2 - vs * a * R)
        for p in pts: c[p] = (xt, y1 + vs * R)
        for m, p, q in e['mids']: c[m] = ((c[p][0] + c[q][0]) / 2, (c[p][1] + c[q][1]) / 2)
        return True
    def radii(c):
        gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
        turns = tight_turns(gl, glyf); out = []
        for e in ends:
            C = c[e['end'][1][0]]
            near = [r for r, x, y, _ in turns if math.dist((x, y), C) < 120]
            out.append(min(near) if near else 999)
        return out
    starts = [c0[e['end'][1][0]][0] for e in ends]
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c0])
    had = dict(kinks(gl))                                    # kinks the stretch already left (whole units): allowed, not worse
    import numpy as np
    from measure import raster
    m0, mx0, my1 = raster(gl, glyf, 1)                      # the outside never moves: one look at it
    def outside(y, faces):
        row = m0[int(round(my1 - y))]; xs = np.where(row)[0]
        if not len(xs): return None
        return (xs.max() if faces > 0 else xs.min()) + mx0
    def side(c, e):
        p = c[e['end'][1][0]]; o = outside(p[1], -e['dir'])
        return abs(o - p[0]) if o is not None else 0
    best = None
    def trial(a, b, d1, d2):
        nonlocal best
        c = list(c0); STATS['tried'] = STATS.get('tried', 0) + 1
        for e, f, x0, d in zip(ends, L, starts, (d1, d2)):
            if not build(c, e, f, x0 + e['dir'] * d, a, b): STATS['nobuild'] = STATS.get('nobuild', 0) + 1; return
        r = radii(c)
        mids = {m for e in ends for m, _, _ in e['mids']}       # halfway between handles: smooth by construction
        bad = [(p, k) for p, k in kinks(gl) if p not in mids and k > had.get(p, 0) + 1.0]
        if bad: STATS['kink'] = STATS.get('kink', 0) + 1; STATS['eg'] = bad; return
        sc = -4 * abs(r[0] - r[1]) - abs((r[0] + r[1]) / 2 - target) - 0.02 * (abs(d1) + abs(d2))   # equal first, then the drawn look
        sc -= 6 * max(0, 0.8 * target - min(r))               # never pinched below the drawn roundness
        if sides and any(side(c, e) < 0.85 * t for e, t in zip(ends, sides)): return   # the stroke beside it holds
        if stem:                                             # the curves' side apexes stay the stem
            from apex import side_apexes
            l, rr, _, _ = side_apexes(gl, glyf)
            if abs(l - stem) > tol * stem or abs(rr - stem) > tol * stem: return

        if best is None or sc > best[0]: best = (sc, c, r, (a, b, d1, d2))
    for a in (0.3, 0.45, 0.55):
        for b in (0.5, 0.8, 1.1):
            for d1 in range(0, 261, 10):
                for d2 in range(0, 261, 10): trial(a, b, d1, d2)
    if best:                                                 # then finer, around the best
        a0, b0, e1, e2 = best[3]
        for a in (a0 - 0.05, a0, a0 + 0.05):
            for b in (b0 - 0.1, b0, b0 + 0.1):
                for d1 in range(max(0, e1 - 10), e1 + 11, 2):
                    for d2 in range(max(0, e2 - 10), e2 + 11, 2): trial(a, b, d1, d2)
    if best: gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in best[1]])
    else: gl.coordinates = type(gl.coordinates)(c0)
    return best[2] if best else None


def smooth_like_drawn(gl, drawn, slack=1.0):
    """Every on-curve point between two handles that kinks more than the drawn letter does there (by
    `slack` degrees) is put on the line through its handles, at its own projection: a move of a unit
    or two, so the shape stays and the curve runs through. Returns the points moved."""
    from measure import kinks
    have = dict(kinks(drawn, 0)); moved = []
    for _ in range(3):                                     # rounding can leave a little; go again
        c = list(gl.coordinates)
        bad = [p for p, a in kinks(gl, 0) if a > have.get(p, 0) + slack]
        if not bad: break
        s = 0; prev = {}
        for e in gl.endPtsOfContours:
            n = e - s + 1
            for i in range(n): prev[s + i] = (s + (i - 1) % n, s + (i + 1) % n)
            s = e + 1
        for p in bad:
            a, b = c[prev[p][0]], c[prev[p][1]]; dx, dy = b[0] - a[0], b[1] - a[1]
            t = ((c[p][0] - a[0]) * dx + (c[p][1] - a[1]) * dy) / (dx * dx + dy * dy)
            c[p] = (round(a[0] + t * dx), round(a[1] + t * dy)); moved.append(p)
        gl.coordinates = type(gl.coordinates)(c)
    return sorted(set(moved))


def at_weight(gl, glyf, target, drawn=None):
    """The @ brought up to `target` (stroke over stem, the median along its centre line) where it is lighter:
    Geist draws it light (0.47 of the stem at 900) and wide it read far lighter than the letters beside it
    (Danny: 0.7 at width 150; at width 100 the cell is too small, it fills in). Every point moves out along
    its outline normal, so every stroke gains the same; then the letter is squeezed back across to its old
    ink box, so it stays in its cell. Same points. Returns the stroke before and after, over the stem."""
    import math
    import numpy as np
    from measure import profile
    def med():
        p = profile(gl, glyf); return float(np.median(p['level'] + p['upright']))
    gl.recalcBounds(glyf); x0, x1 = gl.xMin, gl.xMax; before = med()
    for _ in range(5):
        d = target - med()
        if d <= 1: break
        c = list(gl.coordinates); out = c[:]; s = 0
        for e in gl.endPtsOfContours:
            n = e - s + 1
            for i in range(n):
                (ax, ay), (bx, by) = c[s + (i - 1) % n], c[s + (i + 1) % n]
                dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1
                out[s + i] = (c[s + i][0] - dy / L * d / 2, c[s + i][1] + dx / L * d / 2)
            s = e + 1
        a, b = min(x for x, _ in out), max(x for x, _ in out); k = (x1 - x0) / (b - a)
        gl.coordinates = type(gl.coordinates)([(round(x0 + (x - a) * k), round(y)) for x, y in out])
        gl.recalcBounds(glyf)
    if drawn is not None: smooth_shares(gl, drawn)
    return before, med()


def smooth_shares(gl, drawn):
    """Each on-curve point between two handles put on its handles' line at the same share of the way as in
    `drawn` (the same glyph at width 100): a point between handles stays smooth in every blend of the two
    only if it sits at the same share in both (the grown @ kinked 9-11 degrees at point 46 at 125/900)."""
    c, d, f = list(gl.coordinates), drawn.coordinates, gl.flags; s = 0
    for e in gl.endPtsOfContours:
        n = e - s + 1
        for i in range(n):
            a, p, b = s + (i - 1) % n, s + i, s + (i + 1) % n
            if not (f[p] & 1) or (f[a] & 1) or (f[b] & 1): continue
            da, db = (d[b][0] - d[a][0], d[b][1] - d[a][1]), (d[p][0] - d[a][0], d[p][1] - d[a][1])
            L = da[0] ** 2 + da[1] ** 2
            if not L: continue
            t = (db[0] * da[0] + db[1] * da[1]) / L
            c[p] = (round(c[a][0] + t * (c[b][0] - c[a][0])), round(c[a][1] + t * (c[b][1] - c[a][1])))
        s = e + 1
    gl.coordinates = type(gl.coordinates)(c)


AT_WIDE = 0.7                                              # the @'s stroke over the stem at width 150


def round_s_tips(gl, glyf, target):
    """The s's two counter ends rounded to at least `target` radius. Stretched wide, each end's turn is
    spread over a long run but keeps its height, so it comes to a point (radius 7 at 900, drawn 20). Per
    end, two handles only: the edge handle slides along its level edge toward the tip, the tip handle
    along the tip's upright toward that edge. Both stay on their lines, so every join stays smooth, and
    the tip itself does not move, so the stroke beyond it keeps its thickness. Smallest move that reaches
    the target (or the roundest there is)."""
    import math
    from curves import tight_turns
    from measure import kinks
    c0 = list(gl.coordinates); base = dict(kinks(gl))      # kinks the stretch already left, not ours
    def radius(c, tip):
        gl.coordinates = type(gl.coordinates)(c)
        return min((r for r, x, y, _ in tight_turns(gl, glyf) if math.dist((x, y), c[tip]) < 120), default=999)
    out = []
    for edge, hand, tip in ((9, 10, 11), (33, 34, 35)):    # lower end, upper end
        if c0[edge][1] != c0[edge - 1][1] or c0[hand][0] != c0[tip][0]: out.append(None); continue
        if radius(c0, tip) >= target: out.append(0); continue
        best = None
        for u in range(0, 81, 4):
            for v in range(0, 81, 4):
                c = list(c0)
                c[edge] = (round(c0[edge][0] + (c0[hand][0] - c0[edge][0]) * u / 100), c0[edge][1])
                c[hand] = (c0[hand][0], round(c0[hand][1] + (c0[edge][1] - c0[hand][1]) * v / 100))
                r = radius(c, tip)
                if any(a > base.get(i, 0) + 0.5 for i, a in kinks(gl)): continue
                key = (0, u + v) if r >= target else (1, -r)
                if best is None or key < best[0]: best = (key, c, r)
        c0 = best[1]; out.append(round(best[2], 1))
    gl.coordinates = type(gl.coordinates)(c0)
    return out


def turn_radius(gl, glyf, at, win=60):
    """The tightest turn (radius, font units) of the outline within `win` units of the spot `at`,
    measured as the sweep measures them (folds merged, curves only: curves.tight_turns)."""
    import math
    from curves import tight_turns
    return min((r for r, x, y, _ in tight_turns(gl, glyf, unfold=True, curve_only=True) if math.dist((x, y), at) < win), default=999)


def ease_turn(gl, glyf, drawn, slides, centre, place=(), share=0.7, blends=(0.25, 0.5, 0.75, 1), keep=None, tol=0.05):
    """A curve the stretch has pinched, rounded the way the s's counter ends are (round_s_tips): the two
    handles beside the turn slide along their own lines, so every join stays smooth and nothing else
    moves. `slides` is two of (handle, anchor): the handle moves along the line from the anchor (the
    on-curve point or handle it lines up with) through itself; or (points, from, to, lo, hi): those
    points move together, lo to hi units along the line from point `from` to point `to` (a corner and
    its handle along a cut, say). `place` lists on-curve points
    (point, handle, handle) that sit between two handles: each is put back on its handles' line at the
    same share of the way, so it stays smooth. The width-150 letter is blended with the drawn one
    (`drawn`, width 100, same weight) at `blends` of the way (the widths the font shows in between),
    and the turn measured near point `centre` in each; the target is `share` of the drawn letter's
    radius there. Smallest move that reaches it at every blend (or the roundest there is). Only where
    needed: a turn already at the target is left. `keep`: a function of (glyph, glyf) giving stroke
    thicknesses that must each stay within `tol` of what they were. Returns (drawn radius, before, after),
    the worst blend."""
    import math
    from measure import kinks
    c0 = list(gl.coordinates); d = list(drawn.coordinates)
    rd = turn_radius(drawn, glyf, d[centre])
    if rd >= 999: return (rd, None, None)                  # the drawn letter has no turn here
    want = share * rd
    def worst(c):
        out = 999
        for t in blends:
            gl.coordinates = type(gl.coordinates)([(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for a, b in zip(d, c)])
            out = min(out, turn_radius(gl, glyf, gl.coordinates[centre]))
        gl.coordinates = type(gl.coordinates)(c)
        return out
    r0 = worst(c0)
    if r0 >= want: return (round(want / share, 1), r0, r0)
    gl.coordinates = type(gl.coordinates)(c0); base = dict(kinks(gl)); held = keep(gl, glyf) if keep else []
    slides = [((s[0],), s[1], s[0]) if len(s) == 2 else s for s in slides]
    unit, span = [], []
    for s in slides:
        a, b = c0[s[1]], c0[s[2]]; L = math.dist(a, b); unit.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L, L))
        lo, hi = s[3:] if len(s) == 5 else (-int(0.6 * L) // 4 * 4, max(60, int(L)))
        span.append(range(lo, hi + 1, 4))
    frac = {p: math.dist(c0[h1], c0[p]) / max(1e-9, math.dist(c0[h1], c0[h2])) for p, h1, h2 in place}
    def moved(m1, m2):
        c = list(c0)
        for s, (ux, uy, _), m in zip(slides, unit, (m1, m2)):
            for h in s[0]: c[h] = (round(c0[h][0] + ux * m), round(c0[h][1] + uy * m))
        for p, h1, h2 in place:
            c[p] = (round(c[h1][0] + (c[h2][0] - c[h1][0]) * frac[p]), round(c[h1][1] + (c[h2][1] - c[h1][1]) * frac[p]))
        return c
    best = None
    def trial(m1, m2):
        nonlocal best
        if m1 <= -0.8 * unit[0][2] or m2 <= -0.8 * unit[1][2]: return      # a handle never reaches its anchor
        c = moved(m1, m2); gl.coordinates = type(gl.coordinates)(c)
        if any(a > base.get(i, 0) + 0.5 for i, a in kinks(gl)): return
        r = worst(c)
        key = (0, abs(m1) + abs(m2)) if r >= want else (1, -r)
        if best is not None and key >= best[0]: return
        if keep:
            gl.coordinates = type(gl.coordinates)(c)
            if any(abs(v - h) > tol * h for v, h in zip(keep(gl, glyf), held)): return
        best = (key, (m1, m2), r, c)
    for m1 in span[0]:
        for m2 in span[1]: trial(m1, m2)
    if best:                                               # then by single units, around the best
        e1, e2 = best[1]
        for m1 in range(e1 - 4, e1 + 5):
            for m2 in range(e2 - 4, e2 + 5): trial(m1, m2)
    gl.coordinates = type(gl.coordinates)(best[3] if best and best[2] > r0 else c0)
    return (round(want / share, 1), r0, best[2] if best and best[2] > r0 else r0)


# pinched turns, eased at width 150 (ease_turn): handles that slide (handle, anchor), the on-curve points
# re-placed between their handles, the point the turn is measured near
EASE = {'G': ([(60, 61), (58, 57)], [(59, 58, 60)], 60),           # counter's lower right into the spur's underside
        'uni0032': ([(30, 31), (29, 28)], [], 30),                # the 2's spine into its base
        # the a's arch into the inner end of its terminal: the arch's handle along its level line, and the
        # end's inner corner with its handle along the end's cut (as match_a_end moves it): at 800 the
        # a's search left that corner far out (x 321, against 212 and 230 at 700 and 900), and the
        # arch could only reach it by a hook
        'uni0061': ([(12, 11), ((13, 14), 14, 15, 0, 140)], [], 13),
        # B's two counters end in a point at 800-900 (r 21-25 against 51-54 drawn): each counter's two tip
        # handles slide apart along the tip's upright (moving the edge handles barely helps). A list: one
        # entry per turn
        'B': [([(19, 20), (21, 20)], [], 20), ([(28, 29), (30, 29)], [], 29)]}


def a_arch(gl, glyf):
    """The a's arch, measured at its stations (top, upper left, end): it stays even when its turn is eased."""
    from measure import at_stations
    from measure import a_end_and_middle
    s = dict(at_stations(gl, glyf)); return [s['arch top'], s['arch upper left'], s['arch end'], a_end_and_middle(gl, glyf)[0]]


EASE_KEEP = {'uni0061': a_arch}


def open_s(gl, glyf, ring, share=0.10):
    """The s's upper counter opened, top and bottom, by `share` of the o's level stroke each way: wide,
    its top stroke and spine read too heavy round that counter (Danny, against the S). Top edge 30-33 up
    (31-33 together, so the counter's top stays level and smooth), bottom edge 36-40 down. Then the top-left
    shoulder, which stretching leaves the thinnest stroke in the letter, is brought to halfway between the
    top stroke and the side (measured, across.py), from the outside: the outer curve's corner handle moves
    out toward the corner."""
    from across import across
    d = share * ring; c0 = list(gl.coordinates)
    for i, f in ((30, 0.5), (31, 1), (32, 1), (33, 1)): c0[i] = (c0[i][0], c0[i][1] + d * f)
    for i, f in ((36, 0.5), (37, 1), (38, 1), (39, 0.8), (40, 0.4)): c0[i] = (c0[i][0], c0[i][1] - d * f)
    # the shoulder is thickened from the outside: the outer curve's corner handle 21 moves out toward the
    # corner (the counter keeps its round top-left; pulling that in made a flat facet), 20 and 22 a
    # quarter as far so the outer curve stays one smooth sweep
    cx, cy = c0[20][0], c0[22][1]                          # the outer corner: left side x, top y
    def put(k, _unused=0):
        c = list(c0)
        for i, f in ((21, 1.0), (20, 0.25), (22, 0.25)):
            c[i] = (c[i][0] + (cx - c[i][0]) * k * f * (1 if i == 21 else 0) + (0 if i != 20 else 0),
                    c[i][1] + (cy - c[i][1]) * k * f * (1 if i == 21 else 0))
        # 20 sits on the left side (x fixed) and only moves up; 22 on the top (y fixed) and only moves left
        c[20] = (c0[20][0], c0[20][1] + (cy - c0[20][1]) * k * 0.25)
        c[22] = (c0[22][0] + (cx - c0[22][0]) * k * 0.25, c0[22][1])
        gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
    put(0, 0)
    top, side = across(gl, glyf, [(0.47, 0.93), (0.09, 0.72)])
    target = (top + side) / 2
    from measure import kinks
    best = None
    for k100 in range(0, 91, 3):
        k = k100 / 100; put(k)
        if kinks(gl): continue                             # never a corner where the curve runs smooth
        sh = across(gl, glyf, [(0.20, 0.88)])[0]
        if sh is None: continue
        e = abs(sh - target)
        if best is None or e < best[0]: best = (e, k)
    put(best[1] if best else 0)
    return target


# % @ $: x from the weight whose own upright strokes, stretched, match the drawn letter's; measured on
# these contours (all if None): $'s S only, its bar is set on its own (dollar_bar)
MATCH_UPRIGHT = {'uni0025': None, 'uni0040': None, 'uni0024': [1]}


def upright_width(gl, glyf, stem, contours=None):
    """Median thickness straight across the letter's upright strokes (stem_gate's rays that run
    sideways, from points clear of corners), font units; only the given contours, if any."""
    import numpy as np, copy
    from stem_gate import strokes as gate_strokes
    if contours is not None:
        part = copy.deepcopy(gl); pts, fl, ends, s0 = [], [], [], 0
        for ci, e in enumerate(gl.endPtsOfContours):
            if ci in contours:
                pts += list(gl.coordinates)[s0:e + 1]; fl += list(gl.flags)[s0:e + 1]; ends.append(len(pts) - 1)
            s0 = e + 1
        part.coordinates = type(gl.coordinates)(pts); part.flags = type(gl.flags)(fl)
        part.endPtsOfContours = ends; part.numberOfContours = len(ends); gl = part
    up, _ = gate_strokes(gl, glyf, near=0.5 * stem)
    up = up[up < 1.6 * stem]
    return float(np.median(up)) if len(up) else 0.0


def dollar_bar(gl, drawn):
    """$: its bar (the first contour, a rectangle) is drawn lighter than the stem (half of it at 900).
    Stretched from a lighter weight's x, the bar came out up to 1.4 times the drawn one's; it is set
    back to the drawn bar's width at this weight, about its own centre."""
    e = gl.endPtsOfContours[0]; c = list(gl.coordinates); d = drawn.coordinates
    want = max(x for x, _ in d[:e + 1]) - min(x for x, _ in d[:e + 1])
    x0, x1 = min(x for x, _ in c[:e + 1]), max(x for x, _ in c[:e + 1]); m = (x0 + x1) / 2
    for i in range(e + 1):
        c[i] = (round(m - want / 2) if c[i][0] < m else round(m + want / 2), c[i][1])
    gl.coordinates = type(gl.coordinates)(c)


# ( ): outer curve and inner curve, point beside point, each listed from the bottom cut to the top cut
PAREN = {'uni0028': (list(range(0, 9)), list(range(17, 8, -1))),
         'uni0029': ([0] + list(range(17, 9, -1)), list(range(1, 10)))}


def paren_even(gl, drawn, name):
    """( ): one contour, an outer curve and an inner curve (PAREN), point beside point at the same
    height, cut level at both ends. Stretched, the arms lie flatter and come out thinner across than
    drawn (ends 0.34 of the stem at 150/100 against 0.61): the stretch keeps each pair's gap along
    the level, but a flatter stroke is thinner across for the same gap. Each inner point moves along
    the level only, so the gap is the drawn gap times sin(drawn slope) / sin(slope now), the slope
    of the outer curve there: the stroke is as thick across as drawn at that place (the drawn taper
    toward the ends stays; upright, in the middle, nothing moves). Points, order, flags as drawn."""
    import math
    O, I = PAREN[name]
    c = [tuple(map(float, p)) for p in gl.coordinates]; d = [tuple(map(float, p)) for p in drawn.coordinates]
    def sin_slope(P, j):                                # |sin| of the outer curve's slope at its j-th point
        a, b = P[O[max(j - 1, 0)]], P[O[min(j + 1, len(O) - 1)]]
        return abs(b[1] - a[1]) / math.hypot(b[0] - a[0], b[1] - a[1])
    for j in range(len(O)):
        o, i = O[j], I[j]
        gap = (d[i][0] - d[o][0]) * sin_slope(d, j) / sin_slope(c, j)
        c[i] = (c[o][0] + gap, c[i][1])
    # the inner curve's on-curve middle (upright, so it does not move) stays smooth: its two handles go
    # back onto its drawn tangent through it (they had moved out, the slope beside it being flatter)
    fl = gl.flags
    for j in range(1, len(O) - 1):
        i = I[j]
        if not fl[i] & 1: continue
        h1, h2 = I[j - 1], I[j + 1]
        tx, ty = d[h2][0] - d[h1][0], d[h2][1] - d[h1][1]
        for h in (h1, h2):
            c[h] = (c[i][0] + (c[h][1] - c[i][1]) * tx / ty, c[h][1])
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])


def grave_even(gl, drawn, o=0):
    """` (and %'s slash, its points from `o` = 24): one slanted stroke, 4 corners (o bottom-left, o+1
    top-left, o+2 top-right, o+3 bottom-right), cut level at top and bottom (the grave a little wider
    at the top as drawn). Stretched, it lies flatter, and the same width along the level reads thinner
    across (` 0.82 of the stem at 150/700 against 0.99; %'s slash 0.68 against 0.81 at 150/100). Each
    cut keeps its middle and takes the drawn cut's width times sin(drawn slant) / sin(slant now), so
    the stroke is as thick across at both ends as drawn."""
    import math
    c = [tuple(map(float, p)) for p in gl.coordinates]; d = [tuple(map(float, p)) for p in drawn.coordinates]
    def sin_slant(P):                                   # the two long edges, averaged
        s_ = 0
        for a, b in ((o, o + 1), (o + 3, o + 2)):
            s_ += abs(P[b][1] - P[a][1]) / math.dist(P[a], P[b])
        return s_ / 2
    f = sin_slant(d) / sin_slant(c)
    for a, b in ((o + 1, o + 2), (o, o + 3)):
        m = (c[a][0] + c[b][0]) / 2; w = (d[b][0] - d[a][0]) * f
        c[a], c[b] = (m - w / 2, c[a][1]), (m + w / 2, c[b][1])
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])


S_STEPS = os.environ.get('S_STEPS', 'p')   # s at 150 is the drawn s widened, counter ends rounded (Danny); t thicken, r round ends, o open, p round tips


def main(wdth, weight, out):
    r = wdth / 100
    vf = '../../build/variable/ProxyMono[wght].ttf'       # the weight font (Makefile builds it first)
    # the cell's extra width goes into the letter, not its sidebearings: each glyph is stretched by
    # k = (ink + extra) / ink about the cell centre, capped so narrow letters (i l 1) don't balloon, and
    # dots and other small marks (ink under 200) only move to the new centre
    Y = instantiateVariableFont(TTFont(vf), {'wght': weight})
    gy = Y['glyf']; src = TTFont(vf); inst = {}
    def inst_at(w):
        if w not in inst:
            if w >= 100: inst[w] = instantiateVariableFont(src, {'wght': w})['glyf']
            else:
                # below Thin (wide Thin and ExtraLight need lighter verticals than Thin has): each
                # point carried on past Thin along its Thin-to-ExtraLight line
                a, b = inst_at(100), inst_at(200); f = (100 - w) / 100
                import copy
                t = copy.deepcopy(a)
                for g in t.keys():
                    ga, gb = a[g], b[g]
                    if ga.isComposite() or ga.numberOfContours <= 0: continue
                    ca, cb = ga.getCoordinates(a)[0], gb.getCoordinates(b)[0]
                    t[g].coordinates = type(ca)([(xa + (xa - xb) * f, ya + (ya - yb) * f) for (xa, ya), (xb, yb) in zip(ca, cb)])
                inst[w] = t
        return inst[w]
    def x_source(k):
        w = round(weight_for(stem_at(weight) / k) / 5) * 5 if k != 1 else weight
        return inst_at(w)
    adv = round(CELL * r); extra = adv - CELL; TURNS_TODO = []
    for g in Y.getGlyphOrder():
        b = gy[g]
        if b.isComposite():
            for c in b.components: c.x = round(c.x * r)
        elif b.numberOfContours > 0:
            b.recalcBounds(gy); ink = b.xMax - b.xMin
            k = 1 if ink < 200 else min(max((ink + extra) / ink, r if r < 1 else 1), r * 1.3)
            cy = b.coordinates; ref = strokes(cy, b)
            curved = not all(f & 1 for f in b.flags)
            # curved letters keep the stem rule below, which sets their rings right: matched on their
            # few straight strokes instead, Q's ring came out half its weight at 700 and 0's ring
            # pinched at 100. R too: matched on its stem and leg together, the search traded one for
            # the other and left its stem 1.15-1.19 stems thick at width 150. It takes the stem rule
            # (stem exact) and wide.py sets its leg, a contour of its own, to the stem
            if ref and any(a > 15 for a, _ in ref) and g not in DEEP_V and not curved:
                # a letter with diagonals: the stem rule above leaves them too thin or too thick once
                # they flatten, so try every x-source weight and keep the one whose strokes (vertical
                # and diagonal, measured across) come closest to the target weight's own
                def k_for(w):                             # the stretch worked out on that instance's letter
                    sg = inst_at(w)[g]; sg.recalcBounds(inst_at(w))
                    return min(max((ink + extra) / (sg.xMax - sg.xMin), r if r < 1 else 1), r * 1.3)
                def err(w):
                    xs = inst_at(w)[g].getCoordinates(inst_at(w))[0]; kw = k_for(w)
                    t = [(round(adv / 2 + (x - CELL / 2) * kw), y) for (x, _), (_, y) in zip(xs, cy)]
                    got = strokes(t, b)
                    if len(got) != len(ref): return 9e9
                    return sum((g2 / r2 - 1) ** 2 for (_, g2), (_, r2) in zip(got, ref))
                best = min(range(20, 901, 20), key=err)
                cx = inst_at(best)[g].getCoordinates(inst_at(best))[0]; k = k_for(best)
            elif g in X_TOWARD_TARGET:
                # s: its spine and ends lean, so the stem rule leaves them light; x comes from a weight
                # part way from the stem-matched one back toward the target
                f_ = X_TOWARD_TARGET[g]; w0 = weight_for(stem_at(weight) / k)
                wx = round((w0 + (weight - w0) * f_) / 5) * 5
                cx = inst_at(wx)[g].getCoordinates(inst_at(wx))[0]
            else:
                # the stretch is worked out on the letter it is applied to: the lighter instance's
                # letter can be narrower than the target's (Martian's B is much narrower light), and
                # stretching it by the target's ratio left it short of the cell's extra width
                if ink >= 200:
                    for _ in range(3):
                        sg = x_source(k)[g]; sg.recalcBounds(x_source(k)); ink_s = sg.xMax - sg.xMin
                        k = min(max((ink + extra) / ink_s, r if r < 1 else 1), r * 1.3)
                cx = x_source(k)[g].getCoordinates(x_source(k))[0]
                if g in MATCH_UPRIGHT and k != 1:
                    # % @ $ are drawn lighter (than the stem, or than at light weights) the heavier the weight (@'s
                    # upright strokes 0.96 of the stem at 100, 0.46 at 900): the stem rule's lighter
                    # x-source brings its own, heavier share, so wide its uprights came out heavier
                    # than its level strokes (0.64 against 0.48 at 150/900). x comes instead from the
                    # weight whose own uprights, stretched, are the drawn letter's at this weight ($'s S
                    # came out 1.06 of the stem at 150/700 against 0.97 drawn)
                    sel = MATCH_UPRIGHT[g]
                    want = upright_width(b, gy, stem_at(weight), sel)
                    def k_w(w):
                        sg = inst_at(w)[g]; sg.recalcBounds(inst_at(w))
                        return min(max((ink + extra) / (sg.xMax - sg.xMin), r if r < 1 else 1), r * 1.3)
                    def got(w): return upright_width(inst_at(w)[g], inst_at(w), stem_at(max(w, 100)), sel) * k_w(w)
                    lo, hi = 20, weight
                    while hi - lo > 5:
                        mid = round((lo + hi) / 2 / 5) * 5
                        if mid in (lo, hi): break
                        if got(mid) < want: lo = mid
                        else: hi = mid
                    # (the stem rule's own weight too: below Thin the stretch grows as the source
                    # narrows, so the uprights stop getting lighter there: all of them, then)
                    w_stem = round(weight_for(stem_at(weight) / k) / 5) * 5
                    cands = [lo, hi, w_stem] + (list(range(20, int(weight) + 1, 5)) if lo == 20 else [])
                    wx = min(cands, key=lambda w: abs(got(w) - want)); k = k_w(wx)
                    cx = inst_at(wx)[g].getCoordinates(inst_at(wx))[0]
                    print(g, 'x from', wx, 'uprights', round(got(wx)), 'drawn', round(want))
            # M W w: the heavier the weight, the shallower the V between their stems (Bold's M meets at
            # y 443, Light's at 109). Stretched, the shallow V closes up, so these take their heights
            # from the lighter instance too, keeping the deep V
            if g in DEEP_V: cy = cx
            b.coordinates = type(cy)([(round(adv / 2 + (x - CELL / 2) * k), y) for (x, _), (_, y) in zip(cx, cy)])
            if g == 'uni0030': thin_slash(b, 0.85 * hstem_of(gy['O']))
            if k != 1 and g == 'uni0024': dollar_bar(b, inst_at(weight)[g])
            if k != 1 and g == 'uni0060': grave_even(b, inst_at(weight)[g])
            if k != 1 and g == 'uni0025': grave_even(b, inst_at(weight)[g], 24)
            if k != 1 and g in ('uni0028', 'uni0029'): paren_even(b, inst_at(weight)[g], g)
            if k != 1 and g == 'uni0026':                  # drawn from its centre line (amp_wide.py)
                from amp_wide import amp_wide
                print('& redrawn, worst fit', amp_wide(b, inst_at(weight)[g], adv))
            for p in KEEP_CORNERS.get(g, ()):
                want, got, _, goal, was, now = keep_corner(b, inst_at(weight)[g], p)
                print(g, 'corner', p, 'drawn turn', want, 'now', got, '| thickness drawn', goal, 'stretched', was, 'now', now)

            if g == 'uni0073' and 't' in S_STEPS:
                # the s as drawn has lighter level strokes than the o (154 against 167 at 900), which
                # shows once it is wide: bring its mean to the o's ring
                o_ = gy['uni006F']; d = hstem_of(o_) - sum(level_strokes(b, gy)) / 3
                if d > 0: thicken_y(b, d)
            if g == 'uni0061' and wdth == 150:     # set at 150; other widths come from the variable font
              # the search below takes minutes (thousands of exact measurements); its result is kept in
              # build/cache, keyed by the a it starts from, the weight and the targets, and reused
              import hashlib, json
              key = hashlib.sha1(json.dumps([list(b.coordinates), weight, A_TARGETS.get(weight, [])],
                                            default=str).encode()).hexdigest()
              cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../build/cache', f'a-{key}.json')
              if os.path.exists(cache):
                  b.coordinates = type(b.coordinates)([tuple(p) for p in json.load(open(cache))])
              else:
                thicken_slope(b, k)
                smooth_a_bowl_top(b)
                # stroke thicknesses set by eye on the measured a (see measure.A_STATIONS), per weight,
                # and the end as thick as the arch's middle; the two share point 12, so alternate
                from measure import at_stations
                tg = {st: v for st, _, _, v in A_TARGETS.get(weight, ())}
                top = tg.get('arch top') or dict(at_stations(b, gy))['arch top']
                for _ in range(6):
                    set_station(b, gy, 'arch upper left', (12,), 0, top)    # the arch even along its length
                    set_station(b, gy, 'arch end', (13, 14), 0, top)
                    for station, pts, axis, value in A_TARGETS.get(weight, ()):
                        set_station(b, gy, station, pts, axis, value)
                    got = dict(at_stations(b, gy))
                    if got['arch top'] == got['arch upper left'] == got['arch end'] == top: break
                bowl_top_even(b, gy, top, tg.get('bowl left'))
                polish_a(b, gy, top, tg.get('bowl left'))
                os.makedirs(os.path.dirname(cache), exist_ok=True)
                json.dump([list(p) for p in b.coordinates], open(cache, 'w'))
        w = Y['hmtx'][g][0]
        Y['hmtx'][g] = (adv if w else 0, 0)
    if wdth == 150:                                       # after s's level strokes are thickened
        import math
        from curves import tight_turns
        drawn = inst_at(weight)                            # the drawn letter at this weight, width 100
        for g in ROUND_ENDS:
            if g == 'uni0073' and 'r' not in S_STEPS: continue
            rs = []
            for e in ROUND_ENDS[g]:
                C = drawn[g].coordinates[e['end'][1][0]]
                near = [r for r, x, y, _ in tight_turns(drawn[g], drawn) if math.dist((x, y), C) < 120]
                rs.append(min(near))
            now = []
            for e in ROUND_ENDS[g]:
                C = gy[g].coordinates[e['end'][1][0]]
                near = [r for r, x, y, _ in tight_turns(gy[g], gy) if math.dist((x, y), C) < 120]
                now.append(min(near))
            # only where the stretch has pinched the ends (tighter than the drawn letter's); elsewhere the
            # stretched curves are kept, rebuilding them there only added lumps
            from measure import raster
            import numpy as np
            dm, dx0, dy1 = raster(drawn[g], drawn, 1); sides = []
            for e in ROUND_ENDS[g]:                         # the drawn letter's stroke beside each end
                p = drawn[g].coordinates[e['end'][1][0]]; xs = np.where(dm[int(round(dy1 - p[1]))])[0]
                o = (xs.max() if -e['dir'] > 0 else xs.min()) + dx0; sides.append(abs(o - p[0]))
            # only where the stretch pinched the ends (tighter than the drawn letter's); elsewhere the stretched
            # curves are kept, rebuilding them there only added lumps
            if min(now) < 0.8 * min(rs) and min(now) < 30:
                print(g, 'drawn ends', [round(x, 1) for x in rs], 'sides', [round(x) for x in sides],
                      'stretched', [round(x, 1) for x in now],
                      'rebuilt', round_ends(gy[g], gy, ROUND_ENDS[g], sum(rs) / len(rs), sides, stem=stem_at(weight))
                      or round_ends(gy[g], gy, ROUND_ENDS[g], sum(rs) / len(rs), sides, stem=stem_at(weight), tol=0.05))
            else: print(g, 'drawn ends', [round(x, 1) for x in rs], 'stretched', [round(x, 1) for x in now], 'kept')
    if wdth == 150 and 'o' in S_STEPS: open_s(gy['uni0073'], gy, hstem_of(gy['uni006F']))
    if wdth == 150:                                       # the @ as heavy as it fits (after its uprights matched)
        b_, a_ = at_weight(gy['uni0040'], gy, AT_WIDE * stem_at(weight), inst_at(weight)['uni0040'])
        print('@ stroke', round(b_ / stem_at(weight), 2), '->', round(a_ / stem_at(weight), 2))
    if wdth == 150 and 'p' in S_STEPS:                     # s counter ends: no tighter than 0.7 of the drawn
        import math                                        # letter's tighter end at this weight
        from curves import tight_turns
        dr = inst_at(weight); dg = dr['uni0073']
        rs = [min(r for r, x, y, _ in tight_turns(dg, dr) if math.dist((x, y), dg.coordinates[i]) < 120) for i in (11, 35)]
        print('s ends: target', round(0.7 * min(rs), 1), 'now', round_s_tips(gy['uni0073'], gy, 0.7 * min(rs)))
    if wdth == 150:                                       # S: no kink the drawn S doesn't have (Danny saw
        print('S smoothed', smooth_like_drawn(gy['S'], inst_at(weight)['S']))   # dips at 100/200)
    if wdth == 150:                                        # pinched turns (after the a's cached search)
        for g, turns in EASE.items():
            for slides, place, centre in (turns if isinstance(turns, list) else [turns]):
                print(g, 'turn: drawn, before, after', ease_turn(gy[g], gy, inst_at(weight)[g], slides, centre, place, keep=EASE_KEEP.get(g)))
    for g in Y.getGlyphOrder():
        gy[g].recalcBounds(gy)
        if Y['hmtx'][g][0] or gy[g].numberOfContours: Y['hmtx'][g] = (Y['hmtx'][g][0], getattr(gy[g], 'xMin', 0))
    Y['OS/2'].xAvgCharWidth = adv; Y['hhea'].advanceWidthMax = adv
    Y['OS/2'].usWidthClass = {75: 3, 87.5: 4, 100: 5, 112.5: 6}.get(wdth, 5)
    Y.save(out)


if __name__ == '__main__':
    main(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3])
