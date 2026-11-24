import subprocess

from geopulse import hygiene as hg


def build(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts/good.py").write_text('"""Build the thing.\n\nUsage\n  python scripts/good.py --year 2024\n"""\n')
    (tmp_path / "docs/a.md").write_text("x")
    (tmp_path / "README.md").write_text("See docs/a.md")
    (tmp_path / ".gitignore").write_text("\n".join(hg.REQUIRED_IGNORES))
    return tmp_path


def test_clean_repo_has_no_problems(tmp_path):
    r = build(tmp_path)
    assert all(v == [] for v in hg.run_all(r).values())


def test_forbidden_and_large_files(tmp_path):
    r = build(tmp_path)
    (r / "a.zip").write_bytes(b"x")
    (r / "assignment.pdf").write_bytes(b"x")
    (r / "docs/report.pdf").write_bytes(b"x")              # a PDF inside docs/ is allowed
    (r / "data").mkdir()
    (r / "data/.gitkeep").write_text("")
    (r / "big.csv").write_bytes(b"x" * 2048)
    files = hg.tracked_files(r)
    bad = hg.check_forbidden(files, r)
    assert len(bad) == 2 and any("a.zip" in b for b in bad) and any("assignment.pdf" in b for b in bad)
    assert hg.check_sizes(files, r, limit=1000) and "big.csv" in hg.check_sizes(files, r, limit=1000)[0]
    assert hg.check_sizes(files, r) == []


def test_script_docstrings(tmp_path):
    r = build(tmp_path)
    (r / "scripts/none.py").write_text("print(1)\n")
    (r / "scripts/short.py").write_text('"""Does stuff."""\n')
    (r / "scripts/vague.py").write_text('"""This script does a number of different and interesting things with data."""\n')
    (r / "scripts/broken.py").write_text("def (:\n")
    bad = hg.check_script_docstrings(r)
    assert len(bad) == 4 and not any("good.py" in b for b in bad)
    assert any("how to run" in b for b in bad) and any("syntax error" in b for b in bad)


def test_docs_and_gitignore(tmp_path):
    r = build(tmp_path)
    (r / "docs/orphan.md").write_text("x")
    assert hg.check_docs_linked(r) == ["docs/orphan.md: not linked from README.md"]
    (r / ".gitignore").write_text("data/raw/*\n")
    assert len(hg.check_gitignore(r)) == len(hg.REQUIRED_IGNORES) - 1
    (r / ".gitignore").unlink()
    assert len(hg.check_gitignore(r)) == len(hg.REQUIRED_IGNORES)


def test_git_respects_ignore(tmp_path):
    r = build(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    (r / "ignored.zip").write_bytes(b"x")                    # *.zip is in .gitignore, so git does not list it
    names = {f.name for f in hg.tracked_files(r)}
    assert "ignored.zip" not in names and "README.md" in names
