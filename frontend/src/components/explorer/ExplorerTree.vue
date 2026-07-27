<template>
  <div class="explorer-tree">
    <div
      class="explorer-tree-header"
      :class="{ 'explorer-tree-drop-target': dragOverRoot }"
      data-explorer-root-drop
      @dragenter.prevent="dragOverRoot = true"
      @dragover.prevent="handleRootDragOver"
      @dragleave="dragOverRoot = false"
      @drop.prevent="handleRootDrop"
    >
      <h3 v-if="title" class="explorer-tree-title">{{ title }}</h3>
      <div class="explorer-tree-header-actions">
        <button
          v-if="primaryActionTitle"
          type="button"
          class="explorer-tree-header-action"
          data-explorer-primary-action
          :title="primaryActionTitle"
          @click="emit('primary-action')"
        >
          <span class="material-symbols-outlined text-[16px]">{{ primaryActionIcon || 'add_box' }}</span>
        </button>
        <button
          type="button"
          class="explorer-tree-header-action"
          data-explorer-create-root-folder
          :title="rootActionTitle || 'New folder'"
          @click="emit('create-folder', null)"
        >
          <span class="material-symbols-outlined text-[16px]">create_new_folder</span>
        </button>
      </div>
    </div>
    <ExplorerTreeRow
      v-for="node in tree"
      :key="nodeKey(node)"
      :node="node"
      :depth="0"
      :current-item-id="currentItemId"
      :editable-session-icons="editableSessionIcons"
      :editable-item-icons="editableItemIcons"
      @select-item="handleSelectItem"
      @create-folder="handleCreateFolder"
      @move-item="handleMoveItem"
      @update-session-icon="handleUpdateSessionIcon"
      @update-item-icon="handleUpdateItemIcon"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, ref } from 'vue';
import type { ExplorerItemType, ExplorerTreeNode } from '../../services/api';

defineProps<{
  tree: ExplorerTreeNode[];
  currentItemId?: string | null;
  title?: string;
  rootActionTitle?: string;
  primaryActionTitle?: string;
  primaryActionIcon?: string;
  editableSessionIcons?: boolean;
  editableItemIcons?: boolean;
}>();

const emit = defineEmits<{
  (event: 'select-item', itemType: ExplorerItemType, itemId: string): void;
  (event: 'create-folder', parentFolderId: string | null): void;
  (event: 'move-item', itemType: ExplorerItemType, itemId: string, folderId: string | null): void;
  (event: 'primary-action'): void;
  (event: 'update-session-icon', sessionId: string, icon: string): void;
  (event: 'update-item-icon', itemType: ExplorerItemType, itemId: string, icon: string): void;
}>();

const EXPLORER_DRAG_MIME = 'application/x-math-im-book-explorer-item';
const dragOverRoot = ref(false);
const sessionIconChoices = [
  { id: 'function', iconName: 'functions' },
  { id: 'sigma', iconName: 'calculate' },
  { id: 'matrix', iconName: 'grid_on' },
  { id: 'triangle', iconName: 'change_history' },
  { id: 'atom', iconName: 'science' },
  { id: 'wave', iconName: 'water' },
  { id: 'orbit', iconName: 'all_inclusive' },
] as const;
const sessionIconNameMap: Record<string, string> =
  Object.fromEntries(sessionIconChoices.map((icon) => [icon.id, icon.iconName]));

interface DraggedExplorerItem {
  itemType: ExplorerItemType;
  itemId: string;
}

const nodeKey = (node: ExplorerTreeNode) =>
  node.kind === 'folder'
    ? `folder:${node.folder?.folder_id}`
    : `item:${node.location?.item_type}:${node.location?.item_id || node.item?.item_id}`;

const handleSelectItem = (itemType: ExplorerItemType, itemId: string) => {
  emit('select-item', itemType, itemId);
};

const handleCreateFolder = (parentFolderId: string | null) => {
  emit('create-folder', parentFolderId);
};

const handleMoveItem = (itemType: ExplorerItemType, itemId: string, folderId: string | null) => {
  emit('move-item', itemType, itemId, folderId);
};

const handleUpdateSessionIcon = (sessionId: string, icon: string) => {
  emit('update-session-icon', sessionId, icon);
};

const handleUpdateItemIcon = (itemType: ExplorerItemType, itemId: string, icon: string) => {
  emit('update-item-icon', itemType, itemId, icon);
};

const writeDraggedItem = (event: DragEvent, itemType: ExplorerItemType, itemId: string) => {
  const payload = JSON.stringify({ itemType, itemId });
  event.dataTransfer?.setData(EXPLORER_DRAG_MIME, payload);
  event.dataTransfer?.setData('text/plain', payload);
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
  }
};

const readDraggedItem = (event: DragEvent): DraggedExplorerItem | null => {
  const raw =
    event.dataTransfer?.getData(EXPLORER_DRAG_MIME) ||
    event.dataTransfer?.getData('text/plain');
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<DraggedExplorerItem>;
    if (
      (parsed.itemType === 'session' || parsed.itemType === 'knowledge_node') &&
      typeof parsed.itemId === 'string' &&
      parsed.itemId
    ) {
      return { itemType: parsed.itemType, itemId: parsed.itemId };
    }
  } catch {
    return null;
  }
  return null;
};

const handleRootDragOver = (event: DragEvent) => {
  dragOverRoot.value = true;
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move';
  }
};

const handleRootDrop = (event: DragEvent) => {
  dragOverRoot.value = false;
  const dragged = readDraggedItem(event);
  if (!dragged) return;
  emit('move-item', dragged.itemType, dragged.itemId, null);
};

const itemTitle = (node: ExplorerTreeNode) =>
  String(node.item?.title || node.item?.session_id || node.item?.id || node.item?.item_id || 'Untitled');

const itemId = (node: ExplorerTreeNode) =>
  String(node.location?.item_id || node.item?.item_id || node.item?.session_id || node.item?.id || '');

const itemType = (node: ExplorerTreeNode): ExplorerItemType =>
  (node.location?.item_type || node.item?.item_type || 'knowledge_node') as ExplorerItemType;

const itemIcon = (node: ExplorerTreeNode) => {
  const customIcon = sessionIconNameMap[String(node.item?.icon || '')];
  if (customIcon) return customIcon;
  if (itemType(node) === 'session') {
    return 'functions';
  }
  const type = String(node.item?.type || '').toLowerCase();
  if (type === 'definition') return 'data_object';
  if (type === 'theorem') return 'account_tree';
  if (type === 'proof') return 'functions';
  return 'article';
};

const ExplorerTreeRow: any = defineComponent({
  name: 'ExplorerTreeRow',
  props: {
    node: { type: Object as () => ExplorerTreeNode, required: true },
    depth: { type: Number, required: true },
    currentItemId: { type: String, required: false },
    editableSessionIcons: { type: Boolean, default: false },
    editableItemIcons: { type: Boolean, default: false },
  },
  emits: ['select-item', 'create-folder', 'move-item', 'update-session-icon', 'update-item-icon'],
  setup(props, { emit }): () => any {
    const expanded = ref(true);
    const iconPickerOpen = ref(false);
    const folderId = computed(() => props.node.folder?.folder_id || null);
    const currentItemId = computed(() => itemId(props.node));
    const isActive = computed(
      () => props.node.kind === 'item' && props.currentItemId === currentItemId.value
    );
    const paddingLeft = computed(() => `${props.depth * 14 + 6}px`);
    const dragOverFolder = ref(false);
    const toggleFolder = () => {
      expanded.value = !expanded.value;
    };
    const handleKeyboardAction = (event: KeyboardEvent, action: () => void) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      action();
    };

    return () => {
      if (props.node.kind === 'folder') {
        const id = folderId.value;
        return h('div', { class: 'explorer-tree-group' }, [
          h(
            'div',
            {
              class: [
                'explorer-tree-row explorer-tree-folder',
                dragOverFolder.value ? 'explorer-tree-drop-target' : '',
              ],
              style: { paddingLeft: paddingLeft.value },
              'data-explorer-folder': id,
              role: 'button',
              tabindex: 0,
              'aria-expanded': expanded.value ? 'true' : 'false',
              onClick: toggleFolder,
              onKeydown: (event: KeyboardEvent) => handleKeyboardAction(event, toggleFolder),
              onDragenter: (event: DragEvent) => {
                event.preventDefault();
                event.stopPropagation();
                dragOverFolder.value = true;
              },
              onDragover: (event: DragEvent) => {
                event.preventDefault();
                event.stopPropagation();
                dragOverFolder.value = true;
                if (event.dataTransfer) {
                  event.dataTransfer.dropEffect = 'move';
                }
              },
              onDragleave: () => {
                dragOverFolder.value = false;
              },
              onDrop: (event: DragEvent) => {
                event.preventDefault();
                event.stopPropagation();
                dragOverFolder.value = false;
                const dragged = readDraggedItem(event);
                if (!dragged || !id) return;
                emit('move-item', dragged.itemType, dragged.itemId, id);
              },
            },
            [
              h(
                'button',
                {
                  type: 'button',
                  class: 'explorer-tree-toggle',
                  'data-explorer-folder-toggle': id,
                  onClick: (event: MouseEvent) => {
                    event.stopPropagation();
                    toggleFolder();
                  },
                },
                [
                  h(
                    'span',
                    { class: 'material-symbols-outlined text-[15px]' },
                    expanded.value ? 'expand_more' : 'chevron_right'
                  ),
                ]
              ),
              h('span', { class: 'material-symbols-outlined explorer-tree-icon' }, expanded.value ? 'folder_open' : 'folder'),
              h('span', { class: 'explorer-tree-label' }, props.node.folder?.name || 'Untitled'),
              h(
                'button',
                {
                  type: 'button',
                  class: 'explorer-tree-action',
                  'data-explorer-create-folder': id,
                  title: 'New folder',
                  onClick: (event: MouseEvent) => {
                    event.stopPropagation();
                    emit('create-folder', id);
                  },
                },
                [h('span', { class: 'material-symbols-outlined text-[14px]' }, 'create_new_folder')]
              ),
            ]
          ),
          expanded.value &&
            h(
              'div',
              { class: 'explorer-tree-children' },
              props.node.children.map((child) =>
                h(ExplorerTreeRow as any, {
                  key: nodeKey(child),
                  node: child,
                  depth: props.depth + 1,
                  currentItemId: props.currentItemId,
                  editableSessionIcons: props.editableSessionIcons,
                  editableItemIcons: props.editableItemIcons,
                  onSelectItem: (type: ExplorerItemType, id: string) => emit('select-item', type, id),
                  onCreateFolder: (id: string | null) => emit('create-folder', id),
                  onMoveItem: (type: ExplorerItemType, id: string, folderId: string | null) =>
                    emit('move-item', type, id, folderId),
                  onUpdateSessionIcon: (id: string, icon: string) =>
                    emit('update-session-icon', id, icon),
                  onUpdateItemIcon: (type: ExplorerItemType, id: string, icon: string) =>
                    emit('update-item-icon', type, id, icon),
                })
              )
            ),
        ]);
      }

      const selectItem = () => emit('select-item', itemType(props.node), currentItemId.value);
      const isSessionItem = itemType(props.node) === 'session';
      const canEditIcon =
        props.editableItemIcons || (props.editableSessionIcons && isSessionItem);
      const iconTriggerAttribute = isSessionItem
        ? { 'data-session-icon-trigger': currentItemId.value }
        : { 'data-item-icon-trigger': currentItemId.value };
      const iconOptionAttribute = isSessionItem
        ? 'data-session-icon-option'
        : 'data-item-icon-option';
      const iconElement = canEditIcon
        ? h('span', { class: 'explorer-tree-icon-anchor' }, [
            h(
              'button',
              {
                type: 'button',
                class: 'explorer-tree-icon-button',
                ...iconTriggerAttribute,
                title: 'Change icon',
                onClick: (event: MouseEvent) => {
                  event.stopPropagation();
                  iconPickerOpen.value = !iconPickerOpen.value;
                },
              },
              [
                h(
                  'span',
                  {
                    class: 'material-symbols-outlined explorer-tree-icon',
                    'data-explorer-item-icon': currentItemId.value,
                  },
                  itemIcon(props.node)
                ),
              ]
            ),
            iconPickerOpen.value &&
              h(
                'div',
                { class: 'explorer-tree-icon-picker' },
                sessionIconChoices.map((icon) =>
                  h(
                    'button',
                    {
                      key: icon.id,
                      type: 'button',
                      class: 'explorer-tree-icon-option',
                      [iconOptionAttribute]: icon.id,
                      onClick: (event: MouseEvent) => {
                        event.stopPropagation();
                        iconPickerOpen.value = false;
                        if (isSessionItem && props.editableSessionIcons) {
                          emit('update-session-icon', currentItemId.value, icon.id);
                        } else {
                          emit('update-item-icon', itemType(props.node), currentItemId.value, icon.id);
                        }
                      },
                    },
                    [h('span', { class: 'material-symbols-outlined text-[18px]' }, icon.iconName)]
                  )
                )
              ),
          ])
        : h(
            'span',
            {
              class: 'material-symbols-outlined explorer-tree-icon',
              'data-explorer-item-icon': currentItemId.value,
            },
            itemIcon(props.node)
          );

      return h(
        'div',
        {
          class: [
            'explorer-tree-row explorer-tree-item',
            isActive.value ? 'tree-item-active' : '',
          ],
          style: { paddingLeft: paddingLeft.value },
          'data-explorer-item': currentItemId.value,
          role: 'button',
          tabindex: 0,
          draggable: true,
          onClick: selectItem,
          onKeydown: (event: KeyboardEvent) => handleKeyboardAction(event, selectItem),
          onDragstart: (event: DragEvent) => {
            writeDraggedItem(event, itemType(props.node), currentItemId.value);
          },
        },
        [
          h('span', { class: 'explorer-tree-spacer' }),
          iconElement,
          h('span', { class: 'explorer-tree-label' }, itemTitle(props.node)),
        ]
      );
    };
  },
});
</script>
