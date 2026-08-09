<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkspaceStore } from '../../stores/workspace'

const store = useWorkspaceStore()
const { agentState, agentStateLoading, currentSession, focusedAgentMessageId } = storeToRefs(store)

const currentTurn = computed(() => agentState.value?.current_turn || null)
const queue = computed(() => agentState.value?.knowledge_queue || [])
const memoryScope = computed(() => agentState.value?.memory_scope || null)
const health = computed(() => agentState.value?.context_health || null)
const recent = computed(() => agentState.value?.recent_decisions || [])
const profileObservations = computed(() => agentState.value?.profile_observations || [])
const profilePatches = computed(() => agentState.value?.profile_patches || [])
const focusedMessage = computed(() => {
  if (!focusedAgentMessageId.value) return null
  return currentSession.value?.messages.find(
    (message) => message.message_id === focusedAgentMessageId.value && message.role === 'assistant'
  ) || null
})
const focusedPlan = computed(() => focusedMessage.value?.assistant_context.orchestration_plan || null)
const focusedStateItems = computed(() => focusedMessage.value?.assistant_context.state_items || [])
const isSuggestedDraftReview = computed(() => focusedPlan.value?.route === 'answer_then_suggest_drafts')
const focusedDrafts = computed(() => isSuggestedDraftReview.value ? focusedPlan.value?.candidate_drafts || [] : [])
const selectedDraftIndexes = ref<number[]>([])

type ReviewKnowledgeItem = {
  key: string
  title: string
  reason: string
  draftType?: string
  state: string
  draftIndex?: number
  errorMessage?: string | null
}

const reviewPlan = computed(() => focusedPlan.value || currentTurn.value)
const isFocusedReview = computed(() => !!focusedPlan.value)

const normalizeTitle = (title: string) => title.trim().toLocaleLowerCase()

const focusedStateByTitle = computed(() => new Map(
  focusedStateItems.value.map((item) => [normalizeTitle(item.title), item])
))

const primaryKnowledgeItems = computed<ReviewKnowledgeItem[]>(() => {
  if (!focusedPlan.value) {
    const byTitle = new Map<string, ReviewKnowledgeItem>()
    for (const item of queue.value) {
      const key = normalizeTitle(item.title)
      byTitle.set(key, {
        key: item.item_id,
        title: item.title,
        reason: item.reason,
        draftType: item.draft_type,
        state: item.state,
        errorMessage: item.error_message,
      })
    }
    return [...byTitle.values()]
  }

  if (!isSuggestedDraftReview.value) {
    return focusedStateItems.value.map((item) => ({
      key: item.item_id,
      title: item.title,
      reason: item.reason,
      state: item.state,
      errorMessage: item.error_message,
    }))
  }

  const candidateTitles = new Set(focusedDrafts.value.map((draft) => normalizeTitle(draft.title)))
  const candidates = focusedDrafts.value.map((draft, index) => {
    const stateItem = focusedStateByTitle.value.get(normalizeTitle(draft.title))
    return {
      key: stateItem?.item_id || `draft-${index}`,
      title: draft.title,
      reason: draft.reason,
      draftType: draft.draft_type,
      state: stateItem?.state || 'suggested',
      draftIndex: index,
      errorMessage: stateItem?.error_message,
    }
  })
  const additionalStateItems = focusedStateItems.value
    .filter((item) => !candidateTitles.has(normalizeTitle(item.title)))
    .map((item) => ({
      key: item.item_id,
      title: item.title,
      reason: item.reason,
      state: item.state,
      errorMessage: item.error_message,
    }))
  return [...candidates, ...additionalStateItems]
})

const otherKnowledgeItems = computed<ReviewKnowledgeItem[]>(() => {
  if (!focusedPlan.value) return []
  const focusedIds = new Set(focusedStateItems.value.map((item) => item.item_id))
  const focusedTitles = new Set(primaryKnowledgeItems.value.map((item) => normalizeTitle(item.title)))
  const byTitle = new Map<string, ReviewKnowledgeItem>()

  for (const item of queue.value) {
    const titleKey = normalizeTitle(item.title)
    if (
      item.source_message_id === focusedAgentMessageId.value ||
      focusedIds.has(item.item_id) ||
      focusedTitles.has(titleKey)
    ) continue

    byTitle.set(titleKey, {
      key: item.item_id,
      title: item.title,
      reason: item.reason,
      draftType: item.draft_type,
      state: item.state,
      errorMessage: item.error_message,
    })
  }
  return [...byTitle.values()]
})

const isDraftSelectable = (item: ReviewKnowledgeItem) => (
  item.draftIndex !== undefined && ['suggested', 'failed'].includes(item.state)
)

const selectableDraftCount = computed(() => primaryKnowledgeItems.value.filter(isDraftSelectable).length)

const knowledgeHeading = computed(() => {
  if (!isFocusedReview.value) return 'Knowledge activity'
  if (isSuggestedDraftReview.value && selectableDraftCount.value) return 'Keep the useful parts'
  return 'Knowledge from this response'
})

const knowledgeDescription = computed(() => {
  if (!isFocusedReview.value) return 'Reusable notes created or suggested in this conversation.'
  if (isSuggestedDraftReview.value && selectableDraftCount.value) {
    return 'Choose only the ideas you want to turn into reusable notes.'
  }
  return 'A clear view of what this response added to your library.'
})

const statusMeta = (state: string) => {
  const states: Record<string, { label: string; icon: string; tone: string }> = {
    suggested: { label: 'Suggested', icon: 'bookmark_add', tone: 'suggested' },
    queued: { label: 'Queued', icon: 'schedule', tone: 'active' },
    pending: { label: 'Queued', icon: 'schedule', tone: 'active' },
    running: { label: 'Creating', icon: 'progress_activity', tone: 'active' },
    writing: { label: 'Creating', icon: 'progress_activity', tone: 'active' },
    ready: { label: 'Saved', icon: 'check', tone: 'ready' },
    failed: { label: 'Needs attention', icon: 'error', tone: 'failed' },
  }
  return states[state] || {
    label: state.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()),
    icon: 'circle',
    tone: 'neutral',
  }
}

const humanizeDecision = (value: string) => value
  .replaceAll('_', ' ')
  .replace(/^./, (letter) => letter.toUpperCase())

const describeProfileEntry = (entry: Record<string, any>) => {
  for (const key of ['summary', 'title', 'label', 'reason', 'text', 'content']) {
    if (typeof entry[key] === 'string' && entry[key].trim()) return entry[key]
  }
  return JSON.stringify(entry)
}

const isFocusedDecision = (messageId: string) => focusedAgentMessageId.value === messageId

const compileSelectedDrafts = async () => {
  if (!focusedAgentMessageId.value || !selectedDraftIndexes.value.length) return
  await store.acceptSuggestedDrafts(
    focusedAgentMessageId.value,
    [...selectedDraftIndexes.value].sort((left, right) => left - right)
  )
  selectedDraftIndexes.value = []
}

onMounted(() => {
  if (!agentStateLoading.value) void store.fetchAgentState()
})
</script>

<template>
  <section class="agent-page">
    <div class="agent-page-inner">
      <div v-if="agentStateLoading" class="agent-loading" role="status">
        <span></span>
        Loading agent review...
      </div>

      <section class="review-overview" data-review-overview>
        <div class="review-marker" aria-hidden="true">
          <span class="material-symbols-outlined">{{ isFocusedReview ? 'fact_check' : 'history' }}</span>
        </div>
        <div>
          <p>{{ isFocusedReview ? 'Response approach' : 'Latest response' }}</p>
          <h2 :title="reviewPlan?.user_visible_summary">
            {{ reviewPlan?.user_visible_summary || 'No response details are available yet.' }}
          </h2>
        </div>
      </section>

      <section v-if="primaryKnowledgeItems.length" class="knowledge-panel" data-primary-knowledge>
        <header class="knowledge-heading">
          <div class="knowledge-heading-icon" aria-hidden="true">
            <span class="material-symbols-outlined">auto_stories</span>
          </div>
          <div>
            <h3>{{ knowledgeHeading }}</h3>
            <p>{{ knowledgeDescription }}</p>
          </div>
          <span class="item-count">{{ primaryKnowledgeItems.length }}</span>
        </header>

        <div class="knowledge-list">
          <component
            :is="isDraftSelectable(item) ? 'label' : 'article'"
            v-for="item in primaryKnowledgeItems"
            :key="item.key"
            class="knowledge-item"
            :class="{
              selectable: isDraftSelectable(item),
              selected: item.draftIndex !== undefined && selectedDraftIndexes.includes(item.draftIndex),
            }"
            data-knowledge-item
          >
            <input
              v-if="isDraftSelectable(item)"
              v-model="selectedDraftIndexes"
              type="checkbox"
              :value="item.draftIndex"
              :data-draft-index="item.draftIndex"
            />
            <span v-if="isDraftSelectable(item)" class="draft-check" aria-hidden="true">
              <span class="material-symbols-outlined">check</span>
            </span>
            <span
              v-else
              class="knowledge-status-icon material-symbols-outlined"
              :class="`tone-${statusMeta(item.state).tone}`"
              aria-hidden="true"
            >
              {{ statusMeta(item.state).icon }}
            </span>

            <span class="knowledge-copy">
              <span class="knowledge-title-line">
                <strong>{{ item.title }}</strong>
                <span v-if="item.draftType" class="draft-type">{{ humanizeDecision(item.draftType) }}</span>
              </span>
              <span>{{ item.errorMessage || item.reason }}</span>
            </span>

            <span
              v-if="!isDraftSelectable(item)"
              class="knowledge-status"
              :class="`tone-${statusMeta(item.state).tone}`"
            >
              {{ statusMeta(item.state).label }}
            </span>
          </component>
        </div>

        <footer v-if="selectableDraftCount" class="knowledge-action-bar">
          <p>
            <strong>{{ selectedDraftIndexes.length || 'No' }}</strong>
            {{ selectedDraftIndexes.length === 1 ? 'note selected' : 'notes selected' }}
          </p>
          <button
            class="generate-drafts"
            type="button"
            data-compile-selected-drafts
            :disabled="!selectedDraftIndexes.length"
            @click="compileSelectedDrafts"
          >
            {{ selectedDraftIndexes.length ? `Create ${selectedDraftIndexes.length}` : 'Select notes' }}
            <span class="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
          </button>
        </footer>
      </section>

      <details v-if="otherKnowledgeItems.length" class="other-knowledge" data-other-knowledge>
        <summary>
          <span class="other-summary-copy">
            <span class="material-symbols-outlined" aria-hidden="true">pending_actions</span>
            <span>
              <strong>Elsewhere in this conversation</strong>
              <small>{{ otherKnowledgeItems.length }} other {{ otherKnowledgeItems.length === 1 ? 'note' : 'notes' }}</small>
            </span>
          </span>
          <span class="material-symbols-outlined disclosure-icon" aria-hidden="true">expand_more</span>
        </summary>
        <div class="other-knowledge-list">
          <article v-for="item in otherKnowledgeItems" :key="item.key">
            <span class="material-symbols-outlined" :class="`tone-${statusMeta(item.state).tone}`" aria-hidden="true">
              {{ statusMeta(item.state).icon }}
            </span>
            <span>
              <strong>{{ item.title }}</strong>
              <small>{{ statusMeta(item.state).label }}</small>
            </span>
          </article>
        </div>
      </details>

      <details class="diagnostics">
        <summary>
          <span>
            <span class="material-symbols-outlined">tune</span>
            Context diagnostics
          </span>
          <span class="material-symbols-outlined disclosure-icon">expand_more</span>
        </summary>

        <div class="diagnostic-grid">
          <section class="decision-diagnostics">
            <h3>Decision</h3>
            <dl v-if="reviewPlan">
              <div><dt>Approach</dt><dd>{{ humanizeDecision(reviewPlan.route) }}</dd></div>
              <div><dt>Intent</dt><dd>{{ humanizeDecision(reviewPlan.intent) }}</dd></div>
              <div><dt>Knowledge</dt><dd>{{ humanizeDecision(reviewPlan.persistence_decision) }}</dd></div>
              <div><dt>Confidence</dt><dd>{{ Math.round(reviewPlan.confidence * 100) }}%</dd></div>
            </dl>
            <p v-else>No decision metadata recorded.</p>
          </section>

          <section>
            <h3>Memory Scope</h3>
            <p>{{ memoryScope?.profile_context_summary || 'No profile or scope context influenced this turn.' }}</p>
            <div class="tag-list">
              <span v-for="scopeId in memoryScope?.detected_scope_ids || []" :key="scopeId">{{ scopeId }}</span>
              <span v-for="layer in memoryScope?.profile_layers_used || []" :key="layer">{{ layer }}</span>
            </div>
          </section>

          <section>
            <h3>Context Health</h3>
            <dl v-if="health">
              <div><dt>Active nodes</dt><dd>{{ health.active_node_count }}</dd></div>
              <div><dt>Summary nodes</dt><dd>{{ health.summary_node_count }}</dd></div>
              <div><dt>Pending drafts</dt><dd>{{ health.pending_draft_count }}</dd></div>
              <div><dt>Failed items</dt><dd>{{ health.failed_item_count }}</dd></div>
              <div><dt>Symbol conflicts</dt><dd>{{ health.symbol_conflict_count }}</dd></div>
            </dl>
          </section>

          <section>
            <h3>Profile Observations</h3>
            <div v-if="profileObservations.length" class="diagnostic-list">
              <p v-for="(observation, index) in profileObservations" :key="`profile-observation-${index}`">
                {{ describeProfileEntry(observation) }}
              </p>
            </div>
            <p v-else>No profile observations yet.</p>
          </section>

          <section>
            <h3>Profile Patches</h3>
            <div v-if="profilePatches.length" class="diagnostic-list">
              <p v-for="(patch, index) in profilePatches" :key="`profile-patch-${index}`">
                {{ describeProfileEntry(patch) }}
              </p>
            </div>
            <p v-else>No profile patches yet.</p>
          </section>

          <section class="recent-decisions">
            <h3>Recent Decisions</h3>
            <div v-if="recent.length" class="diagnostic-list">
              <article
                v-for="decision in recent"
                :key="decision.message_id"
                :data-decision-message-id="decision.message_id"
                :data-focused="isFocusedDecision(decision.message_id) ? 'true' : undefined"
              >
                <div>
                  <strong>{{ decision.route }}</strong>
                  <span v-if="isFocusedDecision(decision.message_id)">Focused</span>
                </div>
                <p>{{ decision.result }}</p>
              </article>
            </div>
            <p v-else>No decisions recorded.</p>
          </section>
        </div>
      </details>
    </div>
  </section>
</template>

<style scoped>
.agent-page {
  min-height: 100%;
  padding: 46px 34px 80px;
  background:
    radial-gradient(circle at 82% 2%, rgb(216 232 223 / 0.38), transparent 28%),
    rgb(255 253 247 / 0.64);
}

.agent-page-inner {
  max-width: 820px;
  margin: 0 auto;
  animation: review-in 360ms cubic-bezier(0.2, 0.75, 0.25, 1) both;
}

.review-overview {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  padding: 4px 4px 28px;
  border-bottom: 1px solid rgb(32 35 31 / 0.1);
}

.review-marker {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid rgb(25 63 58 / 0.14);
  border-radius: 14px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  box-shadow: inset 0 -2px 0 rgb(25 63 58 / 0.08);
}

.review-marker .material-symbols-outlined {
  font-size: 21px;
}

.review-overview p {
  margin: 2px 0 7px;
  color: #96715c;
  font-family: var(--font-sans);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

.review-overview h2 {
  max-width: 720px;
  margin: 0;
  color: #21302c;
  font-family: var(--font-serif);
  font-size: clamp(20px, 2.35vw, 25px);
  font-weight: 500;
  letter-spacing: -0.015em;
  line-height: 1.34;
  overflow-wrap: anywhere;
}

.agent-loading {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 14px;
  padding: 10px 13px;
  border-radius: 8px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
  font-family: var(--font-sans);
  font-size: 11px;
}

.agent-loading span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #c86f3d;
}

.knowledge-panel {
  overflow: hidden;
  margin-top: 24px;
  border: 1px solid rgb(32 35 31 / 0.1);
  border-radius: 18px;
  background: #fffdf7;
  box-shadow: 0 10px 32px rgb(31 48 42 / 0.055), 0 1px 0 rgb(32 35 31 / 0.04);
}

.knowledge-heading {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 21px 24px 18px;
}

.knowledge-heading-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 11px;
  color: #9a5734;
  background: #fae7d8;
}

.knowledge-heading-icon .material-symbols-outlined {
  font-size: 18px;
}

.knowledge-heading > div:nth-child(2) {
  min-width: 0;
  flex: 1;
}

.knowledge-heading h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 550;
  letter-spacing: -0.015em;
  line-height: 1.2;
}

.knowledge-heading p {
  margin: 4px 0 0;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 10px;
  line-height: 1.45;
}

.item-count {
  display: grid;
  width: 25px;
  height: 25px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgb(32 35 31 / 0.09);
  border-radius: 50%;
  color: var(--color-on-surface-variant);
  background: var(--color-surface-container-lowest);
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 600;
}

.knowledge-list {
  border-top: 1px solid rgb(32 35 31 / 0.08);
}

.knowledge-item {
  position: relative;
  display: grid;
  min-height: 72px;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 15px 24px;
  background: transparent;
  transition: background-color 150ms ease, box-shadow 150ms ease;
}

.knowledge-item + .knowledge-item {
  border-top: 1px solid rgb(32 35 31 / 0.07);
}

.knowledge-item.selectable {
  cursor: pointer;
}

.knowledge-item.selectable:hover {
  background: rgb(216 232 223 / 0.24);
}

.knowledge-item.selected {
  background: rgb(216 232 223 / 0.38);
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.knowledge-item input {
  position: absolute;
  opacity: 0;
}

.draft-check {
  display: grid;
  width: 19px;
  height: 19px;
  place-items: center;
  border: 1px solid var(--color-outline-variant);
  border-radius: 6px;
  color: #fffdf7;
  background: #fffdf7;
  transition: border-color 140ms ease, background-color 140ms ease, transform 140ms ease;
}

.draft-check .material-symbols-outlined {
  opacity: 0;
  font-size: 13px;
  font-weight: 700;
  transform: scale(0.5);
  transition: opacity 140ms ease, transform 140ms ease;
}

.knowledge-item input:checked + .draft-check {
  border-color: var(--color-primary);
  background: var(--color-primary);
  transform: scale(1.04);
}

.knowledge-item input:checked + .draft-check .material-symbols-outlined {
  opacity: 1;
  transform: scale(1);
}

.knowledge-item input:focus-visible + .draft-check {
  outline: 2px solid #c86f3d;
  outline-offset: 2px;
}

.knowledge-status-icon {
  display: grid;
  width: 20px;
  height: 20px;
  place-items: center;
  border-radius: 50%;
  font-size: 16px;
}

.knowledge-copy {
  min-width: 0;
}

.knowledge-title-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}

.knowledge-copy strong {
  color: var(--color-on-surface);
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
}

.draft-type {
  color: rgb(95 98 91 / 0.68);
  font-family: var(--font-sans);
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.knowledge-copy > span:last-child {
  display: block;
  margin-top: 4px;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 10px;
  line-height: 1.5;
}

.knowledge-status {
  align-self: center;
  padding: 5px 8px;
  border-radius: 999px;
  font-family: var(--font-sans);
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.06em;
  white-space: nowrap;
  text-transform: uppercase;
}

.tone-suggested {
  color: #9a5734;
}

.knowledge-status.tone-suggested {
  background: #fae7d8;
}

.tone-active {
  color: #78631d;
}

.knowledge-status.tone-active {
  background: #f4ecc8;
}

.tone-ready {
  color: var(--color-primary);
}

.knowledge-status.tone-ready {
  background: var(--color-primary-fixed);
}

.tone-failed {
  color: #a23e35;
}

.knowledge-status.tone-failed {
  background: #f8dfdc;
}

.tone-neutral {
  color: var(--color-on-surface-variant);
}

.knowledge-status.tone-neutral {
  background: var(--color-surface-container-low);
}

.knowledge-action-bar {
  display: flex;
  min-height: 60px;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 10px 14px 10px 24px;
  border-top: 1px solid rgb(32 35 31 / 0.08);
  background: var(--color-surface-container-low);
}

.knowledge-action-bar p {
  margin: 0;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 10px;
}

.knowledge-action-bar p strong {
  color: var(--color-on-surface);
  font-weight: 600;
}

.generate-drafts {
  display: inline-flex;
  min-width: 106px;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 13px;
  border: 0;
  border-radius: 10px;
  color: #fffdf7;
  background: var(--color-primary);
  box-shadow: 0 4px 12px rgb(25 63 58 / 0.16);
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 600;
  transition: opacity 140ms ease, transform 140ms ease, box-shadow 140ms ease;
}

.generate-drafts:not(:disabled):hover {
  box-shadow: 0 6px 16px rgb(25 63 58 / 0.22);
  transform: translateY(-1px);
}

.generate-drafts:disabled {
  cursor: default;
  box-shadow: none;
  opacity: 0.34;
}

.generate-drafts .material-symbols-outlined {
  font-size: 13px;
}

.other-knowledge,
.diagnostics {
  overflow: hidden;
  margin-top: 12px;
  border: 1px solid rgb(32 35 31 / 0.09);
  border-radius: 13px;
  background: rgb(255 253 247 / 0.76);
}

.other-knowledge summary,
.diagnostics summary {
  display: flex;
  min-height: 54px;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  list-style: none;
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
}

.other-knowledge summary::-webkit-details-marker,
.diagnostics summary::-webkit-details-marker { display: none; }

.other-summary-copy,
.diagnostics summary > span {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.other-summary-copy > .material-symbols-outlined,
.diagnostics summary .material-symbols-outlined {
  font-size: 16px;
}

.other-summary-copy > span:last-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.other-summary-copy strong {
  color: var(--color-on-surface);
  font-size: 11px;
  font-weight: 600;
}

.other-summary-copy small {
  color: var(--color-on-surface-variant);
  font-size: 9px;
}

.disclosure-icon {
  transition: transform 160ms ease;
}

.other-knowledge[open] .disclosure-icon,
.diagnostics[open] .disclosure-icon {
  transform: rotate(180deg);
}

.other-knowledge-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid rgb(32 35 31 / 0.08);
  background: rgb(32 35 31 / 0.08);
}

.other-knowledge-list article {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  padding: 13px 16px;
  background: #fffdf7;
}

.other-knowledge-list article > .material-symbols-outlined {
  font-size: 16px;
}

.other-knowledge-list article > span:last-child {
  min-width: 0;
}

.other-knowledge-list strong,
.other-knowledge-list small {
  display: block;
  overflow: hidden;
  font-family: var(--font-sans);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.other-knowledge-list strong {
  font-size: 10px;
  font-weight: 600;
}

.other-knowledge-list small {
  margin-top: 2px;
  color: var(--color-on-surface-variant);
  font-size: 8px;
  text-transform: uppercase;
}

.diagnostic-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1px;
  border-top: 1px solid rgb(32 35 31 / 0.08);
  background: rgb(32 35 31 / 0.08);
}

.diagnostic-grid > section {
  min-height: 140px;
  padding: 18px;
  background: #fffdf7;
}

.diagnostic-grid h3 {
  margin: 0 0 10px;
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.diagnostic-grid p,
.diagnostic-grid dt,
.diagnostic-grid dd {
  color: var(--color-on-surface-variant);
  font-family: var(--font-sans);
  font-size: 10px;
  line-height: 1.5;
}

.diagnostic-grid dl {
  margin: 0;
}

.diagnostic-grid dl div {
  display: flex;
  gap: 14px;
  justify-content: space-between;
  padding: 3px 0;
}

.diagnostic-grid dd {
  margin: 0;
  color: var(--color-on-surface);
  font-weight: 600;
}

.decision-diagnostics {
  grid-column: 1 / -1;
  min-height: 0 !important;
}

.decision-diagnostics dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 36px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 12px;
}

.tag-list span {
  padding: 4px 7px;
  border-radius: 5px;
  color: var(--color-on-surface-variant);
  background: var(--color-surface-container-low);
  font-family: var(--font-sans);
  font-size: 9px;
}

.recent-decisions {
  grid-column: 1 / -1;
}

.diagnostic-list article {
  padding: 8px 0;
  border-top: 1px solid rgb(32 35 31 / 0.07);
}

.diagnostic-list article > div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.diagnostic-list article strong,
.diagnostic-list article span {
  font-family: var(--font-sans);
  font-size: 9px;
}

.diagnostic-list article span {
  padding: 2px 5px;
  border-radius: 4px;
  color: var(--color-primary);
  background: var(--color-primary-fixed);
}

.diagnostic-list article p {
  margin: 4px 0 0;
}

@keyframes review-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 640px) {
  .agent-page { padding: 30px 16px 60px; }
  .review-overview { grid-template-columns: 40px minmax(0, 1fr); gap: 13px; padding-bottom: 26px; }
  .review-marker { width: 40px; height: 40px; border-radius: 12px; }
  .review-overview h2 { font-size: 20px; line-height: 1.4; }
  .knowledge-heading { align-items: flex-start; padding: 18px 16px 15px; }
  .knowledge-heading-icon { width: 34px; height: 34px; flex-basis: 34px; }
  .knowledge-item { grid-template-columns: 20px minmax(0, 1fr); gap: 11px; padding: 14px 16px; }
  .knowledge-status { grid-column: 2; justify-self: start; }
  .knowledge-action-bar { padding-left: 16px; }
  .other-knowledge-list,
  .diagnostic-grid,
  .decision-diagnostics dl { grid-template-columns: 1fr; }
  .decision-diagnostics { grid-column: auto; }
  .recent-decisions { grid-column: auto; }
}
</style>
