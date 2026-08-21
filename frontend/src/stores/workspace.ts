import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';
import {
  api,
  type Session,
  type SessionListItem,
  type OutlineNode,
  type KnowledgeNode,
  type KnowledgeNodeUpdate,
  type KnowledgeAnchor,
  type ProviderProfile,
  type CredentialPayload,
  type CredentialSummary,
  type ProviderOption,
  type ProviderId,
  type ProviderCatalogItem,
  type DefaultOptions,
  type AnswerStyleSummary,
  type StrategyAgentSummary,
  type AgentState,
  type AgentProgressEvent,
  type DefaultModelSelection,
  type SelectionKnowledgePromptKind,
  type SelectionKnowledgeSource,
  type ExplorerTreeNode,
  type ExplorerScope,
  type ExplorerItemType,
  type KnowledgeApprovalPolicy,
} from '../services/api';

const LAST_PROVIDER_PROFILE_STORAGE_KEY = 'math-im-book:last-provider-profile';
const KNOWLEDGE_JOB_INITIAL_POLL_DELAY_MS = 20000;
const KNOWLEDGE_JOB_POLL_INTERVAL_MS = 5000;
const KNOWLEDGE_JOB_POLL_LIMIT = 36;
const STREAMING_ASSISTANT_MESSAGE_ID = 'streaming-assistant';

export interface ConfiguredModelProfile {
  key: string;
  provider_id: ProviderId;
  provider_type: ProviderOption['provider_type'];
  provider_label: string;
  credential_id: string;
  model: string;
  base_url?: string;
  label: string;
}

export interface SelectionActionPayload {
  text: string;
  sourceType: 'chat-message' | 'knowledge-node';
  sessionId?: string;
  messageId?: string;
  nodeId?: string;
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const sessions = ref<SessionListItem[]>([]);
  const outline = ref<OutlineNode[]>([]);
  const sessionExplorerTree = ref<ExplorerTreeNode[]>([]);
  const knowledgeExplorerTree = ref<ExplorerTreeNode[]>([]);
  const currentSession = ref<Session | null>(null);
  const currentNode = ref<KnowledgeNode | null>(null);
  const loading = ref(false);
  const explorerBusy = ref(false);
  const errorMessage = ref<string | null>(null);
  const credentials = ref<CredentialSummary[]>([]);
  const providerOptions = ref<ProviderOption[]>([]);
  const providerCatalog = ref<ProviderCatalogItem[]>([]);
  const defaultOptions = ref<DefaultOptions | null>(null);
  const answerStyles = ref<AnswerStyleSummary[]>([]);
  const strategyAgents = ref<StrategyAgentSummary[]>([]);
  const selectedAnswerStyleId = ref<string | null>(null);
  const selectedStrategyAgentId = ref('');
  const selectedKnowledgeScopeId = ref<string | null>(null);
  const selectedKnowledgeApprovalPolicy = ref<KnowledgeApprovalPolicy>('agent_decides');
  const selectedProviderProfile = ref<ProviderProfile | null>(null);
  const draftQuestion = ref('');
  const newSessionFolderId = ref<string | null>(null);
  const conversationBaseFolderId = ref<string | null>(null);
  const activeTab = ref<'chat' | 'book' | 'agent' | 'knowledge'>('chat');
  const agentState = ref<AgentState | null>(null);
  const agentStateLoading = ref(false);
  const focusedAgentMessageId = ref<string | null>(null);
  const agentRunSteps = ref<AgentProgressEvent[]>([]);
  const knowledgeApprovalBusyMessageIds = ref<string[]>([]);
  let knowledgeJobPollToken = 0;
  let standaloneKnowledgeJobPollToken = 0;
  let agentStateRequestToken = 0;

  const configuredModelProfiles = computed<ConfiguredModelProfile[]>(() => {
    const profiles: ConfiguredModelProfile[] = [];
    if (!providerCatalog.value.length || !credentials.value.length) return profiles;

    for (const credential of credentials.value) {
      // Find the catalog entry for this credential
      // Prefer match by provider_id, then provider_type
      const provider = (credential.provider_id ? providerCatalog.value.find(p => p.provider_id === credential.provider_id) : null)
        || providerCatalog.value.find(p => p.provider_type === credential.provider_type);
      
      if (!provider) continue;

      const providerLabel = provider.label || provider.provider_id;
      
      // Determine models to show
      const configuredModels = Array.isArray(credential.models) && credential.models.length
        ? credential.models
        : credential.default_model
          ? [credential.default_model]
          : provider.models;
        
      if (!configuredModels.length) continue;

      // Base URL from credential OR provider default
      const baseUrl = provider.requires_base_url
        ? credential.base_url || provider.default_base_url
        : undefined;

      for (const model of configuredModels) {
        profiles.push({
          key: `${credential.credential_id}::${model}`,
          provider_id: provider.provider_id,
          provider_type: provider.provider_type,
          provider_label: providerLabel,
          credential_id: credential.credential_id,
          model,
          base_url: baseUrl,
          label: `${providerLabel} - ${model} (${credential.credential_id})`,
        });
      }
    }
    return profiles;
  });

  const knowledgeScopeOptions = computed(() => {
    const options: Array<{ id: string; label: string; nodeCount: number }> = [];
    const visit = (nodes: ExplorerTreeNode[], parents: string[]) => {
      for (const node of nodes) {
        if (node.kind !== 'folder' || !node.folder) continue;
        const path = [...parents, node.folder.name];
        const countItems = (children: ExplorerTreeNode[]): number =>
          children.reduce(
            (total, child) => total + (
              child.kind === 'item' ? 1 : countItems(child.children || [])
            ),
            0
          );
        options.push({
          id: node.folder.folder_id,
          label: path.join(' / '),
          nodeCount: countItems(node.children || []),
        });
        visit(node.children || [], path);
      }
    };
    visit(knowledgeExplorerTree.value, []);
    return options;
  });

  function cancelKnowledgeJobPolling() {
    knowledgeJobPollToken += 1;
  }

  function cancelStandaloneKnowledgeJobPolling() {
    standaloneKnowledgeJobPollToken += 1;
  }

  function latestAssistantMessage(session: Session | null): Session['messages'][number] | null {
    if (!session) return null;
    for (let index = session.messages.length - 1; index >= 0; index -= 1) {
      const message = session.messages[index];
      if (message.role === 'assistant') {
        return message;
      }
    }
    return null;
  }

  function cloneAnchors(anchors: KnowledgeAnchor[]): KnowledgeAnchor[] {
    return anchors.map((anchor) => ({ ...anchor }));
  }

  function buildConversationModel(): DefaultModelSelection | undefined {
    if (!selectedProviderProfile.value) return undefined;
    return {
      ...(selectedProviderProfile.value.provider_id
        ? { provider_id: selectedProviderProfile.value.provider_id }
        : {}),
      provider_type: selectedProviderProfile.value.provider_type,
      credential_id: selectedProviderProfile.value.credential_id,
      model: selectedProviderProfile.value.model,
    };
  }

  function applyAnchorsToSession(
    session: Session,
    messageId: string | null,
    anchors: KnowledgeAnchor[]
  ): Session {
    if (!messageId) return session;
    return {
      ...session,
      messages: session.messages.map((message) =>
        message.message_id === messageId
          ? {
              ...message,
              assistant_context: {
                ...message.assistant_context,
                anchors: cloneAnchors(anchors),
              },
            }
          : message
      ),
    };
  }

  function knowledgeJobNeedsPolling(status: string, anchors: KnowledgeAnchor[]): boolean {
    return (
      ['pending', 'queued', 'running'].includes(status) ||
      anchors.some((anchor) => anchor.status === 'pending')
    );
  }

  function knowledgeJobFailed(status: string, anchors: KnowledgeAnchor[]): boolean {
    return status === 'failed' || anchors.some((anchor) => anchor.status === 'failed');
  }

  function nowIsoString(): string {
    return new Date().toISOString();
  }

  function ensureStreamingSession(question: string): Session {
    const existing = currentSession.value;
    if (existing) {
      return {
        ...existing,
        messages: [
          ...existing.messages,
          {
            message_id: `local-user-${Date.now()}`,
            role: 'user',
            content: question,
            assistant_context: {
              referenced_node_ids: [],
              symbol_conflicts: [],
              alignment_notes: [],
            },
            created_at: nowIsoString(),
          },
          {
            message_id: STREAMING_ASSISTANT_MESSAGE_ID,
            role: 'assistant',
            content: '',
            assistant_context: {
              referenced_node_ids: [],
              symbol_conflicts: [],
              alignment_notes: [],
            },
            created_at: nowIsoString(),
          },
        ],
      };
    }
    return {
      session_id: undefined,
      title: undefined,
      icon: undefined,
      provider_profile: undefined,
      default_answer_style_id: null,
      strategy_agent_id: selectedStrategyAgentId.value,
      knowledge_scope_id: selectedKnowledgeScopeId.value,
      knowledge_approval_policy: selectedKnowledgeApprovalPolicy.value,
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: `local-user-${Date.now()}`,
          role: 'user',
          content: question,
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: nowIsoString(),
        },
        {
          message_id: STREAMING_ASSISTANT_MESSAGE_ID,
          role: 'assistant',
          content: '',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: nowIsoString(),
        },
      ],
    };
  }

  function appendStreamingChunk(chunk: string) {
    if (!currentSession.value) return;
    currentSession.value = {
      ...currentSession.value,
      messages: currentSession.value.messages.map((message) =>
        message.message_id === STREAMING_ASSISTANT_MESSAGE_ID
          ? { ...message, content: `${message.content}${chunk}` }
          : message
      ),
    };
  }

  function applyAgentProgress(event: AgentProgressEvent) {
    const existingIndex = agentRunSteps.value.findIndex(
      (step) => step.stage === event.stage
    );
    const completedPrevious = agentRunSteps.value.map((step) =>
      step.state === 'running' && step.stage !== event.stage
        ? { ...step, state: 'completed' as const }
        : step
    );
    if (existingIndex >= 0) {
      completedPrevious[existingIndex] = event;
      agentRunSteps.value = completedPrevious;
      return;
    }
    agentRunSteps.value = [...completedPrevious, event];
  }

  async function pollKnowledgeJob(
    jobId: string,
    sessionId: string,
    messageId: string,
    token: number,
    attempt: number
  ) {
    if (token !== knowledgeJobPollToken) return;
    try {
      const job = await api.getKnowledgeJob(jobId);
      if (token !== knowledgeJobPollToken) return;
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = applyAnchorsToSession(currentSession.value, messageId, job.anchors);
        void fetchAgentState(sessionId);
      }
      if (knowledgeJobFailed(job.status, job.anchors)) {
        errorMessage.value = job.error_message
          ? `Knowledge note failed to save: ${job.error_message}`
          : 'Knowledge note failed to save.';
        await fetchOutline();
        await fetchSessions();
        return;
      }
      if (attempt < KNOWLEDGE_JOB_POLL_LIMIT && knowledgeJobNeedsPolling(job.status, job.anchors)) {
        setTimeout(() => {
          void pollKnowledgeJob(jobId, sessionId, messageId, token, attempt + 1);
        }, KNOWLEDGE_JOB_POLL_INTERVAL_MS);
      } else {
        await fetchOutline();
        await fetchSessions();
      }
    } catch (error) {
      if (token !== knowledgeJobPollToken) return;
      console.error(`Failed to poll knowledge job ${jobId}:`, error);
      if (attempt < KNOWLEDGE_JOB_POLL_LIMIT) {
        setTimeout(() => {
          void pollKnowledgeJob(jobId, sessionId, messageId, token, attempt + 1);
        }, KNOWLEDGE_JOB_POLL_INTERVAL_MS);
      }
    }
  }

  async function pollStandaloneKnowledgeJob(
    jobId: string,
    token: number,
    attempt: number
  ): Promise<void> {
    if (token !== standaloneKnowledgeJobPollToken) return;
    try {
      const job = await api.getKnowledgeJob(jobId);
      if (token !== standaloneKnowledgeJobPollToken) return;
      if (knowledgeJobFailed(job.status, job.anchors)) {
        if (token !== standaloneKnowledgeJobPollToken) return;
        errorMessage.value = job.error_message
          ? `Knowledge note failed to save: ${job.error_message}`
          : 'Knowledge note failed to save.';
        return;
      }
      const readyNodeId = job.anchors.find(
        (anchor) => anchor.status === 'ready' && anchor.node_id
      )?.node_id;
      if (token !== standaloneKnowledgeJobPollToken) return;
      await fetchOutline();
      if (token !== standaloneKnowledgeJobPollToken) return;
      if (readyNodeId) {
        await selectNode(readyNodeId, token);
        return;
      }
      if (
        attempt < KNOWLEDGE_JOB_POLL_LIMIT &&
        knowledgeJobNeedsPolling(job.status, job.anchors)
      ) {
        setTimeout(() => {
          void pollStandaloneKnowledgeJob(jobId, token, attempt + 1);
        }, KNOWLEDGE_JOB_POLL_INTERVAL_MS);
      }
    } catch (error) {
      if (token !== standaloneKnowledgeJobPollToken) return;
      console.error(`Failed to poll knowledge job ${jobId}:`, error);
      if (attempt >= KNOWLEDGE_JOB_POLL_LIMIT) {
        errorMessage.value = 'Failed to start knowledge note generation.';
      }
      if (attempt < KNOWLEDGE_JOB_POLL_LIMIT) {
        setTimeout(() => {
          void pollStandaloneKnowledgeJob(jobId, token, attempt + 1);
        }, KNOWLEDGE_JOB_POLL_INTERVAL_MS);
      }
    }
  }

  function startKnowledgeJobPolling(jobId: string, sessionId: string, messageId: string) {
    knowledgeJobPollToken += 1;
    const token = knowledgeJobPollToken;
    setTimeout(() => {
      void pollKnowledgeJob(jobId, sessionId, messageId, token, 0);
    }, KNOWLEDGE_JOB_INITIAL_POLL_DELAY_MS);
  }

  function loadPersistedProviderProfile(): ProviderProfile | null {
    if (typeof window === 'undefined') return null;
    if (
      !window.localStorage ||
      typeof window.localStorage.getItem !== 'function' ||
      typeof window.localStorage.removeItem !== 'function'
    ) {
      return null;
    }
    const raw = window.localStorage.getItem(LAST_PROVIDER_PROFILE_STORAGE_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as ProviderProfile;
    } catch (error) {
      window.localStorage.removeItem(LAST_PROVIDER_PROFILE_STORAGE_KEY);
      return null;
    }
  }

  function persistProviderProfile(profile: ProviderProfile | null) {
    if (typeof window === 'undefined') return;
    if (
      !window.localStorage ||
      typeof window.localStorage.setItem !== 'function' ||
      typeof window.localStorage.removeItem !== 'function'
    ) {
      return;
    }
    if (profile === null) {
      window.localStorage.removeItem(LAST_PROVIDER_PROFILE_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(
      LAST_PROVIDER_PROFILE_STORAGE_KEY,
      JSON.stringify(profile)
    );
  }

  function providerSelectionOptions(): ProviderOption[] {
    return providerCatalog.value.length ? providerCatalog.value : providerOptions.value;
  }

  function preferredProviderOption(): ProviderOption | null {
    const options = providerSelectionOptions();
    if (!options.length) return null;
    const conversationDefault = defaultOptions.value?.conversation_model;
    const configuredDefault = conversationDefault
      ? options.find(
          (option) =>
            (conversationDefault.provider_id &&
              option.provider_id === conversationDefault.provider_id) ||
            option.provider_type === conversationDefault.provider_type
        )
      : null;
    return (
      configuredDefault ||
      options.find((option) => option.provider_id === 'gemini') ||
      options[0]
    );
  }

  function pickCredentialId(providerId: ProviderId | null | undefined, providerType: ProviderProfile['provider_type']): string {
    return (
      (providerId
        ? credentials.value.find((credential) => credential.provider_id === providerId)?.credential_id
        : null) ||
      credentials.value.find((credential) => credential.provider_type === providerType)?.credential_id ||
      credentials.value[0]?.credential_id ||
      ''
    );
  }

  function normalizeProviderProfile(profile: ProviderProfile | null): ProviderProfile | null {
    if (!profile) return null;
    const options = providerSelectionOptions();
    const option = options.find(
      (candidate) => candidate.provider_id === profile.provider_id
    ) || options.find(
      (candidate) => candidate.provider_type === profile.provider_type
    );
    if (!option) return null;

    const credential_id =
      credentials.value.some(
        (credential) =>
          credential.credential_id === profile.credential_id &&
          (credential.provider_id === undefined ||
            credential.provider_id === profile.provider_id)
      )
        ? profile.credential_id
        : pickCredentialId(option.provider_id, option.provider_type);

    return {
      ...(option.provider_id ? { provider_id: option.provider_id } : {}),
      provider_type: option.provider_type,
      model: profile.model,
      credential_id,
      ...(option.requires_base_url
        ? {
            base_url: profile.base_url || option.default_base_url || '',
          }
        : {}),
    };
  }

  function defaultProviderProfile(): ProviderProfile | null {
    const option = preferredProviderOption();
    if (!option) return null;
    const conversationDefault = defaultOptions.value?.conversation_model;
    const defaultModel =
      conversationDefault &&
      ((conversationDefault.provider_id && conversationDefault.provider_id === option.provider_id) ||
        conversationDefault.provider_type === option.provider_type)
        ? conversationDefault.model
        : option.default_model;
    const credentialId =
      conversationDefault &&
      ((conversationDefault.provider_id && conversationDefault.provider_id === option.provider_id) ||
        conversationDefault.provider_type === option.provider_type) &&
      conversationDefault.credential_id
        ? conversationDefault.credential_id
        : pickCredentialId(option.provider_id, option.provider_type);
    return {
      ...(option.provider_id ? { provider_id: option.provider_id } : {}),
      provider_type: option.provider_type,
      model: defaultModel,
      credential_id: credentialId,
      ...(option.requires_base_url && option.default_base_url
        ? { base_url: option.default_base_url }
        : {}),
    };
  }

  function defaultStrategyAgentId(): string {
    const automatic = strategyAgents.value.find(
      (agent) => agent.strategy_agent_id === 'auto'
    );
    if (automatic) return automatic.strategy_agent_id;
    const configuredDefault = strategyAgents.value.find((agent) => agent.is_default);
    if (configuredDefault) return configuredDefault.strategy_agent_id;
    return strategyAgents.value[0]?.strategy_agent_id || '';
  }

  function defaultKnowledgeApprovalPolicy(): KnowledgeApprovalPolicy {
    return defaultOptions.value?.knowledge_approval_policy || 'agent_decides';
  }

  function ensureSelectedProviderProfile() {
    const candidate =
      normalizeProviderProfile(selectedProviderProfile.value) ||
      normalizeProviderProfile(loadPersistedProviderProfile()) ||
      defaultProviderProfile();
    if (!candidate) return;
    selectedProviderProfile.value = candidate;
  }

  async function fetchOutline() {
    loading.value = true;
    try {
      outline.value = await api.getOutline();
      await fetchKnowledgeExplorer();
    } catch (error) {
      console.error('Failed to fetch outline:', error);
    } finally {
      loading.value = false;
    }
  }

  async function fetchSessions() {
    loading.value = true;
    try {
      sessions.value = await api.getSessions();
      await fetchSessionExplorer();
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      loading.value = false;
    }
  }

  async function fetchSessionExplorer() {
    try {
      sessionExplorerTree.value = (await api.getSessionExplorer()).tree;
    } catch (error) {
      console.error('Failed to fetch session explorer:', error);
    }
  }

  async function fetchKnowledgeExplorer() {
    try {
      knowledgeExplorerTree.value = (await api.getKnowledgeExplorer()).tree;
      if (
        selectedKnowledgeScopeId.value &&
        !knowledgeScopeOptions.value.some(
          (scope) => scope.id === selectedKnowledgeScopeId.value
        )
      ) {
        selectedKnowledgeScopeId.value = null;
      }
    } catch (error) {
      console.error('Failed to fetch knowledge explorer:', error);
    }
  }

  async function organizeKnowledgeExplorer() {
    explorerBusy.value = true;
    try {
      const result = await api.organizeKnowledgeExplorer();
      await fetchKnowledgeExplorer();
      return result;
    } finally {
      explorerBusy.value = false;
    }
  }

  async function renameKnowledgeNode(nodeId: string, title: string) {
    await saveKnowledgeNode(nodeId, { title });
  }

  async function saveKnowledgeNode(nodeId: string, updates: KnowledgeNodeUpdate) {
    explorerBusy.value = true;
    try {
      const node = await api.updateKnowledgeNode(nodeId, updates);
      if (currentNode.value?.id === nodeId) currentNode.value = node;
      outline.value = outline.value.map((entry) =>
        entry.id === nodeId
          ? { ...entry, title: node.title, summary: node.summary, type: node.type }
          : entry
      );
      await fetchKnowledgeExplorer();
      return node;
    } catch (error) {
      console.error(`Failed to rename knowledge node ${nodeId}:`, error);
      throw error;
    } finally {
      explorerBusy.value = false;
    }
  }

  async function createExplorerFolder(
    scope: ExplorerScope,
    name: string,
    parentFolderId: string | null = null
  ) {
    explorerBusy.value = true;
    try {
      await api.createExplorerFolder({
        scope,
        name,
        parent_folder_id: parentFolderId,
      });
      if (scope === 'sessions') await fetchSessionExplorer();
      if (scope === 'knowledge') await fetchKnowledgeExplorer();
    } finally {
      explorerBusy.value = false;
    }
  }

  async function renameExplorerFolder(folderId: string, name: string) {
    explorerBusy.value = true;
    try {
      const folder = await api.renameExplorerFolder(folderId, name);
      if (folder.scope === 'sessions') await fetchSessionExplorer();
      if (folder.scope === 'knowledge') await fetchKnowledgeExplorer();
    } finally {
      explorerBusy.value = false;
    }
  }

  async function deleteExplorerFolder(scope: ExplorerScope, folderId: string) {
    explorerBusy.value = true;
    try {
      await api.deleteExplorerFolder(folderId);
      if (scope === 'sessions') await fetchSessionExplorer();
      if (scope === 'knowledge') await fetchKnowledgeExplorer();
    } finally {
      explorerBusy.value = false;
    }
  }

  async function moveExplorerItem(
    itemType: ExplorerItemType,
    itemId: string,
    folderId: string | null
  ) {
    explorerBusy.value = true;
    try {
      await api.moveExplorerItem(itemType, itemId, {
        folder_id: folderId,
        sort_order: 1000,
      });
      if (itemType === 'session') await fetchSessionExplorer();
      if (itemType === 'knowledge_node') await fetchKnowledgeExplorer();
    } finally {
      explorerBusy.value = false;
    }
  }

  async function updateExplorerItemIcon(
    itemType: ExplorerItemType,
    itemId: string,
    icon: string
  ) {
    explorerBusy.value = true;
    try {
      await api.updateExplorerItemIcon(itemType, itemId, icon);
      if (itemType === 'session') await fetchSessionExplorer();
      if (itemType === 'knowledge_node') await fetchKnowledgeExplorer();
    } finally {
      explorerBusy.value = false;
    }
  }

  async function fetchAnswerStyles() {
    try {
      answerStyles.value = await api.getAnswerStyles();
      if (
        selectedAnswerStyleId.value !== null &&
        !answerStyles.value.some((style) => style.answer_style_id === selectedAnswerStyleId.value)
      ) {
        selectedAnswerStyleId.value = null;
      }
    } catch (error) {
      console.error('Failed to fetch answer styles:', error);
    }
  }

  async function fetchStrategyAgents() {
    try {
      const response = await api.getStrategyAgents();
      strategyAgents.value = [
        {
          strategy_agent_id: 'auto',
          label: 'Auto',
          description: 'Let the Agent choose for each question.',
        },
        ...response.agents,
      ];
      if (
        !strategyAgents.value.some(
          (agent) => agent.strategy_agent_id === selectedStrategyAgentId.value
        )
      ) {
        selectedStrategyAgentId.value =
          defaultStrategyAgentId() ||
          response.default_strategy_agent_id;
      }
    } catch (error) {
      console.error('Failed to fetch strategy agents:', error);
    }
  }

  async function selectSession(sessionId: string) {
    cancelKnowledgeJobPolling();
    newSessionFolderId.value = null;
    loading.value = true;
    focusedAgentMessageId.value = null;
    try {
      currentSession.value = await api.getSession(sessionId);
      if (currentSession.value?.provider_profile) {
        selectedProviderProfile.value = { ...currentSession.value.provider_profile };
      } else {
        selectedProviderProfile.value = null;
        ensureSelectedProviderProfile();
      }
      selectedStrategyAgentId.value =
        currentSession.value?.strategy_agent_id || defaultStrategyAgentId();
      selectedKnowledgeScopeId.value =
        currentSession.value?.knowledge_scope_id || null;
      selectedKnowledgeApprovalPolicy.value =
        currentSession.value?.knowledge_approval_policy || defaultKnowledgeApprovalPolicy();
      selectedAnswerStyleId.value =
        currentSession.value?.default_answer_style_id || null;
      void fetchAgentState(sessionId);
    } catch (error) {
      console.error(`Failed to select session ${sessionId}:`, error);
    } finally {
      loading.value = false;
    }
  }

  async function selectNode(nodeId: string, token?: number) {
    loading.value = true;
    try {
      const node = await api.getNode(nodeId);
      if (token !== undefined && token !== standaloneKnowledgeJobPollToken) return;
      currentNode.value = node;
    } catch (error) {
      console.error(`Failed to select node ${nodeId}:`, error);
    } finally {
      loading.value = false;
    }
  }

  async function ask(question: string) {
    cancelKnowledgeJobPolling();
    loading.value = true;
    errorMessage.value = null;
    agentRunSteps.value = [];
    const previousSession = currentSession.value ? { ...currentSession.value } : null;
    currentSession.value = ensureStreamingSession(question);
    const creatingSession = currentSession.value.session_id === undefined;
    const targetFolderId = creatingSession ? newSessionFolderId.value : null;
    try {
      const strategyAgentId = selectedStrategyAgentId.value || undefined;
      const conversationModel =
        currentSession.value?.session_id === undefined && selectedProviderProfile.value
          ? {
              ...(selectedProviderProfile.value.provider_id
                ? { provider_id: selectedProviderProfile.value.provider_id }
                : {}),
              provider_type: selectedProviderProfile.value.provider_type,
              credential_id: selectedProviderProfile.value.credential_id,
              model: selectedProviderProfile.value.model,
            }
          : undefined;
      const streamCallbacks = {
        onChunk: appendStreamingChunk,
        onProgress: applyAgentProgress,
      };
      const response = await api.askStream(
        question,
        currentSession.value?.session_id,
        conversationModel,
        selectedAnswerStyleId.value || undefined,
        strategyAgentId,
        streamCallbacks,
        selectedKnowledgeScopeId.value,
        selectedKnowledgeApprovalPolicy.value
      );
      const latestAssistant = latestAssistantMessage(response.session);
      const responseAnchors =
        response.answer.anchors !== undefined
          ? response.answer.anchors
          : latestAssistant?.assistant_context.anchors;
      currentSession.value =
        responseAnchors && latestAssistant
          ? applyAnchorsToSession(response.session, latestAssistant.message_id, responseAnchors)
          : response.session;
      if (response.session.provider_profile) {
        selectedProviderProfile.value = { ...response.session.provider_profile };
      }
      selectedStrategyAgentId.value =
        response.session.strategy_agent_id || defaultStrategyAgentId();
      selectedKnowledgeScopeId.value =
        response.session.knowledge_scope_id || null;
      selectedKnowledgeApprovalPolicy.value =
        response.session.knowledge_approval_policy || defaultKnowledgeApprovalPolicy();
      selectedAnswerStyleId.value =
        response.session.default_answer_style_id || null;
      if (
        response.answer.knowledge_job_id &&
        latestAssistant &&
        response.session.session_id
      ) {
        startKnowledgeJobPolling(
          response.answer.knowledge_job_id,
          response.session.session_id,
          latestAssistant.message_id
        );
      }
      if (targetFolderId && response.session.session_id) {
        try {
          await api.moveExplorerItem('session', response.session.session_id, {
            folder_id: targetFolderId,
            sort_order: 1000,
          });
          newSessionFolderId.value = null;
        } catch (error) {
          console.error(`Failed to place new session in folder ${targetFolderId}:`, error);
        }
      }
      // Refresh session list to show updated titles/summaries
      await fetchSessions();
      void fetchAgentState(response.session.session_id);
    } catch (error) {
      currentSession.value = previousSession;
      errorMessage.value = 'Failed to send message. Check your provider settings and try again.';
      console.error('Failed to ask question:', error);
    } finally {
      loading.value = false;
    }
  }

  async function regenerate(messageId: string) {
    if (!currentSession.value?.session_id) return;
    cancelKnowledgeJobPolling();
    loading.value = true;
    errorMessage.value = null;
    try {
      const session = await api.regenerate(
        currentSession.value.session_id,
        messageId,
        selectedAnswerStyleId.value || undefined
      );
      currentSession.value = session;
      if (session.provider_profile) {
        selectedProviderProfile.value = { ...session.provider_profile };
      }
      selectedStrategyAgentId.value = session.strategy_agent_id || defaultStrategyAgentId();
      selectedKnowledgeScopeId.value = session.knowledge_scope_id || null;
      selectedKnowledgeApprovalPolicy.value =
        session.knowledge_approval_policy || defaultKnowledgeApprovalPolicy();
      await fetchSessions();
    } catch (error) {
      errorMessage.value = 'Failed to regenerate response. Check your provider settings and try again.';
      console.error('Failed to regenerate response:', error);
    } finally {
      loading.value = false;
    }
  }

  async function fetchCredentials() {
    try {
      credentials.value = await api.getCredentials();
      ensureSelectedProviderProfile();
    } catch (error) {
      console.error('Failed to fetch credentials:', error);
    }
  }

  async function fetchProviderOptions() {
    try {
      const payload = await api.getProviderOptions();
      providerOptions.value = payload.providers;
      providerCatalog.value = payload.provider_catalog;
      defaultOptions.value = payload.default_options;
      if (!currentSession.value?.session_id) {
        selectedKnowledgeApprovalPolicy.value = defaultKnowledgeApprovalPolicy();
      }
      ensureSelectedProviderProfile();
    } catch (error) {
      console.error('Failed to fetch provider options:', error);
    }
  }

  async function createCredential(payload: CredentialPayload) {
    loading.value = true;
    try {
      await api.createCredential(payload);
      await fetchCredentials();
    } catch (error) {
      console.error('Failed to create credential:', error);
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function updateCredential(credentialId: string, payload: CredentialPayload) {
    loading.value = true;
    try {
      await api.updateCredential(credentialId, payload);
      await fetchCredentials();
    } catch (error) {
      console.error('Failed to update credential:', error);
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function updateDefaultOptions(payload: DefaultOptions) {
    loading.value = true;
    try {
      const updated = await api.updateDefaultOptions(payload);
      defaultOptions.value = updated;
      if (!currentSession.value?.session_id) {
        selectedKnowledgeApprovalPolicy.value = defaultKnowledgeApprovalPolicy();
      }
      ensureSelectedProviderProfile();
    } catch (error) {
      console.error('Failed to update default model settings:', error);
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function deleteSession(sessionId: string) {
    cancelKnowledgeJobPolling();
    loading.value = true;
    try {
      await api.deleteSession(sessionId);
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = null;
        currentNode.value = null;
        focusedAgentMessageId.value = null;
      }
      await fetchSessions();
    } catch (error) {
      console.error(`Failed to delete session ${sessionId}:`, error);
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function updateSessionIcon(sessionId: string, icon: string) {
    explorerBusy.value = true;
    try {
      const session = await api.updateSession(sessionId, { icon });
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = session;
      }
      sessions.value = sessions.value.map((entry) =>
        entry.session_id === sessionId ? { ...entry, icon: session.icon } : entry
      );
      await fetchSessionExplorer();
    } catch (error) {
      console.error(`Failed to update session icon for ${sessionId}:`, error);
      throw error;
    } finally {
      explorerBusy.value = false;
    }
  }

  async function renameSession(sessionId: string, title: string) {
    explorerBusy.value = true;
    try {
      const session = await api.updateSession(sessionId, { title });
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = session;
      }
      sessions.value = sessions.value.map((entry) =>
        entry.session_id === sessionId ? { ...entry, title: session.title } : entry
      );
      await fetchSessionExplorer();
    } catch (error) {
      console.error(`Failed to rename session ${sessionId}:`, error);
      throw error;
    } finally {
      explorerBusy.value = false;
    }
  }

  async function updateSessionConversationModel(sessionId: string, profile: ConfiguredModelProfile) {
    loading.value = true;
    try {
      const session = await api.updateSession(sessionId, {
        conversation_model: {
          provider_id: profile.provider_id,
          provider_type: profile.provider_type,
          credential_id: profile.credential_id,
          model: profile.model,
        },
      });
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = session;
      }
      if (session.provider_profile) {
        selectedProviderProfile.value = { ...session.provider_profile };
      }
    } catch (error) {
      console.error(`Failed to update conversation model for ${sessionId}:`, error);
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function fetchAgentState(sessionId = currentSession.value?.session_id) {
    const token = ++agentStateRequestToken;
    const requestedSessionId = sessionId;
    agentStateLoading.value = true;
    try {
      const nextAgentState = await api.getAgentState(requestedSessionId);
      if (token !== agentStateRequestToken) return;
      if (requestedSessionId !== (currentSession.value?.session_id ?? undefined)) return;
      agentState.value = nextAgentState;
    } catch (error) {
      console.error('Failed to fetch agent state:', error);
    } finally {
      if (token === agentStateRequestToken) {
        agentStateLoading.value = false;
      }
    }
  }

  function openAgentStateForMessage(messageId?: string) {
    focusedAgentMessageId.value = messageId ?? null;
    activeTab.value = 'agent';
    void fetchAgentState(currentSession.value?.session_id);
  }

  async function acceptSuggestedDrafts(messageId: string, draftIndexes: number[]) {
    if (!currentSession.value?.session_id || !draftIndexes.length) return;
    const sessionId = currentSession.value.session_id;
    knowledgeApprovalBusyMessageIds.value = [
      ...new Set([...knowledgeApprovalBusyMessageIds.value, messageId]),
    ];
    try {
      const job = await api.compileSuggestedDrafts(sessionId, messageId, draftIndexes);
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = applyAnchorsToSession(currentSession.value, messageId, job.anchors);
        const message = currentSession.value.messages.find(
          (item) => item.message_id === messageId
        );
        if (message?.assistant_context.orchestration_plan?.authorization) {
          message.assistant_context.orchestration_plan.authorization.status = 'approved';
        }
      }
      startKnowledgeJobPolling(job.job_id, sessionId, messageId);
      void fetchAgentState(sessionId);
    } catch (error) {
      errorMessage.value = 'Failed to start knowledge note generation.';
      console.error('Failed to accept suggested drafts:', error);
    } finally {
      knowledgeApprovalBusyMessageIds.value = knowledgeApprovalBusyMessageIds.value.filter(
        (item) => item !== messageId
      );
    }
  }

  async function rejectSuggestedDrafts(messageId: string) {
    if (!currentSession.value?.session_id) return;
    const sessionId = currentSession.value.session_id;
    knowledgeApprovalBusyMessageIds.value = [
      ...new Set([...knowledgeApprovalBusyMessageIds.value, messageId]),
    ];
    try {
      const session = await api.rejectSuggestedDrafts(sessionId, messageId);
      if (currentSession.value?.session_id === sessionId) {
        currentSession.value = session;
      }
      void fetchAgentState(sessionId);
    } catch (error) {
      errorMessage.value = 'Failed to reject knowledge note generation.';
      console.error('Failed to reject suggested drafts:', error);
    } finally {
      knowledgeApprovalBusyMessageIds.value = knowledgeApprovalBusyMessageIds.value.filter(
        (item) => item !== messageId
      );
    }
  }

  function setDraftQuestion(question: string) {
    draftQuestion.value = question;
  }

  function prepareKnowledgeFollowUp(nodeId: string, title: string) {
    const findFolderId = (nodes: ExplorerTreeNode[]): string | null | undefined => {
      for (const node of nodes) {
        if (node.kind === 'item') {
          const itemId = String(
            node.location?.item_id || node.item?.item_id || node.item?.id || ''
          );
          if (itemId === nodeId) return node.location?.folder_id || null;
          continue;
        }
        const found = findFolderId(node.children || []);
        if (found !== undefined) return found;
      }
      return undefined;
    };
    const nodeScopeId = findFolderId(knowledgeExplorerTree.value);
    if (nodeScopeId !== undefined) selectedKnowledgeScopeId.value = nodeScopeId;
    draftQuestion.value = `围绕知识点「${title}」继续追问：`;
    activeTab.value = 'chat';
  }

  async function generateKnowledgeFromSelection(
    payload: SelectionActionPayload,
    promptKind: SelectionKnowledgePromptKind
  ) {
    cancelStandaloneKnowledgeJobPolling();
    const token = standaloneKnowledgeJobPollToken;
    loading.value = true;
    errorMessage.value = null;
    try {
      const source: SelectionKnowledgeSource | null =
        payload.sourceType === 'knowledge-node'
          ? payload.nodeId
            ? {
                type: 'knowledge-node',
                node_id: payload.nodeId,
              }
            : null
          : payload.sessionId && payload.messageId
            ? {
                type: 'chat-message',
                session_id: payload.sessionId,
                message_id: payload.messageId,
              }
            : null;
      if (!source) {
        errorMessage.value = 'Failed to start knowledge note generation.';
        return;
      }
      const job = await api.compileSelectionKnowledge({
        selected_text: payload.text,
        prompt_kind: promptKind,
        source,
        conversation_model: buildConversationModel(),
      });
      if (token !== standaloneKnowledgeJobPollToken) return;
      await pollStandaloneKnowledgeJob(job.job_id, token, 0);
    } catch (error) {
      errorMessage.value = 'Failed to start knowledge note generation.';
      console.error('Failed to generate knowledge from selection:', error);
    } finally {
      loading.value = false;
    }
  }

  function setConversationBaseFolder(folderId: string | null) {
    conversationBaseFolderId.value = folderId;
  }

  function newSession(folderId?: string | null) {
    cancelKnowledgeJobPolling();
    const nextProfile =
      normalizeProviderProfile(selectedProviderProfile.value) ||
      normalizeProviderProfile(loadPersistedProviderProfile()) ||
      defaultProviderProfile();
    currentSession.value = null;
    currentNode.value = null;
    focusedAgentMessageId.value = null;
    agentRunSteps.value = [];
    selectedProviderProfile.value = nextProfile;
    selectedStrategyAgentId.value = defaultStrategyAgentId();
    selectedKnowledgeScopeId.value = null;
    selectedKnowledgeApprovalPolicy.value = defaultKnowledgeApprovalPolicy();
    selectedAnswerStyleId.value = null;
    newSessionFolderId.value = folderId === undefined
      ? conversationBaseFolderId.value
      : folderId;
  }

  watch(
    selectedProviderProfile,
    (profile) => {
      persistProviderProfile(profile);
    },
    { deep: true, flush: 'sync' }
  );

  async function fork(messageId: string) {
    if (!currentSession.value?.session_id) return;
    cancelKnowledgeJobPolling();
    loading.value = true;
    try {
      const anchorMessage = currentSession.value.messages.find(
        (message) => message.message_id === messageId
      );
      if (!anchorMessage) return;
      const focusQuestion = `Forked from: ${anchorMessage.content.substring(0, 50)}...`;
      const response = await api.fork(currentSession.value.session_id, {
        fork_anchor: {
          type: 'message',
          message_id: messageId,
        },
        focus_question: focusQuestion,
      });
      currentSession.value = response;
      await fetchSessions();
    } catch (error) {
      console.error('Failed to fork session:', error);
    } finally {
      loading.value = false;
    }
  }

  return {
    sessions,
    outline,
    sessionExplorerTree,
    knowledgeExplorerTree,
    currentSession,
    currentNode,
    loading,
    explorerBusy,
    errorMessage,
    credentials,
    providerOptions,
    providerCatalog,
    defaultOptions,
    configuredModelProfiles,
    answerStyles,
    strategyAgents,
    knowledgeScopeOptions,
    selectedAnswerStyleId,
    selectedStrategyAgentId,
    selectedKnowledgeScopeId,
    selectedKnowledgeApprovalPolicy,
    selectedProviderProfile,
    draftQuestion,
    newSessionFolderId,
    conversationBaseFolderId,
    activeTab,
    agentState,
    agentStateLoading,
    focusedAgentMessageId,
    agentRunSteps,
    knowledgeApprovalBusyMessageIds,
    fetchOutline,
    fetchSessions,
    fetchSessionExplorer,
    fetchKnowledgeExplorer,
    organizeKnowledgeExplorer,
    renameKnowledgeNode,
    saveKnowledgeNode,
    createExplorerFolder,
    renameExplorerFolder,
    deleteExplorerFolder,
    moveExplorerItem,
    updateExplorerItemIcon,
    fetchAnswerStyles,
    fetchStrategyAgents,
    fetchCredentials,
    fetchProviderOptions,
    fetchAgentState,
    openAgentStateForMessage,
    acceptSuggestedDrafts,
    rejectSuggestedDrafts,
    setDraftQuestion,
    prepareKnowledgeFollowUp,
    generateKnowledgeFromSelection,
    updateDefaultOptions,
    createCredential,
    updateCredential,
    selectSession,
    selectNode,
    ask,
    regenerate,
    setConversationBaseFolder,
    newSession,
    fork,
    deleteSession,
    renameSession,
    updateSessionIcon,
    updateSessionConversationModel,
  };
});
