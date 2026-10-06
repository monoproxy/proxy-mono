"""Variable ProxyMono from the nine static masters. Usage: vf.py <masters dir> <out.ttf>
Masters are built with VF=1 and are point-compatible. A glyph
that still differs in one master (the M at 900, whose V points meet) is rebuilt in that master by
extrapolating its two nearest compatible neighbours by stem."""
import sys, os
from fontTools.ttLib import TTFont
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from fontTools import varLib

SLANT = float(os.environ.get('SLANT', '0'))   # degrees; 0 = weight axis only (the Google Fonts build)
import math, copy
STYLES = ['Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black']
STEMS = [46, 68, 96, 110, 126, 144, 162, 180, 197]

def sig(f, g):
    gl = f['glyf'][g]
    if not gl.numberOfContours: return ()
    c, e, fl = gl.getCoordinates(f['glyf'])
    return (tuple(e), tuple(x & 1 for x in fl))

def align_starts(F, ref):
    """Rotate each master's contour start points to the default master's, so no contour turns inside out
    between masters (fontbakery interpolation_issues: the A family's shapely-built outlines start anywhere)."""
    for g in F[ref].getGlyphOrder():
        R = F[ref]['glyf'][g]
        if R.isComposite() or R.numberOfContours <= 0: continue
        rc, re_, rf = R.getCoordinates(F[ref]['glyf'])
        for f in F:
            G = f['glyf'][g]
            if G is R or G.isComposite(): continue
            c, e, fl = G.getCoordinates(f['glyf'])
            if list(e) != list(re_): continue
            pts, flags, s = [], [], 0
            for end in e:
                P = list(c[s:end + 1]); Fl = list(fl[s:end + 1]); Rp = list(rc[s:end + 1]); Rf = [x & 1 for x in rf[s:end + 1]]
                n = len(P); best, bk = None, 0
                for k in range(n):
                    if [Fl[(i + k) % n] & 1 for i in range(n)] != Rf: continue
                    d = sum((P[(i + k) % n][0] - Rp[i][0]) ** 2 + (P[(i + k) % n][1] - Rp[i][1]) ** 2 for i in range(n))
                    if best is None or d < best: best, bk = d, k
                pts += [P[(i + bk) % n] for i in range(n)]; flags += [Fl[(i + bk) % n] for i in range(n)]; s = end + 1
            G.coordinates = type(c)(pts); G.flags = type(fl)(flags)

def export_ufos(F, out='../masters'):
    """The nine masters as UFOs and a designspace (sources/masters), exactly as they go into the variable
    font, so the outlines can be opened in a font editor. Generated on every build: edit the generator,
    not these files."""
    import shutil, ufoLib2
    from fontTools.pens.cu2quPen import Cu2QuPen  # noqa: F401
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    ds = DesignSpaceDocument()
    ax = AxisDescriptor(); ax.tag = 'wght'; ax.name = 'Weight'; ax.minimum = 100; ax.default = 400; ax.maximum = 900
    ds.addAxis(ax)
    for i, f in enumerate(F):
        u = ufoLib2.Font(); inf = u.info; os2 = f['OS/2']; hh = f['hhea']
        inf.familyName = 'Proxy Mono'; inf.styleName = STYLES[i]; inf.unitsPerEm = f['head'].unitsPerEm
        inf.versionMajor = 1; inf.versionMinor = 0
        inf.ascender = os2.sTypoAscender; inf.descender = os2.sTypoDescender
        inf.capHeight = os2.sCapHeight; inf.xHeight = os2.sxHeight
        inf.openTypeOS2TypoAscender = os2.sTypoAscender; inf.openTypeOS2TypoDescender = os2.sTypoDescender
        inf.openTypeOS2TypoLineGap = os2.sTypoLineGap
        inf.openTypeOS2WinAscent = os2.usWinAscent; inf.openTypeOS2WinDescent = os2.usWinDescent
        inf.openTypeHheaAscender = hh.ascent; inf.openTypeHheaDescender = hh.descent; inf.openTypeHheaLineGap = hh.lineGap
        inf.openTypeOS2WeightClass = (i + 1) * 100; inf.openTypeOS2VendorID = os2.achVendID
        inf.postscriptIsFixedPitch = True
        inf.postscriptUnderlinePosition = f['post'].underlinePosition; inf.postscriptUnderlineThickness = f['post'].underlineThickness
        inf.openTypeOS2StrikeoutSize = os2.yStrikeoutSize; inf.openTypeOS2StrikeoutPosition = os2.yStrikeoutPosition
        inf.copyright = f['name'].getDebugName(0); inf.openTypeNameLicense = f['name'].getDebugName(13)
        inf.openTypeNameLicenseURL = f['name'].getDebugName(14)
        uni = {}
        for cp, gn in sorted(f.getBestCmap().items()): uni.setdefault(gn, []).append(cp)
        gs = f.getGlyphSet()
        for gn in f.getGlyphOrder():
            g = u.newGlyph(gn); g.width = f['hmtx'][gn][0]; g.unicodes = uni.get(gn, [])
            gs[gn].draw(g.getPen())
        u.lib['public.glyphOrder'] = f.getGlyphOrder()
        u.lib['com.github.googlei18n.ufo2ft.filters'] = []
        name = f'ProxyMono-{STYLES[i]}.ufo'; u.save(os.path.join(out, name), overwrite=True)
        sd = SourceDescriptor(); sd.filename = name; sd.familyName = 'Proxy Mono'; sd.styleName = STYLES[i]
        sd.location = {'Weight': (i + 1) * 100}; ds.addSource(sd)
    ds.write(os.path.join(out, 'ProxyMono.designspace'))

def main(src, out):
    paths = [os.path.join(src, f'ProxyMono-{s}.ttf') for s in STYLES]
    F = [TTFont(p) for p in paths]
    ref = 3   # Regular is the default master
    for g in F[ref].getGlyphOrder():
        ss = [sig(f, g) for f in F]
        for i, s in enumerate(ss):
            if s == ss[ref]: continue
            ok = sorted((j for j in range(9) if ss[j] == ss[ref]), key=lambda j: abs(STEMS[j] - STEMS[i]))[:2]
            a, b = sorted(ok)
            ca = F[a]['glyf'][g].getCoordinates(F[a]['glyf'])[0]; cb = F[b]['glyf'][g].getCoordinates(F[b]['glyf'])[0]
            k = (STEMS[i] - STEMS[a]) / (STEMS[b] - STEMS[a])
            new = F[ref]['glyf'][g].__class__()
            import copy
            new = copy.deepcopy(F[a]['glyf'][g])
            new.coordinates = type(ca)([(round(x + k * (x2 - x)), round(y + k * (y2 - y))) for (x, y), (x2, y2) in zip(ca, cb)])
            F[i]['glyf'][g] = new; new.recalcBounds(F[i]['glyf'])
            F[i]['hmtx'][g] = (700, new.xMin)
            print(f'{g}: master {STYLES[i]} rebuilt from {STYLES[a]}/{STYLES[b]}')
    align_starts(F, ref)
    export_ufos(F)
    ds = DesignSpaceDocument()
    ax = AxisDescriptor(); ax.tag = 'wght'; ax.name = 'Weight'; ax.minimum = 100; ax.default = 400; ax.maximum = 900
    ds.addAxis(ax)
    if SLANT:
        sl = AxisDescriptor(); sl.tag = 'slnt'; sl.name = 'Slant'; sl.minimum = -SLANT; sl.default = 0; sl.maximum = 0
        ds.addAxis(sl)
    for i, f in enumerate(F):
        sd = SourceDescriptor(); sd.font = f; sd.name = STYLES[i]
        sd.location = {'Weight': (i + 1) * 100, **({'Slant': 0} if SLANT else {})}
        sd.filename = paths[i]; ds.addSource(sd)
        if not SLANT: continue
        # slanted master: every outline sheared about half the cap height, so the letter leans without
        # leaving its 700 cell (an oblique, not a drawn italic)
        k = math.tan(math.radians(SLANT)); fs = copy.deepcopy(f); gl = fs['glyf']
        for g in fs.getGlyphOrder():
            gg = gl[g]
            if gg.numberOfContours > 0:
                gg.coordinates = type(gg.coordinates)([(round(x + (y - 400) * k), y) for x, y in gg.coordinates])
                gg.recalcBounds(gl); fs['hmtx'][g] = (700, gg.xMin)
        sd = SourceDescriptor(); sd.font = fs; sd.name = STYLES[i] + ' Slanted'
        sd.location = {'Weight': (i + 1) * 100, 'Slant': -SLANT}; sd.filename = paths[i]; ds.addSource(sd)
    vf, _, _ = varLib.build(ds, exclude=['MVAR'])
    vf['post'].italicAngle = 0
    # names: one family, "Regular" default, STAT for the named weights
    name = vf['name']
    for rec in list(name.names):
        if rec.nameID in (16, 17): name.removeNames(nameID=rec.nameID)
    name.setName('Proxy Mono', 1, 3, 1, 0x409); name.setName('Regular', 2, 3, 1, 0x409)
    name.setName('Proxy Mono Regular', 4, 3, 1, 0x409); name.setName('ProxyMono-Regular', 6, 3, 1, 0x409)
    name.setName('1.000;MNPX;ProxyMono[slnt,wght]' if SLANT else '1.000;MNPX;ProxyMono[wght]', 3, 3, 1, 0x409)
    from fontTools.varLib.instancer.names import updateNameTable  # noqa: F401 (ensures names module is present)
    from fontTools.otlLib.builder import buildStatTable
    fvar = vf['fvar']
    fvar.instances = []
    from fontTools.ttLib.tables._f_v_a_r import NamedInstance
    for i, s in enumerate(STYLES):
        ni = NamedInstance(); ni.coordinates = {'wght': (i + 1) * 100, **({'slnt': 0} if SLANT else {})}
        ni.subfamilyNameID = name.addMultilingualName({'en': s}, mac=False)
        ni.postscriptNameID = name.addMultilingualName({'en': f'ProxyMono-{s}'}, mac=False)
        fvar.instances.append(ni)
    buildStatTable(vf, [{'tag': 'wght', 'name': 'Weight', 'values': [
        {'value': (i + 1) * 100, 'name': s, **({'flags': 2, 'linkedValue': 700} if s == 'Regular' else {})}
        for i, s in enumerate(STYLES)]}] + ([
        {'tag': 'slnt', 'name': 'Slant', 'values': [{'value': 0, 'name': 'Upright', 'flags': 2},
                                                   {'value': -SLANT, 'name': 'Slanted'}]}] if SLANT else []))
    vf['OS/2'].usWeightClass = 400; vf['OS/2'].fsSelection = (1 << 8) | (1 << 7) | (1 << 6); vf['head'].macStyle = 0
    # avar: the masters sit at every hundred, so the mapping is the identity; it says so explicitly
    from fontTools.ttLib import newTable
    avar = newTable('avar'); avar.segments = {a.axisTag: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for a in vf['fvar'].axes}
    vf['avar'] = avar
    import gf_post; gf_post.windows_names(vf)
    vf.save(out)
    import gf_post; gf_post.hmetrics3(out)
    w = TTFont(out); w.flavor = 'woff2'; w.save(out[:-4] + '.woff2')
    print('wrote', out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
