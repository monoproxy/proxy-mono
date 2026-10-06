"""Google Fonts post-pass, run on every static weight and every VF master (az.py calls post() before saving).
Each step answers one fontbakery check-googlefonts warning. Every step is geometric, so it treats each master
the same way and the masters stay point-compatible.

- prune:       drop characters no Google Fonts subset serves (unreachable_subsetting)
- extra:       E/I/O breve and L middle dot, for Catalan, Czech, Welsh and others (shape_languages)
- carons:      d/t/L/l caron as base + vertical caron components (alt_caron)
- soft_dotted: i and j lose their dot under a following top mark, via ccmp (soft_dotted)
- metrics:     typo/hhea ascender clears the A grave (typoascender_exceeds_Agrave)
"""
import os
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

HERE = os.path.dirname(os.path.abspath(__file__))
UL_POS, UL_SIZE = -90, 60        # underline: top edge and thickness
ASC, DSC = 1040, -160          # line still 1200 units; 1040 clears the Black A grave (1033)

def served():
    return {int(l, 16) for l in open(os.path.join(HERE, 'gf_subsets.txt')) if l.strip() and not l.startswith('#')}

def contours(g):
    """[(points, flags)] of a simple glyph, one per contour."""
    out, s = [], 0
    for e in g.endPtsOfContours:
        out.append((list(g.coordinates[s:e + 1]), list(g.flags[s:e + 1]))); s = e + 1
    return out

def from_contours(cs):
    pen = TTGlyphPen(None)
    for pts, fl in cs:
        # TrueType contour back through the pen: on-curve points are lines, runs of off-curves are qCurves
        n = len(pts); start = next(i for i in range(n) if fl[i] & 1)
        seq = [(pts[(start + i) % n], fl[(start + i) % n] & 1) for i in range(n)] + [(pts[start], 1)]
        pen.moveTo(seq[0][0]); off = []
        for p, on in seq[1:]:
            if on:
                pen.qCurveTo(*off, p) if off else pen.lineTo(p); off = []
            else: off.append(p)
        pen.closePath()
    return pen.glyph()

def ybox(pts):
    ys = [p[1] for p in pts]; xs = [p[0] for p in pts]; return min(xs), min(ys), max(xs), max(ys)

def shifted(cs, dx, dy):
    return [([(x + dx, y + dy) for x, y in pts], fl) for pts, fl in cs]

def add_glyph(font, name, glyph, cp=None):
    glyf = font['glyf']
    if name not in glyf.glyphs:
        order = font.getGlyphOrder() + [name]; font.setGlyphOrder(order); glyf.glyphOrder = order
    glyf[name] = glyph; glyph.recalcBounds(glyf)
    font['hmtx'][name] = (700, glyph.xMin if glyph.numberOfContours else 0)
    if cp is not None:
        for t in font['cmap'].tables: t.cmap[cp] = name

def prune(font):
    import unicodedata
    # combining marks stay: the languages Google Fonts checks (Czech, Danish, Vietnamese...) need them
    # and so does all of GF Latin Core (its spacing breve, dot accent and ogonek are in no served subset)
    from fontTools import agl
    core = {ord(agl.toUnicode(l.strip())) for l in open(os.path.join(HERE, 'GF_Latin_Core.txt'))
            if l.strip() and not l.startswith('#') and len(agl.toUnicode(l.strip())) == 1}
    ok = served() | core | {0x20, 0xA0} | {c for c in font.getBestCmap() if unicodedata.category(chr(c)) == 'Mn'}
    cm = font.getBestCmap(); drop = {n for c, n in cm.items() if c not in ok}
    keep = {n for c, n in cm.items() if c in ok}
    drop -= keep
    for t in font['cmap'].tables:
        t.cmap = {c: n for c, n in t.cmap.items() if c in ok}
    order = [n for n in font.getGlyphOrder() if n not in drop]
    for n in drop:
        del font['glyf'].glyphs[n]; del font['hmtx'].metrics[n]
    font.setGlyphOrder(order); font['glyf'].glyphOrder = order

def stem_right(font, name, y):
    """x of the right edge of the leftmost ink run crossing height y."""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.basePen import BasePen
    from shapely.geometry import Polygon, LineString
    from shapely.ops import unary_union
    rings, cur = [], []
    class Flat(BasePen):
        def _moveTo(s_, p): cur.clear(); cur.append(p)
        def _lineTo(s_, p): cur.append(p)
        def _qCurveToOne(s_, p1, p2):
            p0 = cur[-1]
            for i in range(1, 9):
                u = i / 8; cur.append(((1-u)**2*p0[0] + 2*(1-u)*u*p1[0] + u*u*p2[0], (1-u)**2*p0[1] + 2*(1-u)*u*p1[1] + u*u*p2[1]))
        def _closePath(s_): rings.append(list(cur))
    gs = font.getGlyphSet(); gs[name].draw(Flat(gs))
    shape = None
    for r in rings:
        pg = Polygon(r).buffer(0); shape = pg if shape is None else shape.symmetric_difference(pg)
    cut = LineString([(-100, y), (900, y)]).intersection(shape)
    segs = [cut] if cut.geom_type == 'LineString' else list(cut.geoms)
    return min(segs, key=lambda g: g.bounds[0]).bounds[2]

def extra(font):
    glyf = font['glyf']
    def cs(n): return contours(glyf[n])
    def mark_of(n, ymin):           # the accent of a composed letter: its contours wholly above ymin
        return [c for c in cs(n) if ybox(c[0])[1] >= ymin]
    def centre(c): b = ybox([p for pts, _ in c for p in pts]); return (b[0] + b[2]) / 2
    for base, src, ymin, cp in (('E', 'uni0102', 800, 0x0114), ('I', 'uni0102', 800, 0x012C), ('O', 'uni0102', 800, 0x014E),
                                ('uni0065', 'uni0103', 600, 0x0115), ('uni0131', 'uni0103', 600, 0x012D), ('uni006F', 'uni0103', 600, 0x014F)):
        m = mark_of(src, ymin + 1); b = cs(base)
        add_glyph(font, 'uni%04X' % cp, from_contours(b + shifted(m, centre(b) - centre(m), 0)), cp)
    dot = cs('uni00B7')
    for base, cp, ymid in (('L', 0x013F, 400), ('uni006C', 0x0140, 330)):
        b = cs(base)
        # stem's right edge: rightmost outline point in the stem's band (above any bar or tail)
        xr = stem_right(font, base, ymid)
        xmax = max(p[0] for pts, _ in b for p in pts)
        db = ybox(dot[0][0]); d = (db[2] - db[0])
        if base == 'L':
            cx = xr + (min(xmax, 640) - xr) / 2
        else:
            # half a dot clear of the stem, but never past 690: the old 0.9-dot gap pushed the Black dot
            # out of the cell (suspicious_sidebearings)
            cx = xr + min(d * 0.5, 690 - xr - d) + d / 2
        add_glyph(font, 'uni%04X' % cp, from_contours(b + shifted(dot, cx - (db[0] + db[2]) / 2, ymid - (db[1] + db[3]) / 2)), cp)

def runs(font, name, y):
    """[(x0, x1)] ink runs crossing height y, left to right."""
    from fontTools.pens.basePen import BasePen
    from shapely.geometry import Polygon, LineString
    rings, cur = [], []
    class Flat(BasePen):
        def _moveTo(s_, p): cur.clear(); cur.append(p)
        def _lineTo(s_, p): cur.append(p)
        def _qCurveToOne(s_, p1, p2):
            p0 = cur[-1]
            for i in range(1, 9):
                u = i / 8; cur.append(((1-u)**2*p0[0] + 2*(1-u)*u*p1[0] + u*u*p2[0], (1-u)**2*p0[1] + 2*(1-u)*u*p1[1] + u*u*p2[1]))
        def _closePath(s_): rings.append(list(cur))
    gs = font.getGlyphSet(); gs[name].draw(Flat(gs))
    shape = None
    for r in rings:
        pg = Polygon(r).buffer(0); shape = pg if shape is None else shape.symmetric_difference(pg)
    cut = LineString([(-100, y), (900, y)]).intersection(shape)
    segs = [cut] if cut.geom_type == 'LineString' else list(getattr(cut, 'geoms', []))
    return sorted((g.bounds[0], g.bounds[2]) for g in segs if g.length > 0)

def auxiliary(font):
    """Auxiliary letters of the languages Google Fonts checks: Danish O slash acute, French/Pinyin U caron,
    Finnish H caron, Hawaiian okina, long s. Each from the font's own letters and accents."""
    glyf = font['glyf']
    def cs(n): return contours(glyf[n])
    def mark_of(n, ymin): return [c for c in cs(n) if ybox(c[0])[1] >= ymin]
    def centre(c): b = ybox([p for pts, _ in c for p in pts]); return (b[0] + b[2]) / 2
    for base, src, ymin, cp in (('uni00D8', 'uni00C1', 801, 0x01FE), ('uni00F8', 'uni00E1', 601, 0x01FF),
                                ('U', 'uni01CD', 801, 0x01D3), ('uni0075', 'uni01CE', 601, 0x01D4),
                                ('H', 'uni01CD', 801, 0x021E), ('uni0068', 'uni01CD', 801, 0x021F)):
        m = mark_of(src, ymin); b = cs(base)
        add_glyph(font, 'uni%04X' % cp, from_contours(b + shifted(m, centre(b) - centre(m), 0)), cp)
    add_glyph(font, 'uni02BB', from_contours(cs('uni2018')), 0x02BB)
    # modifier apostrophe: the closing quote. Geist builds it from the comma, lifted; composed as a letter
    # plus marks it lost the lift and sat on the baseline as a second comma
    add_glyph(font, 'uni02BC', from_contours(cs('uni2019')), 0x02BC)
    # long s: the f with its crossbar folded onto the stem (same points, so the masters stay compatible).
    # The crossbar is the f's own second contour, so only that contour is folded: finding it by height
    # caught the underside of the hook as well once the two came close (Bold up) and cut the arm to a wedge.
    (x0, x1), = runs(font, 'uni0066', 300)[:1]
    stem_c, bar = cs('uni0066')
    assert len(bar[0]) == 4 and len(stem_c[0]) > 4, 'f: stem and hook, then the crossbar'
    bar = ([(min(max(x, x0), x1), y) for x, y in bar[0]], bar[1])
    add_glyph(font, 'uni017F', from_contours([stem_c, bar]), 0x017F)
    ezh(font)

def ezh(font):
    """Ezh Ʒ ʒ Ǯ ǯ (Finnish/Skolt Sami, shape_languages). No upstream draws it, so it is the font's own 3
    with the upper bowl turned into a flat bar at the cap and a diagonal one stem thick down to the 3's
    middle: the same points, moved, so the masters stay compatible. ʒ is Ʒ dropped by the 200 between
    cap/x-height and baseline/descender; the carons come from Ǎ and ǎ."""
    import math
    glyf = font['glyf']
    (pts, fl), = contours(glyf['uni0033'])
    p = [list(x) for x in pts]
    s = runs(font, 'H', 200)[0]; s = s[1] - s[0]   # H stem, below the crossbar
    L, R, T = glyf['Z'].xMin, glyf['Z'].xMax, 800
    jx, jy = p[17]                                   # inner foot of the diagonal (the 3's middle, top left)
    vx, vy = R - jx, T - jy
    th = math.atan2(vy, vx) + math.asin(min(1, s / math.hypot(vx, vy)))   # edges s apart, perpendicular
    k = 1 / math.tan(th)
    rin = jx + (T - s - jy) * k                      # inner corner: diagonal meets the bar's underside
    def lerp(a, b, n, i): return [a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n]
    # inner edge 17 -> 25 along the diagonal, 25 -> 28 along the bar's underside
    for i in range(18, 26): p[i] = lerp([jx, jy], [rin, T - s], 8, i - 17)
    for i in range(26, 29): p[i] = lerp([rin, T - s], [L, T - s], 3, i - 25)
    # outer edge 28/29 up to the cap, 29 -> 36 along the bar's top, 36 -> 39 down the diagonal
    for i in range(29, 37): p[i] = lerp([L, T], [R, T], 7, i - 29)
    by = p[40][1]
    xo = R - (T - by) * k
    p[40][0] = max(p[40][0], xo)
    for i in range(37, 40): p[i] = lerp([R, T], [xo, by], 3, i - 36)
    cap = from_contours([([tuple(map(round, x)) for x in p], fl)])
    add_glyph(font, 'uni01B7', cap, 0x01B7)
    lc = contours(cap)
    add_glyph(font, 'uni0292', from_contours(shifted(lc, 0, -200)), 0x0292)
    glyf = font['glyf']
    def mark_of(n, ymin): return [c for c in contours(glyf[n]) if ybox(c[0])[1] >= ymin]
    def centre(c): b = ybox([q for pts, _ in c for q in pts]); return (b[0] + b[2]) / 2
    for base, src, ymin, cp in (('uni01B7', 'uni01CD', 801, 0x01EE), ('uni0292', 'uni01CE', 601, 0x01EF)):
        m = mark_of(src, ymin); b = contours(glyf[base])
        add_glyph(font, 'uni%04X' % cp, from_contours(b + shifted(m, centre(b) - centre(m), 0)), cp)

def carons(font):
    glyf = font['glyf']
    for cp, base, ymin in ((0x010F, 'uni0064', 300), (0x0165, 'uni0074', 300), (0x013D, 'L', 300), (0x013E, 'uni006C', 300)):
        n = 'uni%04X' % cp; c = contours(glyf[n])
        mark = [x for x in c if ybox(x[0])[1] >= ymin]; rest = [x for x in c if ybox(x[0])[1] < ymin]
        bname = n + '.base'         # always its own glyph: whether it equals the plain letter can differ per master
        add_glyph(font, bname, from_contours(rest))
        add_glyph(font, n + '.caron', from_contours(mark))
        pen = TTGlyphPen(glyf); pen.addComponent(bname, (1, 0, 0, 1, 0, 0)); pen.addComponent(n + '.caron', (1, 0, 0, 1, 0, 0))
        g = pen.glyph(); glyf[n] = g; g.recalcBounds(glyf); font['hmtx'][n] = (700, g.xMin)

TOP = list(range(0x0300, 0x0315)) + [0x031A] + list(range(0x033D, 0x0345))
BELOW = list(range(0x0316, 0x031A)) + list(range(0x031B, 0x0339)) + [0x0339, 0x033A, 0x033B, 0x033C]

def soft_dotted(font):
    glyf, cm = font['glyf'], font.getBestCmap()
    pairs = [('uni0069', 'uni0131'), ('uni006A', 'uni0237')]
    for n in ('uni012F', 'uni1ECB'):            # i ogonek, i dot below: drop the dot (topmost contour)
        if n in glyf.glyphs:
            c = contours(glyf[n]); top = max(c, key=lambda x: ybox(x[0])[1])
            add_glyph(font, n + '.dotless', from_contours([x for x in c if x is not top])); pairs.append((n, n + '.dotless'))
    top = ' '.join(cm[c] for c in TOP if c in cm); below = ' '.join(cm[c] for c in BELOW if c in cm)
    sd = ' '.join(a for a, _ in pairs); sdl = ' '.join(b for _, b in pairs)
    rules = [f'sub @SD\' @TOP by @SDL;']
    if below: rules += [f'sub @SD\' @BELOW @TOP by @SDL;', f'sub @SD\' @BELOW @BELOW @TOP by @SDL;']
    fea = f"""languagesystem DFLT dflt; languagesystem latn dflt;
@SD = [{sd}]; @SDL = [{sdl}]; @TOP = [{top}]; {'@BELOW = [' + below + '];' if below else ''}
feature ccmp {{ {' '.join(rules)} }} ccmp;
"""
    addOpenTypeFeaturesFromString(font, fea)

def metrics(font):
    os2, hh = font['OS/2'], font['hhea']
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ASC, DSC, 0
    hh.ascent, hh.descent, hh.lineGap = ASC, DSC, 0
    os2.fsSelection |= (1 << 7) | (1 << 8)   # USE_TYPO_METRICS, WWS (names are weight/width/slope only)
    # underline, strikeout and sub/superscript sizes: FontBuilder leaves them all 0, which draws no line.
    # One value for every weight (the variable font carries no MVAR). The underline sits inside the
    # descender (top -90, bottom -150); the strikeout is centred on the dashes (- – — sit at ~330, every weight).
    post = font['post']
    post.underlinePosition, post.underlineThickness = UL_POS, UL_SIZE
    os2.yStrikeoutSize, os2.yStrikeoutPosition = UL_SIZE, 330 + UL_SIZE // 2
    os2.ySubscriptXSize = os2.ySuperscriptXSize = 650
    os2.ySubscriptYSize = os2.ySuperscriptYSize = 600
    os2.ySubscriptXOffset = os2.ySuperscriptXOffset = 0
    os2.ySubscriptYOffset, os2.ySuperscriptYOffset = 75, 350

def windows_names(font):
    """Keep only the Windows name records: Google Fonts ships no Macintosh-platform names, and the
    variable font's two unique IDs (name 3) disagreed across the platforms."""
    font['name'].names = [n for n in font['name'].names if n.platformID == 3]

def separators(font):
    """Line and paragraph separators, empty and one cell wide (separator_glyphs)."""
    for cp in (0x2028, 0x2029):
        add_glyph(font, 'uni%04X' % cp, TTGlyphPen(None).glyph(), cp)

def merge(font, names=('uni221A', 'uni23CE')):
    """Union the overlapping straight-sided pieces Geist builds √ and ⏎ from (contour_count). Only glyphs
    with no curves, so the union is exact; vf.py checks the masters still match."""
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    glyf = font['glyf']
    for n in names:
        cs = contours(glyf[n])
        if not all(f & 1 for _, fl in cs for f in fl): continue
        u = unary_union([Polygon(pts).buffer(0) for pts, _ in cs]).simplify(0.5)
        out = []
        for poly in getattr(u, 'geoms', [u]):
            poly = orient(poly, -1)          # clockwise outer, counter-clockwise holes (TrueType)
            for ring in [poly.exterior] + list(poly.interiors):
                pts = [(round(x), round(y)) for x, y in list(ring.coords)[:-1]]
                out.append((pts, [1] * len(pts)))
        add_glyph(font, n, from_contours(out))

def quads(run):
    """Explicit quadratics (p0, p1, p2) of a run of points on, off..., on (implied on-curves filled in)."""
    out, p0 = [], run[0]
    for a, b in zip(run[1:-1], run[2:]):
        p2 = b if b is run[-1] else ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        out.append((p0, a, p2)); p0 = p2
    return out

def weld_partial(font, n='uni2202'):
    """Geist draws the ∂ as a bowl, its counter and a tail laid over the bowl (contour_count). The tail's
    outer edge already ends on a point of the bowl; its inner edge crosses the bowl's outline, so the two
    are joined there: bowl up to the crossing, then the tail from the crossing round to the shared point.
    The curves are split, not redrawn, so the shape is the same. The crossing moves from one curve segment
    to the next as the weight grows, so each side is always written as the same number of pieces (a piece
    is halved where there is one too few): the masters stay point-compatible."""
    from fontTools.misc.bezierTools import curveCurveIntersections, splitQuadraticAtT
    cs = contours(font['glyf'][n])
    if [len(p) for p, _ in cs] != [12, 18, 14] or cs[0][0][-1] != cs[1][0][14]: return
    (tail, _), (bowl, bfl), counter = cs
    T, B = quads(tail[0:6]), quads(bowl[8:15])     # the tail's inner edge; the bowl's right side, top to the shared point
    i, j, x = next((i, j, x) for i, a in enumerate(T) for j, b in enumerate(B) for x in curveCurveIntersections(a, b))
    up = B[:j] + [splitQuadraticAtT(*B[j], x.t2)[0]]            # bowl, down to the crossing
    while len(up) < 3: up[-1:] = splitQuadraticAtT(*up[-1], 0.5)
    on = [splitQuadraticAtT(*T[i], x.t1)[1]] + T[i + 1:]         # tail, from the crossing on
    while len(on) < 4: on[:1] = splitQuadraticAtT(*on[0], 0.5)
    assert len(up) == 3 and len(on) == 4, n
    mid = [(q, f) for seg in up + on for q, f in ((seg[1], 0), (seg[2], 1))]
    pts = bowl[:9] + [(round(q[0]), round(q[1])) for q, _ in mid] + tail[6:11] + bowl[14:]
    fl = bfl[:9] + [f for _, f in mid] + [1, 0, 0, 0, 0] + bfl[14:]
    add_glyph(font, n, from_contours([(pts, fl), counter]))

def fraction_slash(font, n='uni2044'):
    """Geist draws the fraction slash as the two ends of a bar, one under the numerator and one over the
    denominator of its precomposed fractions, set apart sideways; alone it reads as a broken slash. The
    standalone slash is the lower piece run on up to the cap line: the same stroke, at the same angle and
    thickness as the bar in the fractions, centred in the cell. One contour of four points in every master.
    The precomposed fractions are outlines of their own and keep the two pieces."""
    cs = contours(font['glyf'][n])
    if len(cs) != 2 or any(len(p) != 4 or not all(f & 1 for f in fl) for p, fl in cs): return
    low = min(cs, key=lambda c: ybox(c[0])[1])[0]
    top = max(y for c in cs for _, y in c[0])
    bot = sorted((p for p in low if p[1] == min(q[1] for q in low)))        # the foot, left then right
    up = sorted((p for p in low if p[1] == max(q[1] for q in low)))
    w = bot[1][0] - bot[0][0]; y0 = bot[0][1]
    run = (up[0][0] - bot[0][0]) / (up[0][1] - y0) * (top - y0)              # sideways travel, foot to cap
    xl = round(350 - (run + w) / 2)
    pts = [(xl, y0), (xl + round(run), top), (xl + round(run) + w, top), (xl + w, y0)]
    add_glyph(font, n, from_contours([(pts, [1, 1, 1, 1])]))

def mirrored(font):
    """Less-or-equal is greater-or-equal turned over left to right in the cell, and the four diagonal
    arrows are one arrow: north-west is north-east turned over left to right, and the two southern ones
    are those turned over top to bottom about the arrow's own middle. Geist draws them as mirror images,
    but only one of each was calibrated by its own stem, so the others came out up to a quarter lighter."""
    glyf = font['glyf']
    def flip(src, dst, upside_down=False):
        cs = contours(glyf[src]); b = ybox([p for pts, _ in cs for p in pts]); t = b[1] + b[3]
        add_glyph(font, dst, from_contours([([(x, t - y) if upside_down else (700 - x, y) for x, y in reversed(pts)],
                                             list(reversed(fl))) for pts, fl in cs]))
    flip('uni2265', 'uni2264'); flip('uni2197', 'uni2196')
    flip('uni2197', 'uni2198', True); flip('uni2196', 'uni2199', True)

def post(font):
    prune(font); extra(font); auxiliary(font); carons(font); soft_dotted(font); separators(font); merge(font)
    weld_partial(font); fraction_slash(font); mirrored(font)
    metrics(font); windows_names(font)
    font['maxp'].recalc(font)

def hmetrics3(path):
    """Write hmtx with three long metrics (hhea.numberOfHMetrics = 3, as the OpenType spec recommends for
    monospace fonts). fontTools always packs a monospace font down to 1, so this rewrites the raw table."""
    import struct
    from fontTools.ttLib import TTFont
    f = TTFont(path, recalcBBoxes=False, recalcTimestamp=False)
    order, m = f.getGlyphOrder(), f['hmtx'].metrics
    n = min(3, len(order))
    data = b''.join(struct.pack('>Hh', *m[g]) for g in order[:n]) + b''.join(struct.pack('>h', m[g][1]) for g in order[n:])
    f['hhea'].numberOfHMetrics = n
    from fontTools.ttLib.tables.DefaultTable import DefaultTable
    raw = DefaultTable('hmtx'); raw.data = data
    f.tables['hmtx'] = raw
    f.save(path)
