import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import SelectionActionMenu from './SelectionActionMenu.vue'
import { useWorkspaceStore } from '../../stores/workspace'

type RectLike = Pick<DOMRect, 'x' | 'y' | 'left' | 'top' | 'right' | 'bottom' | 'width' | 'height' | 'toJSON'>

function createRect(left: number, top: number, width = 240, height = 28): RectLike {
  return {
    x: left,
    y: top,
    left,
    top,
    right: left + width,
    bottom: top + height,
    width,
    height,
    toJSON: () => ({}),
  }
}

function mountMenu() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useWorkspaceStore()

  const wrapper = mount(SelectionActionMenu, {
    attachTo: document.body,
    global: {
      plugins: [pinia],
    },
  })

  return { wrapper, store }
}

const mountedWrappers: Array<{ unmount: () => void }> = []

function createSelectionFixture(sourceHtml: string, textSelector: string) {
  const root = document.createElement('div')
  root.innerHTML = sourceHtml
  document.body.appendChild(root)
  const textNode = root.querySelector(textSelector)
  if (!textNode?.firstChild) {
    throw new Error('selection fixture text node missing')
  }
  const range = document.createRange()
  range.selectNodeContents(textNode)
  Object.defineProperty(range, 'getBoundingClientRect', {
    value: () => createRect(120, 180),
  })
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
  return { root, range }
}

function triggerSelectionShortcut(key: 'q', metaKey = false) {
  document.dispatchEvent(
    new KeyboardEvent('keydown', {
      key,
      metaKey,
      ctrlKey: !metaKey,
      bubbles: true,
      cancelable: true,
    })
  )
}

describe('SelectionActionMenu', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  afterEach(() => {
    while (mountedWrappers.length) {
      mountedWrappers.pop()?.unmount()
    }
    document.body.innerHTML = ''
    window.getSelection()?.removeAllRanges()
    vi.restoreAllMocks()
  })

  it('opens for a chat selection on Ctrl+Q and fills the draft from the continue preset', async () => {
    const { wrapper, store } = mountMenu()
    mountedWrappers.push(wrapper)
    const draftSpy = vi.spyOn(store, 'setDraftQuestion').mockImplementation((question) => {
      store.draftQuestion = question
    })

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-session-id="chat-1" data-message-id="msg-1"><span data-selected-text>How does compactness work?</span></div>',
      '[data-selected-text]'
    )

    triggerSelectionShortcut('q')
    await Promise.resolve()
    await nextTick()

    expect(wrapper.get('[data-selection-action-menu]').text()).toContain('继续问')
    expect(wrapper.get('[data-selection-action-menu]').attributes('role')).toBe('dialog')
    expect(wrapper.get('[data-selection-action-menu]').attributes('aria-label')).toBe('Selection actions')
    expect(wrapper.get('[data-selection-primary="continue"]').attributes('aria-pressed')).toBe('false')
    expect(wrapper.get('[data-selection-primary="knowledge"]').attributes('aria-pressed')).toBe('false')
    expect(wrapper.get('[data-selection-primary="continue"]').attributes('role')).toBeUndefined()
    expect(wrapper.get('[data-selection-primary="knowledge"]').attributes('role')).toBeUndefined()
    const continueButton = wrapper.get('[data-selection-primary="continue"]').element as HTMLButtonElement
    for (let attempt = 0; attempt < 5 && document.activeElement !== continueButton; attempt += 1) {
      await Promise.resolve()
      await nextTick()
    }
    expect(document.activeElement).toBe(continueButton)

    await wrapper.get('[data-selection-primary="continue"]').trigger('click')
    await nextTick()
    expect(wrapper.get('[data-selection-primary="continue"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-selection-primary="knowledge"]').attributes('aria-pressed')).toBe('false')
    expect(wrapper.get('[data-selection-secondary="continue-meaning"]').attributes('role')).toBeUndefined()
    await wrapper.get('[data-selection-secondary="continue-meaning"]').trigger('click')

    expect(draftSpy).toHaveBeenCalledWith(
      '请解释我该如何理解下面选中的内容：\n\n> How does compactness work?'
    )
    expect(store.draftQuestion).toBe(
      '请解释我该如何理解下面选中的内容：\n\n> How does compactness work?'
    )
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)
  })

  it('uses newSession before drafting when continuing from a knowledge node selection', async () => {
    const { wrapper, store } = mountMenu()
    mountedWrappers.push(wrapper)
    const calls: string[] = []
    const newSessionSpy = vi.spyOn(store, 'newSession').mockImplementation(() => {
      calls.push('newSession')
    })
    const draftSpy = vi.spyOn(store, 'setDraftQuestion').mockImplementation((question) => {
      calls.push('setDraftQuestion')
      store.draftQuestion = question
    })

    createSelectionFixture(
      '<article data-selection-source="knowledge-node" data-node-id="node-9"><span data-selected-text>Stokes theorem</span></article>',
      '[data-selected-text]'
    )

    triggerSelectionShortcut('q', true)
    await nextTick()

    await wrapper.get('[data-selection-primary="continue"]').trigger('click')
    await wrapper.get('[data-selection-secondary="continue-detail"]').trigger('click')

    expect(newSessionSpy).toHaveBeenCalledTimes(1)
    expect(draftSpy).toHaveBeenCalledTimes(1)
    expect(calls).toEqual(['newSession', 'setDraftQuestion'])
    expect(store.draftQuestion).toBe(
      '请具体说明下面选中内容的关键步骤和容易误解的点：\n\n> Stokes theorem'
    )
  })

  it('calls generateKnowledgeFromSelection for knowledge presets without drafting', async () => {
    const { wrapper, store } = mountMenu()
    mountedWrappers.push(wrapper)
    const generateSpy = vi.spyOn(store, 'generateKnowledgeFromSelection').mockResolvedValue(undefined)
    const draftSpy = vi.spyOn(store, 'setDraftQuestion')

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-session-id="chat-7" data-message-id="msg-7"><span data-selected-text>compactness</span></div>',
      '[data-selected-text]'
    )

    triggerSelectionShortcut('q')
    await nextTick()

    await wrapper.get('[data-selection-primary="knowledge"]').trigger('click')
    await wrapper.get('[data-selection-secondary="knowledge-proof"]').trigger('click')

    expect(generateSpy).toHaveBeenCalledWith(
      {
        text: 'compactness',
        sourceType: 'chat-message',
        sessionId: 'chat-7',
        messageId: 'msg-7',
      },
      'proof'
    )
    expect(draftSpy).not.toHaveBeenCalled()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)
  })

  it('does not open or act when a chat source is missing session or message metadata', async () => {
    const { wrapper, store } = mountMenu()
    mountedWrappers.push(wrapper)
    const generateSpy = vi.spyOn(store, 'generateKnowledgeFromSelection')
    const draftSpy = vi.spyOn(store, 'setDraftQuestion')
    const newSessionSpy = vi.spyOn(store, 'newSession')

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-message-id="msg-1"><span data-selected-text>Missing session</span></div>',
      '[data-selected-text]'
    )
    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-session-id="chat-1"><span data-selected-text>Missing message</span></div>',
      '[data-selected-text]'
    )
    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    expect(generateSpy).not.toHaveBeenCalled()
    expect(draftSpy).not.toHaveBeenCalled()
    expect(newSessionSpy).not.toHaveBeenCalled()
  })

  it('does not open or act when a knowledge source is missing a node id', async () => {
    const { wrapper, store } = mountMenu()
    mountedWrappers.push(wrapper)
    const generateSpy = vi.spyOn(store, 'generateKnowledgeFromSelection')
    const draftSpy = vi.spyOn(store, 'setDraftQuestion')

    createSelectionFixture(
      '<article data-selection-source="knowledge-node"><span data-selected-text>Missing node</span></article>',
      '[data-selected-text]'
    )
    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    expect(generateSpy).not.toHaveBeenCalled()
    expect(draftSpy).not.toHaveBeenCalled()
  })

  it('does not open for empty, outside, or contenteditable selections', async () => {
    const { wrapper } = mountMenu()
    mountedWrappers.push(wrapper)

    triggerSelectionShortcut('q')
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    createSelectionFixture('<div><span data-selected-text>Outside text</span></div>', '[data-selected-text]')
    triggerSelectionShortcut('q')
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    document.body.innerHTML = ''
    const editable = document.createElement('div')
    editable.contentEditable = 'true'
    editable.innerHTML = '<span data-selected-text>Editable text</span>'
    document.body.appendChild(editable)
    const textNode = editable.querySelector('[data-selected-text]')
    if (!textNode?.firstChild) throw new Error('editable text node missing')
    const range = document.createRange()
    range.selectNodeContents(textNode)
    Object.defineProperty(range, 'getBoundingClientRect', {
      value: () => createRect(40, 80),
    })
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    editable.focus()

    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)
  })

  it('does not open when selection is in unmarked title or chrome', async () => {
    const { wrapper } = mountMenu()
    mountedWrappers.push(wrapper)

    const root = document.createElement('div')
    root.innerHTML = `
      <article>
        <h1 data-title>Unmarked title</h1>
        <div data-chrome>Toolbar chrome</div>
      </article>
    `
    document.body.appendChild(root)

    const title = root.querySelector('[data-title]')
    if (!title?.firstChild) throw new Error('title text node missing')
    const titleRange = document.createRange()
    titleRange.selectNodeContents(title)
    Object.defineProperty(titleRange, 'getBoundingClientRect', {
      value: () => createRect(40, 80),
    })
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(titleRange)

    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    const chrome = root.querySelector('[data-chrome]')
    if (!chrome?.firstChild) throw new Error('chrome text node missing')
    const chromeRange = document.createRange()
    chromeRange.selectNodeContents(chrome)
    Object.defineProperty(chromeRange, 'getBoundingClientRect', {
      value: () => createRect(40, 80),
    })
    selection?.removeAllRanges()
    selection?.addRange(chromeRange)

    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)
  })

  it('closes on Escape, selection loss, and outside clicks', async () => {
    const { wrapper } = mountMenu()
    mountedWrappers.push(wrapper)

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-session-id="chat-3" data-message-id="msg-3"><span data-selected-text>bounded text</span></div>',
      '[data-selected-text]'
    )

    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(true)

    document.dispatchEvent(
      new KeyboardEvent('keydown', {
        key: 'Escape',
        bubbles: true,
        cancelable: true,
      })
    )
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(true)

    window.getSelection()?.removeAllRanges()
    document.dispatchEvent(new Event('selectionchange'))
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-session-id="chat-3" data-message-id="msg-3"><span data-selected-text>bounded text</span></div>',
      '[data-selected-text]'
    )
    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(true)

    document.body.dispatchEvent(
      new MouseEvent('pointerdown', {
        bubbles: true,
      })
    )
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)
  })

  it('closes on scroll', async () => {
    const { wrapper } = mountMenu()
    mountedWrappers.push(wrapper)

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-session-id="chat-4" data-message-id="msg-4"><span data-selected-text>scroll me away</span></div>',
      '[data-selected-text]'
    )

    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(true)

    window.dispatchEvent(new Event('scroll'))
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(false)
  })

  it('removes global listeners on unmount', async () => {
    const { wrapper, store } = mountMenu()
    mountedWrappers.push(wrapper)
    const draftSpy = vi.spyOn(store, 'setDraftQuestion')

    createSelectionFixture(
      '<div data-selection-source="chat-message" data-session-id="chat-5" data-message-id="msg-5"><span data-selected-text>cleanup</span></div>',
      '[data-selected-text]'
    )
    triggerSelectionShortcut('q')
    await nextTick()
    expect(wrapper.find('[data-selection-action-menu]').exists()).toBe(true)

    wrapper.unmount()
    mountedWrappers.pop()

    triggerSelectionShortcut('q')
    await nextTick()

    expect(draftSpy).not.toHaveBeenCalled()
    expect(document.querySelector('[data-selection-action-menu]')).toBeNull()
  })
})
