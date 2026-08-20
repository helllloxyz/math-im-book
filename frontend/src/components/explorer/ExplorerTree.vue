<template>
  <section class="explorer-tree" :aria-label="title || 'Explorer'">
    <div
      class="explorer-tree-header"
      :class="{ 'explorer-tree-drop-target': dragOverRoot }"
      data-explorer-root-drop
      @dragenter.prevent="dragOverRoot = true"
      @dragover.prevent="handleRootDragOver"
      @dragleave="dragOverRoot = false"
      @drop.prevent="handleRootDrop"
    >
      <button
        v-if="title"
        type="button"
        class="explorer-tree-scope"
        :class="{ 'is-root-active': !selectedFolderId && !selectedItemId }"
        data-explorer-root-select
        title="Select top level"
        @click="selectRoot"
      >
        <h3 class="explorer-tree-title">{{ title }}</h3>
      </button>
      <div class="explorer-tree-header-actions" @click.stop>
        <button
          type="button"
          class="explorer-tree-header-action explorer-create-trigger"
          data-explorer-create-menu
          :title="`Add to ${baseFolderName || title || 'top level'}`"
          :aria-label="`Create in ${baseFolderName || title || 'top level'}`"
          aria-haspopup="menu"
          :aria-expanded="createMenuOpen ? 'true' : 'false'"
          @click="createMenuOpen = !createMenuOpen"
        >
          <span class="material-symbols-outlined" aria-hidden="true">add</span>
        </button>
        <div v-if="createMenuOpen" class="explorer-create-menu explorer-tree-menu" role="menu">
          <button
            v-if="primaryActionTitle"
            type="button"
            role="menuitem"
            data-explorer-primary-action
            @click="runPrimaryAction"
          >
            <span class="material-symbols-outlined" aria-hidden="true">{{ primaryActionIcon || 'chat_bubble' }}</span>
            {{ primaryActionTitle }}
          </button>
          <button
            type="button"
            role="menuitem"
            data-explorer-create-folder
            @click="openCreateFolder(baseFolderId)"
          >
            <span class="material-symbols-outlined" aria-hidden="true">create_new_folder</span>
            New folder
          </button>
        </div>
      </div>
    </div>

    <label class="explorer-search">
      <span class="material-symbols-outlined" aria-hidden="true">search</span>
      <input
        v-model="query"
        type="search"
        :placeholder="searchPlaceholder || 'Search titles and notes'"
        :aria-label="searchPlaceholder || 'Search titles and notes'"
        data-explorer-search
      />
      <button v-if="query" type="button" aria-label="Clear search" @click="query = ''">
        <span class="material-symbols-outlined" aria-hidden="true">close</span>
      </button>
      <kbd v-else>/</kbd>
    </label>

    <div v-if="filteredTree.length" class="explorer-tree-list">
      <ExplorerTreeRow
        v-for="node in filteredTree"
        :key="nodeKey(node)"
        :node="node"
        :depth="0"
        :current-item-id="selectedItemId"
        :selected-folder-id="selectedFolderId"
        :force-expanded="Boolean(normalizedQuery)"
        :editable-session-icons="editableSessionIcons"
        :editable-item-icons="editableItemIcons"
        :can-rename-items="canRenameItems"
        :can-delete-items="canDeleteItems"
        @select-item="selectItem"
        @move-item="(...args) => emit('move-item', ...args)"
        @select-folder="selectFolder"
        @request-rename-folder="openRenameFolder"
        @request-delete-folder="openDeleteFolder"
        @request-move-item="openMoveItem"
        @request-rename-item="openRenameItem"
        @request-delete-item="openDeleteItem"
        @update-session-icon="(...args) => emit('update-session-icon', ...args)"
        @update-item-icon="(...args) => emit('update-item-icon', ...args)"
      />
    </div>

    <div v-else class="explorer-zero-state" data-explorer-empty>
      <span class="material-symbols-outlined" aria-hidden="true">
        {{ normalizedQuery ? 'search_off' : 'inventory_2' }}
      </span>
      <p>{{ normalizedQuery ? `No results for “${query.trim()}”` : (emptyText || 'Nothing here yet.') }}</p>
      <button v-if="normalizedQuery" type="button" @click="query = ''">Clear search</button>
    </div>

    <Teleport to="body">
      <div
        v-if="dialog"
        class="explorer-dialog-backdrop"
        role="presentation"
        @mousedown.self="closeDialog"
      >
      <form
        v-if="dialog.kind === 'name'"
        class="explorer-dialog"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`${dialog.mode}-title`"
        @submit.prevent="submitNameDialog"
      >
        <div class="explorer-dialog-icon" aria-hidden="true">
          <span class="material-symbols-outlined">{{ dialog.mode === 'create-folder' ? 'create_new_folder' : 'edit' }}</span>
        </div>
        <div>
          <p class="explorer-dialog-kicker">Organize workspace</p>
          <h4 :id="`${dialog.mode}-title`">{{ nameDialogTitle }}</h4>
        </div>
        <label>
          <span>Name</span>
          <input
            ref="nameInput"
            v-model="draftName"
            type="text"
            maxlength="120"
            autocomplete="off"
            data-explorer-name-input
          />
        </label>
        <div class="explorer-dialog-actions">
          <button type="button" class="secondary" @click="closeDialog">Cancel</button>
          <button type="submit" class="primary" :disabled="busy || !draftName.trim()">
            {{ busy ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </form>

      <form
        v-else-if="dialog.kind === 'move'"
        class="explorer-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-item-title"
        @submit.prevent="submitMoveDialog"
      >
        <div class="explorer-dialog-icon" aria-hidden="true">
          <span class="material-symbols-outlined">drive_file_move</span>
        </div>
        <div>
          <p class="explorer-dialog-kicker">Organize workspace</p>
          <h4 id="move-item-title">Move “{{ dialog.title }}”</h4>
        </div>
        <label>
          <span>Destination</span>
          <select v-model="moveDestination" data-explorer-move-select>
            <option value="">Top level</option>
            <option v-for="folder in folderOptions" :key="folder.id" :value="folder.id">
              {{ folder.path }}
            </option>
          </select>
        </label>
        <p class="explorer-dialog-note">You can also drag items directly onto a folder.</p>
        <div class="explorer-dialog-actions">
          <button type="button" class="secondary" @click="closeDialog">Cancel</button>
          <button type="submit" class="primary" :disabled="busy">
            {{ busy ? 'Moving…' : 'Move' }}
          </button>
        </div>
      </form>

      <div
        v-else
        class="explorer-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-resource-title"
      >
        <div class="explorer-dialog-icon danger" aria-hidden="true">
          <span class="material-symbols-outlined">delete_outline</span>
        </div>
        <div>
          <p class="explorer-dialog-kicker">Confirm action</p>
          <h4 id="delete-resource-title">Delete “{{ dialog.title }}”?</h4>
        </div>
        <p v-if="dialog.kind === 'delete-folder' && (dialog.itemCount || dialog.folderCount)" class="explorer-dialog-warning">
          This folder still contains
          <template v-if="dialog.itemCount">{{ dialog.itemCount }} item{{ dialog.itemCount === 1 ? '' : 's' }}</template>
          <template v-if="dialog.itemCount && dialog.folderCount"> and </template>
          <template v-if="dialog.folderCount">{{ dialog.folderCount }} subfolder{{ dialog.folderCount === 1 ? '' : 's' }}</template>.
          Move them elsewhere before deleting the folder.
        </p>
        <p v-else class="explorer-dialog-note">
          {{ dialog.kind === 'delete-folder'
            ? 'Only the empty folder will be removed.'
            : 'The conversation and its messages will be permanently removed.' }}
        </p>
        <div class="explorer-dialog-actions">
          <button type="button" class="secondary" @click="closeDialog">Cancel</button>
          <button
            type="button"
            class="danger-button"
            :disabled="busy || (dialog.kind === 'delete-folder' && (dialog.itemCount > 0 || dialog.folderCount > 0))"
            data-explorer-confirm-delete
            @click="submitDeleteDialog"
          >
            {{ busy ? 'Deleting…' : 'Delete' }}
          </button>
        </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { ExplorerItemType, ExplorerTreeNode } from '../../services/api';
import ExplorerTreeRow from './ExplorerTreeRow.vue';

const props = withDefaults(defineProps<{
  tree: ExplorerTreeNode[];
  currentItemId?: string | null;
  title?: string;
  primaryActionTitle?: string;
  primaryActionIcon?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  busy?: boolean;
  editableSessionIcons?: boolean;
  editableItemIcons?: boolean;
  canRenameItems?: boolean;
  canDeleteItems?: boolean;
}>(), {
  currentItemId: null,
  title: '',
  primaryActionTitle: '',
  primaryActionIcon: 'chat_bubble',
  searchPlaceholder: '',
  emptyText: '',
  busy: false,
  editableSessionIcons: false,
  editableItemIcons: false,
  canRenameItems: false,
  canDeleteItems: false,
});

const emit = defineEmits<{
  (event: 'select-item', itemType: ExplorerItemType, itemId: string): void;
  (event: 'create-folder', parentFolderId: string | null, name: string): void;
  (event: 'rename-folder', folderId: string, name: string): void;
  (event: 'delete-folder', folderId: string): void;
  (event: 'move-item', itemType: ExplorerItemType, itemId: string, folderId: string | null): void;
  (event: 'rename-item', itemType: ExplorerItemType, itemId: string, name: string): void;
  (event: 'delete-item', itemType: ExplorerItemType, itemId: string): void;
  (event: 'primary-action', folderId: string | null): void;
  (event: 'base-folder-change', folderId: string | null): void;
  (event: 'update-session-icon', sessionId: string, icon: string): void;
  (event: 'update-item-icon', itemType: ExplorerItemType, itemId: string, icon: string): void;
}>();

type DialogState =
  | { kind: 'name'; mode: 'create-folder'; parentFolderId: string | null }
  | { kind: 'name'; mode: 'rename-folder'; folderId: string }
  | { kind: 'name'; mode: 'rename-item'; itemType: ExplorerItemType; itemId: string }
  | { kind: 'move'; itemType: ExplorerItemType; itemId: string; title: string }
  | { kind: 'delete-folder'; folderId: string; title: string; itemCount: number; folderCount: number }
  | { kind: 'delete-item'; itemType: ExplorerItemType; itemId: string; title: string };

const EXPLORER_DRAG_MIME = 'application/x-math-im-book-explorer-item';
const query = ref('');
const dragOverRoot = ref(false);
const selectedFolderId = ref<string | null>(null);
const selectedItemId = ref<string | null>(props.currentItemId);
const baseFolderId = ref<string | null>(null);
const createMenuOpen = ref(false);
const dialog = ref<DialogState | null>(null);
const draftName = ref('');
const moveDestination = ref('');
const nameInput = ref<HTMLInputElement | null>(null);

const normalizedQuery = computed(() => query.value.trim().toLocaleLowerCase());
const baseFolderName = computed(() =>
  folderOptions.value.find((folder) => folder.id === baseFolderId.value)?.path || ''
);

const nodeKey = (node: ExplorerTreeNode) =>
  node.kind === 'folder'
    ? `folder:${node.folder?.folder_id}`
    : `item:${node.location?.item_type}:${node.location?.item_id || node.item?.item_id}`;

const itemTitle = (node: ExplorerTreeNode) => String(
  node.item?.title || node.item?.session_id || node.item?.id || node.item?.item_id || 'Untitled'
);

const itemId = (node: ExplorerTreeNode) => String(
  node.location?.item_id || node.item?.item_id || node.item?.session_id || node.item?.id || ''
);

const findItemFolderId = (
  nodes: ExplorerTreeNode[],
  targetItemId: string
): string | null | undefined => {
  for (const node of nodes) {
    if (node.kind === 'item' && itemId(node) === targetItemId) {
      return node.location?.folder_id || null;
    }
    if (node.kind === 'folder') {
      const match = findItemFolderId(node.children, targetItemId);
      if (match !== undefined) return match;
    }
  }
  return undefined;
};

const filterNodes = (nodes: ExplorerTreeNode[]): ExplorerTreeNode[] => {
  const needle = normalizedQuery.value;
  if (!needle) return nodes;
  return nodes.flatMap((node) => {
    if (node.kind === 'item') {
      const haystack = [
        itemTitle(node),
        node.item?.summary,
        node.item?.type,
        node.location?.path_cached,
      ].filter(Boolean).join(' ').toLocaleLowerCase();
      return haystack.includes(needle) ? [node] : [];
    }
    const folderMatches = String(node.folder?.name || '').toLocaleLowerCase().includes(needle);
    const matchingChildren = folderMatches ? node.children : filterNodes(node.children);
    return folderMatches || matchingChildren.length
      ? [{ ...node, children: matchingChildren }]
      : [];
  });
};

const filteredTree = computed(() => filterNodes(props.tree));
const folderOptions = computed(() => {
  const options: Array<{ id: string; path: string }> = [];
  const visit = (nodes: ExplorerTreeNode[], parents: string[]) => {
    for (const node of nodes) {
      if (node.kind !== 'folder' || !node.folder) continue;
      const parts = [...parents, node.folder.name];
      options.push({ id: node.folder.folder_id, path: parts.join(' / ') });
      visit(node.children, parts);
    }
  };
  visit(props.tree, []);
  return options;
});

const nameDialogTitle = computed(() => {
  if (dialog.value?.kind !== 'name') return '';
  if (dialog.value.mode === 'create-folder') return 'Create a folder';
  if (dialog.value.mode === 'rename-folder') return 'Rename folder';
  return dialog.value.itemType === 'knowledge_node'
    ? 'Rename knowledge note'
    : 'Rename conversation';
});

const focusNameInput = async () => {
  await nextTick();
  nameInput.value?.focus();
  nameInput.value?.select();
};
const openCreateFolder = (parentFolderId: string | null) => {
  createMenuOpen.value = false;
  dialog.value = { kind: 'name', mode: 'create-folder', parentFolderId };
  draftName.value = '';
  void focusNameInput();
};
const selectRoot = () => {
  selectedFolderId.value = null;
  selectedItemId.value = null;
  baseFolderId.value = null;
  createMenuOpen.value = false;
  emit('base-folder-change', null);
};
const selectFolder = (folderId: string) => {
  selectedFolderId.value = folderId;
  selectedItemId.value = null;
  baseFolderId.value = folderId;
  createMenuOpen.value = false;
  emit('base-folder-change', folderId);
};
const selectItem = (itemType: ExplorerItemType, selectedId: string, folderId: string | null) => {
  selectedItemId.value = selectedId;
  selectedFolderId.value = null;
  baseFolderId.value = folderId;
  createMenuOpen.value = false;
  emit('base-folder-change', folderId);
  emit('select-item', itemType, selectedId);
};
const runPrimaryAction = () => {
  createMenuOpen.value = false;
  emit('primary-action', baseFolderId.value);
};
const openRenameFolder = (folderId: string, name: string) => {
  dialog.value = { kind: 'name', mode: 'rename-folder', folderId };
  draftName.value = name;
  void focusNameInput();
};
const openRenameItem = (itemType: ExplorerItemType, itemId: string, title: string) => {
  dialog.value = { kind: 'name', mode: 'rename-item', itemType, itemId };
  draftName.value = title;
  void focusNameInput();
};
const openDeleteFolder = (
  folderId: string,
  title: string,
  itemCountValue: number,
  folderCountValue: number
) => {
  dialog.value = {
    kind: 'delete-folder',
    folderId,
    title,
    itemCount: itemCountValue,
    folderCount: folderCountValue,
  };
};
const openDeleteItem = (itemType: ExplorerItemType, itemId: string, title: string) => {
  dialog.value = { kind: 'delete-item', itemType, itemId, title };
};
const openMoveItem = (
  itemType: ExplorerItemType,
  itemId: string,
  title: string,
  folderId: string | null
) => {
  dialog.value = { kind: 'move', itemType, itemId, title };
  moveDestination.value = folderId || '';
};
const closeDialog = () => {
  if (props.busy) return;
  dialog.value = null;
  draftName.value = '';
  moveDestination.value = '';
};
const submitNameDialog = () => {
  if (dialog.value?.kind !== 'name' || !draftName.value.trim()) return;
  const name = draftName.value.trim();
  if (dialog.value.mode === 'create-folder') {
    emit('create-folder', dialog.value.parentFolderId, name);
  } else if (dialog.value.mode === 'rename-folder') {
    emit('rename-folder', dialog.value.folderId, name);
  } else {
    emit('rename-item', dialog.value.itemType, dialog.value.itemId, name);
  }
  closeDialog();
};
const submitMoveDialog = () => {
  if (dialog.value?.kind !== 'move') return;
  emit(
    'move-item',
    dialog.value.itemType,
    dialog.value.itemId,
    moveDestination.value || null
  );
  closeDialog();
};
const submitDeleteDialog = () => {
  if (!dialog.value || dialog.value.kind === 'name' || dialog.value.kind === 'move') return;
  if (dialog.value.kind === 'delete-folder') {
    if (dialog.value.itemCount || dialog.value.folderCount) return;
    emit('delete-folder', dialog.value.folderId);
  } else {
    emit('delete-item', dialog.value.itemType, dialog.value.itemId);
  }
  closeDialog();
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
const handleRootDragOver = (event: DragEvent) => {
  dragOverRoot.value = true;
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
};
const handleRootDrop = (event: DragEvent) => {
  dragOverRoot.value = false;
  const dragged = parseDraggedItem(event);
  if (dragged) emit('move-item', dragged.itemType, dragged.itemId, null);
};

const handleGlobalKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && (dialog.value || createMenuOpen.value)) {
    if (dialog.value) closeDialog();
    createMenuOpen.value = false;
    return;
  }
  const target = event.target as HTMLElement | null;
  const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName || '');
  if (event.key === '/' && !isTyping && !dialog.value) {
    event.preventDefault();
    document.querySelector<HTMLInputElement>('[data-explorer-search]')?.focus();
  }
};

watch(
  () => props.currentItemId,
  (currentItemId) => {
    selectedItemId.value = currentItemId;
    if (!currentItemId) return;
    selectedFolderId.value = null;
    const folderId = findItemFolderId(props.tree, currentItemId);
    if (folderId !== undefined) {
      baseFolderId.value = folderId;
      emit('base-folder-change', folderId);
    }
  },
  { immediate: true }
);

watch(
  () => props.tree,
  (tree) => {
    if (!selectedItemId.value) return;
    const folderId = findItemFolderId(tree, selectedItemId.value);
    if (folderId !== undefined) {
      baseFolderId.value = folderId;
      emit('base-folder-change', folderId);
    }
  }
);

onMounted(() => document.addEventListener('keydown', handleGlobalKeydown));
onBeforeUnmount(() => document.removeEventListener('keydown', handleGlobalKeydown));
</script>
