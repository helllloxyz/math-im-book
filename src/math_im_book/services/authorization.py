from __future__ import annotations

import re

from math_im_book.domain.models import (
    KnowledgeAuthorizationDecision,
    OrchestrationPlan,
)
from math_im_book.storage.markdown import MarkdownKnowledgeRepository


class KnowledgeAuthorizationPolicy:
    """Decide whether a planned knowledge write may run without user approval."""

    auto_approval_confidence = 0.8

    def decide(
        self,
        *,
        plan: OrchestrationPlan | None,
        strategy_mode: str,
        repository: MarkdownKnowledgeRepository,
        approval_policy: str = "agent_decides",
    ) -> KnowledgeAuthorizationDecision:
        if plan is None or not plan.candidate_drafts:
            return KnowledgeAuthorizationDecision(policy=approval_policy)

        existing_node_ids = {node.id for node in repository.list_nodes()}
        collisions = [
            draft.title
            for draft in plan.candidate_drafts
            if self._slugify(draft.title) in existing_node_ids
        ]

        if collisions:
            risk_level = "high"
            requires_approval = True
            risk_reason = "候选节点可能覆盖已有内容。"
        elif strategy_mode != "top-down":
            risk_level = "medium"
            requires_approval = True
            risk_reason = "Raw 模式优先直接回答，本轮还会长期保存知识。"
        elif len(plan.candidate_drafts) > 1:
            risk_level = "medium"
            requires_approval = True
            risk_reason = f"计划一次写入 {len(plan.candidate_drafts)} 个知识节点。"
        elif plan.confidence < self.auto_approval_confidence:
            risk_level = "medium"
            requires_approval = True
            risk_reason = "Agent 对知识缺口的判断置信度不足。"
        else:
            risk_level = "low"
            requires_approval = False
            risk_reason = "单个、高置信度且不覆盖已有内容的节点。"

        if approval_policy == "full_auto":
            return KnowledgeAuthorizationDecision(
                policy=approval_policy,
                mode="auto_execute",
                status="auto_approved",
                risk_level=risk_level,
                operation="write_knowledge_nodes",
                reason=f"当前对话使用完全免审批模式，知识补充已自动执行。风险判断：{risk_reason}",
            )
        if approval_policy == "always_ask":
            return KnowledgeAuthorizationDecision(
                policy=approval_policy,
                mode="require_approval",
                status="pending",
                risk_level=risk_level,
                operation="write_knowledge_nodes",
                reason=f"当前对话设置为始终询问，写入知识库前需要你确认。风险判断：{risk_reason}",
            )
        if requires_approval:
            return KnowledgeAuthorizationDecision(
                policy=approval_policy,
                mode="require_approval",
                status="pending",
                risk_level=risk_level,
                operation="write_knowledge_nodes",
                reason=f"{risk_reason}需要你确认后再写入。",
            )
        return KnowledgeAuthorizationDecision(
            policy=approval_policy,
            mode="auto_execute",
            status="auto_approved",
            risk_level="low",
            operation="write_knowledge_nodes",
            reason=f"{risk_reason}可安全自动补充。",
        )

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-_")
        return slug or "compiled-knowledge"
