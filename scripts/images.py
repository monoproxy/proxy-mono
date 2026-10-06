"""The README and article images, drawn from the built variable font so they never show an old glyph.
Usage (from the repo root, after `make build`): python3 scripts/images.py   — needs Pillow."""
from PIL import Image, ImageDraw, ImageFont

VF = 'fonts/variable/ProxyMono[wght].ttf'
INK, GREY, RULE, PAPER = (244, 244, 236), (140, 140, 140), (52, 52, 52), (17, 17, 17)
NAMES = ['Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black']
_cache = {}

def font(size, wght=400):
    k = (round(size), wght)
    if k not in _cache:
        f = ImageFont.truetype(VF, k[0]); f.set_variation_by_axes([wght]); _cache[k] = f
    return _cache[k]

def text(d, xy, s, size, wght=400, fill=INK, anchor='ls'):
    d.text(xy, s, font=font(size, wght), fill=fill, anchor=anchor)

def hero():
    im = Image.new('RGB', (1900, 1745), 'black'); d = ImageDraw.Draw(im)
    text(d, (32, 470), 'PROXY', 525, 650, 'white'); text(d, (32, 932), 'MONO', 525, 650, 'white')
    text(d, (50, 1033), 'A monospace font rebuilt by code, for code.', 46, 400, 'white')
    text(d, (1850, 1033), '100-900 · OFL', 36, 400, GREY, 'rs')
    d.line([(50, 1094), (1850, 1094)], fill=RULE, width=2)
    for i in range(9):
        text(d, (50 + i * 200, 1262), 'Aa', 131, (i + 1) * 100, 'white')
        text(d, (54 + i * 200, 1322), str((i + 1) * 100), 28, 400, GREY)
    d.line([(50, 1374), (1850, 1374)], fill=RULE, width=2)
    rows = ['ABCDEFGHIJKLMNOPQRSTUVWXYZ  0123456789', 'abcdefghijklmnopqrstuvwxyz  !?&@%${}[]()',
            '0O 1lI|  != => <= ->  ←↑→↓  ①②③  ¼½  €£¥']
    for r, s in zip((1480, 1578, 1672), rows): text(d, (50, r), s, 64.2, 500, 'white')
    im.save('documentation/hero.png')

def letters():
    W = 1900; mx = 165; lines = ['COMING', 'NOW Q4', '2026']
    size = (W - 2 * mx) / 6 / 0.7; lh = size * 0.98; top = 110
    im = Image.new('RGB', (W, int(top + len(lines) * lh + 170)), 'black'); d = ImageDraw.Draw(im)
    for j, l in enumerate(lines): text(d, (mx, top + j * lh + size * 0.8), l, size, 650, 'white')
    y = top + len(lines) * lh + 40
    d.line([(mx, y), (W - mx, y)], fill=(70, 70, 70), width=2)
    text(d, (mx, y + 66), 'M N W G Q rebuilt on one stem. C G O Q and 0 share one oval.', 34, 400, 'white')
    text(d, (W - mx, y + 66), '650', 34, 400, GREY, 'rs')
    im.save('documentation/letters.png')

def weights():
    im = Image.new('RGB', (1900, 1200), PAPER); d = ImageDraw.Draw(im)
    for i, n in enumerate(NAMES):
        y = 135 + 126 * i; w = (i + 1) * 100
        text(d, (40, y - 16), str(w), 28, 400, GREY); text(d, (152, y), n, 97, w)
        text(d, (1860, y - 16), 'if (a >= 0) { return b[i] * 1.5; }', 30, w, INK, 'rs')
        d.line([(40, y + 23), (1860, y + 23)], fill=(40, 40, 40), width=1)
    im.save('documentation/weights.png')

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
    im = Image.new('RGB', (1900, 910), PAPER); d = ImageDraw.Draw(im); size = 38; adv = size * 0.7
    for i, line in enumerate(CODE):
        y = 90 + 60 * i
        text(d, (92, y), str(i + 1), size, 400, (110, 110, 110), 'rs')
        col = 0
        for cls, t in tokens(line):                   # syntax colour on, one grid, all Regular
            for ch in t:
                text(d, (147 + adv * col, y), ch, size, 400, SYNTAX.get(cls, INK)); col += 1
    d.line([(40, 690), (1860, 690)], fill=(40, 40, 40), width=1)
    small = "0O 1lI| {}[]() != => <= -> :: ;, '\" `   for (let i = 0; i < l1.length; i++) {}"
    for px, y in ((11, 752), (13, 797), (16, 850)):
        text(d, (40, y - 4), str(px), 20, 400, GREY); text(d, (110, y), small, px * 2, 400)
    im.save('documentation/code.png')

def specimen():
    im = Image.new('RGB', (1900, 1200), PAPER); d = ImageDraw.Draw(im)
    up, lo = 'ÀÁÂÃÄÅ ÇÈÉÊË ĞŁŃŐŘŠŤŮŽ ÆŒØÞẞ «»', 'àáâãäå çèéêë ğłńőřšťůž æœøþß ¿¡€£¥©®™'
    for i in range(9):
        text(d, (20, 62 + 130 * i), up, 44, (i + 1) * 100); text(d, (20, 120 + 130 * i), lo, 44, (i + 1) * 100)
    im.save('documentation/specimen.png')
    im.resize((1621, 1024), Image.LANCZOS).save('documentation/article/specimen.png')

def weight_axis():
    frames = []
    for i in range(36):
        w = round(100 + 800 * (1 - abs(1 - i / 18)))
        im = Image.new('RGB', (1900, 560), PAPER); d = ImageDraw.Draw(im)
        text(d, (60, 310), 'Proxy Mono', 246, w); text(d, (50, 482), 'wght %d' % w, 60, 500, GREY)
        frames.append(im.convert('P', palette=Image.ADAPTIVE, colors=32))
    frames[0].save('documentation/weight-axis.gif', save_all=True, append_images=frames[1:], duration=90, loop=0)

if __name__ == '__main__':
    for f in (hero, letters, weights, code, specimen, weight_axis): f()
