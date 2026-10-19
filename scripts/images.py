"""The README and article images, drawn from the built variable font so they never show an old glyph.
Usage (from the repo root, after `make build`): python3 scripts/images.py   — needs Pillow."""
from PIL import Image, ImageDraw, ImageFont

VF = 'fonts/variable/ProxyMono[wdth,wght].ttf'
INK, GREY, RULE, PAPER = (244, 244, 236), (140, 140, 140), (52, 52, 52), (0, 0, 0)
W, M = 1900, 90                     # every image: 1900 wide, 90 px of black on all four sides
NAMES = ['Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black']
_cache = {}

def font(size, wght=400, wdth=100):
    k = (round(size, 2), wght, wdth)
    if k not in _cache:
        f = ImageFont.truetype(VF, k[0]); f.set_variation_by_axes([wght, wdth]); _cache[k] = f
    return _cache[k]

_ink = {}

def ink(f, ch):
    """A letter's ink, left to right, from its origin (Pillow's own box is the whole cell)."""
    k = (id(f), ch)
    if k not in _ink:
        size = int(f.size * 3); im = Image.new('L', (size, size), 0)
        ImageDraw.Draw(im).text((f.size, 2 * f.size), ch, font=f, fill=255, anchor='ls')
        b = im.getbbox(); _ink[k] = (b[0] - f.size, 0, b[2] - f.size, 0)
    return _ink[k]

EVEN = ('MONO', 'Mono')             # set with even gaps between letters (images only; the font is untouched)

def text(d, xy, s, size, wght=400, fill=INK, anchor='ls', wdth=100, extent=None):
    f = font(size, wght, wdth)
    if not any(w in s for w in EVEN) or anchor[0] == 'r':
        d.text(xy, s, font=f, fill=fill, anchor=anchor); return
    # monospaced, the M's wide ink leaves M-O tighter than O-N: within MONO / Mono the letters keep the
    # word's own ink extent and get equal gaps; everything else sits on its cells as typed
    x = xy[0] - (f.getlength(s) / 2 if anchor[0] == 'm' else 0); y = xy[1]; base = 'l' + anchor[1]
    i = 0
    for word in s.split(' '):
        if word in EVEN:
            boxes = [ink(f, ch) for ch in word]
            starts = [x + f.getlength(word[:k]) for k in range(len(word))]
            left, right = extent or (starts[0] + boxes[0][0], starts[-1] + boxes[-1][2])
            gap = (right - left - sum(b[2] - b[0] for b in boxes)) / (len(word) - 1)
            px = left
            for ch, b in zip(word, boxes):
                d.text((px - b[0], y), ch, font=f, fill=fill, anchor=base); px += b[2] - b[0] + gap
        else:
            d.text((x, y), word, font=f, fill=fill, anchor=base)
        x += f.getlength(word + ' ')


def span(s, size, wght, wdth=100):
    """Where `s` actually inks, left and right, from its origin at this size (rendered: Pillow's own box
    for a word runs cell edge to cell edge, so a line placed by it sits off by its first letter's side
    bearing, and the P and the M of the hero did not line up)."""
    f = font(size, wght, wdth); w = int(f.getlength(s) + 2 * size)
    im = Image.new('L', (w, int(size * 2)), 0)
    ImageDraw.Draw(im).text((size, size * 1.4), s, font=f, fill=255, anchor='ls')
    b = im.getbbox(); return b[0] - size, b[2] - size

def fit(s, width, wght, wdth=100):
    """The size at which `s` is exactly `width` px of ink across."""
    l, r = span(s, 400, wght, wdth); size = 400 * width / (r - l)
    l, r = span(s, size, wght, wdth); return size * width / (r - l)

def ink_box(ims):
    """The box round every non-black pixel in all the images (several: a GIF's frames, cropped alike)."""
    box = None
    for im in ims:
        b = im.convert('L').point(lambda v: 255 if v > 12 else 0).getbbox()
        if b: box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box

def finish(ims, path=None):
    """Crop to the ink and pad M on every side (the width stays W: ink is drawn from M to W - M)."""
    x0, y0, x1, y1 = ink_box(ims); out = []
    for im in ims:
        c = Image.new('RGB', (W, y1 - y0 + 2 * M), PAPER)
        c.paste(im.crop((x0, y0, x1, y1)), (M + (0 if x1 - x0 >= W - 2 * M else 0), M)); out.append(c)
    if path: out[0].save(path)
    return out

def hero():
    im = Image.new('RGB', (W, 2000), PAPER); d = ImageDraw.Draw(im); R = W - M
    # PROXY across the full inner width; MONO at width 125 and the same size: four characters on cells
    # 1.25 wide end exactly where the five of PROXY do
    big = fit('PROXY', R - M, 650)
    off = span('PROXY', big, 650)[0]
    text(d, (M - off, 470), 'PROXY', big, 650, 'white')
    # MONO: its four letters spread evenly over exactly PROXY's ink, so both lines start and end together
    text(d, (M, 932), 'MONO', big, 100, 'white', wdth=125, extent=(M, R))
    text(d, (M, 1033), 'A monospace font rebuilt by code, for code.', 40, 400, 'white')
    text(d, (R, 1033), '100-900 · 100-150 · OFL', 28, 400, GREY, 'rs')
    d.line([(M, 1094), (R, 1094)], fill=RULE, width=2)
    step = (R - M) / 9
    for i in range(9):
        text(d, (M + i * step, 1262), 'Aa', 125, (i + 1) * 100, 'white')
        text(d, (M + 4 + i * step, 1322), str((i + 1) * 100), 28, 400, GREY)
    d.line([(M, 1374), (R, 1374)], fill=RULE, width=2)
    rows = ['ABCDEFGHIJKLMNOPQRSTUVWXYZ  0123456789', 'abcdefghijklmnopqrstuvwxyz  !?&@%${}[]()',
            '0O 1lI|  != => <= ->  ←↑→↓  ①②③  ¼½  €£¥']
    size = (R - M) / 40 / 0.7                                  # 40 cells across the inner width
    for r, s_ in zip((1480, 1578, 1672), rows): text(d, (M, r), s_, size, 500, 'white')
    finish([im], 'documentation/hero.png')

def weights():
    im = Image.new('RGB', (W, 1300), PAPER); d = ImageDraw.Draw(im); R = W - M
    for i, n in enumerate(NAMES):
        y = 135 + 126 * i; w = (i + 1) * 100
        text(d, (M, y - 16), str(w), 28, 400, GREY); text(d, (M + 112, y), n, 97, w)
        text(d, (R, y - 16), 'if (a >= 0) { return b[i] * 1.5; }', 30, w, INK, 'rs')
        d.line([(M, y + 23), (R, y + 23)], fill=RULE, width=1)
    finish([im], 'documentation/weights.png')

CODE = ['// Reject a request whose token has expired.', 'export function requireFresh(req, res, next) {',
        '  const token = decode(req.headers.authorization);', '  const now = Math.floor(Date.now() / 1000);',
        '  if (!token || now >= token.exp) {', "    return res.status(401).json({ error: 'token expired' });", '  }',
        '  req.user = { id: token.sub, ttl: token.exp - now };', '  next();', '}']
KEYWORDS = ('export', 'function', 'const', 'if', 'return')

def oklch(L, C, h):
    """sRGB 0-255 from OKLCH, for the lab page's syntax palette."""
    import math
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_, m_, s_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_, -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    g = lambda c: 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return tuple(round(255 * min(1, max(0, g(c)))) for c in lin)

# the lab page's "Syntax colour" palette (Vercel's Geist docs code blocks, dark)
SYNTAX = {'c': (161, 161, 161), 'k': oklch(0.6936, 0.2223, 3.91), 's': oklch(0.731, 0.2158, 148.29),
          'n': oklch(0.717, 0.1648, 250.794), 'f': oklch(0.6987, 0.2037, 309.51)}

def tokens(line):
    """[(class, text)]: comment, keyword, string, number, call, or plain ('')."""
    import re
    if line.lstrip().startswith('//'): return [('c', line)]
    out = []
    for m in re.finditer(r"'[^']*'|\d+|[A-Za-z_]\w*|.", line):
        t = m.group(); nxt = line[m.end():m.end() + 1]
        cls = ('s' if t[0] == "'" else 'n' if t.isdigit() else 'k' if t in KEYWORDS
               else 'f' if (t[0].isalpha() or t[0] == '_') and nxt == '(' else '')
        out.append((cls, t))
    return out

def code():
    im = Image.new('RGB', (W, 1000), PAPER); d = ImageDraw.Draw(im); size = 38; adv = size * 0.7; R = W - M
    for i, line in enumerate(CODE):
        y = 90 + 60 * i
        text(d, (M + 52, y), str(i + 1), size, 400, (110, 110, 110), 'rs')
        col = 0
        for cls, t in tokens(line):                   # syntax colour on, one grid, all Regular
            for ch in t:
                text(d, (M + 107 + adv * col, y), ch, size, 400, SYNTAX.get(cls, INK)); col += 1
    d.line([(M, 690), (R, 690)], fill=RULE, width=1)
    small = "0O 1lI| {}[]() != => <= -> :: ;, '\" `   for (let i = 0; i < l1.length; i++) {}"
    k = fit(small, R - M - 70, 400) / 16                     # the 16 px line spans the inner width
    for px, y in ((11, 752), (13, 797), (16, 850)):
        text(d, (M, y - 4), str(px), 20, 400, GREY); text(d, (M + 70, y), small, px * k, 400)
    finish([im], 'documentation/code.png')

def specimen():
    im = Image.new('RGB', (W, 1300), PAPER); d = ImageDraw.Draw(im)
    up, lo = 'ÀÁÂÃÄÅ ÇÈÉÊË ĞŁŃŐŘŠŤŮŽ ÆŒØÞẞ «»', 'àáâãäå çèéêë ğłńőřšťůž æœøþß ¿¡€£¥©®™'
    size = min(fit(t, W - 2 * M, (i + 1) * 100) for t in (up, lo) for i in range(9))   # widest line spans it
    for _ in range(3):                                       # drawn (on a wide canvas), measured, set again
        lh = size * 1.32; pair = 2 * lh + size * 0.3              # line spacing follows the size
        im = Image.new('RGB', (2 * W, int(size + 9 * pair + 200)), PAPER); d = ImageDraw.Draw(im)
        for i in range(9):
            y = size * 1.1 + pair * i
            text(d, (M, y), up, size, (i + 1) * 100); text(d, (M, y + lh), lo, size, (i + 1) * 100)
        x0, _, x1, _ = ink_box([im]); size *= (W - 2 * M) / (x1 - x0)
    im = finish([im])[0]
    im.save('documentation/specimen.png')
    im.resize((1621, round(im.height * 1621 / W)), Image.LANCZOS).save('documentation/article/specimen.png')

def widths():
    # the width axis: the same words at the four named widths; every character keeps one cell, so a line
    # of ten characters grows from 7000 to 10500 units. Sized so the widest line spans the inner width
    WIDTHS = [(100, 'Normal'), (112.5, 'SemiExpanded'), (125, 'Expanded'), (150, 'ExtraExpanded')]
    R = W - M; size = fit('PROXY MONO', R - M, 650, 150); lh = 268; top = 50
    off = span('PROXY MONO', size, 650, 150)[0]
    im = Image.new('RGB', (W, top + lh * len(WIDTHS) + 300), PAPER); d = ImageDraw.Draw(im)
    for i, (wd, n) in enumerate(WIDTHS):
        y = top + i * lh + 150
        text(d, (M - off, y), 'PROXY MONO', size, 650, 'white', wdth=wd)
        d.line([(M, y + 34), (R, y + 34)], fill=RULE, width=2)
        text(d, (M, y + 76), f'{n} {wd:g}', 30, 400, GREY)
    y = top + lh * len(WIDTHS) + 80
    text(d, (M, y), 'Width 100 to 150. One cell per character: 700 units at 100, 1050 at 150.', 34, 400, 'white')
    finish([im], 'documentation/width-axis.png')

def weight_axis():
    # both axes at once: Thin at width 100 out to Black at width 150 and back, centred. Sized so the widest
    # frame spans the inner width; every frame cropped alike, so nothing jumps
    frames = []; N = 100                                     # 100 steps, 30 ms each, held at both ends
    size = fit('Proxy Mono', W - 2 * M, 900, 150)
    for _ in range(3):                                       # the widest frame, drawn and measured
        t = Image.new('RGB', (2 * W, 700), PAPER); text(ImageDraw.Draw(t), (W, 300), 'Proxy Mono', size, 900, anchor='ms', wdth=150)
        x0, _, x1, _ = ink_box([t]); size *= (W - 2 * M) / (x1 - x0)
    for i in range(N):
        f = 1 - abs(1 - i / (N / 2)); f = f * f * (3 - 2 * f)  # eased
        w = round(100 + 800 * f); wd = round(100 + 50 * f, 1)
        im = Image.new('RGB', (W, 700), PAPER); d = ImageDraw.Draw(im)
        text(d, (W / 2, 300), 'Proxy Mono', size, w, anchor='ms', wdth=wd)      # centred: grows both ways
        text(d, (W / 2, 470), 'wght %d   wdth %g' % (w, wd), 56, 500, GREY, 'ms')
        frames.append(im)
    x0, y0, x1, y1 = ink_box(frames)
    out = []
    for im in frames:
        c = Image.new('RGB', (W, y1 - y0 + 2 * M), PAPER); c.paste(im.crop((0, y0, W, y1)), (0, M))
        out.append(c.convert('P', palette=Image.ADAPTIVE, colors=32))
    times = [30] * N; times[0] = times[N // 2] = 350
    out[0].save('documentation/weight-axis.gif', save_all=True, append_images=out[1:], duration=times, loop=0)

if __name__ == '__main__':
    for f in (hero, widths, weights, code, specimen, weight_axis): f()
