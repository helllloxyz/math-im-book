import axios from 'axios';

// Interfaces for API Schemas

export type ProviderType = 'gemini' | 'openai_compatible';
export type ProviderId = 'gemini' | 'deepseek' | 'openrouter' | 'glm';
export type SelectionSourceType = 'chat-message' | 'knowledge-node';
export type SelectionKnowledgePromptKind = 'definition' | 'intuition_node' | 'example' | 'proof';
export type KnowledgeApprovalPolicy = 'agent_decides' | 'always_ask' | 'full_auto';

export interface ProviderProfile {
  provider_id?: ProviderId;
  provider_type: ProviderType;
  model: string;
  credential_id: string;
  base_url?: string;
  options?: Record<string, string>;
}

export interface ProviderOption {
  provider_id?: ProviderId;
  provider_type: ProviderType;
  label: string;
  default_model: string;
  models: string[];
  allow_custom_model: boolean;
  requires_base_url: boolean;
  default_base_url?: string | null;
}

export interface ProviderCatalogItem {
  provider_id: ProviderId;
  provider_type: ProviderType;
  label: string;
  default_model: string;
  models: string[];
  allow_custom_model: boolean;
  requires_base_url: boolean;
  default_base_url: string;
  logo_url?: string | null;
}

export interface DefaultModelSelection {
  provider_id?: ProviderId | null;
  provider_type: ProviderType;
  credential_id?: string | null;
  model: string;
}

export interface DefaultOptions {
  conversation_model: DefaultModelSelection;
  utility_model: DefaultModelSelection;
  markdown_theme: 'academic' | 'reading' | 'geek';
  knowledge_approval_policy: KnowledgeApprovalPolicy;
}

export interface ProviderOptionsPayload {
  providers: ProviderOption[];
  provider_catalog: ProviderCatalogItem[];
  default_options: DefaultOptions;
}

export interface AnswerStyleSummary {
  answer_style_id: string;
  label: string;
  description?: string;
}

export interface StrategyAgentSummary {
  strategy_agent_id: string;
  label: string;
  description?: string;
  instructions?: string;
  is_default?: boolean;
}

export interface StrategyAgentsResponse {
  default_strategy_agent_id: string;
  agents: StrategyAgentSummary[];
}

export interface SessionForkAnchor {
  type: 'message' | 'node';
  message_id?: string | null;
  node_id?: string | null;
  source_message_id?: string | null;
}

export interface SessionBranch {
  branch_id?: string;
  parent_session_id?: string;
  root_session_id?: string;
  fork_anchor?: SessionForkAnchor | null;
  focus_question?: string;
  active_node_ids: string[];
  summary_node_ids: string[];
  active_symbols: Record<string, string>;
}

export type SessionBranchContext = SessionBranch;

export interface KnowledgeAnchor {
  anchor_id: string;
  label: string;
  status: 'pending' | 'ready' | 'failed';
  node_id?: string | null;
  kind?: string | null;
  state?: string | null;
}

export interface KnowledgeDraftCandidate {
  title: string;
  draft_type: string;
  reason: string;
}

export interface KnowledgeAuthorizationDecision {
  policy?: KnowledgeApprovalPolicy;
  mode: 'not_required' | 'auto_execute' | 'require_approval';
  status: 'not_required' | 'auto_approved' | 'pending' | 'approved' | 'denied';
  risk_level: 'low' | 'medium' | 'high';
  operation: string;
  reason: string;
}

export interface OrchestrationPlan {
  route: string;
  intent: string;
  persistence_decision: string;
  confidence: number;
  user_visible_summary: string;
  detected_scope_ids: string[];
  profile_layers_used: string[];
  profile_context_summary?: string | null;
  candidate_drafts: KnowledgeDraftCandidate[];
  strategy_mode: 'top-down' | 'raw';
  strategy_reason: string;
  knowledge_scope_id?: string | null;
  knowledge_scope_label: string;
  authorization?: KnowledgeAuthorizationDecision;
}

export interface AgentStateItem {
  item_id: string;
  kind: string;
  state: string;
  title: string;
  reason: string;
  source_message_id?: string | null;
  node_id?: string | null;
  error_message?: string | null;
}

export interface AgentTurnState {
  session_id: string;
  message_id?: string | null;
  route: string;
  intent: string;
  confidence: number;
  persistence_decision: string;
  user_visible_summary: string;
  detected_scope_ids: string[];
  profile_layers_used: string[];
  profile_context_summary?: string | null;
  active_node_ids: string[];
  candidate_drafts: KnowledgeDraftCandidate[];
}

export interface KnowledgeQueueItem {
  item_id: string;
  title: string;
  draft_type: string;
  state: string;
  reason: string;
  source_session_id?: string | null;
  source_message_id?: string | null;
  target_parent_id?: string | null;
  node_id?: string | null;
  error_message?: string | null;
}

export interface ContextHealth {
  active_node_count: number;
  summary_node_count: number;
  pending_draft_count: number;
  failed_item_count: number;
  symbol_conflict_count: number;
}

export interface MemoryScopeState {
  detected_scope_ids: string[];
  profile_layers_used: string[];
  profile_context_summary?: string | null;
  has_global_user_profile: boolean;
  has_scope_memory: boolean;
}

export interface AgentDecisionSummary {
  session_id: string;
  message_id: string;
  route: string;
  intent: string;
  persistence_decision: string;
  result: string;
}

export interface AgentState {
  current_turn?: AgentTurnState | null;
  knowledge_queue: KnowledgeQueueItem[];
  profile_observations: Array<Record<string, any>>;
  profile_patches: Array<Record<string, any>>;
  memory_scope: MemoryScopeState;
  context_health: ContextHealth;
  recent_decisions: AgentDecisionSummary[];
}

export interface SessionAssistantContext {
  action_type?: string | null;
  referenced_node_ids: string[];
  symbol_conflicts: string[];
  alignment_notes: string[];
  compact_summary?: Record<string, any> | null;
  anchors?: KnowledgeAnchor[];
  orchestration_plan?: OrchestrationPlan | null;
  state_items?: AgentStateItem[];
}

export interface SessionMessage {
  message_id: string;
  role: string;
  content: string;
  provider_name?: string;
  raw_response_meta?: Record<string, string>;
  assistant_context: SessionAssistantContext;
  created_at: string;
}

export interface Session {
  session_id?: string;
  title?: string;
  icon?: string;
  conversation_model?: DefaultModelSelection;
  provider_profile?: ProviderProfile;
  default_answer_style_id?: string | null;
  strategy_agent_id?: string;
  knowledge_approval_policy?: KnowledgeApprovalPolicy;
  knowledge_scope_id?: string | null;
  branch: SessionBranch;
  messages: SessionMessage[];
}

export interface SessionListItem {
  session_id: string;
  title?: string;
  icon?: string;
  conversation_model?: DefaultModelSelection;
  provider_profile?: ProviderProfile;
  default_answer_style_id?: string | null;
  strategy_agent_id?: string;
  knowledge_approval_policy?: KnowledgeApprovalPolicy;
  knowledge_scope_id?: string | null;
  branch: SessionBranch;
  message_count: number;
  last_message?: SessionMessage;
  branch_depth: number;
  child_session_ids: string[];
}

export interface AgentAction {
  action_type: string;
  selected_node_ids: string[];
  draft_requests: Array<{ title: string; draft_type: string; reason: string }>;
  user_visible_reason: string;
}

export interface Answer {
  summary: string;
  detail: string;
  references: string[];
  symbols: Record<string, string>;
  symbol_conflicts: string[];
  assistant_text: string;
  anchors?: KnowledgeAnchor[];
  knowledge_job_id?: string;
}

export interface AskResponse {
  action: AgentAction;
  answer: Answer;
  drafts: Array<{ title: string; draft_type: string; reason: string }>;
  created_node_ids: string[];
  session: Session;
}

export interface AskStreamCallbacks {
  onChunk?: (delta: string) => void;
  onProgress?: (event: AgentProgressEvent) => void;
  requestId?: string;
  signal?: AbortSignal;
}

export interface AgentProgressEvent {
  stage: string;
  label: string;
  detail?: string;
  state: 'running' | 'completed' | 'failed';
}

export interface KnowledgeJob {
  job_id: string;
  status: string;
  anchors: KnowledgeAnchor[];
  error_message?: string | null;
}

export interface SelectionKnowledgeSource {
  type: SelectionSourceType;
  session_id?: string | null;
  message_id?: string | null;
  node_id?: string | null;
}

export interface SelectionKnowledgeRequest {
  selected_text: string;
  prompt_kind: SelectionKnowledgePromptKind;
  source: SelectionKnowledgeSource;
  conversation_model?: DefaultModelSelection;
}

export interface SessionUpdatePayload {
  title?: string;
  icon?: string;
  conversation_model?: DefaultModelSelection;
  knowledge_approval_policy?: KnowledgeApprovalPolicy;
}

export interface RegenerateRequestPayload {
  answer_style_id?: string;
}

export interface OutlineNode {
  id: string;
  title: string;
  type: string;
  summary: string;
  parent_id?: string;
  status: string;
}

export type ExplorerScope = 'sessions' | 'knowledge';
export type ExplorerItemType = 'session' | 'knowledge_node';

export interface ExplorerFolder {
  folder_id: string;
  scope: ExplorerScope;
  name: string;
  parent_folder_id?: string | null;
  created_at: string;
  updated_at: string;
  sort_order: number;
  path_cached?: string | null;
  scope_id?: string | null;
}

export interface ExplorerItemLocation {
  item_type: ExplorerItemType;
  item_id: string;
  folder_id?: string | null;
  sort_order: number;
  path_cached: string;
  location_source: 'user' | 'agent' | 'system';
  user_locked: boolean;
  updated_at: string;
}

export interface ExplorerTreeNode {
  kind: 'folder' | 'item';
  folder?: ExplorerFolder | null;
  location?: ExplorerItemLocation | null;
  item?: Record<string, any> | null;
  children: ExplorerTreeNode[];
}

export interface ExplorerTreeResponse {
  scope: ExplorerScope;
  tree: ExplorerTreeNode[];
}

export interface ExplorerItemIcon {
  item_type: ExplorerItemType;
  item_id: string;
  icon: string;
  updated_at: string;
}

export interface ExplorerOrganizeResult {
  scope: 'knowledge';
  organized_count: number;
  folders_created: number;
}

export interface NodeReference {
  node_id: string;
  reason: string;
}

export interface DisplayNodeReference {
  node_id: string;
  title: string | null;
  summary: string | null;
  reason: string | null;
  type: string | null;
  status: string | null;
}

export interface RelatedDiscussion {
  session_id: string;
  title: string | null;
  preview: string | null;
  message_count: number | null;
  focus_question: string | null;
}

export interface KnowledgeNode {
  id: string;
  title: string;
  type: string;
  summary: string;
  detail: string;
  parent_id?: string;
  source: string;
  references: NodeReference[];
  incoming_references: NodeReference[];
  related_session_ids: string[];
  references_display: DisplayNodeReference[];
  incoming_references_display: DisplayNodeReference[];
  related_discussions: RelatedDiscussion[];
  status: string;
  symbols: Record<string, string>;
  symbol_scopes?: Record<string, Record<string, string>>;
  revision: number;
  updated_at?: string | null;
}

export type KnowledgeNodeUpdate = Partial<Pick<KnowledgeNode, 'title' | 'summary' | 'detail' | 'type'>>;

export interface CredentialSummary {
  credential_id: string;
  provider_type?: ProviderType;
  provider_id?: ProviderId;
  default_model?: string;
  models?: string[];
  base_url?: string | null;
  has_headers: boolean;
}

// API client

const client = axios.create({
  baseURL: '/api',
});

export interface CredentialPayload {
  credential_id: string;
  provider_type: ProviderType;
  provider_id?: ProviderId;
  api_key?: string;
  headers?: Record<string, string>;
  base_url?: string;
  default_model?: string;
  models?: string[];
}

export const api = {
  async getAgentState(sessionId?: string): Promise<AgentState> {
    const response = await client.get('/agent-state', {
      params: sessionId ? { session_id: sessionId } : {},
    });
    return response.data;
  },

  async getSessions(): Promise<SessionListItem[]> {
    const response = await client.get<{ sessions: SessionListItem[] }>('/sessions');
    return response.data.sessions;
  },

  async getSession(sessionId: string): Promise<Session> {
    const response = await client.get<Session>(`/sessions/${sessionId}`);
    return response.data;
  },

  async getOutline(): Promise<OutlineNode[]> {
    const response = await client.get<{ nodes: OutlineNode[] }>('/outline');
    return response.data.nodes;
  },

  async getSessionExplorer(): Promise<ExplorerTreeResponse> {
    const response = await client.get<ExplorerTreeResponse>('/explorer/sessions');
    return response.data;
  },

  async getKnowledgeExplorer(): Promise<ExplorerTreeResponse> {
    const response = await client.get<ExplorerTreeResponse>('/explorer/knowledge');
    return response.data;
  },

  async organizeKnowledgeExplorer(): Promise<ExplorerOrganizeResult> {
    const response = await client.post<ExplorerOrganizeResult>('/explorer/knowledge/organize');
    return response.data;
  },

  async createExplorerFolder(payload: {
    scope: ExplorerScope;
    name: string;
    parent_folder_id?: string | null;
  }): Promise<ExplorerFolder> {
    const response = await client.post<{ folder: ExplorerFolder }>('/explorer/folders', payload);
    return response.data.folder;
  },

  async renameExplorerFolder(folderId: string, name: string): Promise<ExplorerFolder> {
    const response = await client.patch<{ folder: ExplorerFolder }>(
      `/explorer/folders/${folderId}`,
      { name }
    );
    return response.data.folder;
  },

  async deleteExplorerFolder(folderId: string): Promise<void> {
    await client.delete(`/explorer/folders/${folderId}`);
  },

  async moveExplorerItem(
    itemType: ExplorerItemType,
    itemId: string,
    payload: { folder_id?: string | null; sort_order?: number }
  ): Promise<ExplorerItemLocation> {
    const response = await client.patch<{ location: ExplorerItemLocation }>(
      `/explorer/items/${itemType}/${itemId}/location`,
      payload
    );
    return response.data.location;
  },

  async updateExplorerItemIcon(
    itemType: ExplorerItemType,
    itemId: string,
    icon: string
  ): Promise<ExplorerItemIcon> {
    const response = await client.patch<{ icon: ExplorerItemIcon }>(
      `/explorer/items/${itemType}/${itemId}/icon`,
      { icon }
    );
    return response.data.icon;
  },

  async getNode(nodeId: string): Promise<KnowledgeNode> {
    const response = await client.get<{ node: KnowledgeNode }>(`/nodes/${nodeId}`);
    return response.data.node;
  },

  async updateKnowledgeNode(nodeId: string, payload: KnowledgeNodeUpdate): Promise<KnowledgeNode> {
    const response = await client.patch<{ node: KnowledgeNode }>(`/nodes/${nodeId}`, payload);
    return response.data.node;
  },

  async getKnowledgeJob(jobId: string): Promise<KnowledgeJob> {
    const response = await client.get<KnowledgeJob>(`/knowledge-jobs/${jobId}`);
    return response.data;
  },

  async compileSuggestedDrafts(
    sessionId: string,
    messageId: string,
    draftIndexes: number[]
  ): Promise<KnowledgeJob> {
    const response = await client.post<KnowledgeJob>(
      `/sessions/${sessionId}/messages/${messageId}/suggested-drafts/compile`,
      { draft_indexes: draftIndexes }
    );
    return response.data;
  },

  async rejectSuggestedDrafts(
    sessionId: string,
    messageId: string
  ): Promise<Session> {
    const response = await client.post<Session>(
      `/sessions/${sessionId}/messages/${messageId}/suggested-drafts/reject`
    );
    return response.data;
  },

  async compileSelectionKnowledge(payload: SelectionKnowledgeRequest): Promise<KnowledgeJob> {
    const response = await client.post<KnowledgeJob>('/selection/knowledge-drafts', payload);
    return response.data;
  },

  async getCredentials(): Promise<CredentialSummary[]> {
    const response = await client.get<{ credentials: CredentialSummary[] }>('/credentials');
    return response.data.credentials;
  },

  async getProviderOptions(): Promise<ProviderOptionsPayload> {
    const response = await client.get<ProviderOptionsPayload>('/provider-options');
    return response.data;
  },

  async updateDefaultOptions(
    payload: DefaultOptions
  ): Promise<DefaultOptions> {
    const response = await client.put<DefaultOptions>(
      '/provider-options/default-options',
      payload
    );
    return response.data;
  },

  async getAnswerStyles(): Promise<AnswerStyleSummary[]> {
    const response = await client.get<{
      answer_styles?: AnswerStyleSummary[];
      styles?: Array<AnswerStyleSummary | { style_id: string; label: string; description?: string }>;
    } | AnswerStyleSummary[]>('/answer-styles');
    if (Array.isArray(response.data)) {
      return response.data.map((style: any) => ({
        answer_style_id: style.answer_style_id || style.style_id,
        label: style.label,
        description: style.description,
      }));
    }
    const styles = response.data.answer_styles || response.data.styles || [];
    return styles.map((style: any) => ({
      answer_style_id: style.answer_style_id || style.style_id,
      label: style.label,
      description: style.description,
    }));
  },

  async getStrategyAgents(): Promise<StrategyAgentsResponse> {
    const response = await client.get<StrategyAgentsResponse>('/strategy-agents');
    return response.data;
  },

  async createCredential(payload: CredentialPayload): Promise<CredentialSummary> {
    const response = await client.post<{ credential: CredentialSummary }>('/credentials', payload);
    return response.data.credential;
  },

  async updateCredential(credentialId: string, payload: Partial<CredentialPayload>): Promise<CredentialSummary> {
    const response = await client.put<{ credential: CredentialSummary }>(`/credentials/${credentialId}`, payload);
    return response.data.credential;
  },

  async ask(
    question: string,
    sessionId?: string,
    conversationModel?: DefaultModelSelection,
    answerStyleId?: string,
    strategyAgentId?: string,
    knowledgeScopeId?: string | null,
    knowledgeApprovalPolicy?: KnowledgeApprovalPolicy,
    conversationFolderId?: string | null
  ): Promise<AskResponse> {
    const response = await client.post<AskResponse>('/ask', {
      question,
      session_id: sessionId,
      conversation_model: conversationModel,
      answer_style_id: answerStyleId,
      strategy_agent_id: strategyAgentId,
      knowledge_scope_id: knowledgeScopeId,
      knowledge_approval_policy: knowledgeApprovalPolicy,
      conversation_folder_id: conversationFolderId,
    });
    return response.data;
  },

  async askStream(
    question: string,
    sessionId?: string,
    conversationModel?: DefaultModelSelection,
    answerStyleId?: string,
    strategyAgentId?: string,
    callbacks: AskStreamCallbacks = {},
    knowledgeScopeId?: string | null,
    knowledgeApprovalPolicy?: KnowledgeApprovalPolicy,
    conversationFolderId?: string | null
  ): Promise<AskResponse> {
    const response = await fetch('/api/ask/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question,
        request_id: callbacks.requestId,
        session_id: sessionId,
        conversation_model: conversationModel,
        answer_style_id: answerStyleId,
        strategy_agent_id: strategyAgentId,
        knowledge_scope_id: knowledgeScopeId,
        knowledge_approval_policy: knowledgeApprovalPolicy,
        conversation_folder_id: conversationFolderId,
      }),
      signal: callbacks.signal,
    });
    if (!response.ok) {
      throw new Error(`stream request failed with status ${response.status}`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return (await response.json()) as AskResponse;
    }
    if (!response.body) {
      throw new Error('stream response body missing');
    }

    const decoder = new TextDecoder();
    const reader = response.body.getReader();
    let buffer = '';
    let finalPayload: AskResponse | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const events = splitSseEvents(buffer);
      buffer = events.pop() || '';
      for (const rawEvent of events) {
        const parsed = parseSseEvent(rawEvent);
        if (!parsed) continue;
        if (parsed.event === 'chunk') {
          callbacks.onChunk?.(String(parsed.data.delta || ''));
          continue;
        }
        if (parsed.event === 'progress') {
          callbacks.onProgress?.(parsed.data as unknown as AgentProgressEvent);
          continue;
        }
        if (parsed.event === 'final') {
          finalPayload = parsed.data as unknown as AskResponse;
          continue;
        }
        if (parsed.event === 'error') {
          throw new Error(String(parsed.data.detail || 'stream request failed'));
        }
      }
    }

    const trailingEvent = parseSseEvent(buffer);
    if (trailingEvent) {
      if (trailingEvent.event === 'chunk') {
        callbacks.onChunk?.(String(trailingEvent.data.delta || ''));
      } else if (trailingEvent.event === 'progress') {
        callbacks.onProgress?.(trailingEvent.data as unknown as AgentProgressEvent);
      } else if (trailingEvent.event === 'final') {
        finalPayload = trailingEvent.data as unknown as AskResponse;
      } else if (trailingEvent.event === 'error') {
        throw new Error(String(trailingEvent.data.detail || 'stream request failed'));
      }
    }

    if (!finalPayload) {
      throw new Error('stream ended without final payload');
    }
    return finalPayload;
  },

  async cancelAsk(requestId: string): Promise<void> {
    const response = await fetch(`/api/ask/${encodeURIComponent(requestId)}/cancel`, {
      method: 'POST',
      keepalive: true,
    });
    if (!response.ok) {
      throw new Error(`cancel request failed with status ${response.status}`);
    }
  },

  async fork(
    sessionId: string,
    payload: { fork_anchor: SessionForkAnchor; focus_question: string }
  ): Promise<Session> {
    const response = await client.post<Session>(`/sessions/${sessionId}/fork`, payload);
    return response.data;
  },

  async regenerate(
    sessionId: string,
    messageId: string,
    answerStyleId?: string
  ): Promise<Session> {
    const response = await client.post<Session>(
      `/sessions/${sessionId}/messages/${messageId}/regenerate`,
      {
        answer_style_id: answerStyleId,
      } satisfies RegenerateRequestPayload
    );
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await client.delete(`/sessions/${sessionId}`);
  },

  async updateSession(sessionId: string, payload: SessionUpdatePayload): Promise<Session> {
    const response = await client.patch<Session>(`/sessions/${sessionId}`, payload);
    return response.data;
  },
};

function splitSseEvents(buffer: string): string[] {
  return buffer.split(/\r?\n\r?\n/);
}

function parseSseEvent(rawEvent: string): { event: string; data: Record<string, unknown> } | null {
  const lines = rawEvent.split(/\r?\n/);
  let event = 'message';
  let dataRaw = '';
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
      continue;
    }
    if (line.startsWith('data:')) {
      dataRaw += line.slice(5).trim();
    }
  }
  if (!dataRaw) return null;
  return {
    event,
    data: JSON.parse(dataRaw) as Record<string, unknown>,
  };
}
