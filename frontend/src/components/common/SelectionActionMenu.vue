<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useWorkspaceStore, type SelectionActionPayload } from '../../stores/workspace'
import type { SelectionKnowledgePromptKind } from '../../services/api'

type MenuMode = 'continue' | 'knowledge' | null

interface SelectionSnapshot {
  text: string
  payload: SelectionActionPayload
  rect: DOMRect
}

const store = useWorkspaceStore()
const { currentSession, currentNode, activeTab } = storeToRefs(store)

const menuRef = ref<HTMLElement | null>(null)
const continueButtonRef = ref<HTMLButtonElement | null>(null)
const isOpen = ref(false)
const mode = ref<MenuMode>(null)
const selectionSnapshot = ref<SelectionSnapshot | null>(null)
const menuPosition = ref({ top: 0, left: 0 })

const continuePresets = [
  {
    key: 'continue-meaning',
    label: '怎么理解',
    prompt: '请解释我该如何理解下面选中的内容：',
  },
  {
    key: 'continue-intuition',
    label: '形象解释',
    prompt: '请给出下面选中内容的形象解释和直觉图景：',
  },
  {
    key: 'continue-detail',
    label: '具体说明',
    prompt: '请具体说明下面选中内容的关键步骤和容易误解的点：',
  },
] as const

const knowledgePresets: Array<{
  key: string
  label: string
  promptKind: SelectionKnowledgePromptKind
}> = [
  { key: 'knowledge-definition', label: '定义', promptKind: 'definition' },
  { key: 'knowledge-intuition', label: '形象解释', promptKind: 'intuition_node' },
  { key: 'knowledge-example', label: '应用例子', promptKind: 'example' },
  { key: 'knowledge-proof', label: '证明', promptKind: 'proof' },
]

const menuStyle = computed(() => ({
  top: `${menuPosition.value.top}px`,
  left: `${menuPosition.value.left}px`,
}))

const handleResize = () => {
  void updateMenuPosition()
}

const trimSelectedText = (text: string) => text.trim().replace(/\s+\n/g, '\n')

const quoteSelectedText = (text: string) =>
  trimSelectedText(text)
    .split('\n')
    .map((line) => `> ${line}`)
    .join('\n')

const buildDraftQuestion = (prompt: string, text: string) => `${prompt}\n\n${quoteSelectedText(text)}`

const clampPosition = (left: number, top: number, width: number, height: number) => {
  const viewportPadding = 12
  const maxLeft = Math.max(viewportPadding, window.innerWidth - width - viewportPadding)
  const maxTop = Math.max(viewportPadding, window.innerHeight - height - viewportPadding)
  return {
    left: Math.min(Math.max(left, viewportPadding), maxLeft),
    top: Math.min(Math.max(top, viewportPadding), maxTop),
  }
}

const updateMenuPosition = async (rect?: DOMRect) => {
  if (!isOpen.value) return
  await nextTick()
  const activeRect = rect || selectionSnapshot.value?.rect
  if (!activeRect) return
  const menuWidth = menuRef.value?.offsetWidth || 288
  const menuHeight = menuRef.value?.offsetHeight || 180
  const preferredLeft = activeRect.left
  const preferredTop = activeRect.bottom + 12
  const flippedTop = activeRect.top - menuHeight - 12
  const fitsBelow = preferredTop + menuHeight + 12 <= window.innerHeight
  const top = fitsBelow ? preferredTop : flippedTop
  const position = clampPosition(preferredLeft, top, menuWidth, menuHeight)
  menuPosition.value = position
}

const focusPrimaryAction = async () => {
  await nextTick()
  continueButtonRef.value?.focus()
}

const closeMenu = () => {
  isOpen.value = false
  mode.value = null
  selectionSnapshot.value = null
}

const getSelectionSnapshot = (): SelectionSnapshot | null => {
  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null

  const text = trimSelectedText(selection.toString())
  if (!text) return null

  const range = selection.getRangeAt(0)
  const ancestor =
    range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
      ? (range.commonAncestorContainer as Element)
      : range.commonAncestorContainer.parentElement
  const sourceElement = ancestor?.closest(
    '[data-selection-source="chat-message"], [data-selection-source="knowledge-node"]'
  ) as HTMLElement | null
  if (!sourceElement) return null

  const sourceType = sourceElement.dataset.selectionSource as SelectionActionPayload['sourceType'] | undefined
  if (sourceType !== 'chat-message' && sourceType !== 'knowledge-node') return null

  const rect = range.getBoundingClientRect()

  if (sourceType === 'chat-message') {
    const sessionId = sourceElement.dataset.sessionId || undefined
    const messageId = sourceElement.dataset.messageId || undefined
    if (!sessionId || !messageId) return null
    return {
      text,
      rect,
      payload: {
        text,
        sourceType,
        sessionId,
        messageId,
      },
    }
  }

  const nodeId = sourceElement.dataset.nodeId || undefined
  if (!nodeId) return null
  return {
    text,
    rect,
    payload: {
      text,
      sourceType,
      nodeId,
    },
  }
}

const openFromSelection = async () => {
  const snapshot = getSelectionSnapshot()
  if (!snapshot) {
    closeMenu()
    return false
  }
  selectionSnapshot.value = snapshot
  isOpen.value = true
  mode.value = null
  await updateMenuPosition(snapshot.rect)
  await focusPrimaryAction()
  return true
}

const handlePrimaryAction = async (nextMode: Exclude<MenuMode, null>) => {
  mode.value = nextMode
  await updateMenuPosition()
}

const handleContinuePreset = (prompt: string) => {
  const snapshot = selectionSnapshot.value
  if (!snapshot) return
  const question = buildDraftQuestion(prompt, snapshot.text)
  if (snapshot.payload.sourceType === 'knowledge-node') {
    store.newSession()
  }
  store.setDraftQuestion(question)
  closeMenu()
}

const handleKnowledgePreset = (promptKind: SelectionKnowledgePromptKind) => {
  const snapshot = selectionSnapshot.value
  if (!snapshot) return
  void store.generateKnowledgeFromSelection(snapshot.payload, promptKind)
  closeMenu()
}

const handleKeydown = async (event: KeyboardEvent) => {
  if (event.key === 'Escape' && isOpen.value) {
    event.preventDefault()
    closeMenu()
    return
  }

  const shortcut = event.key.toLowerCase() === 'q' && (event.ctrlKey || event.metaKey)
  if (!shortcut) return
  const opened = await openFromSelection()
  if (opened) {
    event.preventDefault()
  }
}

const handleSelectionChange = () => {
  if (!isOpen.value) return
  const snapshot = getSelectionSnapshot()
  if (!snapshot) {
    closeMenu()
    return
  }
  selectionSnapshot.value = snapshot
  void updateMenuPosition(snapshot.rect)
}

const handlePointerDown = (event: PointerEvent) => {
  const target = event.target as Node | null
  if (!isOpen.value || !target || menuRef.value?.contains(target)) return
  closeMenu()
}

const handleScroll = () => {
  if (isOpen.value) closeMenu()
}

watch(
  () => [currentSession.value?.session_id, currentNode.value?.id, activeTab.value],
  () => {
    if (isOpen.value) closeMenu()
  }
)

watch(isOpen, (next) => {
  if (!next) return
  void updateMenuPosition()
})

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.addEventListener('selectionchange', handleSelectionChange)
  document.addEventListener('pointerdown', handlePointerDown)
  window.addEventListener('scroll', handleScroll, true)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.removeEventListener('selectionchange', handleSelectionChange)
  document.removeEventListener('pointerdown', handlePointerDown)
  window.removeEventListener('scroll', handleScroll, true)
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div
    v-if="isOpen"
    ref="menuRef"
    data-selection-action-menu
    role="dialog"
    aria-label="Selection actions"
    class="fixed z-50 w-[18rem] rounded-lg border border-outline-variant/20 bg-surface-container-low/95 p-2 shadow-xl backdrop-blur"
    :style="menuStyle"
  >
    <div class="flex items-center gap-2 px-1 pb-2">
      <button
        ref="continueButtonRef"
        data-selection-primary="continue"
        aria-label="继续问"
        :aria-pressed="mode === 'continue'"
        class="flex-1 rounded-lg px-3 py-2 text-sm font-medium text-on-surface transition-colors hover:bg-primary-fixed hover:text-primary"
        :class="mode === 'continue' ? 'bg-primary-fixed text-primary' : 'bg-surface-container-lowest'"
        @click="handlePrimaryAction('continue')"
      >
        继续问
      </button>
      <button
        data-selection-primary="knowledge"
        aria-label="知识节点"
        :aria-pressed="mode === 'knowledge'"
        class="flex-1 rounded-lg px-3 py-2 text-sm font-medium text-on-surface transition-colors hover:bg-primary-fixed hover:text-primary"
        :class="mode === 'knowledge' ? 'bg-primary-fixed text-primary' : 'bg-surface-container-lowest'"
        @click="handlePrimaryAction('knowledge')"
      >
        知识节点
      </button>
    </div>

    <div v-if="mode === 'continue'" class="space-y-1 px-1 pb-1">
      <button
        v-for="preset in continuePresets"
        :key="preset.key"
        :data-selection-secondary="preset.key"
        class="w-full rounded-lg px-3 py-2 text-left text-sm text-on-surface-variant transition-colors hover:bg-primary-fixed hover:text-primary"
        @click="handleContinuePreset(preset.prompt)"
      >
        {{ preset.label }}
      </button>
    </div>

    <div v-else-if="mode === 'knowledge'" class="space-y-1 px-1 pb-1">
      <button
        v-for="preset in knowledgePresets"
        :key="preset.key"
        :data-selection-secondary="preset.key"
        class="w-full rounded-lg px-3 py-2 text-left text-sm text-on-surface-variant transition-colors hover:bg-primary-fixed hover:text-primary"
        @click="handleKnowledgePreset(preset.promptKind)"
      >
        {{ preset.label }}
      </button>
    </div>
  </div>
</template>
