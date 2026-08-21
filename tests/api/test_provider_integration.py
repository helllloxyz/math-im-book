import json
import time

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import (
    KnowledgeNode,
    ProviderProfile,
    ProviderResult,
)
from math_im_book.services.providers import FakeProviderGateway, ProviderRequest
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore


def test_ask_endpoint_uses_provider_profile_and_persists_session_choice(tmp_path) -> None:
    knowledge_repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="A linear map preserves addition and scalar multiplication.",
            detail="A map T: V -> W is linear when T(u + v) = T(u) + T(v).",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
            symbols={"T": "linear map from V to W"},
        )
    )
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(
        json.dumps(
            {
                "credentials": [
                    {"credential_id": "gemini-main", "api_key": "gemini-secret"}
                ]
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(
        create_app(
            repository=knowledge_repository,
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=FileSessionStore(tmp_path / "sessions"),
            provider_gateway=FakeProviderGateway(
                ProviderResult(
                    output_text="External provider answer.",
                    provider_name="gemini",
                )
            ),
        )
    )

    response = client.post(
        "/api/ask",
        json={
            "session_id": "chat-1",
            "question": "What is a linear map?",
            "provider_profile": {
                "provider_type": "gemini",
                "model": "gemini-2.5-flash",
                "credential_id": "gemini-main",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]["assistant_text"] == "External provider answer."
    assert body["session"]["provider_profile"]["provider_type"] == "gemini"

    follow_up = client.post(
        "/api/ask",
        json={
            "session_id": "chat-1",
            "question": "What is a linear map?",
        },
    )

    assert follow_up.status_code == 200
    assert follow_up.json()["action"]["action_type"] == "reuse_answer"
    assert follow_up.json()["session"]["provider_profile"]["model"] == "gemini-2.5-flash"
    assert follow_up.json()["session"]["branch"] == {
        "branch_id": None,
        "parent_session_id": None,
        "root_session_id": None,
        "focus_question": None,
        "fork_anchor": None,
        "active_node_ids": [],
        "summary_node_ids": [],
        "active_symbols": {},
    }
    assert follow_up.json()["answer"]["assistant_text"] == "External provider answer."


def test_default_knowledge_job_repository_uses_provider_gateway(tmp_path) -> None:
    knowledge_repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(
        json.dumps(
            {
                "credentials": [
                    {"credential_id": "gemini-main", "api_key": "gemini-secret"}
                ]
            }
        ),
        encoding="utf-8",
    )
    session_store = FileSessionStore(tmp_path / "sessions")
    client = TestClient(
        create_app(
            repository=knowledge_repository,
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=session_store,
            provider_gateway=_KnowledgeCompileGateway(),
        )
    )

    response = client.post(
        "/api/ask",
        json={
            "session_id": "chat-compile",
            "question": "linear algebra",
            "provider_profile": {
                "provider_type": "gemini",
                "model": "gemini-2.5-flash",
                "credential_id": "gemini-main",
            },
        },
    )

    assert response.status_code == 200
    job_id = response.json()["answer"]["knowledge_job_id"]
    assert job_id is not None
    for _ in range(20):
        job_response = client.get(f"/api/knowledge-jobs/{job_id}")
        assert job_response.status_code == 200
        if job_response.json()["status"] == "completed":
            break
        time.sleep(0.01)

    node = knowledge_repository.get_node("linear-algebra")
    assert node.summary == "Provider compiled summary."
    assert node.detail == "Provider compiled detail."
    record = session_store.load_record("chat-compile")
    assistant_context = record.messages[-1].assistant_context
    assert assistant_context.anchors[0].status == "ready"
    assert assistant_context.anchors[0].node_id == "linear-algebra"


class _KnowledgeCompileGateway:
    def generate(
        self,
        profile: ProviderProfile,
        request: ProviderRequest,
    ) -> ProviderResult:
        if "context planner" in request.system_instruction:
            return ProviderResult(
                output_text=(
                    '{"route":"draft_first_then_answer",'
                    '"intent":"definition",'
                    '"persistence_decision":"persist_first",'
                    '"confidence":0.92,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[{"title":"Linear Algebra",'
                    '"draft_type":"missing_definition",'
                    '"reason":"The knowledge base is missing this definition."}],'
                    '"user_visible_summary":"Existing knowledge is insufficient."}'
                ),
                provider_name="gemini",
            )
        if "compiling a math knowledge node" in request.system_instruction:
            return ProviderResult(
                output_text=(
                    '{"summary":"Provider compiled summary.",'
                    '"detail":"Provider compiled detail."}'
                ),
                provider_name="gemini",
            )
        return ProviderResult(output_text="Assistant answer.", provider_name="gemini")

    def generate_stream(
        self,
        profile: ProviderProfile,
        request: ProviderRequest,
    ) -> object:
        yield self.generate(profile, request).output_text
