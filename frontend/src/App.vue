<template>
  <div class="app-shell flex h-screen overflow-hidden bg-surface">
    <!-- 1. SideNavBar (Slim Rail) -->
    <aside class="flex flex-col h-full py-8 bg-slate-950 w-20 items-center z-50">
      <div class="mb-12">
        <span class="text-primary-fixed font-serif font-bold text-2xl">Σ</span>
      </div>
      <nav class="flex flex-col gap-10 flex-1">
        <button
          @click="activeTab = 'chat'"
          class="flex flex-col items-center gap-1 group transition-all"
          :class="activeTab === 'chat' ? 'text-primary-fixed' : 'text-slate-500 hover:text-slate-300'"
        >
          <span class="material-symbols-outlined text-2xl" :style="activeTab === 'chat' ? 'font-variation-settings: \'FILL\' 1;' : ''">space_dashboard</span>
          <span class="font-sans text-[9px] uppercase tracking-tighter">Workspace</span>
        </button>
        <button
          @click="activeTab = 'book'"
          class="flex flex-col items-center gap-1 group transition-all"
          :class="activeTab === 'book' ? 'text-primary-fixed' : 'text-slate-500 hover:text-slate-300'"
        >
          <span class="material-symbols-outlined text-2xl" :style="activeTab === 'book' ? 'font-variation-settings: \'FILL\' 1;' : ''">local_library</span>
          <span class="font-sans text-[9px] uppercase tracking-tighter">Library</span>
        </button>
        <button
          @click="activeTab = 'agent'"
          class="flex flex-col items-center gap-1 group transition-all"
          :class="activeTab === 'agent' ? 'text-primary-fixed' : 'text-slate-500 hover:text-slate-300'"
        >
          <span class="material-symbols-outlined text-2xl" :style="activeTab === 'agent' ? 'font-variation-settings: \'FILL\' 1;' : ''">schema</span>
          <span class="font-sans text-[9px] uppercase tracking-tighter">Agent</span>
        </button>
      </nav>
      <div class="mt-auto">
        <GlobalSettings />
      </div>
    </aside>

    <!-- 2. Exploration Sidebar -->
    <aside class="w-72 bg-surface-container-low flex flex-col border-r-0">
      <div class="p-6">
        <h1 class="font-serif italic text-xl text-primary mb-1">The Scriptorium</h1>
        <p
          v-if="activeTab === 'agent'"
          data-sidebar-context-label
          class="font-sans text-[10px] text-on-surface-variant/50 uppercase tracking-widest"
        >
          Agent State
        </p>
      </div>
      
      <div class="flex-1 overflow-y-auto px-4 space-y-8">
        <div v-if="activeTab === 'chat'" class="space-y-6">
          <SessionTree />
          <div v-if="!sessions.length" class="px-2 py-4 italic text-sm text-on-surface-variant/60 font-serif">
            Begin a new inquiry to see branches here.
          </div>
        </div>

        <div v-if="activeTab === 'book'" class="space-y-6">
          <BookOutline />
          <div v-if="!outline.length" class="px-2 py-4 italic text-sm text-on-surface-variant/60 font-serif">
            Reference nodes appear as you explore.
          </div>
        </div>
      </div>
    </aside>

    <!-- 3. Main Workspace -->
    <main class="flex-1 flex flex-col relative bg-surface-container-lowest">
      <header class="glass-panel sticky top-0 z-20 flex justify-between items-center w-full px-12 h-20">
        <div class="flex items-center gap-8">
          <span class="text-lg font-serif italic text-primary">Inquiry Workspace</span>
          <nav class="hidden md:flex gap-6">
            <span class="font-sans uppercase tracking-widest text-[10px] text-primary border-b-2 border-primary pb-1 cursor-default">Derivation</span>
            <span class="font-sans uppercase tracking-widest text-[10px] text-on-surface-variant/40 hover:text-primary transition-colors cursor-pointer">Intuition</span>
            <span class="font-sans uppercase tracking-widest text-[10px] text-on-surface-variant/40 hover:text-primary transition-colors cursor-pointer">Verification</span>
          </nav>
        </div>
        <div class="flex items-center gap-6">
          <div v-if="loading" class="flex items-center gap-2 px-3 py-1 bg-primary-fixed rounded-full text-[10px] text-primary animate-pulse">
            <span class="material-symbols-outlined text-xs animate-spin">progress_activity</span>
            Updating
          </div>
          <ModelSettings />
        </div>
      </header>

      <div ref="scrollContainer" class="flex-1 overflow-y-auto scroll-smooth">
        <AgentStatePage v-if="activeTab === 'agent'" />

        <div
          v-else-if="currentSession && currentSession.messages.length"
          class="max-w-4xl mx-auto p-8 space-y-4"
          data-chat-transcript
        >
          <transition-group name="fade">
            <ChatMessage
              v-for="msg in currentSession.messages"
              :key="msg.message_id" 
              :message="msg"
              :session-id="currentSession?.session_id"
              :assistant-name="assistantName"
              :can-regenerate="canRegenerateMessage(msg.message_id)"
              :is-loading="loading && isLatestMessage(msg.message_id)"
              @fork="handleFork"
              @anchor-click="handleAnchorClick"
              @regenerate="handleRegenerate"
              @review-state="handleReviewState"
            />
          </transition-group>
        </div>
        
        <div v-else class="max-w-3xl mx-auto py-20 p-12">
          <div class="flex flex-col items-center text-center space-y-8">
            <div class="w-16 h-16 rounded-full bg-primary-fixed flex items-center justify-center text-primary">
              <span class="material-symbols-outlined text-3xl">lightbulb_outline</span>
            </div>
            <div>
              <h2 class="text-4xl font-serif mb-4">Inquire of the Scriptorium</h2>
              <p class="text-on-surface-variant/70 leading-relaxed font-serif text-lg">
                Ask for a proof, a derivation, or a physical intuition. Our synthesis engines are at your service.
              </p>
            </div>
          </div>
        </div>
      </div>

      <footer class="p-8 max-w-4xl mx-auto w-full">
        <ChatComposer @ask="store.ask" :loading="loading" />
      </footer>
    </main>

    <!-- 4. Right Library Panel -->
    <aside
      data-reader-panel-shell
      class="bg-surface flex flex-col border-l border-outline-variant/10 transition-[width] duration-300 ease-out"
      :class="isReaderExpanded ? 'w-[780px]' : 'w-[520px]'"
    >
      <ReaderPanel
        :key="currentNode?.id || 'empty'"
        :is-expanded="isReaderExpanded"
        @toggle-expanded="isReaderExpanded = !isReaderExpanded"
      />
    </aside>

    <SelectionActionMenu />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from 'vue'
import SessionTree from './components/explorer/SessionTree.vue'
import BookOutline from './components/explorer/BookOutline.vue'
import AgentStatePage from './components/agent/AgentStatePage.vue'
import ChatMessage from './components/chat/ChatMessage.vue'
import ChatComposer from './components/chat/ChatComposer.vue'
import ModelSettings from './components/chat/ModelSettings.vue'
import GlobalSettings from './components/explorer/GlobalSettings.vue'
import ReaderPanel from './components/reader/ReaderPanel.vue'
import SelectionActionMenu from './components/common/SelectionActionMenu.vue'
import { useWorkspaceStore } from './stores/workspace'
import { storeToRefs } from 'pinia'

const store = useWorkspaceStore()
const { sessions, outline, currentSession, currentNode, loading, activeTab } = storeToRefs(store)

const assistantNames = ['Gauss', 'Noether', 'Euler', 'Riemann', 'Hypatia', 'Newton', 'Lagrange', 'Fourier']

const hashSeed = (seed: string) => {
  let hash = 0
  for (const char of seed) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }
  return hash
}

const assistantName = computed(() => {
  const session = currentSession.value
  const firstUserMessage = session?.messages.find((message) => message.role === 'user')
  const seed = firstUserMessage?.content || session?.session_id || session?.title || 'new-session'
  return assistantNames[hashSeed(seed) % assistantNames.length]
})

const scrollContainer = ref<HTMLElement | null>(null)
const isReaderExpanded = ref(false)

const scrollToBottom = async () => {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

watch(
  () => {
    const msgs = currentSession.value?.messages
    if (!msgs?.length) return null
    return msgs[msgs.length - 1]?.content
  },
  () => { scrollToBottom() }
)

onMounted(() => {
  store.fetchProviderOptions()
  store.fetchStrategyAgents()
  store.fetchAnswerStyles()
  store.fetchSessions()
  store.fetchOutline()
  store.fetchCredentials()
})

const handleFork = (messageId: string) => store.fork(messageId)
const handleRegenerate = (messageId: string) => store.regenerate(messageId)
const handleReviewState = (messageId: string) => store.openAgentStateForMessage(messageId)
const handleAnchorClick = (anchor: { node_id?: string | null }) => {
  if (anchor.node_id) store.selectNode(anchor.node_id)
}

const canRegenerateMessage = (messageId: string) => {
  const messages = currentSession.value?.messages || []
  const latestMessage = messages[messages.length - 1]
  return latestMessage?.role === 'assistant' && latestMessage.message_id === messageId
}

const isLatestMessage = (messageId: string) => {
  const messages = currentSession.value?.messages || []
  return messages[messages.length - 1]?.message_id === messageId
}
</script>

<style>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
