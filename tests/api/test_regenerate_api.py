import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import (
    KnowledgeNode,
    ModelSelection,
    ProviderProfile,
    ProviderResult,
    SessionAssistantContext,
)
from math_im_book.services.providers import FakeProviderGateway
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore, SessionMessage, SessionRecord


def test_regenerate_endpoint_replaces_the_last_assistant_message(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    knowledge_repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="A linear map preserves addition and scalar multiplication.",
            detail="Detailed linear map discussion.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            conversation_model=ModelSelection(
                provider_id="gemini",
                provider_type="gemini",
                model="gemini-2.5-flash",
                credential_id="gemini-main",
            ),
            provider_profile=ProviderProfile(
                provider_type="gemini",
                model="gemini-2.5-flash",
                credential_id="gemini-main",
            ),
            messages=[
                SessionMessage(role="user", content="What is a linear map?"),
                SessionMessage(
                    role="assistant",
                    content="Original answer",
                    assistant_context=SessionAssistantContext(
                        action_type="answer",
                        referenced_node_ids=["linear-map"],
                    ),
                ),
            ],
        )
    )
    original_record = session_store.load_local_record("chat-1")
    assert original_record is not None
    assistant_message_id = original_record.messages[-1].message_id
    client = TestClient(
        create_app(
            repository=knowledge_repository,
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=session_store,
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="Regenerated answer", provider_name="gemini")
            ),
        )
    )

    response = client.post(
        f"/api/sessions/chat-1/messages/{assistant_message_id}/regenerate",
        json={
            "provider_profile": {
                "provider_type": "gemini",
                "model": "gemini-2.5-flash",
                "credential_id": "gemini-main",
            },
            "answer_style_id": "default",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["content"] == "What is a linear map?"
    assert body["messages"][1]["content"] == "Regenerated answer"
    assert body["messages"][1]["message_id"] != assistant_message_id
    assert body["conversation_model"] == {
        "provider_id": "gemini",
        "provider_type": "gemini",
        "model": "gemini-2.5-flash",
        "credential_id": "gemini-main",
    }


def test_regenerate_endpoint_rejects_non_latest_or_non_assistant_messages(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            messages=[
                SessionMessage(role="user", content="First question"),
                SessionMessage(role="assistant", content="First answer"),
                SessionMessage(role="user", content="Second question"),
                SessionMessage(role="assistant", content="Second answer"),
            ],
        )
    )
    record = session_store.load_local_record("chat-1")
    assert record is not None
    first_user_id = record.messages[0].message_id
    first_assistant_id = record.messages[1].message_id
    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=session_store,
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="unused", provider_name="gemini")
            ),
        )
    )

    non_assistant = client.post(
        f"/api/sessions/chat-1/messages/{first_user_id}/regenerate",
        json={"answer_style_id": "default"},
    )
    non_latest = client.post(
        f"/api/sessions/chat-1/messages/{first_assistant_id}/regenerate",
        json={"answer_style_id": "default"},
    )

    assert non_assistant.status_code == 409
    assert non_assistant.json()["detail"] == "Only the latest assistant message can be regenerated"
    assert non_latest.status_code == 409
    assert non_latest.json()["detail"] == "Only the latest assistant message can be regenerated"
