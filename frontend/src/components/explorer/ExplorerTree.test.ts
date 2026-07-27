import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';

import ExplorerTree from './ExplorerTree.vue';
import type { ExplorerTreeNode } from '../../services/api';

describe('ExplorerTree', () => {
  const dataTransfer = () => {
    const values = new Map<string, string>();
    return {
      dropEffect: '',
      effectAllowed: '',
      setData: (key: string, value: string) => values.set(key, value),
      getData: (key: string) => values.get(key) || '',
    };
  };

  const tree = [
    {
      kind: 'folder',
      folder: {
        folder_id: 'folder-1',
        scope: 'knowledge',
        name: 'Linear Algebra',
        parent_folder_id: null,
        created_at: '2026-04-19T00:00:00Z',
        updated_at: '2026-04-19T00:00:00Z',
        sort_order: 1000,
      },
      children: [
        {
          kind: 'item',
          item: {
            item_id: 'linear-map',
            id: 'linear-map',
            title: 'Linear Map',
            type: 'atomic',
          },
          location: {
            item_type: 'knowledge_node',
            item_id: 'linear-map',
            folder_id: 'folder-1',
            sort_order: 1000,
            path_cached: '/Linear Algebra/linear-map',
            location_source: 'agent',
            user_locked: false,
            updated_at: '2026-04-19T00:00:00Z',
          },
          children: [],
        },
      ],
    },
  ] satisfies ExplorerTreeNode[];

  const treeWithDropTarget = [
    ...tree,
    {
      kind: 'folder',
      folder: {
        folder_id: 'folder-2',
        scope: 'knowledge',
        name: 'Analysis',
        parent_folder_id: null,
        created_at: '2026-04-19T00:00:00Z',
        updated_at: '2026-04-19T00:00:00Z',
        sort_order: 2000,
      },
      children: [],
    },
  ] satisfies ExplorerTreeNode[];

  it('renders compact folder rows and expands items', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: 'linear-map',
      },
    });

    expect(wrapper.text()).toContain('Linear Algebra');
    expect(wrapper.text()).toContain('Linear Map');
    expect(wrapper.find('[data-explorer-folder="folder-1"]').exists()).toBe(true);
    expect(wrapper.find('[data-explorer-item="linear-map"]').classes()).toContain('tree-item-active');

    await wrapper.get('[data-explorer-folder-toggle="folder-1"]').trigger('click');
    expect(wrapper.text()).not.toContain('Linear Map');
  });

  it('toggles folders from the full folder row', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
      },
    });

    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    expect(wrapper.text()).not.toContain('Linear Map');

    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    expect(wrapper.text()).toContain('Linear Map');
  });

  it('emits select and create-folder actions', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
      },
    });

    await wrapper.get('[data-explorer-item="linear-map"]').trigger('click');
    await wrapper.get('[data-explorer-create-folder="folder-1"]').trigger('click');

    expect(wrapper.emitted('select-item')?.[0]).toEqual(['knowledge_node', 'linear-map']);
    expect(wrapper.emitted('create-folder')?.[0]).toEqual(['folder-1']);
  });

  it('emits root create-folder from the tree toolbar', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree: [],
        currentItemId: null,
      },
    });

    await wrapper.get('[data-explorer-create-root-folder]').trigger('click');

    expect(wrapper.emitted('create-folder')?.[0]).toEqual([null]);
  });

  it('uses stored session icons for session rows', () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree: [
          {
            kind: 'item',
            item: {
              item_type: 'session',
              item_id: 'chat-1',
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
              updated_at: '2026-04-19T00:00:00Z',
            },
            children: [],
          },
        ],
        currentItemId: null,
      },
    });

    expect(wrapper.find('[data-explorer-item-icon="chat-1"]').text()).toBe('calculate');
  });

  it('emits session icon updates from the icon picker', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree: [
          {
            kind: 'item',
            item: {
              item_type: 'session',
              item_id: 'chat-1',
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
              updated_at: '2026-04-19T00:00:00Z',
            },
            children: [],
          },
        ],
        currentItemId: null,
        editableSessionIcons: true,
      },
    });

    await wrapper.get('[data-session-icon-trigger="chat-1"]').trigger('click');
    await wrapper.get('[data-session-icon-option="wave"]').trigger('click');

    expect(wrapper.emitted('update-session-icon')?.[0]).toEqual(['chat-1', 'wave']);
  });

  it('emits knowledge icon updates from the same icon picker', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree: [
          {
            kind: 'item',
            item: {
              item_type: 'knowledge_node',
              item_id: 'linear-map',
              title: 'Linear Map',
              icon: 'atom',
            },
            location: {
              item_type: 'knowledge_node',
              item_id: 'linear-map',
              folder_id: null,
              sort_order: 1000,
              path_cached: '/linear-map',
              location_source: 'system',
              user_locked: false,
              updated_at: '2026-04-19T00:00:00Z',
            },
            children: [],
          },
        ],
        currentItemId: null,
        editableItemIcons: true,
      },
    });

    expect(wrapper.find('[data-explorer-item-icon="linear-map"]').text()).toBe('science');

    await wrapper.get('[data-item-icon-trigger="linear-map"]').trigger('click');
    await wrapper.get('[data-item-icon-option="orbit"]').trigger('click');

    expect(wrapper.emitted('update-item-icon')?.[0]).toEqual(['knowledge_node', 'linear-map', 'orbit']);
  });

  it('emits the primary header action', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
        title: 'Session Tree',
        primaryActionTitle: 'New Conversation',
        primaryActionIcon: 'add_box',
      },
    });

    await wrapper.get('[data-explorer-primary-action]').trigger('click');

    expect(wrapper.emitted('primary-action')).toHaveLength(1);
  });

  it('does not render a move button on item rows', () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
      },
    });

    expect(wrapper.find('[data-explorer-move-item="linear-map"]').exists()).toBe(false);
  });

  it('emits move-item when an item is dropped on a folder', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree: treeWithDropTarget,
        currentItemId: null,
      },
    });
    const transfer = dataTransfer();

    await wrapper.get('[data-explorer-item="linear-map"]').trigger('dragstart', {
      dataTransfer: transfer,
    });
    await wrapper.get('[data-explorer-folder="folder-2"]').trigger('dragover', {
      dataTransfer: transfer,
    });
    await wrapper.get('[data-explorer-folder="folder-2"]').trigger('drop', {
      dataTransfer: transfer,
    });

    expect(wrapper.emitted('move-item')?.[0]).toEqual(['knowledge_node', 'linear-map', 'folder-2']);
  });

  it('emits move-item with a root folder when an item is dropped on the header', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
        title: 'Book Outline',
      },
    });
    const transfer = dataTransfer();

    await wrapper.get('[data-explorer-item="linear-map"]').trigger('dragstart', {
      dataTransfer: transfer,
    });
    await wrapper.get('[data-explorer-root-drop]').trigger('drop', {
      dataTransfer: transfer,
    });

    expect(wrapper.emitted('move-item')?.[0]).toEqual(['knowledge_node', 'linear-map', null]);
  });
});
