"""Resolve the last successfully published batch snapshot for file consumers."""

import json
from pathlib import Path


def resolve_processed_dir(directory):
    directory = Path(directory).resolve()
    pointer = directory / 'CURRENT.json'
    if not pointer.is_file():
        return directory
    manifest = json.loads(pointer.read_text(encoding='utf-8'))
    target = (directory / manifest['processed_path']).resolve()
    if manifest.get('version') != 1 or not target.is_relative_to(directory.parent / 'runs'):
        raise ValueError('Invalid published snapshot pointer')
    if not (target.parent / 'completed.json').is_file():
        raise ValueError('Published snapshot is incomplete')
    return target
