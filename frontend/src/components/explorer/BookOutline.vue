<template>
  <ExplorerTree
    :tree="knowledgeExplorerTree"
    :current-item-id="currentNode?.id || null"
    title="Library"
    primary-action-title="Organize Library"
    primary-action-icon="auto_awesome"
    search-placeholder="Search notes and concepts"
    empty-text="Knowledge notes will appear here as useful ideas emerge from conversations."
    :busy="explorerBusy"
    editable-item-icons
    can-rename-items
    @select-item="handleSelectItem"
    @create-folder="handleCreateFolder"
    @rename-folder="handleRenameFolder"
    @delete-folder="handleDeleteFolder"
    @move-item="handleMoveItem"
    @rename-item="handleRenameItem"
    @primary-action="handleOrganizeLibrary"
    @update-item-icon="handleUpdateItemIcon"
  />
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import ExplorerTree from './ExplorerTree.vue';
import { useWorkspaceStore } from '../../stores/workspace';
import type { ExplorerItemType } from '../../services/api';
import { buildWorkspaceHref } from '../../services/workspaceNavigation';

const store = useWorkspaceStore();
const { knowledgeExplorerTree, currentNode, explorerBusy } = storeToRefs(store);
const runAction = async (action: () => Promise<void>) => {
  try {
    await action();
  } catch (error) {
    console.error('Explorer action failed:', error);
  }
};

const handleSelectItem = async (itemType: ExplorerItemType, itemId: string) => {
  if (itemType === 'knowledge_node') {
    await store.selectNode(itemId);
    store.activeTab = 'knowledge';
    window.history.replaceState(
      window.history.state,
      '',
      buildWorkspaceHref({
        view: 'knowledge',
        sessionId: store.currentSession?.session_id,
        nodeId: itemId,
      })
    );
  }
};

const handleOrganizeLibrary = async () => {
  try {
    await store.organizeKnowledgeExplorer();
  } catch (error) {
    console.error('Could not organize the library:', error);
  }
};

const handleCreateFolder = async (parentFolderId: string | null, name: string) => {
  await runAction(() =>
    store.createExplorerFolder('knowledge', name, parentFolderId)
  );
};

const handleRenameFolder = async (folderId: string, name: string) => {
  await runAction(() =>
    store.renameExplorerFolder(folderId, name)
  );
};

const handleDeleteFolder = async (folderId: string) => {
  await runAction(() =>
    store.deleteExplorerFolder('knowledge', folderId)
  );
};

const handleMoveItem = async (
  itemType: ExplorerItemType,
  itemId: string,
  folderId: string | null
) => {
  if (itemType !== 'knowledge_node') return;
  await runAction(() =>
    store.moveExplorerItem('knowledge_node', itemId, folderId)
  );
};

const handleRenameItem = async (
  itemType: ExplorerItemType,
  itemId: string,
  name: string
) => {
  if (itemType !== 'knowledge_node') return;
  await runAction(() =>
    store.renameKnowledgeNode(itemId, name)
  );
};

const handleUpdateItemIcon = async (
  itemType: ExplorerItemType,
  itemId: string,
  icon: string
) => {
  await runAction(() =>
    store.updateExplorerItemIcon(itemType, itemId, icon)
  );
};
</script>
