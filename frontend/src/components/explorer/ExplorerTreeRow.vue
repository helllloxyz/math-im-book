<template>
  <div v-if="node.kind === 'folder'" class="explorer-tree-group">
    <div
      class="explorer-tree-row explorer-tree-folder"
      :class="{
        'explorer-tree-drop-target': dragOverFolder,
        'tree-folder-active': isFolderActive,
      }"
      :style="rowIndent"
      :data-explorer-folder="folderId"
      role="button"
      tabindex="0"
      :aria-expanded="isExpanded ? 'true' : 'false'"
      :aria-selected="isFolderActive ? 'true' : 'false'"
      @click="selectAndToggleFolder"
      @keydown.enter.prevent="selectAndToggleFolder"
      @keydown.space.prevent="selectAndToggleFolder"
      @dragenter.prevent.stop="dragOverFolder = true"
      @dragover.prevent.stop="handleFolderDragOver"
      @dragleave="dragOverFolder = false"
      @drop.prevent.stop="handleFolderDrop"
    >
      <button
        type="button"
        class="explorer-tree-toggle"
        :data-explorer-folder-toggle="folderId"
        :aria-label="isExpanded ? 'Collapse folder' : 'Expand folder'"
        @click.stop="toggleFolder"
      >
        <span class="material-symbols-outlined" aria-hidden="true">
          {{ isExpanded ? 'expand_more' : 'chevron_right' }}
        </span>
      </button>
      <span class="material-symbols-outlined explorer-tree-icon" aria-hidden="true">
        {{ isExpanded ? 'folder_open' : 'folder' }}
      </span>
      <span class="explorer-tree-label">{{ node.folder?.name || 'Untitled' }}</span>
      <span class="explorer-tree-count" :aria-label="`${folderItemCount} items`">
        {{ folderItemCount }}
      </span>
      <div class="explorer-tree-menu-anchor" @click.stop>
        <button
          type="button"
          class="explorer-tree-action"
          :data-explorer-folder-menu="folderId"
          aria-label="Folder actions"
          aria-haspopup="menu"
          :aria-expanded="actionMenuOpen ? 'true' : 'false'"
          @click.stop="actionMenuOpen = !actionMenuOpen"
        >
          <span class="material-symbols-outlined" aria-hidden="true">more_horiz</span>
        </button>
        <div v-if="actionMenuOpen" class="explorer-tree-menu" role="menu">
          <button
            type="button"
            role="menuitem"
            :data-explorer-rename-folder="folderId"
            @click.stop="requestRenameFolder"
          >
            <span class="material-symbols-outlined" aria-hidden="true">edit</span>
            Rename
          </button>
          <button
            type="button"
            role="menuitem"
            class="danger"
            :data-explorer-delete-folder="folderId"
            @click.stop="requestDeleteFolder"
          >
            <span class="material-symbols-outlined" aria-hidden="true">delete_outline</span>
            Delete folder
          </button>
        </div>
      </div>
    </div>

    <div v-if="isExpanded" class="explorer-tree-children">
      <ExplorerTreeRow
        v-for="child in node.children"
        :key="nodeKey(child)"
        :node="child"
        :depth="depth + 1"
        :current-item-id="props.currentItemId"
        :selected-folder-id="selectedFolderId"
        :force-expanded="forceExpanded"
        :editable-session-icons="editableSessionIcons"
        :editable-item-icons="editableItemIcons"
        :can-rename-items="canRenameItems"
        :can-delete-items="canDeleteItems"
        @select-item="(...args) => emit('select-item', ...args)"
        @move-item="(...args) => emit('move-item', ...args)"
        @select-folder="(...args) => emit('select-folder', ...args)"
        @request-rename-folder="(...args) => emit('request-rename-folder', ...args)"
        @request-delete-folder="(...args) => emit('request-delete-folder', ...args)"
        @request-move-item="(...args) => emit('request-move-item', ...args)"
        @request-rename-item="(...args) => emit('request-rename-item', ...args)"
        @request-delete-item="(...args) => emit('request-delete-item', ...args)"
        @update-session-icon="(...args) => emit('update-session-icon', ...args)"
        @update-item-icon="(...args) => emit('update-item-icon', ...args)"
      />
    </div>
  </div>

  <div
    v-else
    class="explorer-tree-row explorer-tree-item"
    :class="{ 'tree-item-active': isActive }"
    :style="rowIndent"
    :data-explorer-item="currentItemId"
    :title="itemPath"
    role="button"
    tabindex="0"
    :aria-selected="isActive ? 'true' : 'false'"
    draggable="true"
    @click="selectItem"
    @keydown.enter.prevent="selectItem"
    @keydown.space.prevent="selectItem"
    @dragstart="handleDragStart"
  >
    <span v-if="canEditIcon" class="explorer-tree-icon-anchor" @click.stop>
      <button
        type="button"
        class="explorer-tree-icon-button"
        v-bind="iconTriggerAttribute"
        aria-label="Change icon"
        aria-haspopup="menu"
        :aria-expanded="iconPickerOpen ? 'true' : 'false'"
        @click.stop="iconPickerOpen = !iconPickerOpen"
      >
        <span
          class="material-symbols-outlined explorer-tree-icon"
          :data-explorer-item-icon="currentItemId"
          aria-hidden="true"
        >{{ itemIcon }}</span>
      </button>
      <div v-if="iconPickerOpen" class="explorer-tree-icon-picker" role="menu">
        <button
          v-for="icon in iconChoices"
          :key="icon.id"
          type="button"
          class="explorer-tree-icon-option"
          :data-session-icon-option="isSessionItem ? icon.id : undefined"
          :data-item-icon-option="!isSessionItem ? icon.id : undefined"
          :aria-label="`Use ${icon.id} icon`"
          role="menuitem"
          @click.stop="chooseIcon(icon.id)"
        >
          <span class="material-symbols-outlined" aria-hidden="true">{{ icon.iconName }}</span>
        </button>
      </div>
    </span>
    <span
      v-else
      class="material-symbols-outlined explorer-tree-icon"
      :data-explorer-item-icon="currentItemId"
      aria-hidden="true"
    >{{ itemIcon }}</span>
    <span class="explorer-tree-label">{{ itemTitle }}</span>
    <span
      v-if="knowledgeStatus && knowledgeStatus !== 'ready'"
      class="explorer-tree-status"
      :class="`is-${knowledgeStatus}`"
      :title="statusLabel"
      :aria-label="statusLabel"
    ></span>
    <span v-else-if="messageCount" class="explorer-tree-count" :aria-label="`${messageCount} messages`">
      {{ messageCount }}
    </span>
    <div class="explorer-tree-menu-anchor" @click.stop>
      <button
        type="button"
        class="explorer-tree-action"
        :data-explorer-item-menu="currentItemId"
        aria-label="Item actions"
        aria-haspopup="menu"
        :aria-expanded="actionMenuOpen ? 'true' : 'false'"
        @click.stop="actionMenuOpen = !actionMenuOpen"
      >
        <span class="material-symbols-outlined" aria-hidden="true">more_horiz</span>
      </button>
      <div v-if="actionMenuOpen" class="explorer-tree-menu" role="menu">
        <button type="button" role="menuitem" :data-explorer-move-item="currentItemId" @click.stop="requestMoveItem">
          <span class="material-symbols-outlined" aria-hidden="true">drive_file_move</span>
          Move to…
        </button>
        <button
          v-if="canRenameItems"
          type="button"
          role="menuitem"
          :data-explorer-rename-item="currentItemId"
          @click.stop="requestRenameItem"
        >
          <span class="material-symbols-outlined" aria-hidden="true">edit</span>
          Rename
        </button>
        <button
          v-if="canDeleteItems"
          type="button"
          role="menuitem"
          class="danger"
          :data-explorer-delete-item="currentItemId"
          @click.stop="requestDeleteItem"
        >
          <span class="material-symbols-outlined" aria-hidden="true">delete_outline</span>
          Delete
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import type { ExplorerItemType, ExplorerTreeNode } from '../../services/api';

defineOptions({ name: 'ExplorerTreeRow' });

const props = withDefaults(defineProps<{
  node: ExplorerTreeNode;
  depth: number;
  currentItemId?: string | null;
  selectedFolderId?: string | null;
  forceExpanded?: boolean;
  editableSessionIcons?: boolean;
  editableItemIcons?: boolean;
  canRenameItems?: boolean;
  canDeleteItems?: boolean;
}>(), {
  currentItemId: null,
  selectedFolderId: null,
  forceExpanded: false,
  editableSessionIcons: false,
  editableItemIcons: false,
  canRenameItems: false,
  canDeleteItems: false,
});

const emit = defineEmits<{
  (event: 'select-item', itemType: ExplorerItemType, itemId: string, folderId: string | null): void;
  (event: 'move-item', itemType: ExplorerItemType, itemId: string, folderId: string | null): void;
  (event: 'select-folder', folderId: string): void;
  (event: 'request-rename-folder', folderId: string, name: string): void;
  (event: 'request-delete-folder', folderId: string, name: string, itemCount: number, folderCount: number): void;
  (event: 'request-move-item', itemType: ExplorerItemType, itemId: string, title: string, folderId: string | null): void;
  (event: 'request-rename-item', itemType: ExplorerItemType, itemId: string, title: string): void;
  (event: 'request-delete-item', itemType: ExplorerItemType, itemId: string, title: string): void;
  (event: 'update-session-icon', sessionId: string, icon: string): void;
  (event: 'update-item-icon', itemType: ExplorerItemType, itemId: string, icon: string): void;
}>();

const EXPLORER_DRAG_MIME = 'application/x-math-im-book-explorer-item';
const iconChoices = [
  { id: 'function', iconName: 'functions' },
  { id: 'sigma', iconName: 'calculate' },
  { id: 'matrix', iconName: 'grid_on' },
  { id: 'triangle', iconName: 'change_history' },
  { id: 'atom', iconName: 'science' },
  { id: 'wave', iconName: 'water' },
  { id: 'orbit', iconName: 'all_inclusive' },
] as const;
const iconNameMap: Record<string, string> = Object.fromEntries(
  iconChoices.map((icon) => [icon.id, icon.iconName])
);

const expanded = ref(true);
const dragOverFolder = ref(false);
const actionMenuOpen = ref(false);
const iconPickerOpen = ref(false);

const nodeKey = (node: ExplorerTreeNode) =>
  node.kind === 'folder'
    ? `folder:${node.folder?.folder_id}`
    : `item:${node.location?.item_type}:${node.location?.item_id || node.item?.item_id}`;

const folderId = computed(() => props.node.folder?.folder_id || '');
const isFolderActive = computed(() => props.selectedFolderId === folderId.value);
const isExpanded = computed(() => props.forceExpanded || expanded.value);
const currentItemId = computed(() => String(
  props.node.location?.item_id || props.node.item?.item_id || props.node.item?.session_id || props.node.item?.id || ''
));
const currentItemType = computed<ExplorerItemType>(() =>
  (props.node.location?.item_type || props.node.item?.item_type || 'knowledge_node') as ExplorerItemType
);
const itemTitle = computed(() => String(
  props.node.item?.title || props.node.item?.session_id || props.node.item?.id || currentItemId.value || 'Untitled'
));
const isSessionItem = computed(() => currentItemType.value === 'session');
const isActive = computed(() => props.currentItemId === currentItemId.value);
const rowIndent = computed(() => ({ paddingLeft: `${props.depth * 18 + 4}px` }));
const canEditIcon = computed(() =>
  props.editableItemIcons || (props.editableSessionIcons && isSessionItem.value)
);
const iconTriggerAttribute = computed(() =>
  isSessionItem.value
    ? { 'data-session-icon-trigger': currentItemId.value }
    : { 'data-item-icon-trigger': currentItemId.value }
);
const itemIcon = computed(() => {
  const customIcon = iconNameMap[String(props.node.item?.icon || '')];
  if (customIcon) return customIcon;
  if (isSessionItem.value) return 'functions';
  const type = String(props.node.item?.type || '').toLowerCase();
  if (type === 'definition') return 'data_object';
  if (type === 'theorem') return 'account_tree';
  if (type === 'proof') return 'functions';
  return 'article';
});
const messageCount = computed(() => Number(props.node.item?.message_count || 0));
const knowledgeStatus = computed(() =>
  isSessionItem.value ? '' : String(props.node.item?.status || '')
);
const statusLabel = computed(() => {
  if (knowledgeStatus.value === 'pending') return 'Saving note';
  if (knowledgeStatus.value === 'failed') return 'Note failed to save';
  return knowledgeStatus.value;
});
const itemPath = computed(() => props.node.location?.path_cached || itemTitle.value);

const countItems = (node: ExplorerTreeNode): number =>
  node.kind === 'item'
    ? 1
    : node.children.reduce((total, child) => total + countItems(child), 0);
const folderItemCount = computed(() => countItems(props.node));
const countFolders = (node: ExplorerTreeNode): number =>
  node.children.reduce(
    (total, child) => total + (child.kind === 'folder' ? 1 : 0) + countFolders(child),
    0
  );
const childFolderCount = computed(() => countFolders(props.node));

const toggleFolder = () => {
  if (!props.forceExpanded) expanded.value = !expanded.value;
};

const parseDraggedItem = (event: DragEvent): { itemType: ExplorerItemType; itemId: string } | null => {
  const raw = event.dataTransfer?.getData(EXPLORER_DRAG_MIME)
    || event.dataTransfer?.getData('text/plain');
  if (!raw) return null;
  try {
    const payload = JSON.parse(raw) as { itemType?: string; itemId?: string };
    if (
      (payload.itemType === 'session' || payload.itemType === 'knowledge_node')
      && typeof payload.itemId === 'string'
      && payload.itemId
    ) {
      return { itemType: payload.itemType, itemId: payload.itemId };
    }
  } catch {
    return null;
  }
  return null;
};

const handleFolderDragOver = (event: DragEvent) => {
  dragOverFolder.value = true;
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
};

const handleFolderDrop = (event: DragEvent) => {
  dragOverFolder.value = false;
  const dragged = parseDraggedItem(event);
  if (!dragged || !folderId.value) return;
  emit('move-item', dragged.itemType, dragged.itemId, folderId.value);
};

const handleDragStart = (event: DragEvent) => {
  const payload = JSON.stringify({ itemType: currentItemType.value, itemId: currentItemId.value });
  event.dataTransfer?.setData(EXPLORER_DRAG_MIME, payload);
  event.dataTransfer?.setData('text/plain', payload);
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
};

const selectItem = () => emit(
  'select-item',
  currentItemType.value,
  currentItemId.value,
  props.node.location?.folder_id || null
);
const selectFolder = () => emit('select-folder', folderId.value);
const selectAndToggleFolder = () => {
  selectFolder();
  toggleFolder();
};
const closeMenus = () => {
  actionMenuOpen.value = false;
  iconPickerOpen.value = false;
};
const requestRenameFolder = () => {
  closeMenus();
  emit('request-rename-folder', folderId.value, props.node.folder?.name || 'Untitled');
};
const requestDeleteFolder = () => {
  closeMenus();
  emit(
    'request-delete-folder',
    folderId.value,
    props.node.folder?.name || 'Untitled',
    folderItemCount.value,
    childFolderCount.value
  );
};
const requestMoveItem = () => {
  closeMenus();
  emit(
    'request-move-item',
    currentItemType.value,
    currentItemId.value,
    itemTitle.value,
    props.node.location?.folder_id || null
  );
};
const requestRenameItem = () => {
  closeMenus();
  emit('request-rename-item', currentItemType.value, currentItemId.value, itemTitle.value);
};
const requestDeleteItem = () => {
  closeMenus();
  emit('request-delete-item', currentItemType.value, currentItemId.value, itemTitle.value);
};
const chooseIcon = (icon: string) => {
  iconPickerOpen.value = false;
  if (isSessionItem.value && props.editableSessionIcons) {
    emit('update-session-icon', currentItemId.value, icon);
    return;
  }
  emit('update-item-icon', currentItemType.value, currentItemId.value, icon);
};

onMounted(() => document.addEventListener('click', closeMenus));
onBeforeUnmount(() => document.removeEventListener('click', closeMenus));
</script>
