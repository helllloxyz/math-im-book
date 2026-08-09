import { describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';

import ChatMessage from './ChatMessage.vue';

describe('ChatMessage anchors', () => {
  it('uses the light question surface for user messages', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg_user_question',
          role: 'user',
          content: '介绍下群表示论',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
          },
          created_at: '2026-04-02T09:00:00Z',
        },
      },
      global: {
        plugins: [createPinia()],
      },
    });

    expect(wrapper.classes()).toContain('user-message');
    expect(wrapper.get('.message-card').classes()).toContain('question-card');
  });

  it('marks selectable chat content with source metadata', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        sessionId: 'chat-1',
        message: {
          message_id: 'msg_selectable',
          role: 'assistant',
          content: 'A selectable explanation.',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
          Sigma: true,
        },
      },
    });

    expect(wrapper.find('article').attributes('data-selection-source')).toBeUndefined();
    const source = wrapper.get('[data-selection-source="chat-message"]');
    expect(source.attributes('data-session-id')).toBe('chat-1');
    expect(source.attributes('data-message-id')).toBe('msg_selectable');
  });

  it('does not mark the article shell as selectable chat content', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        sessionId: 'chat-1',
        message: {
          message_id: 'msg_selectable_shell',
          role: 'assistant',
          content: 'A selectable explanation.',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
          Sigma: true,
        },
      },
    });

    expect(wrapper.get('article').attributes('data-selection-source')).toBeUndefined();
    expect(wrapper.get('article').attributes('data-session-id')).toBeUndefined();
    expect(wrapper.get('article').attributes('data-message-id')).toBeUndefined();
  });

  it('uses the assistant display name and icon for assistant messages', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        assistantName: 'Gauss',
        message: {
          message_id: 'msg_assistant_named',
          role: 'assistant',
          content: 'A concise derivation.',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
          Sigma: true,
        },
      },
    });

    expect(wrapper.text()).toContain('Gauss');
    expect(wrapper.text()).not.toContain('Assistant');
    expect(wrapper.find('[data-assistant-icon]').exists()).toBe(true);
  });

  it('shows a thinking indicator for an empty assistant message while loading', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        assistantName: 'Noether',
        isLoading: true,
        message: {
          message_id: 'streaming-assistant',
          role: 'assistant',
          content: '',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
          Sigma: true,
        },
      },
    });

    expect(wrapper.text()).toContain('Working through it');
    expect(wrapper.find('[data-thinking-indicator]').exists()).toBe(true);
  });

  it('renders markdown structure in message content', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg_assistant_markdown',
          role: 'assistant',
          content: '# Heading\n\n- alpha\n- beta\n\n```ts\nconst value = 1\n```',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
        },
      },
    });

    expect(wrapper.html()).toContain('<h1');
    expect(wrapper.html()).toContain('<ul');
    expect(wrapper.html()).toContain('<pre><code');
    expect(wrapper.find('.markdown-content').exists()).toBe(true);
  });

  it('renders knowledge anchors as inline actions and emits ready anchor clicks', async () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg_assistant_1',
          role: 'assistant',
          content: 'Use the resolved node below.',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [
              {
                anchor_id: 'anchor-pending',
                label: 'Pending anchor',
                status: 'pending',
              },
              {
                anchor_id: 'anchor-ready',
                label: 'Ready anchor',
                status: 'ready',
                node_id: 'node-42',
              },
            ],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
        },
      },
    });

    const pendingAnchor = wrapper.get('[data-anchor-id="anchor-pending"]');
    const readyAnchor = wrapper.get('[data-anchor-id="anchor-ready"]');

    expect(pendingAnchor.attributes('disabled')).toBeDefined();
    expect(readyAnchor.text()).toContain('Ready anchor');

    await readyAnchor.trigger('click');

    expect(wrapper.emitted('anchor-click')?.[0]?.[0]).toMatchObject({
      anchor_id: 'anchor-ready',
      node_id: 'node-42',
      status: 'ready',
    });
  });

  it('uses visual state only for knowledge anchor status text', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg_assistant_semantics',
          role: 'assistant',
          content: 'The answer remains available.',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [
              {
                anchor_id: 'anchor-ready',
                label: 'Linear Algebra',
                status: 'ready',
                node_id: 'node-42',
              },
              {
                anchor_id: 'anchor-pending',
                label: 'Draft pending',
                status: 'pending',
              },
              {
                anchor_id: 'anchor-failed',
                label: 'Draft failed',
                status: 'failed',
              },
              {
                anchor_id: 'anchor-suggested',
                label: 'Suggested theorem',
                status: 'ready',
                kind: 'suggested',
              },
            ],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
        },
      },
    });

    expect(wrapper.get('[data-anchor-id="anchor-ready"]').text()).toContain('Linear Algebra');
    expect(wrapper.get('[data-anchor-id="anchor-pending"]').text()).toContain('Draft pending');
    expect(wrapper.get('[data-anchor-id="anchor-failed"]').text()).toContain('Draft failed');
    expect(wrapper.get('[data-anchor-id="anchor-suggested"]').text()).toContain('Suggested theorem');
    expect(wrapper.find('[data-anchor-link-icon]').exists()).toBe(false);
  });

  it('keeps assistant orchestration details concise and user-visible', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg_assistant_agent_summary',
          role: 'assistant',
          content: 'Manifolds are locally Euclidean spaces.',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
            orchestration_plan: {
              route: 'draft_first_then_answer',
              intent: 'teach_concept',
              persistence_decision: 'create_draft',
              confidence: 0.82,
              user_visible_summary: '我将先整理流形定义、例子和应用，再给出答案。',
              detected_scope_ids: [],
              profile_layers_used: [],
              profile_context_summary:
                'No specific user profile or scope memory available; treating as general knowledge request.',
              candidate_drafts: [],
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
        },
      },
    });

    const planStrip = wrapper.get('[data-agent-plan-strip]');

    expect(planStrip.text()).toContain('我将先整理流形定义、例子和应用，再给出答案。');
    expect(planStrip.text()).toContain('View details');
    expect(planStrip.text()).not.toContain('Agent:');
    expect(planStrip.text()).not.toContain('draft_first_then_answer');
    expect(planStrip.text()).not.toContain('No specific user profile');
  });

  it('uses compact spacing for assistant controls, anchors, and agent feedback', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        canRegenerate: true,
        message: {
          message_id: 'msg_assistant_compact',
          role: 'assistant',
          content: 'A compact answer.',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [
              {
                anchor_id: 'anchor-ready',
                label: 'Linear Algebra',
                status: 'ready',
                node_id: 'node-42',
              },
            ],
            orchestration_plan: {
              route: 'answer_only',
              intent: 'teach_concept',
              persistence_decision: 'none',
              confidence: 0.82,
              user_visible_summary: '直接回答当前问题。',
              detected_scope_ids: [],
              profile_layers_used: [],
              profile_context_summary: '',
              candidate_drafts: [],
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: {
        plugins: [createPinia()],
        stubs: {
          MathText: true,
          GitFork: true,
          Copy: true,
          RefreshCw: true,
          Link2: true,
        },
      },
    });

    expect(wrapper.classes()).toEqual(expect.arrayContaining(['message-row', 'assistant-message']));

    const assistantHeader = wrapper.get('[data-assistant-header]');
    expect(assistantHeader.classes()).toContain('message-identity');

    const anchors = wrapper.get('[data-anchor-list]');
    expect(anchors.classes()).toContain('knowledge-links');

    const anchorButton = wrapper.get('[data-anchor-id="anchor-ready"]');
    expect(anchorButton.find('[data-anchor-link-icon]').exists()).toBe(false);
    expect(anchorButton.text()).toContain('Linear Algebra');

    const planStrip = wrapper.get('[data-agent-plan-strip]');
    expect(planStrip.classes()).toContain('response-details');

    const actionBar = wrapper.get('[data-message-actions]');
    expect(actionBar.classes()).toContain('message-actions');

    for (const action of wrapper.findAll('[data-message-action]')) {
      expect(action.find('.material-symbols-outlined').exists()).toBe(true);
    }
  });
});
