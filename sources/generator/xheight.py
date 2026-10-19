"""One x-height per weight and one cap height: every flat top of a letter on its line.

    python3 xheight.py <font.ttf> ...      (in place; a static, a weight master or a width-150 master)

Lowercase: the height still rises with weight (Geist's, kept on purpose), but within a weight the letters
drifted apart: at 900 the n stood at 609, m w y at 611, x at 614, p q at 608, and the width-150 v at 606 at
every weight. The n's flat stem top is the height of the weight.

Capitals: Space Mono's 700 cap height times its scale (700/612) is 800.65, so its capitals stood at 801
while Martian's and Geist's (B D J K P R Y) and the figures stood at 800. Every flat capital top is 800.

Only straight edges move. The two corners of a cut top each slide along their own edge: straight down an
upright stem, along the stroke on a diagonal (A V W X, x v w y), so the stroke keeps its thickness and angle
and its leg is just shortened (or lengthened). A capital's bar (E F I T Z) moves whole, its underside with
it, so it keeps its thickness. No point that is a curve handle or touches a curve moves: such a top is left
alone and reported, so the curves stay as approved. Points only move, so every master keeps its point
count and order.
"""
import sys, unicodedata
from fontTools.ttLib import TTFont

NEAR = 12  # a flat top this close to its line is on it (the ø's slash end, an i's dot are not)
SKIP = {'ƒ'}   # its bar sits below the x-height by design: a bar top, not a stem top
CAP = 800
BAR = 260  # a capital's top corner dropping straight to a level edge within this is a bar's end


def n_height(gl, cm):
    g = gl[cm[ord('n')]]; co, ends, fl = g.getCoordinates(gl)
    ys = [co[i][1] for i in range(len(co) - 1) if fl[i] & 1 and fl[i + 1] & 1 and
          co[i][1] == co[i + 1][1] and 500 < co[i][1] < 700 and abs(co[i][0] - co[i + 1][0]) > 20]
    return max(ys)


def slide(co, p, q, y):
    """p along the straight line through q, to height y."""
    x0, y0 = co[p]; x1, y1 = co[q]
    return (round(x0 + (y - y0) / (y0 - y1) * (x0 - x1)), y)


def level(f, cat, h, bars):
    gl = f['glyf']; cm = f.getBestCmap(); moved = {}; left = []
    names = sorted({g for u, g in cm.items() if unicodedata.category(chr(u)) == cat and chr(u) not in SKIP})
    for name in names:
        g = gl[name]
        if g.isComposite() or not g.numberOfContours:
            continue
        co, ends, fl = g.getCoordinates(gl); start = 0
        on = lambda *ps: all(fl[p] & 1 for p in ps)
        for end in ends:
            idx = list(range(start, end + 1)); n = len(idx); start = end + 1
            for k in range(n):
                a, b = idx[k], idx[(k + 1) % n]
                pa, pb = co[a], co[b]
                if not on(a, b) or pa[1] != pb[1] or pa[1] == h or abs(pa[1] - h) > NEAR \
                        or abs(pa[0] - pb[0]) < 20:
                    continue
                na, nb = idx[(k - 1) % n], idx[(k + 2) % n]   # each corner's other neighbour
                if co[na][1] > pa[1] - 20 or co[nb][1] > pb[1] - 20:
                    continue   # not a top: the ink is not below both corners
                if not on(na, nb):
                    left.append(f'{name}@{pa[1]}'); continue
                dy = h - pa[1]; new = {}
                for p, kq, d in ((a, k - 1, -1), (b, k + 2, 1)):
                    q = idx[kq % n]; r = idx[(kq + d) % n]; s = idx[(kq + 2 * d) % n]
                    x0, y0 = co[p]; xq, yq = co[q]
                    if bars and abs(xq - x0) < 1 and 0 < y0 - yq < BAR and co[r][1] == yq \
                            and abs(co[r][0] - xq) > 20:
                        if not on(r, s):
                            new = None; break
                        # a bar's end: the top corner, the corner under it and the bar's inner end all
                        # drop together, the inner end along the edge it starts (a stem, Z's diagonal)
                        new[p] = (x0, y0 + dy); new[q] = (xq, yq + dy); new[r] = slide(co, r, s, co[r][1] + dy)
                    else:
                        new[p] = slide(co, p, q, h)
                if new is None:
                    left.append(f'{name}@{pa[1]}'); continue
                for p, v in new.items():
                    co[p] = v
                moved.setdefault(name, set()).add(pa[1])
        g.coordinates = co; g.recalcBounds(gl)
    return moved, left


def report(what, h, moved, left):
    return (f'{what} {h}; {len(moved)} levelled' +
            (f' ({" ".join(f"{n}{sorted(v)}" for n, v in list(moved.items())[:10])}{" ..." if len(moved) > 10 else ""})' if moved else '') +
            (f'; left (edge is a curve): {" ".join(left)}' if left else ''))


if __name__ == '__main__':
    # --lower or --caps for one pass only. The weight masters get their capitals levelled only after the
    # width-150 masters are made from them (as close_y.py), so the width step sees the drawn outline and
    # re-solves nothing: at width 150 the same top corners then move as at width 100, and nothing else
    args = sys.argv[1:]; lower = '--caps' not in args; caps = '--lower' not in args
    for path in (a for a in args if not a.startswith('--')):
        f = TTFont(path); h = n_height(f['glyf'], f.getBestCmap()); out = []
        if lower: out.append(report('x-height', h, *level(f, 'Ll', h, False)))
        if caps: out.append(report('cap height', CAP, *level(f, 'Lu', CAP, True)))
        f.save(path); print(f'{path.split("/")[-1]}: {"; ".join(out)}')
