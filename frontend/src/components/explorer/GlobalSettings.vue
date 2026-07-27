<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useWorkspaceStore } from '../../stores/workspace'
import { storeToRefs } from 'pinia'
import type { ProviderCatalogItem, ProviderId } from '../../services/api'

const store = useWorkspaceStore()
const {
  credentials,
  loading,
  providerCatalog,
  configuredModelProfiles,
  defaultOptions,
} = storeToRefs(store)

const isOpen = ref(false)
const activeSection = ref<'providers' | 'defaults'>('providers')
const activeProviderId = ref<ProviderId>('gemini')
const modelToAdd = ref('')
const conversationModelProfileKey = ref('')
const utilityModelProfileKey = ref('')
const markdownTheme = ref<'academic' | 'reading' | 'geek'>('academic')

const fallbackProviderCatalog: ProviderCatalogItem[] = [
  {
    provider_id: 'gemini',
    provider_type: 'gemini',
    label: 'Gemini',
    default_model: 'gemini-2.5-flash',
    models: ['gemini-3-flash-preview', 'gemini-3-pro-preview', 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
    allow_custom_model: false,
    requires_base_url: false,
    default_base_url: '',
    logo_url: '/provider-icons/gemini.svg',
  },
  {
    provider_id: 'deepseek',
    provider_type: 'openai_compatible',
    label: 'DeepSeek',
    default_model: 'deepseek-chat',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    allow_custom_model: true,
    requires_base_url: true,
    default_base_url: 'https://api.deepseek.com/v1',
    logo_url: '/provider-icons/deepseek.png',
  },
  {
    provider_id: 'openrouter',
    provider_type: 'openai_compatible',
    label: 'OpenRouter',
    default_model: 'openrouter/auto',
    models: [
      'openrouter/auto',
      'openrouter/anthropic/claude-3.7-sonnet',
      'openrouter/google/gemini-2.5-pro',
      'openrouter/openai/gpt-4.1',
    ],
    allow_custom_model: true,
    requires_base_url: true,
    default_base_url: 'https://openrouter.ai/api/v1',
    logo_url: '/provider-icons/openrouter.ico',
  },
  {
    provider_id: 'glm',
    provider_type: 'openai_compatible',
    label: 'GLM',
    default_model: 'glm-4.5-air',
    models: ['glm-4.5', 'glm-4.5-air', 'glm-4-air-250414', 'glm-4-flash'],
    allow_custom_model: true,
    requires_base_url: true,
    default_base_url: 'https://open.bigmodel.cn/api/paas/v4',
    logo_url: '/provider-icons/glm.png',
  },
]

const resolvedProviderCatalog = computed(() =>
  (providerCatalog.value && providerCatalog.value.length) ? providerCatalog.value : fallbackProviderCatalog
)

const newCred = ref({
  provider_id: 'gemini' as ProviderId,
  api_key: '',
  base_url: '',
  models: [] as string[],
  default_model: '',
})

const inferProviderId = (credential: {
  credential_id: string
  provider_type?: string
  provider_id?: string
}): ProviderId | null => {
  const providerId = credential.provider_id as ProviderId | undefined
  if (
    providerId &&
    resolvedProviderCatalog.value &&
    resolvedProviderCatalog.value.some((provider) => provider.provider_id === providerId)
  ) {
    return providerId
  }
  if (resolvedProviderCatalog.value && resolvedProviderCatalog.value.some((provider) => provider.provider_id === credential.credential_id)) {
    return credential.credential_id as ProviderId
  }
  if (credential.provider_type === 'gemini') {
    return 'gemini'
  }
  return null
}

const existingConfigs = computed(() =>
  (credentials.value || [])
    .map((credential) => {
      const provider_id = inferProviderId(credential)
      if (!provider_id) return null
      return {
        credential_id: credential.credential_id,
        provider_id,
        provider_type: credential.provider_type || 'openai_compatible',
        models: Array.isArray(credential.models) ? credential.models : undefined,
        default_model: credential.default_model || '',
        base_url: credential.base_url || '',
      }
    })
    .filter((item): item is {
      credential_id: string
      provider_id: ProviderId
      provider_type: 'gemini' | 'openai_compatible'
      models: string[] | undefined
      default_model: string
      base_url: string
    } => item !== null)
)

const selectedProviderMeta = computed(
  () =>
    (resolvedProviderCatalog.value && resolvedProviderCatalog.value.find((provider) => provider.provider_id === activeProviderId.value)) ||
    (resolvedProviderCatalog.value && resolvedProviderCatalog.value[0]) ||
    null
)

const effectiveBaseUrlPlaceholder = computed(
  () => selectedProviderMeta.value?.default_base_url || 'https://api.openai.com/v1'
)

const activeProviderConfig = computed(
  () => (existingConfigs.value || []).find((config) => config.provider_id === activeProviderId.value) || null
)

const canSaveProvider = computed(() => {
  if (loading.value || !selectedProviderMeta.value || !newCred.value.models.length) return false
  if (!activeProviderConfig.value) return Boolean(newCred.value.api_key)
  return true
})

const selectedConversationProfile = computed(
  () => (configuredModelProfiles.value || []).find((profile) => profile.key === conversationModelProfileKey.value) || null
)

const selectedUtilityProfile = computed(
  () => (configuredModelProfiles.value || []).find((profile) => profile.key === utilityModelProfileKey.value) || null
)

const canSaveDefaultOptions = computed(
  () => Boolean(selectedConversationProfile.value && selectedUtilityProfile.value)
)

const isConfigured = (providerId: ProviderId) =>
  (existingConfigs.value || []).some((config) => config.provider_id === providerId)

const syncProviderDefaults = (providerId: ProviderId) => {
  const meta = (resolvedProviderCatalog.value || []).find((provider) => provider.provider_id === providerId)
  if (!meta) return

  const existing = (existingConfigs.value || []).find((config) => config.provider_id === providerId)
  const models = existing && Array.isArray(existing.models)
    ? [...existing.models]
    : [...meta.models]
  if (!models.length && existing?.default_model) {
    models.push(existing.default_model)
  }

  newCred.value.provider_id = providerId
  newCred.value.models = models
  newCred.value.default_model =
    (existing?.default_model && models.includes(existing.default_model) ? existing.default_model : '') ||
    newCred.value.models[0] ||
    meta.default_model ||
    ''
  newCred.value.base_url = meta.requires_base_url
    ? existing?.base_url || meta.default_base_url || ''
    : ''
  newCred.value.api_key = ''
  modelToAdd.value = ''
}

const syncDefaultOptions = () => {
  const conversation = defaultOptions.value?.conversation_model
  const utility = defaultOptions.value?.utility_model
  const firstConfigured = (configuredModelProfiles.value && configuredModelProfiles.value[0]?.key) || ''

  const exactConversation = (configuredModelProfiles.value || []).find(
    (profile) =>
      profile.provider_type === conversation?.provider_type &&
      profile.model === conversation?.model &&
      (!conversation?.provider_id || profile.provider_id === conversation.provider_id) &&
      (!conversation?.credential_id || profile.credential_id === conversation.credential_id)
  )
  const exactUtility = (configuredModelProfiles.value || []).find(
    (profile) =>
      profile.provider_type === utility?.provider_type &&
      profile.model === utility?.model &&
      (!utility?.provider_id || profile.provider_id === utility.provider_id) &&
      (!utility?.credential_id || profile.credential_id === utility.credential_id)
  )

  conversationModelProfileKey.value = exactConversation?.key || firstConfigured
  utilityModelProfileKey.value = exactUtility?.key || conversationModelProfileKey.value || firstConfigured
  markdownTheme.value = defaultOptions.value?.markdown_theme || 'academic'
}

watch(
  () => [activeProviderId.value, (credentials.value || []).length, (resolvedProviderCatalog.value || []).length],
  () => {
    syncProviderDefaults(activeProviderId.value)
  },
  { immediate: true }
)

watch(
  () => [
    (configuredModelProfiles.value || []).length,
    defaultOptions.value?.conversation_model?.model,
    defaultOptions.value?.utility_model?.model,
    defaultOptions.value?.markdown_theme
  ],
  () => {
    syncDefaultOptions()
  },
  { immediate: true }
)

const openModal = () => {
  activeSection.value = 'providers'
  activeProviderId.value = (existingConfigs.value && existingConfigs.value[0]?.provider_id) || 'gemini'
  syncProviderDefaults(activeProviderId.value)
  syncDefaultOptions()
  isOpen.value = true
}

const addModel = () => {
  const nextModel = modelToAdd.value.trim()
  if (!nextModel || newCred.value.models.includes(nextModel)) return
  newCred.value.models = [...newCred.value.models, nextModel]
  if (!newCred.value.default_model) {
    newCred.value.default_model = nextModel
  }
  modelToAdd.value = ''
}

const removeModel = (model: string) => {
  newCred.value.models = newCred.value.models.filter((item) => item !== model)
  if (newCred.value.default_model === model) {
    newCred.value.default_model = newCred.value.models[0] || ''
  }
}

const saveCredential = async () => {
  if (!canSaveProvider.value || !selectedProviderMeta.value) return
  try {
    const payload: Record<string, unknown> = {
      provider_type: selectedProviderMeta.value.provider_type,
      provider_id: activeProviderId.value,
      models: newCred.value.models,
      default_model: newCred.value.default_model || newCred.value.models[0] || selectedProviderMeta.value.default_model,
      headers: {},
    }
    if (selectedProviderMeta.value.requires_base_url) {
      payload.base_url = newCred.value.base_url || effectiveBaseUrlPlaceholder.value
    }
    const currentCredentialId = activeProviderConfig.value?.credential_id || activeProviderId.value
    if (activeProviderConfig.value && !newCred.value.api_key) {
      await store.updateCredential(currentCredentialId, payload as any)
    } else {
      await store.createCredential({
        ...(payload as any),
        credential_id: currentCredentialId,
        api_key: newCred.value.api_key,
      })
    }
    syncProviderDefaults(activeProviderId.value)
  } catch {
    alert('Failed to save credential')
  }
}

const saveDefaultOptions = async () => {
  if (!selectedConversationProfile.value || !selectedUtilityProfile.value) return
  try {
    await store.updateDefaultOptions({
      conversation_model: {
        provider_id: selectedConversationProfile.value.provider_id,
        provider_type: selectedConversationProfile.value.provider_type,
        credential_id: selectedConversationProfile.value.credential_id,
        model: selectedConversationProfile.value.model,
      },
      utility_model: {
        provider_id: selectedUtilityProfile.value.provider_id,
        provider_type: selectedUtilityProfile.value.provider_type,
        credential_id: selectedUtilityProfile.value.credential_id,
        model: selectedUtilityProfile.value.model,
      },
      markdown_theme: markdownTheme.value,
    })
  } catch {
    alert('Failed to save default options')
  }
}
</script>

<template>
  <div class="relative">
    <button
      @click="openModal"
      class="flex h-10 w-10 items-center justify-center rounded-xl text-on-surface-variant/40 transition-colors hover:bg-surface-container-high hover:text-on-surface"
      title="Global Settings"
    >
      <span class="material-symbols-outlined text-[24px]">settings</span>
    </button>

    <div
      v-if="isOpen"
      class="fixed inset-0 z-[100] grid place-items-center bg-on-surface/20 px-4 backdrop-blur-sm"
      @click.self="isOpen = false"
    >
      <div class="flex max-h-[84vh] w-[min(94vw,900px)] flex-col overflow-hidden rounded-3xl bg-surface-container-lowest shadow-2xl ghost-border">
        <div class="flex items-start justify-between gap-4 border-b border-outline-variant/10 bg-surface-container-low px-6 py-5">
          <div>
            <h3 class="flex items-center gap-2 font-serif text-xl font-bold text-primary">
              <span class="material-symbols-outlined text-[22px]">settings</span>
              System Configuration
            </h3>
            <p class="mt-1 font-sans text-[11px] leading-relaxed text-on-surface-variant/70">
              Configure providers and select the global default conversation and utility models.
            </p>
          </div>
          <button @click="isOpen = false" class="flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant/40 transition-colors hover:bg-primary-fixed hover:text-primary">
            <span class="material-symbols-outlined text-[22px]">close</span>
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-6 py-6">
          <section class="grid grid-cols-1 gap-8 md:grid-cols-[240px_1fr]">
            <!-- Sidebar -->
            <aside class="space-y-2">
              <h4 class="flex items-center gap-2 px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">
                <span class="material-symbols-outlined text-[14px]">vpn_key</span>
                Model Provider
              </h4>
              <button
                v-for="provider in resolvedProviderCatalog"
                :key="provider.provider_id"
                @click="activeSection = 'providers'; activeProviderId = provider.provider_id"
                class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left font-sans text-[13px] transition-colors ghost-border"
                :class="activeSection === 'providers' && activeProviderId === provider.provider_id ? 'bg-primary-fixed text-primary border-primary/20' : 'bg-surface-container-lowest text-on-surface-variant/70 hover:bg-surface-container-high hover:text-on-surface'"
              >
                <span class="flex items-center gap-2">
                  <img v-if="provider.logo_url" :src="provider.logo_url" :alt="provider.label" class="h-4 w-4 rounded-sm bg-white object-contain" />
                  <span v-else class="material-symbols-outlined text-[16px] opacity-70">memory</span>
                  {{ provider.label }}
                </span>
                <span
                  class="rounded bg-surface-container px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest transition-colors"
                  :class="isConfigured(provider.provider_id) ? 'bg-primary/10 text-primary' : 'text-on-surface-variant/40'"
                >
                  {{ isConfigured(provider.provider_id) ? 'set' : 'none' }}
                </span>
              </button>

              <div class="my-4 border-t border-outline-variant/10"></div>

              <button
                @click="activeSection = 'defaults'"
                class="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left font-sans text-[13px] transition-colors ghost-border"
                :class="activeSection === 'defaults' ? 'bg-primary-fixed text-primary border-primary/20' : 'bg-surface-container-lowest text-on-surface-variant/70 hover:bg-surface-container-high hover:text-on-surface'"
              >
                <span class="material-symbols-outlined text-[16px] opacity-70">tune</span>
                Default Options
              </button>
            </aside>

            <!-- Main Panel -->
            <div v-if="activeSection === 'providers'" class="space-y-6 rounded-3xl bg-surface-container-low p-6 ghost-border">
              <div class="flex items-center justify-between">
                <h5 class="font-sans text-[11px] font-bold uppercase tracking-widest text-on-surface-variant">
                  {{ selectedProviderMeta.label }} Configuration
                </h5>
                <span
                  class="rounded px-2 py-0.5 font-sans text-[9px] font-bold uppercase tracking-[0.16em]"
                  :class="activeProviderConfig ? 'bg-primary/10 text-primary' : 'bg-surface-container-high text-on-surface-variant/50'"
                >
                  {{ activeProviderConfig ? 'Configured' : 'Not Configured' }}
                </span>
              </div>

              <div class="space-y-2">
                <label class="px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">API Key</label>
                <input
                  v-model="newCred.api_key"
                  type="password"
                  :placeholder="activeProviderConfig ? '•••••••••••••••• (click to replace)' : 'Enter your API key'"
                  class="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-3 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20"
                />
              </div>

              <div class="space-y-3">
                <div class="space-y-2">
                  <label class="px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">Models</label>
                  <div class="space-y-3 rounded-2xl border border-outline-variant/10 bg-surface p-4">
                    <select
                      v-model="newCred.default_model"
                      name="default-model"
                      class="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-2 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20"
                    >
                      <option
                        v-for="model in newCred.models"
                        :key="model"
                        :value="model"
                      >
                        {{ model }}
                      </option>
                    </select>
                    <div
                      v-for="model in newCred.models"
                      :key="model"
                      class="flex items-center gap-3 rounded-xl bg-surface-container px-3 py-2 ghost-border"
                    >
                      <div class="min-w-0 flex-1 font-sans text-[13px] text-on-surface-variant">{{ model }}</div>
                      <button
                        @click="removeModel(model)"
                        class="flex h-6 w-6 items-center justify-center rounded-lg text-on-surface-variant/40 transition-colors hover:bg-surface-container-lowest hover:text-red-500"
                        title="Delete model"
                      >
                        <span class="material-symbols-outlined text-[16px]">delete</span>
                      </button>
                    </div>
                    <div class="grid gap-3 sm:grid-cols-[1fr_auto] pt-2">
                      <input
                        v-model="modelToAdd"
                        type="text"
                        placeholder="Enter model id"
                        class="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-2 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20"
                      />
                      <button
                        @click="addModel"
                        :disabled="!modelToAdd.trim()"
                        class="inline-flex items-center justify-center gap-2 rounded-xl bg-primary-fixed px-4 py-2 font-sans text-[11px] font-bold uppercase tracking-widest text-primary transition-colors hover:bg-primary-container hover:text-on-primary disabled:opacity-50 disabled:hover:bg-primary-fixed disabled:hover:text-primary"
                      >
                        <span class="material-symbols-outlined text-[16px]">add</span>
                        Add
                      </button>
                    </div>
                    <span v-if="!newCred.models.length" class="block font-sans text-[11px] italic text-on-surface-variant/50 pt-2">
                      Add one or more models for this provider.
                    </span>
                  </div>
                </div>
              </div>

              <div v-if="selectedProviderMeta.requires_base_url" class="space-y-2">
                <label class="px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">Base URL</label>
                <input
                  v-model="newCred.base_url"
                  :placeholder="effectiveBaseUrlPlaceholder"
                  class="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-3 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20"
                />
              </div>

              <div class="pt-4 border-t border-outline-variant/10">
                <button
                  @click="saveCredential"
                  :disabled="!canSaveProvider"
                  class="w-full rounded-full bg-primary py-3 font-sans text-[11px] font-bold uppercase tracking-widest text-on-primary transition-colors hover:bg-primary-container disabled:cursor-not-allowed disabled:bg-surface-container disabled:text-on-surface-variant/40"
                >
                  Save Provider Config
                </button>
              </div>
            </div>

            <div v-else class="space-y-6 rounded-3xl bg-surface-container-low p-6 ghost-border">
              <h5 class="font-sans text-[11px] font-bold uppercase tracking-widest text-on-surface-variant">
                Default Options
              </h5>

              <div class="space-y-2">
                <label class="px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">Default Conversation Model</label>
                <select
                  v-model="conversationModelProfileKey"
                  class="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-3 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20"
                >
                  <option v-for="profile in configuredModelProfiles" :key="profile.key" :value="profile.key">
                    {{ profile.label }}
                  </option>
                </select>
              </div>

              <div class="space-y-2">
                <label class="px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">Utility Model</label>
                <select
                  v-model="utilityModelProfileKey"
                  class="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-3 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20"
                >
                  <option v-for="profile in configuredModelProfiles" :key="profile.key" :value="profile.key">
                    {{ profile.label }}
                  </option>
                </select>
                <p class="px-1 font-sans text-[10px] italic text-on-surface-variant/50">Only models already configured in providers can be selected.</p>
              </div>

              <div class="space-y-2">
                <label class="px-1 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">Markdown Theme</label>
                <select
                  v-model="markdownTheme"
                  class="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-4 py-3 font-sans text-[13px] text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary/20"
                >
                  <option value="academic">Academic (严肃学术风)</option>
                  <option value="reading">Reading (温润阅读风)</option>
                  <option value="geek">Geek (极客工程风)</option>
                </select>
                <p class="px-1 font-sans text-[10px] italic text-on-surface-variant/50">Select the typography style for rendering Markdown content.</p>
              </div>

              <div class="pt-4 border-t border-outline-variant/10">
                <button
                  @click="saveDefaultOptions"
                  :disabled="!canSaveDefaultOptions || loading"
                  class="w-full rounded-full bg-primary py-3 font-sans text-[11px] font-bold uppercase tracking-widest text-on-primary transition-colors hover:bg-primary-container disabled:cursor-not-allowed disabled:bg-surface-container disabled:text-on-surface-variant/40"
                >
                  Save Default Options
                </button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
