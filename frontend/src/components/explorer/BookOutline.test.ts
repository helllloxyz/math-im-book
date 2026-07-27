import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

import BookOutline from './BookOutline.vue';
import { useWorkspaceStore } from '../../stores/workspace';

describe('BookOutline', () => {
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
      value: vi.fn(() => 'Linear Algebra'),
      configurable: true,
    });
  });

  it('renders knowledge explorer rows and selects a node', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.knowledgeExplorerTree = [
      {
        kind: 'item',
        item: {
          item_type: 'knowledge_node',
          item_id: 'vector-space',
          id: 'vector-space',
          title: 'Vector Space',
          type: 'atomic',
          summary: 'A set closed under vector addition and scalar multiplication.',
          status: 'ready',
        },
        location: {
          item_type: 'knowledge_node',
          item_id: 'vector-space',
          folder_id: null,
          sort_order: 1000,
          path_cached: '/vector-space',
          location_source: 'system',
          user_locked: false,
          updated_at: '',
        },
        children: [],
      },
    ] as any;
    store.currentNode = { id: 'vector-space' } as any;
    const selectSpy = vi.spyOn(store, 'selectNode').mockResolvedValue(undefined);

    const wrapper = mount(BookOutline, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.text()).toContain('Vector Space');
    expect(wrapper.find('[data-explorer-item="vector-space"]').classes()).toContain('tree-item-active');

    await wrapper.get('[data-explorer-item="vector-space"]').trigger('click');
    expect(selectSpy).toHaveBeenCalledWith('vector-space');
  });

  it('updates knowledge icons from the row picker', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.knowledgeExplorerTree = [
      {
        kind: 'item',
        item: {
          item_type: 'knowledge_node',
          item_id: 'vector-space',
          id: 'vector-space',
          title: 'Vector Space',
          icon: 'sigma',
        },
        location: {
          item_type: 'knowledge_node',
          item_id: 'vector-space',
          folder_id: null,
          sort_order: 1000,
          path_cached: '/vector-space',
          location_source: 'system',
          user_locked: false,
          updated_at: '',
        },
        children: [],
      },
    ] as any;
    const updateIconSpy = vi.spyOn(store, 'updateExplorerItemIcon').mockResolvedValue(undefined);

    const wrapper = mount(BookOutline, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-item-icon-trigger="vector-space"]').trigger('click');
    await wrapper.get('[data-item-icon-option="wave"]').trigger('click');

    expect(updateIconSpy).toHaveBeenCalledWith('knowledge_node', 'vector-space', 'wave');
  });

  it('creates a child knowledge folder from folder rows', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.knowledgeExplorerTree = [
      {
        kind: 'folder',
        folder: {
          folder_id: 'folder-1',
          scope: 'knowledge',
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

    const wrapper = mount(BookOutline, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-explorer-create-folder="folder-1"]').trigger('click');

    expect(createSpy).toHaveBeenCalledWith('knowledge', 'Linear Algebra', 'folder-1');
  });

  it('moves a knowledge node to a dropped folder id', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.knowledgeExplorerTree = [
      {
        kind: 'item',
        item: { item_type: 'knowledge_node', item_id: 'vector-space', title: 'Vector Space' },
        location: {
          item_type: 'knowledge_node',
          item_id: 'vector-space',
          folder_id: null,
          sort_order: 1000,
          path_cached: '/vector-space',
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
          scope: 'knowledge',
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

    const wrapper = mount(BookOutline, {
      global: {
        plugins: [pinia],
      },
    });
    const transfer = dataTransfer();

    await wrapper.get('[data-explorer-item="vector-space"]').trigger('dragstart', {
      dataTransfer: transfer,
    });
    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('drop', {
      dataTransfer: transfer,
    });

    expect(moveSpy).toHaveBeenCalledWith('knowledge_node', 'vector-space', 'folder-1');
  });
});
