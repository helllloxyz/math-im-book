from math_im_book.domain.models import (
    KnowledgeDraftCandidate,
    KnowledgeNode,
    OrchestrationPlan,
)
from math_im_book.services.authorization import KnowledgeAuthorizationPolicy
from math_im_book.storage.markdown import MarkdownKnowledgeRepository


def _plan(*, confidence: float = 0.9, count: int = 1) -> OrchestrationPlan:
    return OrchestrationPlan(
        route="draft_first_then_answer",
        intent="definition",
        persistence_decision="persist_first",
        confidence=confidence,
        user_visible_summary="补充缺失知识。",
        candidate_drafts=[
            KnowledgeDraftCandidate(
                title=f"Missing concept {index}",
                draft_type="missing_definition",
                reason="回答需要这个定义。",
            )
            for index in range(count)
        ],
    )


def test_authorization_auto_executes_one_high_confidence_new_node(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")

    decision = KnowledgeAuthorizationPolicy().decide(
        plan=_plan(),
        strategy_mode="top-down",
        repository=repository,
    )

    assert decision.mode == "auto_execute"
    assert decision.status == "auto_approved"
    assert decision.risk_level == "low"


def test_authorization_requires_approval_for_multiple_nodes(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")

    decision = KnowledgeAuthorizationPolicy().decide(
        plan=_plan(count=2),
        strategy_mode="top-down",
        repository=repository,
    )

    assert decision.mode == "require_approval"
    assert decision.status == "pending"
    assert "2 个知识节点" in decision.reason


def test_authorization_requires_approval_for_raw_mode(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")

    decision = KnowledgeAuthorizationPolicy().decide(
        plan=_plan(),
        strategy_mode="raw",
        repository=repository,
    )

    assert decision.status == "pending"
    assert "Raw 模式" in decision.reason


def test_authorization_requires_approval_before_overwriting_existing_node(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="missing-concept-0",
            title="Missing concept 0",
            type="definition",
            summary="Existing summary.",
            detail="Existing detail.",
            parent_id=None,
            source="manual",
        )
    )

    decision = KnowledgeAuthorizationPolicy().decide(
        plan=_plan(),
        strategy_mode="top-down",
        repository=repository,
    )

    assert decision.status == "pending"
    assert decision.risk_level == "high"
    assert "覆盖已有内容" in decision.reason


def test_full_auto_bypasses_agent_risk_checks(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="missing-concept-0",
            title="Missing concept 0",
            type="definition",
            summary="Existing summary.",
            detail="Existing detail.",
            parent_id=None,
            source="manual",
        )
    )

    decision = KnowledgeAuthorizationPolicy().decide(
        plan=_plan(confidence=0.2, count=2),
        strategy_mode="raw",
        repository=repository,
        approval_policy="full_auto",
    )

    assert decision.policy == "full_auto"
    assert decision.mode == "auto_execute"
    assert decision.status == "auto_approved"
    assert decision.risk_level == "high"
    assert "完全免审批" in decision.reason
    assert "覆盖已有内容" in decision.reason


def test_always_ask_requires_approval_for_a_safe_write(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")

    decision = KnowledgeAuthorizationPolicy().decide(
        plan=_plan(),
        strategy_mode="top-down",
        repository=repository,
        approval_policy="always_ask",
    )

    assert decision.policy == "always_ask"
    assert decision.mode == "require_approval"
    assert decision.status == "pending"
    assert "始终询问" in decision.reason
