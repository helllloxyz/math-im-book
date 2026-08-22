<script setup lang="ts">
import { computed, ref } from 'vue'
import type { AgentProgressEvent, KnowledgeAnchor, OutlineNode, SessionMessage } from '../../services/api'
import { extractMarkdownHeadings, splitMarkdownByCitations } from '../../services/markdown'
import { buildWorkspaceHref } from '../../services/workspaceNavigation'
import MarkdownContent from '../common/MarkdownContent.vue'
import InlineKnowledgeCitation from './InlineKnowledgeCitation.vue'

const props = defineProps<{
  message: SessionMessage
  assistantName?: string
  canRegenerate?: boolean
  isLoading?: boolean
  sessionId?: string | null
  knowledgeNodes?: OutlineNode[]
  agentSteps?: AgentProgressEvent[]
  approvalBusy?: boolean
}>()

const emit = defineEmits<{
  (event: 'copy', content: string): void
  (event: 'regenerate', messageId: string): void
  (event: 'approve-knowledge', messageId: string, draftIndexes: number[]): void
  (event: 'reject-knowledge', messageId: string): void
}>()

const copied = ref(false)
const isAnswerCollapsed = ref(false)
const isQuestionExpanded = ref(false)
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
const knowledgeGapCandidates = computed(() => agentPlan.value?.candidate_drafts || [])
const knowledgeAuthorization = computed(() => {
  const explicit = agentPlan.value?.authorization
  if (explicit) return explicit
  if (knowledgeGapCandidates.value.length) {
    return {
      mode: 'require_approval' as const,
      status: 'pending' as const,
      risk_level: 'medium' as const,
      policy: 'agent_decides' as const,
      operation: 'write_knowledge_nodes',
      reason: '这些候选知识会写入知识库，需要你确认。',
    }
  }
  return null
})
const shouldShowKnowledgeAuthorization = computed(
  () =>
    knowledgeGapCandidates.value.length > 0 &&
    knowledgeAuthorization.value?.status === 'pending'
)
const knowledgeGapTitle = computed(() => {
  const status = knowledgeAuthorization.value?.status
  if (status === 'auto_approved') return 'Agent 已自动处理知识补充'
  if (status === 'approved') return '已授权补充知识'
  if (status === 'denied') return '本次已跳过知识补充'
  return '发现知识缺口，需要授权'
})
const knowledgeAuthorizationLabel = computed(() => {
  const status = knowledgeAuthorization.value?.status
  const policy = knowledgeAuthorization.value?.policy || 'agent_decides'
  if (policy === 'full_auto' && status === 'auto_approved') return 'Full Auto · 已自动执行'
  if (policy === 'always_ask' && status === 'pending') return 'Always Ask · 等待确认'
  if (policy === 'agent_decides' && status === 'auto_approved') return 'Agent 决定 · 已自动授权'
  if (policy === 'agent_decides' && status === 'pending') return 'Agent 决定 · 等待确认'
  if (status === 'approved') return '用户已允许'
  if (status === 'denied') return '已跳过'
  return '等待你的决定'
})
const draftTypeLabel = (draftType: string) => {
  const labels: Record<string, string> = {
    missing_definition: '缺失定义',
    missing_detail: '缺失细节',
    missing_bridge: '缺失连接',
    definition: '定义',
    theorem: '定理',
    proof_skeleton: '证明骨架',
    example: '例子',
    counterexample: '反例',
    notation: '符号',
    bridge: '知识连接',
    summary: '总结',
  }
  return labels[draftType] || draftType.replaceAll('_', ' ')
}
const approveKnowledge = () => {
  emit(
    'approve-knowledge',
    props.message.message_id,
    knowledgeGapCandidates.value.map((_, index) => index)
  )
}
const isAssistant = computed(() => props.message.role === 'assistant')
const roleLabel = computed(() => (isAssistant.value ? props.assistantName || 'Gauss' : 'You'))
const questionPreview = computed(() => props.message.content.replace(/\s+/g, ' ').trim())
const answerOutline = computed(() => extractMarkdownHeadings(props.message.content))
const answerCitationSections = computed(() =>
  splitMarkdownByCitations(props.message.content, referencedNodes.value.length)
)
const answerContentId = computed(
  () => `answer-${props.message.message_id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
)
const questionContentId = computed(
  () => `question-${props.message.message_id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
)
const isDeferredAnswerPending = computed(
  () =>
    isAssistant.value &&
    agentPlan.value?.route === 'ask_before_persist' &&
    knowledgeAuthorization.value?.status === 'approved' &&
    assistantAnchors.value.some((anchor) =>
      ['pending', 'queued', 'running'].includes(anchor.status)
    )
)
const isThinking = computed(
  () =>
    isAssistant.value &&
    (
      isDeferredAnswerPending.value ||
      (
        !props.message.content.trim() &&
        (props.isLoading || props.message.message_id === 'streaming-assistant')
      )
    )
)

const canOpenAnchor = (anchor: KnowledgeAnchor) => anchor.status === 'ready' && !!anchor.node_id

const citationHref = (nodeId: string) => buildWorkspaceHref({
  view: 'knowledge',
  sessionId: props.sessionId || undefined,
  nodeId,
})

const anchorHref = (anchor: KnowledgeAnchor) => buildWorkspaceHref({
  view: 'knowledge',
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

      <div v-if="!isAssistant" class="question-details" data-question-details>
        <button
          class="question-toggle-button"
          type="button"
          :aria-controls="questionContentId"
          :aria-expanded="isQuestionExpanded"
          :aria-label="isQuestionExpanded ? 'Collapse question' : 'Expand question'"
          :title="isQuestionExpanded ? 'Collapse question' : 'Expand question'"
          data-question-summary
          @click="isQuestionExpanded = !isQuestionExpanded"
        >
          <span class="material-symbols-outlined question-toggle" aria-hidden="true">
            expand_more
          </span>
        </button>
        <span
          v-if="!isQuestionExpanded"
          :id="questionContentId"
          class="question-preview"
          data-selection-source="chat-message"
          :data-message-id="message.message_id"
          :data-session-id="sessionId || undefined"
        >{{ questionPreview }}</span>
        <div
          v-else
          :id="questionContentId"
          class="message-content question-content"
          data-selection-source="chat-message"
          :data-message-id="message.message_id"
          :data-session-id="sessionId || undefined"
        >
          <MarkdownContent :content="message.content" />
        </div>
      </div>

      <div
        v-if="isAssistant"
        v-show="!isAnswerCollapsed"
        class="message-content"
        :data-selection-source="isThinking ? undefined : 'chat-message'"
        :data-message-id="isThinking ? undefined : message.message_id"
        :data-session-id="isThinking ? undefined : sessionId || undefined"
      >
        <div v-if="isThinking" class="agent-run-progress" data-thinking-indicator>
          <div class="agent-run-heading">
            <span class="agent-run-mark">A</span>
            <div>
              <strong>Agent 正在处理</strong>
              <small>知识上下文准备完成后开始回答</small>
            </div>
          </div>
          <ol v-if="agentSteps?.length" data-agent-run-steps>
            <li
              v-for="step in agentSteps"
              :key="step.stage"
              :class="`is-${step.state}`"
              :data-agent-stage="step.stage"
            >
              <span class="agent-step-state material-symbols-outlined" aria-hidden="true">
                {{ step.state === 'completed' ? 'check_circle' : step.state === 'failed' ? 'error' : 'progress_activity' }}
              </span>
              <span class="agent-step-copy">
                <strong>{{ step.label }}</strong>
                <small v-if="step.detail">{{ step.detail }}</small>
              </span>
            </li>
          </ol>
          <div v-else class="thinking-indicator">
            <span></span><span></span><span></span>
            <em>正在启动任务</em>
          </div>
        </div>
        <template v-else>
          <template
            v-for="(section, sectionIndex) in answerCitationSections"
            :key="`${message.message_id}-section-${sectionIndex}`"
          >
            <MarkdownContent v-if="section.content" :content="section.content" />
            <div
              v-if="section.citationIndexes.length"
              class="inline-knowledge-citations"
              data-knowledge-citations
            >
              <InlineKnowledgeCitation
                v-for="citationIndex in section.citationIndexes"
                :key="referencedNodes[citationIndex].node_id"
                :citation-index="citationIndex"
                :node="referencedNodes[citationIndex]"
                :href="citationHref(referencedNodes[citationIndex].node_id)"
              />
            </div>
          </template>
        </template>
      </div>

      <section
        v-if="isAssistant && shouldShowKnowledgeAuthorization && knowledgeAuthorization"
        v-show="!isAnswerCollapsed"
        class="knowledge-gap-card"
        :class="`is-${knowledgeAuthorization.status}`"
        data-knowledge-gap-card
      >
        <header>
          <span class="knowledge-gap-icon material-symbols-outlined" aria-hidden="true">
            {{ knowledgeAuthorization.status === 'denied' ? 'block' : 'account_tree' }}
          </span>
          <div>
            <strong>{{ knowledgeGapTitle }}</strong>
            <small>{{ knowledgeAuthorization.reason }}</small>
          </div>
          <span class="knowledge-authorization-status">
            {{ knowledgeAuthorizationLabel }}
          </span>
        </header>

        <ol>
          <li v-for="(draft, index) in knowledgeGapCandidates" :key="`${draft.title}-${index}`">
            <span>{{ index + 1 }}</span>
            <div>
              <strong>{{ draft.title }}</strong>
              <small>{{ draftTypeLabel(draft.draft_type) }} · {{ draft.reason }}</small>
            </div>
          </li>
        </ol>

        <footer>
          <div class="knowledge-gap-scope">
            <span>来源：AI 根据当前 Scope 编译</span>
            <span>写入：{{ agentPlan?.knowledge_scope_label || '全部知识' }}</span>
          </div>
          <div
            v-if="knowledgeAuthorization.status === 'pending'"
            class="knowledge-approval-actions"
          >
            <button
              type="button"
              class="knowledge-deny-button"
              :disabled="approvalBusy"
              data-reject-knowledge
              @click="emit('reject-knowledge', message.message_id)"
            >
              本次跳过
            </button>
            <button
              type="button"
              class="knowledge-approve-button"
              :disabled="approvalBusy"
              data-approve-knowledge
              @click="approveKnowledge"
            >
              <span v-if="approvalBusy" class="material-symbols-outlined is-spinning">progress_activity</span>
              {{ approvalBusy ? '正在处理' : `允许并生成 ${knowledgeGapCandidates.length} 个节点` }}
            </button>
          </div>
        </footer>
      </section>

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
  border: 1px solid rgb(var(--color-accent-rgb) / 0.13);
  border-radius: 14px 14px 4px 14px;
  color: var(--color-on-surface);
  background: color-mix(
    in srgb,
    var(--color-accent-container) 62%,
    var(--color-surface-container-lowest)
  );
  box-shadow: 0 1px 0 rgb(var(--color-accent-rgb) / 0.045);
  font-family: var(--font-sans);
  font-size: 13px;
}

.message-content {
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.58;
}

.question-toggle-button {
  position: absolute;
  right: 0;
  bottom: 0;
  z-index: 1;
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 6px;
  color: color-mix(in srgb, var(--color-accent) 54%, var(--color-on-surface-variant));
  background: transparent;
  cursor: pointer;
  user-select: none;
  transition: color 140ms ease, background-color 140ms ease;
}

.question-details {
  position: relative;
  min-width: 0;
  padding-right: 24px;
}

.question-toggle-button:focus-visible {
  outline: 2px solid rgb(var(--color-accent-rgb) / 0.45);
  outline-offset: 1px;
}

.question-preview {
  display: -webkit-box;
  min-width: 0;
  overflow: hidden;
  color: var(--color-on-surface);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  line-height: 1.45;
  user-select: text;
  white-space: normal;
}

.question-toggle {
  color: var(--color-on-surface-variant);
  font-size: 16px;
  transition: transform 140ms ease;
}

.question-toggle-button:hover {
  color: var(--color-accent);
  background: rgb(var(--color-accent-rgb) / 0.07);
}

.question-toggle-button[aria-expanded="true"] .question-toggle {
  transform: rotate(180deg);
}

.question-content {
  margin-top: 0;
  padding-right: 2px;
  padding-bottom: 14px;
  padding-top: 0;
  user-select: text;
}

.user-message .message-content,
.question-toggle-button {
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

.agent-run-progress {
  display: grid;
  gap: 14px;
  padding: 2px 0 4px;
  font-family: var(--font-sans);
}

.knowledge-gap-card {
  display: grid;
  gap: 14px;
  margin-top: 18px;
  padding: 15px;
  border: 1px solid rgb(var(--color-primary-rgb) / 0.18);
  border-radius: 14px;
  background: linear-gradient(145deg, var(--color-primary-fixed), var(--color-surface-container-lowest) 72%);
  font-family: var(--font-sans);
}

.knowledge-gap-card.is-denied {
  border-color: var(--color-outline-variant);
  background: var(--color-surface-container-low);
}

.knowledge-gap-card > header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: start;
  gap: 10px;
}

.knowledge-gap-card > header > div,
.knowledge-gap-card li > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.knowledge-gap-card strong {
  color: var(--color-on-surface);
  font-size: 12px;
  font-weight: 650;
}

.knowledge-gap-card small,
.knowledge-gap-scope {
  color: var(--color-on-surface-variant);
  font-size: 10px;
  line-height: 1.45;
}

.knowledge-gap-icon {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  color: var(--color-primary);
  background: var(--color-surface-container-lowest);
  font-size: 17px;
}

.knowledge-authorization-status {
  padding: 4px 7px;
  border-radius: 999px;
  color: var(--color-primary);
  background: var(--color-surface-container-lowest);
  font-size: 9px;
  font-weight: 650;
  white-space: nowrap;
}

.knowledge-gap-card ol {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.knowledge-gap-card li {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 10px;
  background: var(--color-surface-container-lowest);
}

.knowledge-gap-card li > span {
  display: grid;
  width: 20px;
  height: 20px;
  place-items: center;
  border-radius: 6px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-size: 9px;
  font-weight: 700;
}

.knowledge-gap-card > footer {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-gap-scope {
  display: grid;
  gap: 2px;
}

.knowledge-approval-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 7px;
}

.knowledge-approval-actions button {
  min-height: 31px;
  padding: 0 11px;
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 650;
}

.knowledge-deny-button {
  color: var(--color-on-surface-variant);
  border-color: var(--color-outline-variant) !important;
  background: var(--color-surface-container-lowest);
}

.knowledge-approve-button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.knowledge-approval-actions button:disabled {
  cursor: wait;
  opacity: 0.58;
}

.knowledge-approve-button .material-symbols-outlined {
  font-size: 14px;
}

.is-spinning {
  animation: spin 1.1s linear infinite;
}

.agent-run-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-run-heading > div,
.agent-step-copy {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.agent-run-heading strong {
  color: var(--color-on-surface);
  font-size: 12px;
  font-weight: 650;
}

.agent-run-heading small,
.agent-step-copy small {
  color: var(--color-on-surface-variant);
  font-size: 10px;
  line-height: 1.35;
}

.agent-run-mark {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  border-radius: 8px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-size: 10px;
  font-weight: 750;
}

.agent-run-progress ol {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0 0 0 4px;
  list-style: none;
}

.agent-run-progress li {
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  align-items: start;
  gap: 8px;
  color: var(--color-on-surface-variant);
}

.agent-run-progress li.is-running {
  color: var(--color-primary);
}

.agent-run-progress li.is-failed {
  color: var(--color-danger);
}

.agent-step-state {
  margin-top: 1px;
  font-size: 16px;
}

.agent-run-progress li.is-running .agent-step-state {
  animation: spin 1.1s linear infinite;
}

.agent-step-copy strong {
  color: currentColor;
  font-size: 11px;
  font-weight: 550;
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

.inline-knowledge-citations {
  display: grid;
  gap: 6px;
  margin: 8px 0 13px;
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

@keyframes spin {
  to { transform: rotate(360deg); }
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

  .knowledge-gap-card > header {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .knowledge-authorization-status {
    grid-column: 2;
    justify-self: start;
  }

  .knowledge-gap-card > footer {
    align-items: stretch;
    flex-direction: column;
  }

  .knowledge-approval-actions button {
    flex: 1;
  }
}
</style>
