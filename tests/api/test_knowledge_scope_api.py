import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import KnowledgeNode
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.explorer import ExplorerStore
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore


def test_ask_uses_selected_folder_as_visible_knowledge_scope(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="uniform-convergence",
            title="一致收敛",
            type="definition",
            summary="在整个定义域上统一控制误差。",
            detail="一致收敛的详细定义。",
            parent_id=None,
            source="chat:test",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="group-action",
            title="群作用",
            type="definition",
            summary="群作用描述群对集合的对称变换。",
            detail="群作用的详细定义。",
            parent_id=None,
            source="chat:test",
        )
    )
    explorer = ExplorerStore(tmp_path / "explorer" / "index.json")
    scope = explorer.create_folder(
        scope="knowledge",
        name="Analysis",
        parent_folder_id=None,
    )
    explorer.move_item(
        item_type="knowledge_node",
        item_id="uniform-convergence",
        folder_id=scope.folder_id,
        sort_order=1000,
        location_source="user",
    )
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    client = TestClient(
        create_app(
            repository=repository,
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=FileSessionStore(tmp_path / "sessions"),
            explorer_store=explorer,
        )
    )

    response = client.post(
        "/api/ask",
        json={
            "question": "为什么需要一致收敛？",
            "strategy_agent_id": "auto",
            "knowledge_scope_id": scope.folder_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["knowledge_scope_id"] == scope.folder_id
    assert body["session"]["branch"]["active_node_ids"] == [
        "uniform-convergence"
    ]
    plan = body["session"]["messages"][-1]["assistant_context"][
        "orchestration_plan"
    ]
    assert plan["strategy_mode"] == "top-down"
    assert plan["knowledge_scope_label"] == "Analysis"

