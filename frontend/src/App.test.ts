import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('./components/chat/ChatMessage.vue', () => ({
  default: {
    name: 'ChatMessage',
    props: ['message', 'assistantName', 'canRegenerate', 'isLoading'],
    emits: ['regenerate', 'anchor-click'],
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
        <button
          v-for="anchor in (message.assistant_context?.anchors || [])"
          :key="anchor.anchor_id"
          :data-anchor-id="anchor.anchor_id"
          :disabled="anchor.status !== 'ready' || !anchor.node_id"
          @click="$emit('anchor-click', anchor)"
        >
          {{ anchor.label }}
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
    props: ['isExpanded'],
    emits: ['toggle-expanded'],
    template: `
      <button
        data-stub="reader-panel"
        :data-expanded="isExpanded ? 'true' : 'false'"
        @click="$emit('toggle-expanded')"
      >
        Reader
      </button>
    `,
  },
}));

import App from './App.vue';
import { useWorkspaceStore } from './stores/workspace';

describe('App new session flow', () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
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

    await wrapper.get('button[title="New Conversation"]').trigger('click');

    expect(store.currentSession).toBeNull();
    expect(wrapper.text()).toContain('Session Tree');
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

    expect(wrapper.text()).toContain('Session Tree');
    expect(wrapper.find('[data-sidebar-new-conversation]').exists()).toBe(false);
    expect(wrapper.findAll('button').filter((button) => button.text().includes('New Conversation'))).toHaveLength(0);

    await wrapper.get('[data-explorer-primary-action]').trigger('click');

    expect(newSessionSpy).toHaveBeenCalledTimes(1);
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
    expect(wrapper.text()).toContain('Book Outline');
    expect(wrapper.find('[data-explorer-create-root-folder]').exists()).toBe(true);
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

  it('shows a text-only empty chat state without starter prompt buttons', async () => {
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

    expect(wrapper.text()).toContain('Inquire of the Scriptorium');
    expect(wrapper.text()).toContain(
      'Ask for a proof, a derivation, or a physical intuition. Our synthesis engines are at your service.'
    );
    expect(wrapper.text()).not.toContain('Begin Inquiry');
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

  it('routes anchor clicks from the latest assistant message to the reader store', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);
    const selectNodeSpy = vi.spyOn(store, 'selectNode').mockResolvedValue(undefined);

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
            anchors: [
              {
                anchor_id: 'anchor-1',
                label: 'Resolved node',
                status: 'ready',
                node_id: 'node-42',
              },
            ],
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

    const anchorButton = wrapper.get('[data-anchor-id="anchor-1"]');
    await anchorButton.trigger('click');

    expect(selectNodeSpy).toHaveBeenCalledWith('node-42');
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
    expect(wrapper.text()).toContain('Updating');
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

    expect(transcript.classes()).toEqual(expect.arrayContaining(['p-8', 'space-y-4']));
    expect(transcript.classes()).not.toContain('p-12');
    expect(transcript.classes()).not.toContain('space-y-12');
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

  it('toggles the right reader panel width from the reader action rail', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    mockStartupFetches(store);

    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
      },
    });

    const panel = () => wrapper.get('[data-reader-panel-shell]');
    const reader = () => wrapper.get('[data-stub="reader-panel"]');

    expect(panel().classes()).toContain('w-[520px]');
    expect(reader().attributes('data-expanded')).toBe('false');

    await reader().trigger('click');

    expect(panel().classes()).toContain('w-[780px]');
    expect(reader().attributes('data-expanded')).toBe('true');

    await reader().trigger('click');

    expect(panel().classes()).toContain('w-[520px]');
    expect(reader().attributes('data-expanded')).toBe('false');
  });
});
