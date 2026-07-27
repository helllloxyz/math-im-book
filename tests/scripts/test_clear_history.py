from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_clear_history_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "clear_history.py"
    spec = importlib.util.spec_from_file_location("clear_history", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["clear_history"] = module
    spec.loader.exec_module(module)
    return module


def test_clear_history_removes_chat_sessions_and_knowledge_nodes(tmp_path) -> None:
    module = _load_clear_history_module()
    sessions_dir = tmp_path / "data" / "chats" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "chat-1").mkdir()
    (sessions_dir / "chat-1" / "messages.jsonl").write_text("{}", encoding="utf-8")
    (sessions_dir / "chat-1" / "session.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "chats" / "sessions_index.json").write_text(
        json.dumps({"sessions": [{"session_id": "chat-1"}]}),
        encoding="utf-8",
    )
    knowledge_dir = tmp_path / "data" / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "node.md").write_text("---\nid: node\n---\nbody", encoding="utf-8")

    result = module.clear_history(tmp_path)

    assert result.removed_chat_sessions == 1
    assert result.removed_knowledge_items == 1
    assert sessions_dir.exists()
    assert list(sessions_dir.iterdir()) == []
    assert json.loads((tmp_path / "data" / "chats" / "sessions_index.json").read_text()) == {
        "sessions": []
    }
    assert knowledge_dir.exists()
    assert list(knowledge_dir.iterdir()) == []
