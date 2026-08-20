<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { storeToRefs } from 'pinia'

const store = useWorkspaceStore()
const { configuredModelProfiles, selectedProviderProfile } = storeToRefs(store)

const isOpen = ref(false)
const selectedConfigKey = ref('')
const selectedConfiguredProfile = computed(
  () => configuredModelProfiles.value.find((profile) => profile.key === selectedConfigKey.value) || null
)

const syncSelectedKey = () => {
  const exact = configuredModelProfiles.value.find(
    (profile) =>
      profile.provider_type === selectedProviderProfile.value?.provider_type &&
      profile.credential_id === selectedProviderProfile.value?.credential_id &&
      profile.model === selectedProviderProfile.value?.model
  );
  selectedConfigKey.value = exact?.key || configuredModelProfiles.value[0]?.key || '';
}

watch(
  selectedProviderProfile,
  () => {
    syncSelectedKey()
  },
  { immediate: true }
)

watch(
  () => configuredModelProfiles.value.length,
  () => {
    syncSelectedKey()
  },
  { immediate: true }
)

const save = async () => {
  if (!selectedConfiguredProfile.value) return
  const profile = selectedConfiguredProfile.value
  if (store.currentSession?.session_id) {
    await store.updateSessionConversationModel(store.currentSession.session_id, profile)
  } else {
    selectedProviderProfile.value = {
      provider_id: profile.provider_id,
      provider_type: profile.provider_type,
      model: profile.model,
      credential_id: profile.credential_id,
      ...(profile.base_url ? { base_url: profile.base_url } : {}),
    } as any
  }
  isOpen.value = false
}

const open = () => {
  syncSelectedKey()
  isOpen.value = true
}
</script>

<template>
  <div class="relative">
    <button
      @click="open"
      class="flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant/40 transition-colors hover:bg-primary-fixed hover:text-primary"
      title="Model Settings"
      aria-label="Choose conversation model"
    >
      <span class="material-symbols-outlined text-[20px]" aria-hidden="true">tune</span>
    </button>

    <div
      v-if="isOpen"
      class="fixed inset-0 z-50 grid place-items-center bg-on-surface/20 px-4 backdrop-blur-sm"
      @click.self="isOpen = false"
    >
      <div class="w-[min(92vw,460px)] overflow-hidden rounded-3xl bg-surface-container-lowest shadow-2xl ghost-border">
        <div class="flex items-start justify-between gap-4 border-b border-outline-variant/10 bg-surface-container-low px-6 py-5">
          <div>
            <h3 class="flex items-center gap-2 font-serif text-lg font-bold text-primary">
              <span class="material-symbols-outlined text-[20px]">tune</span>
              Conversation Model
            </h3>
            <p class="mt-1 font-sans text-[11px] leading-relaxed text-on-surface-variant/70">Choose from models already configured in Global Settings.</p>
          </div>
          <button @click="isOpen = false" class="flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant/40 transition-colors hover:bg-primary-fixed hover:text-primary">
            <span class="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <div class="space-y-4 px-6 py-6">
          <div v-if="configuredModelProfiles.length" class="space-y-2">
            <label class="px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">Select Model</label>
            <select
              v-model="selectedConfigKey"
              class="w-full rounded-xl border border-outline-variant/20 bg-surface px-4 py-3 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:bg-surface-container-lowest focus:ring-1 focus:ring-primary/20"
            >
              <option v-for="profile in configuredModelProfiles" :key="profile.key" :value="profile.key">
                {{ profile.label }}
              </option>
            </select>
          </div>
          <div v-else class="rounded-2xl border border-dashed border-outline-variant/20 bg-surface-container-low py-6 text-center font-serif text-[13px] italic text-on-surface-variant/50">
            No configured models found. Add provider config in Global Settings first.
          </div>
        </div>

        <div class="flex gap-4 border-t border-outline-variant/10 bg-surface-container-low/50 px-6 py-5">
          <button
            @click="isOpen = false"
            class="flex-1 rounded-full border border-outline-variant/20 bg-surface-container-lowest px-4 py-3 font-sans text-[11px] font-bold uppercase tracking-widest text-on-surface-variant/70 transition-colors hover:bg-surface-container-low hover:text-on-surface"
          >
            Cancel
          </button>
          <button
            @click="save"
            :disabled="!selectedConfiguredProfile"
            class="flex-1 rounded-full bg-primary px-4 py-3 font-sans text-[11px] font-bold uppercase tracking-widest text-on-primary transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:bg-surface-container disabled:text-on-surface-variant/40"
          >
            Save Model
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
