"""The & at a wider width, drawn from its centre line and stroke widths (wdth.py calls amp_wide).

Stretched, the & went wrong in four ways (Danny, 400 to 900 at every width): the diagonal bent at the
crossing, the tail swelled where it rises out of the diagonal, the two counters squashed into flat slivers
with pointed ends, and the middle read as a dark knot. Evening the stretched outline edge by edge could not
fix the counters: wide and heavy, the outer curves turn tighter than the stroke is thick, so the inner
edge, an offset of the outer one, folds into a point.

So the wide & is drawn the way a letter is designed: a centre line, and a width for each stroke.

  * the diagonal: one straight centre line through the crossing X, its upper edge through the foot's
    outer corner; as thick as the drawn diagonal
  * the rest of the letter is one more centre line: from X up the loop's left side, over the top, down the
    right side, back through X (the waist) and on round the bowl into the diagonal above the foot. Its
    thickness at each place is the drawn letter's for a stroke running that way (upright and level
    measured on the drawn loop and bowl, blended by direction), so the strokes are even and level strokes
    stay as thin as drawn
  * the tail: a curve from the diagonal to its cut end, as thick as the drawn tail, its cut at the drawn
    cut's angle to the stroke

The loop's corners are quarters whose ends are as round as the loop's height allows, and the curves
through X take the handle lengths that keep their tightest turn loosest: so every inner edge stays a curve
(no point) at 900. The edges are the centre line offset by half the width each side; where two edges meet
(the crotches at X, the tail's root, the bowl into the diagonal) is where the drawn letter has a corner.
The drawn letter's points are then fitted to the edges run by run, corner to extreme: the same 58 points,
contours, order and on/off flags, so it interpolates with width 100, and every smooth on-curve point is an
extreme with its handles level or upright, so it stays smooth in every blend.

Proportions come from the stretched letter (its cell, the loop's and bowl's extremes, the crossing, the
foot and the tail's cut); the loop is drawn at 0.85 of its stretched width, which leaves the curves into X
room to turn. The waist crosses X at 22 degrees: steeper, the curves either side of X turn back on
themselves (a wave in the waist); flatter, the bowl's top reads as a flat bar.
"""
import math
import numpy as np
from scipy.optimize import least_squares, minimize
from scipy.ndimage import gaussian_filter1d

PHI = 22            # the waist's angle below level where it crosses X (degrees)
LOOP_W = 0.85       # the loop's width over the stretched loop's
ROUND = 0.95        # the loop's and bowl's ends: turning radius over the room they have


def _cubic(P0, P1, P2, P3, n=400):
    t = np.linspace(0, 1, n)[:, None]; u = 1 - t
    return u ** 3 * P0 + 3 * u * u * t * P1 + 3 * u * t * t * P2 + t ** 3 * P3


def _unit(v):
    v = np.asarray(v, float); return v / np.linalg.norm(v)


def _curv(S):
    d1 = np.gradient(S, axis=0); d2 = np.gradient(d1, axis=0)
    return (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.linalg.norm(d1, axis=1) ** 3, 1e-12)


def _gentle(P, tP, Q, tQ, n=160):
    """Cubic from P (tangent tP) to Q (tangent tQ), handle lengths chosen so its tightest turn is loosest."""
    L = np.linalg.norm(Q - P); best = None
    for a in np.linspace(0.1, 1.1, 21):
        for b in np.linspace(0.1, 1.1, 21):
            C = _cubic(P, P + tP * a * L, Q - tQ * b * L, Q, n)
            k = np.abs(_curv(C)).max()
            if best is None or k < best[0]: best = (k, C)
    return best[1]


def _quarter(P, tP, Q, tQ, rP, rQ):
    """Cubic from P (tangent tP) to Q (tangent tQ) turning with radius rP at P and rQ at Q, as near as handle
    lengths (0.15 to 1 of the run along each tangent) allow."""
    al, be = np.linalg.solve(np.array([tP, tQ]).T, Q - P)
    cr = abs(tP[0] * tQ[1] - tP[1] * tQ[0])
    def cost(h):
        k0 = (2 / 3) * (be - h[1]) * cr / h[0] ** 2; k1 = (2 / 3) * (al - h[0]) * cr / h[1] ** 2
        return (k0 * rP - 1) ** 2 + (k1 * rQ - 1) ** 2
    h0, h1 = minimize(cost, [0.55 * al, 0.55 * be], bounds=[(0.15 * al, al), (0.15 * be, be)], method='L-BFGS-B').x
    return _cubic(P, P + tP * h0, Q - tQ * h1, Q)


def _left(S):
    T = np.gradient(S, axis=0); T /= np.maximum(np.linalg.norm(T, axis=1), 1e-9)[:, None]
    return np.stack([-T[:, 1], T[:, 0]], 1)


def _crossings(P, Q):
    """Every crossing of polylines P and Q: (place along P, place along Q, point), places as fractional
    indices."""
    out = []; A, e = Q[:-1], Q[1:] - Q[:-1]
    for i in range(len(P) - 1):
        a, d = P[i], P[i + 1] - P[i]
        den = d[0] * e[:, 1] - d[1] * e[:, 0]
        with np.errstate(divide='ignore', invalid='ignore'):
            s = ((A[:, 0] - a[0]) * e[:, 1] - (A[:, 1] - a[1]) * e[:, 0]) / den
            r = ((A[:, 0] - a[0]) * d[1] - (A[:, 1] - a[1]) * d[0]) / den
        for j in np.where((s >= 0) & (s < 1) & (r >= 0) & (r < 1))[0]:
            out.append((i + s[j], j + r[j], a + s[j] * d))
    return out


def _line(a, u, L=3000):
    return np.array([a - u * L, a + u * L])


def _between(P, i, j):
    """Polyline P from place i to place j (either order)."""
    def at(f): k = min(int(f), len(P) - 2); return P[k] + (f - k) * (P[k + 1] - P[k])
    if i <= j: return np.vstack([at(i), P[int(i) + 1:int(j) + 1], at(j)])
    return _between(P, j, i)[::-1]


def _extreme(P, axis, sign):
    v = P[:, axis] * sign; i = int(np.argmax(v)); return float(i), P[i].copy()


def _quad_run(pts, n=16):
    """On-curve, handles, on-curve: the TrueType curve (implied on-points between handles), sampled."""
    pts = [np.asarray(p, float) for p in pts]
    offs = pts[1:-1]; ons = [pts[0]] + [(offs[k] + offs[k + 1]) / 2 for k in range(len(offs) - 1)] + [pts[-1]]
    out = []
    for k, h in enumerate(offs):
        t = np.linspace(0, 1, n, endpoint=False)[:, None]
        out.append((1 - t) ** 2 * ons[k] + 2 * (1 - t) * t * h + t * t * ons[k + 1])
    out.append(pts[-1][None]); return np.vstack(out)


def _dist(Q, P):
    """Distance from each of Q to the polyline P."""
    A, B = P[:-1], P[1:]; d = B - A; L2 = np.maximum((d ** 2).sum(1), 1e-12)
    v = Q[:, None, :] - A[None]; t = np.clip((v * d[None]).sum(2) / L2[None], 0, 1)
    q = A[None] + t[..., None] * d[None]
    return np.sqrt(((Q[:, None, :] - q) ** 2).sum(2)).min(1)


def _fit_run(a, b, nh, target, lock_a=None, lock_b=None):
    """The nh handles between on-curve points a and b fitted to the edge `target` (from a to b). lock 'x' or
    'y': that end is an extreme, its handle keeps the end's x (or y), on the edge's side of it."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(target, axis=0), axis=1))]
    init = [target[min(np.searchsorted(L, L[-1] * (k + 1) / (nh + 1)), len(target) - 1)] for k in range(nh)]
    def ax(lock): return 1 if lock == 'x' else 0
    def side(lock, end, f):
        q = target[min(len(target) - 1, np.searchsorted(L, f * L[-1]))]
        return 1.0 if q[ax(lock)] >= end[ax(lock)] else -1.0
    sa = side(lock_a, a, 0.15) if lock_a else 0; sb = side(lock_b, b, 0.85) if lock_b else 0
    def unpack(v):
        hs = []; k = 0
        for i in range(nh):
            if i == 0 and lock_a: h = a.copy(); h[ax(lock_a)] += sa * v[k]; hs.append(h); k += 1
            elif i == nh - 1 and lock_b: h = b.copy(); h[ax(lock_b)] += sb * v[k]; hs.append(h); k += 1
            else: hs.append(v[k:k + 2]); k += 2
        return hs
    v0, lo = [], []
    for i, h in enumerate(init):
        if i == 0 and lock_a: v0.append(max(2.0, sa * (h - a)[ax(lock_a)])); lo.append(1.0)
        elif i == nh - 1 and lock_b: v0.append(max(2.0, sb * (h - b)[ax(lock_b)])); lo.append(1.0)
        else: v0 += list(h); lo += [-np.inf, -np.inf]
    tq = target[::max(1, len(target) // 80)]
    # a handle next to a corner kept a fifth of the run off it: fitted onto the corner, it left a hook
    # there (a turn of radius 0.3 next to 44 at 150/600)
    gap = 0.2 * np.linalg.norm(b - a)
    def res(v):
        hs = unpack(v); S = _quad_run([a] + hs + [b])
        keep = [max(0.0, gap - np.linalg.norm(hs[0] - a)) if not lock_a else 0.0,
                max(0.0, gap - np.linalg.norm(hs[-1] - b)) if not lock_b else 0.0]
        return np.r_[_dist(S, target), _dist(tq, S), 3 * np.array(keep)]
    r = least_squares(res, np.array(v0, float), bounds=(lo, np.inf), xtol=1e-8, ftol=1e-8)
    return unpack(r.x), float(np.abs(r.fun).max())


def drawn_widths(d):
    """The drawn &'s strokes: loop and bowl (upright, level), diagonal and tail, in units."""
    d = [np.asarray(p, float) for p in d]
    u = _unit(d[21] - d[20])
    tail_o = _quad_run([d[25], d[26], d[27], d[28]], 40); tail_i = _quad_run([d[21], d[22], d[23], d[24]], 40)
    return dict(bowl=np.array([d[41][0] - d[3][0], d[34][1] - d[0][1]]),
                loop=np.array([((d[54][0] - d[11][0]) + (d[17][0] - d[48][0])) / 2, d[14][1] - d[51][1]]),
                diag=abs((d[37] - d[20]) @ np.array([-u[1], u[0]])),
                tail=float(np.median(_dist(tail_o[len(tail_o) // 4: 3 * len(tail_o) // 4], tail_i))))


def amp_wide(gl, drawn, adv):
    """The stretched & `gl` (its points set its proportions) redrawn from its centre line and the strokes of
    `drawn` (the & at this weight, width 100). Same points. Returns the worst distance of a fitted run from
    its edge (units)."""
    s = [np.asarray(p, float) for p in gl.coordinates]; dd = [np.asarray(p, float) for p in drawn.coordinates]
    W = drawn_widths(drawn.coordinates); tb, tl, td, tt = W['bowl'], W['loop'], W['diag'], W['tail']
    # ---- the diagonal: X (the middle of the stretched crossing's four crotches), its upper edge through
    # the foot's outer corner (kept inside the cell)
    X = (s[7] + s[20] + s[38] + s[44]) / 4
    foot = np.array([min(s[29][0], adv - 4), 0.0])
    ang = math.atan2(-X[1], foot[0] - X[0])
    for _ in range(50):
        u = np.array([math.cos(ang), math.sin(ang)]); nB = np.array([-u[1], u[0]])
        ang += ((foot - X) @ nB - td / 2) / np.linalg.norm(foot - X)
    u = np.array([math.cos(ang), math.sin(ang)]); nB = np.array([-u[1], u[0]])   # u: down the diagonal
    upper, lower = _line(X + nB * td / 2, u), _line(X - nB * td / 2, u)
    # ---- the centre line: X, up the loop's left, its top, down its right, X, the bowl's left, its bottom,
    # into the diagonal where the drawn bowl meets it
    Bt = np.array([0.0, s[14][1] - tl[1] / 2]); Bb = np.array([s[0][0], s[0][1] + tb[1] / 2])
    lc = (s[11][0] + s[17][0]) / 2; lw = (s[17][0] - s[11][0]) / 2 * LOOP_W; Bt[0] = lc
    yl = (X[1] + Bt[1]) / 2; yb = (Bb[1] + X[1]) / 2
    Ll = np.array([lc - lw + tl[0] / 2, yl]); Lr = np.array([lc + lw - tl[0] / 2, yl])
    Bl = np.array([s[3][0] + tb[0] / 2, yb])
    phi = math.radians(PHI); uA = np.array([-math.cos(phi), -math.sin(phi)])
    J = X + u * (((dd[31][1] + dd[37][1]) / 2 - X[1]) / u[1])
    psi = math.radians(40); uJ = np.array([math.cos(psi), math.sin(psi)])
    up, dn, rt = np.array([0., 1.]), np.array([0., -1.]), np.array([1., 0.])
    Lj = np.linalg.norm(J - Bb); kj = min(0.45, 0.9 * (J[1] - Bb[1]) / max(Lj * math.sin(psi), 1e-9))
    pieces = [('diag', np.linspace(X + u * 900, X, 400)),
              ('loop', _gentle(X, -u, Ll, up)),
              ('loop', _quarter(Ll, up, Bt, rt, ROUND * (Bt[1] - Ll[1]), 9e3)),
              ('loop', _quarter(Bt, rt, Lr, dn, 9e3, ROUND * (Bt[1] - Lr[1]))),
              ('loop', _gentle(Lr, dn, X, uA)),
              ('bowl', _gentle(X, uA, Bl, dn)),
              ('bowl', _quarter(Bl, dn, Bb, rt, ROUND * (Bl[1] - Bb[1]), 9e3)),
              ('bowl', _cubic(Bb, Bb + rt * 0.45 * Lj, J - uJ * kj * Lj, J)),
              ('bowl', np.linspace(J, J + uJ * 300, 400))]
    S, kind, at = [], [], []                          # at: where each piece starts
    for name, P in pieces:
        P = P if not S else P[1:]
        at.append(sum(len(p) for p in S)); S.append(P); kind += [name] * len(P)
    at.append(sum(len(p) for p in S))
    S = np.vstack(S); n = _left(S); kind = np.array(kind)
    t = np.where(kind == 'diag', td, np.where(kind == 'loop', tl[0] * n[:, 0] ** 2 + tl[1] * n[:, 1] ** 2,
                                               tb[0] * n[:, 0] ** 2 + tb[1] * n[:, 1] ** 2))
    t = gaussian_filter1d(t, 60, mode='nearest')     # eased where one stroke runs into the next
    Le = S + n * t[:, None] / 2; Re = S - n * t[:, None] / 2   # the loop's outside is on the left
    def sec(P, a, b): return at[a], P[at[a]:at[b + 1]]
    def first(xs, key): return sorted(xs, key=key)[0]
    F = {}
    a0, seg = sec(Le, 3, 4); x = first(_crossings(seg, upper), lambda x: -x[0]); F[20] = (a0 + x[0], x[2])
    a1, seg1 = sec(Le, 0, 2); a5, seg5 = sec(Re, 4, 6)
    x = first(_crossings(seg1, seg5), lambda x: abs(a1 + x[0] - at[1])); F[7] = (a1 + x[0], x[2]); i7r = a5 + x[1]
    a1, seg1 = sec(Re, 1, 2); a4, seg4 = sec(Re, 3, 4)
    x = first(_crossings(seg1, seg4), lambda x: -x[1]); F[44] = (a1 + x[0], x[2]); i44r = a4 + x[1]
    a0, seg = sec(Le, 5, 6); x = first(_crossings(seg, lower), lambda x: x[0]); F[38] = (a0 + x[0], x[2])
    a0, seg = sec(Le, 7, 8); x = first(_crossings(seg, lower), lambda x: x[0]); F[37] = (a0 + x[0], x[2])
    a0, seg = sec(Re, 7, 8); x = first(_crossings(seg, lower), lambda x: x[0]); F[31] = (a0 + x[0], x[2])
    def ext(P, a, b, axis, sign):
        a0, seg = sec(P, a, b); k, p = _extreme(seg, axis, sign); return a0 + k, p
    F[0] = ext(Re, 6, 7, 1, -1); F[3] = ext(Re, 5, 6, 0, -1)
    F[11] = ext(Le, 1, 2, 0, -1); F[14] = ext(Le, 2, 3, 1, 1); F[17] = ext(Le, 3, 4, 0, 1)
    F[41] = ext(Le, 5, 6, 0, -1); F[34] = ext(Le, 6, 7, 1, -1)
    F[48] = ext(Re, 3, 4, 0, 1); F[51] = ext(Re, 2, 3, 1, 1); F[54] = ext(Re, 1, 2, 0, -1)
    # ---- the tail: from its root on the diagonal to the middle of the stretched cut, arriving as the drawn
    # tail arrives (upright); leaving the diagonal at the mirror of that about the chord, an even turn
    u_end = _unit(dd[25] - dd[26]); C = (s[24] + s[25]) / 2
    Tr = X + u * (((s[21] + s[28]) / 2 - X) @ u)
    ch = _unit(C - Tr); a_ = 2 * math.atan2(ch[1], ch[0]) - math.atan2(u_end[1], u_end[0])
    u_root = np.array([math.cos(a_), math.sin(a_)])
    T = np.vstack([np.linspace(Tr - u_root * 150, Tr, 100)[:-1], _gentle(Tr, u_root, C, u_end),
                   np.linspace(C, C + u_end * 150, 100)[1:]])
    tn = _left(T); TL = T + tn * tt / 2; TR = T - tn * tt / 2       # TL: the inner side
    x21 = first(_crossings(TL, upper), lambda x: -x[0]); x28 = first(_crossings(TR, upper), lambda x: -x[0])
    dcut, de = _unit(dd[24] - dd[25]), _unit(dd[26] - dd[25])         # the cut, at the drawn cut's angle
    ca = math.atan2(de[0] * dcut[1] - de[1] * dcut[0], de @ dcut); e = -u_end
    cut = _line(C, np.array([math.cos(ca) * e[0] - math.sin(ca) * e[1], math.sin(ca) * e[0] + math.cos(ca) * e[1]]))
    x24 = first(_crossings(TL, cut), lambda x: x[0]); x25 = first(_crossings(TR, cut), lambda x: x[0])
    # ---- the points: corners and extremes where the edges put them, then each run's handles fitted
    c = [None] * 58
    for p in (0, 3, 7, 11, 14, 17, 20, 31, 34, 37, 38, 41, 44, 48, 51, 54): c[p] = np.asarray(F[p][1], float)
    c[21], c[24], c[25], c[28] = x21[2], x24[2], x25[2], x28[2]
    c[29] = X + nB * td / 2 + u * ((0 - (X + nB * td / 2)[1]) / u[1])
    c[30] = X - nB * td / 2 + u * ((0 - (X - nB * td / 2)[1]) / u[1])
    worst = 0.0
    def run(idx, P, i, j, la=None, lb=None):
        nonlocal worst
        hs, mx = _fit_run(c[idx[0]], c[idx[-1]], len(idx) - 2, _between(P, i, j), la, lb)
        for q, h in zip(idx[1:-1], hs): c[q] = h
        worst = max(worst, mx)
    run([31, 32, 33, 0], Re, F[31][0], F[0][0], None, 'y')
    run([0, 1, 2, 3], Re, F[0][0], F[3][0], 'y', 'x')
    run([3, 4, 5, 6, 7], Re, F[3][0], i7r, 'x', None)
    run([7, 8, 9, 10, 11], Le, F[7][0], F[11][0], None, 'x')
    run([11, 12, 13, 14], Le, F[11][0], F[14][0], 'x', 'y')
    run([14, 15, 16, 17], Le, F[14][0], F[17][0], 'y', 'x')
    run([17, 18, 19, 20], Le, F[17][0], F[20][0], 'x', None)
    run([21, 22, 23, 24], TL, x21[0], x24[0])
    run([25, 26, 27, 28], TR, x25[0], x28[0])
    run([38, 39, 40, 41], Le, F[38][0], F[41][0], None, 'x')
    run([41, 42, 43, 34], Le, F[41][0], F[34][0], 'x', 'y')
    run([34, 35, 36, 37], Le, F[34][0], F[37][0], 'y', None)
    run([44, 45, 46, 47, 48], Re, i44r, F[48][0], None, 'x')
    run([48, 49, 50, 51], Re, F[48][0], F[51][0], 'x', 'y')
    run([51, 52, 53, 54], Re, F[51][0], F[54][0], 'y', 'x')
    run([54, 55, 56, 57, 44], Re, F[54][0], F[44][0], 'x', None)
    gl.coordinates = type(gl.coordinates)([(int(round(p[0])), int(round(p[1]))) for p in c])
    return round(worst, 1)
