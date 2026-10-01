"""Quick static preview: MONOPROXY at a target stem (default 900 = design stem 197).
Space Mono glyphs: linear inter/extrapolation of the Regular/Bold source masters (compat-fixed),
scaled 700/612. Martian P R: extrapolated from its own 400/800 instances. Geist Y: its own instance."""
import sys, io, copy
import ufoLib2
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import RecordingPen, DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.fontBuilder import FontBuilder

SC = 700 / 612
PLAIN = False
def pts(ufo, g):
    return [[(p.x, p.y, p.type) for p in c.points] for c in ufo[g].contours]

def fix(g, R):
    """Insert duplicate points so Regular matches Bold's structure (M, W, S)."""
    c = R[0]
    if g == 'M':
        s = c[:]  # 16 pts
        return [[s[0], s[1], (124, 495, 'line'), s[2], s[3], s[4], s[5], s[6], s[7], (488, 495, 'line'),
                 s[8], s[9], s[10], s[11], s[12], s[12], s[13], s[13], s[14], s[15]]]
    if g == 'W':
        s = c[:]
        return [[s[0], s[1], s[2], s[2], s[3], s[3], s[4], s[5], s[6], s[7], s[8], s[8], s[9], s[9],
                 s[10], s[11], s[12], s[12], s[13], s[13], s[14], s[15]]]
    return R

def fixB(g, B):
    if g == 'S':   # Bold lacks two short straight segments present in Regular
        c = B[0][:]
        i = [k for k, p in enumerate(c) if (round(p[0]), round(p[1])) == (194, 514)][0]
        c.insert(i + 1, (194, 514, 'line'))
        j = [k for k, p in enumerate(c) if (round(p[0]), round(p[1])) == (436, 198)][0]
        c.insert(j + 1, (436, 198, 'line'))
        return [c]
    return B


def plain(g, C, master):
    """Close Space Mono's built-in traps (INKT 0): counter-top slits and the M's V slot."""
    if g not in ('M', 'N'):
        return C
    c = [list(p) for p in C[0]]
    def put(i, xy): c[i][0], c[i][1] = xy
    if g == 'M':
        if master == 'R':      # fixed Regular (20 pts): counter apexes down to the stem at 495
            for i in (3, 4): put(i, c[2][:2])
            for i in (7, 8): put(i, c[9][:2])
        else:                  # Bold: slits collapse onto their base; V slot closes to a flat at 174
            for i in (3, 4): put(i, c[2][:2])
            for i in (7, 8): put(i, c[9][:2])
            put(15, c[14][:2]); put(16, c[17][:2])
    if g == 'N':
        if master == 'R':
            put(2, (157, 560)); put(3, (157, 560)); put(8, (455, 140)); put(9, (455, 140))
        else:
            put(2, (193, 540)); put(3, (193, 540)); put(8, (419, 160)); put(9, (419, 160))
    return [[tuple(p) for p in c]]

def blend(A, B, t):
    return [[(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2]) for a, b in zip(ca, cb)] for ca, cb in zip(A, B)]

def draw_ufo_contours(contours, pen, scale=1.0, dx=0.0):
    # contours are UFO point lists; draw as segments via a point-pen style conversion
    from fontTools.pens.pointPen import SegmentToPointPen, PointToSegmentPen
    pp = PointToSegmentPen(pen)
    for c in contours:
        pp.beginPath()
        for x, y, t in c:
            pp.addPoint((x * scale + dx, y * scale), segmentType=t)
        pp.endPath()

def build(stem, out):
    global PLAIN
    R = ufoLib2.Font.open('../upstream/SpaceMono-Regular.ufo'); B = ufoLib2.Font.open('../upstream/SpaceMono-Bold.ufo')
    def hstem(u):
        c = pts(u, 'H')[0]; xs = sorted(set(round(p[0]) for p in c)); return xs[1] - xs[0]
    hR, hB = hstem(R), hstem(B)
    t = (stem / SC - hR) / (hB - hR)
    glyphs = {}
    TMAX = {'M': 1.40, 'W': 1.40}   # four-stroke letters: 4 x full stems cannot fit a 700 cell
    tB = (197 / SC - hR) / (hB - hR)   # t at the Black stem
    NBLACK = [(33, 0), (205, 0), (205, 630), (223, 630), (256, 0), (579, 0), (579, 700), (407, 700), (407, 70), (389, 70), (356, 700), (33, 700)]
    NBLACK_PLAIN = [(33, 0), (205, 0), (205, 540), (205, 540), (256, 0), (579, 0), (579, 700), (407, 700), (407, 160), (407, 160), (356, 700), (33, 700)]
    for g in 'MONX':
        a, b = fix(g, pts(R, g)), fixB(g, pts(B, g))
        if PLAIN:
            a, b = plain(g, a, 'R'), plain(g, b, 'B')
        if g == 'N' and t > 1:
            nb = [[(x, y, 'line') for x, y in (NBLACK_PLAIN if PLAIN else NBLACK)]]
            glyphs[g] = ('sm', blend(b, nb, (t - 1) / (tB - 1)))
        else:
            glyphs[g] = ('sm', blend(a, b, min(t, TMAX.get(g, 99))))
    # Martian P R: instances at 400 and 800, extrapolate by stem
    mar = TTFont('../upstream/martian.woff2')
    i400 = instantiateVariableFont(copy.deepcopy(mar), {'wght': 400})
    i800 = instantiateVariableFont(copy.deepcopy(mar), {'wght': 800})
    def pstem(f):
        gn_ = mar.getBestCmap()[ord('P')]
        c, _, _ = f['glyf'][gn_].getCoordinates(f['glyf']); xs = sorted(p[0] for p in c if abs(p[1]) < 1); return xs[-1] - xs[0]
    k = (stem - pstem(i400)) / (pstem(i800) - pstem(i400))
    for g in 'PR':
        gn = mar.getBestCmap()[ord(g)]
        c4, e4, _ = i400['glyf'][gn].getCoordinates(i400['glyf'])
        c8, _, _ = i800['glyf'][gn].getCoordinates(i800['glyf'])
        coords = [(a[0] + k * (b[0] - a[0]), a[1] + k * (b[1] - a[1])) for a, b in zip(c4, c8)]
        gl = copy.deepcopy(i400['glyf'][gn]); gl.coordinates = type(gl.coordinates)(coords)
        glyphs[g] = ('tt', gl, i400)
    # Geist Y: pick the weight whose stem matches (Geist stem ~= Geist H stem), scale to cap 800
    gei = TTFont('../upstream/GeistMono.ttf')
    gsc = 800 / 710
    g4 = instantiateVariableFont(copy.deepcopy(gei), {'wght': 400})
    g9 = instantiateVariableFont(copy.deepcopy(gei), {'wght': 900})
    def hs(f):
        c, _, _ = f['glyf']['H'].getCoordinates(f['glyf']); xs = sorted(set(round(p[0]) for p in c)); return (xs[1] - xs[0]) * gsc
    def ystem(f):
        c, _, _ = f['glyf']['Y'].getCoordinates(f['glyf']); xs = sorted(p[0] for p in c if abs(p[1]) < 1); return (xs[-1] - xs[0]) * gsc
    kg = (stem - ystem(g4)) / (ystem(g9) - ystem(g4))
    yn = 'Y'
    c4, _, _ = g4['glyf'][yn].getCoordinates(g4['glyf']); c9, _, _ = g9['glyf'][yn].getCoordinates(g9['glyf'])
    gy = copy.deepcopy(g4['glyf'][yn]); gy.coordinates = type(gy.coordinates)([(a[0] + kg * (b[0] - a[0]), a[1] + kg * (b[1] - a[1])) for a, b in zip(c4, c9)])
    glyphs['Y'] = ('geist', gy, g4)
    best = (hs(g4) + kg * (hs(g9) - hs(g4)), None, kg)
    fb = FontBuilder(1000, isTTF=True)
    order = ['.notdef', 'space'] + list('MONPRXY')
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({32: 'space', **{ord(c): c for c in 'MONPRXY'}})
    ttg = {}
    for gname in order:
        pen = TTGlyphPen(None)
        if gname in ('.notdef', 'space'):
            ttg[gname] = pen.glyph(); continue
        kind = glyphs[gname][0]
        if kind == 'sm':
            draw_ufo_contours(glyphs[gname][1], Cu2QuPen(pen, 1.0, reverse_direction=True), SC)
        elif kind == 'tt':
            gl, src = glyphs[gname][1], glyphs[gname][2]
            gl.draw(pen, src['glyf'])
        else:
            gl, src = glyphs[gname][1], glyphs[gname][2]
            tp = TransformPen(pen, (gsc, 0, 0, gsc, (700 - 600 * gsc) / 2, 0))
            gl.draw(tp, src['glyf'])
        ttg[gname] = pen.glyph()
    fb.setupGlyf(ttg)
    fb.setupHorizontalMetrics({g: (700, 0) for g in order})
    fb.setupHorizontalHeader(ascent=1000, descent=-200)
    fb.setupNameTable({'familyName': 'Monoproxy Remix Preview', 'styleName': 'Regular'})
    fb.setupOS2(sTypoAscender=1000, sTypoDescender=-200, usWinAscent=1100, usWinDescent=300)
    fb.setupPost()
    fb.save(out)
    return t, k, best[2], best[0]

if __name__ == '__main__':
    stem = float(sys.argv[1]); out = sys.argv[2]
    PLAIN = len(sys.argv) > 3 and sys.argv[3] == 'plain'
    print(build(stem, out))
