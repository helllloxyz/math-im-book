import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ChatComposer from './ChatComposer.vue'
import { useWorkspaceStore } from '../../stores/workspace'

describe('ChatComposer', () => {
  it('uses a compact two-line input by default', () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(ChatComposer, {
      global: {
        plugins: [pinia],
      },
    })

    const shell = wrapper.get('[data-chat-composer-shell]')
    const inputRow = wrapper.get('[data-chat-composer-input-row]')
    const textarea = wrapper.get('textarea')
    const controls = wrapper.get('[data-chat-composer-controls]')

    expect(shell.classes()).toContain('composer-shell')
    expect(inputRow.classes()).toContain('composer-input-row')
    expect(textarea.attributes('rows')).toBe('2')
    expect(textarea.attributes('aria-label')).toBe('Question')
    expect(controls.classes()).toContain('composer-controls')
    expect(wrapper.text()).toContain('Enter to send')
  })

  it('submits the current draft on Enter and clears it', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkspaceStore()
    store.setDraftQuestion('How does compactness work?')

    const wrapper = mount(ChatComposer, {
      global: {
        plugins: [pinia],
      },
    })

    const textarea = wrapper.get('textarea')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('How does compactness work?')

    await textarea.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('ask')?.[0]).toEqual(['How does compactness work?'])
    expect(store.draftQuestion).toBe('')
  })

  it('grows with multiline content and returns to its minimum height after sending', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(ChatComposer, {
      global: {
        plugins: [pinia],
      },
    })
    const textarea = wrapper.get('textarea')
    const input = textarea.element as HTMLTextAreaElement

    Object.defineProperty(input, 'scrollHeight', {
      configurable: true,
      get: () => (input.value ? 108 : 48),
    })

    await textarea.setValue('First line\nSecond line\nThird line')
    await nextTick()

    expect(input.style.height).toBe('108px')
    expect(input.style.overflowY).toBe('hidden')

    await textarea.trigger('keydown', { key: 'Enter' })
    await nextTick()

    expect(input.value).toBe('')
    expect(input.style.height).toBe('48px')
  })

  it('does not submit when loading or when the draft is blank', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useWorkspaceStore()
    store.setDraftQuestion('How does compactness work?')

    const wrapper = mount(ChatComposer, {
      props: {
        loading: true,
      },
      global: {
        plugins: [pinia],
      },
    })

    const textarea = wrapper.get('textarea')
    await textarea.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('ask')).toBeFalsy()
    expect(store.draftQuestion).toBe('How does compactness work?')

    await wrapper.setProps({ loading: false })
    await textarea.setValue('')
    await textarea.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('ask')).toBeFalsy()
    expect(store.draftQuestion).toBe('')
  })
})
