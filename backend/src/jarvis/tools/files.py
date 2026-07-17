"""File-organization tools (scope: "files"), sandboxed to JARVIS_FILES_ROOT.

Move/create only — no delete tool by design; destructive cleanup stays a
human action.
"""

import json
import shutil
from pathlib import Path

from jarvis.config import get_settings
from jarvis.core.registry import tool


def _root() -> Path:
    root = Path(get_settings().files_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve(relative: str) -> Path:
    root = _root()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes the files root: {relative}")
    return path


@tool(scopes=("files",))
async def file_list(path: str = ".") -> str:
    """List a directory inside the files area as JSON: name, type (file/dir), size."""
    target = _resolve(path)
    entries = [
        {
            "name": entry.name,
            "type": "dir" if entry.is_dir() else "file",
            "size": entry.stat().st_size if entry.is_file() else None,
        }
        for entry in sorted(target.iterdir(), key=lambda e: e.name)
    ]
    return json.dumps(entries)


@tool(scopes=("files",))
async def file_read(path: str, max_chars: int = 4000) -> str:
    """Read a text file from the files area (truncated to max_chars)."""
    return _resolve(path).read_text(errors="replace")[:max_chars]


@tool(scopes=("files",))
async def file_move(src: str, dest: str) -> str:
    """Move or rename a file/directory within the files area. Creates missing
    destination directories."""
    source, destination = _resolve(src), _resolve(dest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return f"moved {src} -> {dest}"


@tool(scopes=("files",))
async def file_mkdir(path: str) -> str:
    """Create a directory (and parents) within the files area."""
    _resolve(path).mkdir(parents=True, exist_ok=True)
    return f"created {path}"
