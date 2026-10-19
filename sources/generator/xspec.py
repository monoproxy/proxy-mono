"""Height test sheets: a to z (or A to Z) in five rows at one weight, on the guides, every flat top printed.

    python3 xspec.py [caps] [noline] [out_dir]      every weight at width 100 and 150 (10 cores) -> build/xheight/

The guides are the design's: cap height 800, x-height 600, baseline 0, overshoot +-16, the 700 (or
1050) cell. The red line is the weight's own x-height, the n's flat stem top (it rises with weight on
purpose). Under each letter is its flat x-height top: red when it is not on the n's. With `caps`, the
capitals against the cap height: red when a flat top is not on 800. `noline` leaves the red line off, to see
the tops themselves.
"""
import os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pathops
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
VF = os.path.join(ROOT, 'fonts/variable/ProxyMono[wdth,wght].ttf')
LABEL = os.path.join(ROOT, 'fonts/ttf/ProxyMono-Regular.ttf')
ROWS = ['abcdef', 'ghijk', 'lmnop', 'qrstu', 'vwxyz']
CAP = 800
SS = 2                  # supersampling
PX = 0.5                # px per unit in the final image
BG, INK, RULE, GRID, RED = (244, 244, 246), (50, 50, 52), (110, 110, 112), (214, 214, 218), (214, 40, 40)
TOP, BOT = 900, -420    # unit band drawn per row
LEFT, RIGHT = 900, 1250 # label margins, units


class Flat(BasePen):
    """Outline -> polygons in pixels."""
    def __init__(self, gs, tf):
        super().__init__(gs); self.tf = tf; self.polys = []; self.cur = []
    def _moveTo(self, p): self.cur = [self.tf(p)]
    def _lineTo(self, p): self.cur.append(self.tf(p))
    def _curveToOne(self, a, b, c):
        p0 = self._getCurrentPoint()
        for i in range(1, 25):
            t = i / 24; u = 1 - t
            self.cur.append(self.tf(tuple(u**3*p0[k] + 3*u*u*t*a[k] + 3*u*t*t*b[k] + t**3*c[k] for k in (0, 1))))
    def _qCurveToOne(self, a, b):
        p0 = self._getCurrentPoint()
        for i in range(1, 13):
            t = i / 12; u = 1 - t
            self.cur.append(self.tf(tuple(u*u*p0[k] + 2*u*t*a[k] + t*t*b[k] for k in (0, 1))))
    def _closePath(self): self.polys.append(self.cur); self.cur = []


def flat_tops(rec, lo=540, hi=680):
    """Level on-curve edges between lo and hi with ink below both ends (stem and arm tops)."""
    out = set(); con = []
    def close():
        ons = [p for k, p in con if k]
        n = len(ons)
        for i in range(n):
            a, b = ons[i], ons[(i + 1) % n]
            if abs(a[1] - b[1]) < .5 and abs(a[0] - b[0]) > 20 and lo < a[1] < hi and \
                    ons[i - 1][1] < a[1] - 20 and ons[(i + 2) % n][1] < a[1] - 20:
                out.add(round(a[1]))
    for op, a in rec:
        if op == 'moveTo': con = [(1, a[0])]
        elif op == 'lineTo': con.append((1, a[0]))
        elif op in ('qCurveTo', 'curveTo'): con += [(0, p) for p in a[:-1]] + [(1, a[-1])]
        elif op in ('closePath', 'endPath'): close(); con = []
    return out


def sheet(job):
    wd, w, out, caps, noline = job
    rows = [r.upper() for r in ROWS] if caps else ROWS
    tops = (lambda r: flat_tops(r, 760, 840)) if caps else flat_tops
    f = instantiateVariableFont(TTFont(VF), {'wdth': wd, 'wght': w})
    gs = f.getGlyphSet(); cm = f.getBestCmap(); cell = f['hmtx'][cm[ord('n')]][0]
    recs = {}
    for c in ''.join(rows):
        r = DecomposingRecordingPen(gs); gs[cm[ord(c)]].draw(r); recs[c] = r.value
    xh = CAP if caps else max(tops(recs['n']))
    k = PX * SS; rowh = TOP - BOT
    W = round((LEFT + 6 * cell + RIGHT) * k); H = round((rowh * len(rows) + 500) * k)
    img = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(img)
    sm = ImageFont.truetype(LABEL, round(26 * SS))
    lab = ImageFont.truetype(LABEL, round(30 * SS)); head = ImageFont.truetype(LABEL, round(44 * SS))
    d.text((LEFT * k, 60 * k), (f'Proxy Mono  wght {w}  wdth {wd}   cap height {xh}' if caps else f'Proxy Mono  wght {w}  wdth {wd}   x-height of this weight (n) {xh}'), fill=INK, font=head)
    x0 = LEFT * k; x1 = (LEFT + 6 * cell) * k
    def dotted(y, col):
        for x in range(round(x0), round(x1), round(8 * SS)): d.line([(x, y), (x + 4 * SS, y)], fill=col, width=SS)
    for r, row in enumerate(rows):
        base = (300 + r * rowh + TOP) * k
        Y = lambda u: base - u * k
        for i in range(7):   # cell lines
            d.line([(x0 + i * cell * k, Y(TOP - 60)), (x0 + i * cell * k, Y(BOT + 100))], fill=GRID, width=SS)
        for u, name in ((800, 'Cap height 800'), (600, 'x-height 600'), (0, 'Baseline 0')):
            d.line([(x0, Y(u)), (x1, Y(u))], fill=RULE, width=SS)
            d.text((x1 + 30 * k, Y(u)), name, fill=RULE, font=lab, anchor='lm')
        for u, name in ((816, 'Overshoot +16'), (-16, 'Overshoot -16')):
            dotted(Y(u), RULE); d.text((x0 - 30 * k, Y(u)), name, fill=RULE, font=lab, anchor='rm')
        gw, gh = round(cell * k), round(rowh * k)
        for i, c in enumerate(row):
            p = pathops.Path(); pen = p.getPen()
            for op, a in recs[c]: getattr(pen, op)(*a)
            p.simplify(fix_winding=True)
            fp = Flat(None, lambda q: (q[0] * k, (TOP - q[1]) * k)); p.draw(fp)
            mask = np.zeros((gh, gw), np.uint8)
            for poly in fp.polys:   # overlaps removed above, so even-odd is the font's own fill
                if len(poly) > 2:
                    m = Image.new('L', (gw, gh), 0); ImageDraw.Draw(m).polygon(poly, fill=255)
                    mask ^= np.array(m)
            img.paste(INK, (round(x0 + i * cell * k), round(Y(TOP))), Image.fromarray(mask))
            ft = sorted(tops(recs[c]))
            off = [t for t in ft if t != xh]
            txt = ' '.join(map(str, ft)) if ft else 'round'
            d.text((x0 + (i + .5) * cell * k, Y(BOT + 45)), f'{c}  {txt}', fill=RED if off else RULE, font=sm, anchor='mm')
        # the weight's own x-height, over the ink so it shows where a top pokes above it
        if not noline:
            d.line([(x0, Y(xh)), (x1, Y(xh))], fill=RED, width=SS)
        if not caps:   # on capitals the red line is the cap height itself, labelled on the right
            d.text((x0 - 30 * k, Y(xh)), f'this weight {xh}', fill=RED, font=lab, anchor='rm')
    img = img.resize((W // SS, H // SS), Image.LANCZOS)
    path = os.path.join(out, f'{"capheight" if caps else "xheight"}{"-noline" if noline else ""}-w{wd}-{w}.png'); img.save(path)
    bad = {c: sorted(tops(recs[c])) for c in recs if any(t != xh for t in tops(recs[c]))}
    return wd, w, xh, bad, path


if __name__ == '__main__':
    args = sys.argv[1:]; caps = 'caps' in args; noline = 'noline' in args
    args = [a for a in args if a not in ('caps', 'noline')]
    out = args[0] if args else os.path.join(ROOT, 'build/xheight')
    os.makedirs(out, exist_ok=True)
    jobs = [(wd, w, out, caps, noline) for wd in (100, 150) for w in range(100, 1000, 100)]
    with ProcessPoolExecutor(10) as ex:
        for wd, w, xh, bad, path in ex.map(sheet, jobs):
            print(f'wdth {wd} wght {w}: {"cap height" if caps else "x-height"} {xh}; off it: ' +
                  (' '.join(f'{c}{v}' for c, v in bad.items()) or 'none'))
