import { describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia } from 'pinia';

import { api } from '../../services/api';
import ChatMessage from './ChatMessage.vue';

describe('ChatMessage anchors', () => {
  it('shows user questions as a preview without a header by default', () => {
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
    const toggle = wrapper.get('[data-question-summary]');
    expect(toggle.attributes('aria-expanded')).toBe('false');
    expect(toggle.text()).not.toContain('Question');
    expect(toggle.text()).not.toContain('介绍下群表示论');
    expect(wrapper.get('.question-preview').isVisible()).toBe(true);
    expect(wrapper.get('.question-preview').text()).toContain('介绍下群表示论');
    expect(wrapper.find('.question-content').exists()).toBe(false);
  });

  it('expands the full question and can collapse back to the preview', async () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg_long_user_question',
          role: 'user',
          content: '第一行问题内容。第二行继续补充。第三行给出条件。第四行提出最终问题。',
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

    const toggle = wrapper.get('[data-question-summary]');
    await toggle.trigger('click');
    expect(toggle.attributes('aria-expanded')).toBe('true');
    expect(wrapper.find('.question-preview').exists()).toBe(false);
    expect(wrapper.get('.question-content').isVisible()).toBe(true);

    await toggle.trigger('click');
    expect(toggle.attributes('aria-expanded')).toBe('false');
    expect(wrapper.get('.question-preview').isVisible()).toBe(true);
    expect(wrapper.find('.question-content').exists()).toBe(false);
  });

  it('keeps the collapsed question preview selectable and associated with its message', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        sessionId: 'chat-1',
        message: {
          message_id: 'msg_user_question',
          role: 'user',
          content: '可以选中并复制的问题',
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

    const preview = wrapper.get('.question-preview');
    expect(preview.attributes('data-selection-source')).toBe('chat-message');
    expect(preview.attributes('data-session-id')).toBe('chat-1');
    expect(preview.attributes('data-message-id')).toBe('msg_user_question');
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

  it('keeps the Markdown heading outline visible while the answer body is collapsed', async () => {
    const wrapper = mount(ChatMessage, {
      props: {
        assistantName: 'Gauss',
        message: {
          message_id: 'msg_answer_collapse',
          role: 'assistant',
          content: '# Compactness\n\nA concise explanation.\n\n## Open covers\n\nMore detail.',
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
      },
    });

    const button = wrapper.get('[data-answer-collapse]');
    const answer = wrapper.get('#answer-msg_answer_collapse');
    const messageContent = answer.get('.message-content');

    expect(button.attributes('aria-expanded')).toBe('true');
    expect(button.attributes('aria-label')).toBe('Collapse answer');
    expect(button.get('.material-symbols-outlined').text()).toBe('expand_less');
    expect(answer.get('[data-answer-outline]').attributes('style')).toContain('display: none');
    expect(messageContent.attributes('style')).toBeUndefined();

    await button.trigger('click');

    expect(button.attributes('aria-expanded')).toBe('false');
    expect(button.attributes('aria-label')).toBe('Expand answer');
    expect(button.get('.material-symbols-outlined').text()).toBe('expand_more');
    expect(answer.isVisible()).toBe(true);
    expect(answer.get('[data-answer-outline]').text()).toContain('Compactness');
    expect(answer.get('[data-answer-outline]').text()).toContain('Open covers');
    expect(answer.get('[data-answer-outline]').attributes('style') || '').not.toContain('display: none');
    expect(answer.get('.message-content').attributes('style')).toContain('display: none');
    expect(answer.get('.message-content').element).toBe(messageContent.element);
    expect(answer.get('[data-message-actions]').isVisible()).toBe(false);

    await button.trigger('click');

    expect(button.attributes('aria-expanded')).toBe('true');
    expect(answer.get('[data-answer-outline]').attributes('style')).toContain('display: none');
    expect(answer.get('.message-content').attributes('style') || '').not.toContain('display: none');
    expect(answer.get('.message-content').element).toBe(messageContent.element);
    expect(answer.get('.message-content').text()).toContain('A concise explanation.');
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

    expect(wrapper.text()).toContain('Agent 正在处理');
    expect(wrapper.text()).toContain('正在启动任务');
    expect(wrapper.find('[data-thinking-indicator]').exists()).toBe(true);
    expect(wrapper.find('[data-answer-collapse]').exists()).toBe(false);
  });

  it('shows concrete Agent search and compile progress before the answer', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        isLoading: true,
        agentSteps: [
          {
            stage: 'searching',
            label: '正在检索当前 Scope 的知识索引',
            detail: '检查 12 个节点的标题与摘要',
            state: 'completed',
          },
          {
            stage: 'compiling',
            label: '正在编译可复用的知识节点',
            detail: '准备 2 个节点',
            state: 'running',
          },
        ],
        message: {
          message_id: 'streaming-assistant',
          role: 'assistant',
          content: '',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
    });

    expect(wrapper.get('[data-agent-run-steps]').text()).toContain('检索当前 Scope');
    expect(wrapper.get('[data-agent-stage="searching"]').classes()).toContain('is-completed');
    expect(wrapper.get('[data-agent-stage="compiling"]').classes()).toContain('is-running');
    expect(wrapper.text()).toContain('准备 2 个节点');
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

  it('opens ready knowledge anchors in a new tab and keeps pending anchors disabled', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        sessionId: 'chat-1',
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
    expect(readyAnchor.element.tagName).toBe('A');
    expect(readyAnchor.attributes('target')).toBe('_blank');
    expect(readyAnchor.attributes('rel')).toBe('noopener noreferrer');

    const target = new URL(readyAnchor.attributes('href')!);
    expect(target.searchParams.get('view')).toBe('knowledge');
    expect(target.searchParams.get('session')).toBe('chat-1');
    expect(target.searchParams.get('node')).toBe('node-42');
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
        sessionId: 'chat-1',
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
              strategy_mode: 'raw',
              strategy_reason: 'Answer directly without a specialized strategy.',
              knowledge_scope_label: 'General knowledge',
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

    const detailsLink = wrapper.get('[data-response-details-link]');
    const target = new URL(detailsLink.attributes('href')!);
    expect(detailsLink.attributes('target')).toBe('_blank');
    expect(detailsLink.attributes('rel')).toBe('noopener noreferrer');
    expect(target.searchParams.get('view')).toBe('details');
    expect(target.searchParams.get('session')).toBe('chat-1');
    expect(target.searchParams.get('message')).toBe('msg_assistant_agent_summary');
  });

  it('shows a knowledge gap approval card and emits approve or reject actions', async () => {
    const wrapper = mount(ChatMessage, {
      props: {
        sessionId: 'chat-1',
        message: {
          message_id: 'msg-gap',
          role: 'assistant',
          content: '先回答当前问题。',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
            orchestration_plan: {
              route: 'ask_before_persist',
              intent: 'definition',
              persistence_decision: 'await_approval',
              confidence: 0.72,
              user_visible_summary: '需要补充两个可复用知识点。',
              detected_scope_ids: [],
              profile_layers_used: [],
              candidate_drafts: [
                {
                  title: '一致收敛',
                  draft_type: 'missing_definition',
                  reason: '需要明确判断标准。',
                },
                {
                  title: '逐项积分条件',
                  draft_type: 'missing_bridge',
                  reason: '需要连接定理。',
                },
              ],
              strategy_mode: 'top-down',
              strategy_reason: '先构建知识结构。',
              knowledge_scope_label: '数学分析',
              authorization: {
                policy: 'always_ask',
                mode: 'require_approval',
                status: 'pending',
                risk_level: 'medium',
                operation: 'write_knowledge_nodes',
                reason: '计划一次写入 2 个知识节点，需要你确认范围。',
              },
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
      global: { plugins: [createPinia()] },
    });

    const card = wrapper.get('[data-knowledge-gap-card]');
    expect(card.text()).toContain('发现知识缺口，需要授权');
    expect(card.text()).toContain('一致收敛');
    expect(card.text()).toContain('逐项积分条件');
    expect(card.text()).toContain('写入：数学分析');
    expect(card.text()).toContain('Always Ask · 等待确认');

    await wrapper.get('[data-approve-knowledge]').trigger('click');
    expect(wrapper.emitted('approve-knowledge')?.[0]).toEqual(['msg-gap', [0, 1]]);

    await wrapper.get('[data-reject-knowledge]').trigger('click');
    expect(wrapper.emitted('reject-knowledge')?.[0]).toEqual(['msg-gap']);
  });

  it('removes completed authorization cards from the conversation flow', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg-auto',
          role: 'assistant',
          content: '已补充知识并回答。',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
            orchestration_plan: {
              route: 'draft_first_then_answer',
              intent: 'definition',
              persistence_decision: 'persist_first',
              confidence: 0.4,
              user_visible_summary: '补充知识。',
              detected_scope_ids: [],
              profile_layers_used: [],
              candidate_drafts: [
                { title: '一致收敛', draft_type: 'definition', reason: '需要定义。' },
              ],
              strategy_mode: 'top-down',
              strategy_reason: '先编译知识。',
              knowledge_scope_label: '数学分析',
              authorization: {
                policy: 'full_auto',
                mode: 'auto_execute',
                status: 'auto_approved',
                risk_level: 'low',
                operation: 'write_knowledge_nodes',
                reason: '当前对话使用完全免审批模式，知识补充将自动执行。',
              },
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
    });

    expect(wrapper.find('[data-knowledge-gap-card]').exists()).toBe(false);
    expect(wrapper.find('[data-approve-knowledge]').exists()).toBe(false);
    expect(wrapper.find('[data-reject-knowledge]').exists()).toBe(false);
  });

  it('hides a user-approved authorization card while knowledge generation continues', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg-approved',
          role: 'assistant',
          content: '知识点准备完成后开始回答。',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [
              { anchor_id: 'uniform-convergence', label: '一致收敛', status: 'pending' },
            ],
            orchestration_plan: {
              route: 'ask_before_persist',
              intent: 'definition',
              persistence_decision: 'persist_first',
              confidence: 0.72,
              user_visible_summary: '需要补充知识点。',
              detected_scope_ids: [],
              profile_layers_used: [],
              candidate_drafts: [
                { title: '一致收敛', draft_type: 'definition', reason: '需要定义。' },
              ],
              strategy_mode: 'top-down',
              strategy_reason: '先编译知识。',
              knowledge_scope_label: '数学分析',
              authorization: {
                policy: 'always_ask',
                mode: 'require_approval',
                status: 'approved',
                risk_level: 'medium',
                operation: 'write_knowledge_nodes',
                reason: '用户已允许。',
              },
            },
          },
          created_at: '2026-04-02T09:00:01Z',
        },
      },
    });

    expect(wrapper.find('[data-knowledge-gap-card]').exists()).toBe(false);
    expect(wrapper.find('[data-thinking-indicator]').exists()).toBe(true);
  });

  it('renders referenced knowledge at its citation and loads full content on expansion', async () => {
    const getNode = vi.spyOn(api, 'getNode').mockResolvedValue({
      id: 'uniform-convergence',
      title: '一致收敛',
      type: 'definition',
      summary: '在整个定义域上统一控制函数列与极限函数的误差。',
      detail: '## 定义\n\n若误差上确界趋于零，则函数列一致收敛。',
      source: 'agent',
      references: [],
      incoming_references: [],
      related_session_ids: [],
      references_display: [],
      incoming_references_display: [],
      related_discussions: [],
      status: 'ready',
      symbols: {},
      revision: 1,
    });
    const wrapper = mount(ChatMessage, {
      props: {
        message: {
          message_id: 'msg_with_knowledge',
          role: 'assistant',
          content: '一致收敛解决了逐点收敛无法统一控制误差的问题。[K1]\n\n下面继续说明应用。',
          assistant_context: {
            referenced_node_ids: ['uniform-convergence'],
            symbol_conflicts: [],
            alignment_notes: [],
            anchors: [],
          },
          created_at: '2026-04-02T09:00:01Z',
        },
        knowledgeNodes: [
          {
            id: 'uniform-convergence',
            title: '一致收敛',
            type: 'definition',
            summary: '在整个定义域上统一控制函数列与极限函数的误差。',
            status: 'ready',
          },
        ],
        sessionId: 'chat-1',
      },
    });

    const citation = wrapper.get('[data-citation-node-id="uniform-convergence"]');
    expect(citation.text()).toContain('一致收敛');
    expect(citation.text()).toContain('统一控制');
    expect(citation.element.tagName).toBe('DETAILS');
    expect(citation.attributes('open')).toBeUndefined();
    expect(getNode).not.toHaveBeenCalled();

    const markdownBlocks = wrapper.findAll('.message-content > .markdown-content');
    expect(markdownBlocks).toHaveLength(2);
    expect(markdownBlocks[0].element.nextElementSibling?.contains(citation.element)).toBe(true);

    (citation.element as HTMLDetailsElement).open = true;
    await citation.trigger('toggle');
    await flushPromises();

    expect(getNode).toHaveBeenCalledWith('uniform-convergence');
    expect(citation.get('[data-citation-detail]').text()).toContain('误差上确界趋于零');
    const link = citation.get('a');
    expect(link.attributes('target')).toBe('_blank');
    expect(link.attributes('rel')).toBe('noopener noreferrer');
    const target = new URL(link.attributes('href')!);
    expect(target.searchParams.get('view')).toBe('knowledge');
    expect(target.searchParams.get('session')).toBe('chat-1');
    expect(target.searchParams.get('node')).toBe('uniform-convergence');

    getNode.mockRestore();
  });

  it('uses compact spacing for assistant controls, anchors, and agent feedback', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        canRegenerate: true,
        sessionId: 'chat-1',
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
              strategy_mode: 'raw',
              strategy_reason: 'Answer directly without a specialized strategy.',
              knowledge_scope_label: 'General knowledge',
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

    const forkLink = wrapper.get('[data-fork-link]');
    const forkTarget = new URL(forkLink.attributes('href')!);
    expect(forkLink.element.tagName).toBe('A');
    expect(forkLink.attributes('target')).toBe('_blank');
    expect(forkLink.attributes('rel')).toBe('noopener noreferrer');
    expect(forkTarget.searchParams.get('view')).toBe('fork');
    expect(forkTarget.searchParams.get('session')).toBe('chat-1');
    expect(forkTarget.searchParams.get('message')).toBe('msg_assistant_compact');

    for (const action of wrapper.findAll('[data-message-action]')) {
      expect(action.find('.material-symbols-outlined').exists()).toBe(true);
    }
  });
});
