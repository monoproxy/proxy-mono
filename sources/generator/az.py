"""A-Z capitals preview fonts. Usage: az.py <stem> <out.ttf> [plain]
Space Mono: A C E F H I L M N O S T U V W X Z   (G = Space Mono C + bar, Q = Space Mono O + Martian tail)
Martian Mono: B D J K P Q R   Geist Mono: Y"""
import sys, os, copy, math
sys.path.insert(0, os.path.dirname(__file__))
import quick900 as q
import plain as P
import ufoLib2
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.filterPen import FilterPen
from fontTools.pens.reverseContourPen import ReverseContourPen

QSEG = 4   # every cubic becomes exactly this many quadratics, at every weight

class FixedQuad(FilterPen):
    """Cubic -> a FIXED number of quadratics (split at equal t, each piece's control point from the
    standard midpoint approximation). Cu2QuPen picks the fewest segments per curve, so the same curve got
    different point counts at different weights and the nine masters could not interpolate; a fixed
    count keeps every weight point-compatible for the variable font."""
    def curveTo(self, *pts):
        if len(pts) != 3:
            return self._outPen.curveTo(*pts)
        p0 = self.current_pt; p1, p2, p3 = pts
        def at(u, a, b, c, d):
            v = 1 - u
            return tuple(v**3*a[i] + 3*v*v*u*b[i] + 3*v*u*u*c[i] + u**3*d[i] for i in (0, 1))
        def dat(u, a, b, c, d):
            v = 1 - u
            return tuple(3*v*v*(b[i]-a[i]) + 6*v*u*(c[i]-b[i]) + 3*u*u*(d[i]-c[i]) for i in (0, 1))
        for k in range(QSEG):
            u0, u1 = k / QSEG, (k + 1) / QSEG
            a, b = at(u0, p0, p1, p2, p3), at(u1, p0, p1, p2, p3)
            da, db = dat(u0, p0, p1, p2, p3), dat(u1, p0, p1, p2, p3)
            h = u1 - u0
            # control point: meet of the end tangents, falling back to the midpoint formula
            c1 = (a[0] + da[0] * h / 3, a[1] + da[1] * h / 3); c2 = (b[0] - db[0] * h / 3, b[1] - db[1] * h / 3)
            q = ((3 * (c1[0] + c2[0]) - (a[0] + b[0])) / 4, (3 * (c1[1] + c2[1]) - (a[1] + b[1])) / 4)
            self._outPen.qCurveTo(q, b)
        self.current_pt = p3
    def moveTo(self, p): self.current_pt = p; self._outPen.moveTo(p)
    def lineTo(self, p): self.current_pt = p; self._outPen.lineTo(p)
    def qCurveTo(self, *pts): self.current_pt = pts[-1]; self._outPen.qCurveTo(*pts)
from fontTools.fontBuilder import FontBuilder

SM = 'ACEFHILMNOSTUVWXZ'
MAR = 'BDJKPQR'
GEI = 'Y'
TMAX = {'M': 1.40, 'W': 1.40}

def plainW(C, master):
    c = [list(p) for p in C[0]]
    if master == 'B':          # close the top-centre slot and the two bottom slots
        for i, j in ((3, 2), (4, 5), (11, 10), (12, 13), (17, 16), (18, 19)):
            c[i][0], c[i][1] = c[j][0], c[j][1]
    return [[tuple(p) for p in c]]

N_APEX = 0.8 * 700     # Plain counters end in a point at 0.8 cap
N_SLOT = 60            # longest a trap slot may bite into the diagonal below the apex

def n_equal(c, PLAIN):
    """N with its diagonal exactly one stem thick (measured perpendicular), in Space Mono units.
    Counters end in a point at N_APEX; Inktrap cuts Space Mono's slit up from that point."""
    xL, xR, s = c[0][0], c[5][0], c[1][0] - c[0][0]
    yT, g = c[2][1], c[3][0] - c[2][0]
    a = N_APEX
    D, E = xR - xL - 2 * s, 700 - 2 * a
    th = math.acos(s / math.hypot(D, E)) - math.atan2(-E, D)   # D cos th + E sin th = s
    tn = math.tan(th)
    xi, xo = xL + s, xR - s
    pts = [(xL, 0), (xi, 0)]
    if PLAIN:
        pts += [(xi, a)] * 3
    else:
        g = min(g, tn * N_SLOT)
        pts += [(xi, yT), (xi + g, yT), (xi + g, a - g / tn)]
    pts += [(xi + a * tn, 0), (xR, 0), (xR, 700), (xo, 700)]
    if PLAIN:
        pts += [(xo, 700 - a)] * 3
    else:
        pts += [(xo, 700 - yT), (xo - g, 700 - yT), (xo - g, 700 - a + g / tn)]
    pts += [(xo - a * tn, 700), (xL, 700)]
    return [[(x, y, 'line') for x, y in pts]]

M_TH1, M_A1, M_XL_MIN = 24.0, 360.0, 12.0   # at 900: arm angle, side-counter apex, min sidebearing

def m_equal(c, s, t, PLAIN):
    """M with all four strokes exactly one stem thick. 400 keeps Space Mono's M (V on the baseline,
    counters ending at 0.8 cap); heavier weights open the arms and lift the V so full-weight strokes fit.
    c = Space Mono M blended at min(t, 1): source of the trap slit/slot sizes. Space Mono units."""
    cx = 306
    heavy = os.environ.get('M_HEAVY', 'full')   # trap-mode M; Danny: keep it FULL, 30 Sep 2026
    if s * q.SC > 162.5 and heavy == 'cap':          # M stops gaining weight at 700
        s = 162 / q.SC; t = (s - 84) / 48
    if s * q.SC > 162.5 and heavy == 'chevron':
        return m_chevron(s, max(46 - 24 * t, M_XL_MIN))
    xL = max(46 - 24 * t, M_XL_MIN)
    xi = xL + s; D = cx - xi
    u = min(max((s * q.SC - 110) / (197 - 110), 0), 1)
    # light end: a = 560, V counter apex one stem above the baseline -> solve the angle
    a0, v0 = 560.0, s
    th0 = math.acos(s / math.hypot(D, v0 - a0)) - math.atan2(a0 - v0, D)
    th = math.radians(math.degrees(th0) + u * (M_TH1 - math.degrees(th0)))
    a = a0 + u * (M_A1 - a0)
    tn, sn, cs = math.tan(th), math.sin(th), math.cos(th)
    v = a + (s - D * cs) / sn                      # V counter apex (inner vertex)
    x5 = xi + a * tn                                # arm's lower edge at the baseline
    if x5 >= cx:                                    # V lifted: arms' lower edges meet above the baseline
        yb = a - D / tn; x5, y5 = cx, yb
    else:
        y5 = 0.0
    xT = cx - (700 - v) * tn                        # arm's inner edge at the cap line
    if PLAIN:
        side = [(xi, a)] * 3
        vs = [(cx, v)] * 4
    else:
        # Space Mono's slits, sized relative to the new counters: side slit rises (yT - 560) above the
        # apex, the V slot drops (174 - yv) below the V apex (Space Mono Bold's plain flat is at 174)
        yT, g = a + (c[3][1] - 560), min(c[4][0] - c[3][0], tn * N_SLOT)
        side = [(xi, yT), (xi + g, yT), (xi + g, a - g / tn)]
        gv = min(c[14][0] - c[16][0], 2 * tn * N_SLOT); yv = v - min(max(174 - c[15][1], 60), 0.5 * (v - y5))
        vs = [(cx + gv / 2, v + gv / 2 / tn), (cx + gv / 2, yv), (cx - gv / 2, yv), (cx - gv / 2, v + gv / 2 / tn)]
    m = lambda p: (2 * cx - p[0], p[1])
    pts = [(xL, 0), (xi, 0)] + side + [(x5, y5), m((x5, y5))] + [m(p) for p in reversed(side)]
    pts += [m((xi, 0)), m((xL, 0)), m((xL, 700)), m((xT, 700))] + vs + [(xT, 700), (xL, 700)]
    return [[(x, y, 'line') for x, y in pts]]

def m_chevron(s, xL, k=0.35):
    """Heavy M (800-900): arms start at the stems' inner top corners and run at the angle that leaves
    k*s of each arm flanked by counters on both sides, so it reads as a stroke. All strokes = s."""
    cx = 306; xi = xL + s; D = cx - xi
    lo, hi = math.radians(1), math.radians(89)
    for _ in range(60):                                     # (D - s cos th) / sin th = k s
        mid = (lo + hi) / 2
        if (D - s * math.cos(mid)) / math.sin(mid) < k * s: lo = mid
        else: hi = mid
    th = (lo + hi) / 2; tn, sn, cs = math.tan(th), math.sin(th), math.cos(th)
    v = 700 - D / tn; a = v - (s - D * cs) / sn; yb = a - D / tn
    m = lambda p: (2 * cx - p[0], p[1])
    side = [(xi, a)] * 3
    pts = [(xL, 0), (xi, 0)] + side + [(cx, yb), (cx, yb)] + [m(p) for p in reversed(side)]
    pts += [m((xi, 0)), m((xL, 0)), m((xL, 700)), m((xi, 700))] + [(cx, v)] * 4 + [(xi, 700), (xL, 700)]
    return [[(x, y, 'line') for x, y in pts]]

def unify_dots(extra, s=None):
    """Every square dot is the period's dot (Danny, 30 Sep 2026: "the square has to be the same size"):
    . : ; ! ? i j. A dot = a small contour of few points within 0.5-1.8x the period's size. Dots that
    sit on the baseline stay on it; the rest keep their centre. Works on Geist-unit recordings."""
    def contours(ops):
        out, cur = [], []
        for op, pts in ops:
            cur.append((op, pts))
            if op in ('closePath', 'endPath'): out.append(cur); cur = []
        return out
    def bbox(c):
        xs = [p[0] for _, pts in c for p in pts]; ys = [p[1] for _, pts in c for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    per = contours(extra['uni002E'][1])
    px0, py0, px1, py1 = bbox(per[0]); dw, dh = px1 - px0, py1 - py0
    ow, oh = dw, dh                              # detection uses the period's own size
    if s: dw = dh = s                            # every dot is a stem-square (Danny, 1 Oct 2026)
    def stem_cx(ops):
        # centre of the vertical stem, measured across at y = 250 (i and j: the dot sits on the stem's axis)
        from shapely.geometry import Polygon as SP, LineString
        rings = []
        for c in contours(ops):
            pts = [p for _, ps in c for p in ps]
            if len(pts) > 12: rings.append(SP(pts).buffer(0))
        if not rings: return None
        cut = LineString([(-500, 250), (1500, 250)]).intersection(max(rings, key=lambda g: g.area))
        segs = [cut] if cut.geom_type == 'LineString' else list(cut.geoms)
        seg = max(segs, key=lambda g: g.length)
        return (seg.bounds[0] + seg.bounds[2]) / 2
    for cp in '.:;!?ij,\u00b7\u2026':
        name = 'uni%04X' % ord(cp)
        if extra[name][0] != 'rec': continue
        new = []
        for c in contours(extra[name][1]):
            x0, y0, x1, y1 = bbox(c); w, h = x1 - x0, y1 - y0
            npts = sum(len(pts) for _, pts in c)
            if npts <= 12 and 0.5 * ow <= w <= 1.8 * ow and 0.5 * oh <= h <= 1.8 * oh:
                cx = (x0 + x1) / 2
                if cp in 'ij' and s:
                    cx = stem_cx(extra[name][1]) or cx
                by = py0 if abs(y0 - py0) < 0.3 * oh else (y0 + y1) / 2 - dh / 2
                a, b = cx - dw / 2, cx + dw / 2
                c = [('moveTo', [(a, by)]), ('lineTo', [(a, by + dh)]), ('lineTo', [(b, by + dh)]),
                     ('lineTo', [(b, by)]), ('closePath', [])]          # clockwise: TrueType outer
            elif s and cp in ',;' and npts > 4:
                # the comma's head matched the old period; scale the comma about its foot on the
                # baseline so its head stays the same size as the (now stem-square) dot
                f = dw / ow; cxx = (x0 + x1) / 2
                c = [(op, [(cxx + (p[0] - cxx) * f, p[1] * f) for p in pts]) for op, pts in c]
            new.extend(c)
        extra[name] = ('rec', new)

CROTCH_GLYPHS = 'nmhru'
XH_G = 532   # x-height in Geist units (600 / (800/710))
CROTCH = 0.5   # how much of the notch where an arch leaves a stem (n m h r u...) is filled in

def shallow_crotch(ops, k=CROTCH):
    """Geist's arches leave the stem low, cutting a deep V notch between the stem's edge and the arch's
    outer curve (Danny, 1 Oct 2026: "reduce the v gap, keep the stem width"). The notch is the pattern
    lineTo(stem top) -> lineTo(A, straight down the stem's edge) -> lineTo(B, a step back onto the arch)
    -> curve. Lift A, B and the curve's first handle by k of the notch depth: the stem edge is only
    extended, never moved, so the stem keeps its width. Works the same upside down (u)."""
    ops = [(op, [tuple(p) for p in pts]) for op, pts in ops]
    for i in range(1, len(ops) - 2):
        (o0, p0), (o1, p1), (o2, p2), (o3, p3) = ops[i - 1], ops[i], ops[i + 1], ops[i + 2]
        if o1 != 'lineTo' or o2 != 'lineTo' or not p0 or o3 not in ('qCurveTo', 'curveTo'):
            continue
        top, a, b = p0[-1], p1[0], p2[0]
        # measured from the arch's height, not the stem's top: on h the stem runs on up to the ascender
        ref = min(top[1], XH_G) if top[1] > a[1] else top[1]
        depth = ref - a[1]
        if abs(top[0] - a[0]) > 60 or abs(depth) < 60 or abs(b[1] - a[1]) > 30 or abs(b[0] - a[0]) > 40:
            continue
        d = k * depth
        # the notch's stem edge slants into the stem (Geist cuts 12-60 units in at the join), so the
        # stem is thinner above the arch than below it. Put the edge back on the stem's true edge: the
        # nearest on-curve point below the join on the same side, within reach.
        j0 = max(q for q in range(i + 1) if ops[q][0] == 'moveTo')
        j1 = min(q for q in range(i, len(ops)) if ops[q][0] in ('closePath', 'endPath'))
        below = [pt for _, ps in ops[j0:j1] for pt in ps[-1:] if (pt[1] < a[1] - 40) == (depth > 0) and
                 abs(pt[1] - a[1]) > 40 and 0 <= (pt[0] - a[0]) * (1 if b[0] < a[0] else -1) < 90]
        dx = 0.0
        if below:
            edge = min(below, key=lambda pt: abs(pt[0] - a[0]))[0]
            dx = edge - a[0]
            ops[i - 1] = (o0, p0[:-1] + [(edge, top[1])])
        ops[i] = (o1, [(a[0] + dx, a[1] + d)])
        ops[i + 1] = (o2, [(b[0] + dx, b[1] + d)])
        # squash the arch's outer curve toward its far end instead of lifting one handle: the curve
        # keeps its shape (no kink) and simply starts higher up the stem
        end = p3[-1][1]; y0, y1 = b[1], b[1] + d
        f = (end - y1) / (end - y0) if end != y0 else 1
        ops[i + 2] = (o3, [(q[0], end - (end - q[1]) * f) for q in p3[:-1]] + [p3[-1]])
    return ops

ARCH_GLYPHS = ''   # arch redraw reverted (Danny, 1 Oct 2026: "looks weird, revert")

def even_counter(ops):
    """n/h arch, one stem thick all the way over (Danny, 1 Oct 2026: thick at the shoulders, thin at
    the top, "make them more even"). The outer and inner curves become two concentric half-ellipses,
    the outer one exactly one stem bigger in both radii, centred on the counter. The outer keeps its
    overshoot height; the inner top drops to one stem below it. On the left the outer curve starts
    where its ellipse meets the stem (the crotch), which also sets how deep the notch is."""
    import math
    t = math.tan(math.pi / 8)
    ops = [(op, [tuple(p) for p in pts]) for op, pts in ops]
    for i in range(6, len(ops) - 2):
        (o0, p0), (o1, p1), (o2, p2) = ops[i], ops[i + 1], ops[i + 2]
        if o0 != 'lineTo' or o1 != 'qCurveTo' or o2 != 'qCurveTo':
            continue
        R, top, L = p0[0], p1[-1], p2[-1]
        if top[1] < R[1] + 80 or abs(L[1] - R[1]) > 15 or L[0] > R[0] - 100:
            continue
        kinds = [ops[i - k][0] for k in (6, 5, 4, 3, 2, 1)]
        if kinds != ['lineTo', 'lineTo', 'qCurveTo', 'qCurveTo', 'lineTo', 'lineTo']:
            break
        A, B = ops[i - 6][1][0], ops[i - 5][1][0]
        oR = ops[i - 3][1][-1][0]
        Tout = max(q[1] for q in ops[i - 4][1] + ops[i - 3][1])
        sw = oR - R[0]                                   # the right stem, i.e. the stem
        ys = R[1]; xc = (R[0] + L[0]) / 2
        rxi = (R[0] - L[0]) / 2; rxo = rxi + sw
        ryo = Tout - ys; ryi = ryo - sw; Tin = ys + ryi
        # outer, left: from the crotch on the ellipse up to the top, one quad on the tangents
        u = min(max((xc - B[0]) / rxo, -1), 1); th = math.acos(u)
        By = ys + ryo * math.sin(th)
        lam = (Tout - By) / (ryo * math.cos(th)) if math.cos(th) > 1e-6 else 0
        cx = B[0] + lam * rxo * math.sin(th)
        step = B[1] - A[1]
        ops[i - 6] = ('lineTo', [(A[0], By - step)])
        ops[i - 5] = ('lineTo', [(B[0], By)])
        ops[i - 4] = ('qCurveTo', [(min(cx, xc), Tout), (xc, Tout)])
        ops[i - 3] = ('qCurveTo', [(xc + rxo * t, Tout), (oR, ys + ryo * t), (oR, ys)])
        ops[i + 1] = ('qCurveTo', [(R[0], ys + ryi * t), (xc + rxi * t, Tin), (xc, Tin)])
        ops[i + 2] = ('qCurveTo', [(xc - rxi * t, Tin), (L[0], ys + ryi * t), (L[0], ys)])
        break
    return ops

def embolden(ops, d):
    """Offset a recorded TrueType outline outward by up to d on every side (thickens every stroke by
    2d), backing off until no counter closes. Returns rings, TrueType-oriented (outer clockwise)."""
    from shapely.geometry import Polygon as SP
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    from fontTools.pens.basePen import BasePen
    rings, cur = [], []
    class Flat(BasePen):
        def _moveTo(s_, p): cur.clear(); cur.append(p)
        def _lineTo(s_, p): cur.append(p)
        def _qCurveToOne(s_, p1, p2):
            p0 = cur[-1]
            for i in range(1, 9):
                u = i / 8; cur.append(((1-u)**2*p0[0] + 2*(1-u)*u*p1[0] + u*u*p2[0], (1-u)**2*p0[1] + 2*(1-u)*u*p1[1] + u*u*p2[1]))
        def _closePath(s_): rings.append(list(cur))
        _endPath = _closePath
    fp = Flat(None)
    for op, pts in ops: getattr(fp, op)(*pts)
    outer, inner = [], []
    for r in rings:
        if len(r) < 3: continue
        a2 = sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))
        (outer if a2 < 0 else inner).append(SP(r).buffer(0))
    geom = unary_union(outer)
    if inner: geom = geom.difference(unary_union(inner))
    def holes(g):
        ps = [g] if g.geom_type == 'Polygon' else list(g.geoms)
        return sum(len(p.interiors) for p in ps), len(ps)
    h0 = holes(geom)
    lo, hi = 0.0, d
    for _ in range(25):
        if holes(geom.buffer(hi, join_style=2, mitre_limit=2.0)) == h0: lo = hi; break
        mid = (lo + hi) / 2
        if holes(geom.buffer(mid, join_style=2, mitre_limit=2.0)) == h0: lo = mid
        else: hi = mid
    g = geom.buffer(lo, join_style=2, mitre_limit=2.0).simplify(0.3)
    out = []
    for p in ([g] if g.geom_type == 'Polygon' else list(g.geoms)):
        p = orient(p, -1.0)
        for ring in [p.exterior] + list(p.interiors):
            out.append(list(ring.coords)[:-1])
    return out

def k_symmetric(c, stem, cap=800):
    """Martian's K = stem rectangle (0-3) + a '<' contour (4-9): (499,0) (218,387) (517,800) (649,800)
    (353,392) (638,0) at 400. Its arm is taller than its leg, so the upper counter starts higher and
    opens wider than the lower one (Danny, 30 Sep 2026). Rebuild the '<' symmetric about cap/2: the
    arm keeps Martian's top-right corner and slope, is one stem thick, and the leg mirrors it."""
    c = [list(p) for p in c]
    slope = (c[6][0] - c[5][0]) / (c[6][1] - c[5][1])        # dx/dy of the arm
    x7 = c[7][0]
    x6 = x7 - stem * math.sqrt(1 + slope * slope)             # horizontal width for a one-stem stroke
    mid = cap / 2
    c[4] = [x6, 0]; c[5] = [x6 - slope * mid, mid]; c[6] = [x6, cap]
    c[7] = [x7, cap]; c[8] = [x7 - slope * mid, mid]; c[9] = [x7, 0]
    return [tuple(p) for p in c]

def plain_martian(g, c):
    """Remove Martian Mono's traps without redrawing the letter (indices are the variable font's)."""
    c = [list(p) for p in c]
    if g == 'B':   # waist: the 16-unit vertical step becomes one point; depth and curves unchanged
        m = [(c[8][0] + c[9][0]) / 2, (c[8][1] + c[9][1]) / 2]; c[8] = list(m); c[9] = list(m)
    if g == 'G':   # the bowl's end runs onto the spur's edge instead of stepping across to it
        dx = c[30][0] - c[31][0]
        c[31] = [c[30][0], c[30][1]]; c[32][0] += 0.5 * dx
    if g == 'Q':   # lift the whole tail (same thickness) until its top edge meets the bowl: no step
        p0, p1 = c[6], c[17]; p2 = [(c[17][0] + c[16][0]) / 2, (c[17][1] + c[16][1]) / 2]
        x3 = c[3][0]; lo, hi = 0.0, 1.0
        for _ in range(60):
            m = (lo + hi) / 2; xm = (1 - m) ** 2 * p0[0] + 2 * (1 - m) * m * p1[0] + m * m * p2[0]
            lo, hi = (m, hi) if xm < x3 else (lo, m)
        yb = (1 - m) ** 2 * p0[1] + 2 * (1 - m) * m * p1[1] + m * m * p2[1]
        dy = max(yb + 2 - c[3][1], 0)
        for i in (0, 3, 4, 5):
            c[i][1] += dy
    return [tuple(p) for p in c]

G_NOTCH_600 = 0.092   # the V's height / stem at 600 (measured); held as the minimum from 600 to 900

def g_split(c):
    """Split the C's outer bottom-right cubic where it reaches the stem's left edge (x_in)."""
    x_in = c[5][0]
    P0, P1, P2, P3 = [p[:2] for p in c[0:4]]
    bez = lambda u, a, b, cc, d: (1-u)**3*a + 3*(1-u)**2*u*b + 3*(1-u)*u*u*cc + u**3*d
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        if bez(m, P0[0], P1[0], P2[0], P3[0]) < x_in: lo = m
        else: hi = m
    u = (lo + hi) / 2
    L = lambda a, b: (a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]))
    B = L(P0, P1); M1 = L(P1, P2); D2 = L(P2, P3); Cc = L(B, M1); E = L(M1, D2); S = L(Cc, E)
    return B, Cc, S

def g_from_c(C, t, notch=None):
    """G = the C exactly (bowl, curves, even stroke) + the bar + a vertical stem on the right from the bar
    down to the baseline (Danny, 30 Sep 2026: "keep the shape but add the vertical stem"; this version is
    the one he approved for 100-600). The bowl's bottom curve is split where it meets the stem's left
    edge; below that the stem's edge runs on down to the baseline, leaving an inverted V between bowl and
    stem. From ~700 up that meeting point drops under the baseline and the V closes, so there the curve
    is lifted to meet the stem at `notch` (a fraction of the stem, held from 600) and the V stays open
    ("even though technically not correct", Danny). Bar from Space Mono's G: bottom 258 -> 228,
    top 336 -> 354, left end 239 -> 260."""
    c = C[0]
    bb, bt, xbl = 258 - 30 * t, 336 + 18 * t, 239 + 21 * t
    x_out, x_in = c[4][0], c[5][0]
    s = x_out - x_in
    B, Cc, S = g_split(c)
    if notch is not None and S[1] < notch * s:
        lift = notch * s - S[1]
        Cc = (Cc[0], Cc[1] + lift); S = (S[0], S[1] + lift)
    inner = (x_in, min(c[6][1], bb), 'line')   # the inner curve starts at the bar's underside
    foot = [(x_in, 0, 'line'), (x_out, 0, 'line')] if S[1] > 0 else [(x_out, S[1], 'line')]
    g = [c[0], (B[0], B[1], None), (Cc[0], Cc[1], None), (x_in, S[1], 'curve')] + foot + [
         (x_out, bt, 'line'), (xbl, bt, 'line'), (xbl, bb, 'line'), (x_in, bb, 'line'), inner] + c[7:]
    return [g]

def q_tail(gl, src, O, stem, PLAIN):
    """Martian's Q tail, re-hung under Space Mono's O. Returns the tail polygon in final units, drawn
    as TrueType outer contours. Plain: the tail is one stem thick and its top edge starts inside the
    O's bottom stroke, so there is no step at the join. Clockwise, like Martian's own tail."""
    from shapely.geometry import Polygon as SP, LineString
    from fontTools.pens.basePen import BasePen
    c, e, _ = gl.getCoordinates(src['glyf'])
    tail = [tuple(c[i]) for i in range(e[0] + 1)]          # contour 0: (310,-171) (310,10) (390,10) (390,-32) (637,-66) (637,-220)
    ring = []
    class Flat(BasePen):
        def _moveTo(s_, p): ring.append(p)
        def _lineTo(s_, p): ring.append(p)
        def _curveToOne(s_, p1, p2, p3):
            p0 = ring[-1]
            for i in range(1, 13):
                u = i / 12; v = 1 - u
                ring.append((v**3*p0[0] + 3*v*v*u*p1[0] + 3*v*u*u*p2[0] + u**3*p3[0], v**3*p0[1] + 3*v*v*u*p1[1] + 3*v*u*u*p2[1] + u**3*p3[1]))
        def _qCurveToOne(s_, p1, p2):
            p0 = ring[-1]
            for i in range(1, 13):
                u = i / 12; ring.append(((1-u)**2*p0[0] + 2*(1-u)*u*p1[0] + u*u*p2[0], (1-u)**2*p0[1] + 2*(1-u)*u*p1[1] + u*u*p2[1]))
        def _closePath(s_): pass
    q.draw_ufo_contours([O[0]], Flat(None), q.SC)           # outer contour of the O
    Opoly = SP(ring)
    def obottom(x):
        seg = LineString([(x, -500), (x, 1500)]).intersection(Opoly)
        return seg.bounds[1]
    (x0, y0), (x5, y5) = tail[0], tail[5]
    xn = tail[2][0]
    if not PLAIN:
        dy = obottom(xn) + 0.3 * stem - tail[1][1]           # keep Martian's tail, nub reaching into the O
        return [(x, y + (dy if i in (1, 2) else 0)) for i, (x, y) in enumerate(tail)]
    k = (y5 - y0) / (x5 - x0)
    lift = stem * math.sqrt(1 + k * k)                       # vertical thickness for a one-stem stroke
    yb = lambda x: y0 + k * (x - x0)
    top = lambda x: yb(x) + lift
    nub = max(obottom(x0), obottom(xn)) + 0.45 * stem        # inside the O's bottom stroke
    pts = [(x0, yb(x0)), (x0, max(nub, top(x0))), (xn, max(nub, top(xn))), (xn, top(xn)), (x5, top(x5)), (x5, yb(x5))]
    return pts

OPTICAL = 0.25   # 0 = centre the ink's bounding box; 1 = centre its mass. A quarter toward the mass.

def center_glyphs(glyf, order, adv=700):
    """Place every glyph in its 700 cell: optical centre on 350, and hmtx lsb = xMin (it was 0, which
    made renderers push every glyph flush left). Centring uses only the ink above the baseline, so
    tails (Q, g, j, y, p, q) hang naturally; glyphs mostly below the baseline use all their ink."""
    from shapely.geometry import Polygon as SP, box as sbox
    from shapely.ops import unary_union
    from fontTools.pens.basePen import BasePen
    metrics = {}
    for name in order:
        g = glyf[name]
        if g.numberOfContours == 0:
            metrics[name] = (adv, 0); continue
        rings, cur = [], []
        class Flat(BasePen):
            def _moveTo(s_, p): cur.clear(); cur.append(p)
            def _lineTo(s_, p): cur.append(p)
            def _qCurveToOne(s_, p1, p2):
                p0 = cur[-1]
                for i in range(1, 9):
                    u = i / 8; cur.append(((1-u)**2*p0[0] + 2*(1-u)*u*p1[0] + u*u*p2[0], (1-u)**2*p0[1] + 2*(1-u)*u*p1[1] + u*u*p2[1]))
            def _closePath(s_): rings.append(list(cur))
            _endPath = _closePath
        g.draw(Flat(None), glyf)
        outer, inner = [], []
        for r in rings:
            if len(r) < 3: continue
            area2 = sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))
            (outer if area2 < 0 else inner).append(SP(r).buffer(0))   # TrueType: outer contours clockwise
        geom = unary_union(outer)
        if inner: geom = geom.difference(unary_union(inner))
        above = geom.intersection(sbox(-3000, 0, 4000, 3000))
        ref = above if above.area > 0.3 * geom.area else geom
        x0, _, x1, _ = ref.bounds; bc = (x0 + x1) / 2
        oc = bc + OPTICAL * (ref.centroid.x - bc)
        dx = round(adv / 2 - oc)
        g.coordinates.translate((dx, 0)); g.recalcBounds(glyf)
        metrics[name] = (adv, g.xMin)
    return metrics

# GF Latin Core (googlefonts/glyphsets): the minimum Google Fonts onboards. Names without an AGL codepoint.
CORE_EXTRA = [0x00AB, 0x00BB, 0x0302, 0x0304, 0x0306, 0x0307, 0x0308, 0x030A, 0x030B, 0x030C, 0x0326,
              0x0327, 0x0328, 0x0131, 0x0237, 0x1E9E]
# glyphs geist_stems.json has not measured: calibrate them by a relative's stem
CAL_AS = {0x0131: ord('i'), 0x0237: ord('j'), 0x00E6: ord('e'), 0x0153: ord('e'), 0x00F0: ord('o'),
          0x00FE: ord('p'), 0x00DF: ord('h'), 0x00C6: ord('E'), 0x0152: ord('E'), 0x00DE: ord('P'),
          0x1E9E: ord('B'), 0x0111: ord('d'), 0x0127: ord('h'), 0x010F: ord('d'), 0x013E: ord('l'),
          0x0165: ord('t'), 0x00F8: ord('o')}

def core_codepoints():
    from fontTools import agl
    names = [l.strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GF_Latin_Core.txt'))
             if l.strip() and not l.startswith('#')]
    cps = {ord(agl.toUnicode(n)) for n in names if len(agl.toUnicode(n)) == 1}
    # beyond Core: everything Geist Mono draws except Cyrillic and the cell-filling box/block/quadrant
    # characters (drawn for Geist's 600 cell, they would not join up in ours), so the language checks
    # (Romanian T-comma, Dutch ij, Latvian, Lithuanian...) and the Plus symbols pass too
    import unicodedata
    gei = TTFont(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'upstream', 'GeistMono.ttf'))
    skip = ('CYRILLIC', 'BOX', 'QUADRANT', 'UPPER HALF', 'LOWER', 'FULL BLOCK', 'LEFT HALF', 'RIGHT HALF',
            'LIGHT SHADE', 'MEDIUM SHADE', 'DARK SHADE', 'LEFT ONE', 'RIGHT ONE', 'UPPER ONE', 'LOWER ONE')
    for c in gei.getBestCmap():
        nm = unicodedata.name(chr(c), '')
        if c > 0x7E and nm and not nm.startswith(skip) and not 0x2580 <= c <= 0x259F: cps.add(c)
    return sorted(cps | set(CORE_EXTRA))

def core_plan(gei, have):
    """Split the missing GF Latin Core characters: Geist composites whose base we already draw are
    rebuilt from OUR base + Geist's mark (so an accented Space Mono / Martian capital keeps its letter);
    everything else (symbols, marks, ae, oe, eth, thorn, germandbls, dotless i/j, d/l/t caron...) is taken
    from Geist's outline and calibrated like the other Geist glyphs."""
    gcm = gei.getBestCmap(); rev = {v: k for k, v in gcm.items()}; G = gei['glyf']
    out, comp = [], []
    import unicodedata
    def is_mark(name):
        c = rev.get(name)
        return c is None or unicodedata.category(chr(c)) in ('Mn', 'Sk', 'Lm')
    todo = [c for c in core_codepoints() if c not in have and c in gcm]
    base_ok = have | set(todo)
    for c in todo:
        g = G[gcm[c]]
        if c not in (0x00AB, 0x00BB) and g.isComposite() and rev.get(g.components[0].glyphName) in base_ok and not G[g.components[0].glyphName].isComposite() \
                and all(is_mark(k.glyphName) for k in g.components[1:]):
            comp.append(c)
        else:
            out.append(c)
    # bases that are themselves composed must be outlines first (e.g. i -> dotlessi is an outline anyway)
    return out, comp

def compose_core(fb, order, metrics, cmap, comp, llo, lhi, kl, gsc):
    """Accented letters: our centred base glyph + Geist's mark(s). A mark keeps Geist's height and sits
    at the same fraction across the base's ink as it does over Geist's own base."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
    from fontTools.pens.boundsPen import BoundsPen
    gcm = llo.getBestCmap(); rev = {v: k for k, v in gcm.items()}
    glo, ghi = llo.getGlyphSet(), lhi.getGlyphSet()
    off = (700 - 600 * gsc) / 2
    def rec(name):
        a, b = DecomposingRecordingPen(glo), DecomposingRecordingPen(ghi)
        glo[name].draw(a); ghi[name].draw(b)
        return [(op, [((p[0] + kl * (q_[0] - p[0])) * gsc + off, (p[1] + kl * (q_[1] - p[1])) * gsc) for p, q_ in zip(pa, pb)])
                for (op, pa), (_, pb) in zip(a.value, b.value)]
    def bbox(ops):
        xs = [p[0] for _, pts in ops for p in pts]; ys = [p[1] for _, pts in ops for p in pts]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None
    glyf = fb.font['glyf']
    ttg = {n: glyf[n] for n in order}
    new = []
    for c in comp:
        gname = gcm[c]
        clo, chi = llo['glyf'][gname].components, lhi['glyf'][gname].components
        base = cmap[rev[clo[0].glyphName]]
        bo = glyf[base]; bo.recalcBounds(glyf)
        gb = bbox(rec(clo[0].glyphName)); gx0, gx1 = gb[0], gb[2]
        bx0, bx1 = (bo.xMin, bo.xMax) if bo.numberOfContours else (350, 350)
        pen = TTGlyphPen(None)
        bo.draw(pen, glyf)
        for kl_, kh in zip(clo[1:], chi[1:]):
            ox = (kl_.x + kl * (kh.x - kl_.x)) * gsc; oy = (kl_.y + kl * (kh.y - kl_.y)) * gsc
            ops = [(op, [(p[0] + ox, p[1] + oy) for p in pts]) for op, pts in rec(kl_.glyphName)]
            mb = bbox(ops)
            if mb is None: continue
            mc = (mb[0] + mb[2]) / 2
            f = (mc - gx0) / (gx1 - gx0) if gx1 > gx0 else 0.5
            dx = bx0 + f * (bx1 - bx0) - mc
            tp = TransformPen(pen, (1, 0, 0, 1, dx, 0))
            for op, pts in ops: getattr(tp, op)(*pts)
        name = 'uni%04X' % c
        g = pen.glyph(); g.recalcBounds(glyf)
        ttg[name] = g; metrics[name] = (700, g.xMin if g.numberOfContours else 0); cmap[c] = name; new.append(name)
    fb2 = FontBuilder(1000, isTTF=True); fb2.setupGlyphOrder(order + new)
    fb2.setupCharacterMap(cmap); fb2.setupGlyf(ttg); fb2.setupHorizontalMetrics(metrics)
    return fb2

WIN = (1228, 297)
REPO_URL = 'https://github.com/monoproxy/proxy-mono'

def gf_fixes(font):
    """Font Bakery (check-googlefonts) table fixes: drawn .notdef, win metrics that clear every glyph,
    code pages, monospace PANOSE, installable fsType, unhinted-font gasp + smart-dropout prep, meta."""
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables import ttProgram
    glyf = font['glyf']
    pen = TTGlyphPen(None)                                    # .notdef: a hollow box on the cell
    for (x0, y0, x1, y1), cw in (((80, 0, 620, 800), True), ((150, 70, 550, 730), False)):
        pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
        if not cw: pts.reverse()
        pen.moveTo(pts[0]); [pen.lineTo(p) for p in pts[1:]]; pen.closePath()
    glyf['.notdef'] = pen.glyph(); font['hmtx']['.notdef'] = (700, 80)
    for n in font.getGlyphOrder(): glyf[n].recalcBounds(glyf)
    ymax = max((glyf[n].yMax for n in font.getGlyphOrder() if glyf[n].numberOfContours), default=1000)
    ymin = min((glyf[n].yMin for n in font.getGlyphOrder() if glyf[n].numberOfContours), default=-200)
    os2 = font['OS/2']
    os2.usWinAscent = max(ymax, WIN[0]); os2.usWinDescent = max(-ymin, WIN[1])   # family-wide: the Black's bounds
    os2.fsType = 0
    os2.panose.bFamilyType = 2; os2.panose.bProportion = 9
    os2.recalcCodePageRanges(font); os2.recalcUnicodeRanges(font)
    gasp = newTable('gasp'); gasp.version = 1; gasp.gaspRange = {0xFFFF: 0x000F}; font['gasp'] = gasp
    prep = newTable('prep'); prep.program = ttProgram.Program()
    prep.program.fromAssembly(['PUSHW[ ]', '511', 'SCANCTRL[ ]', 'PUSHB[ ]', '4', 'SCANTYPE[ ]'])
    font['prep'] = prep
    meta = newTable('meta'); meta.data = {'dlng': 'Latn', 'slng': 'Latn'}; font['meta'] = meta

def build(stem, out, PLAIN):
    q.PLAIN = PLAIN
    R = ufoLib2.Font.open('../upstream/SpaceMono-Regular.ufo'); B = ufoLib2.Font.open('../upstream/SpaceMono-Bold.ufo')
    def hstem(u):
        c = q.pts(u, 'H')[0]; xs = sorted(set(round(p[0]) for p in c)); return xs[1] - xs[0]
    hR, hB = hstem(R), hstem(B)
    t = (stem / q.SC - hR) / (hB - hR)
    tB = (197 / q.SC - hR) / (hB - hR)
    NB = [(33, 0), (205, 0), (205, 630), (223, 630), (256, 0), (579, 0), (579, 700), (407, 700), (407, 70), (389, 70), (356, 700), (33, 700)]
    NBP = [(33, 0), (205, 0), (205, 540), (205, 540), (256, 0), (579, 0), (579, 700), (407, 700), (407, 160), (407, 160), (356, 700), (33, 700)]
    glyphs = {}
    Asrc = q.blend(q.fix('A', q.pts(R, 'A')), q.fixB('A', q.pts(B, 'A')), t)
    hbar = Asrc[1][0][1] - Asrc[0][2][1]              # crossbar thickness at this weight
    for g in SM:
        if PLAIN and g in 'AMNVWXZ':
            tg = min(t, 1.0) if g == 'K' else t      # K: extrapolating past Bold distorts the arm/leg angles
            src = q.blend(q.fix(g, q.pts(R, g)), q.fixB(g, q.pts(B, g)), tg) if g not in 'MW' else None
            if g == 'M' and os.environ.get('M_HEAVY') == 'chevron' and stem > 162.5:
                glyphs[g] = ('sm', m_chevron(stem / q.SC, max(46 - 24 * t, M_XL_MIN)))
            else:
                glyphs[g] = ('sm', P.build(g, src, stem / q.SC, t, hbar))
            continue
        a, b = q.fix(g, q.pts(R, g)), q.fixB(g, q.pts(B, g))
        if PLAIN:
            if g in 'MN':
                a, b = q.plain(g, a, 'R'), q.plain(g, b, 'B')
            elif g == 'W':
                a, b = plainW(a, 'R'), plainW(b, 'B')
        if g == 'M':
            ta, tb = q.fix(g, q.pts(R, g)), q.fixB(g, q.pts(B, g))
            glyphs[g] = ('sm', m_equal(q.blend(ta, tb, min(t, 1))[0], stem / q.SC, t, PLAIN))
            continue
        if g == 'N':
            # geometry from Space Mono's trap N (outer edges, stem, slit height/width), then rebuilt
            ta, tb = q.fix(g, q.pts(R, g)), q.fixB(g, q.pts(B, g))
            src = q.blend(tb, [[(x, y, 'line') for x, y in NB]], (t - 1) / (tB - 1)) if t > 1 else q.blend(ta, tb, t)
            glyphs[g] = ('sm', n_equal(src[0], PLAIN))
        else:
            glyphs[g] = ('sm', q.blend(a, b, min(t, TMAX.get(g, 99))))
        if g == 'S':   # the lower terminal never sticks out past the top bowl's left edge (Danny, 30 Sep)
            # Move the whole tail in, both edges together, so it keeps its thickness (clipping only the
            # outer edge left a hairline end at the light weights). Points (fixed S, 46): 38-44 are the
            # tail from the inner bottom curve's handles to the outer edge's lower handle; 45 goes half.
            c = [list(p) for p in glyphs[g][1][0]]
            xmin = min(p[0] for p in c if p[1] > 350)
            d = xmin - c[42][0]
            if d > 0:
                for i in range(38, 45): c[i][0] += d
                c[45][0] += d / 2
            glyphs[g] = ('sm', [[tuple(p) for p in c]])
    mar = TTFont('../upstream/martian.woff2')
    i400 = instantiateVariableFont(copy.deepcopy(mar), {'wght': 400})
    i800 = instantiateVariableFont(copy.deepcopy(mar), {'wght': 800})
    def pstem(f):
        gn = mar.getBestCmap()[ord('P')]
        c, _, _ = f['glyf'][gn].getCoordinates(f['glyf']); xs = sorted(p[0] for p in c if abs(p[1]) < 1); return xs[-1] - xs[0]
    # below 400 interpolate toward Martian's real Thin master instead of extrapolating 400 -> 800
    mlo, mhi = (instantiateVariableFont(copy.deepcopy(mar), {'wght': 100}), i400) if stem < pstem(i400) else (i400, i800)
    k = (stem - pstem(mlo)) / (pstem(mhi) - pstem(mlo))
    for g in MAR:
        gn = mar.getBestCmap()[ord(g)]
        c4, _, _ = mlo['glyf'][gn].getCoordinates(mlo['glyf']); c8, _, _ = mhi['glyf'][gn].getCoordinates(mhi['glyf'])
        gl = copy.deepcopy(i400['glyf'][gn]); gl.coordinates = type(gl.coordinates)([(x + k * (x2 - x), y + k * (y2 - y)) for (x, y), (x2, y2) in zip(c4, c8)])
        if g == 'K':   # arm and leg as mirror images about half cap height, both one stem thick
            gl.coordinates = type(gl.coordinates)(k_symmetric([tuple(p) for p in gl.coordinates], stem))
        if PLAIN and g in 'BGQ':
            gl.coordinates = type(gl.coordinates)(plain_martian(g, [tuple(p) for p in gl.coordinates]))
        glyphs[g] = ('tt', gl, i400)
    gei = TTFont('../upstream/GeistMono.ttf'); gsc = 800 / 710
    g4 = instantiateVariableFont(copy.deepcopy(gei), {'wght': 400}); g9 = instantiateVariableFont(copy.deepcopy(gei), {'wght': 900})
    def ystem(f):
        c, _, _ = f['glyf']['Y'].getCoordinates(f['glyf']); xs = sorted(p[0] for p in c if abs(p[1]) < 1); return (xs[-1] - xs[0]) * gsc
    g1 = instantiateVariableFont(copy.deepcopy(gei), {'wght': 100})
    ylo, yhi = (g1, g4) if stem < ystem(g4) else (g4, g9)      # Geist's real Thin master below 400
    kg = (stem - ystem(ylo)) / (ystem(yhi) - ystem(ylo))
    c4, _, _ = ylo['glyf']['Y'].getCoordinates(ylo['glyf']); c9, _, _ = yhi['glyf']['Y'].getCoordinates(yhi['glyf'])
    gy = copy.deepcopy(g4['glyf']['Y']); gy.coordinates = type(gy.coordinates)([(x + kg * (x2 - x), y + kg * (y2 - y)) for (x, y), (x2, y2) in zip(c4, c9)])
    glyphs['Y'] = ('geist', gy, g4)
    glyphs['G'] = ('sm', g_from_c(glyphs['C'][1], t, G_NOTCH_600))
    glyphs['Q'] = ('q', glyphs['O'][1], q_tail(glyphs['Q'][1], glyphs['Q'][2], glyphs['O'][1], stem, PLAIN))
    # lowercase, figures, punctuation (all printable ASCII beyond A-Z): Geist Mono, the plain reference
    # (round g j y, no square-hook descenders), calibrated so its n stem equals the target stem; zero is
    # Martian's slashed zero. Geist has no ink traps, so Plain and Inktrap share these.
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    gcm = gei.getBestCmap()
    def nstem(f):                                  # width of the n's left stem, measured across at y=250
        from shapely.geometry import Polygon as SP, LineString
        from fontTools.pens.basePen import BasePen
        rings, cur = [], []
        class Flat(BasePen):
            def _moveTo(s_, p): cur.clear(); cur.append(p)
            def _lineTo(s_, p): cur.append(p)
            def _qCurveToOne(s_, p1, p2):
                p0 = cur[-1]
                for i in range(1, 9):
                    u = i / 8; cur.append(((1-u)**2*p0[0] + 2*(1-u)*u*p1[0] + u*u*p2[0], (1-u)**2*p0[1] + 2*(1-u)*u*p1[1] + u*u*p2[1]))
            def _closePath(s_): rings.append(list(cur))
        f.getGlyphSet()[gcm[ord('n')]].draw(Flat(f.getGlyphSet()))
        cut = LineString([(-100, 250), (1000, 250)]).intersection(SP(rings[0]).buffer(0))
        segs = [cut] if cut.geom_type == 'LineString' else list(cut.geoms)
        return min(segs, key=lambda g: g.bounds[0]).length * gsc
    llo, lhi = (g1, g4) if stem < nstem(g4) else (g4, g9)
    kl = (stem - nstem(llo)) / (nstem(lhi) - nstem(llo))
    gs4, gs9 = llo.getGlyphSet(), lhi.getGlyphSet()
    extra = {}
    # every Geist glyph is calibrated by its OWN stem (geist_stems.json, measured at Geist's 100/400/900
    # masters), not the n's: figures ran ~1.06x, punctuation 0.5-0.9x, m v w x y ~0.9x (Danny, 30 Sep
    # 2026). Extrapolation is held to [-0.3, 1.5] of the master pair; a glyph Geist draws too light to
    # get there (e.g. @, %) is thickened by offsetting its outline, as far as its counters survive.
    import json
    GS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geist_stems.json')))
    mlo_w, mhi_w = ('100', '400') if llo is g1 else ('400', '900')
    target_g = stem / gsc
    # beyond ASCII: what monoproxy.com.au sets. Curly quotes, the superscript 2 and the bullet stay on the
    # n-based calibration with the comma family; the middle dot and ellipsis use the period's square.
    SITE_EXTRA = [0x2014, 0x2013, 0x2192, 0x2197, 0x2191, 0x2193, 0x2190, 0x00D7, 0x00B0, 0x2248, 0x2265,
                  0x2260, 0x2212, 0x2500, 0x2039, 0x203A, 0x201C, 0x201D, 0x2018, 0x2019, 0x00B2, 0x25CF,
                  0x00B7, 0x2026]
    N_BASED = {ord('.'), ord(':'), ord(','), ord(';'), ord('$'), ord('z'), 0x201C, 0x201D, 0x2018, 0x2019,
               0x00B2, 0x25CF, 0x00B7, 0x2026}
    core_out, core_comp = core_plan(gei, set(range(32, 127)) | set(SITE_EXTRA))
    for cp in list(range(33, 65)) + list(range(91, 127)) + SITE_EXTRA + core_out:
        name = 'uni%04X' % cp
        if cp == ord('0'):
            gn = mar.getBestCmap()[cp]
            z4, _, _ = mlo['glyf'][gn].getCoordinates(mlo['glyf']); z8, _, _ = mhi['glyf'][gn].getCoordinates(mhi['glyf'])
            gz = copy.deepcopy(i400['glyf'][gn]); gz.coordinates = type(gz.coordinates)([(x + k * (x2 - x), y + k * (y2 - y)) for (x, y), (x2, y2) in zip(z4, z8)])
            extra[name] = ('tt', gz, i400); continue
        r4, r9 = DecomposingRecordingPen(gs4), DecomposingRecordingPen(gs9)
        if str(cp) not in GS[mlo_w] and cp in CAL_AS: cp_cal = CAL_AS[cp]
        else: cp_cal = cp
        gs4[gcm[cp]].draw(r4); gs9[gcm[cp]].draw(r9)
        kg, short = kl, 0.0
        wlo, whi = GS[mlo_w].get(str(cp_cal)), GS[mhi_w].get(str(cp_cal))
        # dots keep their size; $ is measured by its thin bar (would bloat the S) and z by its bars (its
        # diagonal is too steep to measure, would bloat the diagonal): both were already on the n's stem
        # the dot family . : , ; stays on one calibration so the comma's head = the period's dot (Danny,
        # 30 Sep 2026: the ; mixed a colon dot with a thickened comma and looked wrong)
        if cp not in N_BASED and wlo and whi and whi - wlo > 1:
            kg = min(max((target_g - wlo) / (whi - wlo), -0.3), 1.5)
            short = target_g - (wlo + kg * (whi - wlo))
        ops = [(op, [(a[0] + kg * (b[0] - a[0]), a[1] + kg * (b[1] - a[1])) for a, b in zip(pa, pb)]) for (op, pa), (_, pb) in zip(r4.value, r9.value)]
        if chr(cp) in CROTCH_GLYPHS:
            ops = shallow_crotch(ops)
        if chr(cp) in ARCH_GLYPHS:
            ops = even_counter(ops)
        if short > 0.03 * target_g and not os.environ.get('VF'):   # VF: offsetting changes topology per weight
            extra[name] = ('poly', embolden(ops, short / 2))
        else:
            extra[name] = ('rec', ops)
    # IJ / ij: Space Mono's own drawings (Dutch, shape_languages), blended like the Space Mono capitals
    # The IJ keeps Space Mono's square-ended gap in the left stem: it is what tells IJ from U (Danny,
    # 2 Oct 2026). The ij dots are stem-squares on each stem's axis, like every other dot.
    extra['uni0132'] = ('sm', q.blend(q.pts(R, 'IJ'), q.pts(B, 'IJ'), t))
    ij = q.blend(q.pts(R, 'ij'), q.pts(B, 'ij'), t)
    body = ij[0]; s = stem / q.SC
    dots = []
    for (xa, xb), dot in zip(((body[15][0], body[14][0]), (body[5][0], body[4][0])), ij[1:]):
        cx = (xa + xb) / 2; cy = sum(p[1] for p in dot) / len(dot)
        a, b, lo, hi = cx - s / 2, cx + s / 2, cy - s / 2, cy + s / 2
        dots.append([(a, lo, 'line'), (b, lo, 'line'), (b, hi, 'line'), (a, hi, 'line')])
    extra['uni0133'] = ('sm', [body] + dots)
    unify_dots(extra, stem / gsc)
    glyphs.update(extra)
    order = ['.notdef', 'space'] + [chr(c) for c in range(65, 91)] + sorted(extra)
    fb = FontBuilder(1000, isTTF=True); fb.setupGlyphOrder(order)
    fb.setupCharacterMap({32: 'space', 0xA0: 'space', **{c: chr(c) for c in range(65, 91)}, **{int(n[3:], 16): n for n in extra}})
    ttg = {}
    for gname in order:
        pen = TTGlyphPen(None)
        if gname in ('.notdef', 'space'): ttg[gname] = pen.glyph(); continue
        kind = glyphs[gname][0]
        if kind == 'sm':
            q.draw_ufo_contours(glyphs[gname][1], ReverseContourPen(FixedQuad(pen)), q.SC)
        elif kind == 'path':
            # pathops output: make outer contours clockwise (TrueType) whatever skia's winding choice
            from fontTools.pens.areaPen import AreaPen
            ap = AreaPen(); glyphs[gname][1].draw(ap)
            tgt = TransformPen(FixedQuad(pen), (q.SC, 0, 0, q.SC, 0, 0))
            glyphs[gname][1].draw(ReverseContourPen(tgt) if ap.value > 0 else tgt)
        elif kind == 'q':
            q.draw_ufo_contours(glyphs[gname][1], ReverseContourPen(FixedQuad(pen)), q.SC)
            tail = glyphs[gname][2]
            pen.moveTo(tail[0])
            for pt in tail[1:]: pen.lineTo(pt)
            pen.closePath()
        elif kind == 'tt':
            glyphs[gname][1].draw(pen, glyphs[gname][2]['glyf'])
        elif kind in ('poly', 'multi'):
            tp = TransformPen(pen, (gsc, 0, 0, gsc, (700 - 600 * gsc) / 2, 0))
            for pk, pdata in (glyphs[gname][1] if kind == 'multi' else [('poly', glyphs[gname][1])]):
                if pk == 'poly':
                    for ring in pdata:
                        tp.moveTo(ring[0])
                        for pt in ring[1:]: tp.lineTo(pt)
                        tp.closePath()
                else:
                    for op, pts in pdata: getattr(tp, op)(*pts)
        elif kind == 'rec':
            tp = TransformPen(pen, (gsc, 0, 0, gsc, (700 - 600 * gsc) / 2, 0))
            for op, pts in glyphs[gname][1]:
                getattr(tp, op)(*pts)
        else:
            glyphs[gname][1].draw(TransformPen(pen, (gsc, 0, 0, gsc, (700 - 600 * gsc) / 2, 0)), glyphs[gname][2]['glyf'])
        ttg[gname] = pen.glyph()
    fb.setupGlyf(ttg); metrics = center_glyphs(fb.font['glyf'], order)
    cmap = {32: 'space', 0xA0: 'space', **{c: chr(c) for c in range(65, 91)}, **{int(n[3:], 16): n for n in extra}}
    fb = compose_core(fb, order, metrics, cmap, core_comp, llo, lhi, kl, gsc)
    wcls = {46: 100, 68: 200, 96: 300, 110: 400, 126: 500, 144: 600, 162: 700, 180: 800, 197: 900}.get(round(stem), 400)
    style = {100: 'Thin', 200: 'ExtraLight', 300: 'Light', 400: 'Regular', 500: 'Medium', 600: 'SemiBold',
             700: 'Bold', 800: 'ExtraBold', 900: 'Black'}[wcls]
    fam = 'Proxy Mono'
    fb.setupHorizontalHeader(ascent=1000, descent=-200, lineGap=0)
    fb.setupNameTable({
        # Google Fonts wants exactly this form; the upstream notices (Space Mono, Martian Mono, Geist Mono)
        # live in OFL.txt and AUTHORS.txt
        'copyright': f'Copyright 2026 The Proxy Mono Project Authors ({REPO_URL})',
        'familyName': fam if wcls in (400, 700) else f'{fam} {style}',
        'styleName': 'Bold' if wcls == 700 else 'Regular',
        **({} if wcls in (400, 700) else {'typographicFamily': fam, 'typographicSubfamily': style}),
        'uniqueFontIdentifier': f'1.000;MNPX;ProxyMono-{style}', 'fullName': f'{fam} {style}',
        'designer': 'monoproxy', 'designerURL': 'https://www.monoproxy.com.au', 'manufacturer': 'monoproxy',
        'vendorURL': 'https://www.monoproxy.com.au',
        'version': 'Version 1.000', 'psName': f'ProxyMono-{style}',
        'licenseDescription': 'This Font Software is licensed under the SIL Open Font License, Version 1.1. '
                              'This license is available with a FAQ at: https://openfontlicense.org',
        'licenseInfoURL': 'https://openfontlicense.org'})
    sel = (1 << 7) | ((1 << 5) if wcls == 700 else (1 << 6))   # non-RIBBI weights are 'Regular' of their own family
    fb.setupOS2(version=4, usWeightClass=wcls, achVendID='MNPX', fsSelection=sel, sTypoAscender=1000, sTypoDescender=-200,
                sTypoLineGap=0, usWinAscent=1090, usWinDescent=250, sxHeight=600, sCapHeight=800)
    fb.setupPost(isFixedPitch=1)
    fb.font['head'].macStyle = 1 if wcls == 700 else 0
    gf_fixes(fb.font)
    import gf_post; gf_post.post(fb.font)
    fb.save(out)
    if not os.environ.get('VF'): gf_post.hmetrics3(out)
    if out.endswith('.ttf'):
        w2 = TTFont(out); w2.flavor = 'woff2'; w2.save(out[:-4] + '.woff2')

if __name__ == '__main__':
    build(float(sys.argv[1]), sys.argv[2], len(sys.argv) > 3 and sys.argv[3] == 'plain')
