from __future__ import annotations

from typing import Annotated
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ProviderProfileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_type: Literal["gemini", "openai_compatible"]
    model: str
    credential_id: str
    base_url: str | None = None
    options: dict[str, str] = Field(default_factory=dict)


class ProviderOptionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_type: Literal["gemini", "openai_compatible"]
    label: str
    default_model: str
    models: list[str] = Field(default_factory=list)
    allow_custom_model: bool = False
    requires_base_url: bool = False
    default_base_url: str | None = None


class ProviderCatalogItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    provider_type: Literal["gemini", "openai_compatible"]
    label: str
    default_model: str
    models: list[str] = Field(default_factory=list)
    allow_custom_model: bool = False
    requires_base_url: bool = False
    default_base_url: str = ""
    logo_url: str | None = None


class DefaultModelSelectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str | None = None
    provider_type: Literal["gemini", "openai_compatible"] = "gemini"
    credential_id: str | None = None
    model: str = "gemini-2.5-flash"


class DefaultOptionsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_model: DefaultModelSelectionSchema = Field(
        default_factory=DefaultModelSelectionSchema
    )
    utility_model: DefaultModelSelectionSchema = Field(
        default_factory=DefaultModelSelectionSchema
    )
    markdown_theme: Literal["academic", "reading", "geek"] = "academic"


class ProviderOptionsResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: list[ProviderOptionSchema] = Field(default_factory=list)
    provider_catalog: list[ProviderCatalogItemSchema] = Field(default_factory=list)
    default_options: "DefaultOptionsSchema" = Field(
        default_factory=DefaultOptionsSchema
    )


class AnswerStyleSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_style_id: str
    label: str
    description: str | None = None
    instructions: str
    is_default: bool = False


class AnswerStylesResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_style_id: Literal["default"] = "default"
    styles: list[AnswerStyleSchema] = Field(default_factory=list)


class StrategyAgentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_agent_id: str
    label: str
    description: str | None = None
    instructions: str
    is_default: bool = False


class StrategyAgentsResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_strategy_agent_id: str = "top-down"
    agents: list[StrategyAgentSchema] = Field(default_factory=list)


class PendingDraftRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    draft_type: str
    reason: str


class SelectionKnowledgeSourceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str | None = None
    session_id: str | None = None
    message_id: str | None = None
    node_id: str | None = None


class SelectionKnowledgeDraftRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_text: str | None = None
    prompt_kind: str | None = None
    source: SelectionKnowledgeSourceSchema
    conversation_model: DefaultModelSelectionSchema | None = None


class KnowledgeDraftCandidateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    draft_type: str
    reason: str


class OrchestrationPlanSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: str
    intent: str
    persistence_decision: str
    confidence: float
    user_visible_summary: str
    detected_scope_ids: list[str] = Field(default_factory=list)
    profile_layers_used: list[str] = Field(default_factory=list)
    profile_context_summary: str | None = None
    candidate_drafts: list[KnowledgeDraftCandidateSchema] = Field(default_factory=list)


class AgentStateItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    kind: str
    state: str
    title: str
    reason: str
    source_message_id: str | None = None
    node_id: str | None = None
    error_message: str | None = None


class AgentActionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    selected_node_ids: list[str] = Field(default_factory=list)
    draft_requests: list[PendingDraftRequestSchema] = Field(default_factory=list)
    user_visible_reason: str = ""


class AnswerAnchorSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    label: str
    status: str
    node_id: str | None = None


class AnswerSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    detail: str
    references: list[str] = Field(default_factory=list)
    anchors: list[AnswerAnchorSchema] = Field(default_factory=list)
    knowledge_job_id: str | None = None
    symbols: dict[str, str] = Field(default_factory=dict)
    symbol_conflicts: list[str] = Field(default_factory=list)
    assistant_text: str = ""


class AskRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    session_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None
    provider_profile: ProviderProfileSchema | None = None
    conversation_model: DefaultModelSelectionSchema | None = None
    answer_style_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None
    strategy_agent_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None


class RegenerateRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_profile: ProviderProfileSchema | None = None
    answer_style_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None


class SessionForkRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fork_anchor: "SessionForkAnchorSchema"
    focus_question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CompactRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None


class SessionForkAnchorSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["message", "node"]
    message_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None
    node_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None
    source_message_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None


class SessionBranchSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: str | None = None
    parent_session_id: str | None = None
    root_session_id: str | None = None
    focus_question: str | None = None
    fork_anchor: SessionForkAnchorSchema | None = None
    active_node_ids: list[str] = Field(default_factory=list)
    summary_node_ids: list[str] = Field(default_factory=list)
    active_symbols: dict[str, str] = Field(default_factory=dict)


class SessionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None
    title: str | None = None
    icon: str | None = None
    conversation_model: DefaultModelSelectionSchema | None = None
    provider_profile: ProviderProfileSchema | None = None
    default_answer_style_id: str | None = None
    strategy_agent_id: str = "top-down"
    branch: SessionBranchSchema = Field(default_factory=SessionBranchSchema)
    messages: list["SessionMessageSchema"] = Field(default_factory=list)


class SessionListItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    title: str | None = None
    icon: str | None = None
    conversation_model: DefaultModelSelectionSchema | None = None
    provider_profile: ProviderProfileSchema | None = None
    default_answer_style_id: str | None = None
    strategy_agent_id: str = "top-down"
    branch: SessionBranchSchema = Field(default_factory=SessionBranchSchema)
    message_count: int
    last_message: SessionMessageSchema | None = None
    branch_depth: int = 0
    child_session_ids: list[str] = Field(default_factory=list)


class SessionsListResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[SessionListItemSchema] = Field(default_factory=list)


class AskResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: AgentActionSchema
    answer: AnswerSchema
    drafts: list[PendingDraftRequestSchema] = Field(default_factory=list)
    created_node_ids: list[str] = Field(default_factory=list)
    session: SessionSchema


class KnowledgeJobSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    anchors: list[AnswerAnchorSchema] = Field(default_factory=list)
    error_message: str | None = None


class NodeReferenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    reason: str


class DisplayNodeReferenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    title: str | None = None
    summary: str | None = None
    reason: str | None = None
    type: str | None = None
    status: str | None = None


class RelatedDiscussionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    title: str | None = None
    preview: str | None = None
    message_count: int | None = None
    focus_question: str | None = None


class KnowledgeNodeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    type: str
    summary: str
    detail: str
    parent_id: str | None = None
    source: str
    references: list[NodeReferenceSchema] = Field(default_factory=list)
    incoming_references: list[NodeReferenceSchema] = Field(default_factory=list)
    related_session_ids: list[str] = Field(default_factory=list)
    references_display: list[DisplayNodeReferenceSchema] = Field(default_factory=list)
    incoming_references_display: list[DisplayNodeReferenceSchema] = Field(default_factory=list)
    related_discussions: list[RelatedDiscussionSchema] = Field(default_factory=list)
    status: str
    symbols: dict[str, str] = Field(default_factory=dict)
    symbol_scopes: dict[str, dict[str, str]] = Field(default_factory=dict)


class NodeResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: KnowledgeNodeSchema


class KnowledgeNodeUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OutlineNodeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    type: str
    summary: str
    parent_id: str | None = None
    status: str


class OutlineResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[OutlineNodeSchema] = Field(default_factory=list)


class ExplorerFolderSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: str
    scope: Literal["sessions", "knowledge"]
    name: str
    parent_folder_id: str | None = None
    created_at: str
    updated_at: str
    sort_order: int = 1000
    path_cached: str | None = None


class ExplorerItemLocationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: Literal["session", "knowledge_node"]
    item_id: str
    folder_id: str | None = None
    sort_order: int = 1000
    path_cached: str
    location_source: Literal["user", "agent", "system"]
    user_locked: bool = False
    updated_at: str


class ExplorerTreeNodeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["folder", "item"]
    folder: ExplorerFolderSchema | None = None
    location: ExplorerItemLocationSchema | None = None
    item: dict[str, object] | None = None
    children: list["ExplorerTreeNodeSchema"] = Field(default_factory=list)


class ExplorerTreeResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["sessions", "knowledge"]
    tree: list[ExplorerTreeNodeSchema] = Field(default_factory=list)


class ExplorerFolderCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["sessions", "knowledge"]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    parent_folder_id: str | None = None


class ExplorerFolderUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExplorerFolderResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: ExplorerFolderSchema


class ExplorerItemLocationUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: str | None = None
    sort_order: int = 1000


class ExplorerItemLocationResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: ExplorerItemLocationSchema


class ExplorerItemIconUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icon: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExplorerItemIconResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icon: dict[str, object]


class ExplorerOrganizeResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["knowledge"]
    organized_count: int = 0
    folders_created: int = 0


class SessionMessageSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: str
    content: str
    created_at: str
    provider_name: str | None = None
    raw_response_meta: dict[str, str] = Field(default_factory=dict)
    assistant_context: "SessionAssistantContextSchema" = Field(
        default_factory=lambda: SessionAssistantContextSchema()
    )


class SessionAssistantContextSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str | None = None
    referenced_node_ids: list[str] = Field(default_factory=list)
    anchors: list[AnswerAnchorSchema] = Field(default_factory=list)
    symbol_conflicts: list[str] = Field(default_factory=list)
    alignment_notes: list[str] = Field(default_factory=list)
    compact_summary: dict[str, object] | None = None
    orchestration_plan: OrchestrationPlanSchema | None = None
    state_items: list[AgentStateItemSchema] = Field(default_factory=list)


class AgentTurnStateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message_id: str | None = None
    route: str
    intent: str
    confidence: float
    persistence_decision: str
    user_visible_summary: str
    detected_scope_ids: list[str] = Field(default_factory=list)
    profile_layers_used: list[str] = Field(default_factory=list)
    profile_context_summary: str | None = None
    active_node_ids: list[str] = Field(default_factory=list)
    candidate_drafts: list[KnowledgeDraftCandidateSchema] = Field(default_factory=list)


class KnowledgeQueueItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    title: str
    draft_type: str = ""
    state: str
    reason: str = ""
    source_session_id: str | None = None
    source_message_id: str | None = None
    target_parent_id: str | None = None
    node_id: str | None = None
    error_message: str | None = None


class ContextHealthSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_node_count: int = 0
    summary_node_count: int = 0
    pending_draft_count: int = 0
    failed_item_count: int = 0
    symbol_conflict_count: int = 0


class MemoryScopeStateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_scope_ids: list[str] = Field(default_factory=list)
    profile_layers_used: list[str] = Field(default_factory=list)
    profile_context_summary: str | None = None
    has_global_user_profile: bool = False
    has_scope_memory: bool = False


class AgentDecisionSummarySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message_id: str
    route: str
    intent: str
    persistence_decision: str
    result: str


class AgentStateResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_turn: AgentTurnStateSchema | None = None
    knowledge_queue: list[KnowledgeQueueItemSchema] = Field(default_factory=list)
    profile_observations: list[dict[str, object]] = Field(default_factory=list)
    profile_patches: list[dict[str, object]] = Field(default_factory=list)
    memory_scope: MemoryScopeStateSchema = Field(default_factory=MemoryScopeStateSchema)
    context_health: ContextHealthSchema = Field(default_factory=ContextHealthSchema)
    recent_decisions: list[AgentDecisionSummarySchema] = Field(default_factory=list)
