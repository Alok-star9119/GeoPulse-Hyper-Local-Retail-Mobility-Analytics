"""Day 15: repository hygiene checks, so the repo stays clean and reproducible.

Checks (each returns a list of problem strings; empty = fine):
  - forbidden files (zip archives, PDFs at the top level, raw data formats) that must not be committed
  - files larger than a size limit (the repo holds small tables, not raw data)
  - scripts without a docstring that says what they do and how to run them
  - docs pages that README.md never links to
  - required .gitignore rules
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
FORBIDDEN_SUFFIXES = {".zip", ".parquet", ".gz", ".7z", ".tar", ".shp", ".dbf"}
REQUIRED_IGNORES = ["data/raw/*", "data/interim/*", "data/processed/*", ".env", "__pycache__/", "*.zip", "/*.pdf"]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints", "node_modules"}


def tracked_files(root: Path) -> list[Path]:
    """Files git would commit (tracked + untracked, not ignored). Falls back to a directory walk without git."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root,
                             capture_output=True, text=True, check=True).stdout
        return sorted(root / p for p in out.splitlines() if (root / p).is_file())
    except (OSError, subprocess.CalledProcessError):
        return sorted(p for p in root.rglob("*") if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS))


def check_forbidden(files: list[Path], root: Path) -> list[str]:
    bad = []
    for f in files:
        rel = f.relative_to(root)
        if rel.suffix.lower() in FORBIDDEN_SUFFIXES or (rel.suffix.lower() == ".pdf" and len(rel.parts) == 1):
            if rel.name != ".gitkeep":
                bad.append(f"{rel}: this file type should not be committed (add it to .gitignore)")
    return bad


def check_sizes(files: list[Path], root: Path, limit: int = MAX_BYTES) -> list[str]:
    return [f"{f.relative_to(root)}: {f.stat().st_size / 1e6:.1f} MB is over the {limit / 1e6:.0f} MB limit"
            for f in files if f.stat().st_size > limit]


def check_script_docstrings(root: Path) -> list[str]:
    bad = []
    for f in sorted((root / "scripts").glob("*.py")):
        try:
            doc = ast.get_docstring(ast.parse(f.read_text(encoding="utf-8")))
        except SyntaxError as e:
            bad.append(f"scripts/{f.name}: syntax error ({e.msg})")
            continue
        if not doc or len(doc.split()) < 8:
            bad.append(f"scripts/{f.name}: missing a docstring that explains what it does and how to run it")
        elif "python" not in doc.lower() and "usage" not in doc.lower() and "run" not in doc.lower():
            bad.append(f"scripts/{f.name}: docstring does not say how to run it")
    return bad


def check_docs_linked(root: Path) -> list[str]:
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    return [f"docs/{f.name}: not linked from README.md" for f in sorted((root / "docs").glob("*.md")) if f.name not in text]


def check_gitignore(root: Path, required: list[str] = REQUIRED_IGNORES) -> list[str]:
    f = root / ".gitignore"
    have = {l.strip() for l in f.read_text(encoding="utf-8").splitlines()} if f.exists() else set()
    return [f".gitignore: missing rule '{r}'" for r in required if r not in have]


def run_all(root: Path) -> dict[str, list[str]]:
    files = tracked_files(root)
    return {"forbidden files": check_forbidden(files, root), "large files": check_sizes(files, root),
            "script docstrings": check_script_docstrings(root), "docs linked from README": check_docs_linked(root),
            "gitignore rules": check_gitignore(root)}
