<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type KnowledgeNode, type OutlineNode } from '../../services/api'
import MarkdownContent from '../common/MarkdownContent.vue'

type CitationNode = Pick<OutlineNode, 'title' | 'type' | 'summary'> & {
  node_id: string
}

const props = defineProps<{
  citationIndex: number
  node: CitationNode
  href: string
}>()

const fullNode = ref<KnowledgeNode | null>(null)
const loadState = ref<'idle' | 'loading' | 'ready' | 'failed'>('idle')
const expandedContent = computed(
  () => fullNode.value?.detail || fullNode.value?.summary || props.node.summary
)

const loadKnowledge = async (event: Event) => {
  const details = event.currentTarget as HTMLDetailsElement
  if (!details.open || loadState.value !== 'idle') return
  loadState.value = 'loading'
  try {
    fullNode.value = await api.getNode(props.node.node_id)
    loadState.value = 'ready'
  } catch (error) {
    console.error(`Failed to load cited knowledge ${props.node.node_id}:`, error)
    loadState.value = 'failed'
  }
}
</script>

<template>
  <details
    class="inline-knowledge-citation"
    :data-citation-node-id="node.node_id"
    @toggle="loadKnowledge"
  >
    <summary>
      <span class="citation-index">K{{ citationIndex + 1 }}</span>
      <span class="citation-copy">
        <strong>{{ node.title }}</strong>
        <small>{{ node.summary }}</small>
      </span>
      <span class="citation-toggle material-symbols-outlined" aria-hidden="true">
        expand_more
      </span>
    </summary>

    <div class="citation-detail" data-citation-detail>
      <div v-if="loadState === 'loading'" class="citation-loading" role="status">
        <span class="material-symbols-outlined" aria-hidden="true">progress_activity</span>
        正在载入知识点
      </div>
      <template v-else>
        <MarkdownContent :content="expandedContent" />
        <p v-if="loadState === 'failed'" class="citation-fallback-note">
          完整内容暂时无法载入，当前显示知识点摘要。
        </p>
        <a
          :href="href"
          target="_blank"
          rel="noopener noreferrer"
          :aria-label="`Open ${node.title} in a new tab`"
        >
          打开完整知识页
          <span class="material-symbols-outlined" aria-hidden="true">open_in_new</span>
        </a>
      </template>
    </div>
  </details>
</template>

<style scoped>
.inline-knowledge-citation {
  overflow: hidden;
  border: 1px solid rgb(var(--color-on-surface-rgb) / 0.085);
  border-radius: 11px;
  background: color-mix(
    in srgb,
    var(--color-surface-container-lowest) 92%,
    var(--color-primary-fixed)
  );
  font-family: var(--font-sans);
  transition: border-color 150ms ease, background-color 150ms ease;
}

.inline-knowledge-citation[open] {
  border-color: rgb(var(--color-primary-rgb) / 0.2);
  background: var(--color-surface-container-lowest);
}

.inline-knowledge-citation summary {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  min-height: 48px;
  padding: 8px 10px;
  list-style: none;
  cursor: pointer;
}

.inline-knowledge-citation summary::-webkit-details-marker {
  display: none;
}

.inline-knowledge-citation summary:hover,
.inline-knowledge-citation summary:focus-visible {
  background: var(--color-primary-fixed);
}

.inline-knowledge-citation summary:focus-visible {
  outline: 2px solid rgb(var(--color-primary-rgb) / 0.24);
  outline-offset: -2px;
}

.citation-index {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-size: 9px;
  font-weight: 750;
}

.citation-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.citation-copy strong {
  overflow: hidden;
  color: var(--color-on-surface);
  font-size: 11px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-copy small {
  overflow: hidden;
  color: var(--color-on-surface-variant);
  font-size: 10px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-toggle {
  color: var(--color-on-surface-variant);
  font-size: 17px;
  transition: transform 150ms ease;
}

.inline-knowledge-citation[open] .citation-toggle {
  transform: rotate(180deg);
}

.citation-detail {
  max-height: min(460px, 58vh);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 12px 14px 13px 47px;
  border-top: 1px solid rgb(var(--color-on-surface-rgb) / 0.07);
  color: var(--color-on-surface);
  font-family: var(--font-serif);
  font-size: 14px;
  line-height: 1.55;
  scrollbar-color: rgb(var(--color-on-surface-rgb) / 0.16) transparent;
  scrollbar-width: thin;
}

.citation-detail :deep(.markdown-content > :first-child) {
  margin-top: 0;
}

.citation-detail :deep(.markdown-content > :last-child) {
  margin-bottom: 0;
}

.citation-detail > a {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-top: 10px;
  color: var(--color-primary);
  font-family: var(--font-sans);
  font-size: 9px;
  font-weight: 650;
  text-decoration: none;
  text-transform: uppercase;
}

.citation-detail > a .material-symbols-outlined {
  font-size: 12px;
}

.citation-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 10px;
}

.citation-loading .material-symbols-outlined {
  font-size: 14px;
  animation: citation-spin 1.1s linear infinite;
}

.citation-fallback-note {
  margin: 8px 0 0;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 9px;
}

@keyframes citation-spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
  .citation-detail {
    padding-left: 14px;
  }
}
</style>
