import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import (
    KnowledgeNode,
    PendingDraftRequest,
    ProviderProfile,
    ProviderResult,
    SessionAssistantContext,
    SessionBranchContext,
)
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.services.providers import FakeProviderGateway
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore, SessionMessage, SessionRecord


def _write_credentials(tmp_path, credentials: list[dict[str, object]] | None = None):
    path = tmp_path / "credentials.json"
    path.write_text(
        json.dumps({"credentials": credentials or []}),
        encoding="utf-8",
    )
    return FileCredentialRegistry(path)


def _build_client(
    tmp_path,
    *,
    session_store: FileSessionStore | None = None,
    credential_registry: FileCredentialRegistry | None = None,
    provider_gateway: FakeProviderGateway | None = None,
):
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=provider_gateway,
        auto_start=False,
    )
    return TestClient(
        create_app(
            repository=repository,
            credential_registry=credential_registry or _write_credentials(tmp_path),
            session_store=session_store or FileSessionStore(tmp_path / "sessions"),
            provider_gateway=provider_gateway,
            knowledge_job_repository=knowledge_jobs,
        )
    ), repository, knowledge_jobs


def test_empty_selected_text_is_rejected(tmp_path) -> None:
    client, _, _ = _build_client(tmp_path)

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "   ",
            "prompt_kind": "definition",
            "source": {"type": "knowledge-node", "node_id": "node-1"},
        },
    )

    assert response.status_code == 400


def test_unsupported_prompt_kind_is_rejected(tmp_path) -> None:
    client, _, _ = _build_client(tmp_path)

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "Linear map",
            "prompt_kind": "summary",
            "source": {"type": "knowledge-node", "node_id": "node-1"},
        },
    )

    assert response.status_code == 400


def test_missing_provider_profile_returns_503_and_does_not_queue_job(tmp_path) -> None:
    client, repository, knowledge_jobs = _build_client(tmp_path)
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves vector operations.",
            detail="A linear map preserves addition and scalar multiplication.",
            parent_id=None,
            source="session-1",
            references=[],
            status="ready",
        )
    )

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "Linear maps preserve structure.",
            "prompt_kind": "definition",
            "source": {"type": "knowledge-node", "node_id": "linear-map"},
        },
    )

    assert response.status_code == 503
    assert knowledge_jobs.list_jobs() == []


def test_knowledge_node_source_submits_job_with_selected_node_ids_and_text(
    tmp_path,
) -> None:
    client, repository, knowledge_jobs = _build_client(
        tmp_path,
        credential_registry=_write_credentials(
            tmp_path,
            [
                {
                    "credential_id": "gemini-main",
                    "api_key": "secret",
                    "provider_type": "gemini",
                }
            ],
        ),
    )
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves vector operations.",
            detail="A linear map preserves addition and scalar multiplication.",
            parent_id=None,
            source="session-1",
            references=[],
            status="ready",
        )
    )

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "  Linear maps preserve structure.  ",
            "prompt_kind": "definition",
            "source": {"type": "knowledge-node", "node_id": "linear-map"},
            "conversation_model": {
                "provider_type": "gemini",
                "model": "gemini-2.5-flash",
                "credential_id": "gemini-main",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["anchors"] == []

    job = knowledge_jobs.get_job(payload["job_id"])
    assert job is not None
    assert job.selected_node_ids == ["linear-map"]
    assert "Linear maps preserve structure." in job.question
    assert job.draft_requests == [
        PendingDraftRequest(
            title="Linear maps preserve structure Definition",
            draft_type="definition",
            reason="Draft a definition from the selected text.",
        )
    ]


def test_chat_message_source_preserves_session_and_source_message_ids(
    tmp_path,
) -> None:
    credential_registry = _write_credentials(
        tmp_path,
        [
            {
                "credential_id": "gemini-main",
                "api_key": "secret",
                "provider_type": "gemini",
            }
        ],
    )
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            provider_profile=ProviderProfile(
                provider_type="gemini",
                model="gemini-2.5-flash",
                credential_id="gemini-main",
            ),
            branch_context=SessionBranchContext(
                active_node_ids=["vector-space"],
                active_symbols={"V": "vector space"},
            ),
            messages=[
                SessionMessage(role="user", content="What is a vector space?"),
                SessionMessage(
                    role="assistant",
                    message_id="msg-1",
                    content="A vector space is ...",
                    assistant_context=SessionAssistantContext(
                        referenced_node_ids=["vector-space"],
                    ),
                ),
            ],
        )
    )
    client, repository, knowledge_jobs = _build_client(
        tmp_path,
        session_store=session_store,
        credential_registry=credential_registry,
        provider_gateway=FakeProviderGateway(
            ProviderResult(
                output_text='{"summary":"A proof note.","detail":"A proof detail."}',
                provider_name="gemini",
            )
        ),
    )

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "Proof sketch",
            "prompt_kind": "proof",
            "source": {
                "type": "chat-message",
                "session_id": "chat-1",
                "message_id": "msg-1",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    job = knowledge_jobs.get_job(payload["job_id"])
    assert job is not None
    assert job.session_id == "chat-1"
    assert job.source_message_id == "msg-1"
    assert job.selected_node_ids == ["vector-space"]
    assert job.symbol_constraints == {"V": "vector space"}
    assert job.draft_requests[0].draft_type == "proof"

    completed = knowledge_jobs.run_job(job.job_id)
    assert completed.anchors[0].status == "ready"
    assert repository.get_node(completed.anchors[0].node_id).type == "proof"


def test_long_multiline_selected_text_uses_short_title_seed(tmp_path) -> None:
    credential_registry = _write_credentials(
        tmp_path,
        [
            {
                "credential_id": "gemini-main",
                "api_key": "secret",
                "provider_type": "gemini",
            }
        ],
    )
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-2",
            provider_profile=ProviderProfile(
                provider_type="gemini",
                model="gemini-2.5-flash",
                credential_id="gemini-main",
            ),
            messages=[
                SessionMessage(role="user", content="What is a linear map?"),
                SessionMessage(
                    role="assistant",
                    message_id="msg-2",
                    content="A linear map preserves operations.",
                    assistant_context=SessionAssistantContext(
                        referenced_node_ids=["linear-map"],
                    ),
                ),
            ],
        )
    )
    client, repository, knowledge_jobs = _build_client(
        tmp_path,
        session_store=session_store,
        credential_registry=credential_registry,
        provider_gateway=FakeProviderGateway(
            ProviderResult(
                output_text='{"summary":"A summary.","detail":"A detail."}',
                provider_name="gemini",
            )
        ),
    )
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves vector operations.",
            detail="A linear map preserves addition and scalar multiplication.",
            parent_id=None,
            source="session-1",
            references=[],
            status="ready",
        )
    )
    selected_text = (
        "\n\n"
        "A very long selected passage that should be shortened before it becomes a title seed.\n"
        "The second line should not appear in the title.\n"
    )

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": selected_text,
            "prompt_kind": "example",
            "source": {
                "type": "chat-message",
                "session_id": "chat-2",
                "message_id": "msg-2",
            },
        },
    )

    assert response.status_code == 200
    job = knowledge_jobs.get_job(response.json()["job_id"])
    assert job is not None
    assert job.draft_requests[0].title.endswith("Application Example")
    assert "\n" not in job.draft_requests[0].title
    assert selected_text not in job.draft_requests[0].title

    completed = knowledge_jobs.run_job(job.job_id)
    assert completed.anchors[0].label == job.draft_requests[0].title
    assert completed.anchors[0].label.endswith("Application Example")
    assert "\n" not in completed.anchors[0].label


def test_missing_node_returns_404(tmp_path) -> None:
    client, _, _ = _build_client(tmp_path)

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "Linear map",
            "prompt_kind": "example",
            "source": {"type": "knowledge-node", "node_id": "missing"},
        },
    )

    assert response.status_code == 404


def test_missing_session_or_message_returns_404(tmp_path) -> None:
    client, _, _ = _build_client(tmp_path)

    session_response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "Linear map",
            "prompt_kind": "example",
            "source": {
                "type": "chat-message",
                "session_id": "missing",
                "message_id": "msg-1",
            },
        },
    )
    message_response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "Linear map",
            "prompt_kind": "example",
            "source": {
                "type": "chat-message",
                "session_id": "chat-1",
                "message_id": "missing",
            },
        },
    )

    assert session_response.status_code == 404
    assert message_response.status_code == 404
