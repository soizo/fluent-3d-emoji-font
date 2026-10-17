import io
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from fluent_font.sources import candidate_inventory, emoji_data, image_info, key
from fluent_font.font import mappings, build, validate
from fluent_font.cli import validate_approvals


def record(path, color, size=64):
    im = Image.new('RGBA', (size, size), color)
    im.save(path)
    return dict(path=str(path), **image_info(path.read_bytes()))


def test_roundtrip_complex_sequences_and_lossless_images(tmp_path):
    sequences = ['1f600', '1faea', '1f31a', '1f469-1f3fb-200d-1f4bb', '1f1e8-1f1f3',
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
        for name in [f'u{c:X}' for c in [0x1f600]]:
            glyph = font['glyf'][name]
            assert glyph.xMax > glyph.xMin and glyph.yMax > glyph.yMin
    with TTFont(paths[2]) as svg:
        assert svg['name'].getDebugName(1) == 'Fluent 3D Community SVG'
        assert svg['name'].getDebugName(6) == 'Fluent3DCommunity04SVG-Regular'
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
    assert validate_approvals({'1faea': {'url': 'https://invalid.example/'}}, []) == {}
    with pytest.raises(ValueError, match='no longer matches'):
        validate_approvals({}, [{'sequence': '1faea', 'url': 'https://invalid.example/'}])


def test_mixed_resolutions_rejected(tmp_path):
    a = record(tmp_path / 'a.png', (0, 1, 2, 255))
    Image.new('RGBA', (128, 128), 'red').save(tmp_path / 'b.png')
    b = dict(path=str(tmp_path / 'b.png'), **image_info((tmp_path / 'b.png').read_bytes()))
    records = {'1f600': a, '1f601': b}
    with pytest.raises(ValueError, match='Mixed source resolutions'):
        build(records, mappings(records, {}), tmp_path / 'out', 'test')


def test_tall_artwork_bounds_and_bitmap_origin(tmp_path):
    from fontTools.ttLib import TTFont
    path = tmp_path / 'tall.png'
    Image.new('RGBA', (256, 264), 'red').save(path)
    records = {'1f600': dict(path=str(path), **image_info(path.read_bytes()))}
    aliases = mappings(records, {})
    paths = build(records, aliases, tmp_path / 'fonts', 'tall')
    assert validate(paths, records, aliases) == 4
    with TTFont(paths[0]) as font:
        glyph = font['glyf']['u1F600']
        assert (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax) == (0, -208, 1024, 848)
        bitmap = font['sbix'].strikes[256].glyphs['u1F600']
        assert (bitmap.originOffsetX, bitmap.originOffsetY) == (0, 0)


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


def test_image_audit_revalidates_without_publishing_png_cache(tmp_path, monkeypatch):
    import fluent_font.sources as sources
    raw = tmp_path / 'fixture.png'
    Image.new('RGBA', (64, 64), 'purple').save(raw)
    catalogue = {'records': {'1faea': {'url': 'https://example.invalid/distorted.png',
                                     'source': 'emojipedia', 'rights': 'unverified'}}}
    calls = []
    def get(url, headers):
        calls.append(headers)
        return SimpleNamespace(status_code=304 if headers else 200,
                               content=b'' if headers else raw.read_bytes(),
                               headers={'ETag': '"fixture-v1"'})
    monkeypatch.setattr(sources, 'get', get)
    cache = tmp_path / 'cache'
    first = sources.download_catalogue(catalogue, cache, workers=1, audit_only=True)
    assert not list(cache.glob('*.png'))
    second = sources.download_catalogue(catalogue, cache, workers=1, audit_only=True)
    assert second['1faea']['sha256'] == first['1faea']['sha256']
    assert calls == [{}, {'If-None-Match': '"fixture-v1"'}]


def test_unchanged_url_can_have_new_artwork(tmp_path, monkeypatch):
    import fluent_font.sources as sources
    a = tmp_path / 'a.png'; b = tmp_path / 'b.png'
    Image.new('RGBA', (64, 64), 'red').save(a)
    Image.new('RGBA', (64, 64), 'blue').save(b)
    catalogue = {'records': {'1f31a': {'url': 'https://example.invalid/moon.png',
                                     'source': 'emojipedia', 'rights': 'unverified'}}}
    responses = iter([a.read_bytes(), b.read_bytes()])
    monkeypatch.setattr(sources, 'get', lambda *args, **kwargs:
                        SimpleNamespace(status_code=200, content=next(responses), headers={}))
    first = sources.download_catalogue(catalogue, tmp_path / 'cache', workers=1)
    second = sources.download_catalogue(catalogue, tmp_path / 'cache', workers=1)
    assert first['1f31a']['sha256'] != second['1f31a']['sha256']
    assert first['1f31a']['url'] == second['1f31a']['url']


@pytest.mark.parametrize('allow_local', [False, True])
@pytest.mark.parametrize('crop_size', [473, 440])
def test_emojipedia_is_the_only_font_source_and_rights_gate_is_separate(tmp_path, monkeypatch, allow_local, crop_size):
    import fluent_font.cli as cli
    monkeypatch.delenv('GITHUB_OUTPUT', raising=False)
    records = {k: dict(record(tmp_path / f'{k}.png', c, size=512), sequence=k,
                       source='emojipedia', rights='unverified',
                       url=f'https://example.invalid/{k}.png')
               for k, c in [('1f31a', 'purple'), ('1faea', 'orange')]}
    candidates = {'release': {'title': 'New release', 'slug': 'new', 'date': 1},
                  'asset_set_ids': ['999'],
                  'records': {k: {a: b for a, b in r.items() if a in ['sequence', 'url', 'source', 'rights']}
                              for k, r in records.items()}}
    monkeypatch.setattr(cli, 'discover', lambda: candidates)
    monkeypatch.setattr(cli, 'get', lambda url: SimpleNamespace(content=(
        '# Version: 18.0\n1F31A ; fully-qualified # moon\n1FAEA ; fully-qualified # distorted\n').encode()))
    monkeypatch.setattr(cli, 'download_catalogue', lambda *args, **kwargs: records)
    out = tmp_path / 'out'
    cli.run(Namespace(output=str(out), cache=str(tmp_path / 'cache'),
                      approvals='licenses/approvals.json', allow_unverified_local=allow_local, crop_size=crop_size))
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['selected_source'] == 'emojipedia'
    assert not manifest['publishable']
    assert all(r['source'] == 'emojipedia' for r in manifest['source_records'].values())
    if allow_local:
        assert manifest['shaping_checks_passed'] == 8
        assert manifest['artwork_count'] == 2
        assert all(r['width'] == crop_size and r['height'] == crop_size
                   for r in manifest['embedded_records'].values())
        assert (out / 'NOT-FOR-REDISTRIBUTION.txt').exists()
        from fontTools.ttLib import TTFont
        suffix = '-440' if crop_size == 440 else ''
        with TTFont(out / f'Fluent3D-sbix{suffix}.ttf') as font:
            licence = font['name'].getDebugName(13)
            assert 'RIGHTS UNVERIFIED' in licence
            assert font['OS/2'].fsType == 2
            assert font['name'].getDebugName(1) == 'Fluent 3D Community' + (' 440' if suffix else '')
            assert list(font['sbix'].strikes) == [crop_size]
        if crop_size == 440:
            companion = tmp_path / 'companion'
            cli.run(Namespace(output=str(companion), cache=str(tmp_path / 'cache'),
                              approvals='licenses/approvals.json', allow_unverified_local=True,
                              crop_size=440, source_manifest=str(out / 'manifest.json')))
            assert json.loads((companion / 'manifest.json').read_text())['parent_content_id'] == manifest['content_id']
            records['1faea']['sha256'] = '0' * 64
            with pytest.raises(ValueError, match='source differs'):
                cli.run(Namespace(output=str(tmp_path / 'changed'), cache=str(tmp_path / 'cache'),
                                  approvals='licenses/approvals.json', allow_unverified_local=True,
                                  crop_size=440, source_manifest=str(out / 'manifest.json')))
    else:
        assert manifest['build_status'] == 'rights_pending'
        assert manifest['artwork_count'] == 0
        assert not list(out.glob('*.ttf'))


@pytest.mark.parametrize('size,inset', [(473, 19), (440, 36)])
def test_centre_crop_preserves_exact_pixels_and_original(tmp_path, size, inset):
    from fluent_font.artwork import centre_crop
    image = Image.new('RGBA', (512, 512))
    image.putdata([(x % 256, y % 256, (x + y) % 256, 255)
                   for y in range(512) for x in range(512)])
    path = tmp_path / 'source.png'
    image.save(path)
    original = path.read_bytes()
    source = dict(path=str(path), **image_info(original))
    result = centre_crop({'1faea': source}, tmp_path / 'cropped', size=size)['1faea']
    with Image.open(result['path']) as actual:
        assert actual.size == (size, size)
        assert actual.tobytes() == image.crop((inset, inset, inset + size, inset + size)).tobytes()
    assert path.read_bytes() == original
    assert source['width'] == 512
