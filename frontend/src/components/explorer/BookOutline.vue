<template>
  <ExplorerTree
    :tree="knowledgeExplorerTree"
    :current-item-id="currentNode?.id || null"
    title="Book Outline"
    root-action-title="New knowledge folder"
    editable-item-icons
    @select-item="handleSelectItem"
    @create-folder="handleCreateFolder"
    @move-item="handleMoveItem"
    @update-item-icon="handleUpdateItemIcon"
  />
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import ExplorerTree from './ExplorerTree.vue';
import { useWorkspaceStore } from '../../stores/workspace';
import type { ExplorerItemType } from '../../services/api';

const store = useWorkspaceStore();
const { knowledgeExplorerTree, currentNode } = storeToRefs(store);

const handleSelectItem = (itemType: ExplorerItemType, itemId: string) => {
  if (itemType === 'knowledge_node') {
    store.selectNode(itemId);
  }
};

const handleCreateFolder = async (parentFolderId: string | null) => {
  const name = window.prompt('Folder name');
  if (!name) return;
  await store.createExplorerFolder('knowledge', name, parentFolderId);
};

const handleMoveItem = async (
  itemType: ExplorerItemType,
  itemId: string,
  folderId: string | null
) => {
  if (itemType !== 'knowledge_node') return;
  await store.moveExplorerItem('knowledge_node', itemId, folderId);
};

const handleUpdateItemIcon = async (
  itemType: ExplorerItemType,
  itemId: string,
  icon: string
) => {
  await store.updateExplorerItemIcon(itemType, itemId, icon);
};
</script>
