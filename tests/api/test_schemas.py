import pytest
from pydantic import ValidationError

from math_im_book.api.schemas import (
    AskResponseSchema,
    AnswerStyleSchema,
    AnswerStylesResponseSchema,
    DisplayNodeReferenceSchema,
    KnowledgeNodeSchema,
    NodeReferenceSchema,
    NodeResponseSchema,
    OutlineNodeSchema,
    OutlineResponseSchema,
    PendingDraftRequestSchema,
    RelatedDiscussionSchema,
    ProviderProfileSchema,
    SessionBranchSchema,
    SessionAssistantContextSchema,
    SessionForkAnchorSchema,
    SessionForkRequestSchema,
    SessionSchema,
    StrategyAgentSchema,
    StrategyAgentsResponseSchema,
)


def test_provider_profile_schema_serializes_and_rejects_unknown_fields() -> None:
    profile = ProviderProfileSchema(
        provider_type="gemini",
        model="gemini-2.5-flash",
        credential_id="gemini-main",
        options={"temperature": "0.2"},
    )

    assert profile.model_dump() == {
        "provider_type": "gemini",
        "model": "gemini-2.5-flash",
        "credential_id": "gemini-main",
        "base_url": None,
        "options": {"temperature": "0.2"},
    }

    with pytest.raises(ValidationError):
        ProviderProfileSchema(
            provider_type="unsupported",
            model="x",
            credential_id="c",
        )


def test_ask_response_schema_matches_current_api_shape() -> None:
    response = AskResponseSchema(
        action={
            "action_type": "reuse_answer",
            "selected_node_ids": ["linear-map"],
            "draft_requests": [],
            "user_visible_reason": "Reusing existing knowledge.",
        },
        answer={
            "summary": "A linear map preserves addition and scalar multiplication.",
            "detail": "A map T: V -> W is linear when ...",
            "references": ["linear-map"],
            "symbols": {"T": "linear map from V to W"},
            "symbol_conflicts": [],
            "assistant_text": "A linear map preserves addition and scalar multiplication.",
        },
        drafts=[],
        created_node_ids=[],
        session={
            "session_id": "chat-1",
            "provider_profile": {
                "provider_type": "gemini",
                "model": "gemini-2.5-flash",
                "credential_id": "gemini-main",
                "base_url": None,
                "options": {},
            },
        },
    )

    assert response.model_dump()["answer"]["assistant_text"] == (
        "A linear map preserves addition and scalar multiplication."
    )


def test_answer_style_response_schema_serializes_style_metadata() -> None:
    response = AnswerStylesResponseSchema(
        default_style_id="default",
        styles=[
            AnswerStyleSchema(
                answer_style_id="default",
                label="Default",
                description="Balanced answers.",
                instructions="# Default\n\nUse clear math explanations.",
                is_default=True,
            )
        ],
    )

    assert response.model_dump() == {
        "default_style_id": "default",
        "styles": [
            {
                "answer_style_id": "default",
                "label": "Default",
                "description": "Balanced answers.",
                "instructions": "# Default\n\nUse clear math explanations.",
                "is_default": True,
            }
        ],
    }


def test_strategy_agent_response_schema_serializes_agent_metadata() -> None:
    response = StrategyAgentsResponseSchema(
        default_strategy_agent_id="raw",
        agents=[
            StrategyAgentSchema(
                strategy_agent_id="raw",
                label="Raw",
                description="Use the raw question text with minimal shaping.",
                instructions="# Raw\n\nUse the user's question as-is.",
                is_default=True,
            ),
            StrategyAgentSchema(
                strategy_agent_id="top-down",
                label="Top Down",
                description="Start from the high-level structure.",
                instructions="# Top Down\n\nStart broad, then narrow to details.",
                is_default=False,
            ),
        ],
    )

    assert response.model_dump() == {
        "default_strategy_agent_id": "raw",
        "agents": [
            {
                "strategy_agent_id": "raw",
                "label": "Raw",
                "description": "Use the raw question text with minimal shaping.",
                "instructions": "# Raw\n\nUse the user's question as-is.",
                "is_default": True,
            },
            {
                "strategy_agent_id": "top-down",
                "label": "Top Down",
                "description": "Start from the high-level structure.",
                "instructions": "# Top Down\n\nStart broad, then narrow to details.",
                "is_default": False,
            },
        ],
    }


def test_node_and_outline_response_schemas_match_api_shape() -> None:
    node_response = NodeResponseSchema(
        node={
            "id": "linear-map",
            "title": "Linear Map",
            "type": "atomic",
            "summary": "A linear map preserves addition and scalar multiplication.",
            "detail": "A map T: V -> W is linear when ...",
            "parent_id": "linear-algebra",
            "source": "chat:1",
            "references": [
                {"node_id": "vector-space", "reason": "Uses vector spaces."}
            ],
            "status": "ready",
            "symbols": {"T": "linear map from V to W"},
            "symbol_scopes": {
                "global": {"T": "linear map from V to W"},
                "local": {"x": "vector in V"},
            },
        }
    )
    outline_response = OutlineResponseSchema(
        nodes=[
            {
                "id": "linear-map",
                "title": "Linear Map",
                "type": "atomic",
                "summary": "A linear map preserves addition and scalar multiplication.",
                "parent_id": "linear-algebra",
                "status": "ready",
            }
        ]
    )

    assert node_response.model_dump()["node"]["references"][0]["node_id"] == "vector-space"
    assert node_response.model_dump()["node"]["symbol_scopes"] == {
        "global": {"T": "linear map from V to W"},
        "local": {"x": "vector in V"},
    }
    assert outline_response.model_dump()["nodes"][0]["id"] == "linear-map"


def test_node_response_schema_supports_display_ready_reference_fields() -> None:
    node_response = NodeResponseSchema(
        node={
            "id": "linear-map",
            "title": "Linear Map",
            "type": "atomic",
            "summary": "A linear map preserves addition and scalar multiplication.",
            "detail": "A map T: V -> W is linear when ...",
            "source": "chat:1",
            "references": [{"node_id": "vector-space", "reason": "Uses vector spaces."}],
            "incoming_references": [],
            "related_session_ids": ["chat-1"],
            "references_display": [
                {
                    "node_id": "vector-space",
                    "title": "Vector Space",
                    "summary": "Defines the ambient space.",
                    "reason": "Uses vector spaces.",
                    "type": "atomic",
                    "status": "ready",
                }
            ],
            "incoming_references_display": [],
            "related_discussions": [
                {
                    "session_id": "chat-1",
                    "title": "Linear algebra warmup",
                    "preview": "Why is scalar multiplication required?",
                    "message_count": 4,
                    "focus_question": "What makes a map linear?",
                }
            ],
            "status": "ready",
            "symbols": {},
            "symbol_scopes": {},
        }
    )

    assert node_response.model_dump()["node"]["references_display"][0]["title"] == "Vector Space"
    assert node_response.model_dump()["node"]["related_discussions"][0]["message_count"] == 4


def test_display_node_reference_schema_serializes_and_rejects_extra_fields() -> None:
    reference = DisplayNodeReferenceSchema(
        node_id="vector-space",
        title="Vector Space",
        summary=None,
        reason="Uses vector spaces.",
        type="atomic",
        status="ready",
    )

    assert reference.model_dump() == {
        "node_id": "vector-space",
        "title": "Vector Space",
        "summary": None,
        "reason": "Uses vector spaces.",
        "type": "atomic",
        "status": "ready",
    }

    with pytest.raises(ValidationError):
        DisplayNodeReferenceSchema(
            node_id="vector-space",
            title="Vector Space",
            summary=None,
            reason="Uses vector spaces.",
            type="atomic",
            status="ready",
            extra_field="not allowed",
        )


def test_related_discussion_schema_serializes_and_rejects_extra_fields() -> None:
    discussion = RelatedDiscussionSchema(
        session_id="chat-1",
        title="Linear algebra warmup",
        preview="Why is scalar multiplication required?",
        message_count=4,
        focus_question="What makes a map linear?",
    )

    assert discussion.model_dump() == {
        "session_id": "chat-1",
        "title": "Linear algebra warmup",
        "preview": "Why is scalar multiplication required?",
        "message_count": 4,
        "focus_question": "What makes a map linear?",
    }

    with pytest.raises(ValidationError):
        RelatedDiscussionSchema(
            session_id="chat-1",
            title="Linear algebra warmup",
            preview="Why is scalar multiplication required?",
            message_count=4,
            focus_question="What makes a map linear?",
            extra_field="not allowed",
        )


def test_invalid_outline_node_missing_required_fields_raises() -> None:
    with pytest.raises(ValidationError):
        OutlineNodeSchema(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="A linear map preserves addition and scalar multiplication.",
            parent_id=None,
        )


def test_session_schema_uses_branch_and_message_ids() -> None:
    session = SessionSchema(
        session_id="chat-1",
        branch={
            "branch_id": "branch-1",
            "parent_session_id": "chat-root",
            "root_session_id": "chat-root",
            "fork_anchor": {
                "type": "message",
                "message_id": "msg_0008",
            },
            "active_node_ids": ["linear-map"],
            "summary_node_ids": ["vector-space"],
            "active_symbols": {"T": "linear map from V to W"},
        },
        messages=[
            {
                "message_id": "msg_0008",
                "role": "assistant",
                "content": "A linear map preserves addition.",
                "created_at": "2026-04-02T09:10:02Z",
                "assistant_context": {
                    "action_type": "reuse_answer",
                    "referenced_node_ids": ["linear-map"],
                    "symbol_conflicts": [],
                    "alignment_notes": [],
                    "compact_summary": None,
                },
            }
        ],
    )

    dumped = session.model_dump()

    assert dumped["branch"]["fork_anchor"] == {
        "type": "message",
        "message_id": "msg_0008",
        "node_id": None,
        "source_message_id": None,
    }
    assert "branch_context" not in dumped
    assert dumped["messages"][0]["message_id"] == "msg_0008"
    assert dumped["messages"][0]["created_at"] == "2026-04-02T09:10:02Z"
    assert dumped["messages"][0]["assistant_context"] == {
        "action_type": "reuse_answer",
        "referenced_node_ids": ["linear-map"],
        "anchors": [],
        "symbol_conflicts": [],
        "alignment_notes": [],
        "compact_summary": None,
        "orchestration_plan": None,
        "state_items": [],
    }


def test_session_assistant_context_schema_serializes_orchestration_plan() -> None:
    context = SessionAssistantContextSchema(
        action_type="answer_then_suggest_drafts",
        referenced_node_ids=[],
        anchors=[],
        symbol_conflicts=[],
        alignment_notes=[],
        orchestration_plan={
            "route": "answer_then_suggest_drafts",
            "intent": "broad_overview",
            "persistence_decision": "suggest_drafts",
            "confidence": 0.78,
            "user_visible_summary": "先给概览，并建议可整理的知识点。",
            "detected_scope_ids": ["linear-algebra"],
            "profile_layers_used": ["global_user", "scope_memory:linear-algebra"],
            "profile_context_summary": "识别为线性代数范围；本轮只建议知识点，不直接落盘。",
            "candidate_drafts": [
                {
                    "title": "Vector Space",
                    "draft_type": "definition",
                    "reason": "Foundational reusable concept.",
                }
            ],
        },
        state_items=[
            {
                "item_id": "draft-vector-space",
                "kind": "knowledge_draft",
                "state": "suggested",
                "title": "Vector Space",
                "reason": "Foundational reusable concept.",
                "source_message_id": "msg-assistant",
            }
        ],
    )

    dumped = context.model_dump()

    assert dumped["orchestration_plan"]["route"] == "answer_then_suggest_drafts"
    assert dumped["orchestration_plan"]["detected_scope_ids"] == ["linear-algebra"]
    assert dumped["orchestration_plan"]["profile_layers_used"][0] == "global_user"
    assert dumped["orchestration_plan"]["candidate_drafts"][0]["title"] == "Vector Space"
    assert dumped["state_items"][0]["state"] == "suggested"


def test_session_schema_supports_branch_and_fork_anchor() -> None:
    session = SessionSchema(
        session_id="chat-branch-1",
        branch=SessionBranchSchema(
            branch_id="branch-1",
            parent_session_id="chat-root",
            root_session_id="chat-root",
            fork_anchor=SessionForkAnchorSchema(
                type="node",
                node_id="linear-map",
                source_message_id="msg_0008",
            ),
            focus_question="How does this generalize?",
            active_node_ids=["linear-map", "vector-space"],
            summary_node_ids=["scalar-multiplication"],
            active_symbols={"T": "linear map from V to W"},
        ),
    )

    assert session.model_dump()["branch"] == {
        "branch_id": "branch-1",
        "parent_session_id": "chat-root",
        "root_session_id": "chat-root",
        "fork_anchor": {
            "type": "node",
            "message_id": None,
            "node_id": "linear-map",
            "source_message_id": "msg_0008",
        },
        "focus_question": "How does this generalize?",
        "active_node_ids": ["linear-map", "vector-space"],
        "summary_node_ids": ["scalar-multiplication"],
        "active_symbols": {"T": "linear map from V to W"},
    }


def test_session_fork_request_schema_uses_fork_anchor_and_rejects_indexes() -> None:
    request = SessionForkRequestSchema(
        focus_question="How does this generalize?",
        fork_anchor={"type": "message", "message_id": "msg_0008"},
    )

    assert request.model_dump() == {
        "focus_question": "How does this generalize?",
        "fork_anchor": {
            "type": "message",
            "message_id": "msg_0008",
            "node_id": None,
            "source_message_id": None,
        },
    }

    with pytest.raises(ValidationError):
        SessionForkRequestSchema(
            focus_question="How does this generalize?",
            fork_anchor={"type": "message", "message_id": "msg_0008"},
            forked_from_message_index=3,
        )
