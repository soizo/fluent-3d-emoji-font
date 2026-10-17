# Licensing and source boundaries

The project code is MIT-licensed. This does not license Microsoft emoji artwork, Emojipedia material or any downloaded image.

Version 0.3 and later use only the selected **Emojipedia Microsoft 3D Fluent catalogue** as the image source. Older images from Microsoft's Git repository are not substituted for missing or unapproved catalogue images. The Microsoft MIT notice retained in this repository documents historical releases; it is not evidence that a newer CDN image has the same licence.

Emojipedia's [licensing information](https://emojipedia.org/licensing) directs vendor-artwork licensing enquiries to the rights holders. A working CDN URL, a Microsoft path segment or similarity to an older image does not establish redistribution or font-embedding rights. Access rules and robots.txt are separate from image licensing; the tool does not bypass access restrictions.

## Local builds

The `--allow-unverified-local` option fetches the actual selected images and builds the complete font for local inspection. It is not a declaration that redistribution is permitted. The font carries an unverified-rights notice in name record 13, a restricted-embedding flag and `NOT-FOR-REDISTRIBUTION.txt`. No artwork is relabelled as MIT-licensed.

Scheduled runs do not use this option. Until every selected image has matching rights evidence, they produce an audit report rather than fonts. Source images used for audits remain on the ephemeral runner; only the JSON metadata index is cached. A maintainer may explicitly select `publish_unverified_artwork` when manually starting the workflow. That run builds and tests the fonts in Actions and may upload the unverified build and publish a Release with its original rights notices. This input does not approve the images or change their licence status.

## Rights evidence

Store the relevant rights-holder permission text under `licenses/`, then add an entry to the JSON array in `licenses/approvals.json`:

```json
{
  "sequence": "1faea",
  "url": "https://em-content.zobj.net/source/microsoft-3D-fluent/EXAMPLE-VERSION/distorted-face_1faea.png",
  "sha256": "SHA-256 of the exact PNG",
  "license_id": "Applicable licence identifier",
  "license_file": "licenses/rights-holder-permission.txt",
  "license_sha256": "SHA-256 of the permission text",
  "evidence_url": "Publicly verifiable rights-holder permission URL",
  "redistribution_and_font_embedding": true
}
```

This example is not permission. Review the actual terms, including redistribution, font embedding and required notices. An entry applies only to the recorded URL and image hash. New URLs or changed image content require new review; an entire CDN domain is never implicitly approved. Applicable permission texts are embedded in the font and included in the build output.

Every selected image must be approved before automatic public publication. A partial approval set does not cause the pipeline to switch to an older source or publish a misleading subset.

An explicitly requested Actions publication is not rights-holder permission: the artwork remains unverified, and the original local-build metadata, restricted-embedding flag and notices are retained. It does not approve any entry in `licenses/approvals.json` or bypass the scheduled workflow's rights checks.

Unicode coverage data uses [Unicode License v3](https://www.unicode.org/license.txt). Its licence does not grant rights to vendor artwork. Microsoft, Windows and Fluent are trade marks of their respective owners; the project is not affiliated with Microsoft or Emojipedia.
