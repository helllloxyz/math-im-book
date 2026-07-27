import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import NodeReferences from './NodeReferences.vue';
import { useWorkspaceStore } from '../../stores/workspace';

function buildNode(overrides: Record<string, unknown> = {}) {
  return {
    id: 'linear-map',
    title: 'Linear Map',
    type: 'atomic',
    summary: 'A linear map preserves vector operations.',
    detail: 'Detail',
    source: 'chat:1',
    references: [],
    incoming_references: [],
    related_session_ids: [],
    references_display: [
      {
        node_id: 'vector-space',
        title: 'Vector Space',
        summary: 'Defines the ambient space.',
        reason: 'Needed for the domain and codomain.',
        type: 'atomic',
        status: 'ready',
      },
      {
        node_id: 'basis',
        title: 'Basis',
        summary: 'Provides coordinate descriptions.',
        reason: 'Useful for matrix representations.',
        type: 'atomic',
        status: 'ready',
      },
      {
        node_id: 'kernel',
        title: 'Kernel',
        summary: 'Tracks vectors sent to zero.',
        reason: 'Supports rank-nullity arguments.',
        type: 'atomic',
        status: 'ready',
      },
      {
        node_id: 'image',
        title: 'Image',
        summary: 'Captures the output subspace.',
        reason: 'Completes the transformation picture.',
        type: 'atomic',
        status: 'ready',
      },
    ],
    incoming_references_display: [
      {
        node_id: 'linear-operator',
        title: 'Linear Operator',
        summary: 'Specializes linear maps to one space.',
        reason: 'Uses linear maps as its base notion.',
        type: 'atomic',
        status: 'ready',
      },
    ],
    related_discussions: [
      {
        session_id: 'chat-1',
        title: 'Linear algebra warmup',
        preview: 'Why is scalar multiplication required?',
        focus_question: 'What makes a map linear?',
        message_count: 4,
      },
      {
        session_id: 'chat-2',
        title: null,
        preview: null,
        focus_question: 'How should linearity be stated?',
        message_count: 2,
      },
      {
        session_id: 'chat-3',
        title: null,
        preview: 'Coordinate proof sketch',
        focus_question: null,
        message_count: 7,
      },
      {
        session_id: 'chat-4',
        title: null,
        preview: null,
        focus_question: null,
        message_count: 5,
      },
    ],
    status: 'ready',
    symbols: {},
    symbol_scopes: {},
    ...overrides,
  };
}

describe('NodeReferences', () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
  });

  it('renders a collapsed related concepts section by default', () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;

    const wrapper = mount(NodeReferences, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.text()).toContain('Related concepts');
    expect(wrapper.text()).toContain('5 concepts');
    expect(wrapper.findAll('[data-reference-card]').length).toBe(0);
    expect(wrapper.text()).not.toContain('References & Context');
    expect(wrapper.text()).not.toContain('Related Discussions');
  });

  it('keeps the related concepts section visible when no concepts exist yet', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode({
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
    }) as any;

    const wrapper = mount(NodeReferences, {
      global: {
        plugins: [pinia],
      },
    });

    expect(wrapper.text()).toContain('Related concepts');
    expect(wrapper.text()).toContain('0 concepts');
    expect(wrapper.findAll('[data-reference-card]')).toHaveLength(0);

    await wrapper.get('[data-related-concepts-toggle]').trigger('click');

    expect(wrapper.text()).toContain('No related concepts yet.');
  });

  it('expands related concepts without showing discussion history', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;

    const wrapper = mount(NodeReferences, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-related-concepts-toggle]').trigger('click');

    const card = wrapper.get('[data-reference-card="dependency:vector-space"]');
    expect(card.text()).toContain('Vector Space');
    expect(card.text()).toContain('Defines the ambient space.');
    expect(card.text()).not.toContain('vector-space');
    expect(card.text()).toContain('Depends on');

    const incomingCard = wrapper.get('[data-reference-card="referenced-by:linear-operator"]');
    expect(incomingCard.text()).toContain('Linear Operator');
    expect(incomingCard.text()).toContain('Specializes linear maps to one space.');
    expect(incomingCard.text()).toContain('Referenced by');
    expect(wrapper.text()).not.toContain('Linear algebra warmup');
    expect(wrapper.text()).not.toContain('Why is scalar multiplication required?');
  });

  it('calls selectNode when a node card is clicked', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;
    const selectNodeSpy = vi.spyOn(store, 'selectNode').mockResolvedValue(undefined);

    const wrapper = mount(NodeReferences, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-related-concepts-toggle]').trigger('click');
    await wrapper.get('[data-reference-card="dependency:vector-space"]').trigger('click');

    expect(selectNodeSpy).toHaveBeenCalledWith('vector-space');
  });

  it('resets to collapsed when the selected node changes', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.currentNode = buildNode() as any;

    const wrapper = mount(NodeReferences, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('[data-related-concepts-toggle]').trigger('click');
    expect(wrapper.findAll('[data-reference-card]')).toHaveLength(5);

    store.currentNode = buildNode({
      title: 'Affine Map',
    }) as any;
    await wrapper.vm.$nextTick();

    expect(wrapper.findAll('[data-reference-card]')).toHaveLength(0);
  });
});
