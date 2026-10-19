"""Straight-stroke letters drawn from their centre lines for a wide cell, every stroke one thickness.

    python3 wide.py <font.ttf> <weight>       (rewrites the font in place; run after wdth.py)

Stretching an outline sideways thickens its verticals, thins its diagonals as they lean over and leaves
its horizontals alone, so no one stretch keeps A V K X Y Z 4 even. These are drawn instead: each stroke
is a centre line given a thickness measured square to it (`t`, the weight's stem), with level cuts at
the cap height, x-height, baseline and descender like the rest of the font. Bars are `h`, a touch under
the stem as in the drawn weights (Bold's Z: 155 against 162). Overlaps are merged with skia-pathops.
"""
import math, sys
import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from wdth import stem_at

CAP, XH, DESC = 801, 606, -169


def para(x0, y0, x1, y1, t):
    """A stroke from (x0, y0) to (x1, y1) on its centre line, cut level at both ends, `t` thick square
    to its direction: level cuts make it wider across, by 1 / sin(angle)."""
    s = abs(y1 - y0) / math.hypot(x1 - x0, y1 - y0); hw = t / 2 / s
    return [(x0 - hw, y0), (x0 + hw, y0), (x1 + hw, y1), (x1 - hw, y1)]


def fit(xa, ya, sa, xb, yb, sb, t):
    """Centre line whose ends sit `sa`/`sb` = +1 inside a left edge, -1 inside a right edge, 0 on the
    point itself. The half-width depends on the angle, which depends on the ends, so iterate."""
    ca, cb = xa, xb
    for _ in range(8):
        s = abs(yb - ya) / math.hypot(cb - ca, yb - ya); hw = t / 2 / s
        ca, cb = xa + sa * hw, xb + sb * hw
    return ca, ya, cb, yb


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def at_y(line, y):
    x0, y0, x1, y1 = line
    return x0 + (x1 - x0) * (y - y0) / (y1 - y0)


TRIM = {}                                            # name: boxes cut away after the merge
CLIP = {}                                            # name: the outline a letter is cut down to


def letters(W, t, h, oh, sb=55):
    L, R, M = sb, W - sb, W / 2
    P = {}
    def v_shape(top):
        a = fit(L, top, 1, M, 0, 0, t); b = fit(R, top, -1, M, 0, 0, t)
        return [para(*a, t), para(*b, t)]
    def x_shape(top):
        return [para(*fit(L, top, 1, R, 0, -1, t), t), para(*fit(R, top, -1, L, 0, 1, t), t)]
    def z_shape(top, inset, h, td=None):
        d = fit(R - inset, top - h, -1, L, h, 1, td or t)
        return [rect(L + inset, top - h, R - inset, top), rect(L, 0, R, h), para(*d, td or t)]
    def k_shape(top, stem_top):
        # the arm runs on into the stem until its level-cut end is hidden there (its right corner
        # inside the stem's right edge); what pokes out left of the stem is trimmed in letters()
        arm = fit(R, top, -1, L + t, top * 0.36, 0, t)
        s = (arm[1] - arm[3]) / math.hypot(arm[2] - arm[0], arm[3] - arm[1]); hw = t / 2 / s
        ye = arm[1] + (L + t - hw - arm[0]) * (arm[3] - arm[1]) / (arm[2] - arm[0])
        arm = (arm[0], arm[1], L + t - hw, ye)
        jx = at_y(arm, top * 0.55)
        leg = fit(jx, top * 0.55, 0, R, 0, -1, t)
        return [rect(L, 0, L + t, stem_top), para(*arm, t), para(*leg, t)]
    P['V'] = v_shape(CAP)
    P['uni0076'] = v_shape(XH)
    a = fit(M, CAP, 0, L, 0, 1, t); b = fit(M, CAP, 0, R, 0, -1, t); yb = CAP * 0.22
    P['A'] = [para(*a, t), para(*b, t), rect(at_y(a, yb), yb, at_y(b, yb), yb + h)]
    P['X'] = x_shape(CAP)
    P['uni0078'] = x_shape(XH)
    yj = CAP * 0.42
    # Y: the arms run on a stem's depth into the stem (main() trims them to its width below the
    # join); ended level right at the join, their wide flat ends stuck out either side like ink traps
    def into_stem(a):
        x0, y0, x1, y1 = a; k = t / (y0 - y1)
        return (x0, y0, x1 + (x1 - x0) * k, y1 - t)
    # each arm's outer edge lands exactly on the stem's edge at the join, so the arm runs into the stem
    # with no step
    P['Y'] = [para(*into_stem(fit(L, CAP, 1, M - t / 2, yj, 1, t)), t),
              para(*into_stem(fit(R, CAP, -1, M + t / 2, yj, -1, t)), t),
              rect(M - t / 2, 0, M + t / 2, yj + 1)]
    # trimmed to the Y's outline: down each arm's outer edge to the stem's edge at the join, then down
    # the stem (the arms, run on into the stem, cross each other there and would show either side)
    la, ra = fit(L, CAP, 1, M - t / 2, yj, 1, t), fit(R, CAP, -1, M + t / 2, yj, -1, t)
    CLIP['Y'] = [(L - 1, CAP + 1), (M - t / 2, yj), (M - t / 2, -1), (M + t / 2, -1), (M + t / 2, yj), (R + 1, CAP + 1)]
    P['Z'] = z_shape(CAP, 15, h)
    # z: its bars are the o's level strokes, and its diagonal, which lies almost flat in the wide cell
    # and reads by its height, is the same thickness across, so all three strokes match the o
    P['uni007A'] = z_shape(XH, 10, oh, oh)
    # w: two v's side by side, outer legs from the top corners to the quarter points, inner legs up
    # to a peak at the middle, every leg the stem thickness
    q1, q3 = L + (R - L) * 0.27, R - (R - L) * 0.27
    P['uni0077'] = [para(*fit(L, XH, 1, q1, 0, 0, t), t), para(*fit(M, XH, 0, q1, 0, 0, t), t),
                    para(*fit(M, XH, 0, q3, 0, 0, t), t), para(*fit(R, XH, -1, q3, 0, 0, t), t)]
    P['K'] = k_shape(CAP, CAP)
    P['uni006B'] = k_shape(XH, 800)
    # y: the right arm runs on past the baseline to the descender, the left arm meets it at the baseline
    l = fit(L, XH, 1, M, 0, 0, t); rc = fit(R, XH, -1, M, 0, 0, t)
    xd = at_y(rc, DESC)
    P['uni0079'] = [para(*l, t), para(rc[0], XH, xd, DESC, t)]
    # 4: stem at 62% of the cell, a bar across, the diagonal from the stem's top to the bar's left end
    sx = round(W * 0.62); by = 160
    d = fit(sx + t, CAP, -1, L, by + h, 1, t)
    P['uni0034'] = [rect(sx, 0, sx + t, CAP), rect(L, by, R, by + h), para(*d, t)]
    return P


def union(polys, clip=None):
    path = pathops.Path()
    pen = path.getPen()
    for p in polys:
        # all pieces one way round, or an overlap of two opposite pieces cancels to a hole
        if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(p, p[1:] + p[:1])) < 0: p = p[::-1]
        pen.moveTo(p[0])
        for q in p[1:]: pen.lineTo(q)
        pen.closePath()
    path = pathops.simplify(path, clockwise=True)
    if clip:
        c = pathops.Path(); cp = c.getPen(); cp.moveTo(clip[0])
        for q in clip[1:]: cp.lineTo(q)
        cp.closePath()
        path = pathops.op(path, c, pathops.PathOp.INTERSECTION, clockwise=True)
    return path


def _contours(path):
    out = []
    for c in path.contours:
        pts = []
        for verb, seg in c.segments:
            pts.extend(seg)
        out.append([tuple(p) for p in pts])
    return out


def conform(gl, path, snap=60):
    """Move every point of the drawn glyph `gl` onto the rebuilt outline `path`, contour to contour
    (each drawn contour to the rebuilt one whose middle is nearest): to a rebuilt corner when one is
    within `snap` units, else straight onto the nearest edge. The drawn structure is kept exactly."""
    import math
    new = _contours(path)
    c = list(gl.coordinates); s = 0; out = c[:]
    def mid(ps): return (sum(x for x, _ in ps) / len(ps), sum(y for _, y in ps) / len(ps))
    for e in gl.endPtsOfContours:
        pts = c[s:e + 1]; m = mid(pts)
        tgt = min(new, key=lambda q: math.dist(mid(q), m))
        segs = [(tgt[i], tgt[(i + 1) % len(tgt)]) for i in range(len(tgt))]
        for i, p in enumerate(pts):
            v = min(tgt, key=lambda q: math.dist(q, p))
            if math.dist(v, p) <= snap:
                out[s + i] = v; continue
            best = None
            for (ax, ay), (bx, by) in segs:
                dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy or 1
                t = max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
                q = (ax + t * dx, ay + t * dy); d = math.dist(q, p)
                if best is None or d < best[0]: best = (d, q)
            out[s + i] = best[1]
        s = e + 1
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in out])


# edges across a stroke from each other, named by their first point, where the automatic search pairs
# the wrong edges (the k's arm and leg meet at a point the search can't see past)
MANUAL_PAIRS = {'uni006B': [(0, 2), (0, 10), (3, 5), (6, 8)],
                'uni0079': [(7, 9), (10, 12), (5, 12)]}     # y: left arm, right arm (and its run into the tail)


def edge_pairs(gl, tol=5, manual=None):
    """Straight edges across a stroke from each other: for each edge (contour, index), the nearest
    edge running the opposite way within 5 degrees, overlapping it, on its inner side. Returns
    {edge: (partner, distance)}."""
    import math
    c = gl.coordinates; E = []; s = 0
    if manual:
        import math as _m
        n = len(c); out = {}
        def key(i): return (0, n, i)
        for i, j in manual:
            for a_, b_ in ((i, j), (j, i)):
                a, b = c[a_], c[(a_ + 1) % n]; L = _m.dist(a, b); nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
                m2 = ((c[b_][0] + c[(b_ + 1) % n][0]) / 2, (c[b_][1] + c[(b_ + 1) % n][1]) / 2)
                d = -((m2[0] - a[0]) * nx + (m2[1] - a[1]) * ny)
                if key(a_) not in out: out[key(a_)] = (key(b_), d)
        return out
    for ci, e in enumerate(gl.endPtsOfContours):
        n = e - s + 1
        for i in range(n):
            a, b = c[s + i], c[s + (i + 1) % n]; L = math.dist(a, b)
            if L > 20: E.append(((s, n, i), a, b, L))
        s = e + 1
    out = {}
    for k, a, b, L in E:
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L; nx, ny = -uy, ux        # outward (clockwise)
        best = None
        for k2, a2, b2, L2 in E:
            if k2 == k: continue
            vx, vy = (b2[0] - a2[0]) / L2, (b2[1] - a2[1]) / L2
            if ux * vx + uy * vy > -math.cos(math.radians(tol)): continue      # must run the other way
            m = ((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2)
            d = -((m[0] - a[0]) * nx + (m[1] - a[1]) * ny)                     # inward distance
            proj = [((p[0] - a[0]) * ux + (p[1] - a[1]) * uy) for p in (a2, b2)]
            if 20 < d < 450 and max(proj) > 0 and min(proj) < L and (best is None or d < best[1]): best = (k2, d)
        if best: out[k] = best
    return out


# edges that lie on another edge's line (k: the arm's underside runs on past the leg, 9 on 5's line)
COLINEAR = {'uni006B': [(9, 5)]}


def edge_even(gl, bar, other, rounds=30, manual=None, colinear=()):
    """Set every stroke of an all-straight glyph to its thickness by moving its edges: each edge of
    a pair is first turned (about its middle) to run exactly parallel to its partner, the two
    splitting the difference in angle, then moved so the stroke is `bar` thick if within 12 degrees
    of level, `other` if not, each edge half the difference. Edges on the letter's outer box (cap
    height, baseline, far left or right) hold, so the letter keeps its size. Corners are recomputed
    where the moved edges meet. The drawn points and contours stay exactly as they are."""
    import math
    c = list(gl.coordinates); xs = [x for x, _ in c]; ys = [y for _, y in c]
    X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)     # the letter's box, held throughout
    smooth = set()                                          # (point, handle) joins smooth as drawn
    fl0, s0 = list(gl.flags), 0
    for e0 in gl.endPtsOfContours:
        n0 = e0 - s0 + 1
        for i in range(n0):
            if not fl0[s0 + i] & 1: continue
            for edge, h, sign in ((i - 1, i + 1, 1), (i, i - 1, -1)):
                if not (fl0[s0 + edge % n0] & 1 and fl0[s0 + (edge + 1) % n0] & 1) or fl0[s0 + h % n0] & 1: continue
                a0, b0 = c[s0 + edge % n0], c[s0 + (edge + 1) % n0]; p0, h0 = c[s0 + i], c[s0 + h % n0]
                ex, ey = b0[0] - a0[0], b0[1] - a0[1]; hx, hy = h0[0] - p0[0], h0[1] - p0[1]
                Le, Lh = math.hypot(ex, ey), math.hypot(hx, hy)
                if Le and Lh and (ex * hx + ey * hy) * sign / (Le * Lh) > math.cos(math.radians(15)):
                    smooth.add((s0 + i, s0 + h % n0))
        s0 = e0 + 1
    hold = set()                                            # edges kept still: a corner would leave the box
    for _ in range(rounds):
        c = list(gl.coordinates)
        def on_box(a, b, k=None):
            return k in hold or (abs(a[1] - b[1]) < 2 and (abs(a[1] - Y0) < 2 or abs(a[1] - Y1) < 2)) or \
                   (abs(a[0] - b[0]) < 2 and (abs(a[0] - X0) < 2 or abs(a[0] - X1) < 2))
        def ends(k):
            s, n, i = k; return c[s + i], c[s + (i + 1) % n]
        lines = {}                                                  # edge: (point, direction)
        for k, (k2, d) in edge_pairs(gl, tol=15, manual=manual).items():   # edges up to 15 degrees apart: turned parallel
            a, b = ends(k); a2, b2 = ends(k2)
            L, L2 = math.dist(a, b), math.dist(a2, b2)
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L); v = ((a2[0] - b2[0]) / L2, (a2[1] - b2[1]) / L2)
            fixed, pfixed = on_box(a, b, k), on_box(a2, b2, k2)
            if fixed: continue
            w = u if pfixed else ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2)
            if pfixed: w = v
            Lw = math.hypot(*w); w = (w[0] / Lw, w[1] / Lw); nx, ny = -w[1], w[0]
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); m2 = ((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2)
            dp = -((m2[0] - m[0]) * nx + (m2[1] - m[1]) * ny)        # across the stroke, square to it
            ang = abs(math.degrees(math.atan2(w[1], w[0]))) % 180
            target = bar if min(ang, 180 - ang) < 12 else other
            if dp > 2.5 * target: continue                          # not across a stroke
            diff = target - dp
            if pfixed: sh = diff
            elif abs(diff) < 2: sh = diff if k < k2 else 0         # half a unit each would round back
            else: sh = diff / 2
            lines[k] = ((m[0] + nx * sh, m[1] + ny * sh), w)
        for a_, b_ in colinear:                                 # same line as its partner piece
            n_ = len(c); kb = (0, n_, b_)
            if kb in lines: lines[(0, n_, a_)] = lines[kb]
            else:
                pa, pb = c[b_], c[(b_ + 1) % n_]; L_ = math.dist(pa, pb)
                lines[(0, n_, a_)] = (pa, ((pb[0] - pa[0]) / L_, (pb[1] - pa[1]) / L_))
        new = c[:]; s = 0; fl = list(gl.flags)
        for e in gl.endPtsOfContours:
            n = e - s + 1
            def on(i): return fl[s + i % n] & 1
            def straight(i): return on(i) and on(i + 1)            # edge i: point i to i+1, no handle between
            def line(i):
                k = (s, n, i % n)
                if k in lines: return lines[k]
                a, b = c[s + i % n], c[s + (i + 1) % n]; L = math.dist(a, b) or 1
                return a, ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            def onto(i, p):                                         # p dropped onto edge i's new line
                q, d = line(i); t = (p[0] - q[0]) * d[0] + (p[1] - q[1]) * d[1]
                return (q[0] + d[0] * t, q[1] + d[1] * t)
            for i in range(n):
                if not on(i): continue
                si, so = straight(i - 1), straight(i)
                if si and so:
                    (p1, d1), (p2, d2) = line(i - 1), line(i)
                    den = d1[0] * d2[1] - d1[1] * d2[0]
                    if abs(den) < 1e-6: new[s + i] = onto(i, c[s + i]); continue
                    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
                    new[s + i] = (p1[0] + d1[0] * t, p1[1] + d1[1] * t)
                elif so: new[s + i] = onto(i, c[s + i])             # a curve comes in: follow the edge out
                elif si: new[s + i] = onto(i - 1, c[s + i])         # a curve goes out: follow the edge in
            for i in range(n):                                      # handles ride with the points either side
                if on(i): continue
                j = i
                while not on(j - 1): j -= 1
                k2 = i
                while not on(k2 + 1): k2 += 1
                a_, b_ = s + (j - 1) % n, s + (k2 + 1) % n
                dx = ((new[a_][0] - c[a_][0]) + (new[b_][0] - c[b_][0])) / 2
                dy = ((new[a_][1] - c[a_][1]) + (new[b_][1] - c[b_][1])) / 2
                new[s + i] = (c[s + i][0] + dx, c[s + i][1] + dy)
            # where a straight edge runs into a curve smoothly in the drawing, the curve's first handle
            # goes back onto the edge's line (same distance from the point), or the join gets a bump
            for i in range(n):
                if not on(i): continue
                for edge, h, sign in ((i - 1, i + 1, 1), (i, i - 1, -1)):
                    if not (straight(edge) and not on(h)): continue
                    a0, b0 = c[s + edge % n], c[s + (edge + 1) % n]; p0, h0 = c[s + i], c[s + h % n]
                    ex, ey = b0[0] - a0[0], b0[1] - a0[1]; hx, hy = h0[0] - p0[0], h0[1] - p0[1]
                    Le, Lh = math.hypot(ex, ey), math.hypot(hx, hy)
                    if not Le or not Lh: continue
                    if (s + i, s + h % n) not in smooth: continue          # a corner in the drawing
                    a1, b1 = new[s + edge % n], new[s + (edge + 1) % n]; L1 = math.dist(a1, b1)
                    ux, uy = (b1[0] - a1[0]) / L1 * sign, (b1[1] - a1[1]) / L1 * sign
                    new[s + h % n] = (new[s + i][0] + ux * Lh, new[s + i][1] + uy * Lh)
            s = e + 1
        # a corner pushed outside the box: hold the edges meeting there from now on, and redo
        out = [i for i, (x, y) in enumerate(new) if x > X1 + 1 or x < X0 - 1 or y > Y1 + 1 or y < Y0 - 1]
        if out:
            s = 0
            for e in gl.endPtsOfContours:
                n = e - s + 1
                for i in out:
                    if s <= i <= e: hold.update({(s, n, (i - s) % n), (s, n, (i - s - 1) % n)})
                s = e + 1
            continue
        gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in new])


def close_y_trap(gl):
    """The drawn y ends its left arm in a small level cut (6-7) against the right arm, an ink trap.
    Its left edge (8-7) is run on until it meets the right arm's inner edge (6-5): both cut points go
    there, so the arms join with no notch and the point count stays the drawn one."""
    c = list(gl.coordinates)
    (x1, y1), (x2, y2) = c[8], c[7]; (x3, y3), (x4, y4) = c[5], c[6]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9: return
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    p = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    import math
    L = math.dist(c[5], c[6]); ux, uy = (x4 - x3) / L, (y4 - y3) / L
    if (p[0] - x3) * ux + (p[1] - y3) * uy < 0:
        # the arms meet below where the tail's curve starts (heavy weights): the curve starts there
        # instead, its handle kept on the arm's line so the join stays smooth
        h = math.dist(c[4], c[5]); c[5] = p; c[4] = (p[0] - ux * h, p[1] - uy * h)
    c[6] = c[7] = p
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])


def cross_x(gl, t):
    """x and X: two straight strokes crossing, drawn as 12 corners: 4 feet, 4 tops, 2 side crossings
    and 2 middle crossings (found by where they sit, so X and x number them differently). Each stroke
    keeps its outer corners on the letter's box ('/' from its bottom-left to its top-right, the other
    from top-left to bottom-right) and is exactly `t` across; every other corner is where two stroke
    edges meet, or where one meets the baseline or the top. The drawn structure stays."""
    import math
    c = list(gl.coordinates); y0, y1 = min(y for _, y in c), max(y for _, y in c)
    X0, X1 = min(x for x, _ in c), max(x for x, _ in c)
    feet = sorted((i for i in range(12) if abs(c[i][1] - y0) < 2), key=lambda i: c[i][0])
    tops = sorted((i for i in range(12) if abs(c[i][1] - y1) < 2), key=lambda i: c[i][0])
    mids = [i for i in range(12) if i not in feet and i not in tops]
    if len(feet) != 4 or len(tops) != 4 or len(mids) != 4: return False
    lw, rw = min(mids, key=lambda i: c[i][0]), max(mids, key=lambda i: c[i][0])
    tc, bc = (lambda m: (max(m, key=lambda i: c[i][1]), min(m, key=lambda i: c[i][1])))([i for i in mids if i not in (lw, rw)])
    def pair(A, B, side):
        """Two parallel lines t apart, one through A and one through B (A, B opposite outer corners)."""
        dx, dy = B[0] - A[0], B[1] - A[1]; L = math.hypot(dx, dy); r = side * math.asin(min(1, t / L))
        u = (dx / L * math.cos(r) - dy / L * math.sin(r), dx / L * math.sin(r) + dy / L * math.cos(r))
        return (A, u), (B, u)
    sl_l, sl_r = pair((X0, y0), (X1, y1), 1)            # '/': left edge through bottom-left, right through top-right
    bs_l, bs_r = pair((X0, y1), (X1, y0), -1)           # '\': left edge through top-left, right through bottom-right
    def meet(l1, l2):
        (p1, d1), (p2, d2) = l1, l2; den = d1[0] * d2[1] - d1[1] * d2[0]
        k = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        return (p1[0] + d1[0] * k, p1[1] + d1[1] * k)
    def level(l, y):
        (p, d) = l; k = (y - p[1]) / d[1]; return (p[0] + d[0] * k, y)
    new = {feet[0]: level(sl_l, y0), feet[1]: level(sl_r, y0), feet[2]: level(bs_l, y0), feet[3]: level(bs_r, y0),
           tops[0]: level(bs_l, y1), tops[1]: level(bs_r, y1), tops[2]: level(sl_l, y1), tops[3]: level(sl_r, y1),
           lw: meet(sl_l, bs_l), rw: meet(sl_r, bs_r), tc: meet(bs_r, sl_l), bc: meet(bs_l, sl_r)}
    gl.coordinates = type(gl.coordinates)([(round(new[i][0]), round(new[i][1])) for i in range(12)])
    return True


def square_z(gl):
    """Z: the drawn top bar is inset from the bottom one on both sides (82 against 60 on the
    left at width 100); wide and heavy it shows as a step. The top bar's ends (its upright edges, 4-5
    on the left and 6-7 on the right) go out to the bottom bar's, so both sides run straight up."""
    c = list(gl.coordinates); X0, X1 = min(x for x, _ in c), max(x for x, _ in c)
    for i in (4, 5): c[i] = (X0, c[i][1])
    for i in (6, 7): c[i] = (X1, c[i][1])
    gl.coordinates = type(gl.coordinates)(c)


def build_n(gl, t):
    """N, its 10 drawn points: left stem 0 1 (2 at its top-right), right stem 4 5 6 (7 at its
    bottom-left), the diagonal's edges 2-3 and 7-8, 9 the left stem's bottom-right. Both stems are
    `t`; the diagonal runs from the left stem's top-right corner to the right stem's bottom-left
    corner, `t` across, so the flat caps at top-left and bottom-right are a full stem wide, as in the
    drawn N and the Z."""
    import math
    c = list(gl.coordinates)
    if len(c) != 10: return False
    L, R = min(x for x, _ in c), max(x for x, _ in c); y0, y1 = min(y for _, y in c), max(y for _, y in c)
    A, B = (L + t, y1), (R - t, y0)                  # the diagonal's outer corners
    dx, dy = B[0] - A[0], B[1] - A[1]; D = math.hypot(dx, dy); r = math.asin(min(1, t / D))
    # direction of both edges: A->B turned so lines through A and through B are t apart
    u = (dx / D * math.cos(r) - dy / D * math.sin(r), dx / D * math.sin(r) + dy / D * math.cos(r))
    if (A[1] + ((R - t) - A[0]) * u[1] / u[0]) < y0 or (A[1] + ((R - t) - A[0]) * u[1] / u[0]) > y1:
        u = (dx / D * math.cos(r) + dy / D * math.sin(r), -dx / D * math.sin(r) + dy / D * math.cos(r))
    def at_x(P, x): return (x, P[1] + (x - P[0]) * u[1] / u[0])
    c[0], c[1], c[2], c[9] = (L, y0), (L, y1), A, (L + t, y0)
    c[4], c[5], c[6], c[7] = (R - t, y1), (R, y1), (R, y0), B
    c[3], c[8] = at_x(A, R - t), at_x(B, L + t)
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
    return True


def k_into_stem(gl, t):
    """K is two pieces: the stem, and the arm and leg as one '<' that overlaps it. Light and wide, the
    '<' point stopped short of the stem's right edge (219 against 217 at 150/100): a hairline gap.
    The '<' is stretched sideways from its right edge until its point is half a stem inside."""
    c = list(gl.coordinates); e0 = gl.endPtsOfContours[0]
    stem_r = max(x for x, _ in c[:e0 + 1]); lt = list(range(e0 + 1, len(c)))
    vx = min(c[i][0] for i in lt); X1 = max(c[i][0] for i in lt); want = stem_r - t / 2
    if vx <= want: return False
    f = (X1 - want) / (X1 - vx)
    for i in lt: c[i] = (X1 - (X1 - c[i][0]) * f, c[i][1])
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
    return True


EDGE = {'K', 'uni006B', 'Z', 'uni007A', 'uni0034', 'uni0077', 'uni0079', 'N'}

# ^ < >: two arms meeting at a cut point. Each arm: (outer foot, outer cut point, inner foot, notch
# point); the feet sit on the arms' cut ends, the cut points on the flat where the arms meet
CHEVRONS = {'uni005E': [(0, 1, 7, 6), (3, 2, 4, 5)],
            'uni003C': [(3, 2, 4, 5), (0, 1, 7, 6)],
            'uni003E': [(5, 6, 4, 3), (0, 7, 1, 2)]}


def _join_circle(gl, glyf):
    """The biggest circle inside the letter, across (font units): where the arms of a chevron meet."""
    from scipy import ndimage
    from measure import raster
    m, _, _ = raster(gl, glyf, 1)
    return 2 * ndimage.distance_transform_edt(m).max()


def chevron(gl, glyf, t, circle):
    """^ < >: stretched wide, their arms lie flatter. Each arm is set to `t` straight across: its outer
    edge stays (foot and direction), its inner edge runs parallel `t` inside it, the inner foot and the
    notch slide onto that line (the notch keeps its place across the letter, so the arms still cross
    there as drawn). For < and >, whose arms lie flattest, the meeting point grows into a blob as the
    angle between the arms closes (the biggest circle inside, 1.41 stems at 150/900 against 1.07
    drawn): the flat where the arms meet is cut back along the outer edges until that circle is no
    bigger than `circle` (the drawn letter's, at this weight), and the letter is centred again. The
    drawn points stay, in order."""
    import math
    name = next(n for n in CHEVRONS if glyf[n] is gl)
    arms = CHEVRONS[name]; up = name == 'uni005E'           # ^: axis upright; < >: axis level
    c0 = [tuple(map(float, p)) for p in gl.coordinates]
    def build(trim):
        c = list(c0)
        for A, P, G, N in arms:
            a, p = c0[A], c0[P]
            dx, dy = p[0] - a[0], p[1] - a[1]; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
            nx, ny = -uy, ux                                    # one side of the outer edge
            g = c0[G]
            if (g[0] - a[0]) * nx + (g[1] - a[1]) * ny < 0: nx, ny = -nx, -ny   # toward the inner edge
            q = (a[0] + nx * t, a[1] + ny * t)                  # a point on the inner edge
            def on_line(o, d, coord, val):                      # where line o + s d has coord == val
                s = (val - o[coord]) / d[coord]; return (o[0] + d[0] * s, o[1] + d[1] * s)
            foot = 1 if up else 0                               # feet: level cut (^) or upright cut (< >)
            c[G] = on_line(q, (ux, uy), foot, a[foot])
            c[N] = on_line(q, (ux, uy), 1 - foot, c0[N][1 - foot])
            if up: c[P] = on_line(a, (ux, uy), 1, p[1])
            else:                                               # the flat, cut back toward the feet
                side = 1 if a[0] > p[0] else -1
                c[P] = on_line(a, (ux, uy), 0, p[0] + side * trim)
        if trim and not up:
            # the drawn notch points lie just past where the inner edges cross; cut back, the flat
            # would pass them and they would poke out of it: both go to the crossing (the notch's tip)
            (A1, _, G1, N1), (A2, _, G2, N2) = arms
            d1 = (c[N1][0] - c[G1][0], c[N1][1] - c[G1][1]); d2 = (c[N2][0] - c[G2][0], c[N2][1] - c[G2][1])
            den = d1[0] * d2[1] - d1[1] * d2[0]
            s_ = ((c[G2][0] - c[G1][0]) * d2[1] - (c[G2][1] - c[G1][1]) * d2[0]) / den
            c[N1] = c[N2] = (c[G1][0] + d1[0] * s_, c[G1][1] + d1[1] * s_)
            # centred in the cell again
            sh = -(1 if c0[arms[0][0]][0] > c0[arms[0][1]][0] else -1) * trim / 2
            c = [(x + sh, y) for x, y in c]
        gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
    build(0)
    if up or _join_circle(gl, glyf) <= circle: return 0
    lo, hi = 0.0, 3 * t
    for _ in range(14):
        mid = (lo + hi) / 2; build(mid)
        if _join_circle(gl, glyf) > circle: lo = mid
        else: hi = mid
    build(hi)
    return hi


def main(fpath, weight):
    f = TTFont(fpath); gl = f['glyf']
    W = f['hmtx']['H'][0]; t = stem_at(weight); h = round(t * 0.94)
    o = gl['uni006F']; o.recalcBounds(gl); c = o.coordinates; e = o.endPtsOfContours[0]
    oh = max(y for x, y in c[:e + 1]) - max(y for x, y in c[e + 1:])     # the o's ring at the top
    for name in list(letters(W, t, h, oh)):
        # each letter keeps the width the stretch gave it (its drawn width plus the cell's extra), so
        # its side margins come from the stretched letter it replaces, not one margin for all
        old = gl[name]; old.recalcBounds(gl); sb = (W - (old.xMax - old.xMin)) / 2
        TRIM.clear(); CLIP.clear()
        polys = letters(W, t, h, oh, sb=sb)[name]
        pen = TTGlyphPen(None)
        path = union(polys, rect(sb, DESC - 50, W, 1000) if name in ('K', 'uni006B') else None)
        if name in CLIP:
            path = pathops.op(path, union([CLIP[name]]), pathops.PathOp.INTERSECTION, clockwise=True)
        for box in TRIM.get(name, ()):
            path = pathops.op(path, union([box]), pathops.PathOp.DIFFERENCE, clockwise=True)
        # keep the drawn letter's points (so it still interpolates with width 100 and the other
        # weights): letters built like the rebuilt one move each point onto its outline; the rest
        # (drawn differently: K is two overlapping pieces) keep their own edges, set to thickness
        if name in ('uni0078', 'X') and old.numberOfContours == 1 and len(old.coordinates) == 12 and cross_x(old, t):
            pass
        elif name in EDGE:
            # every stroke one thickness: the stem's, z's the o's ring (bars and diagonal alike)
            bar, other = {'uni007A': (oh, oh)}.get(name, (t, t))
            if name == 'Z': square_z(old)
            edge_even(old, bar, other, manual=MANUAL_PAIRS.get(name), colinear=COLINEAR.get(name, ()))
            if name == 'uni0079': close_y_trap(old)
            if name == 'K' and k_into_stem(old, t):
                edge_even(old, bar, other)
        else:
            conform(old, path)
        old.recalcBounds(gl); f['hmtx'][name] = (W, old.xMin)
    # straight letters the stretch leaves uneven that were never rebuilt (N's diagonal came out half as
    # thick again as its stems): every stroke set to the stem by its own edges
    for name in sorted(EDGE - set(letters(W, t, h, oh))):
        g = gl[name]
        if name == 'N' and build_n(g, t): pass
        else: edge_even(g, t, t, manual=MANUAL_PAIRS.get(name))
        g.recalcBounds(gl); f['hmtx'][name] = (W, g.xMin)
    # ^ < >: arms one stem across, the join no heavier than the drawn letter's at this weight
    import os
    from fontTools.varLib.instancer import instantiateVariableFont
    vf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../build/variable/ProxyMono[wght].ttf')
    dr = instantiateVariableFont(TTFont(vf), {'wght': weight})['glyf']
    for name in CHEVRONS:
        g = gl[name]; trim = chevron(g, gl, t, _join_circle(dr[name], dr))
        g.recalcBounds(gl); f['hmtx'][name] = (W, g.xMin)
        print(name, 'join', round(_join_circle(g, gl)), 'drawn', round(_join_circle(dr[name], dr)), 'flat cut back', round(trim))
    # the Q's tail (its last contour, a straight four-sided stroke) set to the stem across
    q = gl['Q']; s0 = q.endPtsOfContours[-2] + 1
    import copy
    tail = copy.deepcopy(q); tail.coordinates = type(q.coordinates)(list(q.coordinates)[s0:])
    tail.flags = type(q.flags)(list(q.flags)[s0:]); tail.endPtsOfContours = [len(tail.coordinates) - 1]
    tail.numberOfContours = 1
    edge_even(tail, t, t)
    q.coordinates = type(q.coordinates)(list(q.coordinates)[:s0] + list(tail.coordinates))
    q.recalcBounds(gl); f['hmtx']['Q'] = (W, q.xMin)
    r = gl['R']
    if r_leg(r, t): r.recalcBounds(gl); f['hmtx']['R'] = (W, r.xMin)
    f.save(fpath)


def r_leg(gl, t):
    """R's leg is its own contour (13-16: inner foot, inner top, outer top, outer foot), cut level at
    the baseline and where it tucks into the bowl. Stretched, it lies flatter and comes out thin (0.72
    of the stem at 150/900). The outer edge (15-16) stays, so the foot keeps its place in the cell; the
    inner edge (13-14) is set parallel to it, `t` across, its points sliding along their level cuts."""
    import math
    c = list(gl.coordinates)
    if list(gl.endPtsOfContours) != [12, 16, 25] or not all(gl.flags[i] & 1 for i in range(13, 17)): return False
    (ax, ay), (bx, by) = c[15], c[16]                     # outer edge, top to foot
    if abs(c[13][1] - c[16][1]) > 1 or abs(c[14][1] - c[15][1]) > 1: return False
    L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L
    nx, ny = -uy, ux                                      # normal; pointing toward the inner edge
    if (c[14][0] - ax) * nx + (c[14][1] - ay) * ny < 0: nx, ny = -nx, -ny
    px, py = ax + nx * t, ay + ny * t                     # a point on the new inner edge
    for i in (13, 14):                                    # where it crosses each level cut
        y = c[i][1]; c[i] = (px + ux * (y - py) / uy, y)
    gl.coordinates = type(gl.coordinates)([(round(x), round(y)) for x, y in c])
    return True


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]))
