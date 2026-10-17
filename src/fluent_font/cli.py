import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from .sources import (canonical, digest, get, discover, download_catalogue, emoji_data, key)
from .font import mappings, build, validate
from .artwork import centre_crop


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def validate_approvals(candidates, approvals):
    approved = {}
    for approval in approvals:
        seq = approval['sequence']
        if seq in approved:
            raise ValueError(f'Duplicate rights approval: {seq}')
        if seq not in candidates or candidates[seq]['url'] != approval['url']:
            raise ValueError(f'Approval no longer matches latest inventory: {seq}')
        evidence = Path(approval['license_file'])
        if not evidence.is_relative_to('licenses') or '..' in evidence.parts:
            raise ValueError('License evidence must be a file in licenses/')
        if not approval.get('evidence_url') or not approval.get('redistribution_and_font_embedding'):
            raise ValueError('Explicit redistribution/font embedding evidence required')
        if digest(evidence.read_bytes()) != approval['license_sha256']:
            raise ValueError('License evidence changed')
        approved[seq] = approval
    return approved


def github_outputs(tag='', publishable=False, cache_key=''):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'tag={tag}\npublishable={str(publishable).lower()}\ncache_key={cache_key}\n')


def checksums(out):
    sums = [f'{digest(p.read_bytes())}  {p.relative_to(out).as_posix()}'
            for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS']
    (out / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')


def run(args):
    out = Path(args.output)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be empty (prevents stale Release files)')
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    source_manifest = getattr(args, 'source_manifest', None)
    snapshot = json.loads(Path(source_manifest).read_text()) if source_manifest else None
    unicode_raw = ((Path(source_manifest).parent / 'emoji-test.txt').read_bytes() if snapshot else
                   get('https://www.unicode.org/Public/emoji/latest/emoji-test.txt').content)
    unicode_version, unicode_entries = emoji_data(unicode_raw.decode('utf-8-sig'))
    candidates = snapshot['candidate_inventory'] if snapshot else discover()
    write_json(cache / "reference-observation.json", candidates)
    approvals = json.loads(Path(args.approvals).read_text())
    approved = validate_approvals(candidates['records'], approvals)
    pending = sorted(set(candidates['records']) - set(approved))
    records = download_catalogue(candidates, cache, audit_only=bool(pending and not args.allow_unverified_local))
    if snapshot:
        actual = {k: (r['url'], r['sha256']) for k, r in records.items()}
        expected = {k: (r['url'], r['sha256']) for k, r in snapshot['source_records'].items()}
        if actual != expected or digest(unicode_raw) != snapshot['unicode_sha256']:
            raise ValueError('Companion build source differs from the primary release snapshot')
    for required_case in ['1f31a', '1faea']:
        if required_case not in records:
            raise ValueError(f'Required rendering regression character missing from selected catalogue: {required_case}')
    for seq, approval in approved.items():
        if records[seq]['sha256'] != approval['sha256']:
            raise ValueError(f'Artwork changed; license approval must be reviewed: {seq}')
        records[seq].update(rights=approval['license_id'], license_evidence=approval)
    public_records = {k: {a: b for a, b in v.items() if a != 'path'} for k, v in records.items()}
    cache_key = digest(canonical({k: (r['url'], r['sha256']) for k, r in records.items()}))
    if pending and not args.allow_unverified_local:
        # A catalogue observation is not a font release. Do not silently use
        # older Microsoft Git artwork in place of the requested Emojipedia art.
        report = dict(schema_version=2, selected_source='emojipedia',
                      checked_at=datetime.now(timezone.utc).isoformat(),
                      build_status='rights_pending', publishable=False, artwork_count=0,
                      files={}, downloaded_artwork_count=len(records), source_records=public_records,
                      latest_reference=candidates['release'],
                      reference_asset_set_ids=candidates['asset_set_ids'],
                      reference_count=len(candidates['records']),
                      pending_rights_sequences=pending, candidate_inventory=candidates,
                      unicode_version=unicode_version)
        write_json(out / 'manifest.json', report)
        (out / 'STATUS.md').write_text(
            '# Emojipedia source observation\n\n'
            f'Latest selected release: {candidates["release"]["title"]}. '
            f'{len(candidates["records"])} catalogue records; {len(pending)} without '
            'verified redistribution and font-embedding rights.\n\n'
            'No font was built or published. No artwork from another source was substituted. '
            'A local build can use --allow-unverified-local; those outputs are not cleared '
            'for redistribution and are never uploaded by this workflow.\n')
        checksums(out)
        github_outputs(cache_key=cache_key)
        print(json.dumps({k: report[k] for k in ['build_status', 'reference_count', 'publishable']}))
        return
    publishable = not pending
    crop_size = getattr(args, 'crop_size', 473)
    inset = (512 - crop_size) // 2
    records = centre_crop(records, cache / f'cropped-{crop_size}', size=crop_size)
    cropped_records = {k: {a: b for a, b in v.items() if a != 'path'} for k, v in records.items()}
    aliases = mappings(records, unicode_entries)
    required = {s for s, status in unicode_entries.items() if status == 'fully-qualified'}
    missing = sorted(required - aliases.keys())
    candidate_keys = set(candidates['records'])
    # Paths and check timestamps must never trigger a new release.
    implementation = {p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}
    identity_records = {k: {a: b for a, b in v.items() if a not in
                            {'url', 'upstream_commit', 'slug', 'asset_set_id', 'status', 'source'}}
                        for k, v in cropped_records.items()}
    identity_data = dict(records=identity_records, unicode_sha256=digest(unicode_raw),
                         implementation=implementation, config=digest(Path('pyproject.toml').read_bytes()),
                         approvals=approvals, licenses={p.name: digest(p.read_bytes())
                         for p in sorted(Path('licenses').glob('*')) if p.is_file()})
    identity = digest(canonical(identity_data))
    tag = 'v0.4-' + identity[:20]
    checked = datetime.now(timezone.utc).isoformat()
    report = dict(schema_version=2, font_version='0.4.0', content_id=identity, tag=tag, checked_at=checked,
                  selected_source='emojipedia', publishable=publishable,
                  build_status='verified' if publishable else 'local_unverified',
                  unicode_version=unicode_version, unicode_sha256=digest(unicode_raw),
                  latest_reference=candidates['release'],
                  reference_asset_set_ids=candidates['asset_set_ids'],
                  artwork_count=len(records), reference_count=len(candidate_keys),
                  rgi_total=len(required), rgi_covered=len(required)-len(missing),
                  rgi_coverage=(len(required)-len(missing))/len(required),
                  missing_rgi=[key(s) for s in missing],
                  pending_rights_sequences=pending, unverified_reference_count=len(pending),
                  selected_catalogue_png_bytes_preserved=False,
                  image_transform=dict(operation='centre_crop', source_size=[512, 512],
                                       box=[inset, inset, inset + crop_size, inset + crop_size],
                                       output_size=[crop_size, crop_size], resampled=False),
                  parent_content_id=snapshot['content_id'] if snapshot else None,
                  embedded_records=cropped_records,
                  qualification_alias_count=len(aliases)-len(records),
                  extra_non_rgi_sequences=sorted(set(records)-{key(s) for s in unicode_entries}),
                  source_records=public_records, candidate_inventory=candidates,
                  implementation=implementation)
    paths = build(records, aliases, out, identity, variant='440' if crop_size == 440 else None)
    report['shaping_checks_passed'] = validate(paths, records, aliases)
    report['files'] = {p.name: digest(p.read_bytes()) for p in paths}
    write_json(out / 'manifest.json', report)
    (out / 'emoji-test.txt').write_bytes(unicode_raw)
    (out / 'licenses').mkdir()
    shutil.copyfile('licenses/Unicode.txt', out / 'licenses/Unicode.txt')
    for approval in approved.values():
        path = Path(approval['license_file'])
        shutil.copyfile(path, out / 'licenses' / path.name)
    shutil.copyfile('LICENSE', out / 'CODE-LICENSE.txt')
    shutil.copyfile('docs/LICENSING.md', out / 'LICENSING.md')
    notes = (f'# Fluent 3D Community — {tag}\n\n'
             'Rendering fix in 0.2: non-empty glyph bounds and corrected bitmap origins '
             'fix invisible emoji in macOS Chromium/Electron applications, including Obsidian. '
             'Replace the 0.1 font and restart the application to clear cached fonts. '
             'Use Fluent 3D Community (sbix); the SVG alternative now has the distinct '
             'family name Fluent 3D Community SVG. '
             + ('For this companion variant, select Fluent 3D Community 440 or Fluent 3D Community 440 SVG. ' if crop_size == 440 else '') + '\n\n'
             'Source: the selected Emojipedia Microsoft 3D Fluent catalogue only. '
             'No artwork from the older Microsoft Git repository is substituted.\n\n'
             f'Artwork: {len(records)}; Unicode Emoji {unicode_version} RGI coverage: '
             f'{len(required)-len(missing)}/{len(required)} ({report["rgi_coverage"]:.2%}).\n\n'
             f'Latest Emojipedia reference: {candidates["release"]["title"]}, '
             f'asset set IDs {candidates["asset_set_ids"]}, {len(candidate_keys)} records.\n\n'
             f'All {len(candidate_keys)} selected catalogue images are included, with '
             f'centre-cropped from 512×512 to {crop_size}×{crop_size} without resampling. '
             'Embedded PNG bytes are checked against the cropped assets; original source hashes are retained.\n\n'
             f'Redistribution status: {"verified" if publishable else "UNVERIFIED — LOCAL BUILD ONLY"}. '
             f'{len(pending)} images lack confirmed redistribution evidence.\n\n'
             'Install the sbix TTF on macOS. SVG is an application-dependent alternative; '
             'WOFF2 is a web container, not a guarantee of color support. See README.\n\n'
             f'Validated {report["shaping_checks_passed"]} shaping cases; cropped pixels preserved. '
             'See manifest.json for hashes, mappings and all missing sequences.\n')
    (out / 'RELEASE.md').write_text(notes)
    if not publishable:
        (out / 'NOT-FOR-REDISTRIBUTION.txt').write_text(
            'Local Emojipedia-source build. Artwork copyright belongs to its rights holders.\n'
            'Redistribution and font-embedding rights have not been confirmed.\n'
            'The project code MIT licence does not grant rights to these images.\n')
    checksums(out)
    github_outputs(tag, publishable, cache_key)
    print(json.dumps({k: report[k] for k in ['tag', 'artwork_count', 'rgi_total', 'rgi_covered',
                                              'reference_count', 'shaping_checks_passed']}, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Build directly from the latest Emojipedia Microsoft 3D Fluent catalogue')
    parser.add_argument('--output', default='dist')
    parser.add_argument('--cache', default='work/emojipedia-assets')
    parser.add_argument('--approvals', default='licenses/approvals.json')
    parser.add_argument('--crop-size', type=int, choices=[473, 440], default=473)
    parser.add_argument('--source-manifest', help='Pin companion artwork and Unicode input to a primary build manifest')
    parser.add_argument('--allow-unverified-local', action='store_true',
                        help='Build all selected artwork with unverified-rights notices; does not grant publication rights')
    run(parser.parse_args())


if __name__ == '__main__':
    main()
