"""Variable ProxyMono from the nine static masters. Usage: vf.py <masters dir> <out.ttf>
Masters must be built with VF=1 (no per-weight outline offsetting) so they are point-compatible. A glyph
that still differs in one master (the M at 900, whose V points meet) is rebuilt in that master by
extrapolating its two nearest compatible neighbours by stem."""
import sys, os
from fontTools.ttLib import TTFont
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from fontTools import varLib

STYLES = ['Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black']
STEMS = [46, 68, 96, 110, 126, 144, 162, 180, 197]

def sig(f, g):
    gl = f['glyf'][g]
    if not gl.numberOfContours: return ()
    c, e, fl = gl.getCoordinates(f['glyf'])
    return (tuple(e), tuple(x & 1 for x in fl))

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
    ds = DesignSpaceDocument()
    ax = AxisDescriptor(); ax.tag = 'wght'; ax.name = 'Weight'; ax.minimum = 100; ax.default = 400; ax.maximum = 900
    ds.addAxis(ax)
    for i, f in enumerate(F):
        sd = SourceDescriptor(); sd.font = f; sd.name = STYLES[i]; sd.location = {'Weight': (i + 1) * 100}
        sd.filename = paths[i]; ds.addSource(sd)
    vf, _, _ = varLib.build(ds, exclude=['MVAR'])
    # names: one family, "Regular" default, STAT for the named weights
    name = vf['name']
    for rec in list(name.names):
        if rec.nameID in (16, 17): name.removeNames(nameID=rec.nameID)
    name.setName('Proxy Mono', 1, 3, 1, 0x409); name.setName('Regular', 2, 3, 1, 0x409)
    name.setName('Proxy Mono Regular', 4, 3, 1, 0x409); name.setName('ProxyMono-Regular', 6, 3, 1, 0x409)
    name.setName('1.000;MNPX;ProxyMono[wght]', 3, 3, 1, 0x409)
    from fontTools.varLib.instancer.names import updateNameTable  # noqa: F401 (ensures names module is present)
    from fontTools.otlLib.builder import buildStatTable
    fvar = vf['fvar']
    fvar.instances = []
    from fontTools.ttLib.tables._f_v_a_r import NamedInstance
    for i, s in enumerate(STYLES):
        ni = NamedInstance(); ni.coordinates = {'wght': (i + 1) * 100}
        ni.subfamilyNameID = name.addMultilingualName({'en': s}, mac=False)
        ni.postscriptNameID = name.addMultilingualName({'en': f'ProxyMono-{s}'}, mac=False)
        fvar.instances.append(ni)
    buildStatTable(vf, [{'tag': 'wght', 'name': 'Weight', 'values': [
        {'value': (i + 1) * 100, 'name': s, **({'flags': 2, 'linkedValue': 700} if s == 'Regular' else {})}
        for i, s in enumerate(STYLES)]}])
    vf['OS/2'].usWeightClass = 400; vf['OS/2'].fsSelection = (1 << 7) | (1 << 6); vf['head'].macStyle = 0
    vf.save(out)
    w = TTFont(out); w.flavor = 'woff2'; w.save(out[:-4] + '.woff2')
    print('wrote', out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
