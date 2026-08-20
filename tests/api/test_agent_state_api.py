from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import (
    AgentStateItem,
    AnswerAnchor,
    KnowledgeNode,
    KnowledgeDraftCandidate,
    OrchestrationPlan,
    PendingDraftRequest,
    SessionAssistantContext,
    SessionBranch,
)
from math_im_book.domain.models import ProviderProfile, ProviderResult
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.services.providers import ProviderRequest
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import SessionMessage
from math_im_book.storage.sessions import FileSessionStore, SessionRecord


def test_agent_state_returns_current_turn_and_queue(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Linear Algebra",
            branch_context=SessionBranch(),
            messages=[
                SessionMessage(
                    message_id="msg-a",
                    role="assistant",
                    content="Answer",
                    created_at="2026-04-18T00:00:00Z",
                    assistant_context=SessionAssistantContext(
                        action_type="answer_then_suggest_drafts",
                        orchestration_plan=OrchestrationPlan(
                            route="answer_then_suggest_drafts",
                            intent="broad_overview",
                            persistence_decision="suggest_drafts",
                            confidence=0.78,
                            user_visible_summary="先给概览。",
                            detected_scope_ids=["linear-algebra"],
                            profile_layers_used=["global_user", "scope_memory:linear-algebra"],
                            profile_context_summary="识别为线性代数范围。",
                            candidate_drafts=[
                                KnowledgeDraftCandidate(
                                    title="Vector Space",
                                    draft_type="definition",
                                    reason="Reusable concept.",
                                )
                            ],
                        ),
                        state_items=[
                            AgentStateItem(
                                item_id="draft-vector-space",
                                kind="knowledge_draft",
                                state="suggested",
                                title="Vector Space",
                                reason="Reusable concept.",
                                source_message_id="msg-a",
                            )
                        ],
                    ),
                )
            ],
        )
    )
    client = TestClient(create_app(session_store=session_store))

    response = client.get("/api/agent-state?session_id=chat-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_turn"]["route"] == "answer_then_suggest_drafts"
    assert payload["memory_scope"]["detected_scope_ids"] == ["linear-algebra"]
    assert payload["memory_scope"]["profile_layers_used"][1] == "scope_memory:linear-algebra"
    assert payload["knowledge_queue"][0]["title"] == "Vector Space"
    assert payload["recent_decisions"][0]["message_id"] == "msg-a"


def test_agent_state_includes_live_knowledge_jobs(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(SessionRecord(session_id="chat-1", title="Linear Algebra"))
    knowledge_jobs = InMemoryKnowledgeJobRepository(
        MarkdownKnowledgeRepository(tmp_path / "knowledge"),
        auto_start=False,
    )
    job = knowledge_jobs.submit_compile_job(
        session_id="chat-1",
        question="What is a vector space?",
        anchors=[
            AnswerAnchor(
                anchor_id="vector-space",
                label="Vector Space",
                status="pending",
            )
        ],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Vector Space",
                draft_type="definition",
                reason="Foundational reusable concept.",
            )
        ],
    )
    client = TestClient(
        create_app(
            session_store=session_store,
            knowledge_job_repository=knowledge_jobs,
        )
    )

    response = client.get("/api/agent-state?session_id=chat-1")

    assert response.status_code == 200
    queue = response.json()["knowledge_queue"]
    assert queue[0]["item_id"] == job.job_id
    assert queue[0]["title"] == "Vector Space"
    assert queue[0]["state"] == "queued"


def test_accept_suggested_drafts_queues_selected_drafts_and_persists_ready_links(
    tmp_path,
) -> None:
    class CompileGateway:
        def generate(
            self,
            profile: ProviderProfile,
            request: ProviderRequest,
        ) -> ProviderResult:
            return ProviderResult(
                output_text='{"summary":"Kernel summary.","detail":"Kernel detail."}',
                provider_name="test",
            )

    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Linear Algebra",
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="test-model",
                credential_id="test",
            ),
            branch_context=SessionBranch(),
            messages=[
                SessionMessage(
                    message_id="msg-a",
                    role="assistant",
                    content="Answer",
                    created_at="2026-04-18T00:00:00Z",
                    assistant_context=SessionAssistantContext(
                        action_type="answer_then_suggest_drafts",
                        orchestration_plan=OrchestrationPlan(
                            route="answer_then_suggest_drafts",
                            intent="broad_overview",
                            persistence_decision="suggest_drafts",
                            confidence=0.78,
                            user_visible_summary="先给概览。",
                            candidate_drafts=[
                                KnowledgeDraftCandidate(
                                    title="Vector Space",
                                    draft_type="definition",
                                    reason="Reusable concept.",
                                ),
                                KnowledgeDraftCandidate(
                                    title="Kernel",
                                    draft_type="definition",
                                    reason="Reusable concept.",
                                ),
                            ],
                        ),
                        state_items=[
                            AgentStateItem(
                                item_id="draft-vector-space",
                                kind="knowledge_draft",
                                state="suggested",
                                title="Vector Space",
                                reason="Reusable concept.",
                                source_message_id="msg-a",
                            ),
                            AgentStateItem(
                                item_id="draft-kernel",
                                kind="knowledge_draft",
                                state="suggested",
                                title="Kernel",
                                reason="Reusable concept.",
                                source_message_id="msg-a",
                            ),
                        ],
                    ),
                )
            ],
        )
    )
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=CompileGateway(),
        auto_start=False,
    )
    client = TestClient(
        create_app(
            repository=repository,
            session_store=session_store,
            knowledge_job_repository=knowledge_jobs,
        )
    )

    response = client.post(
        "/api/sessions/chat-1/messages/msg-a/suggested-drafts/compile",
        json={"draft_indexes": [1]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["anchors"][0] == {
        "anchor_id": "kernel",
        "label": "Kernel",
        "status": "pending",
        "node_id": None,
    }
    queued_record = session_store.load_record("chat-1")
    queued_context = queued_record.messages[0].assistant_context
    assert queued_context.anchors[0].label == "Kernel"
    assert queued_context.state_items[1].state == "queued"

    completed_job = knowledge_jobs.run_job(payload["job_id"])

    assert completed_job.anchors[0].node_id == "kernel"
    ready_record = session_store.load_record("chat-1")
    ready_context = ready_record.messages[0].assistant_context
    assert ready_context.anchors[0].status == "ready"
    assert ready_context.anchors[0].node_id == "kernel"
    assert ready_context.state_items[1].state == "ready"
    assert ready_context.state_items[1].node_id == "kernel"

    job_response = client.get(f"/api/knowledge-jobs/{payload['job_id']}")
    assert job_response.status_code == 200
    assert job_response.json()["anchors"][0]["node_id"] == "kernel"


def test_get_session_reconciles_stale_queue_from_ready_knowledge_node(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Group Representations",
            messages=[
                SessionMessage(
                    message_id="msg-a",
                    role="assistant",
                    content="Answer",
                    assistant_context=SessionAssistantContext(
                        anchors=[
                            AnswerAnchor(
                                anchor_id="schur-lemma",
                                label="Schur's Lemma",
                                status="pending",
                            )
                        ],
                        state_items=[
                            AgentStateItem(
                                item_id="draft-schur-lemma",
                                kind="knowledge_draft",
                                state="queued",
                                title="Schur's Lemma",
                                reason="Reusable theorem.",
                                source_message_id="msg-a",
                            )
                        ],
                    ),
                )
            ],
        )
    )
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="schur-lemma",
            title="Schur's Lemma",
            type="theorem",
            summary="Intertwiners between irreducible representations are rigid.",
            detail="A reusable theorem statement.",
            parent_id=None,
            source="chat-1",
            references=[],
            status="ready",
        )
    )
    client = TestClient(
        create_app(repository=repository, session_store=session_store)
    )

    response = client.get("/api/sessions/chat-1")

    assert response.status_code == 200
    context = response.json()["messages"][0]["assistant_context"]
    assert context["anchors"][0]["status"] == "ready"
    assert context["anchors"][0]["node_id"] == "schur-lemma"
    assert context["state_items"][0]["state"] == "ready"
    assert context["state_items"][0]["node_id"] == "schur-lemma"
    persisted = session_store.load_record("chat-1")
    assert persisted.messages[0].assistant_context.state_items[0].state == "ready"


def test_fast_suggested_draft_job_cannot_be_overwritten_by_queued_state(tmp_path) -> None:
    class CompileGateway:
        def generate(
            self,
            profile: ProviderProfile,
            request: ProviderRequest,
        ) -> ProviderResult:
            return ProviderResult(
                output_text='{"summary":"Kernel summary.","detail":"Kernel detail."}',
                provider_name="test",
            )

    class CompletingBeforeReturnRepository(InMemoryKnowledgeJobRepository):
        def submit_compile_job(self, **kwargs):
            queued = super().submit_compile_job(**kwargs)
            self.run_job(queued.job_id)
            return queued

    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Linear Algebra",
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="test-model",
                credential_id="test",
            ),
            messages=[
                SessionMessage(
                    message_id="msg-a",
                    role="assistant",
                    content="Answer",
                    assistant_context=SessionAssistantContext(
                        orchestration_plan=OrchestrationPlan(
                            route="answer_then_suggest_drafts",
                            intent="broad_overview",
                            persistence_decision="suggest_drafts",
                            confidence=0.78,
                            user_visible_summary="Start with an overview.",
                            candidate_drafts=[
                                KnowledgeDraftCandidate(
                                    title="Kernel",
                                    draft_type="definition",
                                    reason="Reusable concept.",
                                )
                            ],
                        ),
                        state_items=[
                            AgentStateItem(
                                item_id="draft-kernel",
                                kind="knowledge_draft",
                                state="suggested",
                                title="Kernel",
                                reason="Reusable concept.",
                                source_message_id="msg-a",
                            )
                        ],
                    ),
                )
            ],
        )
    )
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = CompletingBeforeReturnRepository(
        repository,
        provider_gateway=CompileGateway(),
        auto_start=False,
    )
    client = TestClient(
        create_app(
            repository=repository,
            session_store=session_store,
            knowledge_job_repository=knowledge_jobs,
        )
    )

    response = client.post(
        "/api/sessions/chat-1/messages/msg-a/suggested-drafts/compile",
        json={"draft_indexes": [0]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    context = session_store.load_record("chat-1").messages[0].assistant_context
    assert context.anchors[0].status == "ready"
    assert context.state_items[0].state == "ready"
    assert context.state_items[0].node_id == "kernel"


def test_accept_suggested_drafts_preserves_multiple_chinese_links(tmp_path) -> None:
    class CompileGateway:
        def generate(
            self,
            profile: ProviderProfile,
            request: ProviderRequest,
        ) -> ProviderResult:
            title = request.user_message.splitlines()[0].removeprefix("Title: ")
            return ProviderResult(
                output_text=(
                    '{"summary":"'
                    + title
                    + ' summary.","detail":"'
                    + title
                    + ' detail."}'
                ),
                provider_name="test",
            )

    session_store = FileSessionStore(tmp_path / "sessions")
    candidates = [
        KnowledgeDraftCandidate(
            title="流形的基本定义",
            draft_type="definition",
            reason="Need a reusable definition.",
        ),
        KnowledgeDraftCandidate(
            title="局部坐标图",
            draft_type="definition",
            reason="Need a reusable definition.",
        ),
        KnowledgeDraftCandidate(
            title="切空间",
            draft_type="definition",
            reason="Need a reusable definition.",
        ),
    ]
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Manifolds",
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="test-model",
                credential_id="test",
            ),
            messages=[
                SessionMessage(
                    message_id="msg-a",
                    role="assistant",
                    content="Answer",
                    created_at="2026-04-18T00:00:00Z",
                    assistant_context=SessionAssistantContext(
                        action_type="answer_then_suggest_drafts",
                        orchestration_plan=OrchestrationPlan(
                            route="answer_then_suggest_drafts",
                            intent="broad_overview",
                            persistence_decision="suggest_drafts",
                            confidence=0.78,
                            user_visible_summary="先给概览。",
                            candidate_drafts=candidates,
                        ),
                    ),
                )
            ],
        )
    )
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=CompileGateway(),
        auto_start=False,
    )
    client = TestClient(
        create_app(
            repository=repository,
            session_store=session_store,
            knowledge_job_repository=knowledge_jobs,
        )
    )

    response = client.post(
        "/api/sessions/chat-1/messages/msg-a/suggested-drafts/compile",
        json={"draft_indexes": [0, 1, 2]},
    )
    job_id = response.json()["job_id"]
    knowledge_jobs.run_job(job_id)
    job_response = client.get(f"/api/knowledge-jobs/{job_id}")

    assert job_response.status_code == 200
    assert [anchor["anchor_id"] for anchor in job_response.json()["anchors"]] == [
        "流形的基本定义",
        "局部坐标图",
        "切空间",
    ]
    assert [anchor["node_id"] for anchor in job_response.json()["anchors"]] == [
        "流形的基本定义",
        "局部坐标图",
        "切空间",
    ]
    assert [node.id for node in repository.list_nodes()] == [
        "切空间",
        "局部坐标图",
        "流形的基本定义",
    ]
