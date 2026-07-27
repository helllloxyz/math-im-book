<template>
  <ExplorerTree
    :tree="sessionExplorerTree"
    :current-item-id="currentSession?.session_id || null"
    title="Session Tree"
    root-action-title="New session folder"
    primary-action-title="New Conversation"
    primary-action-icon="add_box"
    editable-session-icons
    @select-item="handleSelectItem"
    @create-folder="handleCreateFolder"
    @move-item="handleMoveItem"
    @primary-action="store.newSession"
    @update-session-icon="handleUpdateSessionIcon"
  />
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import ExplorerTree from './ExplorerTree.vue';
import { useWorkspaceStore } from '../../stores/workspace';
import type { ExplorerItemType } from '../../services/api';

const store = useWorkspaceStore();
const { sessionExplorerTree, currentSession } = storeToRefs(store);

const handleSelectItem = (itemType: ExplorerItemType, itemId: string) => {
  if (itemType === 'session') {
    store.selectSession(itemId);
  }
};

const handleCreateFolder = async (parentFolderId: string | null) => {
  const name = window.prompt('Folder name');
  if (!name) return;
  await store.createExplorerFolder('sessions', name, parentFolderId);
};

const handleMoveItem = async (
  itemType: ExplorerItemType,
  itemId: string,
  folderId: string | null
) => {
  if (itemType !== 'session') return;
  await store.moveExplorerItem('session', itemId, folderId);
};

const handleUpdateSessionIcon = async (sessionId: string, icon: string) => {
  await store.updateSessionIcon(sessionId, icon);
};
</script>
