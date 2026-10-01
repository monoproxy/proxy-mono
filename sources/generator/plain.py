"""Plain (INKT 0) capitals rebuilt from full-weight strokes: no ink traps, no slit counters, every
stroke exactly one stem thick (measured perpendicular). Space Mono units: cap 700, advance 612.
Each builder takes the blended Space Mono trap glyph `src` (list of contours of (x, y, type)) for its
outer geometry and angles, and the target stem `s`."""
import math, os
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

C, ADV, CX = 700.0, 612.0, 306.0
FAR = 3000.0


def band(p0, p1, s, side):
    """Stroke of thickness s along the infinite line p0-p1, on `side` ('L' or 'R' of p0->p1)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = math.hypot(dx, dy); ux, uy = dx / n, dy / n
    nx, ny = (-uy, ux) if side == 'L' else (uy, -ux)
    a = (p0[0] - ux * FAR, p0[1] - uy * FAR); b = (p0[0] + ux * FAR, p0[1] + uy * FAR)
    return Polygon([a, b, (b[0] + nx * s, b[1] + ny * s), (a[0] + nx * s, a[1] + ny * s)])


def halfplane(p0, p1, side):
    return band(p0, p1, FAR, side)


def mirror(poly):
    return Polygon([(ADV - x, y) for x, y in poly.exterior.coords])


def solve(f, lo, hi, it=80):
    """Root of monotonic f on [lo, hi] by bisection."""
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (flo > 0): lo = mid
        else: hi = mid
    return (lo + hi) / 2


def contours(geom):
    geom = geom.buffer(0).simplify(0.05)
    polys = [geom] if geom.geom_type == 'Polygon' else list(geom.geoms)
    out = []
    for p in polys:
        p = orient(p, 1.0)   # exterior CCW, holes CW: PostScript direction like the UFO sources
        for ring in [p.exterior] + list(p.interiors):
            pts = list(ring.coords)[:-1]
            out.append([(x, y, 'line') for x, y in pts])
    return out


# ---------------------------------------------------------------- A and V

def _leg_top(xf, s, h, xt_src):
    """Top x of a leg whose outer edge runs from (xf, 0): as Space Mono's, unless the legs' inner edges
    would meet higher than C - h; then lean the legs further so the counter apex sits at C - h."""
    def apex(xt):
        th = math.atan2(xt - xf, C)
        return (CX - xf - s / math.cos(th)) / math.tan(th)
    if apex(xt_src) <= C - h:
        return xt_src
    return solve(lambda xt: apex(xt) - (C - h), xt_src, CX - 1)


def build_A(src, s):
    o, cn = src[0], src[1]
    xf, yb, ybt, xt = o[0][0], o[2][1], cn[0][1], o[7][0]
    h = ybt - yb                                   # apex joint = one crossbar thick
    xt = _leg_top(xf, s, h, xt)
    left = band((xf, 0), (xt, C), s, 'R')
    bar = box(0, yb, ADV, ybt)
    hull = Polygon([(xf, 0), (ADV - xf, 0), (ADV - xt, C), (xt, C)])
    return unary_union([left, mirror(left), bar]).intersection(hull).intersection(box(0, 0, ADV, C))


def build_V(src, s, h):
    o = src[0]
    xt, xb = o[7][0], o[0][0]                      # outer top-left, outer bottom-left
    # a V is an A upside down: flip, reuse the leg solver, flip back
    xb = _leg_top(xt, s, h, xb)
    left = band((xt, C), (xb, 0), s, 'L')
    hull = Polygon([(xt, C), (xb, 0), (ADV - xb, 0), (ADV - xt, C)])
    return unary_union([left, mirror(left)]).intersection(hull).intersection(box(0, 0, ADV, C))


# ---------------------------------------------------------------- X, Z, K

def build_X(src, s):
    """Space Mono's X is four half-arms meeting at a wide hub, not two straight strokes."""
    o = src[0]
    xl = o[0][0]; yh = (o[6][1] + o[7][1]) / 2
    ll = band((o[0][0], 0), o[15][:2], s, 'R').intersection(box(xl, 0, ADV, yh))   # outer edge (48,0)->(223,345)
    ul = band((o[13][0], C), o[14][:2], s, 'L').intersection(box(xl, yh, ADV, C))  # outer edge (48,700)->(223,357)
    return unary_union([ll, mirror(ll), ul, mirror(ul)]).intersection(box(xl, 0, ADV - xl, C))


def build_Z(src, s):
    o = src[0]
    xl, xr = o[0][0], o[1][0]
    bb, tb = o[2][1], o[8][1]                     # bottom bar top, top bar bottom
    xtl, xtr = o[7][0], o[6][0]
    e1a, e1b = o[4][:2], o[5][:2]                 # diagonal lower-right edge
    e2a, e2b = o[11][:2], o[10][:2]               # diagonal upper-left edge
    ma = ((e1a[0] + e2a[0]) / 2, (e1a[1] + e2a[1]) / 2); mb = ((e1b[0] + e2b[0]) / 2, (e1b[1] + e2b[1]) / 2)
    dx, dy = mb[0] - ma[0], mb[1] - ma[1]; n = math.hypot(dx, dy)
    off = (-dy / n * s / 2, dx / n * s / 2)
    diag = band((ma[0] - off[0], ma[1] - off[1]), (mb[0] - off[0], mb[1] - off[1]), s, 'L')
    diag = diag.intersection(box(xl, 0, xtr, C))
    return unary_union([box(xl, 0, xr, bb), box(xtl, tb, xtr, C), diag]).intersection(box(0, 0, ADV, C))


def build_K(src, s):
    o = src[0]
    xL = o[0][0]; xi = xL + s
    xmax = max(p[0] for p in o)
    arm = band(o[8][:2], o[9][:2], s, 'L')        # lower-right edge (279,356)->(569,694); stroke to its upper-left
    leg = band(o[6][:2], o[7][:2], s, 'L')        # upper-right edge (581,6)->(279,344); stroke to its lower-left
    # the leg springs from the arm's underside: keep it below the arm's upper edge
    th = math.atan2(o[9][1] - o[8][1], o[9][0] - o[8][0])
    ux, uy = -math.sin(th) * s, math.cos(th) * s
    up0 = (o[8][0] + ux, o[8][1] + uy); up1 = (o[9][0] + ux, o[9][1] + uy)
    leg = leg.intersection(halfplane(up0, up1, 'R'))
    stem = box(xL, 0, xi, C)
    return unary_union([stem, arm, leg]).intersection(box(xL, 0, xmax, C))


# ---------------------------------------------------------------- N, M, W

def build_N(src, s, sd=None):
    """Classic N: the diagonal runs from the left stem's inner top corner to the right stem's inner
    bottom corner, so both counters are clean triangles. 700 sin th - D cos th = sd (diagonal)."""
    sd = s if sd is None else sd
    o = src[0]
    xL, xR = o[0][0], o[5][0]
    xi, xo = xL + s, xR - s; D = xo - xi
    th = solve(lambda t: C * math.sin(t) - D * math.cos(t) - sd, 0.01, 1.5)
    a = D / math.tan(th)
    return Polygon([(xL, 0), (xi, 0), (xi, a), (xo, 0), (xR, 0), (xR, C), (xo, C), (xo, C - a), (xi, C), (xL, C)])


# M and W keep Space Mono's own shape (near-vertical strokes, V on the baseline, W's plateau at the
# cap). Plain only changes how counters end: in a clean point one crossbar (h) from the baseline or cap
# line, instead of Space Mono's slots. Every stroke is exactly s. Heavier than the cap (Danny chose B,
# 30 Sep 2026) they stop gaining weight: the cap is where the narrowest counter opening falls to
# MW_KAPPA * s.
MW_KAPPA = 0.5


def _hbar(t):
    return 78 + 48 * t                      # Space Mono A crossbar: 78 Regular, 126 Bold


def _t(s):
    return (s - 84) / 48


def m_parts(s, sa=None):
    """sa: arm thickness (default s). Stems are always s."""
    sa = s if sa is None else sa
    t = _t(s); h = _hbar(t)
    xL = max(46 - 24 * t, 12.0); xi = xL + s; D = CX - xi
    # arm: lower-left edge through (xi, C-h), upper-right edge through (CX, h), one arm-thickness apart
    f = lambda a: D * math.cos(a) - (C - 2 * h) * math.sin(a) - sa
    if f(0.0) <= 0:                         # no room: the arms would have to lean backwards
        return xL, xi, 0.0, h, -1e9
    th = solve(f, 0.0, 1.2)
    open_ = (C - h) * math.tan(th)          # side counter's base = half the V counter's top
    return xL, xi, th, h, open_


def w_parts(s):
    t = _t(s); h = _hbar(t)
    xo0, xo7 = 82 - 50 * t, 11 - 3 * t      # Space Mono W outer edge: foot and top x (Regular -> Bold)
    tho = math.atan2(xo0 - xo7, C); w = s / math.cos(tho)
    xv = xo0 - (xo0 - xo7) * h / C + w       # V counter's point, one crossbar above the baseline
    f = lambda a: (CX - xv) * math.cos(a) - (C - 2 * h) * math.sin(a) - s
    if f(0.0) <= 0:
        return xo0, xo7, w, xv, CX, xv, h, -1e9
    ph = solve(f, 0.0, 1.2)
    xf = CX - (C - h) * math.tan(ph)         # inner stroke's outer edge at the baseline (Lambda counter)
    xp = xv + (C - h) * math.tan(ph)         # inner stroke's V-side edge at the cap (plateau end)
    open_ = min(xp - (xo7 + w), 2 * (CX - xf))
    return xo0, xo7, w, xv, xf, xp, h, open_


def _cap(s, parts, idx):
    if parts(s)[idx] >= MW_KAPPA * s:
        return s
    return solve(lambda ss: parts(ss)[idx] - MW_KAPPA * ss, 60.0, s)


def m_arm_fit(s):
    """Heaviest arm (<= s) that keeps Space Mono's M shape with counters opening >= MW_KAPPA * arm."""
    if m_parts(s)[4] >= MW_KAPPA * s:
        return s
    return solve(lambda sa: m_parts(s, sa)[4] - MW_KAPPA * sa, 20.0, s)


# FULL (Danny, 30 Sep 2026: "keep it FULL but reduce the top gap", "to make the stem thicker"): every
# stroke is s at every weight. While it fits, Space Mono's shape (counters reach within one crossbar of
# the far edge). Heavier, the counters get shorter instead of the strokes thinner: the V notch comes
# down from the cap and the side notches come up from the baseline, symmetric about half-height, each
# opening MW_OPEN * s wide.
MW_OPEN = 0.25
MW_OPEN_ABS = MW_OPEN * 144 / (700 / 612)   # heavier than 600 the gaps stay this wide, so they keep
                                             # narrowing relative to the strokes (Danny: "keep reducing")
MW_OPEN_HEAVY = 0.6   # ...but from 700 up the M/W notches open to 0.6 x stem, faded in from 600, so full-weight
                      # M and W stop reading as solid blocks (Danny, 30 Sep 2026, after seeing them live)


def _heavy_target(s):
    u = min(max((s * (700 / 612) - 144) / (162 - 144), 0.0), 1.0)
    return float(os.environ.get('MW_OPEN_HEAVY', MW_OPEN_HEAVY)) * u * s


def m_xl(t):
    """M's outer edge. 'sm': Space Mono's (widens to 12 units from the cell edge when heavy).
    'match': the H's (73 -> 61, Regular -> Bold), so M's margins equal H/N's and the gaps even out.
    'mid': halfway between."""
    sm = max(46 - 24 * t, 12.0); hx = 73 - 12 * t
    mode = os.environ.get('M_SB', 'c2')
    if mode == 'c2':
        # Danny, 30 Sep 2026: Space Mono's wider M up to 600 (running text); halfway between that and the
        # H/N margins from 700 up, where the wordmark is set (its M|O gap is then evened by nudging the
        # wordmark's first O on the site, not in the font)
        u = min(max(((84 + 48 * t) * (700 / 612) - 144) / (162 - 144), 0.0), 1.0)
        return sm + ((sm + hx) / 2 - sm) * u
    if mode == 'c':
        # Danny, 30 Sep 2026 (option C): Space Mono's wider M up to 600, where running text is set and the
        # narrow M read dark; the H/N margins ('match', even gaps) from 700 up, where he approved it
        u = min(max(((84 + 48 * t) * (700 / 612) - 144) / (162 - 144), 0.0), 1.0)
        return sm + (hx - sm) * u
    return sm if mode == 'sm' else hx if mode == 'match' else (sm + hx) / 2


def m_full(s, sa=None):
    sa = s if sa is None else sa                   # arm thickness (stems stay s)
    t = _t(s); h = _hbar(t)
    xL = m_xl(t); xi = xL + s; D = CX - xi
    target = max(min(MW_OPEN * s, MW_OPEN_ABS), _heavy_target(s))
    f = lambda a: D * math.cos(a) - (C - 2 * h) * math.sin(a) - sa
    if f(0.0) > 0:
        th = solve(f, 0.0, 1.2)
        if (C - h) * math.tan(th) >= target:
            return xL, xi, th, C - h, h
    def gap(th):                                   # arm thickness fixes v - a; split it about C/2
        dl = (sa - D * math.cos(th)) / math.sin(th)
        return (C - dl) / 2 * math.tan(th) - target
    th = solve(gap, 0.01, 1.3)
    dl = (sa - D * math.cos(th)) / math.sin(th)
    return xL, xi, th, (C - dl) / 2, (C + dl) / 2


W_SLANT_T = (144 / (700 / 612) - 84) / 48      # hold the outer strokes' slant at its 600-weight value


def w_full(s, si=None):
    """Space Mono's W at full weight. Outer strokes keep their slant (held at the 600 value). Up to ~600
    the counters are Space Mono's (V counters to one crossbar above the baseline, the Lambda counter to
    one below the cap). Heavier, the counters shorten (V from the cap, Lambda from the baseline) and the
    gaps stay MW_OPEN_ABS wide. The approved 900 (Danny, 30 Sep 2026) is this construction. Around 700
    the four strokes fill the width exactly and neither form fits, so the outer strokes step in until the
    heavy form does."""
    t = _t(s)
    target = max(min(MW_OPEN * s, MW_OPEN_ABS), _heavy_target(s))
    h = _hbar(t)
    xo7_0 = 11 - 3 * t
    slant = 71 - 47 * min(t, W_SLANT_T)
    tho = math.atan2(slant, C); w = s / math.cos(tho)

    def parts(xo0, xo7, yv):                       # V counters end at yv, the Lambda counter at C - yv
        xv = xo0 - (xo0 - xo7) * yv / C + w
        f = lambda a: (CX - xv) * math.cos(a) - (C - 2 * yv) * math.sin(a) - (s if si is None else si)
        ph = None
        lean_steps = 21 if target <= MW_OPEN_ABS + 1e-6 else 40   # 12 deg by default; wider gaps may lean to ~23
        for k in range(lean_steps):                # steep solutions only (approved 800: 5.7 deg, 900: 8.3 deg)
            a0, a1 = k * 0.01, (k + 1) * 0.01
            if (f(a0) > 0) != (f(a1) > 0):
                ph = solve(f, a0, a1); break
        if ph is None:
            return None
        xf = CX - (C - yv) * math.tan(ph); xp = xv + (C - yv) * math.tan(ph)
        return xv, xf, xp, min(xp - (xo7 + w), 2 * (CX - xf))

    for step in range(0, 241):
        xo7 = xo7_0 + step * 0.5; xo0 = xo7 + slant
        p = parts(xo0, xo7, h)
        if p is not None and p[3] >= target:
            return xo0, xo7, w, p[0], p[1], p[2], h
        yv = C - 1
        while yv > h:
            q = parts(xo0, xo7, yv)
            if q is not None and q[3] >= target:
                if q[3] <= 1.5 * target:           # gaps near the target, not a jump wide open
                    return xo0, xo7, w, q[0], q[1], q[2], yv
                break                               # this outer position only jumps open: step in
            yv -= 0.25
    raise ValueError('no W fits at stem %.1f' % s)


def build_M(s, t, sa=None):
    mode = os.environ.get('M_HEAVY', 'full')
    if mode == 'full':
        xL, xi, th, a, v = m_full(s, sa)
    else:                                           # 'cap' / 'stems' (earlier options, kept for comparison)
        sa = m_arm_fit(s) if mode == 'stems' else None
        if mode == 'cap':
            s = _cap(s, m_parts, 4)
        xL, xi, th, h, _ = m_parts(s, sa); a, v = C - h, h
    tn = math.tan(th); x5 = xi + a * tn; xT = CX - (C - v) * tn
    return Polygon([(xL, 0), (xi, 0), (xi, a), (x5, 0), (ADV - x5, 0), (ADV - xi, a), (ADV - xi, 0),
                    (ADV - xL, 0), (ADV - xL, C), (ADV - xT, C), (CX, v), (xT, C), (xL, C)])


def build_W(s, t, si=None):
    if os.environ.get('M_HEAVY', 'full') == 'full':
        xo0, xo7, w, xv, xf, xp, yv = w_full(s, si)
    else:
        s = _cap(s, w_parts, 7)
        xo0, xo7, w, xv, xf, xp, yv, _ = w_parts(s)
    return Polygon([(xo0, 0), (xf, 0), (CX, C - yv), (ADV - xf, 0), (ADV - xo0, 0), (ADV - xo7, C),
                    (ADV - xo7 - w, C), (ADV - xv, yv), (ADV - xp, C), (xp, C), (xv, yv), (xo7 + w, C), (xo7, C)])


# Optical colour (Danny, 30 Sep 2026: "M and N look a bit darker at 300, 400"). With every stroke = s,
# N inked 1.20 x H and M/W 1.67 x H. Matching H exactly needed hairline diagonals (0.55-0.67 s), so the
# diagonals (never the stems) are DIAG x s instead: N ~1.14, M/W ~1.50 x H, in line with Space Mono's
# own N 1.25 / M 1.53 and Geist 400 1.16 / 1.38; 0.8 is Space Mono Bold's own M diagonal ratio (0.78).
# Full correction up to 600, fading out by 700 so the approved full-weight heavy M/W are unchanged.
DIAG = 0.9   # M and W only, 100-600, fading out by 700 (Danny chose option C, 30 Sep 2026; 0.8 was rejected)


def h_area(s, t):
    xl = 73 - 12 * t                                 # Space Mono H: stems at 73 (Regular) -> 61 (Bold)
    return 2 * s * C + (ADV - 2 * xl - 2 * s) * (_hbar(t) * 0.97)


def colour_fit(g, src, s, t):
    # M and W only (4 strokes in one cell read darker in running text); N keeps full diagonals
    diag = float(os.environ.get('MW_DIAG', DIAG)) if g in 'MW' else 1.0
    fade = min(max((s * (700 / 612) - 144) / (162 - 144), 0.0), 1.0)
    if fade >= 1.0 or diag >= 1.0:
        return None
    return (diag + (1 - diag) * fade) * s


def build(g, src, s, t, h):
    """h: apex/vertex joint height for A and V (Space Mono's crossbar thickness at this weight)."""
    if g == 'A': geom = build_A(src, s)
    elif g == 'V': geom = build_V(src, s, h)
    elif g == 'X': geom = build_X(src, s)
    elif g == 'Z': geom = build_Z(src, s)
    elif g == 'K': geom = build_K(src, s)
    elif g == 'N': geom = build_N(src, s, colour_fit('N', src, s, t))
    elif g == 'M': geom = build_M(s, t, colour_fit('M', src, s, t))
    elif g == 'W': geom = build_W(s, t, colour_fit('W', src, s, t))
    return contours(geom)
