"""Source adapters. Never infer redistribution permission from a CDN URL."""
import hashlib
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods={"GET", "POST"}, respect_retry_after_header=True)))
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
    # Discover by dated release metadata, then explicitly select that release.
    # Filename anomalies are independently resolved through emoji.code below.
    def query(version):
        response = SESSION.post(GRAPHQL, json={'operationName': 'Inventory', 'query': QUERY,
                                'variables': {'slug': VENDOR, 'version': version}}, timeout=(15, 120))
        response.raise_for_status()
        data = response.json()
        if data.get('errors'):
            raise ValueError(data['errors'])
        return data
    first = query(None)
    latest = max(first['data']['vendorHistoric_v1'], key=lambda r: r['date'])
    first = query(latest['slug'])
    if max(first['data']['vendorHistoric_v1'], key=lambda r: r['date'])['slug'] != latest['slug']:
        raise ValueError('Vendor release changed during discovery; retry a fresh observation')
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


def download_catalogue(catalogue, cache, workers=8, audit_only=False):
    """Fetch exactly the selected Emojipedia artwork; never substitute other art.

    Conditional HTTP requests detect in-place revisions without re-downloading
    unchanged images. Every cached file is verified before a 304 is accepted.
    Downloading an image does not grant rights to redistribute it.
    """
    cache.mkdir(parents=True, exist_ok=True)
    index_path = cache / 'images.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    updated = dict(index)

    def fetch(item):
        seq, candidate = item
        old = index.get(seq, {})
        sha = old.get('sha256', '')
        valid_metadata = (old.get('url') == candidate['url']
                          and re.fullmatch('[0-9a-f]{64}', sha) is not None
                          and re.fullmatch('[0-9a-f]{64}', old.get('pixel_sha256', '')) is not None
                          and isinstance(old.get('width'), int) and isinstance(old.get('height'), int))
        valid_cache = (valid_metadata
                       and (cache / (sha + '.png')).is_file()
                       and digest((cache / (sha + '.png')).read_bytes()) == sha)
        headers = {}
        if valid_cache or (audit_only and valid_metadata):
            if old.get('etag'):
                headers['If-None-Match'] = old['etag']
            elif old.get('last_modified'):
                headers['If-Modified-Since'] = old['last_modified']
        response = get(candidate['url'], headers=headers)
        if response.status_code == 304:
            if not valid_cache and not (audit_only and valid_metadata):
                raise ValueError(f'304 without valid cached artwork: {seq}')
            raw = (cache / (sha + '.png')).read_bytes() if valid_cache else None
        else:
            raw = response.content
        info = (image_info(raw) if raw is not None else
                {k: old[k] for k in ['width', 'height', 'sha256', 'pixel_sha256']})
        path = cache / (info['sha256'] + '.png')
        if not audit_only and not path.exists():
            path.write_bytes(raw)
        entry = dict(url=candidate['url'], **info,
                     etag=response.headers.get('ETag', old.get('etag', '')),
                     last_modified=response.headers.get('Last-Modified', old.get('last_modified', '')))
        return seq, dict(candidate, **info, path=str(path)), entry

    records = {}
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch, item) for item in sorted(catalogue['records'].items())]
            try:
                for future in as_completed(futures):
                    seq, record, entry = future.result()
                    records[seq] = record
                    updated[seq] = entry
                    if len(records) % 100 == 0:
                        index_path.write_bytes(canonical(updated))
                        print(f'Emojipedia artwork: {len(records)}/{len(futures)}', flush=True)
            except BaseException:
                for future in futures:
                    future.cancel()
                raise
    finally:
        index_path.write_bytes(canonical(updated))
    if set(records) != set(catalogue['records']):
        raise ValueError('Incomplete Emojipedia download; refusing a partial font')
    return dict(sorted(records.items()))
