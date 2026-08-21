<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useWorkspaceStore } from '../../stores/workspace';
import type { DisplayNodeReference } from '../../services/api';
import { buildWorkspaceHref } from '../../services/workspaceNavigation';

const store = useWorkspaceStore();

const node = computed(() => store.currentNode);
const expanded = ref(false);

function formatNodeTitle(reference: DisplayNodeReference) {
  return reference.title || reference.node_id;
}

function formatNodeSecondary(reference: DisplayNodeReference) {
  return reference.summary || reference.reason || null;
}

const conceptItems = computed(() => {
  if (!node.value) return [];

  const dependencies = (node.value.references_display || []).map((reference) => ({
    id: reference.node_id,
    cardId: `dependency:${reference.node_id}`,
    title: formatNodeTitle(reference),
    secondary: formatNodeSecondary(reference),
    direction: 'Depends on',
    href: buildWorkspaceHref({
      view: 'knowledge',
      sessionId: store.currentSession?.session_id,
      nodeId: reference.node_id,
    }),
  }));

  const referencedBy = (node.value.incoming_references_display || []).map((reference) => ({
    id: reference.node_id,
    cardId: `referenced-by:${reference.node_id}`,
    title: formatNodeTitle(reference),
    secondary: formatNodeSecondary(reference),
    direction: 'Referenced by',
    href: buildWorkspaceHref({
      view: 'knowledge',
      sessionId: store.currentSession?.session_id,
      nodeId: reference.node_id,
    }),
  }));

  return [...dependencies, ...referencedBy];
});

watch(node, () => {
  expanded.value = false;
});
</script>

<template>
  <div v-if="node" class="border-t border-outline-variant/10 pt-6">
    <button
      data-related-concepts-toggle
      class="flex w-full items-center justify-between gap-4 rounded-lg px-1 py-2 text-left transition-colors hover:text-primary"
      @click="expanded = !expanded"
    >
      <span class="flex items-center gap-2 font-sans text-[11px] font-bold uppercase tracking-widest text-on-surface-variant">
        <span class="material-symbols-outlined text-[15px]">account_tree</span>
        Related concepts
      </span>
      <span class="flex items-center gap-2 font-sans text-[10px] uppercase tracking-widest text-on-surface-variant/60">
        {{ conceptItems.length }} concepts
        <span class="material-symbols-outlined text-[16px]">
          {{ expanded ? 'expand_less' : 'expand_more' }}
        </span>
      </span>
    </button>

    <div v-if="expanded && conceptItems.length > 0" class="mt-3 grid grid-cols-1 gap-2">
      <a
        v-for="item in conceptItems"
        :key="item.cardId"
        :data-reference-card="item.cardId"
        :href="item.href"
        target="_blank"
        rel="noopener noreferrer"
        :aria-label="`Open ${item.title} in a new tab`"
        class="rounded-lg border border-outline-variant/10 bg-surface-container-lowest px-3 py-2 text-left transition-colors hover:border-primary/30 hover:bg-surface-container-low"
      >
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="font-serif text-[14px] font-medium text-primary">{{ item.title }}</div>
            <p v-if="item.secondary" class="mt-1 font-sans text-[11px] leading-relaxed text-on-surface-variant/70">{{ item.secondary }}</p>
          </div>
          <span class="shrink-0 rounded bg-primary-fixed px-2 py-0.5 font-sans text-[9px] uppercase tracking-widest text-primary/70">
            {{ item.direction }}
          </span>
        </div>
      </a>
    </div>
    <p
      v-else-if="expanded"
      class="mt-3 rounded-lg border border-outline-variant/10 bg-surface-container-lowest px-3 py-2 font-sans text-[11px] text-on-surface-variant/60"
    >
      No related concepts yet.
    </p>
  </div>
</template>
