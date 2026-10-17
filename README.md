# Fluent 3D Emoji Font _(fluent-3d-emoji-font)_

[![Source checks](https://github.com/soizo/fluent-3d-emoji-font/actions/workflows/update.yml/badge.svg)](https://github.com/soizo/fluent-3d-emoji-font/actions/workflows/update.yml)

Auditable Fluent 3D emoji font builds with provenance and licensing gates.

Build colour fonts directly from the latest **Microsoft 3D Fluent catalogue on Emojipedia**. From version 0.3 onwards, every image comes from that selected catalogue. The project does not substitute older artwork from Microsoft's open-source repository or use third-party precompiled fonts.

The installed sbix font is named **Fluent 3D Community**; its SVG alternative is named **Fluent 3D Community SVG**. These community names distinguish the fonts from Microsoft products. The repository and Python package use `fluent-3d-emoji-font`.

Artwork redistribution rights are currently unverified. A local build can include the entire catalogue with explicit unverified-rights notices. The public workflow audits the actual source images, records hashes and coverage, and publishes fonts only when every image has suitable rights evidence. The project's MIT licence covers code; it does not grant rights to CDN artwork.

[Latest release](https://github.com/soizo/fluent-3d-emoji-font/releases/latest) · [Source-check reports](https://github.com/soizo/fluent-3d-emoji-font/actions) · [Questions and reports](https://github.com/soizo/fluent-3d-emoji-font/issues)

Version 0.4 is a maintainer-authorised manual publication of the tested 473×473 build. Artwork rights remain unverified; publication does not grant a licence to the artwork. The original build metadata and restricted-embedding notices are retained. Scheduled publication still requires matching rights evidence for every image.

Historical 0.1 and 0.2 releases used Microsoft's older open-source artwork. They do **not** represent the current Emojipedia-source pipeline. In particular, the older new moon face has closed eyes; the current reference has half-open eyes.

## Table of contents

- [Install](#install)
- [Usage](#usage)
- [Formats and rendering](#formats-and-rendering)
- [Source discovery and updates](#source-discovery-and-updates)
- [Coverage and quality](#coverage-and-quality)
- [Automatic publication](#automatic-publication)
- [Contributing](#contributing)
- [Licence](#licence)

## Install

### Dependencies

Use Python 3.13 and internet access. Allow several GB of disk space and memory for the original PNGs and four large colour-font files. Run these commands from the repository root:

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
```

Build the selected Emojipedia catalogue locally, acknowledging that the artwork has not been cleared for redistribution:

```sh
fluent-font --allow-unverified-local --output dist/local
```

The output directory must be empty. Use a different directory for each build. Original images and HTTP validators are cached in `work/emojipedia-assets/`; no Microsoft Git checkout is needed.

- **macOS:** open the generated `Fluent3D-sbix.ttf` in Font Book and install it. Choose **Fluent 3D Community** in the target application.
- **Windows:** install the SVG TTF only in applications that support OpenType-SVG with embedded PNGs.
- **Linux:** copy a supported TTF to `~/.local/share/fonts/` and run `fc-cache -f`.

The sbix and SVG variants have distinct family and PostScript names, so they can be installed together. For Obsidian and other Electron applications on macOS, select the **sbix** family. Replace older installed versions and restart applications if their font caches retain old data.

## Usage

Check both familiar and newly added artwork:

```text
😀 🕵🏽‍♀️ 😍 🥲 👩🏻‍💻 🏳️‍🌈 1️⃣ ❤️ 🌚 🫪
```

The font does not replace the system emoji font automatically. Some applications require explicit font selection. Unsupported sequences may fall back to system artwork; the manifest reports actual coverage separately.

For a web renderer with sbix support:

```sh
fonttools subset dist/local/Fluent3D-sbix.ttf \
  --text="😀 🕵🏽‍♀️ 😍 🥲 👩🏻‍💻 🏳️‍🌈 1️⃣ ❤️ 🌚 🫪" \
  --output-file=dist/local/Fluent3D-custom.woff2 --flavor=woff2 --retain-gids
```

Use the actual text your page needs. Subsetting removes unused glyphs, preserving the selected 473×473 PNGs without further changes. Full-catalogue fonts can exceed Chromium's 128 MB web-font decoding limit; install the full TTF for desktop use and use a suitable subset for web embedding. The source renderer's [limit is documented in Chromium](https://chromium.googlesource.com/chromium/src/+/c30907edb428e4185390d4c606510c65da38ab06/third_party/blink/renderer/platform/fonts/web_font_decoder.cc).

```css
@font-face {
  font-family: "Fluent 3D Community";
  src: url("./Fluent3D-custom.woff2") format("woff2");
  font-display: swap;
}

.emoji {
  font-family: "Fluent 3D Community", "Apple Color Emoji", "Segoe UI Emoji", sans-serif;
}
```

### CLI

The default command audits the selected images and their rights evidence:

```sh
fluent-font --output dist/audit
```

If rights evidence is incomplete, it writes `manifest.json` and `STATUS.md` without producing or publishing fonts. With complete, matching evidence, it builds and validates the full catalogue. It never builds a silently substituted or incomplete subset.

## Formats and rendering

| File | Intended use | Limitations |
| --- | --- | --- |
| `Fluent3D-sbix.ttf` | macOS CoreText and supporting Chromium/Electron applications | Preferred for Obsidian on macOS |
| `Fluent3D-svg.ttf` | Applications supporting OpenType-SVG and embedded PNGs | Select the separate **Fluent 3D Community SVG** family |
| `Fluent3D-sbix.woff2` | Web renderers supporting sbix in WOFF2 | WOFF2 compression does not add sbix support |
| `Fluent3D-svg.woff2` | Web renderers supporting OpenType-SVG in WOFF2 | Test the target browser; this is not universal Chromium support |

CBDT/CBLC is not currently generated. FontGoggles renders outlines and COLR fonts but does not display these sbix PNG or OpenType-SVG images. Use a supporting application to inspect the original 3D artwork.

Version 0.1 had empty glyph bounds, which caused some renderers to reserve width but paint nothing. Non-painting bounds contours and corrected sbix origins fix that issue. Native CoreText checks and Chromium pixel checks now verify visible colour at multiple sizes, including new moon face (`🌚`, U+1F31A) and distorted face (`🫪`, U+1FAEA).

From version 0.4, every 512×512 source is centre-cropped to 473×473 without scaling or resampling. The crop removes 19 pixels from the left and top and 20 from the right and bottom (the difference is odd). Retained RGBA pixels are unchanged; PNGs are re-encoded losslessly. A different source size fails the build for explicit review.

## Source discovery and updates

The public Emojipedia catalogue API supplies release names and dates. The build discovers the newest dated release, explicitly selects it and retrieves its full image list. It does not guess CDN identifiers, generate URLs from English names or permanently hard-code `473`.

Image filenames are cross-checked against the independent `emoji.code` field. This handles skin tones, ZWJ sequences, flags, tag sequences and legacy filenames with duplicated skin-tone suffixes. Unknown naming patterns, conflicting mappings or incomplete downloads stop the build.

Every source is recorded with its exact URL, native dimensions, PNG hash and decoded-pixel hash. Conditional HTTP requests use ETag or Last-Modified values to detect revisions at unchanged URLs. Cache entries are validated before reuse. A changed image creates a new content identity; a changed check date alone does not.

GitHub Actions checks daily at 02:17 UTC and supports **Actions → Update fonts → Run workflow**. Scheduled runs may be delayed or suspended by GitHub on inactive repositories. Public CI caches only the metadata index, never unverified artwork or fonts. See the [source investigation](docs/UPSTREAM.md).

## Coverage and quality

The latest Unicode `emoji-test.txt` provides the coverage denominator. Non-RGI catalogue sequences are retained and reported separately. Qualification aliases are limited to forms listed by Unicode; no unsupported artwork is invented.

Each output is reopened and every mapping is shaped with HarfBuzz. Embedded PNGs are compared byte-for-byte with the cropped assets. The manifest records the crop box and separate original-source and embedded-image hashes. Glyph bounds must be non-empty and match bitmap placement. The required regression characters include `🌚` and `🫪`; system fallback is not counted as font coverage.

Build manifests distinguish catalogue size, downloaded artwork, actual font coverage and pending redistribution evidence. A successful source audit does not mean a font was built or released. Coverage alone is not a claim that older artwork matches a newer reference.

## Automatic publication

After matching rights evidence is supplied for every selected image, the workflow automatically builds the complete catalogue, validates shaping and cropped image bytes, runs native and browser rendering checks, and publishes a content-addressed GitHub Release.

Local unverified builds include `NOT-FOR-REDISTRIBUTION.txt` and an explicit notice in font name record 13. They are never uploaded by the public workflow. The code's MIT licence is not attached to the artwork as a substitute for missing permission. See the [rights evidence process](docs/LICENSING.md).

Completed font builds contain four font files, `manifest.json`, `SHA256SUMS`, `RELEASE.md`, the exact Unicode input and applicable notices. Failed checks do not update a release.

## Contributing

Questions, bugs, mapping fixes, renderer results and verifiable rights-holder evidence are welcome through [GitHub Issues](https://github.com/soizo/fluent-3d-emoji-font/issues) and pull requests.

```sh
python -m pytest -q
```

For macOS rendering checks, use `scripts/check_macos.swift`. The browser check uses `scripts/check_browser.cjs` with Playwright 1.62.1. Do not commit downloaded images, local fonts or unverified rights claims.

## Licence

Project code: [MIT](LICENSE), copyright © 2026 soizo.

Microsoft emoji artwork and material obtained through Emojipedia retain their respective rights holders' copyright. Redistribution and font-embedding rights must be verified independently. The Microsoft MIT notice retained for historical releases does not automatically cover CDN artwork used by the current pipeline.

Unicode data uses [Unicode License v3](licenses/Unicode.txt). Read [Licensing](docs/LICENSING.md) for the full boundary. This project is not affiliated with Microsoft or Emojipedia.
