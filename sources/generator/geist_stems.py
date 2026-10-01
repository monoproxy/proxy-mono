"""Measure each Geist Mono glyph's own stem (Geist units) at its 100 / 400 / 900 masters, so az.py can
calibrate every Geist glyph by its own stem instead of the n's (Danny, 30 Sep 2026: figures and
punctuation drifted 0.5-1.1 x the stem). Stem = median thickness of cuts that go straight across a
vertical/diagonal stroke; glyphs with none (- = _ ~) use their horizontal strokes. Writes
geist_stems.json next to this script."""
import copy, json, os, tempfile
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt as edt

HERE = os.path.dirname(os.path.abspath(__file__))
# beyond ASCII: the characters monoproxy.com.au actually sets (dashes, arrows, quotes, maths)
EXTRA = [0x2014, 0x2013, 0x2192, 0x2197, 0x2191, 0x2193, 0x2190, 0x00D7, 0x00B0, 0x2248, 0x2265, 0x2260,
         0x2212, 0x2500, 0x2039, 0x203A]
SRC = os.path.join(HERE, '..', 'src', 'GeistMono.ttf')

def cuts(a, dt):
    vals = []
    for i in range(a.shape[0]):
        idx = np.flatnonzero(np.diff(np.concatenate(([0], a[i].astype(np.int8), [0]))))
        for s, e in zip(idx[::2], idx[1::2]):
            t = 2 * dt[i, s:e].max()
            if e - s >= 6 and t >= 0.85 * (e - s):
                vals.append(t)
    return vals

# glyphs whose strokes cross: measure only the free arms (top and bottom 30% of the ink), because
# cuts through the crossing read the two strokes as one fat one and would thin the whole glyph
ARMS_ONLY = set('x')

def stem(font, ch):
    im = Image.new('L', (1200, 1600), 0); ImageDraw.Draw(im).text((300, 1200), ch, font=font, fill=255, anchor='ls')
    a = np.array(im) > 127
    if not a.any(): return None
    dt = edt(a)
    if ch in ARMS_ONLY:
        # rows 8-30% and 70-92% of the ink height: each cut crosses one arm; the widest inscribed circle
        # on a slanted straight stroke is its perpendicular thickness (the flat ends are skipped)
        ys = np.flatnonzero(a.any(1)); y0, y1 = ys.min(), ys.max(); h = y1 - y0
        v = []
        for i in list(range(y0 + int(0.08 * h), y0 + int(0.30 * h))) + list(range(y1 - int(0.30 * h), y1 - int(0.08 * h))):
            idx = np.flatnonzero(np.diff(np.concatenate(([0], a[i].astype(np.int8), [0]))))
            for s0, e0 in zip(idx[::2], idx[1::2]):
                v.append(2 * dt[i, s0:e0].max())
        return float(np.median(v)) if v else None
    v = cuts(a, dt)
    if len(v) < 20:                       # no real vertical/diagonal stroke: use the horizontal ones
        v = cuts(a.T, dt.T)
    return float(np.median(v)) if v else None

if __name__ == '__main__':
    g = TTFont(SRC); out = {}
    for w in (100, 400, 900):
        inst = instantiateVariableFont(copy.deepcopy(g), {'wght': w})
        path = os.path.join(tempfile.gettempdir(), f'geist-{w}.ttf'); inst.save(path)
        f = ImageFont.truetype(path, 1000)
        out[w] = {str(c): stem(f, chr(c)) for c in list(range(33, 127)) + EXTRA}
    json.dump(out, open(os.path.join(HERE, 'geist_stems.json'), 'w'), indent=0)
    for c in 'nmwvxy#@%-=_':
        print(c, [round(out[w][str(ord(c))] or 0) for w in (100, 400, 900)])
