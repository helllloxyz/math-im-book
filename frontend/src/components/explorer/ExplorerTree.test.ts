import { describe, expect, it } from 'vitest';
import { DOMWrapper, mount } from '@vue/test-utils';

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
        scope_id: 'scope-linear-algebra',
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
    expect(wrapper.get('[data-explorer-scope-root="true"]').classes()).toContain('explorer-tree-scope-root');
    expect(wrapper.get('[data-explorer-scope-mark]').text()).toBe('adjust');
    expect(wrapper.find('.explorer-tree-icon').exists()).toBe(false);
    expect(wrapper.find('[data-explorer-item="linear-map"]').classes()).toContain('tree-item-active');

    await wrapper.get('[data-explorer-folder-toggle="folder-1"]').trigger('click');
    expect(wrapper.text()).not.toContain('Linear Map');
  });

  it('keeps only the folder selected when a folder row is clicked', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: 'linear-map',
      },
    });

    expect(wrapper.get('[data-explorer-item="linear-map"]').classes()).toContain('tree-item-active');
    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    expect(wrapper.text()).not.toContain('Linear Map');
    expect(wrapper.get('[data-explorer-folder="folder-1"]').classes()).toContain('tree-folder-active');
    expect(wrapper.get('[data-explorer-folder="folder-1"]').attributes('aria-selected')).toBe('true');

    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    expect(wrapper.text()).toContain('Linear Map');
    expect(wrapper.get('[data-explorer-item="linear-map"]').classes()).not.toContain('tree-item-active');
    expect(wrapper.get('[data-explorer-item="linear-map"]').attributes('aria-selected')).toBe('false');
  });

  it('clears a selected scope folder when the blank tree area is clicked', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
        title: 'Conversations',
      },
    });

    const scopeFolder = wrapper.get('[data-explorer-folder="folder-1"]');
    await scopeFolder.trigger('click');
    expect(scopeFolder.classes()).toContain('tree-folder-active');
    expect(scopeFolder.attributes('aria-selected')).toBe('true');

    await wrapper.get('[data-explorer-background]').trigger('click');
    expect(scopeFolder.classes()).not.toContain('tree-folder-active');
    expect(scopeFolder.attributes('aria-selected')).toBe('false');
    expect(wrapper.get('[data-explorer-root-select]').classes()).toContain('is-root-active');
  });

  it('selects a file exclusively and uses its containing folder as the create base', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
        primaryActionTitle: 'New inquiry',
      },
    });

    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    await wrapper.get('[data-explorer-item="linear-map"]').trigger('click');

    expect(wrapper.get('[data-explorer-folder="folder-1"]').classes()).not.toContain('tree-folder-active');
    expect(wrapper.get('[data-explorer-item="linear-map"]').classes()).toContain('tree-item-active');
    expect(wrapper.get('[data-explorer-item="linear-map"]').attributes('aria-selected')).toBe('true');

    await wrapper.get('[data-explorer-primary-action]').trigger('click');

    expect(wrapper.emitted('primary-action')?.[0]).toEqual(['folder-1']);
  });

  it('emits select and create-folder actions', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
      },
    });

    await wrapper.get('[data-explorer-item="linear-map"]').trigger('click');
    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    await wrapper.get('[data-explorer-create-folder]').trigger('click');
    const body = new DOMWrapper(document.body);
    await body.get('[data-explorer-name-input]').setValue('Vector spaces');
    await body.get('.explorer-dialog').trigger('submit');

    expect(wrapper.emitted('select-item')?.[0]).toEqual(['knowledge_node', 'linear-map']);
    expect(wrapper.emitted('create-folder')?.[0]).toEqual(['folder-1', 'Vector spaces']);
  });

  it('emits root create-folder from the tree toolbar', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree: [],
        currentItemId: null,
      },
    });

    await wrapper.get('[data-explorer-create-folder]').trigger('click');
    const body = new DOMWrapper(document.body);
    await body.get('[data-explorer-name-input]').setValue('Inbox');
    await body.get('.explorer-dialog').trigger('submit');

    expect(wrapper.emitted('create-folder')?.[0]).toEqual([null, 'Inbox']);
  });

  it('filters titles and summaries while preserving matching folder context', async () => {
    const wrapper = mount(ExplorerTree, {
      props: { tree, currentItemId: null },
    });

    await wrapper.get('[data-explorer-search]').setValue('linear map');
    expect(wrapper.text()).toContain('Linear Algebra');
    expect(wrapper.text()).toContain('Linear Map');

    await wrapper.get('[data-explorer-search]').setValue('topology');
    expect(wrapper.find('[data-explorer-empty]').text()).toContain('No results');
  });

  it('renames folders and prevents deleting non-empty folders', async () => {
    const wrapper = mount(ExplorerTree, {
      props: { tree, currentItemId: null },
    });

    await wrapper.get('[data-explorer-folder-menu="folder-1"]').trigger('click');
    expect(wrapper.get('[data-explorer-folder-menu="folder-1"] .material-symbols-outlined').text()).toBe('more_vert');
    await wrapper.get('[data-explorer-rename-folder="folder-1"]').trigger('click');
    const body = new DOMWrapper(document.body);
    await body.get('[data-explorer-name-input]').setValue('Foundations');
    await body.get('.explorer-dialog').trigger('submit');
    expect(wrapper.emitted('rename-folder')?.[0]).toEqual(['folder-1', 'Foundations']);

    await wrapper.get('[data-explorer-folder-menu="folder-1"]').trigger('click');
    await wrapper.get('[data-explorer-delete-folder="folder-1"]').trigger('click');
    expect(body.get('[data-explorer-confirm-delete]').attributes('disabled')).toBeDefined();
    expect(body.text()).toContain('Move them elsewhere');
  });

  it('offers a keyboard and touch friendly move dialog', async () => {
    const wrapper = mount(ExplorerTree, {
      props: { tree: treeWithDropTarget, currentItemId: null },
    });

    await wrapper.get('[data-explorer-item-menu="linear-map"]').trigger('click');
    await wrapper.get('[data-explorer-move-item="linear-map"]').trigger('click');
    const body = new DOMWrapper(document.body);
    await body.get('[data-explorer-move-select]').setValue('folder-2');
    await body.get('form[aria-labelledby="move-item-title"]').trigger('submit');

    expect(wrapper.emitted('move-item')?.[0]).toEqual([
      'knowledge_node',
      'linear-map',
      'folder-2',
    ]);
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

    const categoryIcon = wrapper.find('[data-explorer-item-icon="chat-1"]');
    expect(categoryIcon.element.tagName).toBe('IMG');
    expect(categoryIcon.attributes('data-math-category')).toBe('discrete-combinatorics');
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
    await wrapper.get('[data-session-icon-option="applied-modeling"]').trigger('click');

    expect(wrapper.emitted('update-session-icon')?.[0]).toEqual(['chat-1', 'applied-modeling']);
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

    const categoryIcon = wrapper.get('[data-explorer-item-icon="linear-map"]');
    expect(categoryIcon.element.tagName).toBe('IMG');
    expect(categoryIcon.attributes('data-math-category')).toBe('general');

    await wrapper.get('[data-item-icon-trigger="linear-map"]').trigger('click');
    await wrapper.get('[data-item-icon-option="group-theory"]').trigger('click');

    expect(wrapper.emitted('update-item-icon')?.[0]).toEqual(['knowledge_node', 'linear-map', 'group-theory']);
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

    expect(wrapper.emitted('primary-action')?.[0]).toEqual([null]);
  });

  it('targets the selected folder from the unified create menu', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
        primaryActionTitle: 'New inquiry',
      },
    });

    await wrapper.get('[data-explorer-folder="folder-1"]').trigger('click');
    await wrapper.get('[data-explorer-primary-action]').trigger('click');

    expect(wrapper.emitted('primary-action')?.[0]).toEqual(['folder-1']);
  });

  it('clears the selection from blank space and creates at the top level', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: 'linear-map',
        primaryActionTitle: 'New inquiry',
      },
    });

    expect(wrapper.get('[data-explorer-item="linear-map"]').classes()).toContain('tree-item-active');
    await wrapper.get('[data-explorer-background]').trigger('click');
    expect(wrapper.get('[data-explorer-item="linear-map"]').classes()).not.toContain('tree-item-active');
    expect(wrapper.emitted('base-folder-change')?.at(-1)).toEqual([null]);

    await wrapper.get('[data-explorer-primary-action]').trigger('click');
    expect(wrapper.emitted('primary-action')?.[0]).toEqual([null]);

    await wrapper.get('[data-explorer-create-folder]').trigger('click');
    const body = new DOMWrapper(document.body);
    await body.get('[data-explorer-name-input]').setValue('Top-level folder');
    await body.get('form[aria-labelledby="create-folder-title"]').trigger('submit');

    expect(wrapper.emitted('create-folder')?.[0]).toEqual([null, 'Top-level folder']);
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
