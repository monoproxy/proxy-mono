"""The y's stems merge with no notch. Usage: close_y.py <font.ttf>...  (in place)
The drawn y (Geist Mono's) stops its left arm in a small level cut against the right arm, an ink trap that
shows as a step where the stems merge. wide.py closes it at width 150; this closes it at width 100, in the
statics and the weight masters. The masters are closed only after the width-150 masters are made from them
(see Makefile), so width 150 stays exactly as wide.py draws it.
At the heavier weights the left arm's edge crosses the tail's curve (2-5) before it reaches the right arm,
and running it on to the right arm leaves a hook of that curve showing. There the drawn curve is scaled
down until it ends on the arm's edge instead (onto_arm). The point count stays the drawn one."""
import sys
from fontTools.ttLib import TTFont
from wide import close_y_trap


def onto_arm(c):
    """Where the left arm's edge (8 -> 7) crosses the tail's curve (2 -> 5): the curve, kept as drawn but
    scaled about 2 until it ends on that edge, so it rises into the join as at width 150 and the arm meets
    it in a clean corner. False where the edge doesn't cross the curve (it meets the right arm instead)."""
    (ax, ay), (bx, by) = c[8], c[7]; dx, dy = bx - ax, by - ay
    side = lambda p: dx * (p[1] - ay) - dy * (p[0] - ax)
    s2, s5 = side(c[2]), side(c[5])
    if s2 == 0 or (s2 > 0) == (s5 > 0): return False
    k = s2 / (s2 - s5)          # side() is linear, so this scale puts 5 exactly on the edge
    x2, y2 = c[2]
    for i in (3, 4, 5): c[i] = (x2 + k * (c[i][0] - x2), y2 + k * (c[i][1] - y2))
    c[6] = c[7] = c[5]
    return True


for path in sys.argv[1:]:
    f = TTFont(path); gl = f['glyf']; g = f.getBestCmap()[ord('y')]; y = gl[g]
    c = [tuple(map(float, p)) for p in y.coordinates]
    if onto_arm(c):
        y.coordinates = type(y.coordinates)([(round(x), round(v)) for x, v in c])
    else:
        close_y_trap(y)
    y.recalcBounds(gl); f['hmtx'][g] = (f['hmtx'][g][0], y.xMin)
    f.save(path)
