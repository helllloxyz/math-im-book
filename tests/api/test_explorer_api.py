from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import KnowledgeNode
from math_im_book.storage.explorer import ExplorerStore
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore, SessionRecord


def test_sessions_explorer_synthesizes_existing_session_at_root(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(SessionRecord(session_id="chat-1", title="Vector Spaces"))
    client = TestClient(
        create_app(
            session_store=session_store,
            explorer_store=ExplorerStore(tmp_path / "explorer" / "index.json"),
        )
    )

    response = client.get("/api/explorer/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "sessions"
    assert body["tree"][0]["kind"] == "item"
    assert body["tree"][0]["item"]["session_id"] == "chat-1"


def test_create_folder_and_move_session(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(SessionRecord(session_id="chat-1", title="Vector Spaces"))
    client = TestClient(
        create_app(
            session_store=session_store,
            explorer_store=ExplorerStore(tmp_path / "explorer" / "index.json"),
        )
    )

    folder_response = client.post(
        "/api/explorer/folders",
        json={"scope": "sessions", "name": "Course", "parent_folder_id": None},
    )
    folder_id = folder_response.json()["folder"]["folder_id"]
    move_response = client.patch(
        "/api/explorer/items/session/chat-1/location",
        json={"folder_id": folder_id, "sort_order": 1000},
    )
    tree_response = client.get("/api/explorer/sessions")

    assert folder_response.status_code == 200
    assert move_response.status_code == 200
    assert move_response.json()["location"]["user_locked"] is True
    folder = tree_response.json()["tree"][0]
    assert folder["kind"] == "folder"
    assert folder["children"][0]["item"]["session_id"] == "chat-1"


def test_create_folder_with_missing_parent_returns_404(tmp_path) -> None:
    client = TestClient(
        create_app(
            explorer_store=ExplorerStore(tmp_path / "explorer" / "index.json"),
        )
    )

    response = client.post(
        "/api/explorer/folders",
        json={
            "scope": "sessions",
            "name": "Course",
            "parent_folder_id": "missing-folder",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Parent folder not found"


def test_cross_scope_move_returns_400(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves addition and scalar multiplication.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        )
    )
    client = TestClient(
        create_app(
            repository=repository,
            explorer_store=ExplorerStore(tmp_path / "explorer" / "index.json"),
        )
    )
    folder_id = client.post(
        "/api/explorer/folders",
        json={"scope": "sessions", "name": "Chats", "parent_folder_id": None},
    ).json()["folder"]["folder_id"]

    response = client.patch(
        "/api/explorer/items/knowledge_node/linear-map/location",
        json={"folder_id": folder_id, "sort_order": 1000},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Target folder is not in the item scope"


def test_knowledge_explorer_returns_foldered_node(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves addition and scalar multiplication.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        )
    )
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    client = TestClient(create_app(repository=repository, explorer_store=explorer_store))
    folder_id = client.post(
        "/api/explorer/folders",
        json={"scope": "knowledge", "name": "Linear Algebra", "parent_folder_id": None},
    ).json()["folder"]["folder_id"]
    client.patch(
        "/api/explorer/items/knowledge_node/linear-map/location",
        json={"folder_id": folder_id, "sort_order": 1000},
    )

    response = client.get("/api/explorer/knowledge")

    assert response.status_code == 200
    folder = response.json()["tree"][0]
    assert folder["folder"]["name"] == "Linear Algebra"
    assert folder["children"][0]["item"]["id"] == "linear-map"
    assert folder["children"][0]["item"]["icon"] is not None


def test_patch_knowledge_explorer_icon_returns_icon_in_tree(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves addition and scalar multiplication.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        )
    )
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    client = TestClient(create_app(repository=repository, explorer_store=explorer_store))

    response = client.patch(
        "/api/explorer/items/knowledge_node/linear-map/icon",
        json={"icon": "wave"},
    )
    tree_response = client.get("/api/explorer/knowledge")

    assert response.status_code == 200
    assert response.json()["icon"]["icon"] == "wave"
    assert tree_response.json()["tree"][0]["item"]["icon"] == "wave"
