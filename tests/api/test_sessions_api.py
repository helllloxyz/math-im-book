import json

from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import (
    KnowledgeNode,
    ProviderProfile,
    ProviderResult,
    SessionBranchContext,
    SessionForkAnchor,
)
from math_im_book.services.providers import FakeProviderGateway
from math_im_book.storage.credentials import FileCredentialRegistry
from math_im_book.storage.explorer import ExplorerStore
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore, SessionMessage, SessionRecord


class SequencedProviderGateway:
    def __init__(self, results: list[ProviderResult]) -> None:
        self.results = list(results)
        self.requests: list[object] = []

    def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
        self.requests.append(request)
        return self.results.pop(0)

    def generate_stream(self, profile: ProviderProfile, request: object):
        yield self.generate(profile, request).output_text


def test_sessions_endpoint_returns_provider_profile_and_history(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Linear Maps",
            icon="function",
            provider_profile=ProviderProfile(
                provider_type="gemini",
                model="gemini-2.5-flash",
                credential_id="gemini-main",
            ),
            messages=[
                SessionMessage(role="user", content="What is a linear map?"),
                SessionMessage(role="assistant", content="A linear map preserves addition."),
            ],
        )
    )
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

    response = client.get("/api/sessions/chat-1")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "chat-1"
    assert body["title"] == "Linear Maps"
    assert body["icon"] == "function"
    assert body["default_answer_style_id"] is None
    assert body["strategy_agent_id"] == "top-down"
    assert body["provider_profile"]["provider_type"] == "gemini"
    assert body["branch"] == {
        "branch_id": None,
        "parent_session_id": None,
        "root_session_id": None,
        "focus_question": None,
        "fork_anchor": None,
        "active_node_ids": [],
        "summary_node_ids": [],
        "active_symbols": {},
    }
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["message_id"]
    assert body["messages"][0]["created_at"]


def test_answer_styles_endpoint_returns_markdown_metadata(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=FileSessionStore(tmp_path / "sessions"),
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="unused", provider_name="gemini")
            ),
        )
    )

    response = client.get("/api/answer-styles")

    assert response.status_code == 200
    body = response.json()
    assert body["default_style_id"] == "default"
    assert [style["answer_style_id"] for style in body["styles"]] == [
        "default",
        "concise",
        "step-by-step",
        "intuitive",
        "rigorous",
    ]
    assert body["styles"][0]["is_default"] is True
    assert body["styles"][0]["instructions"].startswith("# Default")


def test_strategy_agents_endpoint_returns_markdown_metadata(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=FileSessionStore(tmp_path / "sessions"),
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="unused", provider_name="gemini")
            ),
        )
    )

    response = client.get("/api/strategy-agents")

    assert response.status_code == 200
    body = response.json()
    assert body["default_strategy_agent_id"] == "top-down"
    assert [agent["strategy_agent_id"] for agent in body["agents"]] == [
        "top-down",
        "raw",
    ]
    assert body["agents"][0]["is_default"] is True
    assert body["agents"][0]["instructions"].startswith("# Top Down")


def test_sessions_endpoint_exposes_provider_metadata_for_assistant_messages(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-2",
            title="Generalization",
            icon="wave",
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="gpt-4.1-mini",
                credential_id="openai-main",
            ),
            messages=[
                SessionMessage(role="user", content="Why is T linear?"),
                SessionMessage(
                    role="assistant",
                    content="Because it preserves vector space operations.",
                    provider_name="openai_compatible",
                    raw_response_meta={"request_id": "req-1"},
                ),
            ],
        )
    )
    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=session_store,
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="unused", provider_name="openai_compatible")
            ),
        )
    )

    response = client.get("/api/sessions/chat-2")

    assert response.status_code == 200
    body = response.json()
    assert body["messages"][1]["provider_name"] == "openai_compatible"
    assert body["messages"][1]["raw_response_meta"] == {"request_id": "req-1"}
    assert body["messages"][1]["assistant_context"] == {
        "action_type": None,
        "referenced_node_ids": [],
        "anchors": [],
        "symbol_conflicts": [],
        "alignment_notes": [],
        "compact_summary": None,
        "orchestration_plan": None,
        "state_items": [],
    }


def test_ask_persists_assistant_plan_and_state_for_agent_state_and_sessions(
    tmp_path,
) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-3",
            title="Linear Algebra",
        )
    )
    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=session_store,
            provider_gateway=SequencedProviderGateway(
                [
                    ProviderResult(
                        output_text=(
                            '{"route":"answer_then_suggest_drafts",'
                            '"intent":"broad_overview",'
                            '"persistence_decision":"suggest_drafts",'
                            '"confidence":0.82,'
                            '"selected_node_ids":[],'
                            '"detected_scope_ids":["linear-algebra"],'
                            '"profile_layers_used":["global_user","scope_memory:linear-algebra"],'
                            '"profile_context_summary":"识别为线性代数范围。",'
                            '"candidate_drafts":[{"title":"Vector Space",'
                            '"draft_type":"definition",'
                            '"reason":"Foundational reusable concept."}],'
                            '"user_visible_summary":"先给概览，并建议知识点。"}'
                        ),
                        provider_name="gemini",
                    ),
                    ProviderResult(
                        output_text="线性代数研究向量空间和线性映射。",
                        provider_name="gemini",
                    ),
                ]
            ),
        )
    )

    ask_response = client.post(
        "/api/ask",
        json={
            "session_id": "chat-3",
            "question": "线性代数",
            "provider_profile": {
                "provider_type": "gemini",
                "model": "gemini-2.5-flash",
                "credential_id": "gemini-main",
            },
        },
    )

    assert ask_response.status_code == 200
    assert ask_response.json()["action"]["action_type"] == "answer_then_suggest_drafts"

    agent_state_response = client.get("/api/agent-state?session_id=chat-3")
    assert agent_state_response.status_code == 200
    agent_state = agent_state_response.json()
    assert agent_state["current_turn"]["route"] == "answer_then_suggest_drafts"
    assert agent_state["knowledge_queue"][0]["title"] == "Vector Space"

    session_response = client.get("/api/sessions/chat-3")
    assert session_response.status_code == 200
    assistant_context = session_response.json()["messages"][-1]["assistant_context"]
    assert assistant_context["orchestration_plan"]["route"] == "answer_then_suggest_drafts"
    assert assistant_context["state_items"][0]["title"] == "Vector Space"


def test_sessions_list_endpoint_returns_recent_sessions_with_provider_summary(
    tmp_path,
) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            provider_profile=ProviderProfile(
                provider_type="gemini",
                model="gemini-2.5-flash",
                credential_id="gemini-main",
            ),
            messages=[
                SessionMessage(role="user", content="First question"),
                SessionMessage(role="assistant", content="First answer"),
            ],
        )
    )
    session_store.save_record(
        SessionRecord(
            session_id="chat-2",
            title="Generalization",
            icon="wave",
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="gpt-4.1-mini",
                credential_id="openai-main",
            ),
            branch_context=SessionBranchContext(
                branch_id="branch-2",
                parent_session_id="chat-1",
                root_session_id="chat-1",
                focus_question="How does this generalize?",
                fork_anchor=SessionForkAnchor(
                    type="node",
                    node_id="linear-map",
                    source_message_id="msg_parent",
                ),
                active_node_ids=["linear-map"],
                summary_node_ids=["vector-space"],
                active_symbols={"T": "linear map from V to W"},
            ),
            messages=[
                SessionMessage(role="user", content="Second question"),
                SessionMessage(
                    role="assistant",
                    content="Second answer",
                    provider_name="openai_compatible",
                ),
            ],
        )
    )
    client = TestClient(
        create_app(
            repository=MarkdownKnowledgeRepository(tmp_path / "knowledge"),
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=session_store,
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="unused", provider_name="openai_compatible")
            ),
        )
    )

    response = client.get("/api/sessions")

    assert response.status_code == 200
    body = response.json()
    assert [session["session_id"] for session in body["sessions"]] == [
        "chat-2",
        "chat-1",
    ]
    assert body["sessions"][0]["provider_profile"]["provider_type"] == "openai_compatible"
    assert body["sessions"][0]["title"] == "Generalization"
    assert body["sessions"][0]["icon"] == "wave"
    assert body["sessions"][0]["default_answer_style_id"] is None
    assert body["sessions"][0]["strategy_agent_id"] == "top-down"
    assert body["sessions"][0]["branch"] == {
        "branch_id": "branch-2",
        "parent_session_id": "chat-1",
        "root_session_id": "chat-1",
        "focus_question": "How does this generalize?",
        "fork_anchor": {
            "type": "node",
            "message_id": None,
            "node_id": "linear-map",
            "source_message_id": "msg_parent",
        },
        "active_node_ids": ["linear-map"],
        "summary_node_ids": ["vector-space"],
        "active_symbols": {"T": "linear map from V to W"},
    }
    assert body["sessions"][0]["message_count"] == 2
    assert body["sessions"][0]["last_message"]["role"] == "assistant"
    assert body["sessions"][0]["last_message"]["content"] == "Second answer"


def test_sessions_endpoint_returns_branch_context_when_present(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-branch",
            provider_profile=None,
            branch_context=SessionBranchContext(
                branch_id="branch-1",
                parent_session_id="chat-root",
                root_session_id="chat-root",
                focus_question="Why is this useful?",
                fork_anchor=SessionForkAnchor(
                    type="node",
                    node_id="linear-map",
                    source_message_id="msg_0002",
                ),
                active_node_ids=["linear-map", "vector-space"],
                summary_node_ids=["matrix"],
                active_symbols={"T": "linear map from V to W"},
            ),
            messages=[],
        )
    )
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

    response = client.get("/api/sessions/chat-branch")

    assert response.status_code == 200
    assert response.json()["branch"] == {
        "branch_id": "branch-1",
        "parent_session_id": "chat-root",
        "root_session_id": "chat-root",
        "focus_question": "Why is this useful?",
        "fork_anchor": {
            "type": "node",
            "message_id": None,
            "node_id": "linear-map",
            "source_message_id": "msg_0002",
        },
        "active_node_ids": ["linear-map", "vector-space"],
        "summary_node_ids": ["matrix"],
        "active_symbols": {"T": "linear map from V to W"},
    }


def test_sessions_endpoints_expose_forked_child_relationships(tmp_path) -> None:
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
            session_id="chat-root",
            provider_profile=ProviderProfile(
                provider_type="gemini",
                model="gemini-2.5-flash",
                credential_id="gemini-main",
            ),
            messages=[],
        )
    )
    client = TestClient(
        create_app(
            repository=knowledge_repository,
            credential_registry=FileCredentialRegistry(credentials_path),
            session_store=session_store,
            provider_gateway=FakeProviderGateway(
                ProviderResult(output_text="unused", provider_name="gemini")
            ),
        )
    )

    fork_response = client.post(
        "/api/sessions/chat-root/fork",
        json={
            "fork_anchor": {"type": "node", "node_id": "linear-map"},
            "focus_question": "How does this generalize?",
        },
    )

    assert fork_response.status_code == 200
    child_session_id = fork_response.json()["session_id"]

    list_response = client.get("/api/sessions")
    detail_response = client.get(f"/api/sessions/{child_session_id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    sessions_by_id = {
        session["session_id"]: session for session in list_response.json()["sessions"]
    }
    assert list_response.json()["sessions"][0]["session_id"] == child_session_id
    assert sessions_by_id["chat-root"]["branch_depth"] == 0
    assert sessions_by_id["chat-root"]["child_session_ids"] == [child_session_id]
    assert sessions_by_id[child_session_id]["branch_depth"] == 1
    assert sessions_by_id[child_session_id]["child_session_ids"] == []
    assert detail_response.json()["branch"] == {
        "branch_id": fork_response.json()["branch"]["branch_id"],
        "parent_session_id": "chat-root",
        "root_session_id": "chat-root",
        "focus_question": "How does this generalize?",
        "fork_anchor": {
            "type": "node",
            "message_id": None,
            "node_id": "linear-map",
            "source_message_id": None,
        },
        "active_node_ids": ["linear-map"],
        "summary_node_ids": [],
        "active_symbols": {},
    }


def test_delete_session_endpoint_removes_leaf_session(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-leaf",
            title="Temporary chat",
            icon="atom",
            messages=[SessionMessage(role="user", content="Leaf question")],
        )
    )
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

    response = client.delete("/api/sessions/chat-leaf")

    assert response.status_code == 204
    assert session_store.load_record("chat-leaf") is None


def test_delete_session_endpoint_rejects_sessions_with_children(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(SessionRecord(session_id="chat-root"))
    session_store.save_record(
        SessionRecord(
            session_id="chat-child",
            branch_context=SessionBranchContext(
                parent_session_id="chat-root",
                root_session_id="chat-root",
            ),
        )
    )
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

    response = client.delete("/api/sessions/chat-root")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Cannot delete a conversation that still has child branches"
    )


def test_patch_session_endpoint_updates_icon(tmp_path) -> None:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-icon",
            title="Operator Theory",
            icon="sigma",
            messages=[SessionMessage(role="user", content="What is a compact operator?")],
        )
    )
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

    response = client.patch(
        "/api/sessions/chat-icon",
        json={"icon": "atom"},
    )

    assert response.status_code == 200
    assert response.json()["icon"] == "atom"
    updated = session_store.load_record("chat-icon")
    assert updated is not None
    assert updated.icon == "atom"


def test_forked_session_inherits_parent_explorer_folder(tmp_path) -> None:
    knowledge_repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_repository.save_node(
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="definition",
            summary="A set with vector addition and scalar multiplication.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        )
    )
    session_store = FileSessionStore(tmp_path / "sessions")
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    session_store.save_record(
        SessionRecord(
            session_id="chat-root",
            title="Root",
            messages=[
                SessionMessage(
                    message_id="msg-1",
                    role="user",
                    content="What is a vector space?",
                    created_at="2026-04-19T00:00:00Z",
                )
            ],
        )
    )
    folder = explorer_store.create_folder(
        scope="sessions",
        name="Course",
        parent_folder_id=None,
    )
    explorer_store.move_item(
        item_type="session",
        item_id="chat-root",
        folder_id=folder.folder_id,
        sort_order=1000,
        location_source="user",
    )
    client = TestClient(
        create_app(
            repository=knowledge_repository,
            session_store=session_store,
            explorer_store=explorer_store,
        )
    )

    response = client.post(
        "/api/sessions/chat-root/fork",
        json={
            "fork_anchor": {"type": "node", "node_id": "vector-space"},
            "focus_question": "Explore a branch",
        },
    )

    assert response.status_code == 200
    child_session_id = response.json()["session_id"]
    child_location = explorer_store.find_location("session", child_session_id)
    assert child_location is not None
    assert child_location.folder_id == folder.folder_id
    assert child_location.location_source == "system"
    assert child_location.user_locked is False
