"""How tight a glyph's curves turn: the radius (font units) of the circle through three neighbouring
points of the outline, sampled finely along every curve. Tight turns are where it is smallest.

    python3 curves.py <font.ttf> <glyph> [...]     prints the tightest turns of each contour
"""
import math, sys


def samples(gl, glyf, steps=48, lines=None):
    """The outline, contour by contour, as fine points; each tagged with the on-curve point it
    follows (so a turn can be traced back to the points that make it). `lines`, if a list, gets one set
    per contour: the ring positions where a straight segment starts (the step to the next is a line)."""
    c, f = list(gl.coordinates), list(gl.flags); out = []; s = 0
    for e in gl.endPtsOfContours:
        pts = list(range(s, e + 1)); n = len(pts); ring = []; straight = set()
        # expand implied on-curve points between two handles
        seq = []
        for k in range(n):
            i, j = pts[k], pts[(k + 1) % n]
            seq.append((c[i], f[i] & 1, i))
            if not f[i] & 1 and not f[j] & 1:
                seq.append((((c[i][0] + c[j][0]) / 2, (c[i][1] + c[j][1]) / 2), 1, i))
        m = len(seq); k0 = next(k for k in range(m) if seq[k][1])
        seq = seq[k0:] + seq[:k0]; k = 0
        while k < m:
            p0, _, i0 = seq[k]
            if seq[(k + 1) % m][1]:
                straight.add(len(ring)); ring.append((p0, i0)); k += 1; continue
            p1, p2 = seq[(k + 1) % m][0], seq[(k + 2) % m][0]
            for t in range(steps):
                u = t / steps
                ring.append((((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
                              (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]), i0))
            k += 2
        out.append(ring); s = e + 1
        if lines is not None: lines.append(straight)
    return out


def radius(a, b, c):
    A, B, C = math.dist(b, c), math.dist(a, c), math.dist(a, b)
    cross = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    return float('inf') if cross < 1e-9 else A * B * C / (2 * cross)


def unfolded(gl, near=8):
    """The glyph's coordinates with each fold merged: two on-curve points closer than `near` units where
    the outline runs back on itself (S's counter ends are drawn so). The fold is a zero-area spike,
    invisible, but a three-point circle across it reads about its length."""
    c, f = list(gl.coordinates), gl.flags; s = 0
    for e in gl.endPtsOfContours:
        n = e - s + 1
        for k in range(n):
            a, p, q = s + (k - 1) % n, s + k, s + (k + 1) % n
            if not (f[p] & 1 and f[q] & 1) or math.dist(c[p], c[q]) >= near or math.dist(c[p], c[q]) == 0: continue
            v1 = (c[p][0] - c[a][0], c[p][1] - c[a][1]); v2 = (c[q][0] - c[p][0], c[q][1] - c[p][1])
            if v1[0] * v2[0] + v1[1] * v2[1] < 0:               # runs back the way it came
                m = ((c[p][0] + c[q][0]) / 2, (c[p][1] + c[q][1]) / 2); c[p] = c[q] = m
        s = e + 1
    return c


def tight_turns(gl, glyf, limit=None, gap=4, unfold=False, curve_only=False):
    """Local minima of the turning radius along each contour, tightest first: (radius, x, y, point).
    unfold: measure with folds merged (see unfolded). curve_only: never a circle across a straight
    segment; one through a sample on a curve and the far corner of a short straight run reads that
    corner as a turn (the y's half-closed ink trap between widths read r9 so). Corners are
    measure.kinks' business. Off by default: the S and s builds in wdth.py were tuned on the old reading."""
    if unfold:
        real = gl.coordinates; gl.coordinates = type(real)(unfolded(gl))
        try: return tight_turns(gl, glyf, limit, gap, curve_only=curve_only)
        finally: gl.coordinates = real
    res = []; straight = []
    for ring, line in zip(samples(gl, glyf, lines=straight), straight):
        n = len(ring); rs = []
        for k in range(n):
            if curve_only and any((k + j) % n in line for j in range(-gap, gap)): rs.append(float('inf')); continue
            rs.append(radius(ring[(k - gap) % n][0], ring[k][0], ring[(k + gap) % n][0]))
        for k in range(n):
            w = [rs[(k + d) % n] for d in range(-12, 13)]
            if rs[k] == min(w) and rs[k] < (limit or 1e9):
                res.append((round(rs[k], 1), round(ring[k][0][0]), round(ring[k][0][1]), ring[k][1]))
    return sorted(set(res))


if __name__ == '__main__':
    from fontTools.ttLib import TTFont
    f = TTFont(sys.argv[1]); g = f['glyf']; cm = f.getBestCmap()
    for ch in sys.argv[2:]:
        name = cm.get(ord(ch), ch)
        print(ch, tight_turns(g[name], g, limit=400)[:8])
