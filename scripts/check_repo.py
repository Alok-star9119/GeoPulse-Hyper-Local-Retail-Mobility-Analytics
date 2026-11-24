"""Day 15: check the repository is clean before committing.

Usage
  python scripts/check_repo.py

Looks for zip/PDF/raw-data files that would be committed, files over 5 MB, scripts without a
docstring, docs pages not linked from README.md and missing .gitignore rules.
Exit code 1 if any problem is found, so it can be run before every commit.
"""
import sys

from geopulse.config import PROJECT_ROOT
from geopulse.hygiene import run_all


def main() -> None:
    results = run_all(PROJECT_ROOT)
    problems = 0
    for name, items in results.items():
        print(f"[{'ok' if not items else 'PROBLEM'}] {name}")
        for i in items:
            print(f"    - {i}")
        problems += len(items)
    print(f"\n{problems} problem(s)." if problems else "\nRepository looks clean.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
