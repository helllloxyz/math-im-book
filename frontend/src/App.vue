<template>
  <div class="app-shell">
    <button
      v-if="!isSidebarOpen"
      class="mobile-nav-trigger"
      type="button"
      aria-label="Open navigation"
      @click="isSidebarOpen = true"
    >
      <span class="material-symbols-outlined" aria-hidden="true">menu</span>
    </button>

    <div
      v-if="isSidebarOpen"
      class="mobile-nav-backdrop"
      aria-hidden="true"
      @click="isSidebarOpen = false"
    ></div>

    <aside class="workspace-sidebar" :class="{ 'is-open': isSidebarOpen }">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">∑</div>
        <div>
          <p class="brand-name">Mathbook</p>
          <p class="brand-note">Think in context</p>
        </div>
        <button
          class="mobile-nav-close"
          type="button"
          aria-label="Close navigation"
          @click="isSidebarOpen = false"
        >
          <span class="material-symbols-outlined" aria-hidden="true">close</span>
        </button>
      </div>

      <button class="new-inquiry-button" type="button" @click="startNewInquiry">
        <span class="material-symbols-outlined" aria-hidden="true">add</span>
        <span>New inquiry</span>
        <kbd>N</kbd>
      </button>

      <nav class="workspace-switcher" aria-label="Workspace views">
        <button
          type="button"
          :class="{ active: activeTab === 'chat' || activeTab === 'agent' }"
          @click="showConversations"
        >
          <span class="material-symbols-outlined" aria-hidden="true">forum</span>
          Conversations
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'book' }"
          @click="showLibrary"
        >
          <span class="material-symbols-outlined" aria-hidden="true">library_books</span>
          Library
        </button>
      </nav>

      <div class="sidebar-content">
        <div v-if="activeTab === 'chat' || activeTab === 'agent'" class="sidebar-section">
          <SessionTree />
          <div v-if="!sessions.length" class="sidebar-empty">
            <span class="material-symbols-outlined" aria-hidden="true">chat_bubble_outline</span>
            <p>Your conversations will collect here.</p>
          </div>
        </div>

        <div v-else class="sidebar-section">
          <BookOutline />
          <div v-if="!outline.length" class="sidebar-empty">
            <span class="material-symbols-outlined" aria-hidden="true">auto_stories</span>
            <p>Knowledge notes appear as you explore.</p>
          </div>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="system-status">
          <span class="status-dot"></span>
          <span>Local workspace</span>
        </div>
        <GlobalSettings />
      </div>
    </aside>

    <main class="conversation-workspace">
      <header class="workspace-header">
        <div class="workspace-title-block">
          <button
            v-if="activeTab === 'agent'"
            class="back-button"
            type="button"
            aria-label="Back to conversation"
            @click="showConversations"
          >
            <span class="material-symbols-outlined" aria-hidden="true">arrow_back</span>
          </button>
          <div>
            <p class="workspace-kicker">
              {{ activeTab === 'agent' ? 'Response details' : 'Conversation' }}
            </p>
            <h1>{{ workspaceTitle }}</h1>
          </div>
        </div>

        <div class="workspace-actions">
          <div v-if="loading" class="working-status" role="status">
            <span class="working-dot"></span>
            Thinking
          </div>
          <ModelSettings v-if="activeTab !== 'agent'" />
        </div>
      </header>

      <div ref="scrollContainer" class="workspace-scroll">
        <AgentStatePage v-if="activeTab === 'agent'" />

        <div
          v-else-if="currentSession && currentSession.messages.length"
          class="conversation-transcript"
          data-chat-transcript
        >
          <transition-group name="message">
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

        <section v-else class="empty-workspace">
          <div class="empty-orbit" aria-hidden="true">
            <span>∫</span>
          </div>
          <p class="empty-eyebrow">A quiet place to work things out</p>
          <h2>Start with a question.</h2>
          <p class="empty-description">
            Ask for a proof, unpack an intuition, or check a derivation. Useful ideas can be saved to your library as you go.
          </p>
          <div class="prompt-suggestions" aria-label="Example questions">
            <button type="button" @click="usePrompt('Explain the core intuition before the formal proof.')">
              Explain the intuition
              <span class="material-symbols-outlined" aria-hidden="true">north_east</span>
            </button>
            <button type="button" @click="usePrompt('Derive this result step by step and state every assumption.')">
              Build a derivation
              <span class="material-symbols-outlined" aria-hidden="true">north_east</span>
            </button>
            <button type="button" @click="usePrompt('Check my reasoning and identify the first incorrect step.')">
              Check my reasoning
              <span class="material-symbols-outlined" aria-hidden="true">north_east</span>
            </button>
          </div>
        </section>
      </div>

      <footer v-if="activeTab !== 'agent'" class="composer-dock">
        <ChatComposer :loading="loading" @ask="store.ask" />
      </footer>
    </main>

    <aside
      v-if="currentNode"
      data-reader-panel-shell
      class="reader-panel-shell"
      :class="{ expanded: isReaderExpanded }"
    >
      <ReaderPanel
        :key="currentNode.id"
        :is-expanded="isReaderExpanded"
        @toggle-expanded="isReaderExpanded = !isReaderExpanded"
        @close="closeReader"
      />
    </aside>

    <SelectionActionMenu />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
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

const workspaceTitle = computed(() => {
  if (activeTab.value === 'agent') return 'How this response was made'
  return currentSession.value?.title || 'New inquiry'
})

const scrollContainer = ref<HTMLElement | null>(null)
const isReaderExpanded = ref(false)
const isSidebarOpen = ref(false)

const scrollToBottom = async () => {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

watch(
  () => {
    const messages = currentSession.value?.messages
    if (!messages?.length) return null
    return messages[messages.length - 1]?.content
  },
  scrollToBottom
)

onMounted(() => {
  store.fetchProviderOptions()
  store.fetchStrategyAgents()
  store.fetchAnswerStyles()
  store.fetchSessions()
  store.fetchOutline()
  store.fetchCredentials()
})

const showConversations = () => {
  activeTab.value = 'chat'
  isSidebarOpen.value = false
}

const showLibrary = () => {
  activeTab.value = 'book'
  isSidebarOpen.value = false
}

const startNewInquiry = () => {
  store.newSession()
  activeTab.value = 'chat'
  isSidebarOpen.value = false
}

const usePrompt = (prompt: string) => store.setDraftQuestion(prompt)

const closeReader = () => {
  currentNode.value = null
  isReaderExpanded.value = false
}

const handleFork = (messageId: string) => store.fork(messageId)
const handleRegenerate = (messageId: string) => store.regenerate(messageId)
const handleReviewState = async (messageId: string) => {
  store.openAgentStateForMessage(messageId)
  await nextTick()
  if (scrollContainer.value) scrollContainer.value.scrollTop = 0
}
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
