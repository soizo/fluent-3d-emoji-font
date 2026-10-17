"""Reproducible pixel crops; downloaded source files remain untouched."""
import io
from pathlib import Path

from PIL import Image

from .sources import digest, image_info


def centre_crop(records, output, size=473):
    if size not in (473, 440):
        raise ValueError('Supported crop sizes are 473 and 440')
    inset = (512 - size) // 2
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cropped = {}
    for sequence, record in records.items():
        raw = Path(record['path']).read_bytes()
        if digest(raw) != record['sha256']:
            raise ValueError(f'Source hash mismatch: {sequence}')
        with Image.open(io.BytesIO(raw)) as image:
            if image.size != (512, 512):
                raise ValueError(f'Expected 512×512 source for centre crop: {sequence}')
            # Odd difference: remove 19 px at left/top, 20 px at right/bottom.
            image = image.convert('RGBA').crop((inset, inset, inset + size, inset + size))
            data = io.BytesIO()
            image.save(data, format='PNG')
        data = data.getvalue()
        info = image_info(data)
        path = output / (info['sha256'] + '.png')
        path.write_bytes(data)
        cropped[sequence] = dict(record, **{'path': str(path), **info})
    return cropped
