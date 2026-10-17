"""Source adapters. Never infer redistribution permission from a CDN URL."""
import hashlib
import io
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

VENDOR = "microsoft-3D-fluent"
GRAPHQL = "https://emojipedia.org/api/graphql"
QUERY = """query Inventory($slug: Slug!, $version: Slug) {
 vendorHistoricEmoji_v1(slug:$slug, version:$version) {
  items { images { slug image { source useOriginalImage } status } } statuses
 }
 vendorHistoric_v1(slug:$slug) { slug title date }
}"""
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'Fluent3DFontSourceMonitor/0.1 (+https://github.com/soizo/fluent-3d-emoji-font)'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def get(url, **kwargs):
    for attempt in range(4):
        try:
            response = SESSION.get(url, timeout=(15, 120), **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def sequence(value):
    seq = tuple(int(x, 16) for x in value.replace('-', ' ').split())
    if not seq or any(c > 0x10FFFF or 0xD800 <= c <= 0xDFFF for c in seq):
        raise ValueError(f'Invalid Unicode sequence: {value}')
    return seq


def key(seq):
    return '-'.join(f'{c:04x}' for c in seq)


def emoji_data(text):
    version = re.search(r'^# Version:\s*(\S+)', text, re.M)
    if not version:
        raise ValueError('Unicode version header missing')
    entries = {}
    for line in text.splitlines():
        match = re.match(r'^([0-9A-F ]+)\s*;\s*([a-z-]+)\s*#', line)
        if match:
            entries[sequence(match[1])] = match[2]
    if not entries:
        raise ValueError('Empty Unicode inventory')
    return version[1], entries


def candidate_inventory(payload, codes=None):
    if payload.get('errors'):
        raise ValueError(f'Emojipedia GraphQL errors: {payload["errors"]}')
    data = payload['data']
    releases = data['vendorHistoric_v1']
    if not releases:
        raise ValueError('No vendor releases; refusing stale fallback')
    latest = max(releases, key=lambda r: r['date'])
    records = {}
    for group in data['vendorHistoricEmoji_v1']['items']:
        for item in group['images']:
            if item['status'] == 'REMOVED':
                continue
            source = (item.get('image') or {}).get('source', '')
            match = re.fullmatch(r'source/microsoft-3D-fluent/(\d+)/[^/]+?_([0-9a-fA-F-]+)((?:_[0-9a-fA-F-]+)*)\.png', source)
            if not match:
                raise ValueError(f'Unexpected candidate image path: {source}')
            parsed = sequence(match[2])
            if match[3] and codes is None:
                raise ValueError('Ambiguous filename requires independent emoji code lookup')
            if codes is not None:
                resolved = tuple(map(ord, codes[item['slug']]))
                if parsed != resolved:
                    raise ValueError(f'Filename and emoji code disagree: {source}')
            seq = key(parsed)
            record = dict(sequence=seq, url='https://em-content.zobj.net/' + source,
                          asset_set_id=match[1], slug=item['slug'], status=item['status'],
                          rights='unverified', source='emojipedia')
            if seq in records and records[seq]['url'] != record['url']:
                raise ValueError(f'Conflicting candidate mapping: {seq}')
            records[seq] = record
    if not records:
        raise ValueError('Empty candidate inventory')
    return {'release': latest, 'asset_set_ids': sorted({r['asset_set_id'] for r in records.values()}),
            'records': records}


def discover():
    # The frontend uses version=null for the current full vendor inventory.
    # Explicit historical release paths may contain legacy filename anomalies.
    def query(version):
        response = SESSION.post(GRAPHQL, json={'operationName': 'Inventory', 'query': QUERY,
                                'variables': {'slug': VENDOR, 'version': version}}, timeout=(15, 120))
        response.raise_for_status()
        data = response.json()
        if data.get('errors'):
            raise ValueError(data['errors'])
        return data
    first = query(None)
    # Verify filename mappings against independent emoji.code, including legacy
    # names with a duplicated skin-tone suffix. No inference from English slugs.
    slugs = sorted({i['slug'] for g in first['data']['vendorHistoricEmoji_v1']['items']
                    for i in g['images'] if i['status'] != 'REMOVED'})
    codes = {}
    for start in range(0, len(slugs), 100):
        batch = slugs[start:start+100]
        fields = ' '.join(f'e{i}:emoji_v1(slug:{json.dumps(slug)}) {{ code }}'
                          for i, slug in enumerate(batch))
        response = SESSION.post(GRAPHQL, json={'operationName': 'Resolve',
                                'query': 'query Resolve {' + fields + '}'}, timeout=(15, 120))
        response.raise_for_status()
        data = response.json()
        if data.get('errors'):
            raise ValueError(data['errors'])
        for i, slug in enumerate(batch):
            code = data['data'][f'e{i}']['code']
            if not code:
                raise ValueError(f'Empty emoji code: {slug}')
            codes[slug] = code
        time.sleep(0.2)
    return candidate_inventory(first, codes)


def image_info(data):
    with Image.open(io.BytesIO(data)) as im:
        if im.format != 'PNG' or im.width < 32 or im.height < 32 or im.height > im.width * 2:
            raise ValueError('Expected valid original PNG >=32px')
        im.verify()
    with Image.open(io.BytesIO(data)) as im:
        rgba = im.convert('RGBA')
        if rgba.getextrema()[3] == (0, 0):
            raise ValueError('Fully transparent image')
        return {'width': im.width, 'height': im.height, 'sha256': digest(data),
                'pixel_sha256': digest(rgba.tobytes())}


def official_inventory(root):
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True)
    if dirty:
        raise ValueError('Official upstream checkout must be clean')
    license_data = (root / 'LICENSE').read_bytes()
    # Require the reviewed upstream license, including its copyright notice.
    reviewed = Path('licenses/Microsoft-MIT.txt').read_bytes()
    if license_data != reviewed:
        raise ValueError('Upstream license changed; review required')
    tones = ['Default', 'Light', 'Medium-Light', 'Medium', 'Medium-Dark', 'Dark']
    records = {}
    for meta_path in sorted((root / 'assets').glob('*/metadata.json')):
        meta = json.loads(meta_path.read_text())
        paths = sorted(meta_path.parent.glob('**/3D/*.png'))
        expected = meta.get('unicodeSkintones')
        if len(paths) != (6 if expected else 1):
            raise ValueError(f'Unexpected asset layout: {meta_path}')
        for path in paths:
            value = expected[tones.index(path.parent.parent.name)] if expected else meta['unicode']
            seq = key(sequence(value))
            if seq in records:
                raise ValueError(f'Duplicate official sequence: {seq}')
            raw = path.read_bytes()
            info = image_info(raw)
            rel = path.relative_to(root).as_posix()
            records[seq] = dict(sequence=seq, source='microsoft-git', rights='MIT', path=str(path),
                                url=f'https://raw.githubusercontent.com/microsoft/fluentui-emoji/{commit}/{quote(rel)}',
                                upstream_commit=commit, **info)
    if not records:
        raise ValueError('No official assets')
    return commit, records
