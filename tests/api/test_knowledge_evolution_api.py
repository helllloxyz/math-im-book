import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import KnowledgeNode
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore


def test_knowledge_node_update_creates_a_new_revision(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="uniform-convergence",
            title="一致收敛",
            type="definition",
            summary="旧摘要",
            detail="旧正文",
            parent_id=None,
            source="chat:test",
        )
    )
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    client = TestClient(
        create_app(
            repository=repository,
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=FileSessionStore(tmp_path / "sessions"),
        )
    )

    response = client.patch(
        "/api/nodes/uniform-convergence",
        json={"summary": "新摘要", "detail": "扩充后的正文"},
    )

    assert response.status_code == 200
    node = response.json()["node"]
    assert node["revision"] == 2
    assert node["summary"] == "新摘要"
    assert node["detail"] == "扩充后的正文"
    assert node["updated_at"]
    assert repository.get_node("uniform-convergence").revision == 2

