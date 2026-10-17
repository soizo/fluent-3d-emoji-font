# Fluent 3D Emoji Font _(fluent-3d-emoji-font)_

[![Automatic updates](https://github.com/soizo/fluent-3d-emoji-font/actions/workflows/update.yml/badge.svg)](https://github.com/soizo/fluent-3d-emoji-font/actions/workflows/update.yml)

Auditable Fluent 3D emoji font builds with provenance and licensing gates.

This repository automatically builds colour fonts from Microsoft's official PNG artwork while using Emojipedia to discover the latest candidate artwork. The installed font is named **Fluent 3D Community** to distinguish this community project from Microsoft products; the repository and Python package use the `fluent-3d-emoji-font` name.

The public fonts contain only artwork with verified redistribution rights. They do not claim complete visual parity with the latest Microsoft release. When redistribution rights for new artwork listed by Emojipedia cannot be confirmed, the build records the catalogue entry and coverage gap but excludes the image from the public font. The project does not depend on third-party precompiled fonts.

[Download the latest fonts](https://github.com/soizo/fluent-3d-emoji-font/releases/latest) · [View releases and coverage](https://github.com/soizo/fluent-3d-emoji-font/releases) · [View build status](https://github.com/soizo/fluent-3d-emoji-font/actions)

## Table of contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Formats and compatibility](#formats-and-compatibility)
- [Local build](#local-build)
- [Discovery, mapping and quality](#discovery-mapping-and-quality)
- [Release contents](#release-contents)
- [Contributing](#contributing)
- [Licence](#licence)

## Background

The project checks for upstream changes every day at 02:17 UTC. GitHub may delay scheduled workflows and may suspend them on public repositories with prolonged inactivity. You can also run **Actions → Update fonts → Run workflow** manually. A failed build does not update the release.

A new content release is created only when the code, redistributable artwork, licence evidence or Unicode coverage data changes. An unchanged build retains the existing release date. A reference-catalogue-only change updates the workflow report without republishing identical fonts.

The build preserves the source PNG bytes rather than tracing the artwork into COLR vectors. This keeps the original 3D appearance intact and avoids lossy conversion.

## Install

Download `Fluent3D-fonts.tar.gz` from the [latest release](https://github.com/soizo/fluent-3d-emoji-font/releases/latest), then extract it to retain the fonts, licences, provenance manifest and checksums together.

```sh
curl -LO https://github.com/soizo/fluent-3d-emoji-font/releases/latest/download/Fluent3D-fonts.tar.gz
tar -xzf Fluent3D-fonts.tar.gz
```

If you download an individual font file, retain the licence notices from the archive. The licence text is also embedded in font name record 13.

- **macOS:** double-click `Fluent3D-sbix.ttf`, select **Install Font**, then choose **Fluent 3D Community** in an application that supports custom fonts.
- **Windows:** right-click a suitable TTF and select **Install**.
- **Linux:** place a suitable TTF in `~/.local/share/fonts/`, then run `fc-cache -f`.

The sbix font is named **Fluent 3D Community**; the SVG alternative is named **Fluent 3D Community SVG**. They have distinct PostScript names and may be installed together. For Obsidian and other Electron applications on macOS, choose the sbix font.

If you installed a 0.1 release, replace it with version 0.2 or later and restart the application. Version 0.1 contained empty glyph bounds: some renderers reserved the correct width but painted no image. Version 0.2 supplies non-painting bounds contours and correct bitmap placement, preserving the original PNGs.

## Usage

The font does not replace Apple Color Emoji or Segoe UI Emoji automatically. Select **Fluent 3D Community** in an application that permits font selection, then test a representative set:

```text
😀 👩🏻‍💻 🏳️‍🌈 1️⃣ ❤️ 🏴
```

Some applications force their system emoji font. Sequences missing from the licensed artwork set may also fall back to the system font; see `manifest.json` in the release for the exact coverage.

For the web, choose the format supported by your target browser and renderer:

```css
@font-face {
  font-family: "Fluent 3D Community";
  src: url("./Fluent3D-sbix.woff2") format("woff2");
  font-display: swap;
}

.emoji {
  font-family: "Fluent 3D Community", "Apple Color Emoji", "Segoe UI Emoji", sans-serif;
}
```

WOFF2 is a compression container; it does not add support for the underlying colour-font table. Test the chosen file in every browser and operating system you intend to support.

### CLI

The `fluent-font` command discovers the latest reference release, inventories a clean checkout of Microsoft's official artwork, builds all formats and validates every mapping:

```sh
fluent-font --upstream work/upstream --output dist
```

The output directory must be empty to prevent stale release files from being mixed into a new build.

## Formats and compatibility

| File | Recommended use | Limitations |
| --- | --- | --- |
| `Fluent3D-sbix.ttf` | macOS Font Book and CoreText applications | Preferred on macOS; application font selection and system fallback affect the result |
| `Fluent3D-svg.ttf` | Applications with OpenType-SVG support, including some Windows and Linux applications | Support depends on the renderer, including support for PNG images embedded in SVG |
| `Fluent3D-sbix.woff2` | Web renderers that support sbix in WOFF2 | WOFF2 compression does not add sbix support |
| `Fluent3D-svg.woff2` | Web renderers that support OpenType-SVG in WOFF2 | Verify in the target browser; this is not a universal Chromium solution |

CBDT/CBLC is not currently generated, so renderers that require it are not guaranteed to work. macOS Chromium/Electron can use the sbix font. Release checks cover native CoreText and actual Chromium canvas pixels at five sizes, including skin-tone and ZWJ sequences; shaping alone does not count as a rendering pass. Other operating systems have not received equivalent real-device rendering certification.

FontGoggles currently renders outlines and COLR fonts, but does not display these sbix PNG or OpenType-SVG images. A blank preview there does not establish that a bitmap font is broken. Use a supporting application or the release workflow's CoreText and Chromium previews to inspect the original 3D artwork.

Source PNGs are embedded without scaling or re-encoding. Rendering above the artwork's native resolution remains subject to normal bitmap limitations.

## Local build

### Dependencies

You need Python 3.13, Git, internet access and approximately 2 GB of free space. Run the following commands from the repository root:

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
git clone --depth 1 https://github.com/microsoft/fluentui-emoji.git work/upstream
fluent-font --upstream work/upstream --output dist
```

The Microsoft artwork checkout must be clean. If you reuse an existing checkout, update it to the latest official `main` branch first. Use a new empty output directory for every build.

Fonts are byte-for-byte reproducible when the source version, code, Unicode inputs and pinned dependencies are unchanged. Reproducibility across differing operating systems or dependency environments is not guaranteed. Dependencies are pinned, and Dependabot proposes tested upgrades.

## Discovery, mapping and quality

The public Emojipedia catalogue API supplies release names and dates. The build selects the newest dated release, then retrieves its full artwork list. It does not guess CDN identifiers, derive URLs from English names or hard-code asset-set identifier `473`. The API is not a stability guarantee; an unexpected response fails the build. See the [upstream investigation](docs/UPSTREAM.md) for details.

Official Microsoft `metadata.json` files provide `unicode` and `unicodeSkintones` mappings, including the default artwork and five skin-tone variants. The build does not infer modifier positions from filenames. Candidate image sequences are cross-checked against the independent `emoji.code` field, including paths with duplicated skin-tone suffixes. Unknown naming patterns and conflicting mappings fail the build.

The latest official Unicode `emoji-test.txt` supplies the coverage denominator. Non-RGI artwork is retained and reported separately. Qualification aliases are created only for variation-selector forms explicitly listed by Unicode; the build does not invent unsupported mixed-tone or family sequences.

Fonts include `cmap` and GSUB `rlig` tables. Long sequences take priority so that ZWJ sequences, skin tones, flags, keycaps and tag sequences shape correctly. Every released format is reopened and checked with HarfBuzz, and every embedded image is compared byte-for-byte with its source PNG. These checks validate font structure and mappings but do not replace platform-specific CoreText or DirectWrite rendering tests.

Mixed source resolutions, empty images, licence changes, download failures, unknown directory structures, duplicate mappings, conflicts and shaping errors all prevent publication.

## Release contents

Each release contains:

- `manifest.json`: source URLs, the official commit, reference release, source-file and pixel SHA-256 hashes, Unicode version, coverage and every missing sequence;
- `SHA256SUMS`: checksums for fonts, manifests, Unicode data and licence files;
- `RELEASE.md`: coverage for that content version and the gap caused by unverified redistribution rights;
- `emoji-test.txt` and `licenses/`: the rebuild input and required licence notices;
- four font files and `Fluent3D-fonts.tar.gz` containing the complete release bundle.

A new catalogue release does not prove that older character artwork is unchanged. Each check hashes every PNG in Microsoft's official repository. Artwork approved from another source is downloaded again and compared with the hash bound to its licence evidence; an in-place change blocks publication pending review. Unapproved CDN images are not downloaded, so the project does not claim visual parity between those images and older official artwork.

## Contributing

Questions and bug reports are welcome in [GitHub Issues](https://github.com/soizo/fluent-3d-emoji-font/issues). Pull requests are accepted for mapping fixes, renderer test results, documentation improvements and verifiable rights-holder licence evidence.

Run the test suite before opening a pull request:

```sh
python -m pytest -q
```

New artwork without confirmed redistribution and font-embedding rights may be recorded only as a candidate. It must not be added to a public font. Follow the evidence and approval process in [Licensing](docs/LICENSING.md).

## Licence

Project code: [MIT](LICENSE), copyright © 2026 soizo.

Microsoft's official artwork is distributed under Microsoft's separate [MIT licence](licenses/Microsoft-MIT.txt). Unicode data is distributed under the [Unicode License v3](licenses/Unicode.txt). Emojipedia catalogue information and vendor artwork are not covered by the project code licence. See [Licensing](docs/LICENSING.md) for the full boundary and approval process.

Microsoft, Windows and Fluent are trade marks of their respective owners. This project is not affiliated with Microsoft or Emojipedia.
