from pathlib import Path

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
    library_root = client.get("/api/explorer/knowledge").json()["tree"][0]["folder"]

    assert folder_response.status_code == 200
    assert move_response.status_code == 200
    assert move_response.json()["location"]["user_locked"] is True
    folder = tree_response.json()["tree"][0]
    assert folder["kind"] == "folder"
    assert folder["children"][0]["item"]["session_id"] == "chat-1"
    assert session_store.load_record("chat-1").branch_context.knowledge_scope_id == (
        library_root["folder_id"]
    )


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


def test_creating_root_folder_also_creates_paired_library_scope(tmp_path: Path) -> None:
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    client = TestClient(create_app(explorer_store=explorer_store))

    response = client.post(
        "/api/explorer/folders",
        json={"scope": "sessions", "name": "Analysis", "parent_folder_id": None},
    )
    conversations_root = response.json()["folder"]
    library_roots = [
        node
        for node in client.get("/api/explorer/knowledge").json()["tree"]
        if node["kind"] == "folder" and node["folder"]["name"] == "Analysis"
    ]

    assert response.status_code == 200
    assert conversations_root["scope_id"]
    assert len(library_roots) == 1
    assert library_roots[0]["folder"]["scope_id"] == conversations_root["scope_id"]


def test_move_missing_item_does_not_create_stale_explorer_metadata(tmp_path: Path) -> None:
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    client = TestClient(create_app(explorer_store=explorer_store))

    response = client.patch(
        "/api/explorer/items/session/missing/location",
        json={"folder_id": None, "sort_order": 1000},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"
    assert explorer_store.load_payload()["locations"] == []


def test_icon_update_for_missing_knowledge_note_returns_404(tmp_path: Path) -> None:
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    client = TestClient(create_app(explorer_store=explorer_store))

    response = client.patch(
        "/api/explorer/items/knowledge_node/missing/icon",
        json={"icon": "atom"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge note not found"
    assert explorer_store.load_payload()["item_icons"] == []


def test_knowledge_explorer_returns_foldered_node(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat:1",
            title="Linear Algebra Foundations",
            icon="linear-algebra",
        )
    )
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
    client = TestClient(
        create_app(
            repository=repository,
            session_store=session_store,
            explorer_store=explorer_store,
        )
    )
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
    assert folder["children"][0]["item"]["icon"] == "linear-algebra"


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
        json={"icon": "topology"},
    )
    tree_response = client.get("/api/explorer/knowledge")

    assert response.status_code == 200
    assert response.json()["icon"]["icon"] == "topology"
    assert tree_response.json()["tree"][0]["item"]["icon"] == "topology"


def test_organize_knowledge_groups_unlocked_root_nodes_and_preserves_user_placement(
    tmp_path: Path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    for node in (
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="definition",
            summary="A set with vector operations.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        ),
        KnowledgeNode(
            id="basis-proof",
            title="Basis Extension Proof",
            type="proof",
            summary="Extends a linearly independent set.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        ),
        KnowledgeNode(
            id="manual-note",
            title="Manual Note",
            type="atomic",
            summary="A user-positioned note.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        ),
    ):
        repository.save_node(node)
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    explorer_store.move_item(
        item_type="knowledge_node",
        item_id="manual-note",
        folder_id=None,
        sort_order=1000,
        location_source="user",
    )
    client = TestClient(create_app(repository=repository, explorer_store=explorer_store))

    response = client.post("/api/explorer/knowledge/organize")
    second_response = client.post("/api/explorer/knowledge/organize")

    assert response.status_code == 200
    assert response.json() == {
        "scope": "knowledge",
        "organized_count": 2,
        "folders_created": 2,
    }
    assert second_response.json()["organized_count"] == 0
    assert explorer_store.find_location("knowledge_node", "vector-space").path_cached == (
        "/Definitions/vector-space"
    )
    assert explorer_store.find_location("knowledge_node", "basis-proof").path_cached == (
        "/Proofs & Derivations/basis-proof"
    )
    manual_location = explorer_store.find_location("knowledge_node", "manual-note")
    assert manual_location is not None
    assert manual_location.folder_id is None
    assert manual_location.user_locked is True


def test_organize_knowledge_keeps_categories_inside_the_library_scope(
    tmp_path: Path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="metric-space",
            title="Metric Space",
            type="definition",
            summary="A set equipped with a metric.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        )
    )
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    _conversations, library = explorer_store.create_scope_root(
        name="Analysis",
        primary_scope="sessions",
    )
    explorer_store.ensure_item_location(
        item_type="knowledge_node",
        item_id="metric-space",
        folder_id=library.folder_id,
        location_source="system",
    )
    client = TestClient(
        create_app(repository=repository, explorer_store=explorer_store)
    )

    response = client.post("/api/explorer/knowledge/organize")

    assert response.status_code == 200
    assert explorer_store.find_location(
        "knowledge_node",
        "metric-space",
    ).path_cached == "/Analysis/Definitions/metric-space"
