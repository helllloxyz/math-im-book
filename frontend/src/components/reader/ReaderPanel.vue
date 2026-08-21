<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { useWorkspaceStore } from '../../stores/workspace';
import MarkdownContent from '../common/MarkdownContent.vue';
import NodeReferences from './NodeReferences.vue';

const store = useWorkspaceStore();

const props = defineProps<{
  isExpanded?: boolean;
  pageMode?: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle-expanded'): void;
  (e: 'close'): void;
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

const isEditing = ref(false);
const editDraft = reactive({ title: '', type: '', summary: '', detail: '' });

const resetEditDraft = () => {
  if (!node.value) return;
  editDraft.title = node.value.title;
  editDraft.type = node.value.type;
  editDraft.summary = node.value.summary;
  editDraft.detail = node.value.detail;
};

watch(() => node.value?.id, () => {
  isEditing.value = false;
  resetEditDraft();
}, { immediate: true });

const startEditing = () => {
  resetEditDraft();
  isEditing.value = true;
};

const saveEdit = async () => {
  if (!node.value) return;
  await store.saveKnowledgeNode(node.value.id, {
    title: editDraft.title,
    type: editDraft.type,
    summary: editDraft.summary,
    detail: editDraft.detail,
  });
  isEditing.value = false;
};

const prepareFollowUp = () => {
  if (!node.value) return;
  store.prepareKnowledgeFollowUp(node.value.id, node.value.title);
};
</script>

<template>
  <div
    class="reader-panel flex h-full flex-col overflow-hidden bg-surface text-on-surface"
    :class="{ 'knowledge-page-reader': props.pageMode }"
    :data-knowledge-page="props.pageMode ? 'true' : undefined"
  >
    <!-- Header -->
    <div class="flex h-[74px] shrink-0 items-center justify-between gap-4 border-b border-outline-variant/10 px-6">
      <div class="min-w-0 flex items-center gap-3 text-on-surface-variant/60">
        <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-fixed text-primary material-symbols-outlined text-[18px]" :title="currentTypeMeta.label">{{ currentTypeMeta.icon }}</span>
        <div>
          <p class="font-sans text-[9px] font-semibold uppercase tracking-[0.14em] text-on-surface-variant/60">Knowledge note</p>
          <p class="max-w-[260px] truncate font-sans text-[12px] font-medium text-on-surface">{{ node?.title }}</p>
        </div>
      </div>
      <div class="flex shrink-0 items-center text-on-surface-variant/40">
        <button
          v-if="node"
          title="Ask a follow-up about this note"
          aria-label="Ask about this knowledge note"
          data-reader-action="follow-up"
          class="hover:text-primary transition-colors flex items-center justify-center w-8 h-8 rounded-full hover:bg-primary-fixed"
          @click="prepareFollowUp"
        >
          <span class="material-symbols-outlined text-[18px]">chat_bubble</span>
        </button>
        <button
          v-if="node"
          :title="isEditing ? 'Cancel editing' : 'Edit knowledge note'"
          :aria-label="isEditing ? 'Cancel editing' : 'Edit knowledge note'"
          data-reader-action="edit"
          class="hover:text-primary transition-colors flex items-center justify-center w-8 h-8 rounded-full hover:bg-primary-fixed"
          @click="isEditing ? (isEditing = false) : startEditing()"
        >
          <span class="material-symbols-outlined text-[18px]">{{ isEditing ? 'undo' : 'edit' }}</span>
        </button>
        <button
          v-if="!props.pageMode"
          :title="isExpanded ? 'Restore preview' : 'Expand preview'"
          :aria-label="isExpanded ? 'Restore note width' : 'Expand note width'"
          data-reader-action="toggle-width"
          class="hover:text-primary transition-colors flex items-center justify-center w-8 h-8 rounded-full hover:bg-primary-fixed"
          @click="emit('toggle-expanded')"
        >
          <span class="material-symbols-outlined text-[18px]">
            {{ isExpanded ? 'close_fullscreen' : 'open_in_full' }}
          </span>
        </button>
        <button
          v-if="!props.pageMode"
          title="Close note"
          aria-label="Close note"
          data-reader-action="close"
          class="hover:text-primary transition-colors flex items-center justify-center w-8 h-8 rounded-full hover:bg-primary-fixed"
          @click="emit('close')"
        >
          <span class="material-symbols-outlined text-[18px]">close</span>
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto px-8 py-10 scroll-smooth">
      <article
        v-if="node"
        class="mx-auto space-y-10 transition-[max-width] duration-300 ease-out"
        :class="props.pageMode || isExpanded ? 'max-w-[58rem]' : 'max-w-2xl'"
      >
        <form
          v-if="isEditing"
          class="space-y-6 rounded-2xl bg-surface-container-lowest p-6 shadow-sm ghost-border"
          data-knowledge-editor
          @submit.prevent="saveEdit"
        >
          <div class="grid gap-2">
            <label class="font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Title</label>
            <input v-model="editDraft.title" required class="rounded-xl border border-outline-variant/20 bg-surface px-4 py-3 font-serif text-xl text-on-surface outline-none focus:border-primary/40" />
          </div>
          <div class="grid gap-2">
            <label class="font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Type</label>
            <input v-model="editDraft.type" required class="rounded-xl border border-outline-variant/20 bg-surface px-4 py-3 font-sans text-sm text-on-surface outline-none focus:border-primary/40" />
          </div>
          <div class="grid gap-2">
            <label class="font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Summary</label>
            <textarea v-model="editDraft.summary" required rows="3" class="resize-y rounded-xl border border-outline-variant/20 bg-surface px-4 py-3 font-serif text-base leading-relaxed text-on-surface outline-none focus:border-primary/40"></textarea>
          </div>
          <div class="grid gap-2">
            <label class="font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Detail</label>
            <textarea v-model="editDraft.detail" required rows="14" class="resize-y rounded-xl border border-outline-variant/20 bg-surface px-4 py-3 font-mono text-sm leading-relaxed text-on-surface outline-none focus:border-primary/40"></textarea>
          </div>
          <div class="flex items-center justify-between gap-4">
            <p class="font-sans text-[10px] text-on-surface-variant">Saving creates revision {{ node.revision + 1 }}.</p>
            <div class="flex gap-2">
              <button type="button" class="rounded-lg px-4 py-2 font-sans text-xs text-on-surface-variant hover:bg-surface-container-low" @click="isEditing = false">Cancel</button>
              <button type="submit" :disabled="store.explorerBusy" class="rounded-lg bg-primary px-4 py-2 font-sans text-xs font-semibold text-on-primary disabled:opacity-50">
                {{ store.explorerBusy ? 'Saving…' : 'Save revision' }}
              </button>
            </div>
          </div>
        </form>

        <template v-else>
        <div class="space-y-6">
          <h1 class="font-serif text-4xl font-medium leading-tight tracking-[-0.025em] text-primary">
            {{ node.title }}
          </h1>

          <div v-if="node.detail && node.summary" class="border-l-2 border-accent/50 pl-5 font-serif text-lg leading-relaxed text-on-surface-variant italic">
            {{ node.summary }}
          </div>
          <p class="font-sans text-[9px] uppercase tracking-widest text-on-surface-variant/55">
            Revision {{ node.revision }}
          </p>
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
        </template>
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
