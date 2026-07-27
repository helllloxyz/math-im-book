import pytest

from math_im_book.domain.models import (
    KnowledgeNode,
    ProviderProfile,
    ProviderResult,
    SessionBranch,
)
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.services.orchestrator import KnowledgeOrchestrator
from math_im_book.services.planner import PlannerOutputError, QuestionPlanner
from math_im_book.services.providers import FakeProviderGateway
from math_im_book.storage.answer_styles import FileAnswerStyleRepository
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.strategy_agents import FileStrategyAgentRepository


class RecordingProviderGateway:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result
        self.requests: list[tuple[ProviderProfile, object]] = []

    def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
        if "context planner" in request.system_instruction:
            return ProviderResult(
                output_text=(
                    '{"action_type":"reuse_answer",'
                    '"selected_node_ids":["linear-map"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"The node directly answers the question."}'
                ),
                provider_name=self.result.provider_name,
            )
        self.requests.append((profile, request))
        return self.result


class SequenceProviderGateway:
    def __init__(self, results: list[ProviderResult]) -> None:
        self.results = results
        self.requests: list[tuple[ProviderProfile, object]] = []

    def generate(self, profile: ProviderProfile, request: object) -> ProviderResult:
        self.requests.append((profile, request))
        return self.results.pop(0)


class EmptyStreamRecordingProviderGateway(RecordingProviderGateway):
    def generate_stream(self, profile: ProviderProfile, request: object):
        self.requests.append((profile, request))
        if False:
            yield ""


def test_orchestrator_reuses_existing_nodes_in_answer(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"action_type":"reuse_answer",'
                    '"selected_node_ids":["linear-map"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"The node directly answers the question."}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="Assistant reply", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
    )

    result = orchestrator.answer(
        "What is a linear map?",
        provider_profile=_provider_profile(),
    )

    assert result.action.action_type == "reuse_answer"
    assert result.answer.summary.startswith("A linear map preserves")
    assert result.answer.references == ["linear-map"]
    assert result.created_node_ids == []
    assert result.orchestration_plan is not None
    assert result.orchestration_plan.route == "reuse_answer"


def test_orchestrator_reuses_multiple_selected_nodes_in_answer(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="vector-space",
            title="Vector Space",
            type="atomic",
            summary="A vector space has vector addition and scalar multiplication.",
            detail="A vector space is a set with compatible addition and scalar multiplication.",
            parent_id="linear-algebra",
            source="chat:1",
            references=[],
            status="ready",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="linear-combination",
            title="Linear Combination",
            type="atomic",
            summary="A linear combination is a finite sum of scalar multiples.",
            detail="A linear combination has the form a_1 v_1 + ... + a_n v_n.",
            parent_id="linear-algebra",
            source="chat:2",
            references=[],
            status="ready",
        )
    )
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"action_type":"reuse_answer",'
                    '"selected_node_ids":["vector-space","linear-combination"],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"Both nodes directly answer the question."}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="Combined answer", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
    )

    result = orchestrator.answer(
        "How do linear combinations work inside vector spaces?",
        provider_profile=_provider_profile(),
    )
    answer_request = gateway.requests[1][1]

    assert result.answer.references == ["vector-space", "linear-combination"]
    assert [anchor.node_id for anchor in result.answer.anchors] == [
        "vector-space",
        "linear-combination",
    ]
    assert "## Vector Space" in answer_request.system_instruction
    assert "## Linear Combination" in answer_request.system_instruction


def test_orchestrator_uses_top_down_strategy_prefix_by_default(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = RecordingProviderGateway(
        ProviderResult(output_text="Assistant reply", provider_name="gemini")
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=gateway,
        strategy_agent_repository=FileStrategyAgentRepository(
            tmp_path / "strategy_agents"
        ),
        answer_style_repository=FileAnswerStyleRepository(
            tmp_path / "answer_styles"
        ),
    )

    orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )

    request = gateway.requests[0][1]

    assert "Start with the high-level structure." in request.system_instruction
    assert "Use the user's question as-is." not in request.system_instruction


def test_orchestrator_raw_strategy_omits_top_down_only_guidance(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = RecordingProviderGateway(
        ProviderResult(output_text="Assistant reply", provider_name="gemini")
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=gateway,
        strategy_agent_repository=FileStrategyAgentRepository(
            tmp_path / "strategy_agents"
        ),
        answer_style_repository=FileAnswerStyleRepository(
            tmp_path / "answer_styles"
        ),
    )

    orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
        strategy_agent_id="raw",
    )

    request = gateway.requests[0][1]

    assert "Use the user's question as-is." in request.system_instruction
    assert "Start with the high-level structure." not in request.system_instruction


def test_orchestrator_appends_answer_style_override_after_strategy_prefix(
    tmp_path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = RecordingProviderGateway(
        ProviderResult(output_text="Assistant reply", provider_name="gemini")
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=gateway,
        strategy_agent_repository=FileStrategyAgentRepository(
            tmp_path / "strategy_agents"
        ),
        answer_style_repository=FileAnswerStyleRepository(
            tmp_path / "answer_styles"
        ),
    )

    orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )
    orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
        answer_style_id="concise",
    )

    default_request = gateway.requests[0][1]
    concise_request = gateway.requests[1][1]

    assert "Keep answers short and complete." not in default_request.system_instruction
    assert "Keep answers short and complete." in concise_request.system_instruction
    assert concise_request.system_instruction.startswith(default_request.system_instruction)


def test_orchestrator_treats_default_answer_style_id_as_no_override(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = RecordingProviderGateway(
        ProviderResult(output_text="Assistant reply", provider_name="gemini")
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=gateway,
        strategy_agent_repository=FileStrategyAgentRepository(
            tmp_path / "strategy_agents"
        ),
        answer_style_repository=FileAnswerStyleRepository(
            tmp_path / "answer_styles"
        ),
    )

    orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )
    orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
        answer_style_id="default",
    )

    no_override_request = gateway.requests[0][1]
    default_request = gateway.requests[1][1]

    assert default_request.system_instruction == no_override_request.system_instruction


def test_orchestrator_prompt_contract_answers_in_user_language(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = RecordingProviderGateway(
        ProviderResult(output_text="Assistant reply", provider_name="gemini")
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=gateway,
        strategy_agent_repository=FileStrategyAgentRepository(
            tmp_path / "strategy_agents"
        ),
        answer_style_repository=FileAnswerStyleRepository(
            tmp_path / "answer_styles"
        ),
    )

    orchestrator.answer(
        "Was ist eine lineare Abbildung?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )

    request = gateway.requests[0][1]

    assert "Answer in the user's language unless they request otherwise." in (
        request.system_instruction
    )
    assert "## Context" in request.system_instruction
    assert "## Question" in request.system_instruction
    assert "## Context\nQuestion:" not in request.system_instruction


def test_orchestrator_prompt_contract_includes_knowledge_system_rules(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = RecordingProviderGateway(
        ProviderResult(output_text="Assistant reply", provider_name="gemini")
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=gateway,
        strategy_agent_repository=FileStrategyAgentRepository(
            tmp_path / "strategy_agents"
        ),
        answer_style_repository=FileAnswerStyleRepository(
            tmp_path / "answer_styles"
        ),
    )

    orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )

    request = gateway.requests[0][1]

    assert "Reuse the provided knowledge before extending it." in request.system_instruction
    assert "Name knowledge gaps explicitly" in request.system_instruction
    assert "Preserve symbol meanings from the Symbols block." in request.system_instruction


def test_orchestrator_queues_knowledge_job_instead_of_persisting_new_node(
    tmp_path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
            symbols={"V": "vector space"},
        )
    )
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"action_type":"expand_with_drafts",'
                    '"selected_node_ids":["vector-space"],'
                    '"draft_requests":[{"title":"Linear Map",'
                    '"draft_type":"missing_definition",'
                    '"reason":"Need a definition node."}],'
                    '"user_visible_reason":"Existing knowledge is insufficient."}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="Queued answer", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
        knowledge_job_repository=knowledge_jobs,
    )

    result = orchestrator.answer(
        "Explain what a linear map is.",
        provider_profile=_provider_profile(),
        branch_context=SessionBranch(
            active_node_ids=["vector-space"],
            active_symbols={"T": "linear operator on V"},
        ),
    )

    assert result.action.action_type == "expand_with_drafts"
    assert [draft.draft_type for draft in result.drafts] == ["missing_definition"]
    assert result.created_node_ids == []
    assert [anchor.label for anchor in result.answer.anchors] == ["Linear Map"]
    assert result.answer.anchors[0].status == "pending"
    assert result.answer.knowledge_job_id is not None
    job = knowledge_jobs.get_job(result.answer.knowledge_job_id)
    assert job.status == "queued"
    assert job.symbol_constraints == {
        "T": "linear operator on V",
        "V": "vector space",
    }

    with pytest.raises(FileNotFoundError):
        repository.get_node("linear-map")


def test_orchestrator_queues_all_draft_first_candidates(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"route":"draft_first_then_answer",'
                    '"intent":"definition",'
                    '"persistence_decision":"persist_first",'
                    '"confidence":0.88,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"candidate_drafts":['
                    '{"title":"Linear Map","draft_type":"missing_definition","reason":"Need a definition."},'
                    '{"title":"Kernel","draft_type":"missing_definition","reason":"Need a definition."}'
                    '],'
                    '"user_visible_summary":"Create durable notes first."}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="Queued answer", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
        knowledge_job_repository=knowledge_jobs,
    )

    result = orchestrator.answer(
        "Explain linear maps and kernels.",
        provider_profile=_provider_profile(),
    )

    assert result.action.action_type == "expand_with_drafts"
    assert [anchor.label for anchor in result.answer.anchors] == ["Linear Map", "Kernel"]
    assert [anchor.status for anchor in result.answer.anchors] == ["pending", "pending"]
    assert result.answer.knowledge_job_id is not None
    job = knowledge_jobs.get_job(result.answer.knowledge_job_id)
    assert [draft.title for draft in job.draft_requests] == ["Linear Map", "Kernel"]
    assert [anchor.label for anchor in job.anchors] == ["Linear Map", "Kernel"]


def test_orchestrator_renders_empty_reuse_answer_without_knowledge_job(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"action_type":"reuse_answer",'
                    '"selected_node_ids":[],'
                    '"draft_requests":[],'
                    '"user_visible_reason":"No knowledge node is needed."}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="1 + 1 = 2.", provider_name="gemini"),
        ]
    )
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
        knowledge_job_repository=knowledge_jobs,
    )

    result = orchestrator.answer(
        "What is 1+1?",
        provider_profile=_provider_profile(),
    )

    assert result.action.action_type == "reuse_answer"
    assert result.answer.assistant_text == "1 + 1 = 2."
    assert result.answer.references == []
    assert result.answer.anchors == []
    assert result.answer.knowledge_job_id is None


def test_orchestrator_suggests_drafts_without_starting_knowledge_job(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    gateway = SequenceProviderGateway(
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
            ProviderResult(output_text="线性代数研究线性结构。", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
        knowledge_job_repository=knowledge_jobs,
    )

    result = orchestrator.answer("线性代数", provider_profile=_provider_profile())

    assert result.action.action_type == "answer_then_suggest_drafts"
    assert result.answer.knowledge_job_id is None
    assert result.answer.anchors == []
    assert result.answer.assistant_text == "线性代数研究线性结构。"
    assert result.state_items[0].state == "suggested"
    assert result.state_items[0].title == "Vector Space"
    assert result.orchestration_plan.route == "answer_then_suggest_drafts"
    assert result.orchestration_plan.detected_scope_ids == ["linear-algebra"]


def test_orchestrator_does_not_queue_knowledge_job_for_compact_then_answer(
    tmp_path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"route":"compact_then_answer",'
                    '"intent":"compact",'
                    '"persistence_decision":"do_not_persist",'
                    '"confidence":0.6,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[],'
                    '"user_visible_summary":"先压缩当前上下文，再直接回答。"}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="Compact answer.", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
        knowledge_job_repository=knowledge_jobs,
    )

    result = orchestrator.answer("请先压缩再回答。", provider_profile=_provider_profile())

    assert result.action.action_type == "compact_then_answer"
    assert result.answer.assistant_text == "Compact answer."
    assert result.answer.knowledge_job_id is None
    assert result.drafts == []


def test_orchestrator_does_not_queue_knowledge_job_for_empty_draft_first_then_answer(
    tmp_path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"route":"draft_first_then_answer",'
                    '"intent":"broad_overview",'
                    '"persistence_decision":"persist_first",'
                    '"confidence":0.72,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":[],'
                    '"profile_layers_used":[],'
                    '"profile_context_summary":null,'
                    '"candidate_drafts":[],'
                    '"user_visible_summary":"需要先整理知识，但当前没有有效候选。"}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="Direct answer.", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
        knowledge_job_repository=knowledge_jobs,
    )

    with pytest.raises(PlannerOutputError):
        orchestrator.answer("先整理再回答。", provider_profile=_provider_profile())


def _provider_profile() -> ProviderProfile:
    return ProviderProfile(
        provider_type="gemini",
        model="gemini-2.5-flash",
        credential_id="gemini-main",
    )


def test_orchestrator_streams_provider_chunks_via_callback(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=FakeProviderGateway(
            ProviderResult(output_text="Rendered by stream.", provider_name="gemini")
        ),
    )
    streamed_chunks: list[str] = []

    result = orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
        stream_callback=streamed_chunks.append,
    )

    assert "".join(streamed_chunks) == "Rendered by stream."
    assert result.answer.assistant_text == "Rendered by stream."


def test_orchestrator_falls_back_when_provider_stream_returns_no_text(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
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
        )
    )
    gateway = EmptyStreamRecordingProviderGateway(
        ProviderResult(output_text="Rendered by non-stream fallback.", provider_name="gemini")
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(),
        provider_gateway=gateway,
    )
    streamed_chunks: list[str] = []

    result = orchestrator.answer(
        "What is a linear map?",
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
        stream_callback=streamed_chunks.append,
    )

    assert streamed_chunks == ["Rendered by non-stream fallback."]
    assert result.answer.assistant_text == "Rendered by non-stream fallback."
