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
        <div class="brand-mark" aria-hidden="true">
          <img class="brand-mark-image" src="/favicon.png?v=3" alt="" />
        </div>
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

      <nav class="workspace-switcher" aria-label="Workspace views">
        <button
          type="button"
          :class="{ active: activeTab === 'chat' || activeTab === 'agent' }"
          @click="showConversations"
        >
          <span class="workspace-switcher-icon" aria-hidden="true">
            <span class="material-symbols-outlined">chat_bubble</span>
          </span>
          <span>Conversations</span>
        </button>
        <button
          type="button"
          :class="{ active: activeTab === 'book' || activeTab === 'knowledge' }"
          @click="showLibrary"
        >
          <span class="workspace-switcher-icon" aria-hidden="true">
            <span class="material-symbols-outlined">book_2</span>
          </span>
          <span>Library</span>
        </button>
      </nav>

      <div class="sidebar-content">
        <div v-if="activeTab === 'chat' || activeTab === 'agent'" class="sidebar-section">
          <SessionTree />
        </div>

        <div v-else class="sidebar-section">
          <BookOutline />
        </div>
      </div>

      <div class="sidebar-footer">
        <GlobalSettings />
      </div>
    </aside>

    <main class="conversation-workspace">
      <ReaderPanel
        v-if="activeTab === 'knowledge'"
        :key="currentNode?.id || 'knowledge-page'"
        page-mode
      />

      <template v-else>
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
              :knowledge-nodes="outline"
              :assistant-name="assistantName"
              :can-regenerate="canRegenerateMessage(msg.message_id)"
              :is-loading="loading && isLatestMessage(msg.message_id)"
              :agent-steps="isLatestMessage(msg.message_id) ? agentRunSteps : []"
              :approval-busy="knowledgeApprovalBusyMessageIds.includes(msg.message_id)"
              @regenerate="handleRegenerate"
              @approve-knowledge="store.acceptSuggestedDrafts"
              @reject-knowledge="store.rejectSuggestedDrafts"
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
        <ChatComposer
          :loading="loading"
          :can-cancel="askInFlight"
          @ask="store.ask"
          @cancel="store.cancelAsk"
        />
      </footer>
      </template>
    </main>

    <SelectionActionMenu />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import { buildWorkspaceHref, readWorkspaceTarget } from './services/workspaceNavigation'

const store = useWorkspaceStore()
const {
  currentSession,
  currentNode,
  outline,
  loading,
  askInFlight,
  activeTab,
  agentRunSteps,
  knowledgeApprovalBusyMessageIds,
} = storeToRefs(store)

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
const isSidebarOpen = ref(false)
let workspaceInitialized = false
let applyingHistoryTarget = false

const workspaceHrefMatches = (href: string) =>
  new URL(href).toString() === new URL(window.location.href).toString()

const syncConversationUrl = (mode: 'push' | 'replace' = 'push') => {
  const href = buildWorkspaceHref({
    view: 'conversation',
    sessionId: currentSession.value?.session_id,
  })
  if (workspaceHrefMatches(href)) return
  const method = mode === 'push' ? 'pushState' : 'replaceState'
  window.history[method](window.history.state, '', href)
}

const scrollToBottom = async () => {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

const scrollToTop = async () => {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = 0
  }
}

watch(
  () => {
    const messages = currentSession.value?.messages
    return [
      currentSession.value?.session_id || null,
      messages?.length ? messages[messages.length - 1]?.content : null,
    ] as const
  },
  ([sessionId, lastMessageContent], [previousSessionId, previousLastMessageContent]) => {
    if (sessionId !== previousSessionId) {
      void scrollToTop()
      return
    }
    if (lastMessageContent !== previousLastMessageContent) {
      void scrollToBottom()
    }
  }
)

watch(
  () => [activeTab.value, currentSession.value?.session_id || null] as const,
  ([tab]) => {
    if (!workspaceInitialized || applyingHistoryTarget || tab !== 'chat') return
    syncConversationUrl()
  },
  { flush: 'post' }
)

const handleGlobalShortcut = (event: KeyboardEvent) => {
  const target = event.target as HTMLElement | null
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName || '')) return
  if (event.key.toLocaleLowerCase() === 'n' && !event.metaKey && !event.ctrlKey && !event.altKey) {
    event.preventDefault()
    startNewInquiry()
  }
}

const initializeWorkspace = async () => {
  const target = readWorkspaceTarget()

  await Promise.all([
    store.fetchProviderOptions(),
    store.fetchStrategyAgents(),
    store.fetchAnswerStyles(),
    store.fetchSessions(),
    store.fetchOutline(),
    store.fetchCredentials(),
  ])

  if (target.sessionId) {
    await store.selectSession(target.sessionId)
  }

  if (target.nodeId) {
    await store.selectNode(target.nodeId)
  }

  if (target.view === 'fork' && target.sessionId && target.messageId) {
    await store.fork(target.messageId)
    const openedSessionId = currentSession.value?.session_id || target.sessionId
    window.history.replaceState(
      window.history.state,
      '',
      buildWorkspaceHref({ view: 'conversation', sessionId: openedSessionId })
    )
    activeTab.value = 'chat'
  } else if (target.view === 'details' && target.messageId) {
    store.openAgentStateForMessage(target.messageId)
    await nextTick()
    if (scrollContainer.value) scrollContainer.value.scrollTop = 0
  } else if (target.view === 'knowledge' && target.nodeId) {
    activeTab.value = 'knowledge'
  } else if (target.view === 'library' && target.nodeId) {
    // Keep old knowledge links working while moving details to their own page.
    activeTab.value = 'knowledge'
    window.history.replaceState(
      window.history.state,
      '',
      buildWorkspaceHref({
        view: 'knowledge',
        sessionId: target.sessionId,
        nodeId: target.nodeId,
      })
    )
  } else if (target.view === 'library') {
    activeTab.value = 'book'
  }

  workspaceInitialized = true
  if (!target.view || target.view === 'conversation') {
    syncConversationUrl('replace')
  }
}

const applyHistoryTarget = async () => {
  const target = readWorkspaceTarget()
  applyingHistoryTarget = true
  try {
    if (target.sessionId && target.sessionId !== currentSession.value?.session_id) {
      await store.selectSession(target.sessionId)
    } else if (!target.sessionId && (!target.view || target.view === 'conversation')) {
      store.newSession()
    }

    if (target.view === 'details' && target.messageId) {
      store.openAgentStateForMessage(target.messageId)
    } else if (target.view === 'knowledge' && target.nodeId) {
      if (target.nodeId !== currentNode.value?.id) await store.selectNode(target.nodeId)
      activeTab.value = 'knowledge'
    } else if (target.view === 'library') {
      activeTab.value = 'book'
    } else {
      activeTab.value = 'chat'
    }
  } finally {
    await nextTick()
    applyingHistoryTarget = false
  }
}

onMounted(() => {
  void initializeWorkspace()
  document.addEventListener('keydown', handleGlobalShortcut)
  window.addEventListener('popstate', applyHistoryTarget)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleGlobalShortcut)
  window.removeEventListener('popstate', applyHistoryTarget)
})

const showConversations = () => {
  activeTab.value = 'chat'
  isSidebarOpen.value = false
}

const showLibrary = () => {
  activeTab.value = 'book'
  isSidebarOpen.value = false
  const href = buildWorkspaceHref({
    view: 'library',
    sessionId: currentSession.value?.session_id,
  })
  if (!workspaceHrefMatches(href)) {
    window.history.pushState(window.history.state, '', href)
  }
}

const startNewInquiry = () => {
  store.newSession()
  activeTab.value = 'chat'
  isSidebarOpen.value = false
}

const usePrompt = (prompt: string) => store.setDraftQuestion(prompt)

const handleRegenerate = (messageId: string) => store.regenerate(messageId)

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
