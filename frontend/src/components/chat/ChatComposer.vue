<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkspaceStore } from '../../stores/workspace'

const props = defineProps<{
  loading?: boolean
}>()

const emit = defineEmits<{
  (event: 'ask', question: string): void
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
  const question = draftQuestion.value
  emit('ask', question)
  store.setDraftQuestion('')
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="composer-wrap">
    <div data-chat-composer-shell class="composer-shell">
      <div data-chat-composer-input-row class="composer-input-row">
        <textarea
          v-model="draftQuestion"
          rows="2"
          :disabled="loading"
          aria-label="Question"
          placeholder="Ask a mathematical question…"
          @keydown="handleKeydown"
        ></textarea>
        <button
          class="send-button"
          type="button"
          :disabled="!draftQuestion.trim() || loading"
          aria-label="Send message"
          @click="submit"
        >
          <span class="material-symbols-outlined">arrow_upward</span>
        </button>
      </div>

      <div data-chat-composer-controls class="composer-controls">
        <div class="composer-options">
          <label>
            <span class="material-symbols-outlined" aria-hidden="true">format_quote</span>
            <span class="sr-only">Answer style</span>
            <select v-model="selectedAnswerStyleValue" aria-label="Answer style">
              <option value="">Natural response</option>
              <option
                v-for="style in selectableAnswerStyles"
                :key="style.answer_style_id"
                :value="style.answer_style_id"
              >
                {{ style.label }}
              </option>
            </select>
          </label>

          <label v-if="isNewSession && strategyAgents.length">
            <span class="material-symbols-outlined" aria-hidden="true">route</span>
            <span class="sr-only">Strategy</span>
            <select v-model="selectedStrategyAgentId" aria-label="Strategy">
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
        <span class="composer-hint">Enter to send · Shift Enter for a new line</span>
      </div>
    </div>

    <p v-if="errorMessage" role="alert" class="composer-error">
      <span class="material-symbols-outlined">error</span>
      {{ errorMessage }}
    </p>
  </div>
</template>

<style scoped>
.composer-wrap {
  width: 100%;
  max-width: 850px;
  margin: 0 auto;
}

.composer-shell {
  overflow: hidden;
  border: 1px solid rgb(32 35 31 / 0.14);
  border-radius: 16px;
  background: #fffdf7;
  box-shadow: 0 14px 40px rgb(32 35 31 / 0.09), 0 1px 1px rgb(32 35 31 / 0.08);
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.composer-shell:focus-within {
  border-color: rgb(25 63 58 / 0.42);
  box-shadow: 0 18px 48px rgb(32 35 31 / 0.12), 0 0 0 3px rgb(216 232 223 / 0.5);
}

.composer-input-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 13px 13px 9px 17px;
}

textarea {
  min-height: 48px;
  flex: 1;
  resize: none;
  border: 0;
  outline: 0;
  color: var(--color-on-surface);
  background: transparent;
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.55;
}

textarea::placeholder {
  color: rgb(95 98 91 / 0.55);
}

.send-button {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border: 0;
  border-radius: 11px;
  color: #fffdf7;
  background: var(--color-primary);
  box-shadow: 0 5px 12px rgb(25 63 58 / 0.18);
  transition: background-color 150ms ease, transform 150ms ease, opacity 150ms ease;
}

.send-button:hover:not(:disabled) {
  background: #c86f3d;
  transform: translateY(-1px);
}

.send-button:disabled {
  cursor: default;
  opacity: 0.26;
  box-shadow: none;
}

.send-button .material-symbols-outlined {
  font-size: 18px;
}

.composer-controls {
  display: flex;
  min-height: 34px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 13px 7px 14px;
  border-top: 1px solid rgb(32 35 31 / 0.065);
}

.composer-options {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 4px;
}

.composer-options label {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 3px;
  border-radius: 6px;
  color: var(--color-on-surface-variant);
  background: transparent;
}

.composer-options label:hover {
  background: var(--color-surface-container-low);
}

.composer-options .material-symbols-outlined {
  margin-left: 6px;
  font-size: 14px;
}

select {
  max-width: 150px;
  min-height: 25px;
  border: 0;
  outline: 0;
  color: inherit;
  background: transparent;
  font-family: var(--font-sans);
  font-size: 10px;
}

.composer-hint {
  flex: 0 0 auto;
  color: rgb(95 98 91 / 0.52);
  font-family: var(--font-sans);
  font-size: 9px;
}

.composer-error {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 2px 0;
  padding: 8px 12px;
  border: 1px solid rgb(171 53 42 / 0.15);
  border-radius: 9px;
  color: #8f3027;
  background: #fff2ef;
  font-family: var(--font-sans);
  font-size: 11px;
}

.composer-error .material-symbols-outlined {
  font-size: 15px;
}

@media (max-width: 640px) {
  .composer-hint {
    display: none;
  }

  .composer-controls {
    justify-content: flex-start;
  }
}
</style>
