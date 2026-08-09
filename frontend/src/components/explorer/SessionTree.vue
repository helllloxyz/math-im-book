<template>
  <ExplorerTree
    :tree="sessionExplorerTree"
    :current-item-id="currentSession?.session_id || null"
    title="Conversations"
    primary-action-title="New inquiry"
    primary-action-icon="chat_bubble"
    search-placeholder="Search conversations"
    empty-text="Your questions and conversations will collect here."
    :busy="explorerBusy"
    editable-session-icons
    can-rename-items
    can-delete-items
    @select-item="handleSelectItem"
    @create-folder="handleCreateFolder"
    @rename-folder="handleRenameFolder"
    @delete-folder="handleDeleteFolder"
    @move-item="handleMoveItem"
    @rename-item="handleRenameItem"
    @delete-item="handleDeleteItem"
    @primary-action="handleNewInquiry"
    @update-session-icon="handleUpdateSessionIcon"
  />
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import ExplorerTree from './ExplorerTree.vue';
import { useWorkspaceStore } from '../../stores/workspace';
import type { ExplorerItemType } from '../../services/api';

const store = useWorkspaceStore();
const { sessionExplorerTree, currentSession, explorerBusy } = storeToRefs(store);
const runAction = async (action: () => Promise<void>) => {
  try {
    await action();
  } catch (error) {
    console.error('Explorer action failed:', error);
  }
};

const handleNewInquiry = (folderId: string | null) => store.newSession(folderId);

const handleSelectItem = (itemType: ExplorerItemType, itemId: string) => {
  if (itemType === 'session') {
    store.selectSession(itemId);
  }
};

const handleCreateFolder = async (parentFolderId: string | null, name: string) => {
  await runAction(() =>
    store.createExplorerFolder('sessions', name, parentFolderId)
  );
};

const handleRenameFolder = async (folderId: string, name: string) => {
  await runAction(() =>
    store.renameExplorerFolder(folderId, name)
  );
};

const handleDeleteFolder = async (folderId: string) => {
  await runAction(() =>
    store.deleteExplorerFolder('sessions', folderId)
  );
};

const handleMoveItem = async (
  itemType: ExplorerItemType,
  itemId: string,
  folderId: string | null
) => {
  if (itemType !== 'session') return;
  await runAction(() =>
    store.moveExplorerItem('session', itemId, folderId)
  );
};

const handleRenameItem = async (
  itemType: ExplorerItemType,
  itemId: string,
  name: string
) => {
  if (itemType !== 'session') return;
  await runAction(() =>
    store.renameSession(itemId, name)
  );
};

const handleDeleteItem = async (itemType: ExplorerItemType, itemId: string) => {
  if (itemType !== 'session') return;
  await runAction(() =>
    store.deleteSession(itemId)
  );
};

const handleUpdateSessionIcon = async (sessionId: string, icon: string) => {
  await runAction(() =>
    store.updateSessionIcon(sessionId, icon)
  );
};
</script>
