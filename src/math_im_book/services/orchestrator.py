from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from math_im_book.domain.models import (
    AgentAction,
    AgentStateItem,
    OrchestrationPlan,
    AskResult,
    AnswerAnchor,
    AnswerPayload,
    KnowledgeNode,
    PendingDraftRequest,
    ProviderProfile,
    SymbolContext,
    SessionBranchContext,
)
from math_im_book.services.context_selector import ContextSelector
from math_im_book.services.authorization import KnowledgeAuthorizationPolicy
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.services.planner import QuestionPlanner
from math_im_book.services.prompt_compiler import AnswerPromptCompiler
from math_im_book.services.providers import ProviderGateway, ProviderRequest
from math_im_book.services.symbols import SymbolRegistry
from math_im_book.storage.answer_styles import FileAnswerStyleRepository
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.strategy_agents import FileStrategyAgentRepository
from math_im_book.storage.sessions import clear_provider_response, remember_provider_response
from math_im_book.storage.user_profile import FileUserProfileRepository


class QuestionCancelledError(Exception):
    """Raised when a user stops an in-flight question."""


class KnowledgeOrchestrator:
    def __init__(
        self,
        repository: MarkdownKnowledgeRepository,
        planner: QuestionPlanner,
        symbol_registry: SymbolRegistry | None = None,
        provider_gateway: ProviderGateway | None = None,
        context_selector: ContextSelector | None = None,
        knowledge_job_repository: InMemoryKnowledgeJobRepository | None = None,
        answer_style_repository: FileAnswerStyleRepository | None = None,
        strategy_agent_repository: FileStrategyAgentRepository | None = None,
        prompt_compiler: AnswerPromptCompiler | None = None,
        user_profile_repository: FileUserProfileRepository | None = None,
        authorization_policy: KnowledgeAuthorizationPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.planner = planner
        self.symbol_registry = symbol_registry or SymbolRegistry()
        self.provider_gateway = provider_gateway
        if self.provider_gateway is not None and self.planner.provider_gateway is None:
            self.planner.provider_gateway = self.provider_gateway
        self.context_selector = context_selector
        self.knowledge_job_repository = (
            knowledge_job_repository
            or InMemoryKnowledgeJobRepository(repository)
        )
        if (
            self.provider_gateway is not None
            and self.knowledge_job_repository.provider_gateway is None
        ):
            self.knowledge_job_repository.provider_gateway = self.provider_gateway
        self.answer_style_repository = (
            answer_style_repository
            or FileAnswerStyleRepository(Path("data/config/answer_styles"))
        )
        self.strategy_agent_repository = (
            strategy_agent_repository
            or FileStrategyAgentRepository(Path("data/config/strategy_agents"))
        )
        self.prompt_compiler = prompt_compiler or AnswerPromptCompiler()
        self.user_profile_repository = user_profile_repository or FileUserProfileRepository()
        self.authorization_policy = authorization_policy or KnowledgeAuthorizationPolicy()

    def answer(
        self,
        question: str,
        session_id: str | None = None,
        provider_profile: ProviderProfile | None = None,
        branch_context: SessionBranchContext | None = None,
        answer_style_id: str | None = None,
        strategy_agent_id: str | None = None,
        stream_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
        knowledge_approval_policy: str = "agent_decides",
        cancel_check: Callable[[], bool] | None = None,
    ) -> AskResult:
        self._raise_if_cancelled(cancel_check)

        def guarded_stream_callback(delta: str) -> None:
            self._raise_if_cancelled(cancel_check)
            if stream_callback is not None:
                stream_callback(delta)

        resolved_stream_callback = (
            guarded_stream_callback if stream_callback is not None else None
        )
        clear_provider_response()
        self._emit_progress(
            progress_callback,
            stage="planning",
            label="正在理解问题并确定处理方式",
        )
        selected_branch_context = self._selected_branch_context(question, branch_context)
        answer_style_instructions = self._answer_style_instructions(answer_style_id)
        summary_nodes: list[KnowledgeNode] = []
        if selected_branch_context is not None:
            context_nodes = [
                self.repository.get_node(node_id)
                for node_id in selected_branch_context.active_node_ids
            ]
            summary_nodes = [
                self.repository.get_node(node_id)
                for node_id in selected_branch_context.summary_node_ids
            ]
        else:
            context_nodes = self.repository.list_nodes()
        planner_nodes = self._planner_candidate_nodes(selected_branch_context)
        self._emit_progress(
            progress_callback,
            stage="searching",
            label="正在检索当前 Scope 的知识索引",
            detail=f"检查 {len(planner_nodes)} 个节点的标题与摘要",
        )
        action = self.planner.plan(
            question=question,
            nodes=planner_nodes,
            session_id=session_id,
            provider_profile=provider_profile,
            branch_symbols=(
                dict(selected_branch_context.active_symbols)
                if selected_branch_context is not None
                else {}
            ),
        )
        self._raise_if_cancelled(cancel_check)
        self._emit_progress(
            progress_callback,
            stage="organizing",
            label="已整理本轮知识上下文",
            detail=f"选用 {len(action.selected_node_ids)} 个已有知识节点",
        )
        plan = action.orchestration_plan
        strategy_mode, strategy_reason = self._resolve_strategy_mode(
            question,
            strategy_agent_id,
            plan=plan,
        )
        if plan is not None:
            plan.strategy_mode = strategy_mode
            plan.strategy_reason = strategy_reason
            plan.knowledge_scope_id = (
                selected_branch_context.knowledge_scope_id
                if selected_branch_context is not None
                else None
            )
            plan.authorization = self.authorization_policy.decide(
                plan=plan,
                strategy_mode=strategy_mode,
                repository=self.repository,
                approval_policy=knowledge_approval_policy,
            )
        action = self._apply_knowledge_authorization(action)
        plan = action.orchestration_plan
        strategy_instructions = self._strategy_instructions(strategy_mode)
        selected_nodes = [self.repository.get_node(node_id) for node_id in action.selected_node_ids]
        branch_symbols = (
            dict(selected_branch_context.active_symbols)
            if selected_branch_context is not None
            else {}
        )
        symbol_context = self.symbol_registry.build_context(
            selected_nodes,
            branch_symbols=branch_symbols,
            include_local_symbols=True,
        )
        scope_symbol_context = self.symbol_registry.build_context(
            self._merge_unique_nodes(context_nodes, summary_nodes),
            branch_symbols=branch_symbols,
        )
        detail_symbol_guidance = self._symbol_guidance_text(
            symbols=symbol_context.symbols,
            conflicts=scope_symbol_context.conflicts,
        )
        if action.action_type == "ask_before_persist":
            summary = action.user_visible_reason or (
                plan.user_visible_summary if plan else "Knowledge approval is required."
            )
            detail = (
                "知识点计划已就绪，等待你的批准。批准后会先生成知识点，"
                "再基于这些知识点回答。"
            )
            return AskResult(
                action=action,
                answer=AnswerPayload(
                    summary=summary,
                    detail=detail,
                    references=[node.id for node in selected_nodes],
                    anchors=[],
                    symbols=symbol_context.symbols,
                    symbol_conflicts=scope_symbol_context.conflicts,
                    assistant_text=detail,
                ),
                drafts=[],
                created_node_ids=[],
                branch_context=selected_branch_context,
                orchestration_plan=plan,
                state_items=self._state_items_for_plan(plan),
            )

        if action.action_type in {
            "answer_only",
            "answer_then_suggest_drafts",
            "clarify_first",
            "compact_then_answer",
        }:
            summary = action.user_visible_reason or (plan.user_visible_summary if plan else "Answering directly.")
            detail = summary
            detail = self._detail_with_summary_context(detail, summary_nodes)
            detail = self._detail_with_symbol_guidance(detail, detail_symbol_guidance)
            self._emit_answering_progress(progress_callback)
            assistant_text = self._render_answer(
                question=question,
                summary=summary,
                detail=detail,
                symbols=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                session_id=session_id,
                provider_profile=provider_profile,
                strategy_instructions=strategy_instructions,
                knowledge_references=selected_nodes,
                answer_style_instructions=answer_style_instructions,
                stream_callback=resolved_stream_callback,
            )
            return AskResult(
                action=action,
                answer=AnswerPayload(
                    summary=summary,
                    detail=detail,
                    references=[node.id for node in selected_nodes],
                    anchors=[],
                    symbols=symbol_context.symbols,
                    symbol_conflicts=scope_symbol_context.conflicts,
                    assistant_text=assistant_text,
                ),
                drafts=[],
                created_node_ids=[],
                branch_context=selected_branch_context,
                orchestration_plan=plan,
                state_items=self._state_items_for_plan(plan),
            )

        if action.action_type == "reuse_answer":
            summary = self._reuse_summary(selected_nodes)
            detail = self._reuse_detail(selected_nodes)
            detail = self._detail_with_summary_context(detail, summary_nodes)
            detail = self._detail_with_symbol_guidance(detail, detail_symbol_guidance)
            self._emit_answering_progress(progress_callback)
            assistant_text = self._render_answer(
                question=question,
                summary=summary,
                detail=detail,
                symbols=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                session_id=session_id,
                provider_profile=provider_profile,
                strategy_instructions=strategy_instructions,
                knowledge_references=selected_nodes,
                answer_style_instructions=answer_style_instructions,
                stream_callback=resolved_stream_callback,
            )
            return AskResult(
                action=action,
                answer=AnswerPayload(
                    summary=summary,
                    detail=detail,
                    references=[node.id for node in selected_nodes],
                    anchors=[
                        AnswerAnchor(
                            anchor_id=node.id,
                            label=node.title,
                            status="ready",
                            node_id=node.id,
                        )
                        for node in selected_nodes
                    ],
                    symbols=symbol_context.symbols,
                    symbol_conflicts=scope_symbol_context.conflicts,
                    assistant_text=assistant_text,
                ),
                branch_context=selected_branch_context,
                orchestration_plan=plan,
                state_items=self._state_items_for_plan(plan),
            )

        if action.action_type == "expand_with_drafts" and action.draft_requests:
            self._raise_if_cancelled(cancel_check)
            draft_title = action.draft_requests[0].title
            self._emit_progress(
                progress_callback,
                stage="compiling",
                label="正在编译可复用的知识节点",
                detail=f"准备 {len(action.draft_requests)} 个节点",
            )
            answer_summary = f"{draft_title}: knowledge prepared."
            answer_detail = (
                action.user_visible_reason
                or f"Knowledge was compiled for {draft_title} before answering."
            )
            if selected_nodes:
                answer_detail += " Related knowledge: " + ", ".join(
                    node.title for node in selected_nodes
                ) + "."
            if summary_nodes:
                answer_detail += " Summary context: " + " ".join(
                    f"{node.title}: {node.summary}"
                    for node in summary_nodes
                )
            answer_detail = self._detail_with_symbol_guidance(
                answer_detail,
                detail_symbol_guidance,
            )
            draft_anchors = [
                AnswerAnchor(
                    anchor_id=self._slugify(draft.title),
                    label=draft.title,
                    status="pending",
                    node_id=None,
                )
                for draft in action.draft_requests
            ]
            job = self.knowledge_job_repository.submit_compile_job(
                question=question,
                anchors=draft_anchors,
                selected_node_ids=list(action.selected_node_ids),
                draft_requests=list(action.draft_requests),
                provider_profile=provider_profile,
                session_id=session_id,
                knowledge_scope_id=(
                    selected_branch_context.knowledge_scope_id
                    if selected_branch_context is not None
                    else None
                ),
                symbol_constraints=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                run_inline=True,
            )
            self._raise_if_cancelled(cancel_check)
            draft_anchors = list(job.anchors)
            compiled_nodes = [
                self.repository.get_node(anchor.node_id)
                for anchor in draft_anchors
                if anchor.status == "ready" and anchor.node_id is not None
            ]
            answer_nodes = self._merge_unique_nodes(selected_nodes, compiled_nodes)
            if compiled_nodes:
                answer_detail += " Compiled knowledge: " + ", ".join(
                    node.title for node in compiled_nodes
                ) + "."
            elif job.error_message:
                answer_detail += f" Knowledge compilation failed: {job.error_message}."
            self._emit_progress(
                progress_callback,
                stage="compiling",
                label=(
                    "知识节点已编译完成"
                    if job.status == "completed"
                    else "知识节点编译失败，回答尚未生成"
                ),
                detail=(
                    f"生成 {len(compiled_nodes)} 个可引用节点"
                    if job.status == "completed"
                    else job.error_message
                ),
                state="completed" if job.status == "completed" else "failed",
            )
            if job.status != "completed":
                failure_detail = (
                    "知识点生成失败，因此尚未生成回答。请重试知识点生成后再继续。"
                )
                return AskResult(
                    action=action,
                    answer=AnswerPayload(
                        summary=answer_summary,
                        detail=failure_detail,
                        references=[node.id for node in selected_nodes],
                        anchors=draft_anchors,
                        knowledge_job_id=job.job_id,
                        symbols=symbol_context.symbols,
                        symbol_conflicts=scope_symbol_context.conflicts,
                        assistant_text=failure_detail,
                    ),
                    drafts=action.draft_requests,
                    created_node_ids=[node.id for node in compiled_nodes],
                    branch_context=selected_branch_context,
                    orchestration_plan=plan,
                    state_items=self._state_items_for_plan(plan),
                )
            self._emit_answering_progress(progress_callback)
            assistant_text = self._render_answer(
                question=question,
                summary=answer_summary,
                detail=answer_detail,
                symbols=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                session_id=session_id,
                provider_profile=provider_profile,
                strategy_instructions=strategy_instructions,
                knowledge_references=answer_nodes,
                answer_style_instructions=answer_style_instructions,
                stream_callback=resolved_stream_callback,
            )
            return AskResult(
                action=action,
                answer=AnswerPayload(
                    summary=answer_summary,
                    detail=answer_detail,
                    references=[node.id for node in answer_nodes],
                    anchors=draft_anchors,
                    knowledge_job_id=job.job_id,
                    symbols=symbol_context.symbols,
                    symbol_conflicts=scope_symbol_context.conflicts,
                    assistant_text=assistant_text,
                ),
                drafts=action.draft_requests,
                created_node_ids=[node.id for node in compiled_nodes],
                branch_context=selected_branch_context,
                orchestration_plan=plan,
                state_items=self._state_items_for_plan(plan),
            )

        summary = action.user_visible_reason or (plan.user_visible_summary if plan else "Answering directly.")
        detail = summary
        detail = self._detail_with_summary_context(detail, summary_nodes)
        detail = self._detail_with_symbol_guidance(detail, detail_symbol_guidance)
        self._emit_answering_progress(progress_callback)
        assistant_text = self._render_answer(
            question=question,
            summary=summary,
            detail=detail,
            symbols=symbol_context.symbols,
            symbol_conflicts=scope_symbol_context.conflicts,
            session_id=session_id,
            provider_profile=provider_profile,
            strategy_instructions=strategy_instructions,
            knowledge_references=selected_nodes,
            answer_style_instructions=answer_style_instructions,
            stream_callback=resolved_stream_callback,
        )
        return AskResult(
            action=action,
            answer=AnswerPayload(
                summary=summary,
                detail=detail,
                references=[node.id for node in selected_nodes],
                anchors=[],
                symbols=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                assistant_text=assistant_text,
            ),
            drafts=[],
            created_node_ids=[],
            branch_context=selected_branch_context,
            orchestration_plan=plan,
            state_items=self._state_items_for_plan(plan),
        )

    def answer_from_knowledge(
        self,
        *,
        question: str,
        knowledge_node_ids: list[str],
        session_id: str | None = None,
        provider_profile: ProviderProfile | None = None,
        branch_context: SessionBranchContext | None = None,
        answer_style_id: str | None = None,
        strategy_agent_id: str | None = None,
        plan: OrchestrationPlan | None = None,
    ) -> AnswerPayload:
        """Generate a deferred answer after its knowledge nodes are ready."""
        clear_provider_response()
        knowledge_nodes: list[KnowledgeNode] = []
        for node_id in knowledge_node_ids:
            try:
                knowledge_nodes.append(self.repository.get_node(node_id))
            except FileNotFoundError:
                continue

        branch_symbols = dict(branch_context.active_symbols) if branch_context else {}
        symbol_context = self.symbol_registry.build_context(
            knowledge_nodes,
            branch_symbols=branch_symbols,
            include_local_symbols=True,
        )
        scope_nodes: list[KnowledgeNode] = []
        if branch_context is not None:
            for node_id in [
                *branch_context.active_node_ids,
                *branch_context.summary_node_ids,
            ]:
                try:
                    scope_nodes.append(self.repository.get_node(node_id))
                except FileNotFoundError:
                    continue
        scope_symbol_context = self.symbol_registry.build_context(
            self._merge_unique_nodes(scope_nodes, knowledge_nodes),
            branch_symbols=branch_symbols,
        )
        summary = (
            plan.user_visible_summary
            if plan is not None and plan.user_visible_summary
            else "知识上下文已准备完成。"
        )
        detail = (
            "已先生成并整理可复用知识点："
            + "、".join(node.title for node in knowledge_nodes)
            + "。请基于这些知识点回答，并在相关位置标注引用。"
        )
        detail = self._detail_with_symbol_guidance(
            detail,
            self._symbol_guidance_text(
                symbols=symbol_context.symbols,
                conflicts=scope_symbol_context.conflicts,
            ),
        )
        strategy_mode = (
            plan.strategy_mode
            if plan is not None and plan.strategy_mode in {"top-down", "raw"}
            else strategy_agent_id
        )
        assistant_text = self._render_answer(
            question=question,
            summary=summary,
            detail=detail,
            symbols=symbol_context.symbols,
            symbol_conflicts=scope_symbol_context.conflicts,
            session_id=session_id,
            provider_profile=provider_profile,
            strategy_instructions=self._strategy_instructions(strategy_mode),
            knowledge_references=knowledge_nodes,
            answer_style_instructions=self._answer_style_instructions(answer_style_id),
        )
        return AnswerPayload(
            summary=summary,
            detail=detail,
            references=[node.id for node in knowledge_nodes],
            symbols=symbol_context.symbols,
            symbol_conflicts=scope_symbol_context.conflicts,
            assistant_text=assistant_text,
        )

    def _selected_branch_context(
        self,
        question: str,
        branch_context: SessionBranchContext | None,
    ) -> SessionBranchContext | None:
        if branch_context is None:
            return None
        if self.context_selector is None:
            return branch_context
        return self.context_selector.select(question, branch_context)

    @staticmethod
    def _emit_progress(
        callback: Callable[[dict[str, object]], None] | None,
        *,
        stage: str,
        label: str,
        detail: str | None = None,
        state: str = "running",
    ) -> None:
        if callback is None:
            return
        event: dict[str, object] = {
            "stage": stage,
            "label": label,
            "state": state,
        }
        if detail:
            event["detail"] = detail
        callback(event)

    @classmethod
    def _emit_answering_progress(
        cls,
        callback: Callable[[dict[str, object]], None] | None,
    ) -> None:
        cls._emit_progress(
            callback,
            stage="answering",
            label="知识上下文已就绪，正在生成回答",
        )

    def _planner_candidate_nodes(
        self,
        branch_context: SessionBranchContext | None,
    ) -> list[KnowledgeNode]:
        """Expose the scoped title/summary index to the planning Agent.

        Lexical selection still supplies fast conversational context, while the
        planner can now search the complete selected Scope by meaning instead of
        being limited to literal matches from the first retrieval pass.
        """
        scope_id = branch_context.knowledge_scope_id if branch_context else None
        if self.context_selector is not None:
            return self.context_selector.list_scope_nodes(scope_id)
        return self.repository.list_nodes()

    @staticmethod
    def _apply_knowledge_authorization(
        action: AgentAction,
    ) -> AgentAction:
        """Apply the write policy before turning candidate gaps into durable nodes."""
        plan = action.orchestration_plan
        if plan is None or not plan.candidate_drafts:
            return action
        if plan.authorization.mode == "require_approval":
            plan.route = "ask_before_persist"
            plan.persistence_decision = "await_approval"
            return AgentAction(
                action_type="ask_before_persist",
                selected_node_ids=list(action.selected_node_ids),
                user_visible_reason=action.user_visible_reason,
                orchestration_plan=plan,
            )
        if action.action_type == "expand_with_drafts":
            return action
        plan.route = "draft_first_then_answer"
        plan.persistence_decision = "persist_first"
        return AgentAction(
            action_type="expand_with_drafts",
            selected_node_ids=list(action.selected_node_ids),
            draft_requests=[
                PendingDraftRequest(
                    title=candidate.title,
                    draft_type=candidate.draft_type,
                    reason=candidate.reason,
                )
                for candidate in plan.candidate_drafts
            ],
            user_visible_reason=action.user_visible_reason,
            orchestration_plan=plan,
        )

    @staticmethod
    def _detail_with_summary_context(
        detail: str,
        summary_nodes: list[KnowledgeNode],
    ) -> str:
        if not summary_nodes:
            return detail
        summary_text = " ".join(
            f"{node.title}: {node.summary}"
            for node in summary_nodes
        )
        return f"{detail} Summary context: {summary_text}"

    @staticmethod
    def _reuse_summary(nodes: list[KnowledgeNode]) -> str:
        if len(nodes) == 1:
            return nodes[0].summary
        return "\n".join(f"{node.title}: {node.summary}" for node in nodes)

    @staticmethod
    def _reuse_detail(nodes: list[KnowledgeNode]) -> str:
        if not nodes:
            return ""
        return (
            "Use the concise reusable knowledge references below as navigation "
            "anchors. Their full note details remain available to the user on "
            "separate knowledge pages and are intentionally not included here."
        )

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-_")
        return slug or "generated-node"

    def _state_items_for_plan(self, plan: OrchestrationPlan | None) -> list[AgentStateItem]:
        if plan is None:
            return []
        items: list[AgentStateItem] = []
        for draft in plan.candidate_drafts:
            items.append(
                AgentStateItem(
                    item_id=f"draft-{self._slugify(draft.title)}",
                    kind="knowledge_draft",
                    state="suggested",
                    title=draft.title,
                    reason=draft.reason,
                )
            )
        return items

    def _render_answer(
        self,
        question: str,
        summary: str,
        detail: str,
        symbols: dict[str, str],
        symbol_conflicts: list[str],
        session_id: str | None,
        provider_profile: ProviderProfile | None,
        strategy_instructions: str,
        knowledge_references: list[KnowledgeNode],
        answer_style_instructions: str | None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> str:
        if provider_profile is None or self.provider_gateway is None:
            clear_provider_response()
            if stream_callback is not None and detail:
                stream_callback(detail)
            return detail
        system_instruction = self.prompt_compiler.compile(
            question=question,
            summary=summary,
            detail=detail,
            symbols=symbols,
            symbol_conflicts=symbol_conflicts,
            strategy_instructions=strategy_instructions,
            knowledge_references=knowledge_references,
            user_profile_summary=self.user_profile_repository.load(),
            answer_style_instructions=answer_style_instructions,
        )
        request = ProviderRequest(
            system_instruction=system_instruction,
            user_message=question,
            session_id=session_id,
        )
        if stream_callback is not None:
            chunks: list[str] = []
            for chunk in self.provider_gateway.generate_stream(provider_profile, request):
                if not chunk:
                    continue
                chunks.append(chunk)
                stream_callback(chunk)
            output_text = "".join(chunks)
            if not output_text:
                provider_result = self.provider_gateway.generate(provider_profile, request)
                remember_provider_response(
                    provider_result.provider_name,
                    provider_result.raw_response_meta,
                )
                if provider_result.output_text:
                    stream_callback(provider_result.output_text)
                return provider_result.output_text
            remember_provider_response(provider_profile.provider_type, {})
            return output_text

        provider_result = self.provider_gateway.generate(provider_profile, request)
        remember_provider_response(
            provider_result.provider_name,
            provider_result.raw_response_meta,
        )
        return provider_result.output_text

    @staticmethod
    def _raise_if_cancelled(
        cancel_check: Callable[[], bool] | None,
    ) -> None:
        if cancel_check is not None and cancel_check():
            raise QuestionCancelledError("Question generation cancelled")

    @staticmethod
    def _merge_unique_nodes(*groups: list[KnowledgeNode]) -> list[KnowledgeNode]:
        merged: list[KnowledgeNode] = []
        seen_node_ids: set[str] = set()
        for group in groups:
            for node in group:
                if node.id in seen_node_ids:
                    continue
                seen_node_ids.add(node.id)
                merged.append(node)
        return merged

    @staticmethod
    def _detail_with_symbol_guidance(detail: str, guidance: str) -> str:
        if not guidance:
            return detail
        return f"{detail} {guidance}"

    @staticmethod
    def _symbol_guidance_text(
        symbols: dict[str, str],
        conflicts: list[str],
    ) -> str:
        if not symbols and not conflicts:
            return ""
        guidance_parts: list[str] = []
        if conflicts:
            guidance_parts.append(f"Symbol warning: {' '.join(conflicts)}")
        if symbols:
            symbol_text = ", ".join(
                f"{name}={meaning}" for name, meaning in sorted(symbols.items())
            )
            guidance_parts.append(f"Use {symbol_text}.")
        return " ".join(guidance_parts)

    def _strategy_instructions(self, strategy_agent_id: str | None) -> str:
        catalog = self.strategy_agent_repository.load()
        selected_strategy_agent_id = (
            strategy_agent_id or catalog.default_strategy_agent_id
        )
        if selected_strategy_agent_id:
            try:
                return catalog.get(selected_strategy_agent_id).instructions
            except KeyError:
                pass
        if catalog.agents:
            return catalog.agents[0].instructions
        raise KeyError("No strategy agents configured")

    def _resolve_strategy_mode(
        self,
        question: str,
        requested_strategy_agent_id: str | None,
        *,
        plan: OrchestrationPlan | None = None,
    ) -> tuple[str, str]:
        catalog = self.strategy_agent_repository.load()
        requested = (
            requested_strategy_agent_id or catalog.default_strategy_agent_id or "auto"
        ).strip()
        if requested in {"top-down", "raw"}:
            label = "Top Down" if requested == "top-down" else "Raw"
            return requested, f"已按你的选择使用 {label} 模式。"

        normalized = question.strip().lower()
        top_down_cues = (
            "系统",
            "整体",
            "框架",
            "体系",
            "梳理",
            "学习路线",
            "从头",
            "为什么需要",
            "overview",
            "big picture",
            "roadmap",
            "systematically",
            "connect",
            "relationship",
        )
        is_top_down = any(cue in normalized for cue in top_down_cues)
        if plan is not None and not is_top_down:
            is_top_down = (
                plan.intent in {"broad_exploratory", "broad_overview", "teach_concept"}
                or plan.route in {"answer_then_suggest_drafts", "draft_first_then_answer"}
                or len(plan.candidate_drafts) >= 2
            )
        if not is_top_down:
            is_top_down = len(normalized) >= 90 or normalized.count("？") + normalized.count("?") > 1
        if is_top_down:
            return (
                "top-down",
                "Agent 判断这个问题涉及整体结构或多个层次，将先搭框架再回答细节。",
            )
        return (
            "raw",
            "Agent 判断这个问题聚焦于具体知识点，将直接回答并只引用必要知识。",
        )

    def _answer_style_instructions(self, answer_style_id: str | None) -> str | None:
        if answer_style_id is None:
            return None
        normalized_answer_style_id = answer_style_id.strip()
        if normalized_answer_style_id in {"", "default"}:
            return None
        return self.answer_style_repository.get(normalized_answer_style_id).instructions
