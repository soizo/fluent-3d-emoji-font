"""Lossless PNG sbix and OpenType-SVG fonts with explicitly tested sequences."""
import base64
import io
import struct
from collections import defaultdict
from pathlib import Path

import uharfbuzz as hb
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable, woff2
from fontTools.ttLib.tables.sbixGlyph import Glyph
from fontTools.ttLib.tables.sbixStrike import Strike
from fontTools.ttLib.tables.S_V_G_ import SVGDocument

from .sources import sequence, key, image_info


class LinearStrike(Strike):
    """fontTools-compatible sbix strike without quadratic bitmap concatenation."""
    def compile(self, ttFont):
        order = ttFont.getGlyphOrder()
        offset = 4 + 4 * (len(order) + 1)
        offsets, chunks = [], []
        for name in order:
            glyph = self.glyphs.get(name, Glyph(glyphName=name))
            glyph.compile(ttFont)
            glyph.glyphDataOffset = offset
            offsets.append(offset)
            chunks.append(glyph.rawdata)
            offset += len(glyph.rawdata)
        offsets.append(offset)
        self.data = (struct.pack('>HH', self.ppem, self.resolution)
                     + struct.pack('>' + 'I' * len(offsets), *offsets)
                     + b''.join(chunks))


def save_font(font, path):
    if font.flavor != 'woff2':
        font.save(path)
        return
    # fontTools 4.60.1 has no WOFF2 quality parameter. Scope the adapter to
    # this single-threaded save, preserving all other Brotli API operations.
    # Quality 5 is still lossless; PNG data gains little from quality 11.
    previous = woff2.brotli
    class FastLosslessBrotli:
        def __getattr__(self, name):
            return getattr(previous, name)
        def compress(self, data, **kwargs):
            return previous.compress(data, quality=5, **kwargs)
    try:
        woff2.brotli = FastLosslessBrotli()
        font.save(path)
    finally:
        woff2.brotli = previous


def glyph_name(seq):
    return 'u' + '_'.join(f'{c:X}' for c in seq)


def bitmap_bounds(record):
    """Design-space bounds matching the PNG's original pixel-space placement."""
    size = record['width']
    bottom = -round(size * 192 / 1024) - (record['height'] - size) // 2
    return (0, round(bottom * 1024 / size), 1024,
            round((bottom + record['height']) * 1024 / size))


def bounds_glyph(bounds):
    # A two-point closed contour has a real bounding box but no filled area.
    # Skia/CoreText otherwise discards empty glyf glyphs before drawing sbix.
    # Avoid a filled rectangle, which would obscure artwork in outline renderers.
    x_min, y_min, x_max, y_max = bounds
    pen = TTGlyphPen(None)
    pen.moveTo((x_min, y_min))
    pen.lineTo((x_max, y_max))
    pen.closePath()
    return pen.glyph()


def set_format_names(font, identity, svg=False):
    family = 'Fluent 3D Community' + (' SVG' if svg else '')
    ps_name = 'Fluent3DCommunity' + ('SVG' if svg else '') + '-Regular'
    names = {1: family, 3: identity + (';svg' if svg else ';sbix'),
             4: family + ' Regular', 6: ps_name}
    for record in font['name'].names:
        if record.nameID in names:
            record.string = names[record.nameID].encode(record.getEncoding())


def mappings(records, unicode_entries):
    result = {sequence(k): k for k in records}
    # Only Unicode-listed qualified/unqualified spellings of the same sequence.
    normalized = defaultdict(set)
    for seq, target in result.items():
        normalized[tuple(c for c in seq if c != 0xFE0F)].add(target)
    for seq in unicode_entries:
        if seq not in result:
            options = normalized.get(tuple(c for c in seq if c != 0xFE0F), set())
            if len(options) == 1:
                result[seq] = next(iter(options))
    return result


def base_font(records, aliases, identity):
    components = {c for seq in aliases for c in seq}
    targets = {k: glyph_name(sequence(k)) for k in records}
    cmap = {c: targets[aliases[(c,)]] if (c,) in aliases else f'c{c:X}' for c in components}
    order = ['.notdef'] + sorted(set(cmap.values()) | set(targets.values()))
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    glyphs = {g: TTGlyphPen(None).glyph() for g in order}
    glyphs.update({targets[k]: bounds_glyph(bitmap_bounds(record)) for k, record in records.items()})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({g: (1024 if g in targets.values() else 0, 0) for g in order})
    builder.setupHorizontalHeader(ascent=848, descent=-208)
    builder.setupNameTable({'familyName': 'Fluent 3D Community', 'styleName': 'Regular',
                            'uniqueFontIdentifier': identity,
                            'fullName': 'Fluent 3D Community Regular',
                            'psName': 'Fluent3DCommunity-Regular', 'version': 'Version 0.200',
                            'copyright': 'Artwork: Microsoft Corporation; see bundled source and license notices.',
                            'licenseDescription': '\n\n'.join(p.read_text() for p in sorted(Path('licenses').iterdir())
                                if p.is_file() and p.suffix != '.json')})
    builder.setupOS2(sTypoAscender=848, sTypoDescender=-208, usWinAscent=848,
                    usWinDescent=208, fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    font = builder.font
    font['head'].fontRevision = 0.2
    set_format_names(font, identity)
    font['head'].created = font['head'].modified = 2082844800  # 1970; reproducible builds
    font.recalcTimestamp = False
    rules = []
    for seq in sorted(aliases, key=lambda s: (-len(s), s)):
        if len(seq) > 1:
            rules.append('sub ' + ' '.join(cmap[c] for c in seq) + ' by ' + targets[aliases[seq]] + ';')
    if rules:
        addOpenTypeFeaturesFromString(font, 'languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n'
                                     'feature rlig {\n' + '\n'.join(rules) + '\n} rlig;')
    return font, targets


def build(records, aliases, output, identity):
    output.mkdir(parents=True, exist_ok=True)
    font, targets = base_font(records, aliases, identity)
    sbix = newTable('sbix')
    sbix.version = 1
    sbix.flags = 1
    sbix.strikes = {}
    for k, record in records.items():
        raw = Path(record['path']).read_bytes()
        info = image_info(raw)
        if info['sha256'] != record['sha256']:
            raise ValueError(f'Asset changed after inventory: {k}')
        size = info['width']
        if size not in sbix.strikes:
            sbix.strikes[size] = LinearStrike(ppem=size, resolution=72)
        sbix.strikes[size].glyphs[targets[k]] = Glyph(glyphName=targets[k], graphicType='png ',
                # With a glyf contour, sbix offsets are relative to its lower
                # left corner. That corner already includes baseline placement.
                originOffsetX=0, originOffsetY=0, imageData=raw)
    # Every strike must contain every emoji, never silently drop differently sized assets.
    if len(sbix.strikes) != 1:
        raise ValueError('Mixed source resolutions require explicit strike design; no implicit resampling')
    font['sbix'] = sbix
    paths = []
    for flavor, suffix in [(None, 'ttf'), ('woff2', 'woff2')]:
        font.flavor = flavor
        path = output / f'Fluent3D-sbix.{suffix}'
        save_font(font, path)
        paths.append(path)
    font.flavor = None
    del font['sbix']
    set_format_names(font, identity, svg=True)
    svg = newTable('SVG ')
    svg.docList = []
    for k, record in records.items():
        gid = font.getGlyphID(targets[k])
        encoded = base64.b64encode(Path(record['path']).read_bytes()).decode()
        height = record['height'] * 1024 / record['width']
        y = -832 - (height-1024)/2
        doc = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
               f'<g id="glyph{gid}"><image x="0" y="{y:g}" width="1024" height="{height:g}" '
               f'xlink:href="data:image/png;base64,{encoded}"/></g></svg>')
        svg.docList.append(SVGDocument(doc, gid, gid, compressed=True))
    font['SVG '] = svg
    for flavor, suffix in [(None, 'ttf'), ('woff2', 'woff2')]:
        font.flavor = flavor
        path = output / f'Fluent3D-svg.{suffix}'
        save_font(font, path)
        paths.append(path)
    return paths


def validate(paths, records, aliases):
    checked = 0
    for path in paths:
        font = TTFont(path, recalcTimestamp=False)
        for k, record in records.items():
            glyph = font['glyf'][glyph_name(sequence(k))]
            actual_bounds = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
            if actual_bounds != bitmap_bounds(record):
                raise ValueError(f'Empty or incorrect rendering bounds: {k}: {actual_bounds}')
        font.flavor = None
        buf = io.BytesIO()
        font.save(buf)
        face = hb.Face(buf.getvalue())
        shaper = hb.Font(face)
        for seq, target in aliases.items():
            buffer = hb.Buffer()
            buffer.add_str(''.join(map(chr, seq)))
            buffer.guess_segment_properties()
            hb.shape(shaper, buffer)
            actual = [i.codepoint for i in buffer.glyph_infos]
            expected = [font.getGlyphID(glyph_name(sequence(target)))]
            if actual != expected:
                raise ValueError(f'Shaping failed in {path.name}: {key(seq)} -> {actual}, expected {expected}')
            checked += 1
        if 'sbix' in font:
            for k, record in records.items():
                glyph = glyph_name(sequence(k))
                found = [s.glyphs[glyph].imageData for s in font['sbix'].strikes.values()
                         if glyph in s.glyphs and s.glyphs[glyph].imageData]
                if found != [Path(record['path']).read_bytes()]:
                    raise ValueError(f'PNG bytes changed: {k}')
        if 'SVG ' in font:
            import re
            docs = {doc.startGlyphID: doc for doc in font['SVG '].docList}
            for k, record in records.items():
                gid = font.getGlyphID(glyph_name(sequence(k)))
                encoded = re.search('base64,([^" ]+)', docs[gid].data)[1]
                if base64.b64decode(encoded) != Path(record['path']).read_bytes():
                    raise ValueError(f'SVG PNG bytes changed: {k}')
        font.close()
    return checked
