import pytest

from math_im_book.domain.models import ProviderProfile, ProviderResult
from math_im_book.domain.models import KnowledgeNode
from math_im_book.services.planner import PlannerOutputError, QuestionPlanner


class RecordingPlannerGateway:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result
        self.requests: list[object] = []

    def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
        self.requests.append(request)
        return self.result


def test_planner_prefers_bridge_draft_when_two_nodes_cover_partial_context() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"expand_with_drafts",'
                    '"selected_node_ids":["linear-combination","vector-space"],'
                    '"draft_requests":[{"title":"Linear Combinations In Vector Spaces",'
                    '"draft_type":"missing_bridge",'
                    '"reason":"Need a bridge between the selected nodes."}],'
                    '"user_visible_reason":"The selected nodes need a bridge."}'
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
            summary="A vector space has vectors, addition, and scalar multiplication.",
            detail="Detailed vector space axioms.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        ),
        KnowledgeNode(
            id="linear-combination",
            title="Linear Combination",
            type="atomic",
            summary="A linear combination is a finite sum of scalar multiples of vectors.",
            detail="Detailed definition of linear combinations.",
            parent_id="linear-algebra",
            source="chat:2",
            references=[],
            status="ready",
        ),
    ]

    action = planner.plan(
        question="How do linear combinations work inside a vector space?",
        nodes=nodes,
        provider_profile=_provider_profile(),
    )

    assert action.action_type == "expand_with_drafts"
    assert action.selected_node_ids == ["linear-combination", "vector-space"]
    assert [draft.draft_type for draft in action.draft_requests] == ["missing_bridge"]


def test_planner_uses_detail_and_symbols_for_reuse_confidence() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"reuse_answer",'
                    '"selected_node_ids":["linear-map"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"The detail and symbols directly answer the question."}'
                ),
                provider_name="gemini",
            )
        )
    )
    nodes = [
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="A linear map preserves the vector space operations.",
            detail="For T: V -> W, linearity means T(u + v) = T(u) + T(v) and T(cu) = cT(u).",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
            symbols={"T": "linear map from V to W"},
        )
    ]

    action = planner.plan(
        question="Why does T(u + v) = T(u) + T(v) express linearity?",
        nodes=nodes,
        provider_profile=_provider_profile(),
    )

    assert action.action_type == "reuse_answer"
    assert action.selected_node_ids == ["linear-map"]


def test_planner_prefers_llm_decision_when_provider_returns_structured_action() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"expand_with_drafts",'
                    '"selected_node_ids":["vector-space"],'
                    '"draft_requests":[{"title":"Linear Transformation",'
                    '"draft_type":"missing_definition",'
                    '"reason":"Need a node for the requested concept."}],'
                    '"user_visible_reason":"The current context needs a new concept node."}'
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
        question="Explain linear transformation.",
        nodes=nodes,
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )

    assert action.action_type == "expand_with_drafts"
    assert action.selected_node_ids == ["vector-space"]
    assert action.draft_requests[0].title == "Linear Transformation"


def test_planner_prompt_names_only_supported_action_types() -> None:
    gateway = RecordingPlannerGateway(
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
    planner = QuestionPlanner(provider_gateway=gateway)
    nodes = [
        KnowledgeNode(
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
    ]

    planner.plan(
        question="What is a linear map?",
        nodes=nodes,
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )

    request = gateway.requests[0]

    assert "route must be one of: answer_only, reuse_answer, answer_then_suggest_drafts" in (
        request.system_instruction
    )
    assert "select_node" not in request.system_instruction


def test_planner_rejects_invalid_provider_output() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text="not-json",
                provider_name="gemini",
            )
        )
    )
    nodes = [
        KnowledgeNode(
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
    ]

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=nodes,
            provider_profile=_provider_profile(),
        )


def test_planner_rejects_unknown_action_type() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"compact",'
                    '"selected_node_ids":["linear-map"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"Unknown planner action."}'
                ),
                provider_name="gemini",
            )
        )
    )
    nodes = [
        KnowledgeNode(
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
    ]

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=nodes,
            provider_profile=_provider_profile(),
        )


def test_planner_rejects_empty_draft_requests_for_expand() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"expand_with_drafts",'
                    '"selected_node_ids":["vector-space"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"Need a new draft."}'
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

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="Explain linear transformation.",
            nodes=nodes,
            provider_profile=_provider_profile(),
        )


def test_planner_rejects_unknown_selected_node_id() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"reuse_answer",'
                    '"selected_node_ids":["missing-node"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"Bad node id."}'
                ),
                provider_name="gemini",
            )
        )
    )
    nodes = [
        KnowledgeNode(
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
    ]

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=nodes,
            provider_profile=_provider_profile(),
        )


def test_planner_rejects_unknown_draft_type() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"action_type":"expand_with_drafts",'
                    '"selected_node_ids":[],'
                    '"draft_requests":[{"title":"Linear Map",'
                    '"draft_type":"freeform_generation",'
                    '"reason":"Bad draft type."}],'
                    '"user_visible_reason":"Bad draft."}'
                ),
                provider_name="gemini",
            )
        )
    )

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=[],
            provider_profile=_provider_profile(),
        )


def test_planner_clamps_confidence_into_unit_interval() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"route":"answer_then_suggest_drafts",'
                    '"intent":"broad_overview",'
                    '"persistence_decision":"suggest_drafts",'
                    '"confidence":1.7,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[],'
                    '"user_visible_summary":"High confidence."}'
                ),
                provider_name="gemini",
            )
        )
    )

    action = planner.plan(
        question="What is a linear map?",
        nodes=[],
        provider_profile=_provider_profile(),
    )

    assert action.orchestration_plan.confidence == 1.0


@pytest.mark.parametrize(
    ("raw_confidence", "expected"),
    [
        ('"0.72"', 0.72),
        ('"high"', 0.0),
        ("null", 0.0),
        ("true", 0.0),
    ],
)
def test_planner_degrades_invalid_confidence_without_failing_answer(
    raw_confidence: str,
    expected: float,
) -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"route":"answer_only",'
                    '"intent":"definition",'
                    '"persistence_decision":"do_not_persist",'
                    f'"confidence":{raw_confidence},'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[],'
                    '"user_visible_summary":"Answer directly."}'
                ),
                provider_name="gemini",
            )
        )
    )

    action = planner.plan(
        question="What is a linear map?",
        nodes=[],
        provider_profile=_provider_profile(),
    )

    assert action.orchestration_plan.confidence == expected


def test_planner_rejects_candidate_drafts_that_are_not_objects() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"route":"answer_then_suggest_drafts",'
                    '"intent":"broad_overview",'
                    '"persistence_decision":"suggest_drafts",'
                    '"confidence":0.5,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":["not-an-object"],'
                    '"user_visible_summary":"Bad candidate."}'
                ),
                provider_name="gemini",
            )
        )
    )

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=[],
            provider_profile=_provider_profile(),
        )


def test_planner_rejects_empty_candidate_drafts_for_draft_first_then_answer() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"route":"draft_first_then_answer",'
                    '"intent":"broad_overview",'
                    '"persistence_decision":"persist_first",'
                    '"confidence":0.75,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[],'
                    '"user_visible_summary":"Need a draft."}'
                ),
                provider_name="gemini",
            )
        )
    )

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=[],
            provider_profile=_provider_profile(),
        )


def test_planner_rejects_unknown_candidate_draft_type_in_new_route() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"route":"answer_then_suggest_drafts",'
                    '"intent":"broad_overview",'
                    '"persistence_decision":"suggest_drafts",'
                    '"confidence":0.5,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[{"title":"Linear Map",'
                    '"draft_type":"freeform_generation",'
                    '"reason":"Bad draft type."}],'
                    '"user_visible_summary":"Bad draft."}'
                ),
                provider_name="gemini",
            )
        )
    )

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=[],
            provider_profile=_provider_profile(),
        )


def test_planner_rejects_empty_candidate_draft_fields_in_new_route() -> None:
    planner = QuestionPlanner(
        provider_gateway=RecordingPlannerGateway(
            ProviderResult(
                output_text=(
                    '{"route":"answer_then_suggest_drafts",'
                    '"intent":"broad_overview",'
                    '"persistence_decision":"suggest_drafts",'
                    '"confidence":0.5,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[{"title":"",'
                    '"draft_type":"definition",'
                    '"reason":"Bad draft."}],'
                    '"user_visible_summary":"Bad draft."}'
                ),
                provider_name="gemini",
            )
        )
    )

    with pytest.raises(PlannerOutputError):
        planner.plan(
            question="What is a linear map?",
            nodes=[],
            provider_profile=_provider_profile(),
        )


def _provider_profile() -> ProviderProfile:
    return ProviderProfile(
        provider_type="gemini",
        model="gemini-2.5-flash",
        credential_id="gemini-main",
    )
