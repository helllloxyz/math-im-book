<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkspaceStore } from '../../stores/workspace'

const props = defineProps<{
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'ask', question: string): void
}>()

const store = useWorkspaceStore()
const {
  draftQuestion,
  answerStyles,
  selectedAnswerStyleId,
  strategyAgents,
  selectedStrategyAgentId,
  currentSession,
  errorMessage,
} = storeToRefs(store)

const selectableAnswerStyles = computed(() =>
  answerStyles.value.filter((style) => style.answer_style_id !== 'default')
)

const selectedAnswerStyleValue = computed({
  get: () => selectedAnswerStyleId.value || '',
  set: (value: string) => {
    selectedAnswerStyleId.value = value || null
  },
})

const isNewSession = computed(() => !currentSession.value?.session_id)

const submit = () => {
  if (!draftQuestion.value.trim() || props.loading) return
  const q = draftQuestion.value
  emit('ask', q)
  store.setDraftQuestion('')
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="mx-auto max-w-4xl w-full">
    <div
      data-chat-composer-shell
      class="relative flex flex-col gap-2 bg-surface-container-low rounded-2xl p-3 shadow-sm ghost-border"
    >
      <div data-chat-composer-input-row class="flex items-end gap-3">
        <textarea
          v-model="draftQuestion"
          @keydown="handleKeydown"
          placeholder="Inquire of the Scriptorium..."
          class="flex-1 bg-transparent border-none focus:ring-0 font-serif text-base leading-6 resize-none placeholder:text-on-surface-variant/40 outline-none"
          rows="2"
          :disabled="loading"
        ></textarea>
        <button
          @click="submit"
          :disabled="!draftQuestion.trim() || loading"
          class="w-10 h-10 bg-primary text-on-primary rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 disabled:cursor-not-allowed shrink-0"
          aria-label="Send message"
        >
          <span class="material-symbols-outlined text-[18px]">send</span>
        </button>
      </div>

      <div data-chat-composer-controls class="flex flex-wrap gap-3 pt-1 border-t border-outline-variant/10">
        <div class="space-y-1">
          <label class="flex items-center gap-2">
            <span class="font-sans text-[10px] uppercase tracking-widest text-on-surface-variant/60">Answer style</span>
            <select
              v-model="selectedAnswerStyleValue"
              aria-label="Answer style"
              class="rounded border border-transparent bg-surface-container px-2 py-1 font-sans text-[11px] text-on-surface outline-none transition-colors hover:border-outline-variant/20 focus:border-primary-container/40"
            >
              <option value="">No extra style</option>
              <option
                v-for="style in selectableAnswerStyles"
                :key="style.answer_style_id"
                :value="style.answer_style_id"
              >
                {{ style.label }}
              </option>
            </select>
          </label>
        </div>
        <div class="space-y-1">
          <label class="flex items-center gap-2">
            <span class="font-sans text-[10px] uppercase tracking-widest text-on-surface-variant/60">Strategy</span>
            <select
              v-model="selectedStrategyAgentId"
              aria-label="Strategy"
              :disabled="!isNewSession"
              class="rounded border border-transparent bg-surface-container px-2 py-1 font-sans text-[11px] text-on-surface outline-none transition-colors hover:border-outline-variant/20 focus:border-primary-container/40 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option
                v-for="agent in strategyAgents"
                :key="agent.strategy_agent_id"
                :value="agent.strategy_agent_id"
              >
                {{ agent.label }}
              </option>
            </select>
          </label>
        </div>
      </div>
    </div>
    
    <p
      v-if="errorMessage"
      role="alert"
      class="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm leading-6 text-red-700 font-sans"
    >
      {{ errorMessage }}
    </p>
  </div>
</template>
