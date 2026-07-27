from math_im_book.domain.models import (
    AgentStateItem,
    ChatSession,
    KnowledgeDraftCandidate,
    OrchestrationPlan,
    SessionAssistantContext,
)
from math_im_book.storage.sessions import (
    FileSessionStore,
    SessionMessage,
    SessionRecord,
    SessionWorkingTurn,
)


def _assistant_context() -> SessionAssistantContext:
    return SessionAssistantContext(
        action_type="answer_then_suggest_drafts",
        orchestration_plan=OrchestrationPlan(
            route="answer_then_suggest_drafts",
            intent="broad_overview",
            persistence_decision="suggest_drafts",
            confidence=0.78,
            user_visible_summary="先给概览，并建议可整理的知识点。",
            detected_scope_ids=["linear-algebra"],
            profile_layers_used=["global_user", "scope_memory:linear-algebra"],
            profile_context_summary="识别为线性代数范围；本轮只建议知识点，不直接落盘。",
            candidate_drafts=[
                KnowledgeDraftCandidate(
                    title="Vector Space",
                    draft_type="definition",
                    reason="Foundational reusable concept.",
                )
            ],
        ),
        state_items=[
            AgentStateItem(
                item_id="draft-vector-space",
                kind="knowledge_draft",
                state="suggested",
                title="Vector Space",
                reason="Foundational reusable concept.",
                source_message_id="msg-assistant",
                node_id="vector-space",
                error_message="Previous write failed.",
            )
        ],
    )


def test_session_store_roundtrips_assistant_orchestration_context(tmp_path) -> None:
    store = FileSessionStore(tmp_path / "chats")
    store.save(ChatSession(session_id="chat-1"))
    store.append_messages(
        "chat-1",
        [
            SessionMessage(role="user", content="线性代数"),
            SessionMessage(
                role="assistant",
                content="线性代数研究向量空间和线性映射。",
                message_id="msg-assistant",
                assistant_context=_assistant_context(),
            ),
        ],
    )

    record = store.load_record("chat-1")

    assert record is not None
    context = record.messages[-1].assistant_context
    assert context.orchestration_plan is not None
    assert context.orchestration_plan.route == "answer_then_suggest_drafts"
    assert context.orchestration_plan.detected_scope_ids == ["linear-algebra"]
    assert context.orchestration_plan.candidate_drafts[0].title == "Vector Space"
    assert context.state_items[0].state == "suggested"
    assert context.state_items[0].node_id == "vector-space"
    assert context.state_items[0].error_message == "Previous write failed."


def test_session_store_roundtrips_working_turn_agent_state(tmp_path) -> None:
    store = FileSessionStore(tmp_path / "chats")
    store.save_record(SessionRecord(session_id="chat-1"))
    store.save_working_turn(
        "chat-1",
        SessionWorkingTurn(
            state="answering",
            assistant_message=SessionMessage(
                role="assistant",
                content="先回答，再建议可积累的知识点。",
                assistant_context=_assistant_context(),
            ),
        ),
    )

    working_turn = store.load_working_turn("chat-1")

    assert working_turn is not None
    assert working_turn.assistant_message is not None
    context = working_turn.assistant_message.assistant_context
    assert context.orchestration_plan is not None
    assert context.orchestration_plan.profile_layers_used == [
        "global_user",
        "scope_memory:linear-algebra",
    ]
    assert context.state_items[0].kind == "knowledge_draft"
