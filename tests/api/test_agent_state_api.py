from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import (
    AgentStateItem,
    AnswerAnchor,
    KnowledgeAuthorizationDecision,
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
                            authorization=KnowledgeAuthorizationDecision(
                                mode="require_approval",
                                status="pending",
                                risk_level="medium",
                                operation="write_knowledge_nodes",
                                reason="Multiple nodes need approval.",
                            ),
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
    assert queued_context.orchestration_plan.authorization.status == "approved"

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


def test_approved_drafts_generate_knowledge_before_replacing_waiting_answer(
    tmp_path,
) -> None:
    class KnowledgeFirstGateway:
        def __init__(self) -> None:
            self.purposes: list[str] = []

        def generate(
            self,
            profile: ProviderProfile,
            request: ProviderRequest,
        ) -> ProviderResult:
            self.purposes.append(request.purpose)
            if request.purpose == "knowledge_compile":
                return ProviderResult(
                    output_text=(
                        '{"summary":"核是映到零向量的所有向量。",'
                        '"detail":"线性映射的核定义为 $\\\\ker T=\\\\{v:T(v)=0\\\\}$。"}'
                    ),
                    provider_name="test",
                )
            return ProviderResult(
                output_text="核刻画了线性映射失去的信息。[K1]",
                provider_name="test",
            )

    gateway = KnowledgeFirstGateway()
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-knowledge-first",
            title="Kernel",
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="test-model",
                credential_id="test",
            ),
            branch_context=SessionBranch(),
            messages=[
                SessionMessage(
                    message_id="msg-question",
                    role="user",
                    content="什么是线性映射的核？",
                ),
                SessionMessage(
                    message_id="msg-answer",
                    role="assistant",
                    content="知识点计划已就绪，等待你的批准。",
                    assistant_context=SessionAssistantContext(
                        action_type="ask_before_persist",
                        orchestration_plan=OrchestrationPlan(
                            route="ask_before_persist",
                            intent="definition",
                            persistence_decision="await_approval",
                            confidence=0.72,
                            user_visible_summary="先生成核的定义，再回答。",
                            candidate_drafts=[
                                KnowledgeDraftCandidate(
                                    title="线性映射的核",
                                    draft_type="definition",
                                    reason="回答需要可复用定义。",
                                )
                            ],
                            strategy_mode="top-down",
                            authorization=KnowledgeAuthorizationDecision(
                                mode="require_approval",
                                status="pending",
                                risk_level="medium",
                                operation="write_knowledge_nodes",
                                reason="需要用户确认。",
                            ),
                        ),
                    ),
                ),
            ],
        )
    )
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(
        repository,
        provider_gateway=gateway,
        auto_start=False,
    )
    client = TestClient(
        create_app(
            repository=repository,
            session_store=session_store,
            provider_gateway=gateway,
            knowledge_job_repository=knowledge_jobs,
        )
    )

    response = client.post(
        "/api/sessions/chat-knowledge-first/messages/msg-answer/suggested-drafts/compile",
        json={"draft_indexes": [0]},
    )

    assert response.status_code == 200
    waiting_record = session_store.load_record("chat-knowledge-first")
    assert "等待你的批准" in waiting_record.messages[-1].content

    knowledge_jobs.run_job(response.json()["job_id"])

    completed_record = session_store.load_record("chat-knowledge-first")
    completed_message = completed_record.messages[-1]
    assert completed_message.content == "核刻画了线性映射失去的信息。[K1]"
    assert completed_message.assistant_context.referenced_node_ids == ["线性映射的核"]
    assert completed_message.assistant_context.action_type == "expand_with_drafts"
    assert completed_message.assistant_context.orchestration_plan.route == (
        "draft_first_then_answer"
    )
    assert repository.get_node("线性映射的核").status == "ready"
    assert gateway.purposes == ["knowledge_compile", "answer"]


def test_reject_suggested_drafts_persists_denial_without_writing_nodes(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-approval",
            messages=[
                SessionMessage(
                    message_id="msg-approval",
                    role="assistant",
                    content="Answer",
                    created_at="2026-04-18T00:00:00Z",
                    assistant_context=SessionAssistantContext(
                        action_type="ask_before_persist",
                        orchestration_plan=OrchestrationPlan(
                            route="ask_before_persist",
                            intent="definition",
                            persistence_decision="await_approval",
                            confidence=0.7,
                            user_visible_summary="发现一个知识缺口。",
                            candidate_drafts=[
                                KnowledgeDraftCandidate(
                                    title="Vector Space",
                                    draft_type="definition",
                                    reason="需要可复用定义。",
                                )
                            ],
                            authorization=KnowledgeAuthorizationDecision(
                                mode="require_approval",
                                status="pending",
                                risk_level="medium",
                                operation="write_knowledge_nodes",
                                reason="需要用户确认。",
                            ),
                        ),
                        state_items=[
                            AgentStateItem(
                                item_id="draft-vector-space",
                                kind="knowledge_draft",
                                state="suggested",
                                title="Vector Space",
                                reason="需要可复用定义。",
                            )
                        ],
                    ),
                )
            ],
        )
    )
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    client = TestClient(
        create_app(repository=repository, session_store=session_store)
    )

    response = client.post(
        "/api/sessions/chat-approval/messages/msg-approval/suggested-drafts/reject"
    )

    assert response.status_code == 200
    context = response.json()["messages"][0]["assistant_context"]
    assert context["orchestration_plan"]["authorization"]["status"] == "denied"
    assert context["state_items"][0]["state"] == "dismissed"
    assert response.json()["messages"][0]["content"] == (
        "已跳过知识点生成，因此本轮没有生成回答。"
    )
    assert repository.list_nodes() == []


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
