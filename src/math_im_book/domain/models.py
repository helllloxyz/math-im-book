from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NodeReference:
    node_id: str
    reason: str


@dataclass(slots=True)
class KnowledgeNode:
    id: str
    title: str
    type: str
    summary: str
    detail: str
    parent_id: str | None
    source: str
    references: list[NodeReference] = field(default_factory=list)
    status: str = "ready"
    symbols: dict[str, str] = field(default_factory=dict)
    symbol_scopes: dict[str, dict[str, str]] = field(default_factory=dict)
    revision: int = 1
    updated_at: str | None = None


@dataclass(slots=True)
class PendingDraftRequest:
    title: str
    draft_type: str
    reason: str


@dataclass(slots=True)
class KnowledgeDraftCandidate:
    title: str
    draft_type: str
    reason: str


@dataclass(slots=True)
class OrchestrationPlan:
    route: str
    intent: str
    persistence_decision: str
    confidence: float
    user_visible_summary: str
    detected_scope_ids: list[str] = field(default_factory=list)
    profile_layers_used: list[str] = field(default_factory=list)
    profile_context_summary: str | None = None
    candidate_drafts: list[KnowledgeDraftCandidate] = field(default_factory=list)
    strategy_mode: str = "raw"
    strategy_reason: str = ""
    knowledge_scope_id: str | None = None
    knowledge_scope_label: str = "全部知识"


@dataclass(slots=True)
class AgentStateItem:
    item_id: str
    kind: str
    state: str
    title: str
    reason: str
    source_message_id: str | None = None
    node_id: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class AgentAction:
    action_type: str
    selected_node_ids: list[str] = field(default_factory=list)
    draft_requests: list[PendingDraftRequest] = field(default_factory=list)
    user_visible_reason: str = ""
    orchestration_plan: OrchestrationPlan | None = None


@dataclass(slots=True)
class AnswerAnchor:
    anchor_id: str
    label: str
    status: str
    node_id: str | None = None


@dataclass(slots=True)
class AnswerPayload:
    summary: str
    detail: str
    references: list[str] = field(default_factory=list)
    anchors: list[AnswerAnchor] = field(default_factory=list)
    knowledge_job_id: str | None = None
    symbols: dict[str, str] = field(default_factory=dict)
    symbol_conflicts: list[str] = field(default_factory=list)
    assistant_text: str = ""


@dataclass(slots=True)
class SessionForkAnchor:
    type: str
    message_id: str | None = None
    node_id: str | None = None
    source_message_id: str | None = None


@dataclass(slots=True)
class SessionBranch:
    branch_id: str | None = None
    parent_session_id: str | None = None
    root_session_id: str | None = None
    focus_question: str | None = None
    fork_anchor: SessionForkAnchor | None = None
    active_node_ids: list[str] = field(default_factory=list)
    summary_node_ids: list[str] = field(default_factory=list)
    active_symbols: dict[str, str] = field(default_factory=dict)
    knowledge_scope_id: str | None = None


@dataclass(slots=True)
class AskResult:
    action: AgentAction
    answer: AnswerPayload
    drafts: list[PendingDraftRequest] = field(default_factory=list)
    created_node_ids: list[str] = field(default_factory=list)
    branch_context: "SessionBranch | None" = None
    orchestration_plan: OrchestrationPlan | None = None
    state_items: list[AgentStateItem] = field(default_factory=list)


@dataclass(slots=True)
class SymbolContext:
    symbols: dict[str, str] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProviderProfile:
    provider_type: str
    model: str
    credential_id: str
    base_url: str | None = None
    options: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ModelSelection:
    provider_id: str | None
    provider_type: str
    model: str
    credential_id: str | None = None


@dataclass(slots=True)
class ProviderResult:
    output_text: str
    provider_name: str
    raw_response_meta: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AnswerStyle:
    style_id: str
    label: str
    instructions: str
    description: str | None = None
    is_default: bool = False


@dataclass(slots=True)
class AnswerStyleCatalog:
    default_style_id: str = "default"
    styles: list[AnswerStyle] = field(default_factory=list)

    def get(self, style_id: str) -> AnswerStyle:
        for style in self.styles:
            if style.style_id == style_id:
                return style
        raise KeyError(style_id)


@dataclass(slots=True)
class StrategyAgent:
    strategy_agent_id: str
    label: str
    instructions: str
    description: str | None = None
    is_default: bool = False


@dataclass(slots=True)
class StrategyAgentCatalog:
    default_strategy_agent_id: str = "top-down"
    agents: list[StrategyAgent] = field(default_factory=list)

    def get(self, strategy_agent_id: str) -> StrategyAgent:
        for agent in self.agents:
            if agent.strategy_agent_id == strategy_agent_id:
                return agent
        raise KeyError(strategy_agent_id)


@dataclass(slots=True)
class ChatSession:
    session_id: str
    title: str | None = None
    icon: str | None = None
    conversation_model: ModelSelection | None = None
    provider_profile: ProviderProfile | None = None
    default_answer_style_id: str | None = None
    strategy_agent_id: str = "top-down"
    branch_context: "SessionBranch" = field(
        default_factory=lambda: SessionBranch()
    )


@dataclass(slots=True)
class SessionAssistantContext:
    action_type: str | None = None
    referenced_node_ids: list[str] = field(default_factory=list)
    anchors: list[AnswerAnchor] = field(default_factory=list)
    symbol_conflicts: list[str] = field(default_factory=list)
    alignment_notes: list[str] = field(default_factory=list)
    compact_summary: dict[str, object] | None = None
    orchestration_plan: OrchestrationPlan | None = None
    state_items: list[AgentStateItem] = field(default_factory=list)


@dataclass(slots=True)
class SessionMessage:
    message_id: str
    role: str
    content: str
    created_at: str
    provider_name: str | None = None
    raw_response_meta: dict[str, str] = field(default_factory=dict)
    assistant_context: SessionAssistantContext = field(
        default_factory=SessionAssistantContext
    )


SessionBranchContext = SessionBranch
