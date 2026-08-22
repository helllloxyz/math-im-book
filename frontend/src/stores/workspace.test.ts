import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('../services/api', () => ({
  api: {
    getProviderOptions: vi.fn(),
    getCredentials: vi.fn(),
    getAnswerStyles: vi.fn(),
    getStrategyAgents: vi.fn(),
    getSessions: vi.fn(),
    getSession: vi.fn(),
    getOutline: vi.fn(),
    getSessionExplorer: vi.fn(),
    getKnowledgeExplorer: vi.fn(),
    organizeKnowledgeExplorer: vi.fn(),
    createExplorerFolder: vi.fn(),
    renameExplorerFolder: vi.fn(),
    deleteExplorerFolder: vi.fn(),
    moveExplorerItem: vi.fn(),
    updateExplorerItemIcon: vi.fn(),
    getNode: vi.fn(),
    updateKnowledgeNode: vi.fn(),
    getKnowledgeJob: vi.fn(),
    compileSuggestedDrafts: vi.fn(),
    rejectSuggestedDrafts: vi.fn(),
    compileSelectionKnowledge: vi.fn(),
    createCredential: vi.fn(),
    updateCredential: vi.fn(),
    ask: vi.fn(),
    askStream: vi.fn(),
    cancelAsk: vi.fn(),
    regenerate: vi.fn(),
    fork: vi.fn(),
    deleteSession: vi.fn(),
    updateSession: vi.fn(),
    getAgentState: vi.fn(),
  },
}));

import { api } from '../services/api';
import { useWorkspaceStore } from './workspace';

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('workspace store provider configuration', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    const storage = new Map<string, string>();
    Object.defineProperty(globalThis, 'window', {
      value: {
        localStorage: {
          getItem: (key: string) => storage.get(key) ?? null,
          setItem: (key: string, value: string) => {
            storage.set(key, value);
          },
          removeItem: (key: string) => {
            storage.delete(key);
          },
          clear: () => {
            storage.clear();
          },
        },
      },
      configurable: true,
    });
  });

  it('initializes the selected provider profile from provider options config', async () => {
    vi.mocked(api.getProviderOptions).mockResolvedValue({
      providers: [
        {
          provider_type: 'gemini',
          label: 'Google Gemini',
          default_model: 'gemini-3-flash-preview',
          models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
          allow_custom_model: false,
          requires_base_url: false,
          default_base_url: null,
        },
      ],
      provider_catalog: [],
      default_options: {
        conversation_model: {
          provider_type: 'gemini',
          model: 'gemini-3-flash-preview',
          credential_id: 'gemini-main',
        },
        utility_model: {
          provider_type: 'gemini',
          model: 'gemini-3-flash-preview',
          credential_id: 'gemini-main',
        },
      },
    } as any);
    vi.mocked(api.getCredentials).mockResolvedValue([
      {
        credential_id: 'gemini-main',
        provider_type: 'gemini',
        has_headers: false,
      },
    ]);

    const store = useWorkspaceStore();

    await store.fetchProviderOptions();
    await store.fetchCredentials();

    expect(store.providerOptions[0].models).toEqual([
      'gemini-3-flash-preview',
      'gemini-3-pro-preview',
    ]);
    expect(store.selectedProviderProfile).toEqual({
      provider_type: 'gemini',
      model: 'gemini-3-flash-preview',
      credential_id: 'gemini-main',
    });
  });

  it('refreshes explorer trees with sessions and outline', async () => {
    vi.mocked(api.getSessions).mockResolvedValue([]);
    vi.mocked(api.getOutline).mockResolvedValue([]);
    vi.mocked(api.getSessionExplorer).mockResolvedValue({
      scope: 'sessions',
      tree: [
        {
          kind: 'item',
          item: { item_id: 'chat-1', session_id: 'chat-1', title: 'Vector Spaces' },
          location: {
            item_type: 'session',
            item_id: 'chat-1',
            folder_id: null,
            sort_order: 1000,
            path_cached: '/chat-1',
            location_source: 'system',
            user_locked: false,
            updated_at: '',
          },
          children: [],
        },
      ],
    } as any);
    vi.mocked(api.getKnowledgeExplorer).mockResolvedValue({
      scope: 'knowledge',
      tree: [
        {
          kind: 'item',
          item: { item_id: 'linear-map', id: 'linear-map', title: 'Linear Map' },
          location: {
            item_type: 'knowledge_node',
            item_id: 'linear-map',
            folder_id: null,
            sort_order: 1000,
            path_cached: '/linear-map',
            location_source: 'system',
            user_locked: false,
            updated_at: '',
          },
          children: [],
        },
      ],
    } as any);
    const store = useWorkspaceStore();

    await store.fetchSessions();
    await store.fetchOutline();

    expect(store.sessionExplorerTree[0].item?.session_id).toBe('chat-1');
    expect(store.knowledgeExplorerTree[0].item?.id).toBe('linear-map');
  });

  it('offers only root Library folders as knowledge scopes', () => {
    const store = useWorkspaceStore();
    store.knowledgeExplorerTree = [
      {
        kind: 'folder',
        folder: { folder_id: 'library-course', name: 'Course', parent_folder_id: null },
        children: [
          {
            kind: 'folder',
            folder: {
              folder_id: 'library-definitions',
              name: 'Definitions',
              parent_folder_id: 'library-course',
            },
            children: [
              {
                kind: 'item',
                item: { item_id: 'vector-space', title: 'Vector Space' },
                children: [],
              },
            ],
          },
        ],
      },
    ] as any;

    expect(store.knowledgeScopeOptions).toEqual([
      { id: 'library-course', label: 'Course', nodeCount: 1 },
    ]);
  });

  it('creates folders and moves items through explorer actions', async () => {
    vi.mocked(api.createExplorerFolder).mockResolvedValue({ folder_id: 'folder-1' } as any);
    vi.mocked(api.moveExplorerItem).mockResolvedValue({ item_id: 'chat-1' } as any);
    vi.mocked(api.getSessionExplorer).mockResolvedValue({ scope: 'sessions', tree: [] });
    vi.mocked(api.getKnowledgeExplorer).mockResolvedValue({ scope: 'knowledge', tree: [] });
    const store = useWorkspaceStore();

    await store.createExplorerFolder('sessions', 'Course', null);
    await store.moveExplorerItem('session', 'chat-1', 'folder-1');

    expect(api.createExplorerFolder).toHaveBeenCalledWith({
      scope: 'sessions',
      name: 'Course',
      parent_folder_id: null,
    });
    expect(api.moveExplorerItem).toHaveBeenCalledWith('session', 'chat-1', {
      folder_id: 'folder-1',
      sort_order: 1000,
    });
    expect(api.getSessionExplorer).toHaveBeenCalledTimes(2);
    expect(api.getKnowledgeExplorer).toHaveBeenCalledTimes(1);
  });

  it('renames and deletes folders while refreshing the matching scope', async () => {
    vi.mocked(api.renameExplorerFolder).mockResolvedValue({
      folder_id: 'folder-1',
      scope: 'knowledge',
      name: 'Foundations',
    } as any);
    vi.mocked(api.deleteExplorerFolder).mockResolvedValue(undefined);
    vi.mocked(api.getKnowledgeExplorer).mockResolvedValue({ scope: 'knowledge', tree: [] });
    const store = useWorkspaceStore();

    await store.renameExplorerFolder('folder-1', 'Foundations');
    await store.deleteExplorerFolder('knowledge', 'folder-1');

    expect(api.renameExplorerFolder).toHaveBeenCalledWith('folder-1', 'Foundations');
    expect(api.deleteExplorerFolder).toHaveBeenCalledWith('folder-1');
    expect(api.getKnowledgeExplorer).toHaveBeenCalledTimes(2);
    expect(store.explorerBusy).toBe(false);
  });

  it('organizes knowledge notes and refreshes the library tree', async () => {
    vi.mocked(api.organizeKnowledgeExplorer).mockResolvedValue({
      scope: 'knowledge',
      organized_count: 3,
      folders_created: 2,
    });
    vi.mocked(api.getKnowledgeExplorer).mockResolvedValue({ scope: 'knowledge', tree: [] });
    const store = useWorkspaceStore();

    const result = await store.organizeKnowledgeExplorer();

    expect(result.organized_count).toBe(3);
    expect(api.getKnowledgeExplorer).toHaveBeenCalledTimes(1);
    expect(store.explorerBusy).toBe(false);
  });

  it('renames a knowledge note without changing its stable id', async () => {
    vi.mocked(api.updateKnowledgeNode).mockResolvedValue({
      id: 'linear-map',
      title: 'Linear transformations',
    } as any);
    vi.mocked(api.getKnowledgeExplorer).mockResolvedValue({ scope: 'knowledge', tree: [] });
    const store = useWorkspaceStore();
    store.currentNode = { id: 'linear-map', title: 'Linear Map' } as any;
    store.outline = [{ id: 'linear-map', title: 'Linear Map' }] as any;

    await store.renameKnowledgeNode('linear-map', 'Linear transformations');

    expect(api.updateKnowledgeNode).toHaveBeenCalledWith('linear-map', {
      title: 'Linear transformations',
    });
    expect(store.currentNode?.id).toBe('linear-map');
    expect(store.currentNode?.title).toBe('Linear transformations');
    expect(store.outline[0].title).toBe('Linear transformations');
  });

  it('always clears explorer busy state when a folder action fails', async () => {
    vi.mocked(api.createExplorerFolder).mockRejectedValue(new Error('duplicate'));
    const store = useWorkspaceStore();

    await expect(store.createExplorerFolder('sessions', 'Course')).rejects.toThrow('duplicate');

    expect(store.explorerBusy).toBe(false);
  });

  it('updates explorer item icons and refreshes the matching tree', async () => {
    vi.mocked(api.updateExplorerItemIcon).mockResolvedValue({ icon: 'wave' } as any);
    vi.mocked(api.getKnowledgeExplorer).mockResolvedValue({
      scope: 'knowledge',
      tree: [
        {
          kind: 'item',
          item: { item_type: 'knowledge_node', item_id: 'linear-map', icon: 'wave' },
          children: [],
        },
      ],
    });
    const store = useWorkspaceStore();

    await store.updateExplorerItemIcon('knowledge_node', 'linear-map', 'wave');

    expect(api.updateExplorerItemIcon).toHaveBeenCalledWith('knowledge_node', 'linear-map', 'wave');
    expect(api.getKnowledgeExplorer).toHaveBeenCalledTimes(1);
    expect(store.knowledgeExplorerTree[0].item?.icon).toBe('wave');
  });

  it('initializes the selected provider profile from the configured conversation default', async () => {
    vi.mocked(api.getProviderOptions).mockResolvedValue({
      providers: [],
      provider_catalog: [
        {
          provider_id: 'gemini',
          provider_type: 'gemini',
          label: 'Gemini',
          default_model: 'gemini-3-flash-preview',
          models: ['gemini-3-flash-preview'],
          allow_custom_model: false,
          requires_base_url: false,
          default_base_url: '',
        },
        {
          provider_id: 'deepseek',
          provider_type: 'openai_compatible',
          label: 'DeepSeek',
          default_model: 'deepseek-chat',
          models: ['deepseek-chat'],
          allow_custom_model: true,
          requires_base_url: true,
          default_base_url: 'https://api.deepseek.com/v1',
        },
      ],
      default_options: {
        conversation_model: {
          provider_id: 'deepseek',
          provider_type: 'openai_compatible',
          model: 'deepseek-chat',
          credential_id: 'deepseek',
        },
        utility_model: {
          provider_id: 'deepseek',
          provider_type: 'openai_compatible',
          model: 'deepseek-chat',
          credential_id: 'deepseek',
        },
      },
    } as any);
    vi.mocked(api.getCredentials).mockResolvedValue([
      {
        credential_id: 'gemini',
        provider_type: 'gemini',
        provider_id: 'gemini',
        has_headers: false,
      },
      {
        credential_id: 'deepseek',
        provider_type: 'openai_compatible',
        provider_id: 'deepseek',
        has_headers: false,
        base_url: 'https://api.deepseek.com/v1',
      },
    ] as any);

    const store = useWorkspaceStore();

    await store.fetchProviderOptions();
    await store.fetchCredentials();

    expect(store.selectedProviderProfile).toEqual({
      provider_id: 'deepseek',
      provider_type: 'openai_compatible',
      model: 'deepseek-chat',
      credential_id: 'deepseek',
      base_url: 'https://api.deepseek.com/v1',
    });
  });

  it('keeps the current provider profile when starting a new session', async () => {
    vi.mocked(api.getProviderOptions).mockResolvedValue({
      providers: [
        {
          provider_type: 'openai_compatible',
          label: 'OpenAI Compatible',
          default_model: 'gpt-5.1',
          models: ['gpt-5.1'],
          allow_custom_model: true,
          requires_base_url: true,
          default_base_url: 'https://api.openai.com/v1',
        },
      ],
      provider_catalog: [],
      default_options: {
        conversation_model: {
          provider_type: 'openai_compatible',
          model: 'gpt-5.1',
          credential_id: 'openai-main',
          base_url: 'https://api.openai.com/v1',
        },
        utility_model: {
          provider_type: 'openai_compatible',
          model: 'gpt-5.1',
          credential_id: 'openai-main',
          base_url: 'https://api.openai.com/v1',
        },
      },
    } as any);
    vi.mocked(api.getCredentials).mockResolvedValue([
      {
        credential_id: 'openai-main',
        provider_type: 'openai_compatible',
        has_headers: false,
      },
    ]);

    const store = useWorkspaceStore();

    await store.fetchProviderOptions();
    await store.fetchCredentials();
    store.selectedProviderProfile = {
      provider_type: 'openai_compatible',
      model: 'other-model',
      credential_id: 'openai-main',
      base_url: 'https://example.com/v1',
    };

    store.newSession();

    expect(store.selectedProviderProfile).toEqual({
      provider_type: 'openai_compatible',
      model: 'other-model',
      credential_id: 'openai-main',
      base_url: 'https://example.com/v1',
    });
  });

  it('restores the last used provider profile from local storage', async () => {
    window.localStorage.setItem(
      'math-im-book:last-provider-profile',
      JSON.stringify({
        provider_type: 'gemini',
        model: 'gemini-3-pro-preview',
        credential_id: 'gemini-main',
      })
    );
    vi.mocked(api.getProviderOptions).mockResolvedValue({
      providers: [
        {
          provider_type: 'gemini',
          label: 'Google Gemini',
          default_model: 'gemini-3-flash-preview',
          models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
          allow_custom_model: false,
          requires_base_url: false,
          default_base_url: null,
        },
      ],
      provider_catalog: [],
      default_options: {
        conversation_model: {
          provider_type: 'gemini',
          model: 'gemini-3-pro-preview',
          credential_id: 'gemini-main',
        },
        utility_model: {
          provider_type: 'gemini',
          model: 'gemini-3-pro-preview',
          credential_id: 'gemini-main',
        },
      },
    } as any);
    vi.mocked(api.getCredentials).mockResolvedValue([
      {
        credential_id: 'gemini-main',
        provider_type: 'gemini',
        has_headers: false,
      },
    ]);

    const store = useWorkspaceStore();

    await store.fetchProviderOptions();
    await store.fetchCredentials();

    expect(store.selectedProviderProfile).toEqual({
      provider_type: 'gemini',
      model: 'gemini-3-pro-preview',
      credential_id: 'gemini-main',
    });
  });

  it('uses the last selected provider profile for a new session', async () => {
    vi.mocked(api.getProviderOptions).mockResolvedValue({
      providers: [
        {
          provider_type: 'gemini',
          label: 'Google Gemini',
          default_model: 'gemini-3-flash-preview',
          models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
          allow_custom_model: false,
          requires_base_url: false,
          default_base_url: null,
        },
      ],
      provider_catalog: [],
      default_options: {
        conversation_model: {
          provider_type: 'gemini',
          model: 'gemini-3-pro-preview',
          credential_id: 'gemini-main',
        },
        utility_model: {
          provider_type: 'gemini',
          model: 'gemini-3-pro-preview',
          credential_id: 'gemini-main',
        },
      },
    } as any);
    vi.mocked(api.getCredentials).mockResolvedValue([
      {
        credential_id: 'gemini-main',
        provider_type: 'gemini',
        has_headers: false,
      },
    ]);

    const store = useWorkspaceStore();

    await store.fetchProviderOptions();
    await store.fetchCredentials();
    store.selectedProviderProfile = {
      provider_type: 'gemini',
      model: 'gemini-3-pro-preview',
      credential_id: 'gemini-main',
    };

    store.newSession();

    expect(store.selectedProviderProfile).toEqual({
      provider_type: 'gemini',
      model: 'gemini-3-pro-preview',
      credential_id: 'gemini-main',
    });
  });

  it('loads answer styles and keeps the selected style empty until the user picks one', async () => {
    vi.mocked(api.getAnswerStyles).mockResolvedValue([
      {
        answer_style_id: 'default',
        label: 'Default',
        description: 'Stable default prompting',
      },
      {
        answer_style_id: 'rigorous',
        label: 'Rigorous',
        description: 'Tighter reasoning and proof checks',
      },
    ] as any);

    const store = useWorkspaceStore();

    await store.fetchAnswerStyles();

    expect(api.getAnswerStyles).toHaveBeenCalledTimes(1);
    expect(store.answerStyles.map((style) => style.answer_style_id)).toEqual(['default', 'rigorous']);
    expect(store.selectedAnswerStyleId).toBeNull();
  });

  it('adds Auto and defaults new sessions to per-question Agent selection', async () => {
    vi.mocked(api.getStrategyAgents).mockResolvedValue({
      default_strategy_agent_id: 'top-down',
      agents: [
        {
          strategy_agent_id: 'top-down',
          label: 'Top Down',
          description: 'Start from structure first.',
          instructions: '# Top Down',
          is_default: true,
        },
        {
          strategy_agent_id: 'raw',
          label: 'Raw',
          description: 'Use the question as-is.',
          instructions: '# Raw',
          is_default: false,
        },
      ],
    } as any);

    const store = useWorkspaceStore();

    await store.fetchStrategyAgents();

    expect(api.getStrategyAgents).toHaveBeenCalledTimes(1);
    expect(store.strategyAgents.map((agent) => agent.strategy_agent_id)).toEqual([
      'auto',
      'top-down',
      'raw',
    ]);
    expect(store.selectedStrategyAgentId).toBe('auto');

    store.selectedStrategyAgentId = 'raw';
    store.newSession();

    expect(store.selectedStrategyAgentId).toBe('auto');
  });

  it('syncs answer, strategy, and approval settings when selecting a session', async () => {
    vi.mocked(api.getSession).mockResolvedValue({
      session_id: 'sess-123',
      default_answer_style_id: 'rigorous',
      strategy_agent_id: 'raw',
      knowledge_approval_policy: 'full_auto',
      messages: [],
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
    } as any);

    const store = useWorkspaceStore();

    await store.selectSession('sess-123');

    expect(store.selectedAnswerStyleId).toBe('rigorous');
    expect(store.selectedStrategyAgentId).toBe('raw');
    expect(store.selectedKnowledgeApprovalPolicy).toBe('full_auto');
  });

  it('sends the selected answer style id with ask requests only when explicitly selected', async () => {
    vi.mocked(api.askStream).mockResolvedValue({
      action: {
        action_type: 'answer',
        selected_node_ids: [],
        draft_requests: [],
        user_visible_reason: 'done',
      },
      answer: {
        summary: 'summary',
        detail: 'detail',
        references: [],
        symbols: {},
        symbol_conflicts: [],
        assistant_text: 'assistant reply',
      },
      drafts: [],
      created_node_ids: [],
      session: {
        session_id: 'chat-1',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        messages: [],
      } as any,
    } as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;
    store.selectedProviderProfile = {
      provider_type: 'gemini',
      model: 'gemini-3-flash-preview',
      credential_id: 'gemini-main',
    } as any;
    store.selectedAnswerStyleId = 'rigorous';

    await store.ask('Explain the proof.');

    expect(api.askStream).toHaveBeenCalledWith(
      'Explain the proof.',
      'chat-1',
      undefined,
      'rigorous',
      undefined,
      expect.objectContaining({
        onChunk: expect.any(Function),
      }),
      null,
      'agent_decides'
    );
  });

  it('omits answer style id from ask requests when no style is selected', async () => {
    vi.mocked(api.askStream).mockResolvedValue({
      action: {
        action_type: 'answer',
        selected_node_ids: [],
        draft_requests: [],
        user_visible_reason: 'done',
      },
      answer: {
        summary: 'summary',
        detail: 'detail',
        references: [],
        symbols: {},
        symbol_conflicts: [],
        assistant_text: 'assistant reply',
      },
      drafts: [],
      created_node_ids: [],
      session: {
        session_id: 'chat-1',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        messages: [],
      } as any,
    } as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;
    vi.mocked(api.getAgentState).mockResolvedValue({
      current_turn: null,
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        profile_context_summary: null,
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any);
    store.selectedProviderProfile = {
      provider_type: 'gemini',
      model: 'gemini-3-flash-preview',
      credential_id: 'gemini-main',
    } as any;
    store.selectedAnswerStyleId = null as any;

    await store.ask('Explain the proof.');

    expect(api.askStream).toHaveBeenCalledWith(
      'Explain the proof.',
      'chat-1',
      undefined,
      undefined,
      undefined,
      expect.objectContaining({
        onChunk: expect.any(Function),
      }),
      null,
      'agent_decides'
    );
    expect(api.getAgentState).toHaveBeenCalledWith('chat-1');
  });

  it('sends the selected strategy agent with the first ask in a new session', async () => {
    vi.mocked(api.askStream).mockResolvedValue({
      action: {
        action_type: 'answer',
        selected_node_ids: [],
        draft_requests: [],
        user_visible_reason: 'done',
      },
      answer: {
        summary: 'summary',
        detail: 'detail',
        references: [],
        symbols: {},
        symbol_conflicts: [],
        assistant_text: 'assistant reply',
      },
      drafts: [],
      created_node_ids: [],
      session: {
        session_id: 'chat-1',
        strategy_agent_id: 'raw',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        messages: [],
      } as any,
    } as any);

    const store = useWorkspaceStore();
    store.selectedProviderProfile = {
      provider_type: 'gemini',
      model: 'gemini-3-flash-preview',
      credential_id: 'gemini-main',
    } as any;
    store.selectedStrategyAgentId = 'raw';
    store.selectedKnowledgeApprovalPolicy = 'always_ask';

    await store.ask('Explain the proof.');

    expect(api.askStream).toHaveBeenCalledWith(
      'Explain the proof.',
      undefined,
      {
        provider_type: 'gemini',
        model: 'gemini-3-flash-preview',
        credential_id: 'gemini-main',
      },
      undefined,
      'raw',
      expect.objectContaining({
        onChunk: expect.any(Function),
      }),
      null,
      'always_ask'
    );
  });

  it('places a newly created conversation in the selected folder', async () => {
    vi.mocked(api.askStream).mockResolvedValue({
      action: {
        action_type: 'answer',
        selected_node_ids: [],
        draft_requests: [],
        user_visible_reason: 'done',
      },
      answer: {
        summary: 'summary',
        detail: 'detail',
        references: [],
        symbols: {},
        symbol_conflicts: [],
        assistant_text: 'assistant reply',
      },
      drafts: [],
      created_node_ids: [],
      session: {
        session_id: 'chat-in-course',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        messages: [],
      },
    } as any);
    vi.mocked(api.getSessions).mockResolvedValue([]);
    vi.mocked(api.getSessionExplorer).mockResolvedValue({ scope: 'sessions', tree: [] });
    vi.mocked(api.getKnowledgeExplorer).mockResolvedValue({ scope: 'knowledge', tree: [] });

    const store = useWorkspaceStore();
    store.sessionExplorerTree = [
      {
        kind: 'folder',
        folder: {
          folder_id: 'folder-course-root',
          scope: 'sessions',
          scope_id: 'scope-course',
          name: 'Course',
          parent_folder_id: null,
        },
        children: [
          {
            kind: 'folder',
            folder: {
              folder_id: 'folder-course',
              scope: 'sessions',
              scope_id: 'scope-course',
              name: 'Week 1',
              parent_folder_id: 'folder-course-root',
            },
            children: [],
          },
        ],
      },
    ] as any;
    store.knowledgeExplorerTree = [
      {
        kind: 'folder',
        folder: {
          folder_id: 'library-course',
          scope: 'knowledge',
          scope_id: 'scope-course',
          name: 'Course',
          parent_folder_id: null,
        },
        children: [],
      },
    ] as any;
    store.newSession('folder-course');

    expect(store.selectedKnowledgeScopeId).toBe('library-course');
    await store.ask('Start inside this course.');

    const askCall = vi.mocked(api.askStream).mock.calls[0];
    expect(askCall?.[6]).toBe('library-course');
    expect(askCall?.at(-1)).toBe('folder-course');
    expect(api.moveExplorerItem).not.toHaveBeenCalled();
    expect(store.newSessionFolderId).toBeNull();
  });

  it('uses the remembered conversation base folder for shortcut-created sessions', () => {
    const store = useWorkspaceStore();

    store.setConversationBaseFolder('folder-course');
    store.newSession();

    expect(store.newSessionFolderId).toBe('folder-course');

    store.newSession(null);
    expect(store.newSessionFolderId).toBeNull();
  });

  it('polls knowledge jobs and updates the latest assistant anchors in place', async () => {
    vi.useFakeTimers();
    vi.mocked(api.askStream).mockImplementation(
      async (
        _question: string,
        _sessionId: string | undefined,
        _conversationModel: any,
        _answerStyleId: string | undefined,
        _strategyAgentId: string | undefined,
        callbacks?: { onChunk?: (delta: string) => void }
      ) => {
        callbacks?.onChunk?.('assistant ');
        callbacks?.onChunk?.('reply');
        return {
          action: {
            action_type: 'answer',
            selected_node_ids: [],
            draft_requests: [],
            user_visible_reason: 'done',
          },
          answer: {
            summary: 'summary',
            detail: 'detail',
            references: [],
            symbols: {},
            symbol_conflicts: [],
            assistant_text: 'assistant reply',
            knowledge_job_id: 'job-1',
            anchors: [
              {
                anchor_id: 'anchor-1',
                label: 'Resolving anchor',
                status: 'pending',
              },
            ],
          },
          drafts: [],
          created_node_ids: [],
          session: {
            session_id: 'chat-1',
            branch: {
              active_node_ids: [],
              summary_node_ids: [],
              active_symbols: {},
            },
            messages: [
              {
                message_id: 'msg_user_1',
                role: 'user',
                content: 'Explain the proof.',
                assistant_context: { referenced_node_ids: [], symbol_conflicts: [], alignment_notes: [] },
                created_at: '2026-04-02T09:00:00Z',
              },
              {
                message_id: 'msg_assistant_1',
                role: 'assistant',
                content: 'assistant reply',
                assistant_context: {
                  referenced_node_ids: [],
                  symbol_conflicts: [],
                  alignment_notes: [],
                  anchors: [
                    {
                      anchor_id: 'anchor-1',
                      label: 'Resolving anchor',
                      status: 'pending',
                    },
                  ],
                },
                created_at: '2026-04-02T09:00:01Z',
              },
            ],
          } as any,
        } as any;
      }
    );
    vi.mocked(api.getKnowledgeJob)
      .mockResolvedValueOnce({
        job_id: 'job-1',
        status: 'pending',
        anchors: [
          {
            anchor_id: 'anchor-1',
            label: 'Resolving anchor',
            status: 'pending',
          },
        ],
      } as any)
      .mockResolvedValueOnce({
        job_id: 'job-1',
        status: 'ready',
        anchors: [
          {
            anchor_id: 'anchor-1',
            label: 'Resolving anchor',
            status: 'ready',
            node_id: 'node-42',
          },
        ],
      } as any);
    vi.mocked(api.getSessions).mockResolvedValue([] as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;

    await store.ask('Explain the proof.');
    await Promise.resolve();

    expect(store.currentSession?.messages.at(-1)?.assistant_context.anchors?.[0]).toMatchObject({
      anchor_id: 'anchor-1',
      status: 'pending',
    });

    await vi.advanceTimersByTimeAsync(19_000);
    expect(api.getKnowledgeJob).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1_100);
    await Promise.resolve();

    expect(api.getKnowledgeJob).toHaveBeenCalledWith('job-1');
    expect(api.getKnowledgeJob).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5_000);
    await Promise.resolve();

    expect(api.getKnowledgeJob).toHaveBeenCalledTimes(2);
    expect(store.currentSession?.messages.at(-1)?.assistant_context.anchors?.[0]).toMatchObject({
      anchor_id: 'anchor-1',
      status: 'ready',
      node_id: 'node-42',
    });

    vi.useRealTimers();
  });

  it('reports failed knowledge jobs and stops polling them', async () => {
    vi.useFakeTimers();
    vi.mocked(api.askStream).mockResolvedValue({
      action: {
        action_type: 'answer',
        selected_node_ids: [],
        draft_requests: [],
        user_visible_reason: 'done',
      },
      answer: {
        summary: 'summary',
        detail: 'detail',
        references: [],
        symbols: {},
        symbol_conflicts: [],
        assistant_text: 'assistant reply',
        knowledge_job_id: 'job-1',
        anchors: [
          {
            anchor_id: 'anchor-1',
            label: 'Linear Algebra',
            status: 'pending',
          },
        ],
      },
      drafts: [],
      created_node_ids: [],
      session: {
        session_id: 'chat-1',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        messages: [
          {
            message_id: 'msg_assistant_1',
            role: 'assistant',
            content: 'assistant reply',
            assistant_context: {
              referenced_node_ids: [],
              symbol_conflicts: [],
              alignment_notes: [],
              anchors: [
                {
                  anchor_id: 'anchor-1',
                  label: 'Linear Algebra',
                  status: 'pending',
                },
              ],
            },
            created_at: '2026-04-02T09:00:01Z',
          },
        ],
      },
    } as any);
    vi.mocked(api.getKnowledgeJob).mockResolvedValue({
      job_id: 'job-1',
      status: 'failed',
      error_message: 'provider unavailable',
      anchors: [
        {
          anchor_id: 'anchor-1',
          label: 'Linear Algebra',
          status: 'failed',
        },
      ],
    } as any);
    vi.mocked(api.getSessions).mockResolvedValue([] as any);

    const store = useWorkspaceStore();

    await store.ask('Explain linear algebra.');
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(19_000);

    expect(api.getKnowledgeJob).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1_100);
    await Promise.resolve();

    expect(store.currentSession?.messages.at(-1)?.assistant_context.anchors?.[0]).toMatchObject({
      anchor_id: 'anchor-1',
      status: 'failed',
    });
    expect(store.errorMessage).toBe('Knowledge note failed to save: provider unavailable');
    expect(api.getKnowledgeJob).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  it('accepts suggested drafts and starts knowledge job polling', async () => {
    vi.useFakeTimers();
    vi.mocked(api.compileSuggestedDrafts).mockResolvedValue({
      job_id: 'job-1',
      status: 'queued',
      anchors: [
        {
          anchor_id: 'kernel',
          label: 'Kernel',
          status: 'pending',
        },
      ],
    } as any);
    vi.mocked(api.getAgentState).mockResolvedValue({
      current_turn: null,
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        profile_context_summary: null,
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any);
    vi.mocked(api.getKnowledgeJob).mockResolvedValue({
      job_id: 'job-1',
      status: 'completed',
      anchors: [
        {
          anchor_id: 'kernel',
          label: 'Kernel',
          status: 'ready',
          node_id: 'kernel',
        },
      ],
    } as any);
    vi.mocked(api.getSession).mockResolvedValue({
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [
        {
          message_id: 'msg-a',
          role: 'assistant',
          content: '核刻画了线性映射失去的信息。[K1]',
          assistant_context: {
            referenced_node_ids: ['kernel'],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [
              {
                anchor_id: 'kernel',
                label: 'Kernel',
                status: 'ready',
                node_id: 'kernel',
              },
            ],
            orchestration_plan: {
              route: 'draft_first_then_answer',
              authorization: { status: 'approved' },
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any);
    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [
        {
          message_id: 'msg-a',
          role: 'assistant',
          content: 'answer',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
            orchestration_plan: {
              route: 'ask_before_persist',
              candidate_drafts: [
                { title: 'Kernel', draft_type: 'definition', reason: 'Needed.' },
              ],
              authorization: { status: 'pending' },
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any;

    await store.acceptSuggestedDrafts('msg-a', [1]);

    expect(api.compileSuggestedDrafts).toHaveBeenCalledWith('chat-1', 'msg-a', [1]);
    expect(store.currentSession?.messages[0].assistant_context.anchors?.[0]).toMatchObject({
      anchor_id: 'kernel',
      status: 'pending',
    });

    await vi.advanceTimersByTimeAsync(20_000);
    await Promise.resolve();

    expect(api.getKnowledgeJob).toHaveBeenCalledWith('job-1');
    expect(store.currentSession?.messages[0].assistant_context.anchors?.[0]).toMatchObject({
      anchor_id: 'kernel',
      status: 'ready',
      node_id: 'kernel',
    });
    expect(api.getSession).toHaveBeenCalledWith('chat-1');
    expect(store.currentSession?.messages[0].content).toBe(
      '核刻画了线性映射失去的信息。[K1]'
    );
    expect(store.currentSession?.messages[0].assistant_context.referenced_node_ids).toEqual([
      'kernel',
    ]);
    expect(api.getOutline).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  it('rejects a pending knowledge write and refreshes the message state', async () => {
    vi.mocked(api.rejectSuggestedDrafts).mockResolvedValue({
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [
        {
          message_id: 'msg-a',
          role: 'assistant',
          content: 'answer',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
            orchestration_plan: {
              route: 'ask_before_persist',
              intent: 'definition',
              persistence_decision: 'await_approval',
              confidence: 0.7,
              user_visible_summary: '发现知识缺口。',
              detected_scope_ids: [],
              profile_layers_used: [],
              candidate_drafts: [],
              strategy_mode: 'raw',
              strategy_reason: '',
              knowledge_scope_label: '全部知识',
              authorization: {
                mode: 'require_approval',
                status: 'denied',
                risk_level: 'medium',
                operation: 'write_knowledge_nodes',
                reason: '需要审批。',
              },
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any);
    vi.mocked(api.getAgentState).mockResolvedValue({
      current_turn: null,
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any);
    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any;

    await store.rejectSuggestedDrafts('msg-a');

    expect(api.rejectSuggestedDrafts).toHaveBeenCalledWith('chat-1', 'msg-a');
    expect(
      store.currentSession?.messages[0].assistant_context.orchestration_plan?.authorization?.status
    ).toBe('denied');
    expect(store.knowledgeApprovalBusyMessageIds).toEqual([]);
  });

  it('updates the draft question through setDraftQuestion', () => {
    const store = useWorkspaceStore();

    store.setDraftQuestion('What is compactness?');

    expect(store.draftQuestion).toBe('What is compactness?');
  });

  it('generates knowledge from a chat selection and selects the ready node', async () => {
    vi.mocked(api.compileSelectionKnowledge).mockResolvedValue({
      job_id: 'job-99',
      status: 'completed',
      anchors: [
        {
          anchor_id: 'anchor-99',
          label: 'Compactness',
          status: 'ready',
          node_id: 'node-99',
        },
      ],
    } as any);
    vi.mocked(api.getKnowledgeJob).mockResolvedValue({
      job_id: 'job-99',
      status: 'completed',
      anchors: [
        {
          anchor_id: 'anchor-99',
          label: 'Compactness',
          status: 'ready',
          node_id: 'node-99',
        },
      ],
    } as any);
    vi.mocked(api.getOutline).mockResolvedValue([
      {
        id: 'node-99',
        title: 'Compactness',
        type: 'definition',
        summary: 'Compactness summary',
        status: 'ready',
      },
    ] as any);
    vi.mocked(api.getNode).mockResolvedValue({
      id: 'node-99',
      title: 'Compactness',
      type: 'definition',
      summary: 'Compactness summary',
      detail: 'Compactness detail',
      source: 'generated',
      references: [],
      incoming_references: [],
      related_session_ids: [],
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
      status: 'ready',
      symbols: {},
    } as any);

    const store = useWorkspaceStore();
    store.selectedProviderProfile = {
      provider_type: 'openai_compatible',
      credential_id: 'openai-main',
      model: 'gpt-5.1',
      base_url: 'https://example.com/v1',
    } as any;
    store.currentSession = {
      session_id: 'chat-current',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;

    await store.generateKnowledgeFromSelection(
      {
        text: 'compactness',
        sourceType: 'chat-message',
        sessionId: 'chat-1',
        messageId: 'msg-1',
      },
      'definition'
    );

    expect(api.compileSelectionKnowledge).toHaveBeenCalledWith({
      selected_text: 'compactness',
      prompt_kind: 'definition',
      source: {
        type: 'chat-message',
        session_id: 'chat-1',
        message_id: 'msg-1',
      },
      conversation_model: {
        provider_type: 'openai_compatible',
        credential_id: 'openai-main',
        model: 'gpt-5.1',
      },
    });
    expect(api.getKnowledgeJob).toHaveBeenCalledWith('job-99');
    expect(api.getOutline).toHaveBeenCalledTimes(1);
    expect(api.getNode).toHaveBeenCalledWith('node-99');
    expect(store.currentNode?.id).toBe('node-99');
    expect(store.errorMessage).toBeNull();
  });

  it('keeps polling standalone selection jobs while they are running and selects the ready node', async () => {
    vi.useFakeTimers();
    vi.mocked(api.compileSelectionKnowledge).mockResolvedValue({
      job_id: 'job-101',
      status: 'queued',
      anchors: [
        {
          anchor_id: 'anchor-101',
          label: 'Compactness',
          status: 'pending',
        },
      ],
    } as any);
    vi.mocked(api.getKnowledgeJob)
      .mockResolvedValueOnce({
        job_id: 'job-101',
        status: 'running',
        anchors: [
          {
            anchor_id: 'anchor-101',
            label: 'Compactness',
            status: 'pending',
          },
        ],
      } as any)
      .mockResolvedValueOnce({
        job_id: 'job-101',
        status: 'completed',
        anchors: [
          {
            anchor_id: 'anchor-101',
            label: 'Compactness',
            status: 'ready',
            node_id: 'node-101',
          },
        ],
      } as any);
    vi.mocked(api.getOutline).mockResolvedValue([
      {
        id: 'node-101',
        title: 'Compactness',
        type: 'definition',
        summary: 'Compactness summary',
        status: 'ready',
      },
    ] as any);
    vi.mocked(api.getNode).mockResolvedValue({
      id: 'node-101',
      title: 'Compactness',
      type: 'definition',
      summary: 'Compactness summary',
      detail: 'Compactness detail',
      source: 'generated',
      references: [],
      incoming_references: [],
      related_session_ids: [],
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
      status: 'ready',
      symbols: {},
    } as any);

    const store = useWorkspaceStore();
    store.selectedProviderProfile = {
      provider_type: 'openai_compatible',
      credential_id: 'openai-main',
      model: 'gpt-5.1',
      base_url: 'https://example.com/v1',
    } as any;

    const selectionPromise = store.generateKnowledgeFromSelection(
      {
        text: 'compactness',
        sourceType: 'chat-message',
        sessionId: 'chat-1',
        messageId: 'msg-1',
      },
      'definition'
    );

    await Promise.resolve();
    expect(api.getKnowledgeJob).toHaveBeenCalledWith('job-101');
    expect(api.getKnowledgeJob).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(5_000);
    await Promise.resolve();

    await selectionPromise;

    expect(api.getKnowledgeJob).toHaveBeenCalledTimes(2);
    expect(api.getNode).toHaveBeenCalledWith('node-101');
    expect(store.currentNode?.id).toBe('node-101');
    expect(store.errorMessage).toBeNull();

    vi.useRealTimers();
  });

  it('generates knowledge from a knowledge node selection using the payload node id and selected provider profile', async () => {
    vi.mocked(api.compileSelectionKnowledge).mockResolvedValue({
      job_id: 'job-100',
      status: 'completed',
      anchors: [
        {
          anchor_id: 'anchor-100',
          label: 'Compactness',
          status: 'ready',
          node_id: 'node-100',
        },
      ],
    } as any);
    vi.mocked(api.getKnowledgeJob).mockResolvedValue({
      job_id: 'job-100',
      status: 'completed',
      anchors: [
        {
          anchor_id: 'anchor-100',
          label: 'Compactness',
          status: 'ready',
          node_id: 'node-100',
        },
      ],
    } as any);
    vi.mocked(api.getOutline).mockResolvedValue([
      {
        id: 'node-100',
        title: 'Compactness',
        type: 'definition',
        summary: 'Compactness summary',
        status: 'ready',
      },
    ] as any);
    vi.mocked(api.getNode).mockResolvedValue({
      id: 'node-100',
      title: 'Compactness',
      type: 'definition',
      summary: 'Compactness summary',
      detail: 'Compactness detail',
      source: 'generated',
      references: [],
      incoming_references: [],
      related_session_ids: [],
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
      status: 'ready',
      symbols: {},
    } as any);

    const store = useWorkspaceStore();
    store.selectedProviderProfile = {
      provider_type: 'openai_compatible',
      credential_id: 'openai-main',
      model: 'gpt-5.1',
      base_url: 'https://example.com/v1',
    } as any;
    store.currentNode = {
      id: 'node-current',
      title: 'Current node',
      type: 'definition',
      summary: 'Current summary',
      detail: 'Current detail',
      source: 'generated',
      references: [],
      incoming_references: [],
      related_session_ids: [],
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
      status: 'ready',
      symbols: {},
    } as any;

    await store.generateKnowledgeFromSelection(
      {
        text: 'compactness',
        sourceType: 'knowledge-node',
        nodeId: 'node-77',
      },
      'definition'
    );

    expect(api.compileSelectionKnowledge).toHaveBeenCalledWith({
      selected_text: 'compactness',
      prompt_kind: 'definition',
      source: {
        type: 'knowledge-node',
        node_id: 'node-77',
      },
      conversation_model: {
        provider_type: 'openai_compatible',
        credential_id: 'openai-main',
        model: 'gpt-5.1',
      },
    });
    expect(api.getKnowledgeJob).toHaveBeenCalledWith('job-100');
    expect(api.getNode).toHaveBeenCalledWith('node-100');
    expect(store.currentNode?.id).toBe('node-100');
    expect(store.errorMessage).toBeNull();
  });

  it('ignores stale standalone selection jobs after a newer selection starts', async () => {
    vi.useFakeTimers();
    const oldJob = deferred<any>();
    vi.mocked(api.compileSelectionKnowledge)
      .mockResolvedValueOnce({
        job_id: 'job-old',
        status: 'queued',
        anchors: [],
      } as any)
      .mockResolvedValueOnce({
        job_id: 'job-new',
        status: 'queued',
        anchors: [],
      } as any);
    vi.mocked(api.getKnowledgeJob)
      .mockImplementationOnce(() => oldJob.promise)
      .mockResolvedValueOnce({
        job_id: 'job-new',
        status: 'completed',
        anchors: [
          {
            anchor_id: 'anchor-new',
            label: 'Fresh node',
            status: 'ready',
            node_id: 'node-new',
          },
        ],
      } as any);
    vi.mocked(api.getOutline).mockResolvedValue([
      {
        id: 'node-new',
        title: 'Fresh node',
        type: 'definition',
        summary: 'Fresh summary',
        status: 'ready',
      },
    ] as any);
    vi.mocked(api.getNode).mockResolvedValue({
      id: 'node-new',
      title: 'Fresh node',
      type: 'definition',
      summary: 'Fresh summary',
      detail: 'Fresh detail',
      source: 'generated',
      references: [],
      incoming_references: [],
      related_session_ids: [],
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
      status: 'ready',
      symbols: {},
    } as any);

    const store = useWorkspaceStore();
    store.selectedProviderProfile = {
      provider_type: 'openai_compatible',
      credential_id: 'openai-main',
      model: 'gpt-5.1',
      base_url: 'https://example.com/v1',
    } as any;

    const firstSelection = store.generateKnowledgeFromSelection(
      {
        text: 'old selection',
        sourceType: 'knowledge-node',
        nodeId: 'node-old',
      },
      'definition'
    );

    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(20_000);
    await Promise.resolve();

    const secondSelection = store.generateKnowledgeFromSelection(
      {
        text: 'new selection',
        sourceType: 'knowledge-node',
        nodeId: 'node-fresh',
      },
      'definition'
    );

    await Promise.resolve();
    oldJob.resolve({
      job_id: 'job-old',
      status: 'completed',
      anchors: [
        {
          anchor_id: 'anchor-old',
          label: 'Old node',
          status: 'ready',
          node_id: 'node-old',
        },
      ],
    } as any);
    await Promise.resolve();

    await vi.advanceTimersByTimeAsync(20_000);
    await Promise.resolve();

    await Promise.all([firstSelection, secondSelection]);

    expect(api.getNode).toHaveBeenCalledWith('node-new');
    expect(api.getNode).not.toHaveBeenCalledWith('node-old');
    expect(store.currentNode?.id).toBe('node-new');

    vi.useRealTimers();
  });

  it('rejects selection drafts with explicit source ids before compiling', async () => {
    const store = useWorkspaceStore();
    store.selectedProviderProfile = {
      provider_type: 'openai_compatible',
      credential_id: 'openai-main',
      model: 'gpt-5.1',
      base_url: 'https://example.com/v1',
    } as any;
    store.currentSession = {
      session_id: 'chat-current',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;
    store.currentNode = {
      id: 'node-current',
      title: 'Current node',
      type: 'definition',
      summary: 'Current summary',
      detail: 'Current detail',
      source: 'generated',
      references: [],
      incoming_references: [],
      related_session_ids: [],
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
      status: 'ready',
      symbols: {},
    } as any;

    await store.generateKnowledgeFromSelection(
      {
        text: 'compactness',
        sourceType: 'chat-message',
        messageId: 'msg-1',
      },
      'definition'
    );

    expect(api.compileSelectionKnowledge).not.toHaveBeenCalled();
    expect(store.errorMessage).toBe('Failed to start knowledge note generation.');

    store.errorMessage = null;
    vi.mocked(api.compileSelectionKnowledge).mockClear();

    await store.generateKnowledgeFromSelection(
      {
        text: 'compactness',
        sourceType: 'knowledge-node',
      },
      'definition'
    );

    expect(api.compileSelectionKnowledge).not.toHaveBeenCalled();
    expect(store.errorMessage).toBe('Failed to start knowledge note generation.');
  });

  it('surfaces selection compile failures and terminal job failures', async () => {
    vi.mocked(api.compileSelectionKnowledge)
      .mockRejectedValueOnce(new Error('compile failed'))
      .mockResolvedValueOnce({
        job_id: 'job-200',
        status: 'queued',
        anchors: [],
      } as any);
    vi.mocked(api.getKnowledgeJob).mockResolvedValue({
      job_id: 'job-200',
      status: 'failed',
      error_message: 'provider unavailable',
      anchors: [
        {
          anchor_id: 'anchor-200',
          label: 'Compactness',
          status: 'failed',
        },
      ],
    } as any);

    const store = useWorkspaceStore();
    store.selectedProviderProfile = {
      provider_type: 'openai_compatible',
      credential_id: 'openai-main',
      model: 'gpt-5.1',
      base_url: 'https://example.com/v1',
    } as any;

    await store.generateKnowledgeFromSelection(
      {
        text: 'compactness',
        sourceType: 'chat-message',
        sessionId: 'chat-1',
        messageId: 'msg-1',
      },
      'definition'
    );

    expect(store.errorMessage).toBe('Failed to start knowledge note generation.');

    store.errorMessage = null;

    await store.generateKnowledgeFromSelection(
      {
        text: 'compactness',
        sourceType: 'chat-message',
        sessionId: 'chat-2',
        messageId: 'msg-2',
      },
      'definition'
    );

    expect(api.getKnowledgeJob).toHaveBeenCalledWith('job-200');
    expect(store.errorMessage).toBe('Knowledge note failed to save: provider unavailable');
  });

  it('exposes a user-visible error message and preserves session state when ask fails', async () => {
    vi.mocked(api.askStream).mockRejectedValue(new Error('provider down'));

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;

    await store.ask('Explain the proof.');

    expect(store.errorMessage).toBe('Failed to send message. Check your provider settings and try again.');
    expect(store.loading).toBe(false);
    expect(store.currentSession?.session_id).toBe('chat-1');
  });

  it('cancels an in-flight answer and restores the question for retry', async () => {
    vi.mocked(api.cancelAsk).mockResolvedValue(undefined);
    vi.mocked(api.askStream).mockImplementation(
      async (_question, _sessionId, _model, _style, _strategy, callbacks) =>
        new Promise((_, reject) => {
          callbacks?.signal?.addEventListener('abort', () => {
            const error = new Error('aborted');
            error.name = 'AbortError';
            reject(error);
          });
        })
    );
    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;

    const pendingAsk = store.ask('Explain the proof.');
    expect(store.askInFlight).toBe(true);

    store.cancelAsk();
    await pendingAsk;

    expect(api.cancelAsk).toHaveBeenCalledTimes(1);
    expect(store.askInFlight).toBe(false);
    expect(store.errorMessage).toBe('Generation stopped.');
    expect(store.draftQuestion).toBe('Explain the proof.');
    expect(store.currentSession?.session_id).toBe('chat-1');
  });

  it('clears the ask error message on a successful retry', async () => {
    vi.mocked(api.askStream)
      .mockRejectedValueOnce(new Error('provider down'))
      .mockResolvedValueOnce({
        action: {
          action_type: 'answer',
          selected_node_ids: [],
          draft_requests: [],
          user_visible_reason: 'done',
        },
        answer: {
          summary: 'summary',
          detail: 'detail',
          references: [],
          symbols: {},
          symbol_conflicts: [],
          assistant_text: 'assistant reply',
        },
        drafts: [],
        created_node_ids: [],
        session: {
          session_id: 'chat-1',
          branch: {
            active_node_ids: [],
            summary_node_ids: [],
            active_symbols: {},
          },
          messages: [],
        } as any,
      } as any);
    vi.mocked(api.getSessions).mockResolvedValue([] as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;

    await store.ask('Explain the proof.');
    expect(store.errorMessage).toBe('Failed to send message. Check your provider settings and try again.');

    await store.ask('Explain the proof again.');

    expect(store.errorMessage).toBeNull();
    expect(store.currentSession?.session_id).toBe('chat-1');
  });

  it('regenerates the last assistant message without creating a new round', async () => {
    vi.mocked(api.regenerate).mockResolvedValue({
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'msg_user_1',
          role: 'user',
          content: 'Explain the proof.',
          assistant_context: { referenced_node_ids: [], symbol_conflicts: [], alignment_notes: [] },
          created_at: '2026-04-02T09:00:00Z',
        },
        {
          message_id: 'msg_assistant_2',
          role: 'assistant',
          content: 'Regenerated answer',
          assistant_context: { referenced_node_ids: [], symbol_conflicts: [], alignment_notes: [] },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any);
    vi.mocked(api.getSessions).mockResolvedValue([] as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'msg_user_1',
          role: 'user',
          content: 'Explain the proof.',
          assistant_context: { referenced_node_ids: [], symbol_conflicts: [], alignment_notes: [] },
          created_at: '2026-04-02T09:00:00Z',
        },
        {
          message_id: 'msg_assistant_1',
          role: 'assistant',
          content: 'Original answer',
          assistant_context: { referenced_node_ids: [], symbol_conflicts: [], alignment_notes: [] },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any;
    store.selectedProviderProfile = {
      provider_type: 'gemini',
      model: 'gemini-3-flash-preview',
      credential_id: 'gemini-main',
    } as any;
    store.selectedAnswerStyleId = 'rigorous';
    await store.regenerate('msg_assistant_1');

    expect(api.regenerate).toHaveBeenCalledWith(
      'chat-1',
      'msg_assistant_1',
      'rigorous'
    );
    expect(store.currentSession?.messages).toHaveLength(2);
    expect(store.currentSession?.messages[1].content).toBe('Regenerated answer');
  });

  it('deletes the current session and refreshes the list', async () => {
    vi.mocked(api.getSessions).mockResolvedValue([
      {
        session_id: 'chat-2',
        title: 'Kept session',
        icon: 'atom',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        message_count: 0,
        branch_depth: 0,
        child_session_ids: [],
      },
    ] as any);
    vi.mocked(api.deleteSession).mockResolvedValue();

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Delete me',
      icon: 'sigma',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;

    await store.deleteSession('chat-1');

    expect(api.deleteSession).toHaveBeenCalledWith('chat-1');
    expect(store.currentSession).toBeNull();
    expect(store.sessions[0]?.session_id).toBe('chat-2');
  });

  it('updates the current session icon in place', async () => {
    vi.mocked(api.getSessionExplorer).mockResolvedValue({ scope: 'sessions', tree: [] });
    vi.mocked(api.updateSession).mockResolvedValue({
      session_id: 'chat-1',
      title: 'Operator Theory',
      icon: 'wave',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Operator Theory',
      icon: 'sigma',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [],
    } as any;
    store.sessions = [
      {
        session_id: 'chat-1',
        title: 'Operator Theory',
        icon: 'sigma',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        message_count: 0,
        branch_depth: 0,
        child_session_ids: [],
      },
    ] as any;

    await store.updateSessionIcon('chat-1', 'wave');

    expect(api.updateSession).toHaveBeenCalledWith('chat-1', { icon: 'wave' });
    expect(store.currentSession?.icon).toBe('wave');
    expect(store.sessions[0]?.icon).toBe('wave');
  });

  it('renames the current session and refreshes the explorer title', async () => {
    vi.mocked(api.getSessionExplorer).mockResolvedValue({ scope: 'sessions', tree: [] });
    vi.mocked(api.updateSession).mockResolvedValue({
      session_id: 'chat-1',
      title: 'Spectral foundations',
      icon: 'sigma',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any);
    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Old title',
      icon: 'sigma',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any;
    store.sessions = [{ session_id: 'chat-1', title: 'Old title' }] as any;

    await store.renameSession('chat-1', 'Spectral foundations');

    expect(api.updateSession).toHaveBeenCalledWith('chat-1', { title: 'Spectral foundations' });
    expect(store.currentSession?.title).toBe('Spectral foundations');
    expect(store.sessions[0]?.title).toBe('Spectral foundations');
    expect(api.getSessionExplorer).toHaveBeenCalledTimes(1);
  });

  it('fetches agent state for the current session', async () => {
    vi.mocked(api.getAgentState).mockResolvedValue({
      current_turn: {
        session_id: 'chat-1',
        message_id: 'msg-a',
        route: 'answer_then_suggest_drafts',
        intent: 'broad_overview',
        confidence: 0.78,
        persistence_decision: 'suggest_drafts',
        user_visible_summary: '先给概览。',
        detected_scope_ids: ['linear-algebra'],
        profile_layers_used: ['global_user', 'scope_memory:linear-algebra'],
        profile_context_summary: '识别为线性代数范围。',
        active_node_ids: [],
        candidate_drafts: [],
      },
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: ['linear-algebra'],
        profile_layers_used: ['global_user', 'scope_memory:linear-algebra'],
        profile_context_summary: '识别为线性代数范围。',
        has_global_user_profile: true,
        has_scope_memory: true,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any;

    await store.fetchAgentState();

    expect(api.getAgentState).toHaveBeenCalledWith('chat-1');
    expect(store.agentState?.current_turn?.route).toBe('answer_then_suggest_drafts');
  });

  it('keeps the latest agent state when session changes between fetches', async () => {
    const first = deferred<any>();
    const second = deferred<any>();
    vi.mocked(api.getAgentState)
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-old',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any;

    const firstFetch = store.fetchAgentState('chat-old');

    store.currentSession = {
      session_id: 'chat-new',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any;

    const secondFetch = store.fetchAgentState('chat-new');

    second.resolve({
      current_turn: {
        session_id: 'chat-new',
        message_id: 'msg-new',
        route: 'answer',
        intent: 'current',
        confidence: 1,
        persistence_decision: 'none',
        user_visible_summary: 'new',
        detected_scope_ids: [],
        profile_layers_used: [],
        active_node_ids: [],
        candidate_drafts: [],
      },
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        profile_context_summary: null,
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any);
    await secondFetch;

    first.resolve({
      current_turn: {
        session_id: 'chat-old',
        message_id: 'msg-old',
        route: 'answer_then_suggest_drafts',
        intent: 'stale',
        confidence: 0.1,
        persistence_decision: 'suggest_drafts',
        user_visible_summary: 'old',
        detected_scope_ids: [],
        profile_layers_used: [],
        active_node_ids: [],
        candidate_drafts: [],
      },
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        profile_context_summary: null,
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any);
    await firstFetch;

    expect(store.agentState?.current_turn?.session_id).toBe('chat-new');
    expect(store.agentState?.current_turn?.route).toBe('answer');
  });

  it('stores the focused agent message when opening agent state for a message', async () => {
    vi.mocked(api.getAgentState).mockResolvedValue({
      current_turn: null,
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        profile_context_summary: null,
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any);

    const store = useWorkspaceStore();
    store.currentSession = {
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any;

    store.openAgentStateForMessage('msg-focus');

    expect((store as any).focusedAgentMessageId).toBe('msg-focus');
    expect(store.activeTab).toBe('agent');
    expect(api.getAgentState).toHaveBeenCalledWith('chat-1');
  });
});
