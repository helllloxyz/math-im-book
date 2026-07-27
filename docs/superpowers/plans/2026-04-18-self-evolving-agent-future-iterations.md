# Self-Evolving Agent Future Iterations Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current V1 orchestration visibility work into a reliable self-evolving learning system with scoped memory, reviewable profile updates, actionable Agent State, and safer knowledge persistence.

**Architecture:** Keep the existing separation: Chat answers questions, Reader renders stable knowledge nodes, Agent State exposes orchestration and pending actions, `USER.md` stores global user preferences, and future Scope Memory stores subject/project-specific learning context. Implement future work as small slices that preserve auditability before adding automation: observe first, propose second, apply last.

**Tech Stack:** Python dataclasses/Pydantic/FastAPI, file-backed JSONL storage, existing session storage, pytest, Vue 3, Pinia, TypeScript, Vitest.

---

## Current Baseline

The current implementation already provides the first slice:

- Planner can emit richer routes such as `answer_only`, `reuse_answer`, `answer_then_suggest_drafts`, `draft_first_then_answer`, `ask_before_persist`, `clarify_first`, and `compact_then_answer`.
- Broad first-pass questions no longer have to auto-persist as weak knowledge nodes.
- Assistant turns can persist orchestration plan and state items.
- Agent State page exists and can show current turn status, recent decisions, and live knowledge jobs.
- `USER.md` can be loaded into planner and answer prompt compiler as global profile context.
- Chat anchors distinguish ready sources, suggested drafts, pending writes, and failed writes.

The remaining work is not about making the planner more clever immediately. It is about making memory and persistence trustworthy enough that more automation will be safe.

## Product Principles For Future Work

Use these rules to resolve implementation tradeoffs:

- `USER.md` stores global preferences and stable background assumptions, not mathematical content.
- Scope Memory stores per-subject or per-project learning state, not cross-session global personality.
- Knowledge nodes store durable mathematical content, not chat answers or provider process text.
- Chat remains the interaction surface; Reader remains the stable knowledge reading surface; Agent State is the operational and review surface.
- Any system-maintained profile or memory update must be inspectable, reversible, and explainable.
- Automation should progress through `observe -> suggest -> auto_low_risk`, not directly to silent mutation.

## Future Slice 1: Profile Observation Store

**Purpose:** Record candidate learnings about the user without mutating `USER.md`.

**Files:**

- Create: `src/math_im_book/domain/profile.py`
- Create: `src/math_im_book/storage/profile_observations.py`
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`
- Test: `tests/storage/test_profile_observations.py`
- Test: `tests/api/test_agent_state_api.py`

**Data Contract:**

```python
@dataclass(frozen=True)
class ProfileObservation:
    observation_id: str
    created_at: str
    source_type: str
    source_session_id: str | None
    source_message_ids: list[str]
    category: str
    claim: str
    evidence_count: int
    confidence: str
    sensitivity: str
    status: str
    suggested_patch: str | None
```

**Storage:**

```text
data/config/user_profile/observations.jsonl
```

**Tasks:**

- [ ] Add `ProfileObservation` domain type with explicit allowed categories: `background`, `learning_style`, `answer_depth`, `persistence_policy`, `orchestration`, `language`, `notation`.
- [ ] Add file-backed JSONL repository with append/list/update-status methods.
- [ ] Expose active observations through `GET /api/agent-state`.
- [ ] Make observation records visible in Agent State as read-only candidates.
- [ ] Add tests that one explicit user preference can be stored as a high-confidence observation.
- [ ] Add tests that a low-confidence inferred background observation is shown but not promoted.

**Acceptance Criteria:**

- Agent State can show profile observations without editing `USER.md`.
- Observations survive process restart because they are JSONL-backed.
- Invalid categories, invalid confidence values, and missing claims are rejected or ignored before persistence.

## Future Slice 2: Profile Patch Proposals

**Purpose:** Convert observations into concrete proposed edits to `USER.md`, still without applying them automatically by default.

**Files:**

- Create: `src/math_im_book/storage/profile_patches.py`
- Modify: `src/math_im_book/storage/user_profile.py`
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Modify: `frontend/src/components/agent/AgentStatePage.vue`
- Test: `tests/storage/test_profile_patches.py`
- Test: `tests/api/test_user_profile_api.py`
- Test: `frontend/src/components/agent/AgentStatePage.test.ts`

**Data Contract:**

```python
@dataclass(frozen=True)
class ProfilePatchProposal:
    proposal_id: str
    created_at: str
    status: str
    target_section: str
    operation: str
    current_text: str | None
    proposed_text: str
    rationale: str
    evidence_observation_ids: list[str]
    risk_level: str
```

**Storage:**

```text
data/config/user_profile/patches.jsonl
data/config/user_profile/history.jsonl
```

**Tasks:**

- [ ] Add `ProfilePatchProposal` repository with statuses: `pending`, `approved`, `rejected`, `applied`, `superseded`.
- [ ] Add API endpoints for listing, approving, rejecting, and applying patch proposals.
- [ ] Render patch proposals in Agent State with proposed text, rationale, risk level, and evidence links.
- [ ] Keep default mode as `suggest`: proposals require user approval.
- [ ] Add history records for every applied patch.
- [ ] Add tests that approving a low-risk language preference appends one line to the correct `USER.md` section.
- [ ] Add tests that rejecting a proposal leaves `USER.md` unchanged and marks the proposal as `rejected`.

**Acceptance Criteria:**

- User can inspect proposed `USER.md` edits before they land.
- Every applied edit has an audit record.
- Patch application is idempotent: applying the same proposal twice does not duplicate text.

## Future Slice 3: Scope Memory

**Purpose:** Keep subject/project-specific learning context out of global `USER.md`.

**Files:**

- Create: `src/math_im_book/domain/scope_memory.py`
- Create: `src/math_im_book/storage/scope_memory.py`
- Modify: `src/math_im_book/services/planner.py`
- Modify: `src/math_im_book/services/prompt_compiler.py`
- Modify: `src/math_im_book/api/app.py`
- Modify: `frontend/src/components/agent/AgentStatePage.vue`
- Test: `tests/storage/test_scope_memory.py`
- Test: `tests/services/test_planner_strategy.py`
- Test: `tests/services/test_prompt_compiler.py`
- Test: `tests/api/test_agent_state_api.py`

**Storage:**

```text
data/config/scope_memory/<scope_id>/MEMORY.md
data/config/scope_memory/<scope_id>/observations.jsonl
data/config/scope_memory/<scope_id>/patches.jsonl
```

**Scope Examples:**

```text
linear-algebra
math-im-book
differential-geometry
project:<session-or-book-id>
```

**Tasks:**

- [ ] Add a deterministic scope id normalizer that converts provider output into safe directory names.
- [ ] Add `ScopeMemoryRepository` with read/write/list operations.
- [ ] Extend `OrchestrationPlan.detected_scope_ids` from audit-only metadata into planner input for known scopes.
- [ ] Load relevant `MEMORY.md` into planner and answer compiler after `USER.md`.
- [ ] Display detected scope, memory summary, and source file path in Agent State.
- [ ] Add tests that a linear algebra scope memory affects answer depth without changing global `USER.md`.
- [ ] Add tests that unknown scopes do not create files silently unless the route or user action asks to persist.

**Acceptance Criteria:**

- Global profile remains small and stable.
- Subject-specific facts like "in linear algebra, user wants abstract definitions paired with matrix examples" live in Scope Memory.
- Agent State explains which memory layers affected a turn.

## Future Slice 4: Actionable Agent State

**Purpose:** Make Agent State a control surface, not only a status page.

**Files:**

- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/services/knowledge_jobs.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Modify: `frontend/src/components/agent/AgentStatePage.vue`
- Test: `tests/api/test_agent_state_actions.py`
- Test: `tests/services/test_knowledge_jobs.py`
- Test: `frontend/src/components/agent/AgentStatePage.test.ts`
- Test: `frontend/src/stores/workspace.test.ts`

**Actions:**

```text
approve draft
reject draft
defer draft
retry failed knowledge write
apply profile patch
reject profile patch
open related chat turn
open related knowledge node
```

**Tasks:**

- [ ] Add backend action endpoints that operate on state item ids.
- [ ] Persist state item status transitions in session assistant context or a dedicated queue store.
- [ ] Add retry path for failed knowledge jobs with the original draft request.
- [ ] Add frontend buttons for actions with disabled states and short explanations.
- [ ] Refresh Agent State and current session anchors after each action.
- [ ] Add tests that rejecting a suggested draft removes it from actionable queue but keeps the historical decision visible.
- [ ] Add tests that retrying a failed write creates a new job and updates the old item to `superseded`.

**Acceptance Criteria:**

- The user can resolve pending items without leaving Agent State.
- Action history remains visible enough to audit what happened.
- Failed writes do not look like source citations.

## Future Slice 5: `/compact` As Review And Promotion Moment

**Purpose:** Make `/compact` the main lifecycle event for promoting observations, drafts, and messy session content into stable artifacts.

**Files:**

- Create: `src/math_im_book/services/compact_review.py`
- Modify: `src/math_im_book/services/orchestrator.py`
- Modify: `src/math_im_book/services/planner.py`
- Modify: `src/math_im_book/api/app.py`
- Modify: `frontend/src/components/agent/AgentStatePage.vue`
- Test: `tests/services/test_compact_review.py`
- Test: `tests/services/test_orchestrator.py`
- Test: `tests/api/test_agent_state_api.py`

**Review Outputs:**

```text
session summary
duplicate draft groups
promotable knowledge drafts
profile observations worth keeping
scope memory patches
stale or rejected candidates
```

**Tasks:**

- [ ] Detect `/compact` and route to `compact_then_answer`.
- [ ] Build a compact review service that reads session messages, state items, observations, and knowledge job outcomes.
- [ ] Group duplicate or overlapping draft candidates by normalized title and draft type.
- [ ] Generate review items instead of directly mutating knowledge/profile.
- [ ] Display compact review results in Agent State.
- [ ] Add tests that broad overview answers are not promoted unless enough bounded subnodes exist.
- [ ] Add tests that repeated explicit user preferences create one profile patch proposal, not many duplicate proposals.

**Acceptance Criteria:**

- `/compact` becomes a controlled consolidation flow.
- The user can see what the system wants to promote and why.
- Duplicate drafts and profile observations are merged before asking for approval.

## Future Slice 6: Knowledge Persistence Quality Gates

**Purpose:** Prevent weak, noisy, or process-oriented content from entering the knowledge base.

**Files:**

- Modify: `src/math_im_book/services/prompt_compiler.py`
- Modify: `src/math_im_book/services/orchestrator.py`
- Modify: `src/math_im_book/storage/knowledge.py`
- Modify: `frontend/src/components/chat/ChatMessage.vue`
- Test: `tests/services/test_prompt_compiler.py`
- Test: `tests/services/test_orchestrator.py`
- Test: `tests/storage/test_knowledge.py`
- Test: `frontend/src/components/chat/ChatMessage.test.ts`

**Quality Gates:**

```text
title is non-empty and bounded
draft_type is allowed
no provider process text
no "compiled from question" user-visible phrasing
summary and detail are mathematical content
source references are ready nodes only
broad overview nodes require supporting subnodes or explicit user approval
```

**Tasks:**

- [ ] Add compiler output validation that rejects process text and empty node boundaries.
- [ ] Add deterministic sanitizer for known bad phrases before storage.
- [ ] Store rejected compile attempts as failed Agent State items instead of weak knowledge nodes.
- [ ] Add explicit copy for failed writes that says the answer remains usable but persistence failed.
- [ ] Add tests that "No anchor knowledge was available" never appears in user-visible knowledge content.
- [ ] Add tests that a broad topic like `线性代数` creates suggested drafts, not a single formal node by default.

**Acceptance Criteria:**

- Knowledge nodes read like durable notes, not build logs.
- Failed persistence is transparent but does not pollute Reader.
- Source anchors only mean "used as answer source", not "saved after answer".

## Future Slice 7: Planner Observability And Evaluation Fixtures

**Purpose:** Make dynamic orchestration testable without relying only on live provider behavior.

**Files:**

- Create: `tests/fixtures/orchestration_cases.json`
- Create: `tests/services/test_orchestration_fixtures.py`
- Modify: `src/math_im_book/services/planner.py`
- Modify: `docs/DEVELOPMENT_PLAYBOOK.md`

**Fixture Shape:**

```json
{
  "case_id": "broad_linear_algebra_beginner",
  "question": "线性代数",
  "profile_summary": "User prefers beginner-friendly explanations with examples.",
  "active_node_titles": [],
  "expected_routes": ["answer_then_suggest_drafts", "answer_only"],
  "forbidden_routes": ["draft_first_then_answer"],
  "expected_candidate_titles": ["向量空间", "线性映射"]
}
```

**Tasks:**

- [ ] Add deterministic fixture tests for common orchestration cases.
- [ ] Add cases for broad overview, definition, proof, example, meta-design, explicit no-save, and profile update.
- [ ] Log planner route, confidence, persistence decision, and route fallback reason in a structured debug object.
- [ ] Document how to add new orchestration cases when bugs are found.
- [ ] Add tests that invalid provider JSON falls back to safe `answer_only` rather than persistence.

**Acceptance Criteria:**

- Route behavior can be regression-tested without live model calls.
- Planner failures degrade into safe, user-visible behavior.
- Future subagents can add cases before changing planner logic.

## Future Slice 8: UX Polish For Memory And Persistence

**Purpose:** Make the system understandable to users who do not care about internal planner terminology.

**Files:**

- Modify: `frontend/src/components/chat/ChatMessage.vue`
- Modify: `frontend/src/components/agent/AgentStatePage.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/stores/workspace.ts`
- Test: `frontend/src/components/chat/ChatMessage.test.ts`
- Test: `frontend/src/components/agent/AgentStatePage.test.ts`
- Test: `frontend/src/App.test.ts`

**UX Copy Rules:**

```text
Ready source: stable note used to answer
Suggested draft: possible note, not saved yet
Pending write: saving is in progress
Failed write: answer succeeded, saving failed
Profile suggestion: possible preference update
Scope memory: subject/project learning context
```

**Tasks:**

- [ ] Replace planner route names with user-facing labels in the UI.
- [ ] Add compact explanatory tooltips for source, draft, pending, failed, and profile suggestion badges.
- [ ] Add empty Agent State view explaining what will appear there.
- [ ] Add focused view when opened from a specific assistant message.
- [ ] Keep Reader free of operational state and link users to Agent State for review actions.
- [ ] Add tests that user-facing labels do not expose raw route names such as `answer_then_suggest_drafts`.

**Acceptance Criteria:**

- Users can tell whether a link is a source, suggestion, pending write, or failure.
- Agent State explains decisions without exposing raw planner JSON by default.
- Markdown Reader remains a clean knowledge reading surface.

## Suggested Implementation Order

1. Profile Observation Store.
2. Profile Patch Proposals.
3. Actionable Agent State for patch and draft decisions.
4. Knowledge Persistence Quality Gates.
5. Planner Observability And Evaluation Fixtures.
6. Scope Memory.
7. `/compact` review and promotion.
8. UX polish pass after real usage reveals confusing labels.

This order keeps risk low: first collect and show evidence, then add user-approved mutation, then add scoped memory, and only later automate consolidation.

## Deferred Decisions

These decisions should be made when implementing the relevant slice, not earlier:

- Whether `auto_low_risk` should ever be enabled by default. The safe default remains `suggest`.
- Whether Scope Memory should be created implicitly from detected scope or only after user confirmation. The safe default is confirmation.
- Whether failed knowledge jobs should preserve full compiler input. The safe default is to preserve only non-secret draft metadata and error summaries.
- Whether Agent State should become a split panel later. The current default remains a dedicated page.

## Verification Checklist For Each Slice

Run these before marking a slice complete:

```bash
.venv/bin/pytest -q -o cache_dir=/tmp/math-im-book-pytest-cache
cd frontend && npm run test -- --run
cd frontend && npm run build
git diff --check
```

Each slice should also include at least one focused backend or frontend test that fails before implementation and passes after implementation.
