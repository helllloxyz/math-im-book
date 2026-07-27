<script setup lang="ts">
import { computed } from 'vue';
import { useWorkspaceStore } from '../../stores/workspace';
import MarkdownContent from '../common/MarkdownContent.vue';
import NodeReferences from './NodeReferences.vue';

const store = useWorkspaceStore();

defineProps<{
  isExpanded?: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle-expanded'): void;
}>();

const node = computed(() => store.currentNode);

const nodeTypeMeta: Record<string, { icon: string; label: string }> = {
  atomic: { icon: 'science', label: 'Atomic note' },
  section: { icon: 'local_library', label: 'Section' },
  definition: { icon: 'data_object', label: 'Definition' },
  theorem: { icon: 'account_tree', label: 'Theorem' },
  lemma: { icon: 'schema', label: 'Lemma' },
  proof: { icon: 'functions', label: 'Proof' },
};

const currentTypeMeta = computed(() => {
  if (!node.value) {
    return { icon: 'local_library', label: 'Library' };
  }
  return nodeTypeMeta[node.value.type.toLowerCase()] || {
    icon: 'article',
    label: `${node.value.type} note`,
  };
});

const markdownDetail = computed(() => {
  if (!node.value?.detail) {
    return node.value?.summary || '';
  }
  return node.value.detail;
});
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden bg-surface text-on-surface">
    <!-- Header -->
    <div class="h-20 flex shrink-0 items-center justify-between gap-4 px-6 border-b border-outline-variant/10">
      <div class="min-w-0 flex items-center gap-3 text-on-surface-variant/60">
        <span class="material-symbols-outlined text-[20px]" :title="currentTypeMeta.label">{{ currentTypeMeta.icon }}</span>
      </div>
      <div class="flex shrink-0 items-center text-on-surface-variant/40">
        <button
          :title="isExpanded ? 'Restore preview' : 'Expand preview'"
          data-reader-action="toggle-width"
          class="hover:text-primary transition-colors flex items-center justify-center w-8 h-8 rounded-full hover:bg-primary-fixed"
          @click="emit('toggle-expanded')"
        >
          <span class="material-symbols-outlined text-[18px]">
            {{ isExpanded ? 'close_fullscreen' : 'open_in_full' }}
          </span>
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto px-8 py-10 scroll-smooth">
      <article
        v-if="node"
        class="mx-auto space-y-12 transition-[max-width] duration-300 ease-out"
        :class="isExpanded ? 'max-w-[58rem]' : 'max-w-2xl'"
      >
        <div class="space-y-6">
          <h1 class="font-serif italic text-4xl leading-tight text-primary">
            {{ node.title }}
          </h1>

          <div v-if="node.detail && node.summary" class="border-l-2 border-primary/20 pl-6 font-serif text-xl leading-relaxed text-on-surface-variant italic">
            {{ node.summary }}
          </div>
        </div>

        <div
          class="font-serif text-[17px] leading-relaxed text-on-surface"
          data-selection-source="knowledge-node"
          :data-node-id="node.id"
        >
          <MarkdownContent :content="markdownDetail" />
        </div>

        <!-- Symbol Registry -->
        <div v-if="node.symbols && Object.keys(node.symbols).length > 0" class="pt-10">
          <h3 class="font-sans text-[11px] font-bold uppercase tracking-widest text-on-surface-variant mb-6">Symbol Registry</h3>
          <div class="grid grid-cols-2 gap-4">
            <div v-for="(desc, sym) in node.symbols" :key="sym" class="bg-surface-container-lowest p-5 rounded-2xl shadow-sm hover:bg-primary-fixed transition-colors duration-300 group cursor-help ghost-border">
              <div class="font-serif text-3xl mb-3 text-primary">{{ sym }}</div>
              <p class="font-sans text-[10px] text-on-surface-variant/80 leading-relaxed">{{ desc }}</p>
            </div>
          </div>
        </div>

        <NodeReferences />
      </article>

      <!-- Empty State -->
      <div v-else class="flex h-full items-center justify-center py-20">
        <div class="max-w-sm rounded-3xl bg-surface-container-lowest p-10 text-center shadow-sm ghost-border">
          <div class="mx-auto mb-8 flex h-16 w-16 items-center justify-center rounded-full bg-primary-fixed text-primary">
            <span class="material-symbols-outlined text-[32px]">local_library</span>
          </div>
          <h2 class="mb-3 font-serif text-2xl text-on-surface">Knowledge Library</h2>
          <p class="font-serif text-lg leading-relaxed text-on-surface-variant/70 italic">
            Select a section from the book outline to explore formal definitions and derivations.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
