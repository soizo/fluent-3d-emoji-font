import io
import json
from pathlib import Path

import pytest
from PIL import Image

from fluent_font.sources import candidate_inventory, emoji_data, image_info, key
from fluent_font.font import mappings, build, validate
from fluent_font.cli import approved_candidates


def record(path, color):
    im = Image.new('RGBA', (64, 64), color)
    im.save(path)
    return dict(path=str(path), **image_info(path.read_bytes()))


def test_roundtrip_complex_sequences_and_lossless_images(tmp_path):
    sequences = ['1f600', '1f469-1f3fb-200d-1f4bb', '1f1e8-1f1f3',
                 '0031-fe0f-20e3', '2764-fe0f', '1f3f4-e0067-e0062-e0065-e006e-e0067-e007f']
    records = {k: record(tmp_path / f'{i}.png', (i*30, 100, 180, 255)) for i, k in enumerate(sequences)}
    entries = {tuple(int(c,16) for c in k.split('-')): 'fully-qualified' for k in sequences}
    entries[(0x31, 0x20e3)] = 'unqualified'
    entries[(0x2764,)] = 'unqualified'
    aliases = mappings(records, entries)
    paths = build(records, aliases, tmp_path / 'fonts', 'test')
    assert validate(paths, records, aliases) == len(paths) * len(aliases)
    from fontTools.ttLib import TTFont
    with TTFont(paths[0]) as font:
        assert 'Permission is hereby granted' in font['name'].getDebugName(13)
        assert 'Microsoft Corporation' in font['name'].getDebugName(13)
    first = [p.read_bytes() for p in paths]
    assert [p.read_bytes() for p in build(records, aliases, tmp_path / 'fonts2', 'test')] == first


def test_unicode_parser():
    version, entries = emoji_data('# Version: 17.0\n1F469 1F3FB 200D 1F4BB ; fully-qualified # 👩🏻‍💻\n')
    assert version == '17.0'
    assert list(entries)[0] == (0x1f469, 0x1f3fb, 0x200d, 0x1f4bb)
    with pytest.raises(ValueError):
        emoji_data('Access denied')


def payload(images):
    return {'data': {'vendorHistoric_v1': [{'slug': 'old', 'date': 1}, {'slug': 'new', 'date': 2}],
                     'vendorHistoricEmoji_v1': {'items': [{'images': images}]}}}


def item(source):
    return {'slug': 'test', 'status': 'NEW', 'image': {'source': source}}


def test_version_discovery_and_conflict():
    source = 'source/microsoft-3D-fluent/999/new-name_1f469-1f3fb-200d-1f4bb.png'
    data = candidate_inventory(payload([item(source)]))
    assert data['release']['slug'] == 'new'
    assert data['asset_set_ids'] == ['999']
    assert '1f469-1f3fb-200d-1f4bb' in data['records']
    with pytest.raises(ValueError, match='Conflicting'):
        candidate_inventory(payload([item(source), item(source.replace('new-name', 'other'))]))
    with pytest.raises(ValueError):
        candidate_inventory(payload([item('source/other/1/name_1f600.png')]))


def test_rights_gate_does_not_download_unapproved(tmp_path):
    assert approved_candidates({'1faea': {'url': 'https://invalid.example/'}}, [], tmp_path) == {}
    with pytest.raises(ValueError, match='no longer matches'):
        approved_candidates({}, [{'sequence': '1faea', 'url': 'https://invalid.example/'}], tmp_path)


def test_mixed_resolutions_rejected(tmp_path):
    a = record(tmp_path / 'a.png', (0, 1, 2, 255))
    Image.new('RGBA', (128, 128), 'red').save(tmp_path / 'b.png')
    b = dict(path=str(tmp_path / 'b.png'), **image_info((tmp_path / 'b.png').read_bytes()))
    records = {'1f600': a, '1f601': b}
    with pytest.raises(ValueError, match='Mixed source resolutions'):
        build(records, mappings(records, {}), tmp_path / 'out', 'test')


def test_repeated_skin_tone_suffix_needs_independent_code():
    source = 'source/microsoft-3D-fluent/999/waving-hand_light-skin-tone_1f44b-1f3fb_1f3fb.png'
    data = payload([item(source)])
    with pytest.raises(ValueError, match='independent'):
        candidate_inventory(data)
    assert '1f44b-1f3fb' in candidate_inventory(data, {'test': '👋🏻'})['records']
    with pytest.raises(ValueError, match='disagree'):
        candidate_inventory(data, {'test': '🏻'})


def test_linear_strike_matches_fonttools():
    from fontTools.ttLib.tables.sbixStrike import Strike
    from fontTools.ttLib.tables.sbixGlyph import Glyph
    from fluent_font.font import LinearStrike
    class Font:
        def getGlyphOrder(self):
            return ['.notdef', 'a', 'b']
        def getGlyphID(self, name):
            return self.getGlyphOrder().index(name)
    reference = Strike(ppem=64, resolution=72)
    linear = LinearStrike(ppem=64, resolution=72)
    for strike in [reference, linear]:
        strike.glyphs['a'] = Glyph(glyphName='a', graphicType='png ', imageData=b'fixture',
                                  originOffsetX=0, originOffsetY=-12)
        strike.compile(Font())
    assert reference.data == linear.data


def test_discover_selects_latest_dated_release(monkeypatch):
    import fluent_font.sources as sources
    p = payload([item('source/microsoft-3D-fluent/1001/test_1f600.png')])
    calls = []
    class Response:
        def __init__(self, data):
            self.data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self.data
    def post(url, json, timeout):
        calls.append(json)
        if json['operationName'] == 'Resolve':
            return Response({'data': {'e0': {'code': '😀'}}})
        return Response(p)
    monkeypatch.setattr(sources.SESSION, 'post', post)
    monkeypatch.setattr(sources.time, 'sleep', lambda seconds: None)
    result = sources.discover()
    assert calls[0]['variables']['version'] is None
    assert calls[1]['variables']['version'] == 'new'
    assert result['asset_set_ids'] == ['1001']
