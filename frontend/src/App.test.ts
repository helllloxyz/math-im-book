import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('./components/chat/ChatMessage.vue', () => ({
  default: {
    name: 'ChatMessage',
    props: ['message', 'assistantName', 'canRegenerate', 'isLoading', 'sessionId', 'agentSteps', 'approvalBusy'],
    emits: ['regenerate', 'approve-knowledge', 'reject-knowledge'],
    template: `
      <div
        data-stub="chat-message"
        :data-assistant-name="message.role === 'assistant' ? assistantName : undefined"
        :data-loading="isLoading ? 'true' : 'false'"
      >
        <button
          v-if="canRegenerate"
          data-stub="regenerate"
          @click="$emit('regenerate', message.message_id)"
        >
          {{ message.message_id }}
        </button>
      </div>
    `,
  },
}));

vi.mock('./components/chat/ModelSettings.vue', () => ({
  default: {
    name: 'ModelSettings',
    template: '<div data-stub="model-settings"></div>',
  },
}));

vi.mock('./components/explorer/GlobalSettings.vue', () => ({
  default: {
    name: 'GlobalSettings',
    template: '<div data-stub="global-settings"></div>',
  },
}));

vi.mock('./components/reader/ReaderPanel.vue', () => ({
  default: {
    name: 'ReaderPanel',
    props: {
      isExpanded: Boolean,
      pageMode: Boolean,
    },
    emits: ['toggle-expanded', 'close'],
    template: `
      <div>
        <button
          data-stub="reader-panel"
          :data-expanded="isExpanded ? 'true' : 'false'"
          :data-page-mode="pageMode ? 'true' : 'false'"
          @click="$emit('toggle-expanded')"
        >
          Reader
        </button>
        <button data-stub="close-reader" @click="$emit('close')">Close</button>
      </div>
    `,
  },
}));

import App from './App.vue';
import { useWorkspaceStore } from './stores/workspace';

describe('App new session flow', () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
    window.history.replaceState({}, '', '/');
  });

  function mockStartupFetches(store: ReturnType<typeof useWorkspaceStore>) {
    vi.spyOn(store, 'fetchProviderOptions').mockResolvedValue(undefined);
    vi.spyOn(store, 'fetchStrategyAgents').mockResolvedValue(undefined);
    vi.spyOn(store, 'fetchAnswerStyles').mockResolvedValue(undefined);
    vi.spyOn(store, 'fetchSessions').mockResolvedValue(undefined);
    vi.spyOn(store, 'fetchOutline').mockResolvedValue(undefined);
    vi.spyOn(store, 'fetchCredentials').mockResolvedValue(undefined);
  }

  it('clears the current session when the new conversation button is clicked', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.sessions = [
      {
        session_id: 'chat-1',
        title: 'Current session',
        icon: 'sigma',
        branch: {
          active_node_ids: [],
          summary_node_ids: [],
          active_symbols: {},
        },
        message_count: 1,
        branch_depth: 0,
        child_session_ids: [],
      },
    ] as any;
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Current session',
      icon: 'sigma',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'msg_0001',
          role: 'user',
          content: 'hello',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:00Z',
        },
      ],
    } as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-explorer-create-menu]').trigger('click');
    await wrapper.get('[data-explorer-primary-action]').trigger('click');

    expect(store.currentSession).toBeNull();
    expect(wrapper.text()).toContain('Conversations');
  });

  it('uses the chat sidebar header as the new conversation action', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    const newSessionSpy = vi.spyOn(store, 'newSession');

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.text()).toContain('Conversations');
    expect(wrapper.find('[data-sidebar-new-conversation]').exists()).toBe(false);
    expect(wrapper.findAll('button').filter((button) => button.text().includes('New Conversation'))).toHaveLength(0);

    await wrapper.get('[data-explorer-create-menu]').trigger('click');
    await wrapper.get('[data-explorer-primary-action]').trigger('click');

    expect(newSessionSpy).toHaveBeenCalledWith(null);
  });

  it('uses the explorer tree header as the library sidebar context label', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.activeTab = 'book';

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.find('[data-sidebar-context-label]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Library');
    expect(wrapper.find('[data-explorer-create-menu]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Knowledge Explorer');
  });

  it('fetches startup metadata on mount and keeps the composer style selector optional', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.answerStyles = [
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
    ] as any;
    store.selectedAnswerStyleId = null as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    expect(store.fetchStrategyAgents).toHaveBeenCalledTimes(1);
    expect(store.fetchAnswerStyles).toHaveBeenCalledTimes(1);
    expect(wrapper.get('select[aria-label="Answer style"]')).toBeTruthy();
    expect(wrapper.get('select[aria-label="Answer style"]').element).toHaveProperty('value', '');

    await wrapper.get('select[aria-label="Answer style"]').setValue('rigorous');

    expect(store.selectedAnswerStyleId).toBe('rigorous');
  });

  it('shows a focused empty state with useful starter prompts', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.currentSession = null;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.text()).toContain('Start with a question.');
    expect(wrapper.text()).toContain(
      'Ask for a proof, unpack an intuition, or check a derivation.'
    );
    await wrapper.get('[aria-label="Example questions"] button').trigger('click');
    expect(store.draftQuestion).toBe('Explain the core intuition before the formal proof.');
  });

  it('routes regenerate from the latest assistant message to the store', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    const regenerateSpy = vi.spyOn(store, 'regenerate').mockResolvedValue(undefined);

    store.currentSession = {
      session_id: 'chat-1',
      title: 'Current session',
      icon: 'sigma',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'msg_user_1',
          role: 'user',
          content: 'first question',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:00Z',
        },
        {
          message_id: 'msg_assistant_1',
          role: 'assistant',
          content: 'first answer',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
        {
          message_id: 'msg_user_2',
          role: 'user',
          content: 'second question',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:02Z',
        },
        {
          message_id: 'msg_assistant_2',
          role: 'assistant',
          content: 'second answer',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:03Z',
        },
      ],
    } as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    const regenerateButtons = wrapper.findAll('[data-stub="regenerate"]');
    expect(regenerateButtons).toHaveLength(1);
    await regenerateButtons[0].trigger('click');

    expect(regenerateSpy).toHaveBeenCalledWith('msg_assistant_2');
  });

  it('loads a linked knowledge node on its dedicated page', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    window.history.replaceState({}, '', '/?view=knowledge&session=chat-1&node=node-42');
    const selectSessionSpy = vi.spyOn(store, 'selectSession').mockResolvedValue(undefined);
    const selectNodeSpy = vi.spyOn(store, 'selectNode').mockResolvedValue(undefined);

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    await vi.waitFor(() => expect(selectNodeSpy).toHaveBeenCalledWith('node-42'));
    expect(selectSessionSpy).toHaveBeenCalledWith('chat-1');
    expect(store.activeTab).toBe('knowledge');
    expect(wrapper.get('[data-stub="reader-panel"]').attributes('data-page-mode')).toBe('true');
  });

  it('creates a linked fork in the new workspace and replaces the one-shot URL', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    window.history.replaceState(
      {},
      '',
      '/?view=fork&session=chat-1&message=msg-assistant-1'
    );

    const sourceSession = {
      session_id: 'chat-1',
      title: 'Source conversation',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [],
    } as any;
    const forkedSession = {
      ...sourceSession,
      session_id: 'chat-2',
      title: 'Forked conversation',
    } as any;
    const selectSessionSpy = vi.spyOn(store, 'selectSession').mockImplementation(async () => {
      store.currentSession = sourceSession;
    });
    const forkSpy = vi.spyOn(store, 'fork').mockImplementation(async () => {
      store.currentSession = forkedSession;
    });

    mount(App, { global: { plugins: [pinia] } });

    await vi.waitFor(() => expect(forkSpy).toHaveBeenCalledWith('msg-assistant-1'));
    const resolvedUrl = new URL(window.location.href);
    expect(selectSessionSpy).toHaveBeenCalledWith('chat-1');
    expect(resolvedUrl.searchParams.get('view')).toBe('conversation');
    expect(resolvedUrl.searchParams.get('session')).toBe('chat-2');
    expect(resolvedUrl.searchParams.has('message')).toBe(false);
    expect(store.activeTab).toBe('chat');
  });

  it('does not expose regenerate controls for non-latest assistant messages', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Current session',
      icon: 'sigma',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'msg_user_1',
          role: 'user',
          content: 'first question',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:00Z',
        },
        {
          message_id: 'msg_assistant_1',
          role: 'assistant',
          content: 'first answer',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
        {
          message_id: 'msg_user_2',
          role: 'user',
          content: 'second question',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:02Z',
        },
      ],
    } as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.findAll('[data-stub="regenerate"]')).toHaveLength(0);
  });

  it('keeps the chat visible while a new conversation response is preparing', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.loading = true;
    store.sessions = [];
    store.outline = [];
    store.currentSession = {
      session_id: undefined,
      title: undefined,
      icon: undefined,
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'local-user-1',
          role: 'user',
          content: 'derive something',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:00Z',
        },
        {
          message_id: 'streaming-assistant',
          role: 'assistant',
          content: '',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.find('.loading-overlay').exists()).toBe(false);
    expect(wrapper.text()).toContain('Thinking');
  });

  it('keeps the chat transcript spacing compact', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Current session',
      icon: 'sigma',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'msg_user_1',
          role: 'user',
          content: 'first question',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:00Z',
        },
        {
          message_id: 'msg_assistant_1',
          role: 'assistant',
          content: 'first answer',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    const transcript = wrapper.get('[data-chat-transcript]');

    expect(transcript.classes()).toContain('conversation-transcript');
  });

  it('loads linked response details at the top of a new workspace', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    window.history.replaceState(
      {},
      '',
      '/?view=details&session=chat-1&message=msg_assistant_1'
    );
    const selectSessionSpy = vi.spyOn(store, 'selectSession').mockResolvedValue(undefined);
    vi.spyOn(store, 'fetchAgentState').mockResolvedValue(undefined);
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Current session',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [
        {
          message_id: 'msg_assistant_1',
          role: 'assistant',
          content: 'A long answer',
          assistant_context: { referenced_node_ids: [], symbol_conflicts: [], alignment_notes: [] },
          created_at: '2026-04-02T09:00:01Z',
        },
      ],
    } as any;

    const wrapper = mount(App, { global: { plugins: [pinia] } });
    const scroll = wrapper.get('.workspace-scroll').element as HTMLElement;
    scroll.scrollTop = 420;

    await vi.waitFor(() => expect(store.activeTab).toBe('agent'));

    expect(selectSessionSpy).toHaveBeenCalledWith('chat-1');
    expect(store.focusedAgentMessageId).toBe('msg_assistant_1');
    expect(scroll.scrollTop).toBe(0);
  });

  it('uses one assistant persona name for every assistant message in a session', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.loading = true;
    store.currentSession = {
      session_id: 'chat-1',
      title: 'Current session',
      icon: 'sigma',
      branch: {
        active_node_ids: [],
        summary_node_ids: [],
        active_symbols: {},
      },
      messages: [
        {
          message_id: 'msg_user_1',
          role: 'user',
          content: 'derive something',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:00Z',
        },
        {
          message_id: 'msg_assistant_1',
          role: 'assistant',
          content: 'first answer',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
        {
          message_id: 'msg_user_2',
          role: 'user',
          content: 'continue',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:02Z',
        },
        {
          message_id: 'streaming-assistant',
          role: 'assistant',
          content: '',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:03Z',
        },
      ],
    } as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    const assistantMessages = wrapper.findAll('[data-assistant-name]');
    const assistantNames = assistantMessages.map((message) => message.attributes('data-assistant-name'));

    expect(assistantMessages).toHaveLength(2);
    expect(new Set(assistantNames).size).toBe(1);
    expect(assistantNames[0]).toMatch(/Gauss|Noether|Euler|Riemann|Hypatia|Newton|Lagrange|Fourier/);
    expect(assistantMessages[0].attributes('data-loading')).toBe('false');
    expect(assistantMessages[1].attributes('data-loading')).toBe('true');
  });

  it('does not show a side reader merely because a node exists in chat state', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    store.currentNode = { id: 'node-1', title: 'A note' } as any;

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.find('[data-reader-panel-shell]').exists()).toBe(false);
    expect(wrapper.find('[data-stub="reader-panel"]').exists()).toBe(false);
  });

  it('renders the node reader only in the dedicated knowledge view', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);

    store.currentNode = { id: 'node-1', title: 'A note' } as any;
    store.activeTab = 'knowledge';
    const wrapper = mount(App, { global: { plugins: [pinia] } });

    expect(wrapper.find('[data-reader-panel-shell]').exists()).toBe(false);
    expect(wrapper.get('[data-stub="reader-panel"]').attributes('data-page-mode')).toBe('true');
  });
});
