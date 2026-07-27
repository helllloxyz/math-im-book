# Agent Orchestration And State Panel Design

## 1. Purpose

This document expands the self-evolving `USER.md` design into an implementation-oriented product design.

It answers three questions:

1. When and how should `USER.md` update?
2. How should the agent dynamically choose an orchestration path without becoming an opaque black box?
3. How should the UI expose this new workflow without overloading the Markdown Reader?

The key UI decision is:

```text
The Reader remains a knowledge-node reading surface.
Agent state gets its own page or panel.
```

The Reader should show stable Markdown knowledge. It should not become a mixed dashboard of jobs, drafts, profile observations, and planner internals. A separate state page keeps the product understandable:

- Chat is where the user works.
- Reader is where the user reads durable knowledge.
- Agent State is where the user sees what the system is planning, saving, updating, or unsure about.

## 2. Conceptual Model

The system has four durable surfaces and one transient planning layer.

### 2.1 Chat

Purpose:

- Natural interaction.
- Questions and answers.
- Follow-up exploration.
- Forking from answers or references.

Chat should not show every internal detail, but it should show the user enough to trust the agent's current move.

### 2.2 Reader

Purpose:

- Render one selected knowledge node as Markdown.
- Show node-level reading navigation.
- Keep the reading experience clean.

Reader contents:

- Node title.
- Node summary.
- Node detail Markdown.
- References.
- Incoming references.
- Related discussions.

Reader should not show:

- Planner JSON.
- Profile update candidates.
- Knowledge job queues.
- Draft review lists unrelated to the selected node.

### 2.3 Agent State

Purpose:

- Explain the current agent workflow.
- Show pending drafts and knowledge jobs.
- Show profile observations and proposed `USER.md` updates.
- Show why something was or was not persisted.
- Give the user a place to approve, reject, retry, or defer system actions.

This is the new page. A compact right-panel preview can be added later, but the primary product surface is a dedicated Agent State page.

### 2.4 USER.md

Purpose:

- Long-term user profile.
- Learning preferences.
- Background assumptions.
- Persistence policy.
- Orchestration defaults.

It is updated by the system, but only through a controlled lifecycle.

### 2.5 Orchestration Plan

Purpose:

- Transient plan created for a user turn.
- It decides the route before the final answer or persistence action.
- It produces both a machine-readable plan and a user-visible summary.

It should be persisted with the session turn for auditability, but it is not a knowledge node.

## 3. USER.md Update Lifecycle

`USER.md` should self-evolve, but direct writes must be conservative. The system should distinguish evidence collection from profile mutation.

### 3.1 Update Artifacts

There are three profile-related artifacts:

1. `ProfileObservation`
2. `ProfilePatchProposal`
3. `USER.md`

They form a pipeline:

```text
conversation evidence
-> ProfileObservation
-> ProfilePatchProposal
-> USER.md update
```

### 3.2 ProfileObservation

A `ProfileObservation` is a candidate learning about the user.

It is not yet a durable preference.

Fields:

```json
{
  "observation_id": "obs_20260418_001",
  "created_at": "2026-04-18T12:00:00Z",
  "source_type": "explicit_instruction | repeated_behavior | correction | regeneration | manual_edit | compact_review",
  "source_session_id": "chat-abc",
  "source_message_ids": ["msg-1", "msg-4"],
  "category": "background | learning_style | answer_depth | persistence_policy | orchestration | language | notation",
  "claim": "User prefers overall design analysis before implementation for major product changes.",
  "evidence_count": 3,
  "confidence": "low | medium | high",
  "sensitivity": "low | medium | high",
  "status": "active | dismissed | promoted",
  "suggested_patch": "Add to Learning Style: For major changes, first discuss product goal and architecture before implementation."
}
```

Observation rules:

- One explicit user instruction can create a high-confidence observation.
- Repeated behavior should require multiple turns or sessions.
- Knowledge background observations are sensitive and should start at low or medium confidence unless explicitly stated by the user.
- The system must not infer sensitive personal information.
- A single confused question must not downgrade the user's assumed background.

### 3.3 ProfilePatchProposal

A `ProfilePatchProposal` is a concrete proposed edit to `USER.md`.

Fields:

```json
{
  "proposal_id": "patch_20260418_001",
  "created_at": "2026-04-18T12:10:00Z",
  "status": "pending | approved | rejected | applied | superseded",
  "target_section": "Learning Style",
  "operation": "append | replace | remove",
  "current_text": "- Prefer top-down explanations for new topics.",
  "proposed_text": "- For major product or architecture changes, first clarify the overall goal and design before implementation.",
  "rationale": "The user repeatedly asked to step back from implementation and think through the system design.",
  "evidence_observation_ids": ["obs_20260418_001"],
  "risk_level": "low | medium | high"
}
```

Patch rules:

- Low-risk patches can be auto-applied only after the product is stable.
- Medium-risk patches should be shown in Agent State for approval.
- High-risk patches require explicit approval.
- Background assumptions are usually medium or high risk.
- Language and formatting preferences are usually low risk.

### 3.4 Update Timing

`USER.md` can update at four moments.

#### 3.4.1 Immediate Explicit Preference

Triggered by direct user instruction:

```text
以后都先给整体设计，不要直接写代码。
```

Behavior:

- Create a high-confidence observation.
- Create a patch proposal immediately.
- If the preference is low-risk and the user wording is unambiguous, apply it or show a one-click confirmation.

#### 3.4.2 End Of Turn Observation

Triggered after each completed assistant turn.

Behavior:

- The system may create observations.
- It should not update `USER.md` directly.
- Observations appear in Agent State as "learned candidates".

#### 3.4.3 Compact/Profile Review

Triggered by `/compact`, end-of-session review, or explicit "整理一下我的偏好".

Behavior:

- Aggregate observations.
- Merge duplicates.
- Discard weak or contradicted observations.
- Generate patch proposals.
- Ask the user to approve or reject meaningful changes.

This should be the main profile-evolution moment.

#### 3.4.4 Manual Profile Edit

Triggered when the user directly edits `USER.md` or uses a profile settings page.

Behavior:

- Treat manual edits as authoritative.
- The system should adapt observations and future proposals to avoid fighting the user's written profile.

### 3.5 Update Modes

The product should support three modes:

```text
observe
Only collect observations. Never propose patches automatically.

suggest
Collect observations and propose patches. Apply only after approval.

auto_low_risk
Auto-apply low-risk patches. Ask for medium/high-risk changes.
```

Recommended default:

```text
suggest
```

Reason:

- It demonstrates self-evolution.
- It avoids silent drift.
- It lets the user correct bad inferences early.

### 3.6 USER.md Change History

Every applied update should leave an audit trail.

Recommended storage:

```text
data/config/user_profile/USER.md
data/config/user_profile/observations.jsonl
data/config/user_profile/patches.jsonl
data/config/user_profile/history.jsonl
```

History record:

```json
{
  "applied_at": "2026-04-18T12:30:00Z",
  "proposal_id": "patch_20260418_001",
  "operation": "append",
  "target_section": "Learning Style",
  "applied_text": "- For major product or architecture changes, first clarify the overall goal and design before implementation.",
  "approved_by": "user | auto_low_risk",
  "source_session_id": "chat-abc"
}
```

## 4. Dynamic Orchestration Design

The agent needs flexibility, but flexibility should not mean arbitrary behavior. Each turn should produce an `OrchestrationPlan` with explicit inputs, decisions, confidence, and outputs.

### 4.1 Planner Inputs

The planner should receive:

- User question.
- Current session branch context.
- Active knowledge nodes.
- Summary knowledge nodes.
- Current symbols.
- `USER.md` profile summary.
- Current project/book context.
- Recent conversation summary.
- Available orchestration routes.
- Persistence boundary rules.

### 4.2 OrchestrationPlan Contract

Proposed schema:

```json
{
  "plan_id": "plan_20260418_001",
  "created_at": "2026-04-18T12:00:00Z",
  "question": "线性代数",
  "intent": "broad_overview",
  "scope": "broad | focused | narrow | ambiguous",
  "user_background_assumption": {
    "level": "beginner | intermediate | advanced | unknown",
    "basis": "USER.md says preferred prerequisite level is undergraduate math.",
    "confidence": "low | medium | high"
  },
  "knowledge_assessment": {
    "status": "enough | partially_enough | missing_key_node | missing_prerequisite | none_available | uncertain",
    "active_node_ids": [],
    "summary_node_ids": [],
    "missing_topics": ["向量空间", "线性映射", "矩阵表示"]
  },
  "persistence_assessment": {
    "decision": "do_not_persist | suggest_drafts | persist_first | ask_user | defer_to_compact",
    "reason": "Broad first-pass overview should not become a formal node before subnodes exist.",
    "candidate_drafts": [
      {
        "title": "向量空间",
        "draft_type": "definition",
        "reason": "Foundational reusable concept."
      }
    ]
  },
  "route": "answer_then_suggest_drafts",
  "confidence": 0.78,
  "risk_flags": [],
  "user_visible_summary": "这是宽泛入口问题。我会先给一个中等长度概览，并建议几个可整理的知识点。",
  "internal_notes": "Do not create a formal overview node yet."
}
```

### 4.3 Intent Types

Initial intent taxonomy:

- `broad_overview`: user asks for an entry point or topic overview.
- `definition`: user asks what something means.
- `proof`: user asks why a result is true.
- `example`: user asks for an example or counterexample.
- `calculation`: user asks for computation or derivation.
- `connection`: user asks how concepts relate.
- `organization`: user asks to structure notes or a chapter.
- `debug_understanding`: user expresses confusion or asks what is wrong.
- `meta_design`: user asks about product/system design.
- `profile_update`: user states a preference or background fact.
- `compact`: user asks to summarize, organize, or clean up.

### 4.4 Route Types

#### 4.4.1 answer_only

Use when:

- The question is temporary or conversational.
- Persistence value is low.
- The user asks for high-level orientation but there is not enough structure to create a stable node.

Outputs:

- Chat answer.
- No draft.
- Optional profile observation.

#### 4.4.2 reuse_answer

Use when:

- Existing knowledge nodes support the answer.
- The planner can name the supporting nodes.

Outputs:

- Chat answer.
- Ready source references.
- No new persistence.

#### 4.4.3 answer_then_suggest_drafts

Use when:

- The question is broad or exploratory.
- The answer may reveal useful future nodes.
- Immediate persistence would create weak overview content.

Outputs:

- Chat answer.
- Suggested drafts.
- User actions: generate, dismiss, defer to compact.

#### 4.4.4 draft_first_then_answer

Use when:

- The answer depends on stable definitions, theorem statements, notation, or proof skeletons.
- The content is clearly reusable.
- The boundary is clear enough to write a knowledge node.

Outputs:

- Knowledge node creation or verification.
- Chat answer citing the node.
- Ready source references.

#### 4.4.5 ask_before_persist

Use when:

- The agent is uncertain whether a candidate should be durable.
- The user may prefer lightweight chat.
- The content is personal, speculative, or too broad.

Outputs:

- Chat answer or short clarification.
- User prompt to approve persistence.

#### 4.4.6 clarify_first

Use when:

- The question is too ambiguous to answer well.
- Persistence would be risky before scope is known.

Outputs:

- One concise clarification question.
- No knowledge persistence.

#### 4.4.7 compact_then_answer

Use when:

- Current context is cluttered.
- Multiple pending drafts overlap.
- Symbol conflicts or duplicate nodes block good answering.

Outputs:

- Compact proposal.
- Optional answer after compact succeeds.

### 4.5 Route Selection Rules

The planner should combine deterministic guards with LLM judgment.

Deterministic guards:

- If user explicitly asks not to save, route cannot persist.
- If question starts with `/compact`, use `compact_then_answer`.
- If no provider is configured, avoid routes that require provider-backed compilation.
- If confidence is below a threshold, use `ask_before_persist` or `clarify_first`.
- If candidate node title is empty or boundary unclear, do not create a formal knowledge node.

LLM judgment:

- Intent classification.
- Missing knowledge topics.
- Whether content is reusable.
- User level assumptions.
- Candidate draft titles and reasons.

Recommended confidence thresholds:

```text
>= 0.75: execute chosen route.
0.50 - 0.74: execute answer route, but ask before persistence.
< 0.50: clarify first or answer without persistence.
```

### 4.6 Two-Stage Planning

For better reliability, split planning into two stages.

Stage 1: classify and route.

```text
question + profile + knowledge summaries -> OrchestrationPlan
```

Stage 2: execute route.

```text
OrchestrationPlan -> answer / draft / knowledge job / profile observation
```

Benefits:

- Easier to debug.
- Easier to show the user what happened.
- Easier to test with fixtures.
- Avoids mixing answer generation with persistence decisions.

### 4.7 Plan Persistence

Each assistant turn should store the simplified plan in `assistant_context`.

Recommended minimal persisted shape:

```json
{
  "orchestration_plan": {
    "route": "answer_then_suggest_drafts",
    "intent": "broad_overview",
    "persistence_decision": "suggest_drafts",
    "confidence": 0.78,
    "user_visible_summary": "先给概览，并建议可整理的知识点。",
    "candidate_drafts": []
  }
}
```

Store full debug plans separately if they are too verbose for session messages.

## 5. Agent State Page

### 5.1 Why A Separate Page

The previous three-column model had:

- Left: navigation.
- Middle: chat.
- Right: Markdown reader and references.

The new self-evolving agent needs a place for:

- Current orchestration plan.
- Suggested drafts.
- Knowledge job queue.
- Failed persistence attempts.
- Profile observations.
- `USER.md` patch proposals.
- Compact proposals.

Putting all of this in the Reader would damage the reading experience. The Reader should stay focused on durable knowledge content.

### 5.2 Navigation Placement

Recommended top-level workspace modes:

```text
Chat
Reader
Agent State
Settings
```

The first implementation should add a dedicated `Agent State` workspace page.

Recommended navigation:

- Top-level navigation or route includes `Agent State`.
- Chat cards can deep-link into Agent State focused on a turn.
- Knowledge queue items can deep-link into Reader when a node becomes ready.
- Reader can deep-link back to Agent State for generation history or review state.

The current three-column workspace can keep Reader focused on Markdown:

```text
Left: navigation
Middle: chat or selected workspace page
Right: Reader for Markdown knowledge nodes
```

Reason to use a separate page first:

- Agent State will contain review-heavy workflows.
- Profile patches and knowledge queues need more horizontal space than a right tab.
- The Reader should remain a stable reading surface, not a dashboard.
- A dedicated page makes future implementation easier to test and route.

Optional later enhancement:

```text
Add a compact Agent State preview in the right panel for quick current-turn status.
Keep the full Agent State page as the review and management surface.
```

### 5.3 Agent State Information Architecture

Agent State should have five sections.

#### 5.3.1 Current Turn

Shows what the agent is doing now.

Fields:

- Route.
- Intent.
- Confidence.
- User-visible reason.
- Active sources.
- Suggested drafts.
- Persistence decision.

Example:

```text
Current Turn
Route: answer_then_suggest_drafts
Intent: broad overview
Decision: answer now, suggest knowledge nodes
Reason: This is a broad entry question. A formal overview node should wait until subnodes exist.
```

Actions:

- Generate suggested drafts.
- Dismiss suggestions.
- Defer to compact.
- Show full plan.

#### 5.3.2 Knowledge Queue

Shows persistence work.

States:

- `suggested`: candidate draft, not approved.
- `approved`: user or policy approved creation.
- `writing`: provider job running.
- `ready`: node created.
- `failed`: job failed.
- `needs_review`: node exists but may need user review.
- `dismissed`: user rejected candidate.

Item fields:

```json
{
  "item_id": "draft_001",
  "title": "向量空间",
  "type": "definition",
  "state": "suggested",
  "source_session_id": "chat-abc",
  "source_message_id": "msg-123",
  "reason": "Foundational reusable concept for the current question.",
  "target_parent_id": "linear-algebra",
  "node_id": null,
  "error_message": null
}
```

Actions:

- Generate.
- Generate all.
- Edit title.
- Choose parent.
- Dismiss.
- Retry failed job.
- Open ready node in Reader.

#### 5.3.3 Profile Learning

Shows candidate updates to `USER.md`.

Subsections:

- New observations.
- Patch proposals.
- Applied history.

Observation example:

```text
Observation
The user prefers product-level design before implementation for major changes.
Evidence: 3 turns
Confidence: medium
Action: propose USER.md update
```

Patch proposal example:

```diff
## Learning Style
+ For major product or architecture changes, first clarify the overall goal and design before implementation.
```

Actions:

- Apply.
- Edit and apply.
- Reject.
- Snooze.
- Show evidence.

#### 5.3.4 Context Health

Shows whether the current branch is becoming hard to use.

Signals:

- Active nodes count.
- Summary nodes count.
- Pending draft count.
- Symbol conflicts.
- Duplicate/overlapping draft candidates.
- Old unresolved failed jobs.
- Context size warning.

Actions:

- Run compact.
- Resolve symbol conflict.
- Merge duplicate drafts.
- Archive stale suggestions.

#### 5.3.5 Recent Agent Decisions

Audit trail of recent turns.

Fields:

- Time.
- User question summary.
- Route.
- Persistence decision.
- Result.

Example:

```text
12:03 线性代数
Route: answer_then_suggest_drafts
Result: answered, suggested 3 drafts

12:09 向量空间的基
Route: draft_first_then_answer
Result: created node "Basis of a Vector Space", answered with reference
```

### 5.4 Chat Card Integration

The chat card should show only the summary, not the whole state.

Under assistant answer:

```text
Agent: answered first, suggested 3 knowledge nodes.
[Review] [Generate all] [Dismiss]
```

For source reuse:

```text
Agent: answered using 2 knowledge nodes.
[Vector Space] [Linear Map]
```

For failed persistence:

```text
Agent: answer is available, but saving "Vector Space" failed.
[Retry] [Details]
```

Clicking `Review` opens Agent State focused on that turn.

### 5.5 Reader Integration

Reader should remain stable and simple.

Reader can show small badges when opened from Agent State:

```text
Status: ready | needs review | generated from draft | referenced by current answer
```

But all workflows stay in Agent State.

Reader actions:

- Open source chat.
- Fork from node.
- Mark needs review.
- Approve node.
- Edit node later, if editing is supported.

Reader should not include:

- USER.md patch approval.
- Full knowledge queue.
- Job logs.
- Planner details.

## 6. Backend Data Model Sketch

### 6.1 SessionAssistantContext Additions

Add optional fields:

```json
{
  "orchestration_plan": {
    "route": "answer_then_suggest_drafts",
    "intent": "broad_overview",
    "persistence_decision": "suggest_drafts",
    "confidence": 0.78,
    "user_visible_summary": "先给概览，并建议可整理的知识点。"
  },
  "state_items": [
    {
      "item_id": "draft_001",
      "kind": "knowledge_draft",
      "state": "suggested",
      "title": "向量空间"
    }
  ]
}
```

Keep this lightweight. Full state should live in dedicated stores.

### 6.2 New Stores

Recommended file-backed stores:

```text
data/agent_state/turn_plans/<session_id>.jsonl
data/agent_state/knowledge_queue.jsonl
data/config/user_profile/observations.jsonl
data/config/user_profile/patches.jsonl
data/config/user_profile/history.jsonl
data/config/user_profile/USER.md
```

The first implementation may simplify paths, but the model should keep these responsibilities separate.

### 6.3 API Surface

Suggested APIs:

```text
GET /api/agent-state
GET /api/agent-state/sessions/{session_id}
POST /api/agent-state/knowledge-items/{item_id}/approve
POST /api/agent-state/knowledge-items/{item_id}/dismiss
POST /api/agent-state/knowledge-items/{item_id}/retry
POST /api/user-profile/patches/{proposal_id}/apply
POST /api/user-profile/patches/{proposal_id}/reject
GET /api/user-profile
GET /api/user-profile/history
```

Minimal first version can use fewer endpoints:

```text
GET /api/agent-state
POST /api/agent-state/actions
GET /api/user-profile
POST /api/user-profile/actions
```

Prefer explicit endpoints once behavior stabilizes.

## 7. Frontend Data Model Sketch

### 7.1 AgentState

```ts
interface AgentState {
  current_turn?: AgentTurnState;
  knowledge_queue: KnowledgeQueueItem[];
  profile_observations: ProfileObservation[];
  profile_patches: ProfilePatchProposal[];
  context_health: ContextHealth;
  recent_decisions: AgentDecisionSummary[];
}
```

### 7.2 AgentTurnState

```ts
interface AgentTurnState {
  session_id: string;
  message_id?: string;
  route: OrchestrationRoute;
  intent: AgentIntent;
  confidence: number;
  persistence_decision: PersistenceDecision;
  user_visible_summary: string;
  active_node_ids: string[];
  candidate_drafts: KnowledgeDraftCandidate[];
}
```

### 7.3 KnowledgeQueueItem

```ts
type KnowledgeQueueState =
  | 'suggested'
  | 'approved'
  | 'writing'
  | 'ready'
  | 'failed'
  | 'needs_review'
  | 'dismissed';

interface KnowledgeQueueItem {
  item_id: string;
  title: string;
  draft_type: string;
  state: KnowledgeQueueState;
  reason: string;
  source_session_id?: string;
  source_message_id?: string;
  target_parent_id?: string;
  node_id?: string;
  error_message?: string;
}
```

### 7.4 ProfilePatchProposal

```ts
interface ProfilePatchProposal {
  proposal_id: string;
  target_section: string;
  operation: 'append' | 'replace' | 'remove';
  current_text?: string;
  proposed_text: string;
  rationale: string;
  risk_level: 'low' | 'medium' | 'high';
  status: 'pending' | 'approved' | 'rejected' | 'applied' | 'superseded';
}
```

## 8. Implementation Sequence

### 8.1 Slice 1: Transparent Planning

Goal:

- Every turn produces and stores a lightweight orchestration plan.
- Chat cards show the plan summary.

Tasks:

- Add `OrchestrationPlan` domain model.
- Extend planner prompt and parser.
- Add fallback deterministic route selection.
- Store plan summary in assistant context.
- Render chat card plan strip.

No profile updates yet.

### 8.2 Slice 2: Knowledge Queue

Goal:

- Suggested drafts and writing jobs become visible state items.

Tasks:

- Add queue item model.
- Convert current anchors/pending jobs into queue items.
- Add states: suggested, writing, ready, failed.
- Add retry/dismiss actions.
- Add Agent State compact tab with Knowledge Queue.

### 8.3 Slice 3: Agent State Page

Goal:

- Build the dedicated Agent State page for Current Turn, Knowledge Queue, Context Health, and Recent Decisions.

Tasks:

- Add an Agent State route/page.
- Add `AgentStatePage.vue`.
- Add store state and API client methods.
- Connect Review buttons from chat cards to focused Agent State view.
- Keep Reader as the Markdown-focused knowledge node surface.

### 8.4 Slice 4: Profile Observations

Goal:

- Collect candidate profile observations without mutating `USER.md`.

Tasks:

- Add `USER.md` loader.
- Add observation store.
- Generate observations after turns or during compact.
- Show observations in Agent State.
- Allow dismissing observations.

### 8.5 Slice 5: Profile Patch Proposals

Goal:

- Convert observations into proposed `USER.md` patches.

Tasks:

- Add patch proposal store.
- Add apply/reject actions.
- Add profile history.
- Show diff-style UI.
- Apply approved patches to `USER.md`.

### 8.6 Slice 6: Compact As Review Moment

Goal:

- `/compact` becomes the main moment for consolidating drafts, context, and profile learning.

Tasks:

- Extend compact output with knowledge queue recommendations.
- Extend compact output with profile patch proposals.
- Show compact review in Agent State.
- Keep auto mutations conservative.

## 9. Error Handling

### 9.1 Planning Failure

If LLM planning fails:

- Fall back to deterministic route.
- Prefer `answer_only` or `ask_before_persist`.
- Do not create formal knowledge nodes.
- Show a low-key warning in Agent State, not in the main answer unless it affects the user.

### 9.2 Knowledge Job Failure

If knowledge persistence fails:

- Keep the chat answer.
- Mark queue item as `failed`.
- Store error message.
- Offer retry.
- Do not leave a generic disabled link under the answer.

### 9.3 Profile Update Failure

If profile patch application fails:

- Keep proposal pending.
- Show error.
- Do not partially rewrite `USER.md`.

### 9.4 Conflicting Profile Observations

If observations conflict:

- Do not auto-apply.
- Show both as unresolved.
- Ask during profile review or compact.

## 10. Testing Strategy

### 10.1 Planner Tests

Fixtures:

- Broad question with no knowledge -> `answer_then_suggest_drafts`.
- Definition question with clear boundary -> `draft_first_then_answer`.
- Existing knowledge enough -> `reuse_answer`.
- Ambiguous question -> `clarify_first`.
- User says "do not save" -> no persistence route.

### 10.2 USER.md Lifecycle Tests

Fixtures:

- Explicit preference creates high-confidence observation.
- Repeated behavior creates medium-confidence observation after threshold.
- Low-risk patch can be proposed.
- High-risk background assumption is not auto-applied.
- Rejected observation does not reappear immediately.

### 10.3 Agent State API Tests

Verify:

- Current turn state returns plan summary.
- Queue item state transitions are valid.
- Failed knowledge jobs expose errors.
- Patch proposal apply writes history.

### 10.4 Frontend Tests

Verify:

- Chat card shows route summary.
- Review opens Agent State focused on the turn.
- Reader remains focused on Markdown node content.
- Agent State displays queue states and actions.
- Profile patch proposal renders diff and calls apply/reject.

## 11. Product Defaults

Initial defaults:

- `USER.md` update mode: `suggest`.
- Broad first-pass topics: `answer_then_suggest_drafts`.
- Definitions/proofs/notation: `draft_first_then_answer` when confidence is high.
- Low confidence persistence: `ask_before_persist`.
- Planning failure: `answer_only`, no persistence.
- Agent State placement: dedicated page.
- Optional compact Agent State preview can come later if the page proves useful.

## 12. Non-Goals For First Implementation

- No automatic large-scale rewriting of `USER.md`.
- No graph visualization.
- No multi-agent autonomous background planning.
- No bulk pre-generation of knowledge nodes.
- No full diff/merge system for knowledge nodes.
- No hidden persistence that the user cannot inspect.

## 13. Summary

The system should expose enough of its agent workflow to make knowledge growth understandable.

The core implementation move is to separate surfaces:

```text
Chat: natural conversation and lightweight plan summary.
Reader: stable Markdown knowledge reading.
Agent State: planning, drafts, queue, profile learning, compact review.
USER.md: long-term profile updated through observations and patch proposals.
```

This lets the system become more intelligent without becoming more mysterious.
