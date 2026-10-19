"""Width and weight variable font: wdth 100 to 150, wght 100 to 900.

    python3 vf_wdth.py <wide masters dir> <out.ttf>

The width-100 masters are the weight variable font itself (build/variable), instanced at each named
weight, so width 100 is exactly the weight font. Names, named instances (weights, at width 100), STAT
(weights; widths Normal / SemiExpanded / Expanded / ExtraExpanded, as Google's axis registry names
them) and avar follow vf.py, then the Google Fonts post-pass. The width-150 masters are ProxyMono-W150-<weight>.ttf in the given folder,
made by wdth.py then wide.py. Every glyph must have the same structure in all 18; any that do not are
listed and the build stops.
"""
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib import build
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor

VF = '../../build/variable/ProxyMono[wght].ttf'      # the weight font, built first (see Makefile)
WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900]


def sig(f, g):
    gl = f['glyf'][g]
    if gl.isComposite(): return ('composite', tuple(c.glyphName for c in gl.components))
    if gl.numberOfContours <= 0: return ('empty',)
    return (tuple(gl.endPtsOfContours), tuple(x & 1 for x in gl.flags))


def main(wide_dir, out):
    narrow = {w: instantiateVariableFont(TTFont(VF), {'wght': w}) for w in WEIGHTS}
    wide = {w: TTFont(f'{wide_dir}/ProxyMono-W150-{w}.ttf') for w in WEIGHTS}
    ref = narrow[400]; bad = {}
    for g in ref.getGlyphOrder():
        want = sig(ref, g)
        for label, fonts in (('100', narrow), ('150', wide)):
            for w, f in fonts.items():
                if sig(f, g) != want: bad.setdefault(g, []).append(f'{label}/{w}')
    if bad:
        for g, where in bad.items(): print(f'{g}: differs at {", ".join(where)}')
        raise SystemExit(f'{len(bad)} glyphs differ in structure; not building')
    ds = DesignSpaceDocument()
    for tag, name, lo, df, hi in (('wght', 'Weight', 100, 400, 900), ('wdth', 'Width', 100, 100, 150)):
        ax = AxisDescriptor(); ax.tag, ax.name, ax.minimum, ax.default, ax.maximum = tag, name, lo, df, hi
        ds.addAxis(ax)
    for w in WEIGHTS:
        for wd, f in ((100, narrow[w]), (150, wide[w])):
            sd = SourceDescriptor(); sd.font = f; sd.name = f'w{w}-d{wd}'
            sd.location = {'Weight': w, 'Width': wd}; ds.addSource(sd)
    vf, _, _ = build(ds, exclude=['MVAR'])
    vf['post'].italicAngle = 0
    name = vf['name']
    for rec in list(name.names):
        if rec.nameID in (16, 17): name.removeNames(nameID=rec.nameID)
    name.setName('Proxy Mono', 1, 3, 1, 0x409); name.setName('Regular', 2, 3, 1, 0x409)
    name.setName('Proxy Mono Regular', 4, 3, 1, 0x409); name.setName('ProxyMono-Regular', 6, 3, 1, 0x409)
    name.setName('1.000;MNPX;ProxyMono[wdth,wght]', 3, 3, 1, 0x409)
    from fontTools.otlLib.builder import buildStatTable
    from fontTools.ttLib.tables._f_v_a_r import NamedInstance
    from fontTools.ttLib import newTable
    STYLES = ['Thin', 'ExtraLight', 'Light', 'Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold', 'Black']
    fvar = vf['fvar']; fvar.instances = []
    for w, st in zip(WEIGHTS, STYLES):                     # named instances: weights only, at width 100
        ni = NamedInstance(); ni.coordinates = {'wght': w, 'wdth': 100}
        ni.subfamilyNameID = name.addMultilingualName({'en': st}, mac=False)
        ni.postscriptNameID = name.addMultilingualName({'en': f'ProxyMono-{st}'}, mac=False)
        fvar.instances.append(ni)
    buildStatTable(vf, [
        {'tag': 'wght', 'name': 'Weight', 'values': [
            {'value': w, 'name': st, **({'flags': 2, 'linkedValue': 700} if st == 'Regular' else {})}
            for w, st in zip(WEIGHTS, STYLES)]},
        {'tag': 'wdth', 'name': 'Width', 'values': [
            {'value': 100, 'name': 'Normal', 'flags': 2}, {'value': 112.5, 'name': 'SemiExpanded'},
            {'value': 125, 'name': 'Expanded'}, {'value': 150, 'name': 'ExtraExpanded'}]}])
    vf['OS/2'].usWeightClass = 400; vf['OS/2'].usWidthClass = 5
    vf['OS/2'].fsSelection = (1 << 8) | (1 << 7) | (1 << 6); vf['head'].macStyle = 0
    avar = newTable('avar'); avar.segments = {a.axisTag: {-1.0: -1.0, 0.0: 0.0, 1.0: 1.0} for a in fvar.axes}
    vf['avar'] = avar
    import gf_post; gf_post.windows_names(vf)
    vf.save(out)
    gf_post.hmetrics3(out)
    w2 = TTFont(out); w2.flavor = 'woff2'; w2.save(out[:-4] + '.woff2')
    print('built', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
