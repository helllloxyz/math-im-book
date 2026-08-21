import pytest

from math_im_book.domain.models import KnowledgeNode, ProviderProfile, ProviderResult
from math_im_book.services.planner import QuestionPlanner
from math_im_book.services.providers import FakeProviderGateway
from math_im_book.storage.user_profile import FileUserProfileRepository


class RecordingPlannerGateway:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result
        self.requests: list[object] = []

    def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
        self.requests.append(request)
        return self.result


def test_planner_without_provider_returns_answer_only_fallback() -> None:
    planner = QuestionPlanner()

    action = planner.plan(question="What is a linear map?", nodes=[])

    assert action.action_type == "answer_only"
    assert action.selected_node_ids == []
    assert action.orchestration_plan.route == "answer_only"
    assert action.orchestration_plan.persistence_decision == "do_not_persist"


def test_planner_without_provider_defaults_to_answer_only_even_with_nodes() -> None:
    planner = QuestionPlanner()

    action = planner.plan_without_provider("What is a linear map?", [_linear_map_node()])

    assert action.action_type == "answer_only"
    assert action.selected_node_ids == []
    assert action.orchestration_plan.route == "answer_only"
    assert action.orchestration_plan.persistence_decision == "do_not_persist"


def test_planner_falls_back_to_answer_only_for_broad_question_without_provider() -> None:
    planner = QuestionPlanner()

    action = planner.plan_without_provider("线性代数", [])

    assert action.action_type == "answer_only"
    assert action.orchestration_plan.route == "answer_only"
    assert action.orchestration_plan.persistence_decision == "do_not_persist"
    assert action.orchestration_plan.detected_scope_ids == []


def test_planner_parses_orchestration_plan_contract() -> None:
    gateway = RecordingPlannerGateway(
        ProviderResult(
            output_text=(
                '{"route":"answer_then_suggest_drafts",'
                '"intent":"broad_overview",'
                '"persistence_decision":"suggest_drafts",'
                '"confidence":0.82,'
                '"selected_node_ids":[],'
                '"detected_scope_ids":["linear-algebra"],'
                '"profile_layers_used":["global_user","scope_memory:linear-algebra"],'
                '"profile_context_summary":"识别为线性代数范围；用户倾向先看整体再整理节点。",'
                '"candidate_drafts":[{"title":"向量空间",'
                '"draft_type":"definition",'
                '"reason":"可复用的基础概念。"}],'
                '"user_visible_summary":"先给概览，并建议知识点。"}'
            ),
            provider_name="gemini",
        )
    )
    planner = QuestionPlanner(provider_gateway=gateway)

    action = planner.plan(
        "线性代数",
        [],
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )

    assert action.action_type == "answer_then_suggest_drafts"
    assert action.orchestration_plan.route == "answer_then_suggest_drafts"
    assert action.orchestration_plan.intent == "broad_overview"
    assert action.orchestration_plan.detected_scope_ids == ["linear-algebra"]
    assert "scope_memory:linear-algebra" in action.orchestration_plan.profile_layers_used
    assert action.orchestration_plan.candidate_drafts[0].title == "向量空间"
    assert "every candidate draft title and reason must use the same language" in (
        gateway.requests[0].system_instruction
    )


def test_planner_returns_reuse_action_from_provider() -> None:
    planner = QuestionPlanner(
        provider_gateway=FakeProviderGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"reuse_answer",'
                    '"selected_node_ids":["linear-map"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"The node directly answers the question."}'
                ),
                provider_name="gemini",
            )
        )
    )
    nodes = [_linear_map_node()]

    action = planner.plan(
        question="What is a linear map?",
        nodes=nodes,
        provider_profile=_provider_profile(),
    )

    assert action.action_type == "reuse_answer"
    assert action.selected_node_ids == ["linear-map"]
    assert action.draft_requests == []


def test_planner_returns_expand_action_from_provider() -> None:
    planner = QuestionPlanner(
        provider_gateway=FakeProviderGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"expand_with_drafts",'
                    '"selected_node_ids":["vector-space"],'
                    '"draft_requests":[{"title":"Linear Map",'
                    '"draft_type":"missing_definition",'
                    '"reason":"Need a definition node."}],'
                    '"user_visible_reason":"The knowledge base is missing the definition."}'
                ),
                provider_name="gemini",
            )
        )
    )
    nodes = [
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="atomic",
            summary="A vector space is closed under addition and scalar multiplication.",
            detail="Detailed definition of a vector space.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    ]

    action = planner.plan(
        question="Explain what a linear map is.",
        nodes=nodes,
        provider_profile=_provider_profile(),
    )

    assert action.action_type == "expand_with_drafts"
    assert action.selected_node_ids == ["vector-space"]
    assert [draft.draft_type for draft in action.draft_requests] == ["missing_definition"]


def test_planner_accepts_fenced_empty_reuse_answer() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    "```json\n"
                    "{\n"
                    '  "action_type": "reuse_answer",\n'
                    '  "selected_node_ids": [],\n'
                    '  "draft_requests": [],\n'
                    '  "user_visible_reason": "This can be answered directly."\n'
                    "}\n"
                    "```"
                ),
                provider_name="openai_compatible",
            )
        )
    )

    action = planner.plan(
        question="What is 1+1?",
        nodes=[_linear_map_node()],
        provider_profile=_provider_profile(),
    )

    assert action.action_type == "reuse_answer"
    assert action.selected_node_ids == []
    assert action.draft_requests == []
    assert action.user_visible_reason == "This can be answered directly."


def test_planner_includes_user_profile_summary_in_prompt(tmp_path) -> None:
    user_profile_path = tmp_path / "USER.md"
    user_profile_path.write_text(
        "# USER\n\nThe user prefers broad overviews before details.",
        encoding="utf-8",
    )
    gateway = RecordingPlannerGateway(
        ProviderResult(
            output_text=(
                '{"action_type":"reuse_answer",'
                '"selected_node_ids":[],'
                '"draft_requests":[],'
                '"user_visible_reason":"This can be answered directly."}'
            ),
            provider_name="gemini",
        )
    )
    planner = QuestionPlanner(
        provider_gateway=gateway,
        user_profile_repository=FileUserProfileRepository(user_profile_path),
    )

    planner.plan(
        question="What is a linear map?",
        nodes=[_linear_map_node()],
        provider_profile=_provider_profile(),
    )

    request = gateway.requests[0]

    assert "The user prefers broad overviews before details." in request.system_instruction


def test_planner_semantically_searches_the_complete_lightweight_node_index() -> None:
    nodes = [
        KnowledgeNode(
            id=f"node-{index}",
            title=f"Concept {index}",
            type="atomic",
            summary=f"Lightweight searchable summary {index}.",
            detail=f"Private full detail {index}.",
            parent_id=None,
            source="chat:test",
        )
        for index in range(15)
    ]
    gateway = RecordingPlannerGateway(
        ProviderResult(
            output_text=(
                '{"action_type":"reuse_answer",'
                '"selected_node_ids":["node-14"],'
                '"draft_requests":[],'
                '"user_visible_reason":"The final indexed node is relevant."}'
            ),
            provider_name="gemini",
        )
    )
    planner = QuestionPlanner(provider_gateway=gateway)

    action = planner.plan(
        question="Find the semantically related concept.",
        nodes=nodes,
        provider_profile=_provider_profile(),
    )

    request = gateway.requests[0]
    assert action.selected_node_ids == ["node-14"]
    assert "id=node-14; title=Concept 14" in request.user_message
    assert "Private full detail 14" not in request.user_message
    assert "semantic search space" in request.system_instruction


def _linear_map_node() -> KnowledgeNode:
    return KnowledgeNode(
        id="linear-map",
        title="Linear Map",
        type="atomic",
        summary="A linear map preserves addition and scalar multiplication.",
        detail="Detailed definition of a linear map.",
        parent_id="linear-algebra",
        source="chat:1",
        references=[],
        status="ready",
    )


def _provider_profile() -> ProviderProfile:
    return ProviderProfile(
        provider_type="gemini",
        model="gemini-2.5-flash",
        credential_id="gemini-main",
    )
