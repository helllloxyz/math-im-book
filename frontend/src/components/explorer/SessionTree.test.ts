import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

import SessionTree from './SessionTree.vue';
import { useWorkspaceStore } from '../../stores/workspace';

describe('SessionTree', () => {
  const dataTransfer = () => {
    const values = new Map<string, string>();
    return {
      dropEffect: '',
      effectAllowed: '',
      setData: (key: string, value: string) => values.set(key, value),
      getData: (key: string) => values.get(key) || '',
    };
  };

  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
    Object.defineProperty(window, 'prompt', {
      value: vi.fn(() => 'Course'),
      configurable: true,
    });
  });

  it('renders session explorer rows and selects a session', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.sessionExplorerTree = [
      {
        kind: 'item',
        item: {
          item_type: 'session',
          item_id: 'chat-1',
          session_id: 'chat-1',
          title: 'Spectral Theorem',
          icon: 'sigma',
          message_count: 3,
        },
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
    ] as any;
    store.currentSession = { session_id: 'chat-1', messages: [], branch: {} } as any;
    const selectSpy = vi.spyOn(store, 'selectSession').mockResolvedValue(undefined);

    const wrapper = mount(SessionTree, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.text()).toContain('Spectral Theorem');
    expect(wrapper.find('[data-explorer-item="chat-1"]').classes()).toContain('tree-item-active');

    await wrapper.get('[data-explorer-item="chat-1"]').trigger('click');
    expect(selectSpy).toHaveBeenCalledWith('chat-1');
  });

  it('starts a new conversation from the session tree header', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    const newSessionSpy = vi.spyOn(store, 'newSession');

    const wrapper = mount(SessionTree, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-explorer-primary-action]').trigger('click');

    expect(newSessionSpy).toHaveBeenCalledTimes(1);
  });

  it('updates session icons from the row picker', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.sessionExplorerTree = [
      {
        kind: 'item',
        item: {
          item_type: 'session',
          item_id: 'chat-1',
          session_id: 'chat-1',
          title: 'Spectral Theorem',
          icon: 'sigma',
        },
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
    ] as any;
    const updateIconSpy = vi.spyOn(store, 'updateSessionIcon').mockResolvedValue(undefined);

    const wrapper = mount(SessionTree, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-session-icon-trigger="chat-1"]').trigger('click');
    await wrapper.get('[data-session-icon-option="atom"]').trigger('click');

    expect(updateIconSpy).toHaveBeenCalledWith('chat-1', 'atom');
  });

  it('creates a child session folder from folder rows', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.sessionExplorerTree = [
      {
        kind: 'folder',
        folder: {
          folder_id: 'folder-1',
          scope: 'sessions',
          name: 'Course',
          parent_folder_id: null,
          created_at: '',
          updated_at: '',
          sort_order: 1000,
        },
        children: [],
      },
    ] as any;
    const createSpy = vi.spyOn(store, 'createExplorerFolder').mockResolvedValue(undefined);

    const wrapper = mount(SessionTree, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-explorer-create-folder="folder-1"]').trigger('click');

    expect(createSpy).toHaveBeenCalledWith('sessions', 'Course', 'folder-1');
  });

  it('moves a session to a dropped folder id', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.sessionExplorerTree = [
      {
        kind: 'item',
        item: { item_type: 'session', item_id: 'chat-1', title: 'Spectral Theorem' },
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
      {
        kind: 'folder',
        folder: {
          folder_id: 'folder-1',
          scope: 'sessions',
          name: 'Course',
          parent_folder_id: null,
          created_at: '',
          updated_at: '',
          sort_order: 1000,
        },
        children: [],
      },
    ] as any;
    const moveSpy = vi.spyOn(store, 'moveExplorerItem').mockResolvedValue(undefined);

    const wrapper = mount(SessionTree, {
      global: {
        plugins: [pinia],
      },
    });
    const transfer = dataTransfer();

    await wrapper.get('[data-explorer-item="chat-1"]').trigger('dragstart', {
      dataTransfer: transfer,
    });
    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('drop', {
      dataTransfer: transfer,
    });

    expect(moveSpy).toHaveBeenCalledWith('session', 'chat-1', 'folder-1');
  });
});
