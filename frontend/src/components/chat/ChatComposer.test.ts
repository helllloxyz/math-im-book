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

    expect(shell.classes()).toContain('gap-2')
    expect(shell.classes()).toContain('p-3')
    expect(inputRow.classes()).toContain('gap-3')
    expect(textarea.attributes('rows')).toBe('2')
    expect(textarea.classes()).toContain('text-base')
    expect(textarea.classes()).toContain('leading-6')
    expect(controls.classes()).toContain('gap-3')
    expect(controls.classes()).toContain('pt-1')
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
