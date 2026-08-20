<script setup lang="ts">
import { computed, ref } from 'vue'
import type { KnowledgeAnchor, SessionMessage } from '../../services/api'
import { buildWorkspaceHref } from '../../services/workspaceNavigation'
import MarkdownContent from '../common/MarkdownContent.vue'

const props = defineProps<{
  message: SessionMessage
  assistantName?: string
  canRegenerate?: boolean
  isLoading?: boolean
  sessionId?: string | null
}>()

const emit = defineEmits<{
  (event: 'copy', content: string): void
  (event: 'regenerate', messageId: string): void
}>()

const copied = ref(false)
const assistantAnchors = computed(() => props.message.assistant_context.anchors || [])
const isAssistant = computed(() => props.message.role === 'assistant')
const roleLabel = computed(() => (isAssistant.value ? props.assistantName || 'Gauss' : 'You'))
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
  <div class="message-row" :class="isAssistant ? 'assistant-message' : 'user-message'">
    <div v-if="isAssistant" class="message-identity" data-assistant-header>
      <div class="assistant-mark" data-assistant-icon>∑</div>
      <span>{{ roleLabel }}</span>
    </div>

    <article class="message-card" :class="{ 'question-card': !isAssistant }">
      <div
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

      <div v-if="isAssistant && assistantAnchors.length" class="knowledge-links" data-anchor-list>
        <span class="knowledge-label">Saved ideas</span>
        <template
          v-for="anchor in assistantAnchors"
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

      <div
        v-if="isAssistant && message.assistant_context.orchestration_plan"
        class="response-details"
        data-agent-plan-strip
      >
        <p>{{ message.assistant_context.orchestration_plan.user_visible_summary }}</p>
        <a
          :href="detailsHref"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open response details in a new tab"
          data-response-details-link
        >
          View details
          <span class="material-symbols-outlined">open_in_new</span>
        </a>
      </div>

      <div v-if="isAssistant && !isThinking" class="message-actions" data-message-actions>
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
  margin-bottom: 26px;
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
  margin: 0 0 8px 3px;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.assistant-mark {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border-radius: 7px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-family: var(--font-serif);
  font-size: 14px;
}

.message-card {
  position: relative;
  width: 100%;
}

.assistant-message .message-card {
  padding: 24px 27px 10px;
  border: 1px solid rgb(var(--color-on-surface-rgb) / 0.075);
  border-radius: 16px;
  background: rgb(var(--color-surface-lowest-rgb) / 0.82);
  box-shadow: 0 1px 0 rgb(var(--color-on-surface-rgb) / 0.04);
}

.user-message .message-card {
  width: auto;
  max-width: 78%;
  padding: 12px 16px;
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
  line-height: 1.68;
}

.user-message .message-content {
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.55;
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

.knowledge-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 18px;
  padding-top: 14px;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--color-surface-container-low);
  font-family: var(--font-sans);
}

.response-details p {
  margin: 0;
  color: var(--color-on-surface-variant);
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
  min-height: 30px;
  margin-top: 4px;
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
  padding: 5px 7px;
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
    padding: 19px 18px 8px;
  }

  .user-message .message-card {
    max-width: 90%;
  }

  .message-actions {
    opacity: 1;
  }
}
</style>
