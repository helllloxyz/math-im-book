from math_im_book.domain.models import KnowledgeNode, SessionBranchContext
from math_im_book.services.context_selector import ContextSelector
from math_im_book.storage.markdown import MarkdownKnowledgeRepository


def _save_node(
    repository: MarkdownKnowledgeRepository,
    *,
    node_id: str,
    title: str,
    summary: str,
) -> None:
    repository.save_node(
        KnowledgeNode(
            id=node_id,
            title=title,
            type="definition",
            summary=summary,
            detail=summary,
            parent_id=None,
            source="chat:test",
        )
    )


def test_context_selector_limits_chinese_lexical_search_to_knowledge_scope(
    tmp_path,
) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    _save_node(
        repository,
        node_id="uniform-convergence",
        title="一致收敛",
        summary="一致收敛控制函数列在整个定义域上的误差。",
    )
    _save_node(
        repository,
        node_id="uniform-continuity",
        title="一致连续",
        summary="一致连续要求同一个距离尺度适用于整个定义域。",
    )
    selector = ContextSelector(
        repository,
        scope_node_ids_resolver=lambda scope_id: (
            ["uniform-convergence"] if scope_id == "scope-analysis" else []
        ),
    )

    selected = selector.select(
        "为什么需要一致收敛？",
        SessionBranchContext(
            active_node_ids=["uniform-continuity"],
            knowledge_scope_id="scope-analysis",
        ),
    )

    assert selected.knowledge_scope_id == "scope-analysis"
    assert selected.active_node_ids == ["uniform-convergence"]
    assert "uniform-continuity" not in selected.summary_node_ids

