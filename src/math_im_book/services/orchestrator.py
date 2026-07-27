from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from math_im_book.domain.models import (
    AgentStateItem,
    OrchestrationPlan,
    AskResult,
    AnswerAnchor,
    AnswerPayload,
    KnowledgeNode,
    ProviderProfile,
    SymbolContext,
    SessionBranchContext,
)
from math_im_book.services.context_selector import ContextSelector
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

    def answer(
        self,
        question: str,
        session_id: str | None = None,
        provider_profile: ProviderProfile | None = None,
        branch_context: SessionBranchContext | None = None,
        answer_style_id: str | None = None,
        strategy_agent_id: str | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> AskResult:
        clear_provider_response()
        selected_branch_context = self._selected_branch_context(question, branch_context)
        strategy_instructions = self._strategy_instructions(strategy_agent_id)
        answer_style_instructions = self._answer_style_instructions(answer_style_id)
        summary_nodes: list[KnowledgeNode] = []
        if selected_branch_context is not None:
            nodes = [
                self.repository.get_node(node_id)
                for node_id in selected_branch_context.active_node_ids
            ]
            summary_nodes = [
                self.repository.get_node(node_id)
                for node_id in selected_branch_context.summary_node_ids
            ]
        else:
            nodes = self.repository.list_nodes()
        action = self.planner.plan(
            question=question,
            nodes=nodes,
            session_id=session_id,
            provider_profile=provider_profile,
            branch_symbols=(
                dict(selected_branch_context.active_symbols)
                if selected_branch_context is not None
                else {}
            ),
        )
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
            self._merge_unique_nodes(nodes, summary_nodes),
            branch_symbols=branch_symbols,
        )
        detail_symbol_guidance = self._symbol_guidance_text(
            symbols=symbol_context.symbols,
            conflicts=scope_symbol_context.conflicts,
        )
        plan = action.orchestration_plan
        if action.action_type in {
            "answer_only",
            "answer_then_suggest_drafts",
            "ask_before_persist",
            "clarify_first",
            "compact_then_answer",
        }:
            summary = action.user_visible_reason or (plan.user_visible_summary if plan else "Answering directly.")
            detail = summary
            detail = self._detail_with_summary_context(detail, summary_nodes)
            detail = self._detail_with_symbol_guidance(detail, detail_symbol_guidance)
            assistant_text = self._render_answer(
                question=question,
                summary=summary,
                detail=detail,
                symbols=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                session_id=session_id,
                provider_profile=provider_profile,
                strategy_instructions=strategy_instructions,
                answer_style_instructions=answer_style_instructions,
                stream_callback=stream_callback,
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
            assistant_text = self._render_answer(
                question=question,
                summary=summary,
                detail=detail,
                symbols=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                session_id=session_id,
                provider_profile=provider_profile,
                strategy_instructions=strategy_instructions,
                answer_style_instructions=answer_style_instructions,
                stream_callback=stream_callback,
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
            draft_title = action.draft_requests[0].title
            answer_summary = f"{draft_title}: compilation queued."
            answer_detail = (
                action.user_visible_reason
                or f"A knowledge compilation job is running for {draft_title}."
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
                symbol_constraints=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
            )
            assistant_text = self._render_answer(
                question=question,
                summary=answer_summary,
                detail=answer_detail,
                symbols=symbol_context.symbols,
                symbol_conflicts=scope_symbol_context.conflicts,
                session_id=session_id,
                provider_profile=provider_profile,
                strategy_instructions=strategy_instructions,
                answer_style_instructions=answer_style_instructions,
                stream_callback=stream_callback,
            )
            return AskResult(
                action=action,
                answer=AnswerPayload(
                    summary=answer_summary,
                    detail=answer_detail,
                    references=list(action.selected_node_ids),
                    anchors=draft_anchors,
                    knowledge_job_id=job.job_id,
                    symbols=symbol_context.symbols,
                    symbol_conflicts=scope_symbol_context.conflicts,
                    assistant_text=assistant_text,
                ),
                drafts=action.draft_requests,
                created_node_ids=[],
                branch_context=selected_branch_context,
                orchestration_plan=plan,
                state_items=self._state_items_for_plan(plan),
            )

        summary = action.user_visible_reason or (plan.user_visible_summary if plan else "Answering directly.")
        detail = summary
        detail = self._detail_with_summary_context(detail, summary_nodes)
        detail = self._detail_with_symbol_guidance(detail, detail_symbol_guidance)
        assistant_text = self._render_answer(
            question=question,
            summary=summary,
            detail=detail,
            symbols=symbol_context.symbols,
            symbol_conflicts=scope_symbol_context.conflicts,
            session_id=session_id,
            provider_profile=provider_profile,
            strategy_instructions=strategy_instructions,
            answer_style_instructions=answer_style_instructions,
            stream_callback=stream_callback,
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
        if len(nodes) == 1:
            return nodes[0].detail
        return "\n\n".join(f"## {node.title}\n\n{node.detail}" for node in nodes)

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

    def _answer_style_instructions(self, answer_style_id: str | None) -> str | None:
        if answer_style_id is None:
            return None
        normalized_answer_style_id = answer_style_id.strip()
        if normalized_answer_style_id in {"", "default"}:
            return None
        return self.answer_style_repository.get(normalized_answer_style_id).instructions
