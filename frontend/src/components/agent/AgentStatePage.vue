<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useWorkspaceStore } from '../../stores/workspace';

const store = useWorkspaceStore();
const { agentState, agentStateLoading, currentSession, focusedAgentMessageId } = storeToRefs(store);

const currentTurn = computed(() => agentState.value?.current_turn || null);
const queue = computed(() => agentState.value?.knowledge_queue || []);
const memoryScope = computed(() => agentState.value?.memory_scope || null);
const health = computed(() => agentState.value?.context_health || null);
const recent = computed(() => agentState.value?.recent_decisions || []);
const profileObservations = computed(() => agentState.value?.profile_observations || []);
const profilePatches = computed(() => agentState.value?.profile_patches || []);
const focusedMessage = computed(() => {
  if (!focusedAgentMessageId.value) return null;
  return (
    currentSession.value?.messages.find(
      (message) =>
        message.message_id === focusedAgentMessageId.value &&
        message.role === 'assistant'
    ) || null
  );
});
const focusedPlan = computed(() => focusedMessage.value?.assistant_context.orchestration_plan || null);
const focusedStateItems = computed(() => focusedMessage.value?.assistant_context.state_items || []);
const isSuggestedDraftReview = computed(() => focusedPlan.value?.route === 'answer_then_suggest_drafts');
const focusedDrafts = computed(() => {
  if (!isSuggestedDraftReview.value) return [];
  return focusedPlan.value?.candidate_drafts || [];
});
const selectedDraftIndexes = ref<number[]>([]);

const describeProfileEntry = (entry: Record<string, any>) => {
  if (typeof entry.summary === 'string' && entry.summary.trim()) return entry.summary;
  if (typeof entry.title === 'string' && entry.title.trim()) return entry.title;
  if (typeof entry.label === 'string' && entry.label.trim()) return entry.label;
  if (typeof entry.reason === 'string' && entry.reason.trim()) return entry.reason;
  if (typeof entry.text === 'string' && entry.text.trim()) return entry.text;
  if (typeof entry.content === 'string' && entry.content.trim()) return entry.content;
  return JSON.stringify(entry);
};

const isFocusedDecision = (messageId: string) => focusedAgentMessageId.value === messageId;

const compileSelectedDrafts = async () => {
  if (!focusedAgentMessageId.value || !selectedDraftIndexes.value.length) return;
  await store.acceptSuggestedDrafts(
    focusedAgentMessageId.value,
    [...selectedDraftIndexes.value].sort((left, right) => left - right)
  );
  selectedDraftIndexes.value = [];
};

onMounted(() => {
  if (!agentStateLoading.value) {
    void store.fetchAgentState();
  }
});
</script>

<template>
  <section class="h-full overflow-y-auto p-10">
    <div class="mx-auto max-w-5xl space-y-8">
      <header>
        <p class="font-sans text-[10px] uppercase tracking-widest text-primary/70">Agent State</p>
        <h2 class="font-serif text-3xl text-on-surface">Accumulation Control</h2>
      </header>

      <section
        v-if="agentStateLoading"
        class="rounded-lg border border-primary/20 bg-primary-fixed/30 p-4 font-sans text-sm text-primary"
      >
        Loading agent review...
      </section>

      <section
        v-if="focusedPlan"
        class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6"
      >
        <h3 class="stitch-label mb-4">Selected Review</h3>
        <div class="space-y-3">
          <p class="font-sans text-sm text-on-surface-variant">{{ focusedPlan.user_visible_summary }}</p>
          <div class="flex flex-wrap gap-2 text-[11px] uppercase tracking-widest">
            <span class="rounded bg-primary-fixed px-3 py-1 text-primary">{{ focusedPlan.route }}</span>
            <span class="rounded bg-surface px-3 py-1 text-on-surface-variant">{{ focusedPlan.intent }}</span>
            <span class="rounded bg-surface px-3 py-1 text-on-surface-variant">{{ Math.round(focusedPlan.confidence * 100) }}%</span>
            <span class="rounded bg-surface px-3 py-1 text-on-surface-variant">{{ focusedPlan.persistence_decision }}</span>
          </div>
        </div>
        <div v-if="focusedDrafts.length || focusedStateItems.length" class="mt-5 grid gap-3 md:grid-cols-2">
          <article
            v-for="(draft, index) in focusedDrafts"
            :key="`draft-${draft.title}`"
            class="rounded bg-surface p-4"
          >
            <label class="flex items-start gap-3">
              <input
                v-model="selectedDraftIndexes"
                type="checkbox"
                :value="index"
                :data-draft-index="index"
                class="mt-1"
              />
              <span>
                <span class="block font-serif text-base text-on-surface">{{ draft.title }}</span>
                <span class="block font-sans text-[10px] uppercase tracking-widest text-primary">{{ draft.draft_type }}</span>
              </span>
            </label>
            <p class="mt-2 font-sans text-xs text-on-surface-variant">{{ draft.reason }}</p>
          </article>
          <article
            v-for="item in focusedStateItems"
            :key="item.item_id"
            class="rounded bg-surface p-4"
          >
            <div class="flex items-start justify-between gap-3">
              <p class="font-serif text-base text-on-surface">{{ item.title }}</p>
              <span class="rounded bg-primary-fixed px-2 py-1 font-sans text-[10px] uppercase tracking-widest text-primary">{{ item.state }}</span>
            </div>
            <p class="mt-2 font-sans text-xs text-on-surface-variant">{{ item.reason }}</p>
          </article>
        </div>
        <button
          v-if="focusedDrafts.length"
          class="mt-5 rounded bg-primary px-4 py-2 font-sans text-[11px] uppercase tracking-widest text-on-primary disabled:opacity-40"
          data-compile-selected-drafts
          :disabled="!selectedDraftIndexes.length"
          @click="compileSelectedDrafts"
        >
          Generate selected
        </button>
      </section>

      <section class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
        <h3 class="stitch-label mb-4">Current Turn</h3>
        <div v-if="currentTurn" class="space-y-3">
          <p class="font-sans text-sm text-on-surface-variant">{{ currentTurn.user_visible_summary }}</p>
          <div class="flex flex-wrap gap-2 text-[11px] uppercase tracking-widest">
            <span class="rounded bg-primary-fixed px-3 py-1 text-primary">{{ currentTurn.route }}</span>
            <span class="rounded bg-surface px-3 py-1 text-on-surface-variant">{{ currentTurn.intent }}</span>
            <span class="rounded bg-surface px-3 py-1 text-on-surface-variant">{{ Math.round(currentTurn.confidence * 100) }}%</span>
          </div>
        </div>
        <p v-else class="font-serif italic text-on-surface-variant/70">No current agent turn.</p>
      </section>

      <section class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
        <h3 class="stitch-label mb-4">Knowledge Queue</h3>
        <div v-if="queue.length" class="space-y-3">
          <article v-for="item in queue" :key="item.item_id" class="rounded bg-surface p-4">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="font-serif text-lg">{{ item.title }}</p>
                <p class="font-sans text-xs text-on-surface-variant">{{ item.reason }}</p>
              </div>
              <span class="rounded bg-primary-fixed px-3 py-1 font-sans text-[10px] uppercase tracking-widest text-primary">{{ item.state }}</span>
            </div>
          </article>
        </div>
        <p v-else class="font-serif italic text-on-surface-variant/70">No knowledge items waiting.</p>
      </section>

      <section class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
        <h3 class="stitch-label mb-4">Memory Scope</h3>
        <div v-if="memoryScope" class="space-y-4">
          <p class="font-serif text-sm text-on-surface-variant">
            {{ memoryScope.profile_context_summary || 'No profile or scope context influenced this turn.' }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="scopeId in memoryScope.detected_scope_ids"
              :key="scopeId"
              class="rounded bg-primary-fixed px-3 py-1 font-sans text-[10px] uppercase tracking-widest text-primary"
            >
              {{ scopeId }}
            </span>
            <span
              v-for="layer in memoryScope.profile_layers_used"
              :key="layer"
              class="rounded bg-surface px-3 py-1 font-sans text-[10px] uppercase tracking-widest text-on-surface-variant"
            >
              {{ layer }}
            </span>
          </div>
        </div>
        <p v-else class="font-serif italic text-on-surface-variant/70">No memory scope metadata recorded.</p>
      </section>

      <section class="grid gap-6 md:grid-cols-2">
        <div class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
          <h3 class="stitch-label mb-4">Profile Observations</h3>
          <div v-if="profileObservations.length" class="space-y-3">
            <article
              v-for="(observation, index) in profileObservations"
              :key="`profile-observation-${index}`"
              class="rounded bg-surface p-4"
            >
              <p class="font-sans text-[10px] uppercase tracking-widest text-primary">Observation {{ index + 1 }}</p>
              <p class="mt-2 font-serif text-sm text-on-surface-variant">{{ describeProfileEntry(observation) }}</p>
            </article>
          </div>
          <p v-else class="font-serif italic text-on-surface-variant/70">No profile observations yet.</p>
        </div>

        <div class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
          <h3 class="stitch-label mb-4">Profile Patches</h3>
          <div v-if="profilePatches.length" class="space-y-3">
            <article
              v-for="(patch, index) in profilePatches"
              :key="`profile-patch-${index}`"
              class="rounded bg-surface p-4"
            >
              <p class="font-sans text-[10px] uppercase tracking-widest text-primary">Patch {{ index + 1 }}</p>
              <p class="mt-2 font-serif text-sm text-on-surface-variant">{{ describeProfileEntry(patch) }}</p>
            </article>
          </div>
          <p v-else class="font-serif italic text-on-surface-variant/70">No profile patches yet.</p>
        </div>
      </section>

      <section class="grid gap-6 md:grid-cols-2">
        <div class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
          <h3 class="stitch-label mb-4">Context Health</h3>
          <dl v-if="health" class="grid grid-cols-2 gap-3 font-sans text-sm">
            <dt>Active nodes</dt><dd>{{ health.active_node_count }}</dd>
            <dt>Summary nodes</dt><dd>{{ health.summary_node_count }}</dd>
            <dt>Pending drafts</dt><dd>{{ health.pending_draft_count }}</dd>
            <dt>Failed items</dt><dd>{{ health.failed_item_count }}</dd>
            <dt>Symbol conflicts</dt><dd>{{ health.symbol_conflict_count }}</dd>
          </dl>
        </div>

        <div class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
          <h3 class="stitch-label mb-4">Recent Decisions</h3>
          <div v-if="recent.length" class="space-y-3">
            <article
              v-for="decision in recent"
              :key="decision.message_id"
              :data-decision-message-id="decision.message_id"
              :data-focused="isFocusedDecision(decision.message_id) ? 'true' : undefined"
              class="rounded border-l-2 pl-3 py-2 transition-colors"
              :class="isFocusedDecision(decision.message_id)
                ? 'border-primary bg-primary-fixed/30'
                : 'border-primary/40'"
            >
              <div class="flex items-center gap-2">
                <p class="font-sans text-xs uppercase tracking-widest text-primary">{{ decision.route }}</p>
                <span
                  v-if="isFocusedDecision(decision.message_id)"
                  class="rounded-full bg-primary px-2 py-0.5 font-sans text-[10px] uppercase tracking-widest text-on-primary"
                >
                  Focused
                </span>
              </div>
              <p class="font-serif text-sm text-on-surface-variant">{{ decision.result }}</p>
            </article>
          </div>
          <p v-else class="font-serif italic text-on-surface-variant/70">No decisions recorded.</p>
        </div>
      </section>
    </div>
  </section>
</template>
