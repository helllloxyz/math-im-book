<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeAnchor, SessionMessage } from '../../services/api'
import MarkdownContent from '../common/MarkdownContent.vue'

const props = defineProps<{
  message: SessionMessage
  assistantName?: string
  canRegenerate?: boolean
  isLoading?: boolean
  sessionId?: string | null
}>()

const emit = defineEmits<{
  (e: 'fork', messageId: string): void
  (e: 'copy', content: string): void
  (e: 'regenerate', messageId: string): void
  (e: 'anchor-click', anchor: KnowledgeAnchor): void
  (e: 'review-state', messageId: string): void
}>()

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

const openAnchor = (anchor: KnowledgeAnchor) => {
  if (!canOpenAnchor(anchor)) return
  emit('anchor-click', anchor)
}

const copyContent = () => {
  navigator.clipboard.writeText(props.message.content)
  emit('copy', props.message.content)
}
</script>

<template>
  <div class="mb-6 flex flex-col group" :class="isAssistant ? 'items-start' : 'items-center'">
    <!-- Identity Header (Stitch style) -->
    <div v-if="isAssistant" class="flex items-center gap-2 mb-3 px-1.5" data-assistant-header>
      <div
        class="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center text-on-primary shadow-sm"
        data-assistant-icon
      >
        <span class="material-symbols-outlined text-base">functions</span>
      </div>
      <div>
        <p class="stitch-label text-primary">{{ roleLabel }}</p>
        <p class="font-sans text-[10px] text-on-surface-variant/60">Synthesized Proof Engine</p>
      </div>
    </div>

    <!-- Article Style Container -->
    <article
      :class="[
        'w-full transition-all duration-500',
        isAssistant 
          ? 'stitch-article' 
          : 'max-w-2xl bg-surface-container-high/40 rounded-xl p-4 border-l-4 border-primary/20 italic font-serif'
      ]"
    >
      <div
        class="space-y-3"
        :data-selection-source="isThinking ? undefined : 'chat-message'"
        :data-message-id="isThinking ? undefined : message.message_id"
        :data-session-id="isThinking ? undefined : sessionId || undefined"
      >
        <div
          v-if="isThinking"
          class="inline-flex items-center gap-3 text-sm text-on-surface-variant/70 animate-pulse"
          data-thinking-indicator
        >
          <span class="material-symbols-outlined animate-spin text-primary">progress_activity</span>
          思考中...
        </div>
        <MarkdownContent v-else :content="message.content" />
      </div>

      <!-- Anchors / Knowledge Links -->
      <div
        v-if="isAssistant && assistantAnchors.length"
        class="mt-4 flex flex-wrap gap-1.5 pt-3 border-t border-outline-variant/10"
        data-anchor-list
      >
        <button
          v-for="anchor in assistantAnchors"
          :key="anchor.anchor_id"
          :data-anchor-id="anchor.anchor_id"
          :disabled="!canOpenAnchor(anchor)"
          class="inline-flex items-center rounded-full px-2 py-0.5 font-sans text-[11px] font-medium transition-all"
          :class="canOpenAnchor(anchor)
            ? 'bg-primary-fixed text-primary hover:bg-primary-container hover:text-on-primary'
            : 'bg-surface-container-high text-on-surface-variant/40 opacity-60'"
          @click="openAnchor(anchor)"
        >
          <span>{{ anchor.label }}</span>
        </button>
      </div>

      <!-- Orchestration Plan Strip -->
      <div
        v-if="isAssistant && message.assistant_context.orchestration_plan"
        class="mt-3 flex items-start justify-between gap-2 rounded-md border border-outline-variant/15 bg-surface-container-low px-2.5 py-1.5"
        data-agent-plan-strip
      >
        <p class="font-sans text-[11px] leading-snug text-on-surface-variant">
          {{ message.assistant_context.orchestration_plan.user_visible_summary }}
        </p>
        <button
          class="shrink-0 rounded bg-primary-fixed px-2 py-0.5 font-sans text-[9px] uppercase tracking-widest text-primary hover:bg-primary transition-colors"
          @click="emit('review-state', message.message_id)"
        >
          Review
        </button>
      </div>

      <!-- Interaction Bar (Only for Assistant) -->
      <div
        v-if="isAssistant"
        class="mt-0 flex items-center justify-end gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
        data-message-actions
      >
        <button 
          @click="emit('fork', message.message_id)" 
          class="w-6 h-6 flex items-center justify-center rounded-full text-on-surface-variant/40 hover:bg-primary-fixed hover:text-primary transition-colors"
          title="Fork session"
          data-message-action
        >
          <span class="material-symbols-outlined text-[11px]">alt_route</span>
        </button>
        <button 
          @click="copyContent" 
          class="w-6 h-6 flex items-center justify-center rounded-full text-on-surface-variant/40 hover:bg-primary-fixed hover:text-primary transition-colors"
          title="Copy"
          data-message-action
        >
          <span class="material-symbols-outlined text-[11px]">content_copy</span>
        </button>
        <button
          v-if="canRegenerate"
          @click="emit('regenerate', message.message_id)" 
          class="w-6 h-6 flex items-center justify-center rounded-full text-on-surface-variant/40 hover:bg-primary-fixed hover:text-primary transition-colors"
          title="Regenerate"
          data-message-action
        >
          <span class="material-symbols-outlined text-[11px]">cached</span>
        </button>
      </div>
    </article>
  </div>
</template>
