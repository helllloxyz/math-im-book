import json
from pathlib import Path

import pytest

from math_im_book.storage.explorer import (
    ExplorerFolderConflictError,
    ExplorerInvalidMoveError,
    ExplorerStore,
)


def test_create_folder_rejects_duplicate_sibling_names(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)

    with pytest.raises(ExplorerFolderConflictError):
        store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)


def test_same_folder_name_is_allowed_in_different_scopes(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    knowledge = store.create_folder(scope="knowledge", name="Archive", parent_folder_id=None)
    sessions = store.create_folder(scope="sessions", name="Archive", parent_folder_id=None)

    assert knowledge.folder_id != sessions.folder_id
    assert knowledge.scope == "knowledge"
    assert sessions.scope == "sessions"


def test_scope_root_creates_paired_conversation_and_library_folders(
    tmp_path: Path,
) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    conversations, library = store.create_scope_root(
        name="Linear Algebra",
        primary_scope="sessions",
    )
    child = store.create_folder(
        scope="sessions",
        name="Week 1",
        parent_folder_id=conversations.folder_id,
    )

    assert conversations.scope_id is not None
    assert library.scope_id == conversations.scope_id
    assert child.scope_id == conversations.scope_id
    assert store.paired_scope_root(
        child.folder_id,
        target_scope="knowledge",
    ).folder_id == library.folder_id


def test_scope_root_rename_updates_its_library_pair(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    conversations, library = store.create_scope_root(
        name="Algebra",
        primary_scope="sessions",
    )

    store.rename_scope_root(conversations.folder_id, "Abstract Algebra")

    assert store.get_folder(conversations.folder_id).name == "Abstract Algebra"
    assert store.get_folder(library.folder_id).name == "Abstract Algebra"


def test_rename_folder_rejects_duplicate_sibling_names(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)
    folder = store.create_folder(scope="knowledge", name="Topology", parent_folder_id=None)

    with pytest.raises(ExplorerFolderConflictError):
        store.rename_folder(folder.folder_id, name="Linear Algebra")


def test_rename_folder_refreshes_nested_item_location_paths(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    parent = store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)
    child = store.create_folder(
        scope="knowledge",
        name="Vector Spaces",
        parent_folder_id=parent.folder_id,
    )
    store.move_item(
        item_type="knowledge_node",
        item_id="linear-map",
        folder_id=child.folder_id,
        sort_order=2000,
        location_source="user",
    )

    store.rename_folder(parent.folder_id, name="Matrices")

    location = store.find_location("knowledge_node", "linear-map")

    assert location is not None
    assert location.path_cached == "/Matrices/Vector Spaces/linear-map"


def test_move_item_sets_user_locked_location_and_cached_path(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)

    location = store.move_item(
        item_type="knowledge_node",
        item_id="linear-map",
        folder_id=folder.folder_id,
        sort_order=2000,
        location_source="user",
    )

    assert location.item_type == "knowledge_node"
    assert location.item_id == "linear-map"
    assert location.folder_id == folder.folder_id
    assert location.user_locked is True
    assert location.path_cached == "/Linear Algebra/linear-map"


def test_non_user_move_clears_user_locked_flag(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)

    store.move_item(
        item_type="knowledge_node",
        item_id="linear-map",
        folder_id=folder.folder_id,
        sort_order=2000,
        location_source="user",
    )

    location = store.move_item(
        item_type="knowledge_node",
        item_id="linear-map",
        folder_id=folder.folder_id,
        sort_order=3000,
        location_source="agent",
    )

    assert location.location_source == "agent"
    assert location.user_locked is False


def test_ensure_item_location_creates_system_root_location_only_when_missing(
    tmp_path: Path,
) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    location = store.ensure_item_location(
        item_type="session",
        item_id="chat-1",
        sort_order=2500,
    )

    assert location.location_source == "system"
    assert location.folder_id is None
    assert location.path_cached == "/chat-1"
    assert store.load_payload()["locations"] == [
        {
            "item_type": "session",
            "item_id": "chat-1",
            "folder_id": None,
            "sort_order": 2500,
            "path_cached": "/chat-1",
            "location_source": "system",
            "user_locked": False,
            "updated_at": location.updated_at,
        }
    ]


def test_ensure_item_location_accepts_folder_and_location_source(
    tmp_path: Path,
) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Course", parent_folder_id=None)

    location = store.ensure_item_location(
        item_type="session",
        item_id="chat-1",
        folder_id=folder.folder_id,
        location_source="agent",
    )

    assert location.folder_id == folder.folder_id
    assert location.location_source == "agent"
    assert location.user_locked is False
    assert location.path_cached == "/Course/chat-1"


def test_ensure_item_location_returns_existing_user_location_without_overwriting(
    tmp_path: Path,
) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Course", parent_folder_id=None)
    original = store.move_item(
        item_type="session",
        item_id="chat-1",
        folder_id=folder.folder_id,
        sort_order=1000,
        location_source="user",
    )

    location = store.ensure_item_location(item_type="session", item_id="chat-1")

    assert location.item_id == original.item_id
    assert location.location_source == "user"
    assert location.user_locked is True
    assert location.folder_id == folder.folder_id
    assert location.path_cached == "/Course/chat-1"


def test_cross_scope_move_is_rejected(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Chats", parent_folder_id=None)

    with pytest.raises(ExplorerInvalidMoveError):
        store.move_item(
            item_type="knowledge_node",
            item_id="linear-map",
            folder_id=folder.folder_id,
            sort_order=1000,
            location_source="user",
        )


def test_knowledge_scope_includes_nodes_in_nested_folders(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    parent = store.create_folder(
        scope="knowledge",
        name="Analysis",
        parent_folder_id=None,
    )
    child = store.create_folder(
        scope="knowledge",
        name="Convergence",
        parent_folder_id=parent.folder_id,
    )
    store.move_item(
        item_type="knowledge_node",
        item_id="uniform-convergence",
        folder_id=child.folder_id,
        sort_order=1000,
        location_source="user",
    )

    assert store.list_item_ids_in_folder(
        item_type="knowledge_node",
        folder_id=parent.folder_id,
        include_descendants=True,
    ) == ["uniform-convergence"]
    assert store.list_item_ids_in_folder(
        item_type="knowledge_node",
        folder_id=parent.folder_id,
        include_descendants=False,
    ) == []


def test_delete_non_empty_folder_is_rejected(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Course", parent_folder_id=None)
    store.move_item(
        item_type="session",
        item_id="chat-1",
        folder_id=folder.folder_id,
        sort_order=1000,
        location_source="user",
    )

    with pytest.raises(ExplorerInvalidMoveError):
        store.delete_folder(folder.folder_id)


def test_delete_empty_folder_removes_folder_from_payload(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Course", parent_folder_id=None)

    store.delete_folder(folder.folder_id)

    assert store.load_payload()["folders"] == []


def test_synthesized_locations_are_not_persisted_until_moved(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    tree = store.build_tree(
        scope="sessions",
        items=[
            {
                "item_type": "session",
                "item_id": "chat-1",
                "title": "Vector Spaces",
            }
        ],
    )

    assert tree[0]["kind"] == "item"
    assert tree[0]["item"]["item_id"] == "chat-1"
    assert tree[0]["item"]["title"] == "Vector Spaces"
    assert tree[0]["location"]["folder_id"] is None
    assert tree[0]["location"]["path_cached"] == "/chat-1"
    assert store.load_payload()["locations"] == []


def test_rename_folder_accepts_positional_name(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Drafts", parent_folder_id=None)

    renamed = store.rename_folder(folder.folder_id, "Course")

    assert renamed.name == "Course"


def test_find_location_returns_persisted_location_and_none_when_absent(
    tmp_path: Path,
) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)
    store.move_item(
        item_type="knowledge_node",
        item_id="linear-map",
        folder_id=folder.folder_id,
        sort_order=1000,
        location_source="user",
    )

    location = store.find_location("knowledge_node", "linear-map")

    assert location is not None
    assert location.item_type == "knowledge_node"
    assert location.item_id == "linear-map"
    assert location.folder_id == folder.folder_id
    assert store.find_location("session", "missing") is None


def test_item_icon_customization_is_applied_to_tree_items(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    icon = store.set_item_icon(
        item_type="knowledge_node",
        item_id="linear-map",
        icon="atom",
    )
    tree = store.build_tree(
        scope="knowledge",
        items=[
            {
                "item_type": "knowledge_node",
                "item_id": "linear-map",
                "title": "Linear Map",
            }
        ],
    )

    assert icon["item_type"] == "knowledge_node"
    assert icon["item_id"] == "linear-map"
    assert icon["icon"] == "atom"
    assert tree[0]["item"]["icon"] == "atom"


def test_remove_item_cleans_location_and_icon_metadata(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Course", parent_folder_id=None)
    store.move_item(
        item_type="session",
        item_id="chat-1",
        folder_id=folder.folder_id,
        sort_order=1000,
        location_source="user",
    )
    store.set_item_icon(item_type="session", item_id="chat-1", icon="sigma")

    assert store.remove_item(item_type="session", item_id="chat-1") is True
    assert store.find_location("session", "chat-1") is None
    assert store.load_payload()["item_icons"] == []
    store.delete_folder(folder.folder_id)


def test_remove_missing_item_is_a_noop(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    assert store.remove_item(item_type="session", item_id="missing") is False


def test_stale_folder_location_falls_back_to_root_tree_item(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    store.load_payload()
    store.index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "folders": [],
                "locations": [
                    {
                        "item_type": "session",
                        "item_id": "chat-1",
                        "folder_id": "missing-folder",
                        "sort_order": 1000,
                        "path_cached": "/Ghost/chat-1",
                        "location_source": "system",
                        "user_locked": False,
                        "updated_at": "2026-04-19T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    tree = store.build_tree(
        scope="sessions",
        items=[
            {
                "item_type": "session",
                "item_id": "chat-1",
                "title": "Vector Spaces",
            }
        ],
    )

    assert tree[0]["kind"] == "item"
    assert tree[0]["item"]["item_id"] == "chat-1"
    assert tree[0]["location"]["folder_id"] is None
    assert tree[0]["location"]["path_cached"] == "/chat-1"
