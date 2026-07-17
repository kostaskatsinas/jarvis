"""Dev-assistant tools (scope: "dev"), sandboxed to JARVIS_WORKSPACE_ROOT.

Repo-aware read/search/write plus a fixed set of git operations. There is
deliberately no arbitrary-command tool: the blast radius of the dev agent
is "files inside the workspace volume", nothing more.
"""

import asyncio
import json
import os
from pathlib import Path

from jarvis.config import get_settings
from jarvis.core.registry import tool

TREE_LIMIT = 200


def _workspace() -> Path:
    root = Path(get_settings().workspace_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _repo_path(repo: str) -> Path:
    if not repo or "/" in repo or repo.startswith("."):
        raise ValueError(f"invalid repo name: {repo!r}")
    path = _workspace() / repo
    if not path.is_dir():
        raise ValueError(f"unknown repo: {repo!r} (use repo_list / git_clone)")
    return path


def _resolve_in_repo(repo: str, relative: str) -> Path:
    root = _repo_path(repo)
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes the repo: {relative}")
    return path


async def _git(*args: str, cwd: Path, ok_exit: tuple[int, ...] = (0,)) -> str:
    process = await asyncio.create_subprocess_exec(
        "git", *args, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    output, _ = await process.communicate()
    text = output.decode(errors="replace").strip()
    if process.returncode not in ok_exit:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{text}")
    return text


@tool(scopes=("dev",))
async def git_clone(url: str, name: str = "") -> str:
    """Clone a git repository into the workspace. Optional name overrides the
    directory name derived from the URL."""
    target = name or url.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1]
    if "/" in target or target.startswith("."):
        raise ValueError(f"invalid target name: {target!r}")
    await _git("clone", "--depth", "50", url, target, cwd=_workspace())
    return f"cloned {url} -> {target}"


@tool(scopes=("dev",))
async def repo_list() -> str:
    """List repositories currently in the workspace."""
    repos = sorted(p.name for p in _workspace().iterdir() if (p / ".git").is_dir())
    return json.dumps(repos)


@tool(scopes=("dev",))
async def repo_tree(repo: str, path: str = ".", max_entries: int = TREE_LIMIT) -> str:
    """List files under a repo path (recursive, .git excluded, capped)."""
    base = _resolve_in_repo(repo, path)
    entries: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for filename in sorted(filenames):
            entries.append(str(Path(dirpath, filename).relative_to(_repo_path(repo))))
            if len(entries) >= max_entries:
                entries.append(f"... truncated at {max_entries} entries")
                return json.dumps(entries)
    return json.dumps(entries)


@tool(scopes=("dev",))
async def repo_read(repo: str, path: str, max_chars: int = 8000) -> str:
    """Read a file from a workspace repo (truncated to max_chars)."""
    return _resolve_in_repo(repo, path).read_text(errors="replace")[:max_chars]


@tool(scopes=("dev",))
async def repo_search(repo: str, pattern: str, max_results: int = 50) -> str:
    """Search a repo for a pattern (git grep, includes untracked files).
    Returns 'path:line:content' matches."""
    # exit 1 = no matches for git grep, not an error
    output = await _git(
        "grep", "-n", "--untracked", "-e", pattern, cwd=_repo_path(repo), ok_exit=(0, 1)
    )
    lines = output.splitlines()
    if len(lines) > max_results:
        lines = lines[:max_results] + [f"... truncated at {max_results} matches"]
    return "\n".join(lines) or "(no matches)"


@tool(scopes=("dev",))
async def repo_write(repo: str, path: str, content: str) -> str:
    """Create or overwrite a file in a workspace repo (parents created).
    Use repo_diff afterwards to show the user what changed."""
    target = _resolve_in_repo(repo, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"wrote {len(content)} chars to {repo}/{path}"


@tool(scopes=("dev",))
async def repo_diff(repo: str) -> str:
    """Show working-tree state of a repo: git status plus the full diff."""
    cwd = _repo_path(repo)
    status = await _git("status", "--short", "--untracked-files=all", cwd=cwd)
    diff = await _git("diff", cwd=cwd)
    return f"STATUS:\n{status or '(clean)'}\n\nDIFF:\n{diff or '(no diff)'}"
