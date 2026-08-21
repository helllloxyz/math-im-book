import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

import ReaderPanel from './ReaderPanel.vue';
import { useWorkspaceStore } from '../../stores/workspace';

function buildNode(overrides: Record<string, unknown> = {}) {
  return {
    id: 'variation-of-action',
    title: 'Variation of the Action',
    type: 'section',
    summary: 'Stationary action produces the Euler-Lagrange equations.',
    detail: '## Derivation\n\n- Fix the endpoints\n- Integrate by parts\n\n```text\n\\delta S = 0\n```',
    source: 'chat:test',
    references: [],
    incoming_references: [],
    related_session_ids: [],
    references_display: [],
    incoming_references_display: [],
    related_discussions: [],
    status: 'ready',
    symbols: {},
    symbol_scopes: {},
    ...overrides,
  };
}

describe('ReaderPanel', () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
  });

  it('renders node detail as markdown html', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;

    const wrapper = mount(ReaderPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          NodeReferences: true,
          BookOpen: true,
          Share2: true,
          Printer: true,
          Search: true,
          Hash: true,
        },
      },
    });

    expect(wrapper.html()).toContain('<h2');
    expect(wrapper.html()).toContain('<ul');
    expect(wrapper.html()).toContain('<pre><code');
    expect(wrapper.find('.markdown-content').exists()).toBe(true);
  });

  it('marks the reader detail as a knowledge-node selection source', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode({
      id: 'node-77',
    }) as any;

    const wrapper = mount(ReaderPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          NodeReferences: true,
        },
      },
    });

    expect(wrapper.get('article').attributes('data-selection-source')).toBeUndefined();
    const source = wrapper.get('[data-selection-source="knowledge-node"]');
    expect(source.attributes('data-node-id')).toBe('node-77');
  });

  it('does not mark the article shell or chrome as selectable knowledge content', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode({
      id: 'node-88',
    }) as any;

    const wrapper = mount(ReaderPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          NodeReferences: true,
        },
      },
    });

    expect(wrapper.get('article').attributes('data-selection-source')).toBeUndefined();
    expect(wrapper.get('article').attributes('data-node-id')).toBeUndefined();
    expect(wrapper.get('h1').attributes('data-selection-source')).toBeUndefined();
    expect(wrapper.get('[data-reader-action="toggle-width"]').attributes('data-selection-source')).toBeUndefined();
  });

  it('uses a compact non-clickable type icon without extra crowded actions', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode({
      type: 'atomic',
    }) as any;

    const wrapper = mount(ReaderPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          NodeReferences: true,
        },
      },
    });

    expect(wrapper.text()).not.toContain('atomic');
    expect(wrapper.text()).not.toContain('ATOMIC');
    expect(wrapper.text()).toContain('science');
    expect(wrapper.find('[data-reader-action="node-menu"]').exists()).toBe(false);
    expect(wrapper.find('[data-reader-action="search"]').exists()).toBe(false);
  });

  it('does not render the source and status strip above the note content', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode({
      source: 'chat:auto',
      status: 'ready',
    }) as any;

    const wrapper = mount(ReaderPanel, {
      global: {
        plugins: [pinia],
        stubs: {
          NodeReferences: true,
        },
      },
    });

    expect(wrapper.text()).toContain('Variation of the Action');
    expect(wrapper.text()).not.toContain('Source:');
    expect(wrapper.text()).not.toContain('chat:auto');
    expect(wrapper.text()).not.toContain('ready');
  });

  it('replaces print and share with a preview width toggle', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;

    const wrapper = mount(ReaderPanel, {
      props: {
        isExpanded: false,
      },
      global: {
        plugins: [pinia],
        stubs: {
          NodeReferences: true,
        },
      },
    });

    expect(wrapper.find('[data-reader-action="print"]').exists()).toBe(false);
    expect(wrapper.find('[data-reader-action="share"]').exists()).toBe(false);

    const toggle = wrapper.get('[data-reader-action="toggle-width"]');
    expect(toggle.attributes('title')).toBe('Expand preview');
    expect(toggle.text()).toContain('open_in_full');

    await toggle.trigger('click');

    expect(wrapper.emitted('toggle-expanded')).toHaveLength(1);
  });

  it('shows restore affordance when preview is expanded', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;

    const wrapper = mount(ReaderPanel, {
      props: {
        isExpanded: true,
      },
      global: {
        plugins: [pinia],
        stubs: {
          NodeReferences: true,
        },
      },
    });

    const toggle = wrapper.get('[data-reader-action="toggle-width"]');
    expect(toggle.attributes('title')).toBe('Restore preview');
    expect(toggle.text()).toContain('close_fullscreen');
  });

  it('uses the full article layout without panel-only controls on a knowledge page', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;

    const wrapper = mount(ReaderPanel, {
      props: { pageMode: true },
      global: { plugins: [pinia], stubs: { NodeReferences: true } },
    });

    expect(wrapper.attributes('data-knowledge-page')).toBe('true');
    expect(wrapper.find('[data-reader-action="toggle-width"]').exists()).toBe(false);
    expect(wrapper.find('[data-reader-action="close"]').exists()).toBe(false);
    expect(wrapper.get('article').classes()).toContain('max-w-[58rem]');
  });
});
