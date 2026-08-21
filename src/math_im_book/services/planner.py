from __future__ import annotations

import json
import math
from typing import Any

from math_im_book.domain.models import (
    AgentAction,
    KnowledgeDraftCandidate,
    KnowledgeNode,
    OrchestrationPlan,
    PendingDraftRequest,
    ProviderProfile,
)
from math_im_book.services.providers import ProviderGateway, ProviderRequest
from math_im_book.storage.user_profile import FileUserProfileRepository


class PlannerError(Exception):
    pass


class PlannerOutputError(PlannerError):
    pass


class QuestionPlanner:
    _ALLOWED_ACTION_TYPES = {"reuse_answer", "expand_with_drafts"}
    _ALLOWED_DRAFT_TYPES = {
        "missing_definition",
        "missing_detail",
        "missing_bridge",
        "definition",
        "theorem",
        "proof_skeleton",
        "example",
        "counterexample",
        "notation",
        "bridge",
        "summary",
    }

    _ALLOWED_ROUTES = {
        "answer_only",
        "reuse_answer",
        "answer_then_suggest_drafts",
        "draft_first_then_answer",
        "ask_before_persist",
        "clarify_first",
        "compact_then_answer",
    }

    _ROUTE_TO_LEGACY_ACTION = {
        "answer_only": "answer_only",
        "reuse_answer": "reuse_answer",
        "answer_then_suggest_drafts": "answer_then_suggest_drafts",
        "draft_first_then_answer": "expand_with_drafts",
        "ask_before_persist": "ask_before_persist",
        "clarify_first": "clarify_first",
        "compact_then_answer": "compact_then_answer",
    }

    def __init__(
        self,
        provider_gateway: ProviderGateway | None = None,
        user_profile_repository: FileUserProfileRepository | None = None,
    ) -> None:
        self.provider_gateway = provider_gateway
        self.user_profile_repository = user_profile_repository or FileUserProfileRepository()

    def plan(
        self,
        question: str,
        nodes: list[KnowledgeNode],
        session_id: str | None = None,
        provider_profile: ProviderProfile | None = None,
        branch_symbols: dict[str, str] | None = None,
    ) -> AgentAction:
        if provider_profile is None or self.provider_gateway is None:
            return self.plan_without_provider(question, nodes, branch_symbols)
        return self._plan_with_provider(
            question,
            nodes,
            session_id,
            provider_profile,
            branch_symbols or {},
        )

    def plan_without_provider(
        self,
        question: str,
        nodes: list[KnowledgeNode],
        branch_symbols: dict[str, str] | None = None,
    ) -> AgentAction:
        selected_node_ids: list[str] = []
        route = "answer_only"
        persistence_decision = "do_not_persist"
        summary = "I will answer directly without saving a knowledge node."
        plan = OrchestrationPlan(
            route=route,
            intent=self._infer_basic_intent(question),
            persistence_decision=persistence_decision,
            confidence=0.55,
            user_visible_summary=summary,
            detected_scope_ids=[],
            profile_layers_used=[],
            profile_context_summary=None,
        )
        return AgentAction(
            action_type=route,
            selected_node_ids=selected_node_ids,
            user_visible_reason=summary,
            orchestration_plan=plan,
        )

    @staticmethod
    def _infer_basic_intent(question: str) -> str:
        normalized = question.strip().lower()
        if normalized.startswith("/compact"):
            return "compact"
        if any(token in normalized for token in ("prove", "证明", "why", "为什么")):
            return "proof"
        if any(token in normalized for token in ("what is", "什么是", "define", "定义")):
            return "definition"
        return "broad_overview"

    def _plan_with_provider(
        self,
        question: str,
        nodes: list[KnowledgeNode],
        session_id: str | None,
        provider_profile: ProviderProfile,
        branch_symbols: dict[str, str],
    ) -> AgentAction:
        candidate_node_ids = {node.id for node in nodes}
        user_profile_summary = self.user_profile_repository.load()
        provider_result = self.provider_gateway.generate(
            provider_profile,
            ProviderRequest(
                system_instruction=self._planner_system_instruction(
                    user_profile_summary
                ),
                user_message=(
                    f"Question: {question}\n"
                    "Active symbols: "
                    + (
                        ", ".join(
                            f"{name}={meaning}"
                            for name, meaning in sorted(branch_symbols.items())
                        )
                        if branch_symbols
                        else "none"
                    )
                    + "\n"
                    "Knowledge node index (titles and summaries only):\n"
                    + "\n".join(
                        f"- id={node.id}; title={node.title}; summary={node.summary}"
                        for node in nodes
                    )
                ),
                session_id=session_id,
                session_id_suffix="planner",
                purpose="planner",
            ),
        )
        try:
            payload = json.loads(self._strip_markdown_json_fence(provider_result.output_text))
        except json.JSONDecodeError:
            raise PlannerOutputError("Planner provider returned non-JSON output")
        if not isinstance(payload, dict):
            raise PlannerOutputError("Planner provider returned non-object JSON")

        return self._parse_orchestration_payload(payload, candidate_node_ids)

    def _parse_orchestration_payload(
        self,
        payload: dict[str, Any],
        candidate_node_ids: set[str],
    ) -> AgentAction:
        route = payload.get("route")
        if isinstance(route, str):
            return self._parse_new_route_payload(payload, candidate_node_ids, route)
        return self._parse_legacy_payload(payload, candidate_node_ids)

    def _parse_new_route_payload(
        self,
        payload: dict[str, Any],
        candidate_node_ids: set[str],
        route: str,
    ) -> AgentAction:
        if route not in self._ALLOWED_ROUTES:
            raise PlannerOutputError("Planner provider returned unsupported route")

        selected_node_ids = self._validated_selected_node_ids(
            payload.get("selected_node_ids"), candidate_node_ids
        )

        detected_scope_ids = self._string_list(payload.get("detected_scope_ids", []))
        profile_layers_used = self._string_list(payload.get("profile_layers_used", []))

        profile_context_summary = payload.get("profile_context_summary")
        if not isinstance(profile_context_summary, str):
            profile_context_summary = None

        confidence = self._validated_confidence(payload.get("confidence"))

        candidate_drafts = self._validated_candidate_drafts(
            payload.get("candidate_drafts"),
            route=route,
        )

        user_visible_summary = self._validated_reason(payload.get("user_visible_summary"))
        intent = payload.get("intent")
        if not isinstance(intent, str):
            intent = "broad_overview"

        persistence_decision = payload.get("persistence_decision")
        if not isinstance(persistence_decision, str):
            persistence_decision = "do_not_persist"

        plan = OrchestrationPlan(
            route=route,
            intent=intent,
            persistence_decision=persistence_decision,
            confidence=confidence,
            user_visible_summary=user_visible_summary,
            detected_scope_ids=detected_scope_ids,
            profile_layers_used=profile_layers_used,
            profile_context_summary=profile_context_summary,
            candidate_drafts=candidate_drafts,
        )

        action_type = self._ROUTE_TO_LEGACY_ACTION.get(route, "answer_only")

        draft_requests = []
        if action_type == "expand_with_drafts":
            draft_requests = [
                PendingDraftRequest(title=d.title, draft_type=d.draft_type, reason=d.reason)
                for d in candidate_drafts
            ]

        return AgentAction(
            action_type=action_type,
            selected_node_ids=selected_node_ids,
            draft_requests=draft_requests,
            user_visible_reason=user_visible_summary,
            orchestration_plan=plan,
        )

    def _validated_selected_node_ids(
        self,
        value: object,
        candidate_node_ids: set[str],
    ) -> list[str]:
        if not self._is_valid_string_list(value):
            raise PlannerOutputError("Planner provider returned invalid selected_node_ids")
        selected_node_ids = list(value)
        if len(set(selected_node_ids)) != len(selected_node_ids):
            raise PlannerOutputError("Planner provider returned duplicate selected_node_ids")
        unknown_node_ids = set(selected_node_ids) - candidate_node_ids
        if unknown_node_ids:
            raise PlannerOutputError("Planner provider selected unknown node ids")
        return selected_node_ids

    def _validated_confidence(self, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PlannerOutputError("Planner provider returned invalid confidence")
        confidence = float(value)
        if not math.isfinite(confidence):
            raise PlannerOutputError("Planner provider returned invalid confidence")
        return max(0.0, min(1.0, confidence))

    def _validated_candidate_drafts(
        self,
        value: object,
        *,
        route: str,
    ) -> list[KnowledgeDraftCandidate]:
        if not isinstance(value, list):
            raise PlannerOutputError("candidate_drafts must be a list")
        candidate_drafts: list[KnowledgeDraftCandidate] = []
        for raw_draft in value:
            if not isinstance(raw_draft, dict):
                raise PlannerOutputError("candidate_drafts must contain objects")
            title = raw_draft.get("title")
            draft_type = raw_draft.get("draft_type")
            reason = raw_draft.get("reason")
            if not all(
                isinstance(item, str) and item.strip()
                for item in (title, draft_type, reason)
            ):
                raise PlannerOutputError(
                    "candidate_drafts require non-empty title, draft_type, and reason"
                )
            if draft_type not in self._ALLOWED_DRAFT_TYPES:
                raise PlannerOutputError("Planner provider returned unsupported draft_type")
            candidate_drafts.append(
                KnowledgeDraftCandidate(
                    title=title.strip(),
                    draft_type=draft_type,
                    reason=reason.strip(),
                )
            )
        if route == "draft_first_then_answer" and not candidate_drafts:
            raise PlannerOutputError("draft_first_then_answer requires candidate_drafts")
        return candidate_drafts

    def _parse_legacy_payload(
        self,
        payload: dict[str, Any],
        candidate_node_ids: set[str],
    ) -> AgentAction:
        action_type = payload.get("action_type")
        if not isinstance(action_type, str) or action_type not in self._ALLOWED_ACTION_TYPES:
            raise PlannerOutputError("Planner provider returned unsupported action_type")

        selected_node_ids = payload.get("selected_node_ids", [])
        if not self._is_valid_string_list(selected_node_ids):
            raise PlannerOutputError("Planner provider returned invalid selected_node_ids")
        if len(set(selected_node_ids)) != len(selected_node_ids):  # type: ignore
            raise PlannerOutputError("Planner provider returned duplicate selected_node_ids")
        unknown_node_ids = set(selected_node_ids) - candidate_node_ids  # type: ignore
        if unknown_node_ids:
            raise PlannerOutputError("Planner provider selected unknown node ids")

        raw_drafts = payload.get("draft_requests", [])
        user_visible_reason = self._validated_reason(payload.get("user_visible_reason"))

        draft_requests: list[PendingDraftRequest] = []
        if action_type == "reuse_answer":
            if raw_drafts not in ([], None):
                raise PlannerOutputError("reuse_answer must not include draft_requests")
        else:
            if not isinstance(raw_drafts, list) or not raw_drafts:
                raise PlannerOutputError("expand_with_drafts requires draft_requests")
            for raw_draft in raw_drafts:
                if not isinstance(raw_draft, dict):
                    raise PlannerOutputError("draft_requests must contain objects")
                title = raw_draft.get("title")
                draft_type = raw_draft.get("draft_type")
                reason = raw_draft.get("reason")
                if not all(isinstance(value, str) and value for value in (title, draft_type, reason)):
                    raise PlannerOutputError("draft_requests require title, draft_type, and reason")
                if draft_type not in self._ALLOWED_DRAFT_TYPES:
                    raise PlannerOutputError("Planner provider returned unsupported draft_type")
                draft_requests.append(
                    PendingDraftRequest(title=title, draft_type=draft_type, reason=reason)
                )
            if not draft_requests:
                raise PlannerOutputError("expand_with_drafts requires draft_requests")

        plan = OrchestrationPlan(
            route="draft_first_then_answer" if action_type == "expand_with_drafts" else "reuse_answer",
            intent="definition" if draft_requests else "broad_overview",
            persistence_decision="persist_first" if draft_requests else "do_not_persist",
            confidence=0.7,
            user_visible_summary=user_visible_reason,
            detected_scope_ids=[],
            profile_layers_used=["knowledge_context"] if selected_node_ids else [],
            profile_context_summary=None,
            candidate_drafts=[
                KnowledgeDraftCandidate(title=d.title, draft_type=d.draft_type, reason=d.reason)
                for d in draft_requests
            ],
        )

        return AgentAction(
            action_type=action_type,
            selected_node_ids=selected_node_ids,  # type: ignore
            draft_requests=draft_requests,
            user_visible_reason=user_visible_reason,
            orchestration_plan=plan,
        )

    @staticmethod
    def _string_list(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        return [v for v in values if isinstance(v, str) and v]

    @staticmethod
    def _is_valid_string_list(values: object) -> bool:
        return isinstance(values, list) and all(isinstance(value, str) and value for value in values)

    @staticmethod
    def _validated_reason(value: object) -> str:
        return value if isinstance(value, str) else ""

    def _planner_system_instruction(self, user_profile_summary: str) -> str:
        profile_block = self._user_profile_block(user_profile_summary)
        parts = [
            "You are a context planner for a math knowledge system. "
            "Return bare JSON only, with no Markdown fences or explanatory text. "
            "Prefer the new keys route, intent, persistence_decision, confidence, "
            "selected_node_ids, detected_scope_ids, profile_layers_used, "
            "profile_context_summary, candidate_drafts, user_visible_summary. "
            "route must be one of: answer_only, reuse_answer, answer_then_suggest_drafts, "
            "draft_first_then_answer, ask_before_persist, clarify_first, compact_then_answer. "
            "detected_scope_ids must only include scopes visible in supplied context; use [] if uncertain. "
            "profile_layers_used must name layers that influenced the decision, for example global_user, "
            "scope_memory:linear-algebra, or knowledge_context; use [] if no profile or scope context was used. "
            "candidate_drafts must contain objects with title, draft_type, and reason. "
            "draft_type must be one of: missing_definition, missing_detail, missing_bridge, "
            "definition, theorem, proof_skeleton, example, counterexample, notation, bridge, summary. "
            "Use draft_first_then_answer only when durable knowledge should be created before answering. "
            "Use answer_then_suggest_drafts for broad exploratory questions that should not be persisted immediately. "
            "Treat the supplied knowledge node index as a semantic search space: match by meaning, not only shared words. "
            "Select at most 6 node ids and only when their title and summary materially support the answer. "
            "The full node bodies are intentionally unavailable; never imply that you inspected details not supplied here. "
            "When nodes are selected, use profile_context_summary to briefly explain what context they contribute. "
            "user_visible_summary and candidate draft reasons must use the same language as the user's question. "
            "For backward compatibility, action_type and draft_requests are also accepted.",
        ]
        if profile_block:
            parts.append(profile_block)
        return "\n\n".join(parts)

    @staticmethod
    def _user_profile_block(user_profile_summary: str) -> str:
        summary = user_profile_summary.strip()
        if not summary:
            return ""
        return "\n".join(["## User Profile", summary])

    @staticmethod
    def _strip_markdown_json_fence(value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            if lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
        return stripped
