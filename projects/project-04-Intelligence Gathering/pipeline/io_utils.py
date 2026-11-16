"""Small filesystem helpers shared by the analysis and vault writers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> bool:
    """Write text through a temporary file, returning False when content is unchanged."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding=encoding, errors="replace") == content:
        return False
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return True


def atomic_write_lines(path: Path, lines: Iterable[str], encoding: str = "utf-8") -> None:
    """Stream lines into a temporary file and atomically replace the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            for line in lines:
                handle.write(line)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
