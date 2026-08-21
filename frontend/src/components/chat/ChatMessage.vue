<script setup lang="ts">
import { computed, ref } from 'vue'
import type { KnowledgeAnchor, OutlineNode, SessionMessage } from '../../services/api'
import { extractMarkdownHeadings } from '../../services/markdown'
import { buildWorkspaceHref } from '../../services/workspaceNavigation'
import MarkdownContent from '../common/MarkdownContent.vue'

const props = defineProps<{
  message: SessionMessage
  assistantName?: string
  canRegenerate?: boolean
  isLoading?: boolean
  sessionId?: string | null
  knowledgeNodes?: OutlineNode[]
}>()

const emit = defineEmits<{
  (event: 'copy', content: string): void
  (event: 'regenerate', messageId: string): void
  (event: 'open-node', nodeId: string): void
}>()

const copied = ref(false)
const isAnswerCollapsed = ref(false)
const assistantAnchors = computed(() => props.message.assistant_context.anchors || [])
const referencedNodes = computed(() => {
  const nodesById = new Map((props.knowledgeNodes || []).map((node) => [node.id, node]))
  return props.message.assistant_context.referenced_node_ids.flatMap((nodeId) => {
    const node = nodesById.get(nodeId)
    return node ? [{ node_id: node.id, title: node.title, summary: node.summary, type: node.type }] : []
  })
})
const referencedNodeIds = computed(() => new Set(referencedNodes.value.map((node) => node.node_id)))
const knowledgeChangeAnchors = computed(() =>
  assistantAnchors.value.filter((anchor) => !anchor.node_id || !referencedNodeIds.value.has(anchor.node_id))
)
const agentPlan = computed(() => props.message.assistant_context.orchestration_plan || null)
const strategyLabel = computed(() =>
  agentPlan.value?.strategy_mode === 'top-down' ? 'Top Down' : 'Raw'
)
const intentLabel = computed(() => {
  const intent = agentPlan.value?.intent || ''
  const labels: Record<string, string> = {
    broad_exploratory: '系统理解与知识梳理',
    broad_overview: '建立整体理解',
    teach_concept: '理解一个概念',
    definition: '查清定义与边界',
    proof: '理解或验证证明',
    compact: '整理当前上下文',
    clarify: '澄清问题',
  }
  if (labels[intent]) return labels[intent]
  if (!intent) return '理解当前问题'
  if (intent.length > 32 || /[_\n]/.test(intent)) return '理解当前问题的核心诉求'
  return intent
})
const knowledgeResultLabel = computed(() => {
  const candidates = agentPlan.value?.candidate_drafts.length || 0
  if (candidates) return `发现 ${candidates} 个候选知识点`
  if (knowledgeChangeAnchors.value.length) return `知识库有 ${knowledgeChangeAnchors.value.length} 项变化`
  return '本轮不修改知识库'
})
const isAssistant = computed(() => props.message.role === 'assistant')
const roleLabel = computed(() => (isAssistant.value ? props.assistantName || 'Gauss' : 'You'))
const questionPreview = computed(() => props.message.content.replace(/\s+/g, ' ').trim())
const answerOutline = computed(() => extractMarkdownHeadings(props.message.content))
const answerContentId = computed(
  () => `answer-${props.message.message_id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
)
const isThinking = computed(
  () =>
    isAssistant.value &&
    !props.message.content.trim() &&
    (props.isLoading || props.message.message_id === 'streaming-assistant')
)

const canOpenAnchor = (anchor: KnowledgeAnchor) => anchor.status === 'ready' && !!anchor.node_id

const anchorHref = (anchor: KnowledgeAnchor) => buildWorkspaceHref({
  view: 'library',
  sessionId: props.sessionId || undefined,
  nodeId: anchor.node_id || undefined,
})

const detailsHref = computed(() => buildWorkspaceHref({
  view: 'details',
  sessionId: props.sessionId || undefined,
  messageId: props.message.message_id,
}))

const forkHref = computed(() => buildWorkspaceHref({
  view: 'fork',
  sessionId: props.sessionId || undefined,
  messageId: props.message.message_id,
}))

const copyContent = async () => {
  await navigator.clipboard.writeText(props.message.content)
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1200)
  emit('copy', props.message.content)
}
</script>

<template>
  <div
    class="message-row"
    :class="[
      isAssistant ? 'assistant-message' : 'user-message',
      { 'answer-collapsed': isAssistant && isAnswerCollapsed },
    ]"
  >
    <div v-if="isAssistant" class="message-identity" data-assistant-header>
      <div class="assistant-mark" data-assistant-icon>∑</div>
      <span>{{ roleLabel }}</span>
      <button
        v-if="!isThinking"
        class="answer-collapse-button"
        type="button"
        :aria-controls="answerContentId"
        :aria-expanded="!isAnswerCollapsed"
        :aria-label="isAnswerCollapsed ? 'Expand answer' : 'Collapse answer'"
        :title="isAnswerCollapsed ? 'Expand answer' : 'Collapse answer'"
        data-answer-collapse
        @click="isAnswerCollapsed = !isAnswerCollapsed"
      >
        <span class="material-symbols-outlined" aria-hidden="true">
          {{ isAnswerCollapsed ? 'expand_more' : 'expand_less' }}
        </span>
      </button>
    </div>

    <article
      :id="isAssistant ? answerContentId : undefined"
      class="message-card"
      :class="{ 'question-card': !isAssistant }"
    >
      <nav
        v-if="isAssistant"
        v-show="isAnswerCollapsed"
        class="answer-outline"
        aria-label="Answer outline"
        data-answer-outline
      >
        <span class="answer-outline-label">Answer outline</span>
        <ol v-if="answerOutline.length">
          <li
            v-for="(heading, index) in answerOutline"
            :key="`${heading.level}-${index}-${heading.text}`"
            :style="{ '--outline-depth': heading.level - 1 }"
          >
            <span class="outline-marker" aria-hidden="true"></span>
            <span>{{ heading.text }}</span>
          </li>
        </ol>
        <p v-else class="answer-outline-empty">No section headings in this answer.</p>
      </nav>

      <details v-if="!isAssistant" class="question-details" data-question-details>
        <summary data-question-summary>
          <span class="question-label">Question</span>
          <span class="question-preview">{{ questionPreview }}</span>
          <span class="material-symbols-outlined question-toggle" aria-hidden="true">
            expand_more
          </span>
        </summary>
        <div
          class="message-content question-content"
          data-selection-source="chat-message"
          :data-message-id="message.message_id"
          :data-session-id="sessionId || undefined"
        >
          <MarkdownContent :content="message.content" />
        </div>
      </details>

      <div
        v-if="isAssistant"
        v-show="!isAnswerCollapsed"
        class="message-content"
        :data-selection-source="isThinking ? undefined : 'chat-message'"
        :data-message-id="isThinking ? undefined : message.message_id"
        :data-session-id="isThinking ? undefined : sessionId || undefined"
      >
        <div v-if="isThinking" class="thinking-indicator" data-thinking-indicator>
          <span></span><span></span><span></span>
          <em>Working through it</em>
        </div>
        <MarkdownContent v-else :content="message.content" />
      </div>

      <div
        v-if="isAssistant && referencedNodes.length"
        v-show="!isAnswerCollapsed"
        class="knowledge-citations"
        data-knowledge-citations
      >
        <div class="citation-heading">
          <span>本轮引用</span>
          <small>{{ referencedNodes.length }} 个知识点 · 点击查看完整内容</small>
        </div>
        <button
          v-for="(citation, index) in referencedNodes"
          :key="citation.node_id"
          type="button"
          :data-citation-node-id="citation.node_id"
          @click="emit('open-node', citation.node_id)"
        >
          <span class="citation-index">K{{ index + 1 }}</span>
          <span class="citation-copy">
            <strong>{{ citation.title }}</strong>
            <small>{{ citation.summary }}</small>
          </span>
          <span class="material-symbols-outlined" aria-hidden="true">chevron_right</span>
        </button>
      </div>

      <div
        v-if="isAssistant && knowledgeChangeAnchors.length"
        v-show="!isAnswerCollapsed"
        class="knowledge-links"
        data-anchor-list
      >
        <span class="knowledge-label">知识库变化</span>
        <template
          v-for="anchor in knowledgeChangeAnchors"
          :key="anchor.anchor_id"
        >
          <a
            v-if="canOpenAnchor(anchor)"
            :data-anchor-id="anchor.anchor_id"
            :href="anchorHref(anchor)"
            target="_blank"
            rel="noopener noreferrer"
            :aria-label="`Open ${anchor.label} in a new tab`"
          >
            {{ anchor.label }}
            <span class="material-symbols-outlined">open_in_new</span>
          </a>
          <button
            v-else
            :data-anchor-id="anchor.anchor_id"
            type="button"
            disabled
          >
            {{ anchor.label }}
            <span class="anchor-status">{{ anchor.status }}</span>
          </button>
        </template>
      </div>

      <details
        v-if="isAssistant && agentPlan"
        v-show="!isAnswerCollapsed"
        class="response-details"
        data-agent-plan-strip
      >
        <summary>
          <span class="agent-plan-label">Agent</span>
          <strong>{{ strategyLabel }}</strong>
          <span>{{ agentPlan.knowledge_scope_label }}</span>
          <span>引用 {{ referencedNodes.length }}</span>
          <span class="material-symbols-outlined" aria-hidden="true">expand_more</span>
        </summary>
        <div class="agent-plan-body">
          <dl>
            <div><dt>我理解了什么</dt><dd>{{ intentLabel }}</dd></div>
            <div><dt>我准备怎么做</dt><dd>{{ agentPlan.user_visible_summary }}</dd></div>
            <div v-if="agentPlan.strategy_reason"><dt>为什么这样做</dt><dd>{{ agentPlan.strategy_reason }}</dd></div>
            <div><dt>我用了什么</dt><dd>{{ agentPlan.knowledge_scope_label }} · {{ referencedNodes.length }} 个引用</dd></div>
            <div><dt>我产生了什么</dt><dd>{{ knowledgeResultLabel }}</dd></div>
          </dl>
          <a
            :href="detailsHref"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open response details in a new tab"
            data-response-details-link
          >
            View details · 查看完整处理详情
            <span class="material-symbols-outlined">open_in_new</span>
          </a>
        </div>
      </details>

      <div
        v-if="isAssistant && !isThinking"
        v-show="!isAnswerCollapsed"
        class="message-actions"
        data-message-actions
      >
        <a
          :href="forkHref"
          target="_blank"
          rel="noopener noreferrer"
          title="Fork conversation in a new tab"
          aria-label="Fork conversation in a new tab"
          data-message-action
          data-fork-link
        >
          <span class="material-symbols-outlined">alt_route</span>
          Fork
        </a>
        <button type="button" title="Copy response" data-message-action @click="copyContent">
          <span class="material-symbols-outlined">{{ copied ? 'check' : 'content_copy' }}</span>
          {{ copied ? 'Copied' : 'Copy' }}
        </button>
        <button
          v-if="canRegenerate"
          type="button"
          title="Regenerate response"
          data-message-action
          @click="emit('regenerate', message.message_id)"
        >
          <span class="material-symbols-outlined">refresh</span>
          Retry
        </button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.message-row {
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;
}

.assistant-message {
  align-items: stretch;
}

.user-message {
  align-items: flex-end;
}

.message-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 5px 3px;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.assistant-mark {
  display: grid;
  width: 21px;
  height: 21px;
  place-items: center;
  border-radius: 7px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-family: var(--font-serif);
  font-size: 12px;
}

.answer-collapse-button {
  display: grid;
  width: 23px;
  height: 23px;
  place-items: center;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 6px;
  color: color-mix(in srgb, var(--color-on-surface-variant) 48%, transparent);
  background: transparent;
  transition: color 140ms ease, background-color 140ms ease;
}

.answer-collapse-button:hover,
.answer-collapse-button:focus-visible {
  color: color-mix(in srgb, var(--color-on-surface-variant) 76%, transparent);
  background: rgb(var(--color-on-surface-rgb) / 0.045);
}

.answer-collapse-button:focus-visible {
  outline: 2px solid rgb(var(--color-on-surface-rgb) / 0.18);
  outline-offset: 2px;
}

.answer-collapse-button .material-symbols-outlined {
  font-size: 16px;
}

.message-card {
  position: relative;
  width: 100%;
}

.assistant-message .message-card {
  padding: 18px 22px 6px;
  border: 1px solid rgb(var(--color-on-surface-rgb) / 0.075);
  border-radius: 16px;
  background: rgb(var(--color-surface-lowest-rgb) / 0.82);
  box-shadow: 0 1px 0 rgb(var(--color-on-surface-rgb) / 0.04);
}

.answer-collapsed .message-card {
  padding: 12px 18px;
}

.answer-outline {
  font-family: var(--font-sans);
}

.answer-outline-label {
  display: block;
  margin-bottom: 7px;
  color: color-mix(in srgb, var(--color-on-surface-variant) 70%, transparent);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.answer-outline ol {
  display: grid;
  gap: 3px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.answer-outline li {
  display: flex;
  min-height: 23px;
  align-items: center;
  gap: 8px;
  padding-left: calc(var(--outline-depth) * 14px);
  color: var(--color-on-surface);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
}

.outline-marker {
  width: 5px;
  height: 5px;
  flex: 0 0 5px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--color-primary) 62%, transparent);
}

.answer-outline-empty {
  margin: 0;
  color: var(--color-on-surface-variant);
  font-size: 11px;
  line-height: 1.4;
}

.user-message .message-card {
  width: auto;
  max-width: 82%;
  padding: 8px 11px;
  border: 1px solid rgb(var(--color-primary-rgb) / 0.14);
  border-radius: 14px 14px 4px 14px;
  color: var(--color-on-surface);
  background: var(--color-primary-fixed);
  box-shadow: 0 1px 0 rgb(var(--color-primary-rgb) / 0.06);
  font-family: var(--font-sans);
  font-size: 13px;
}

.message-content {
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.58;
}

.question-details summary {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  list-style: none;
  cursor: pointer;
  user-select: none;
}

.question-details summary::-webkit-details-marker {
  display: none;
}

.question-details summary:focus-visible {
  border-radius: 5px;
  outline: 2px solid rgb(var(--color-primary-rgb) / 0.45);
  outline-offset: 3px;
}

.question-label {
  flex: 0 0 auto;
  color: color-mix(in srgb, var(--color-primary) 82%, var(--color-on-surface));
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.question-preview {
  min-width: 0;
  overflow: hidden;
  color: var(--color-on-surface);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.question-toggle {
  flex: 0 0 auto;
  margin-left: 1px;
  color: var(--color-on-surface-variant);
  font-size: 16px;
  transition: transform 140ms ease;
}

.question-details[open] .question-toggle {
  transform: rotate(180deg);
}

.question-details[open] .question-preview {
  display: none;
}

.question-content {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgb(var(--color-primary-rgb) / 0.12);
}

.user-message .message-content,
.question-details summary {
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.45;
}

.user-message :deep(.markdown-content) {
  color: var(--color-on-surface);
  --tw-prose-body: var(--color-on-surface);
  --tw-prose-headings: var(--color-on-surface);
  --tw-prose-links: var(--color-primary);
  --tw-prose-bold: var(--color-on-surface);
  --tw-prose-counters: var(--color-on-surface-variant);
  --tw-prose-bullets: var(--color-on-surface-variant);
  --tw-prose-quotes: var(--color-on-surface);
  --tw-prose-code: var(--color-on-surface);
}

.message-content :deep(.markdown-content > :first-child) {
  margin-top: 0;
}

.message-content :deep(.markdown-content > :last-child) {
  margin-bottom: 0;
}

.assistant-message :deep(.markdown-content p) {
  margin-bottom: 0.72em;
}

.assistant-message :deep(.markdown-content h1),
.assistant-message :deep(.markdown-content h2),
.assistant-message :deep(.markdown-content h3) {
  margin-top: 1.15em;
  margin-bottom: 0.6em;
}

.assistant-message :deep(.markdown-content .katex-display) {
  margin-top: 1.15em;
  margin-bottom: 1.15em;
}

.thinking-indicator {
  display: flex;
  min-height: 28px;
  align-items: center;
  gap: 5px;
  color: var(--color-on-surface-variant);
}

.thinking-indicator span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: thinking 1.2s ease-in-out infinite;
}

.thinking-indicator span:nth-child(2) { animation-delay: 120ms; }
.thinking-indicator span:nth-child(3) { animation-delay: 240ms; }

.thinking-indicator em {
  margin-left: 6px;
  font-size: 13px;
}

.knowledge-citations {
  display: grid;
  gap: 6px;
  margin-top: 14px;
  padding-top: 11px;
  border-top: 1px solid rgb(var(--color-on-surface-rgb) / 0.075);
  font-family: var(--font-sans);
}

.citation-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-on-surface-variant);
}

.citation-heading span {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.citation-heading small {
  font-size: 9px;
}

.knowledge-citations > button {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 8px 9px;
  border: 1px solid rgb(var(--color-on-surface-rgb) / 0.065);
  border-radius: 9px;
  color: var(--color-on-surface);
  background: var(--color-surface-container-lowest);
  text-align: left;
}

.knowledge-citations > button:hover,
.knowledge-citations > button:focus-visible {
  border-color: rgb(var(--color-primary-rgb) / 0.24);
  background: var(--color-primary-fixed);
}

.citation-index {
  display: grid;
  width: 27px;
  height: 27px;
  place-items: center;
  border-radius: 7px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-size: 9px;
  font-weight: 700;
}

.citation-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.citation-copy strong {
  overflow: hidden;
  font-size: 11px;
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

.knowledge-citations .material-symbols-outlined {
  color: var(--color-on-surface-variant);
  font-size: 16px;
}

.knowledge-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgb(var(--color-on-surface-rgb) / 0.075);
}

.knowledge-label {
  margin-right: 3px;
  color: color-mix(in srgb, var(--color-on-surface-variant) 72%, transparent);
  font-family: var(--font-sans);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.knowledge-links a,
.knowledge-links button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  border: 0;
  border-radius: 6px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-family: var(--font-sans);
  font-size: 10px;
  text-decoration: none;
}

.knowledge-links button:disabled {
  cursor: default;
  color: color-mix(in srgb, var(--color-on-surface-variant) 72%, transparent);
  background: var(--color-surface-container-low);
}

.knowledge-links .material-symbols-outlined {
  font-size: 12px;
}

.anchor-status {
  opacity: 0.65;
  font-size: 8px;
  text-transform: uppercase;
}

.response-details {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--color-surface-container-low);
  font-family: var(--font-sans);
}

.response-details summary {
  display: flex;
  align-items: center;
  gap: 7px;
  list-style: none;
  cursor: pointer;
  color: var(--color-on-surface-variant);
  font-size: 10px;
  line-height: 1.45;
}

.response-details summary::-webkit-details-marker {
  display: none;
}

.response-details summary strong {
  color: var(--color-primary);
}

.response-details summary .material-symbols-outlined {
  margin-left: auto;
  transition: transform 140ms ease;
}

.response-details[open] summary .material-symbols-outlined {
  transform: rotate(180deg);
}

.agent-plan-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.agent-plan-body {
  margin-top: 9px;
  padding-top: 9px;
  border-top: 1px solid rgb(var(--color-on-surface-rgb) / 0.075);
}

.agent-plan-body dl {
  display: grid;
  gap: 6px;
  margin: 0 0 8px;
}

.agent-plan-body dl > div {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: 10px;
}

.agent-plan-body dt {
  color: var(--color-on-surface-variant);
  font-size: 9px;
  font-weight: 700;
}

.agent-plan-body dd {
  margin: 0;
  color: var(--color-on-surface);
  font-size: 10px;
  line-height: 1.45;
}

.response-details a {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 3px;
  border: 0;
  color: var(--color-primary);
  background: transparent;
  font-size: 9px;
  font-weight: 600;
  text-decoration: none;
  text-transform: uppercase;
}

.response-details .material-symbols-outlined {
  font-size: 12px;
}

.message-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  min-height: 24px;
  margin-top: 1px;
  opacity: 0;
  transition: opacity 140ms ease;
}

.message-row:hover .message-actions,
.message-row:focus-within .message-actions {
  opacity: 1;
}

.message-actions a,
.message-actions button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border: 0;
  border-radius: 5px;
  color: color-mix(in srgb, var(--color-on-surface-variant) 78%, transparent);
  background: transparent;
  font-family: var(--font-sans);
  font-size: 9px;
  text-decoration: none;
}

.message-actions a:hover,
.message-actions button:hover {
  color: var(--color-primary);
  background: var(--color-primary-fixed);
}

.message-actions .material-symbols-outlined {
  font-size: 13px;
}

@keyframes thinking {
  0%, 100% { opacity: 0.26; transform: translateY(1px); }
  50% { opacity: 1; transform: translateY(-2px); }
}

@media (max-width: 640px) {
  .assistant-message .message-card {
    padding: 16px 16px 5px;
  }

  .user-message .message-card {
    max-width: 94%;
  }

  .message-actions {
    opacity: 1;
  }
}
</style>
