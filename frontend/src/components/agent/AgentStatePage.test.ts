import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AgentStatePage from './AgentStatePage.vue';
import { useWorkspaceStore } from '../../stores/workspace';

describe('AgentStatePage', () => {
  let pinia: ReturnType<typeof createPinia>;

  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);
  });

  it('renders the latest response, knowledge activity, memory scope, and recent decisions', () => {
    const store = useWorkspaceStore();
    store.agentState = {
      current_turn: {
        session_id: 'chat-1',
        message_id: 'msg-a',
        route: 'answer_then_suggest_drafts',
        intent: 'broad_overview',
        confidence: 0.78,
        persistence_decision: 'suggest_drafts',
        user_visible_summary: '先给概览。',
        detected_scope_ids: ['linear-algebra'],
        profile_layers_used: ['global_user', 'scope_memory:linear-algebra'],
        profile_context_summary: '识别为线性代数范围。',
        active_node_ids: [],
        candidate_drafts: [{ title: 'Vector Space', draft_type: 'definition', reason: 'Reusable.' }],
      },
      knowledge_queue: [{ item_id: 'draft-1', title: 'Vector Space', draft_type: 'definition', state: 'suggested', reason: 'Reusable.' }],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: ['linear-algebra'],
        profile_layers_used: ['global_user', 'scope_memory:linear-algebra'],
        profile_context_summary: '识别为线性代数范围。',
        has_global_user_profile: true,
        has_scope_memory: true,
      },
      context_health: { active_node_count: 0, summary_node_count: 0, pending_draft_count: 1, failed_item_count: 0, symbol_conflict_count: 0 },
      recent_decisions: [{ session_id: 'chat-1', message_id: 'msg-a', route: 'answer_then_suggest_drafts', intent: 'broad_overview', persistence_decision: 'suggest_drafts', result: '先给概览。' }],
    } as any;
    vi.spyOn(store, 'fetchAgentState').mockResolvedValue(undefined);

    const wrapper = mount(AgentStatePage, { global: { plugins: [pinia] } });

    expect(wrapper.text()).toContain('Latest response');
    expect(wrapper.text()).toContain('Answer then suggest drafts');
    expect(wrapper.text()).toContain('Knowledge activity');
    expect(wrapper.text()).toContain('Memory Scope');
    expect(wrapper.text()).toContain('linear-algebra');
    expect(wrapper.text()).toContain('Vector Space');
    expect(wrapper.text()).toContain('Recent Decisions');
  });

  it('shows profile observation and patch sections even when they are empty', () => {
    const store = useWorkspaceStore();
    store.agentState = {
      current_turn: null,
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        profile_context_summary: null,
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [],
    } as any;
    vi.spyOn(store, 'fetchAgentState').mockResolvedValue(undefined);

    const wrapper = mount(AgentStatePage, { global: { plugins: [pinia] } });

    expect(wrapper.text()).toContain('Profile Observations');
    expect(wrapper.text()).toContain('Profile Patches');
    expect(wrapper.text()).toContain('No profile observations yet.');
    expect(wrapper.text()).toContain('No profile patches yet.');
  });

  it('marks the focused recent decision when the store has a focused agent message id', () => {
    const store = useWorkspaceStore();
    (store as any).focusedAgentMessageId = 'msg-a';
    store.agentState = {
      current_turn: null,
      knowledge_queue: [],
      profile_observations: [],
      profile_patches: [],
      memory_scope: {
        detected_scope_ids: [],
        profile_layers_used: [],
        profile_context_summary: null,
        has_global_user_profile: false,
        has_scope_memory: false,
      },
      context_health: {
        active_node_count: 0,
        summary_node_count: 0,
        pending_draft_count: 0,
        failed_item_count: 0,
        symbol_conflict_count: 0,
      },
      recent_decisions: [
        {
          session_id: 'chat-1',
          message_id: 'msg-a',
          route: 'answer_then_suggest_drafts',
          intent: 'broad_overview',
          persistence_decision: 'suggest_drafts',
          result: '先给概览。',
        },
        {
          session_id: 'chat-1',
          message_id: 'msg-b',
          route: 'answer_only',
          intent: 'follow_up',
          persistence_decision: 'none',
          result: '后续补充。',
        },
      ],
    } as any;
    vi.spyOn(store, 'fetchAgentState').mockResolvedValue(undefined);

    const wrapper = mount(AgentStatePage, { global: { plugins: [pinia] } });

    const focusedDecision = wrapper.get('[data-decision-message-id="msg-a"]');
    const unfocusedDecision = wrapper.get('[data-decision-message-id="msg-b"]');

    expect(focusedDecision.attributes('data-focused')).toBe('true');
    expect(focusedDecision.text()).toContain('Focused');
    expect(unfocusedDecision.attributes('data-focused')).toBeUndefined();
  });

  it('shows the focused message plan while the agent state refreshes', () => {
    const store = useWorkspaceStore();
    (store as any).focusedAgentMessageId = 'msg-a';
    (store as any).agentStateLoading = true;
    store.currentSession = {
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [
        {
          message_id: 'msg-a',
          role: 'assistant',
          content: '先给概览。',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            orchestration_plan: {
              route: 'answer_then_suggest_drafts',
              intent: 'broad_overview',
              confidence: 0.78,
              persistence_decision: 'suggest_drafts',
              user_visible_summary: '先回答，再建议沉淀草稿。',
              detected_scope_ids: [],
              profile_layers_used: [],
              profile_context_summary: null,
              candidate_drafts: [
                { title: 'Vector Space', draft_type: 'definition', reason: 'Reusable concept.' },
              ],
            },
            state_items: [
              {
                item_id: 'draft-vector-space',
                kind: 'knowledge_draft',
                state: 'suggested',
                title: 'Vector Space',
                reason: 'Reusable concept.',
              },
            ],
          },
          created_at: '2026-04-18T00:00:00Z',
        },
      ],
    } as any;
    const fetchAgentState = vi.spyOn(store, 'fetchAgentState').mockResolvedValue(undefined);

    const wrapper = mount(AgentStatePage, { global: { plugins: [pinia] } });

    expect(wrapper.text()).toContain('Loading agent review');
    expect(wrapper.text()).toContain('Response approach');
    expect(wrapper.text()).toContain('Answer then suggest drafts');
    expect(wrapper.text()).toContain('先回答，再建议沉淀草稿。');
    expect(wrapper.text()).toContain('Vector Space');
    expect(wrapper.findAll('[data-primary-knowledge] [data-knowledge-item]')).toHaveLength(1);
    expect(wrapper.find('[data-other-knowledge]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Keep the useful parts');
    expect(fetchAgentState).not.toHaveBeenCalled();
  });

  it('compiles selected suggested drafts from the focused review', async () => {
    const store = useWorkspaceStore();
    (store as any).focusedAgentMessageId = 'msg-a';
    store.currentSession = {
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [
        {
          message_id: 'msg-a',
          role: 'assistant',
          content: '先给概览。',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            orchestration_plan: {
              route: 'ask_before_persist',
              intent: 'broad_overview',
              confidence: 0.78,
              persistence_decision: 'await_approval',
              user_visible_summary: '先回答，再建议沉淀草稿。',
              detected_scope_ids: [],
              profile_layers_used: [],
              profile_context_summary: null,
              candidate_drafts: [
                { title: 'Vector Space', draft_type: 'definition', reason: 'Reusable concept.' },
                { title: 'Kernel', draft_type: 'definition', reason: 'Reusable concept.' },
              ],
            },
            state_items: [],
          },
          created_at: '2026-04-18T00:00:00Z',
        },
      ],
    } as any;
    vi.spyOn(store, 'fetchAgentState').mockResolvedValue(undefined);
    const acceptSuggestedDrafts = vi
      .spyOn(store, 'acceptSuggestedDrafts')
      .mockResolvedValue(undefined);

    const wrapper = mount(AgentStatePage, { global: { plugins: [pinia] } });

    await wrapper.get('[data-draft-index="1"]').setValue(true);
    await wrapper.get('[data-compile-selected-drafts]').trigger('click');

    expect(acceptSuggestedDrafts).toHaveBeenCalledWith('msg-a', [1]);
  });

  it('does not offer manual draft generation for draft-first decisions', () => {
    const store = useWorkspaceStore();
    (store as any).focusedAgentMessageId = 'msg-a';
    store.currentSession = {
      session_id: 'chat-1',
      branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
      messages: [
        {
          message_id: 'msg-a',
          role: 'assistant',
          content: '正在先沉淀知识点。',
          assistant_context: {
            referenced_node_ids: [],
            symbol_conflicts: [],
            alignment_notes: [],
            orchestration_plan: {
              route: 'draft_first_then_answer',
              intent: 'definition',
              confidence: 0.86,
              persistence_decision: 'persist_first',
              user_visible_summary: '先生成定义节点，再回答。',
              detected_scope_ids: [],
              profile_layers_used: [],
              profile_context_summary: null,
              candidate_drafts: [
                { title: 'Vector Space', draft_type: 'definition', reason: 'Reusable concept.' },
              ],
            },
            state_items: [
              {
                item_id: 'draft-vector-space',
                kind: 'knowledge_draft',
                state: 'writing',
                title: 'Vector Space',
                reason: 'Reusable concept.',
              },
            ],
          },
          created_at: '2026-04-18T00:00:00Z',
        },
      ],
    } as any;
    vi.spyOn(store, 'fetchAgentState').mockResolvedValue(undefined);

    const wrapper = mount(AgentStatePage, { global: { plugins: [pinia] } });

    expect(wrapper.find('[data-draft-index="0"]').exists()).toBe(false);
    expect(wrapper.find('[data-compile-selected-drafts]').exists()).toBe(false);
    expect(wrapper.text()).toContain('Creating');
  });
});
