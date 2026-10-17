import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from .sources import (canonical, digest, get, discover, official_inventory, emoji_data,
                      image_info, key, sequence)
from .font import mappings, build, validate


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def approved_candidates(candidates, approvals, cache):
    records = {}
    for approval in approvals:
        seq = approval['sequence']
        if seq not in candidates or candidates[seq]['url'] != approval['url']:
            raise ValueError(f'Approval no longer matches latest inventory: {seq}')
        evidence = Path(approval['license_file'])
        if not evidence.is_relative_to('licenses') or '..' in evidence.parts:
            raise ValueError('License evidence must be a file in licenses/')
        if not approval.get('evidence_url') or not approval.get('redistribution_and_font_embedding'):
            raise ValueError('Explicit redistribution/font embedding evidence required')
        if digest(evidence.read_bytes()) != approval['license_sha256']:
            raise ValueError('License evidence changed')
        # Re-fetch even if the URL/set ID is unchanged: detect in-place artwork revisions.
        raw = get(approval['url']).content
        info = image_info(raw)
        if info['sha256'] != approval['sha256']:
            raise ValueError(f'Artwork changed; license approval must be reviewed: {seq}')
        path = cache / (info['sha256'] + '.png')
        path.write_bytes(raw)
        records[seq] = dict(candidates[seq], **info, path=str(path), rights=approval['license_id'],
                            license_evidence=approval)
    return records


def run(args):
    out = Path(args.output)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be empty (prevents stale Release files)')
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    unicode_raw = get('https://unicode.org/Public/emoji/latest/emoji-test.txt').content
    unicode_version, unicode_entries = emoji_data(unicode_raw.decode('utf-8-sig'))
    candidates = discover()
    write_json(cache / "reference-observation.json", candidates)
    commit, records = official_inventory(Path(args.upstream))
    approvals = json.loads(Path(args.approvals).read_text())
    records.update(approved_candidates(candidates['records'], approvals, cache))
    aliases = mappings(records, unicode_entries)
    required = {s for s, status in unicode_entries.items() if status == 'fully-qualified'}
    missing = sorted(required - aliases.keys())
    candidate_keys = set(candidates['records'])
    candidate_missing = sorted(candidate_keys - set(records))
    # Paths and check timestamps must never trigger a new release.
    public_records = {k: {a: b for a, b in v.items() if a != 'path'} for k, v in records.items()}
    implementation = {p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}
    identity_records = {k: {a: b for a, b in v.items() if a not in
                            {'url', 'upstream_commit', 'slug', 'asset_set_id', 'status', 'source'}}
                        for k, v in public_records.items()}
    identity_data = dict(records=identity_records, unicode_sha256=digest(unicode_raw),
                         implementation=implementation, config=digest(Path('pyproject.toml').read_bytes()),
                         approvals=approvals, licenses={p.name: digest(p.read_bytes())
                         for p in sorted(Path('licenses').glob('*')) if p.is_file()})
    identity = digest(canonical(identity_data))
    tag = 'v0.2-' + identity[:20]
    checked = datetime.now(timezone.utc).isoformat()
    report = dict(schema_version=1, font_version='0.2.0', content_id=identity, tag=tag, checked_at=checked,
                  unicode_version=unicode_version, unicode_sha256=digest(unicode_raw),
                  microsoft_commit=commit, latest_reference=candidates['release'],
                  reference_asset_set_ids=candidates['asset_set_ids'],
                  artwork_count=len(records), reference_count=len(candidate_keys),
                  rgi_total=len(required), rgi_covered=len(required)-len(missing),
                  rgi_coverage=(len(required)-len(missing))/len(required),
                  missing_rgi=[key(s) for s in missing],
                  reference_sequences_without_releasable_artwork=candidate_missing,
                  unverified_reference_count=len(candidate_keys - {a['sequence'] for a in approvals}),
                  latest_reference_visual_parity_verified=False,
                  qualification_alias_count=len(aliases)-len(records),
                  extra_non_rgi_sequences=sorted(set(records)-{key(s) for s in unicode_entries}),
                  source_records=public_records, candidate_inventory=candidates,
                  implementation=implementation)
    paths = build(records, aliases, out, identity)
    report['shaping_checks_passed'] = validate(paths, records, aliases)
    report['files'] = {p.name: digest(p.read_bytes()) for p in paths}
    write_json(out / 'manifest.json', report)
    (out / 'emoji-test.txt').write_bytes(unicode_raw)
    shutil.copytree('licenses', out / 'licenses')
    shutil.copyfile('LICENSE', out / 'CODE-LICENSE.txt')
    shutil.copyfile('docs/LICENSING.md', out / 'LICENSING.md')
    notes = (f'# Fluent 3D Community — {tag}\n\n'
             'Rendering fix in 0.2: non-empty glyph bounds and corrected bitmap origins '
             'fix invisible emoji in macOS Chromium/Electron applications, including Obsidian. '
             'Replace the 0.1 font and restart the application to clear cached fonts. '
             'Use Fluent 3D Community (sbix); the SVG alternative now has the distinct '
             'family name Fluent 3D Community SVG.\n\n'
             f'Official Microsoft commit: `{commit}`.\n\n'
             f'Artwork: {len(records)}; Unicode Emoji {unicode_version} RGI coverage: '
             f'{len(required)-len(missing)}/{len(required)} ({report["rgi_coverage"]:.2%}).\n\n'
             f'Latest Emojipedia reference: {candidates["release"]["title"]}, '
             f'asset set IDs {candidates["asset_set_ids"]}, {len(candidate_keys)} records.\n\n'
             f'**Latest-reference visual parity is NOT verified.** '
             f'{len(candidate_missing)} reference sequences have no releasable artwork; '
             'existing official artwork may also differ from updated reference designs. '
             'Unverified CDN images are excluded. This is a licensed subset release.\n\n'
             'Install the sbix TTF on macOS. SVG is an application-dependent alternative; '
             'WOFF2 is a web container, not a guarantee of color support. See README.\n\n'
             f'Validated {report["shaping_checks_passed"]} shaping cases; original PNG bytes preserved. '
             'See manifest.json for hashes, mappings and all missing sequences.\n')
    (out / 'RELEASE.md').write_text(notes)
    # Checksums include reports and licenses as well as fonts.
    sums = [f'{digest(p.read_bytes())}  {p.relative_to(out).as_posix()}'
            for p in sorted(out.rglob('*')) if p.is_file()]
    (out / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'tag={tag}\n')
    print(json.dumps({k: report[k] for k in ['tag', 'artwork_count', 'rgi_total', 'rgi_covered',
                                              'reference_count', 'shaping_checks_passed']}, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Discover latest reference and build licensed Fluent fonts')
    parser.add_argument('--upstream', required=True, help='Clean microsoft/fluentui-emoji Git checkout')
    parser.add_argument('--output', default='dist')
    parser.add_argument('--cache', default='work/approved-assets')
    parser.add_argument('--approvals', default='licenses/approvals.json')
    run(parser.parse_args())


if __name__ == '__main__':
    main()
