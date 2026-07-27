#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClearHistoryResult:
    removed_chat_sessions: int
    removed_knowledge_items: int


def clear_history(repo_root: Path) -> ClearHistoryResult:
    data_dir = repo_root / "data"
    sessions_dir = data_dir / "chats" / "sessions"
    sessions_index_path = data_dir / "chats" / "sessions_index.json"
    knowledge_dir = data_dir / "knowledge"

    removed_chat_sessions = _clear_directory(sessions_dir)
    removed_knowledge_items = _clear_directory(knowledge_dir)

    sessions_dir.mkdir(parents=True, exist_ok=True)
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    sessions_index_path.parent.mkdir(parents=True, exist_ok=True)
    sessions_index_path.write_text(
        json.dumps({"sessions": []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ClearHistoryResult(
        removed_chat_sessions=removed_chat_sessions,
        removed_knowledge_items=removed_knowledge_items,
    )


def _clear_directory(path: Path) -> int:
    if not path.exists():
        return 0
    removed_items = 0
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed_items += 1
    return removed_items


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear local runtime chat history and generated knowledge nodes."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to clean. Defaults to this script's parent repo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = clear_history(args.repo_root.resolve())
    print(f"removed chat sessions: {result.removed_chat_sessions}")
    print(f"removed knowledge items: {result.removed_knowledge_items}")
    print("sessions index reset: data/chats/sessions_index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
