"""Durable file writes (M2): what is reported as written survives a power loss.

`os.replace` is atomic, but without `fsync` the new name can reach the disk before the data,
leaving an empty or truncated file after a crash. Files are flushed before the rename and the
folder after it. Windows cannot open a folder to flush it; NTFS journals the rename itself.
"""

import os
from pathlib import Path


def fsync_file(path: Path):
    # Windows' fsync (_commit) needs a descriptor open for writing.
    with open(path, "rb+") as handle:
        os.fsync(handle.fileno())


def fsync_dir(path: Path):
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def replace_durably(part: Path, target: Path):
    """Flushes `part`, renames it over `target` and flushes the folder."""
    fsync_file(part)
    os.replace(part, target)
    fsync_dir(Path(target).parent)


def write_durably(path: Path, data: bytes):
    path = Path(path)
    part = path.with_name(f".{path.name}.part")
    part.write_bytes(data)
    replace_durably(part, path)
