"""Simple script to count files and lines of code in the repository."""

from __future__ import annotations

import argparse
from pathlib import Path


def walk_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for entry in root.rglob("*"):
        if entry.is_file():
            result.append(entry)
    return result


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Count files and total code lines in a repo.")
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Repository root to scan (default: current directory)",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    files = walk_files(root)
    total_lines = 0
    for path in files:
        total_lines += count_lines(path)
    print(f"scanned root: {root}")
    print(f"files: {len(files)}")
    print(f"lines: {total_lines}")


if __name__ == "__main__":
    main()
