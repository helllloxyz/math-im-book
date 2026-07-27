# Agent State V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first implementation slice for transparent agent orchestration: every assistant turn carries a lightweight orchestration plan, chat cards show the plan summary, and a dedicated Agent State page shows current turn status, memory scope awareness, knowledge queue, context health, and recent decisions.

**Architecture:** Add a small `OrchestrationPlan` model to the backend and persist it inside `SessionAssistantContext`. The plan records the route plus lightweight profile-layer metadata such as detected scope ids and which profile layers influenced the route. Extend planner output parsing but keep backward compatibility with existing `reuse_answer` and `expand_with_drafts` responses. Add a read-only Agent State API derived from existing session state first; automatic `USER.md` mutation, Scope Memory storage, and durable queue stores are deferred to later slices.

**Tech Stack:** Python dataclasses, Pydantic schemas, FastAPI, file-backed session storage, pytest, Vue 3, Pinia, TypeScript, Vitest.

---

## Coordination Rules For Subagents

This plan is designed for multiple subagents. Use these write ownership boundaries to avoid conflicts:

```text
Subagent A: Backend data contract and session persistence
Subagent B: Planner and orchestrator route behavior
Subagent C: Agent State backend API
Subagent D: Frontend API/types/store
Subagent E: Frontend UI components and App navigation
Subagent F: Final integration and verification
```

Do not edit files outside your assigned task unless the plan explicitly says to. If a required interface is missing because another task has not landed yet, add the failing test and stop with a clear note instead of inventing a parallel interface.

Before starting any task, run:

```bash
git status --short
```

Expected: either clean output or unrelated user changes. Do not revert unrelated changes.

Backend tests:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/api tests/services tests/storage
```

Frontend tests:

```bash
cd frontend && npm run test
```

---

## Memory Layer Boundary For V1

The implementation must preserve this boundary:

```text
Answers belong to Chat.
Subject facts belong to Knowledge.
Global preferences belong to USER.md.
Scoped learning state belongs to Scope Memory.
```

V1 does not implement automatic `USER.md` mutation or Scope Memory file writes. V1 only makes the route decision and memory-layer usage visible so later work can safely add self-evolution.

### Layers

`USER.md`

- Global user profile.
- Cross-subject preferences, communication style, global orchestration defaults.
- Example: "User prefers overall design before implementation."

`Scope Memory`

- Future per-subject or per-project memory.
- Records the user's local learning state, local preferences, and current progress in a scope.
- Example: "In linear algebra, user is comfortable with matrices but wants examples for abstract vector-space definitions."

`Knowledge Base`

- Durable subject facts.
- Definitions, theorems, proofs, examples, notation decisions, and stable concept relationships.

`Chat / Session Archive`

- Raw interaction history and temporary process.
- Searchable later, but not injected as always-on profile context.

### V1 Contract

`OrchestrationPlan` carries these fields for future compatibility:

- `detected_scope_ids`: planner-visible scope ids such as `linear-algebra` or `math-im-book`. Empty list means no scope was confidently detected.
- `profile_layers_used`: names of profile/memory layers used or considered, such as `global_user`, `scope_memory:linear-algebra`, or `knowledge_context`. V1 may return an empty list when no layer is available.
- `profile_context_summary`: short user-visible explanation of profile/scope influence. `None` means no profile context affected the decision.

These fields are audit metadata. They do not imply any Scope Memory store exists yet.

---

## Files And Responsibilities

### Backend

`src/math_im_book/domain/models.py`

Add dataclasses for:

- `KnowledgeDraftCandidate`
- `OrchestrationPlan`
- optional `AgentStateItem`

Extend `SessionAssistantContext` with:

- `orchestration_plan: OrchestrationPlan | None`
- `state_items: list[AgentStateItem]`

`src/math_im_book/api/schemas.py`

Add Pydantic schemas mirroring the new dataclasses and expose them through:

- `SessionAssistantContextSchema`
- `AskResponseSchema` indirectly through `session.messages`
- new Agent State response schemas

`src/math_im_book/storage/sessions.py`

Serialize and deserialize `orchestration_plan` and `state_items` in message assistant context.

`src/math_im_book/services/planner.py`

Parse the new planner output contract while remaining compatible with old planner output. Add deterministic fallback plan creation. V1 should preserve scope/profile metadata from provider output but should not create a Scope Memory store.

`src/math_im_book/services/orchestrator.py`

Attach an `OrchestrationPlan` to `AskResult` and `SessionAssistantContext`. Route behavior remains minimal for V1:

- `reuse_answer` behaves as today.
- `answer_only` renders an answer without knowledge job.
- `answer_then_suggest_drafts` renders answer and returns suggested state items without submitting a job.
- `expand_with_drafts` remains compatible and maps to `draft_first_then_answer` or pending write.

`src/math_im_book/api/app.py`

Persist plan and state items in assistant messages. Add read-only `GET /api/agent-state` that exposes memory scope awareness as audit metadata.

### Frontend

`frontend/src/services/api.ts`

Add TypeScript interfaces for:

- `OrchestrationPlan`
- `KnowledgeDraftCandidate`
- `AgentStateItem`
- `MemoryScopeState`
- `AgentState`
- `AgentTurnState`
- `KnowledgeQueueItem`
- `ContextHealth`
- `AgentDecisionSummary`

Add `api.getAgentState(sessionId?: string)`.

`frontend/src/stores/workspace.ts`

Add:

- `activeTab: 'chat' | 'book' | 'agent'`
- `agentState`
- `fetchAgentState`
- `openAgentStateForMessage`

Call `fetchAgentState` after ask, after job polling updates, and when selecting session.

`frontend/src/components/chat/ChatMessage.vue`

Render a compact plan strip for assistant messages with an orchestration plan.

Emit:

- `review-state`

`frontend/src/components/agent/AgentStatePage.vue`

New dedicated page for current turn, memory scope metadata, knowledge queue, context health, and recent decisions.

`frontend/src/App.vue`

Add side nav entry for Agent State and render `AgentStatePage` in the main workspace when active.

---

## Task 1: Backend Data Contract And Session Persistence

**Owner:** Subagent A

**Files:**

- Modify: `src/math_im_book/domain/models.py`
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Test: `tests/api/test_schemas.py`
- Test: `tests/storage/test_sessions.py`

- [ ] **Step 1: Write schema test for orchestration plan in assistant context**

Add to `tests/api/test_schemas.py`:

```python
def test_session_assistant_context_schema_serializes_orchestration_plan() -> None:
    context = SessionAssistantContextSchema(
        action_type="answer_then_suggest_drafts",
        referenced_node_ids=[],
        anchors=[],
        symbol_conflicts=[],
        alignment_notes=[],
        orchestration_plan={
            "route": "answer_then_suggest_drafts",
            "intent": "broad_overview",
            "persistence_decision": "suggest_drafts",
            "confidence": 0.78,
            "user_visible_summary": "先给概览，并建议可整理的知识点。",
            "detected_scope_ids": ["linear-algebra"],
            "profile_layers_used": ["global_user", "scope_memory:linear-algebra"],
            "profile_context_summary": "识别为线性代数范围；本轮只建议知识点，不直接落盘。",
            "candidate_drafts": [
                {
                    "title": "Vector Space",
                    "draft_type": "definition",
                    "reason": "Foundational reusable concept.",
                }
            ],
        },
        state_items=[
            {
                "item_id": "draft-vector-space",
                "kind": "knowledge_draft",
                "state": "suggested",
                "title": "Vector Space",
                "reason": "Foundational reusable concept.",
                "source_message_id": "msg-assistant",
            }
        ],
    )

    dumped = context.model_dump()

    assert dumped["orchestration_plan"]["route"] == "answer_then_suggest_drafts"
    assert dumped["orchestration_plan"]["detected_scope_ids"] == ["linear-algebra"]
    assert dumped["orchestration_plan"]["profile_layers_used"][0] == "global_user"
    assert dumped["orchestration_plan"]["candidate_drafts"][0]["title"] == "Vector Space"
    assert dumped["state_items"][0]["state"] == "suggested"
```

- [ ] **Step 2: Run schema test and verify it fails**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/api/test_schemas.py::test_session_assistant_context_schema_serializes_orchestration_plan
```

Expected: fail because `SessionAssistantContextSchema` does not accept `orchestration_plan` or `state_items`.

- [ ] **Step 3: Add domain dataclasses**

In `src/math_im_book/domain/models.py`, add after `PendingDraftRequest`:

```python
@dataclass(slots=True)
class KnowledgeDraftCandidate:
    title: str
    draft_type: str
    reason: str


@dataclass(slots=True)
class OrchestrationPlan:
    route: str
    intent: str
    persistence_decision: str
    confidence: float
    user_visible_summary: str
    detected_scope_ids: list[str] = field(default_factory=list)
    profile_layers_used: list[str] = field(default_factory=list)
    profile_context_summary: str | None = None
    candidate_drafts: list[KnowledgeDraftCandidate] = field(default_factory=list)


@dataclass(slots=True)
class AgentStateItem:
    item_id: str
    kind: str
    state: str
    title: str
    reason: str = ""
    source_message_id: str | None = None
    node_id: str | None = None
    error_message: str | None = None
```

Extend `SessionAssistantContext`:

```python
@dataclass(slots=True)
class SessionAssistantContext:
    action_type: str | None = None
    referenced_node_ids: list[str] = field(default_factory=list)
    anchors: list[AnswerAnchor] = field(default_factory=list)
    symbol_conflicts: list[str] = field(default_factory=list)
    alignment_notes: list[str] = field(default_factory=list)
    compact_summary: dict[str, object] | None = None
    orchestration_plan: OrchestrationPlan | None = None
    state_items: list[AgentStateItem] = field(default_factory=list)
```

- [ ] **Step 4: Add API schemas**

In `src/math_im_book/api/schemas.py`, add after `PendingDraftRequestSchema`:

```python
class KnowledgeDraftCandidateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    draft_type: str
    reason: str


class OrchestrationPlanSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: str
    intent: str
    persistence_decision: str
    confidence: float
    user_visible_summary: str
    detected_scope_ids: list[str] = Field(default_factory=list)
    profile_layers_used: list[str] = Field(default_factory=list)
    profile_context_summary: str | None = None
    candidate_drafts: list[KnowledgeDraftCandidateSchema] = Field(default_factory=list)


class AgentStateItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    kind: str
    state: str
    title: str
    reason: str = ""
    source_message_id: str | None = None
    node_id: str | None = None
    error_message: str | None = None
```

Extend `SessionAssistantContextSchema`:

```python
class SessionAssistantContextSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str | None = None
    referenced_node_ids: list[str] = Field(default_factory=list)
    anchors: list[AnswerAnchorSchema] = Field(default_factory=list)
    symbol_conflicts: list[str] = Field(default_factory=list)
    alignment_notes: list[str] = Field(default_factory=list)
    compact_summary: dict[str, object] | None = None
    orchestration_plan: OrchestrationPlanSchema | None = None
    state_items: list[AgentStateItemSchema] = Field(default_factory=list)
```

- [ ] **Step 5: Add conversion helpers in API app**

In `src/math_im_book/api/app.py`, import new dataclasses and add helpers near `_answer_anchor_to_schema`:

```python
def _orchestration_plan_to_schema(plan: OrchestrationPlan | None) -> OrchestrationPlanSchema | None:
    if plan is None:
        return None
    return OrchestrationPlanSchema(
        route=plan.route,
        intent=plan.intent,
        persistence_decision=plan.persistence_decision,
        confidence=plan.confidence,
        user_visible_summary=plan.user_visible_summary,
        detected_scope_ids=plan.detected_scope_ids,
        profile_layers_used=plan.profile_layers_used,
        profile_context_summary=plan.profile_context_summary,
        candidate_drafts=[
            KnowledgeDraftCandidateSchema(
                title=draft.title,
                draft_type=draft.draft_type,
                reason=draft.reason,
            )
            for draft in plan.candidate_drafts
        ],
    )


def _agent_state_item_to_schema(item: AgentStateItem) -> AgentStateItemSchema:
    return AgentStateItemSchema(
        item_id=item.item_id,
        kind=item.kind,
        state=item.state,
        title=item.title,
        reason=item.reason,
        source_message_id=item.source_message_id,
        node_id=item.node_id,
        error_message=item.error_message,
    )
```

Then include fields in `_session_message_to_schema`:

```python
orchestration_plan=_orchestration_plan_to_schema(
    message.assistant_context.orchestration_plan
),
state_items=[
    _agent_state_item_to_schema(item).model_dump()
    for item in message.assistant_context.state_items
],
```

- [ ] **Step 6: Add session storage serialization**

In `src/math_im_book/storage/sessions.py`, import the new dataclasses and add helpers near `_serialize_message`:

```python
def _serialize_orchestration_plan(plan: OrchestrationPlan | None) -> dict[str, object] | None:
    if plan is None:
        return None
    return {
        "route": plan.route,
        "intent": plan.intent,
        "persistence_decision": plan.persistence_decision,
        "confidence": plan.confidence,
        "user_visible_summary": plan.user_visible_summary,
        "detected_scope_ids": plan.detected_scope_ids,
        "profile_layers_used": plan.profile_layers_used,
        "profile_context_summary": plan.profile_context_summary,
        "candidate_drafts": [
            {
                "title": draft.title,
                "draft_type": draft.draft_type,
                "reason": draft.reason,
            }
            for draft in plan.candidate_drafts
        ],
    }


def _serialize_state_item(item: AgentStateItem) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "kind": item.kind,
        "state": item.state,
        "title": item.title,
        "reason": item.reason,
        "source_message_id": item.source_message_id,
        "node_id": item.node_id,
        "error_message": item.error_message,
    }
```

Add to serialized assistant context:

```python
"orchestration_plan": _serialize_orchestration_plan(
    message.assistant_context.orchestration_plan
),
"state_items": [
    _serialize_state_item(item)
    for item in message.assistant_context.state_items
],
```

Add deserialization helpers:

```python
def _load_orchestration_plan(payload: object) -> OrchestrationPlan | None:
    if not isinstance(payload, dict):
        return None
    route = payload.get("route")
    intent = payload.get("intent")
    persistence_decision = payload.get("persistence_decision")
    confidence = payload.get("confidence")
    user_visible_summary = payload.get("user_visible_summary")
    if not isinstance(route, str) or not isinstance(intent, str):
        return None
    if not isinstance(persistence_decision, str) or not isinstance(user_visible_summary, str):
        return None
    if not isinstance(confidence, int | float):
        return None
    return OrchestrationPlan(
        route=route,
        intent=intent,
        persistence_decision=persistence_decision,
        confidence=float(confidence),
        user_visible_summary=user_visible_summary,
        detected_scope_ids=_load_string_list(payload.get("detected_scope_ids")),
        profile_layers_used=_load_string_list(payload.get("profile_layers_used")),
        profile_context_summary=payload.get("profile_context_summary") if isinstance(payload.get("profile_context_summary"), str) else None,
        candidate_drafts=_load_draft_candidates(payload.get("candidate_drafts")),
    )


def _load_string_list(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, str) and item]


def _load_draft_candidates(payload: object) -> list[KnowledgeDraftCandidate]:
    if not isinstance(payload, list):
        return []
    drafts: list[KnowledgeDraftCandidate] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        draft_type = item.get("draft_type")
        reason = item.get("reason")
        if all(isinstance(value, str) and value for value in (title, draft_type, reason)):
            drafts.append(KnowledgeDraftCandidate(title=title, draft_type=draft_type, reason=reason))
    return drafts


def _load_state_items(payload: object) -> list[AgentStateItem]:
    if not isinstance(payload, list):
        return []
    items: list[AgentStateItem] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_id = item.get("item_id")
        kind = item.get("kind")
        state = item.get("state")
        title = item.get("title")
        if not all(isinstance(value, str) and value for value in (item_id, kind, state, title)):
            continue
        items.append(
            AgentStateItem(
                item_id=item_id,
                kind=kind,
                state=state,
                title=title,
                reason=item.get("reason") if isinstance(item.get("reason"), str) else "",
                source_message_id=item.get("source_message_id") if isinstance(item.get("source_message_id"), str) else None,
                node_id=item.get("node_id") if isinstance(item.get("node_id"), str) else None,
                error_message=item.get("error_message") if isinstance(item.get("error_message"), str) else None,
            )
        )
    return items
```

Use them in `_load_assistant_context`:

```python
orchestration_plan=_load_orchestration_plan(raw_context.get("orchestration_plan")),
state_items=_load_state_items(raw_context.get("state_items")),
```

- [ ] **Step 7: Add storage roundtrip test**

Create `tests/storage/test_sessions.py`:

```python
from math_im_book.domain.models import (
    AgentStateItem,
    KnowledgeDraftCandidate,
    OrchestrationPlan,
    SessionAssistantContext,
)
from math_im_book.storage.sessions import FileSessionStore, SessionMessage, SessionRecord


def test_session_store_roundtrips_orchestration_plan(tmp_path) -> None:
    store = FileSessionStore(tmp_path / "sessions")
    record = SessionRecord(session_id="chat-1", messages=[
        SessionMessage(
            message_id="msg-1",
            role="assistant",
            content="Answer",
            created_at="2026-04-18T00:00:00Z",
            assistant_context=SessionAssistantContext(
                action_type="answer_then_suggest_drafts",
                orchestration_plan=OrchestrationPlan(
                    route="answer_then_suggest_drafts",
                    intent="broad_overview",
                    persistence_decision="suggest_drafts",
                    confidence=0.78,
                    user_visible_summary="先给概览。",
                    detected_scope_ids=["linear-algebra"],
                    profile_layers_used=["global_user", "scope_memory:linear-algebra"],
                    profile_context_summary="识别为线性代数范围。",
                    candidate_drafts=[
                        KnowledgeDraftCandidate(
                            title="Vector Space",
                            draft_type="definition",
                            reason="Reusable concept.",
                        )
                    ],
                ),
                state_items=[
                    AgentStateItem(
                        item_id="draft-vector-space",
                        kind="knowledge_draft",
                        state="suggested",
                        title="Vector Space",
                        reason="Reusable concept.",
                    )
                ],
            ),
        )
    ])

    store.save_record(record)
    loaded = store.load_record("chat-1")

    context = loaded.messages[0].assistant_context
    assert context.orchestration_plan.route == "answer_then_suggest_drafts"
    assert context.orchestration_plan.detected_scope_ids == ["linear-algebra"]
    assert context.orchestration_plan.candidate_drafts[0].title == "Vector Space"
    assert context.state_items[0].state == "suggested"
```

Adjust constructor arguments for `SessionRecord` to match the current class definition in `src/math_im_book/storage/sessions.py`.

- [ ] **Step 8: Run tests**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/api/test_schemas.py tests/storage/test_sessions.py
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add src/math_im_book/domain/models.py src/math_im_book/api/schemas.py src/math_im_book/storage/sessions.py tests/api/test_schemas.py tests/storage/test_sessions.py
git commit -m "feat: persist orchestration plan in sessions"
```

---

## Task 2: Planner Contract And Route Fallbacks

**Owner:** Subagent B

**Files:**

- Modify: `src/math_im_book/services/planner.py`
- Test: `tests/services/test_planner.py`
- Test: `tests/services/test_planner_strategy.py`

- [ ] **Step 1: Write failing tests for new planner contract**

Add to `tests/services/test_planner.py`:

```python
def test_planner_parses_orchestration_plan_contract() -> None:
    gateway = FakeProviderGateway(
        ProviderResult(
            output_text=(
                '{"route":"answer_then_suggest_drafts",'
                '"intent":"broad_overview",'
                '"persistence_decision":"suggest_drafts",'
                '"confidence":0.82,'
                '"selected_node_ids":[],'
                '"detected_scope_ids":["linear-algebra"],'
                '"profile_layers_used":["global_user","scope_memory:linear-algebra"],'
                '"profile_context_summary":"识别为线性代数范围；用户倾向先看整体再整理节点。",'
                '"candidate_drafts":[{"title":"Vector Space",'
                '"draft_type":"definition",'
                '"reason":"Foundational reusable concept."}],'
                '"user_visible_summary":"先给概览，并建议知识点。"}'
            ),
            provider_name="gemini",
        )
    )
    planner = QuestionPlanner(provider_gateway=gateway)

    action = planner.plan(
        "线性代数",
        [],
        provider_profile=ProviderProfile(
            provider_type="gemini",
            model="gemini-2.5-flash",
            credential_id="gemini-main",
        ),
    )

    assert action.action_type == "answer_then_suggest_drafts"
    assert action.orchestration_plan.route == "answer_then_suggest_drafts"
    assert action.orchestration_plan.intent == "broad_overview"
    assert action.orchestration_plan.detected_scope_ids == ["linear-algebra"]
    assert "scope_memory:linear-algebra" in action.orchestration_plan.profile_layers_used
    assert action.orchestration_plan.candidate_drafts[0].title == "Vector Space"
```

Add a fallback test:

```python
def test_planner_falls_back_to_answer_only_for_broad_question_without_provider() -> None:
    planner = QuestionPlanner()

    action = planner.plan_without_provider("线性代数", [])

    assert action.action_type == "answer_only"
    assert action.orchestration_plan.route == "answer_only"
    assert action.orchestration_plan.persistence_decision == "do_not_persist"
    assert action.orchestration_plan.detected_scope_ids == []
```

Replace the existing `test_planner_requires_provider_configuration` with:

```python
def test_planner_without_provider_returns_answer_only_fallback() -> None:
    planner = QuestionPlanner()

    action = planner.plan(question="What is a linear map?", nodes=[])

    assert action.action_type == "answer_only"
    assert action.orchestration_plan.route == "answer_only"
    assert action.orchestration_plan.persistence_decision == "do_not_persist"
```

Remove `PlannerConfigurationError` from the imports in `tests/services/test_planner.py`:

```python
from math_im_book.services.planner import QuestionPlanner
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/services/test_planner.py::test_planner_parses_orchestration_plan_contract tests/services/test_planner.py::test_planner_falls_back_to_answer_only_for_broad_question_without_provider
```

Expected: fail because `AgentAction` has no `orchestration_plan` and `QuestionPlanner.plan_without_provider` does not exist.

- [ ] **Step 3: Extend `AgentAction`**

In `src/math_im_book/domain/models.py`, add field:

```python
@dataclass(slots=True)
class AgentAction:
    action_type: str
    selected_node_ids: list[str] = field(default_factory=list)
    draft_requests: list[PendingDraftRequest] = field(default_factory=list)
    user_visible_reason: str = ""
    orchestration_plan: OrchestrationPlan | None = None
```

- [ ] **Step 4: Update planner allowed routes and prompt**

In `QuestionPlanner`, add:

```python
_ALLOWED_ROUTES = {
    "answer_only",
    "reuse_answer",
    "answer_then_suggest_drafts",
    "draft_first_then_answer",
    "ask_before_persist",
    "clarify_first",
    "compact_then_answer",
}

_ROUTE_TO_LEGACY_ACTION = {
    "answer_only": "answer_only",
    "reuse_answer": "reuse_answer",
    "answer_then_suggest_drafts": "answer_then_suggest_drafts",
    "draft_first_then_answer": "expand_with_drafts",
    "ask_before_persist": "ask_before_persist",
    "clarify_first": "clarify_first",
    "compact_then_answer": "compact_then_answer",
}
```

Update provider system instruction to request the new fields:

```python
"Return bare JSON only, with no Markdown fences or explanatory text. "
"Prefer the new keys route, intent, persistence_decision, confidence, "
"selected_node_ids, detected_scope_ids, profile_layers_used, "
"profile_context_summary, candidate_drafts, user_visible_summary. "
"route must be one of: answer_only, reuse_answer, answer_then_suggest_drafts, "
"draft_first_then_answer, ask_before_persist, clarify_first, compact_then_answer. "
"detected_scope_ids must only include scopes visible in supplied context; use [] if uncertain. "
"profile_layers_used must name layers that influenced the decision, for example global_user, "
"scope_memory:linear-algebra, or knowledge_context; use [] if no profile or scope context was used. "
"candidate_drafts must contain objects with title, draft_type, and reason. "
"Use draft_first_then_answer only when durable knowledge should be created before answering. "
"Use answer_then_suggest_drafts for broad exploratory questions that should not be persisted immediately. "
"For backward compatibility, action_type and draft_requests are also accepted."
```

- [ ] **Step 5: Implement parser helpers**

Add methods:

```python
def plan_without_provider(
    self,
    question: str,
    nodes: list[KnowledgeNode],
    branch_symbols: dict[str, str] | None = None,
) -> AgentAction:
    selected_node_ids = [node.id for node in nodes[:1]] if nodes else []
    if selected_node_ids:
        route = "reuse_answer"
        persistence_decision = "do_not_persist"
        summary = "I can answer using existing knowledge."
    else:
        route = "answer_only"
        persistence_decision = "do_not_persist"
        summary = "I will answer directly without saving a knowledge node."
    plan = OrchestrationPlan(
        route=route,
        intent=self._infer_basic_intent(question),
        persistence_decision=persistence_decision,
        confidence=0.55,
        user_visible_summary=summary,
        detected_scope_ids=[],
        profile_layers_used=[],
        profile_context_summary=None,
    )
    return AgentAction(
        action_type=route,
        selected_node_ids=selected_node_ids,
        user_visible_reason=summary,
        orchestration_plan=plan,
    )


@staticmethod
def _infer_basic_intent(question: str) -> str:
    normalized = question.strip().lower()
    if normalized.startswith("/compact"):
        return "compact"
    if any(token in normalized for token in ("prove", "证明", "why", "为什么")):
        return "proof"
    if any(token in normalized for token in ("what is", "什么是", "define", "定义")):
        return "definition"
    return "broad_overview"
```

Modify `plan()` so missing provider returns fallback instead of raising:

```python
if provider_profile is None or self.provider_gateway is None:
    return self.plan_without_provider(question, nodes, branch_symbols)
```

Add `_parse_orchestration_payload` that accepts both new and old contracts:

```python
def _parse_orchestration_payload(
    self,
    payload: dict[str, object],
    candidate_node_ids: set[str],
) -> AgentAction:
    route = payload.get("route")
    if isinstance(route, str):
        return self._parse_new_route_payload(payload, candidate_node_ids, route)
    return self._parse_legacy_payload(payload, candidate_node_ids)
```

Implement `_parse_new_route_payload` by validating selected ids, detected scope ids, profile layers, candidate drafts, confidence, and creating `OrchestrationPlan`.

Add helper:

```python
@staticmethod
def _string_list(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, str) and item.strip()]
```

When creating the new-route plan, include:

```python
profile_context_summary = payload.get("profile_context_summary")
plan = OrchestrationPlan(
    route=route,
    intent=intent,
    persistence_decision=persistence_decision,
    confidence=confidence,
    user_visible_summary=user_visible_summary,
    detected_scope_ids=self._string_list(payload.get("detected_scope_ids")),
    profile_layers_used=self._string_list(payload.get("profile_layers_used")),
    profile_context_summary=profile_context_summary if isinstance(profile_context_summary, str) else None,
    candidate_drafts=candidate_drafts,
)
```

- [ ] **Step 6: Keep legacy parser tests green**

Existing tests expect `expand_with_drafts` and `reuse_answer` to parse. Ensure old `action_type` payloads still return the same action types and now include a compatible plan:

```python
plan = OrchestrationPlan(
    route="draft_first_then_answer" if action_type == "expand_with_drafts" else "reuse_answer",
    intent="definition" if draft_requests else "broad_overview",
    persistence_decision="persist_first" if draft_requests else "do_not_persist",
    confidence=0.7,
    user_visible_summary=user_visible_reason,
    detected_scope_ids=[],
    profile_layers_used=["knowledge_context"] if selected_node_ids else [],
    profile_context_summary=None,
    candidate_drafts=[
        KnowledgeDraftCandidate(title=d.title, draft_type=d.draft_type, reason=d.reason)
        for d in draft_requests
    ],
)
```

- [ ] **Step 7: Run planner tests**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/services/test_planner.py tests/services/test_planner_strategy.py
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add src/math_im_book/domain/models.py src/math_im_book/services/planner.py tests/services/test_planner.py tests/services/test_planner_strategy.py
git commit -m "feat: add orchestration planner contract"
```

---

## Task 3: Orchestrator Route Execution And Message Context

**Owner:** Subagent B or separate backend subagent after Task 2

**Files:**

- Modify: `src/math_im_book/domain/models.py`
- Modify: `src/math_im_book/services/orchestrator.py`
- Modify: `src/math_im_book/api/app.py`
- Test: `tests/services/test_orchestrator.py`
- Test: `tests/api/test_sessions_api.py`

- [ ] **Step 1: Write failing orchestrator test for `answer_then_suggest_drafts`**

Add to `tests/services/test_orchestrator.py`:

```python
def test_orchestrator_suggests_drafts_without_starting_knowledge_job(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    knowledge_jobs = InMemoryKnowledgeJobRepository(repository, auto_start=False)
    gateway = SequenceProviderGateway(
        [
            ProviderResult(
                output_text=(
                    '{"route":"answer_then_suggest_drafts",'
                    '"intent":"broad_overview",'
                    '"persistence_decision":"suggest_drafts",'
                    '"confidence":0.82,'
                    '"selected_node_ids":[],'
                    '"detected_scope_ids":["linear-algebra"],'
                    '"profile_layers_used":["global_user","scope_memory:linear-algebra"],'
                    '"profile_context_summary":"识别为线性代数范围。",'
                    '"candidate_drafts":[{"title":"Vector Space",'
                    '"draft_type":"definition",'
                    '"reason":"Foundational reusable concept."}],'
                    '"user_visible_summary":"先给概览，并建议知识点。"}'
                ),
                provider_name="gemini",
            ),
            ProviderResult(output_text="线性代数研究线性结构。", provider_name="gemini"),
        ]
    )
    orchestrator = KnowledgeOrchestrator(
        repository=repository,
        planner=QuestionPlanner(provider_gateway=gateway),
        provider_gateway=gateway,
        knowledge_job_repository=knowledge_jobs,
    )

    result = orchestrator.answer("线性代数", provider_profile=_provider_profile())

    assert result.action.action_type == "answer_then_suggest_drafts"
    assert result.answer.knowledge_job_id is None
    assert result.answer.anchors == []
    assert result.answer.assistant_text == "线性代数研究线性结构。"
    assert result.state_items[0].state == "suggested"
    assert result.state_items[0].title == "Vector Space"
    assert result.orchestration_plan.route == "answer_then_suggest_drafts"
    assert result.orchestration_plan.detected_scope_ids == ["linear-algebra"]
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/services/test_orchestrator.py::test_orchestrator_suggests_drafts_without_starting_knowledge_job
```

Expected: fail because `AskResult` does not expose `state_items` or `orchestration_plan`, and orchestrator treats every non-reuse action as a knowledge job.

- [ ] **Step 3: Extend `AskResult`**

In `src/math_im_book/domain/models.py`:

```python
@dataclass(slots=True)
class AskResult:
    action: AgentAction
    answer: AnswerPayload
    drafts: list[PendingDraftRequest] = field(default_factory=list)
    created_node_ids: list[str] = field(default_factory=list)
    branch_context: "SessionBranch | None" = None
    orchestration_plan: OrchestrationPlan | None = None
    state_items: list[AgentStateItem] = field(default_factory=list)
```

- [ ] **Step 4: Add state item helper in orchestrator**

In `src/math_im_book/services/orchestrator.py`:

```python
def _state_items_for_plan(self, plan: OrchestrationPlan | None) -> list[AgentStateItem]:
    if plan is None:
        return []
    items: list[AgentStateItem] = []
    for draft in plan.candidate_drafts:
        items.append(
            AgentStateItem(
                item_id=f"draft-{self._slugify(draft.title)}",
                kind="knowledge_draft",
                state="suggested",
                title=draft.title,
                reason=draft.reason,
            )
        )
    return items
```

- [ ] **Step 5: Implement `answer_only` and `answer_then_suggest_drafts` branches**

After symbol context and before the current `reuse_answer` branch, define:

```python
plan = action.orchestration_plan
```

For `answer_only`, `answer_then_suggest_drafts`, `ask_before_persist`, and `clarify_first`, render an answer without a knowledge job:

```python
if action.action_type in {
    "answer_only",
    "answer_then_suggest_drafts",
    "ask_before_persist",
    "clarify_first",
}:
    summary = action.user_visible_reason or (plan.user_visible_summary if plan else "Answering directly.")
    detail = summary
    detail = self._detail_with_summary_context(detail, summary_nodes)
    detail = self._detail_with_symbol_guidance(detail, detail_symbol_guidance)
    assistant_text = self._render_answer(...)
    return AskResult(
        action=action,
        answer=AnswerPayload(
            summary=summary,
            detail=detail,
            references=[node.id for node in selected_nodes],
            anchors=[],
            symbols=symbol_context.symbols,
            symbol_conflicts=scope_symbol_context.conflicts,
            assistant_text=assistant_text,
        ),
        drafts=[],
        created_node_ids=[],
        branch_context=selected_branch_context,
        orchestration_plan=plan,
        state_items=self._state_items_for_plan(plan),
    )
```

Use the existing `_render_answer` call arguments exactly as in the reuse branch.

For `reuse_answer`, include `orchestration_plan=plan` and `state_items=[]` in returned `AskResult`.

For existing knowledge-job branch, include:

```python
orchestration_plan=plan,
state_items=[
    AgentStateItem(
        item_id=f"draft-{draft_anchor.anchor_id}",
        kind="knowledge_draft",
        state="writing",
        title=draft_title,
        reason=action.user_visible_reason,
    )
],
```

- [ ] **Step 6: Persist plan and state items in API app ask paths**

In `src/math_im_book/api/app.py`, where `assistant_message = SessionMessage(...)` is created, extend `SessionAssistantContext`:

```python
assistant_context=SessionAssistantContext(
    action_type=result.action.action_type,
    referenced_node_ids=list(result.answer.references),
    anchors=list(result.answer.anchors),
    symbol_conflicts=list(result.answer.symbol_conflicts),
    orchestration_plan=result.orchestration_plan,
    state_items=list(result.state_items),
),
```

Do the same for regenerate path if it creates `SessionAssistantContext` separately.

- [ ] **Step 7: Extend ask response answer/action if needed**

Keep top-level `AskResponseSchema` backward compatible. Do not add a top-level `orchestration_plan` yet unless frontend needs it. The plan is available in `response.session.messages[-1].assistant_context.orchestration_plan`.

- [ ] **Step 8: Run tests**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/services/test_orchestrator.py tests/api/test_sessions_api.py tests/api/test_schemas.py
```

Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add src/math_im_book/domain/models.py src/math_im_book/services/orchestrator.py src/math_im_book/api/app.py tests/services/test_orchestrator.py tests/api/test_sessions_api.py tests/api/test_schemas.py
git commit -m "feat: attach orchestration plans to assistant turns"
```

---

## Task 4: Read-Only Agent State API

**Owner:** Subagent C

**Files:**

- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`
- Test: `tests/api/test_agent_state_api.py`

- [ ] **Step 1: Write failing API test**

Create `tests/api/test_agent_state_api.py`:

```python
from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import (
    AgentStateItem,
    KnowledgeDraftCandidate,
    OrchestrationPlan,
    SessionAssistantContext,
    SessionBranch,
)
from math_im_book.storage.sessions import SessionMessage
from math_im_book.storage.sessions import FileSessionStore, SessionRecord


def test_agent_state_returns_current_turn_and_queue(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Linear Algebra",
            branch_context=SessionBranch(),
            messages=[
                SessionMessage(
                    message_id="msg-a",
                    role="assistant",
                    content="Answer",
                    created_at="2026-04-18T00:00:00Z",
                    assistant_context=SessionAssistantContext(
                        action_type="answer_then_suggest_drafts",
                        orchestration_plan=OrchestrationPlan(
                            route="answer_then_suggest_drafts",
                            intent="broad_overview",
                            persistence_decision="suggest_drafts",
                            confidence=0.78,
                            user_visible_summary="先给概览。",
                            detected_scope_ids=["linear-algebra"],
                            profile_layers_used=["global_user", "scope_memory:linear-algebra"],
                            profile_context_summary="识别为线性代数范围。",
                            candidate_drafts=[
                                KnowledgeDraftCandidate(
                                    title="Vector Space",
                                    draft_type="definition",
                                    reason="Reusable concept.",
                                )
                            ],
                        ),
                        state_items=[
                            AgentStateItem(
                                item_id="draft-vector-space",
                                kind="knowledge_draft",
                                state="suggested",
                                title="Vector Space",
                                reason="Reusable concept.",
                                source_message_id="msg-a",
                            )
                        ],
                    ),
                )
            ],
        )
    )
    client = TestClient(create_app(session_store=session_store))

    response = client.get("/api/agent-state?session_id=chat-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_turn"]["route"] == "answer_then_suggest_drafts"
    assert payload["memory_scope"]["detected_scope_ids"] == ["linear-algebra"]
    assert payload["memory_scope"]["profile_layers_used"][1] == "scope_memory:linear-algebra"
    assert payload["knowledge_queue"][0]["title"] == "Vector Space"
    assert payload["recent_decisions"][0]["message_id"] == "msg-a"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/api/test_agent_state_api.py
```

Expected: 404 because `/api/agent-state` does not exist.

- [ ] **Step 3: Add schemas**

In `src/math_im_book/api/schemas.py`, add:

```python
class AgentTurnStateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message_id: str | None = None
    route: str
    intent: str
    confidence: float
    persistence_decision: str
    user_visible_summary: str
    detected_scope_ids: list[str] = Field(default_factory=list)
    profile_layers_used: list[str] = Field(default_factory=list)
    profile_context_summary: str | None = None
    active_node_ids: list[str] = Field(default_factory=list)
    candidate_drafts: list[KnowledgeDraftCandidateSchema] = Field(default_factory=list)


class KnowledgeQueueItemSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    title: str
    draft_type: str = ""
    state: str
    reason: str = ""
    source_session_id: str | None = None
    source_message_id: str | None = None
    target_parent_id: str | None = None
    node_id: str | None = None
    error_message: str | None = None


class ContextHealthSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_node_count: int = 0
    summary_node_count: int = 0
    pending_draft_count: int = 0
    failed_item_count: int = 0
    symbol_conflict_count: int = 0


class MemoryScopeStateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_scope_ids: list[str] = Field(default_factory=list)
    profile_layers_used: list[str] = Field(default_factory=list)
    profile_context_summary: str | None = None
    has_global_user_profile: bool = False
    has_scope_memory: bool = False


class AgentDecisionSummarySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message_id: str
    route: str
    intent: str
    persistence_decision: str
    result: str


class AgentStateResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_turn: AgentTurnStateSchema | None = None
    knowledge_queue: list[KnowledgeQueueItemSchema] = Field(default_factory=list)
    profile_observations: list[dict[str, object]] = Field(default_factory=list)
    profile_patches: list[dict[str, object]] = Field(default_factory=list)
    memory_scope: MemoryScopeStateSchema = Field(default_factory=MemoryScopeStateSchema)
    context_health: ContextHealthSchema = Field(default_factory=ContextHealthSchema)
    recent_decisions: list[AgentDecisionSummarySchema] = Field(default_factory=list)
```

- [ ] **Step 4: Add API route**

In `src/math_im_book/api/app.py`, add:

```python
@app.get("/api/agent-state", response_model=AgentStateResponseSchema)
def get_agent_state(session_id: str | None = None) -> AgentStateResponseSchema:
    record = sessions.load_record(session_id) if session_id else _latest_session_record(sessions)
    if record is None:
        return AgentStateResponseSchema()
    return _agent_state_for_record(record)
```

Add helper:

```python
def _latest_session_record(sessions: FileSessionStore) -> SessionRecord | None:
    records = sessions.list_recent_records()
    return records[0] if records else None
```

Add `_agent_state_for_record(record)`:

```python
def _agent_state_for_record(record: SessionRecord) -> AgentStateResponseSchema:
    assistant_messages = [
        message for message in record.messages if message.role == "assistant"
    ]
    latest = assistant_messages[-1] if assistant_messages else None
    queue: list[KnowledgeQueueItemSchema] = []
    recent: list[AgentDecisionSummarySchema] = []
    for message in assistant_messages:
        context = message.assistant_context
        for item in context.state_items:
            queue.append(
                KnowledgeQueueItemSchema(
                    item_id=item.item_id,
                    title=item.title,
                    state=item.state,
                    reason=item.reason,
                    source_session_id=record.session_id,
                    source_message_id=item.source_message_id or message.message_id,
                    node_id=item.node_id,
                    error_message=item.error_message,
                )
            )
        if context.orchestration_plan is not None:
            recent.append(
                AgentDecisionSummarySchema(
                    session_id=record.session_id,
                    message_id=message.message_id,
                    route=context.orchestration_plan.route,
                    intent=context.orchestration_plan.intent,
                    persistence_decision=context.orchestration_plan.persistence_decision,
                    result=context.orchestration_plan.user_visible_summary,
                )
            )
    current_turn = None
    if latest is not None and latest.assistant_context.orchestration_plan is not None:
        plan = latest.assistant_context.orchestration_plan
        current_turn = AgentTurnStateSchema(
            session_id=record.session_id,
            message_id=latest.message_id,
            route=plan.route,
            intent=plan.intent,
            confidence=plan.confidence,
            persistence_decision=plan.persistence_decision,
            user_visible_summary=plan.user_visible_summary,
            detected_scope_ids=list(plan.detected_scope_ids),
            profile_layers_used=list(plan.profile_layers_used),
            profile_context_summary=plan.profile_context_summary,
            active_node_ids=list(record.branch_context.active_node_ids),
            candidate_drafts=[
                KnowledgeDraftCandidateSchema(
                    title=draft.title,
                    draft_type=draft.draft_type,
                    reason=draft.reason,
                )
                for draft in plan.candidate_drafts
            ],
        )
    memory_scope = MemoryScopeStateSchema()
    if current_turn is not None:
        memory_scope = MemoryScopeStateSchema(
            detected_scope_ids=list(current_turn.detected_scope_ids),
            profile_layers_used=list(current_turn.profile_layers_used),
            profile_context_summary=current_turn.profile_context_summary,
            has_global_user_profile="global_user" in current_turn.profile_layers_used,
            has_scope_memory=any(layer.startswith("scope_memory:") for layer in current_turn.profile_layers_used),
        )
    return AgentStateResponseSchema(
        current_turn=current_turn,
        knowledge_queue=queue,
        memory_scope=memory_scope,
        context_health=ContextHealthSchema(
            active_node_count=len(record.branch_context.active_node_ids),
            summary_node_count=len(record.branch_context.summary_node_ids),
            pending_draft_count=sum(1 for item in queue if item.state in {"suggested", "writing"}),
            failed_item_count=sum(1 for item in queue if item.state == "failed"),
            symbol_conflict_count=sum(
                len(message.assistant_context.symbol_conflicts)
                for message in assistant_messages[-3:]
            ),
        ),
        recent_decisions=list(reversed(recent[-10:])),
    )
```

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache tests/api/test_agent_state_api.py tests/api/test_sessions_api.py
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/math_im_book/api/schemas.py src/math_im_book/api/app.py tests/api/test_agent_state_api.py
git commit -m "feat: expose read-only agent state"
```

---

## Task 5: Frontend API, Store, And Agent State Page

**Owner:** Subagent D and E can split this task. If split, D owns `services/api.ts` and `stores/workspace.ts`; E owns components and `App.vue`.

**Files:**

- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/components/agent/AgentStatePage.vue`
- Test: `frontend/src/stores/workspace.test.ts`
- Test: `frontend/src/App.test.ts`
- Test: `frontend/src/components/agent/AgentStatePage.test.ts`

- [ ] **Step 1: Write failing store test**

Add to `frontend/src/stores/workspace.test.ts`:

```ts
it('fetches agent state for the current session', async () => {
  vi.mocked(api.getAgentState).mockResolvedValue({
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
      candidate_drafts: [],
    },
    knowledge_queue: [],
    profile_observations: [],
    profile_patches: [],
    memory_scope: {
      detected_scope_ids: ['linear-algebra'],
      profile_layers_used: ['global_user', 'scope_memory:linear-algebra'],
      profile_context_summary: '识别为线性代数范围。',
      has_global_user_profile: true,
      has_scope_memory: true,
    },
    context_health: {
      active_node_count: 0,
      summary_node_count: 0,
      pending_draft_count: 0,
      failed_item_count: 0,
      symbol_conflict_count: 0,
    },
    recent_decisions: [],
  } as any);

  const store = useWorkspaceStore();
  store.currentSession = {
    session_id: 'chat-1',
    branch: { active_node_ids: [], summary_node_ids: [], active_symbols: {} },
    messages: [],
  } as any;

  await store.fetchAgentState();

  expect(api.getAgentState).toHaveBeenCalledWith('chat-1');
  expect(store.agentState?.current_turn?.route).toBe('answer_then_suggest_drafts');
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
cd frontend && npm run test -- workspace.test.ts
```

Expected: fail because `api.getAgentState`, `store.fetchAgentState`, and `store.agentState` do not exist.

- [ ] **Step 3: Add TypeScript API types and method**

In `frontend/src/services/api.ts`, add:

```ts
export interface KnowledgeDraftCandidate {
  title: string;
  draft_type: string;
  reason: string;
}

export interface OrchestrationPlan {
  route: string;
  intent: string;
  persistence_decision: string;
  confidence: number;
  user_visible_summary: string;
  detected_scope_ids: string[];
  profile_layers_used: string[];
  profile_context_summary?: string | null;
  candidate_drafts: KnowledgeDraftCandidate[];
}

export interface AgentStateItem {
  item_id: string;
  kind: string;
  state: string;
  title: string;
  reason: string;
  source_message_id?: string | null;
  node_id?: string | null;
  error_message?: string | null;
}

export interface AgentTurnState {
  session_id: string;
  message_id?: string | null;
  route: string;
  intent: string;
  confidence: number;
  persistence_decision: string;
  user_visible_summary: string;
  detected_scope_ids: string[];
  profile_layers_used: string[];
  profile_context_summary?: string | null;
  active_node_ids: string[];
  candidate_drafts: KnowledgeDraftCandidate[];
}

export interface KnowledgeQueueItem {
  item_id: string;
  title: string;
  draft_type: string;
  state: string;
  reason: string;
  source_session_id?: string | null;
  source_message_id?: string | null;
  target_parent_id?: string | null;
  node_id?: string | null;
  error_message?: string | null;
}

export interface ContextHealth {
  active_node_count: number;
  summary_node_count: number;
  pending_draft_count: number;
  failed_item_count: number;
  symbol_conflict_count: number;
}

export interface MemoryScopeState {
  detected_scope_ids: string[];
  profile_layers_used: string[];
  profile_context_summary?: string | null;
  has_global_user_profile: boolean;
  has_scope_memory: boolean;
}

export interface AgentDecisionSummary {
  session_id: string;
  message_id: string;
  route: string;
  intent: string;
  persistence_decision: string;
  result: string;
}

export interface AgentState {
  current_turn?: AgentTurnState | null;
  knowledge_queue: KnowledgeQueueItem[];
  profile_observations: Array<Record<string, any>>;
  profile_patches: Array<Record<string, any>>;
  memory_scope: MemoryScopeState;
  context_health: ContextHealth;
  recent_decisions: AgentDecisionSummary[];
}
```

Extend `SessionAssistantContext`:

```ts
orchestration_plan?: OrchestrationPlan | null;
state_items?: AgentStateItem[];
```

Add method to `api` object:

```ts
async getAgentState(sessionId?: string): Promise<AgentState> {
  const response = await client.get('/agent-state', {
    params: sessionId ? { session_id: sessionId } : {},
  });
  return response.data;
},
```

- [ ] **Step 4: Add store state and action**

In `frontend/src/stores/workspace.ts`, import `type AgentState` and add:

```ts
const agentState = ref<AgentState | null>(null);
```

Add action:

```ts
async function fetchAgentState(sessionId = currentSession.value?.session_id) {
  try {
    agentState.value = await api.getAgentState(sessionId);
  } catch (error) {
    console.error('Failed to fetch agent state:', error);
  }
}

function openAgentStateForMessage(messageId?: string) {
  activeTab.value = 'agent';
  void fetchAgentState(currentSession.value?.session_id);
}
```

Change `activeTab` type:

```ts
const activeTab = ref<'chat' | 'book' | 'agent'>('chat');
```

Call `await fetchAgentState()` after:

- successful `ask`
- successful `selectSession`
- knowledge job polling updates anchors

Return `agentState`, `fetchAgentState`, and `openAgentStateForMessage` from the store.

- [ ] **Step 5: Run store test**

Run:

```bash
cd frontend && npm run test -- workspace.test.ts
```

Expected: pass.

- [ ] **Step 6: Write AgentStatePage component test**

Create `frontend/src/components/agent/AgentStatePage.test.ts`:

```ts
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import AgentStatePage from './AgentStatePage.vue';
import { useWorkspaceStore } from '../../stores/workspace';

describe('AgentStatePage', () => {
  let pinia: ReturnType<typeof createPinia>;

  beforeEach(() => {
    pinia = createPinia();
    setActivePinia(pinia);
  });

  it('renders current turn, memory scope, knowledge queue, and recent decisions', () => {
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

    const wrapper = mount(AgentStatePage, { global: { plugins: [pinia] } });

    expect(wrapper.text()).toContain('Current Turn');
    expect(wrapper.text()).toContain('answer_then_suggest_drafts');
    expect(wrapper.text()).toContain('Memory Scope');
    expect(wrapper.text()).toContain('linear-algebra');
    expect(wrapper.text()).toContain('Vector Space');
    expect(wrapper.text()).toContain('Recent Decisions');
  });
});
```

- [ ] **Step 7: Run component test and verify failure**

Run:

```bash
cd frontend && npm run test -- AgentStatePage.test.ts
```

Expected: fail because component does not exist.

- [ ] **Step 8: Create `AgentStatePage.vue`**

Create `frontend/src/components/agent/AgentStatePage.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useWorkspaceStore } from '../../stores/workspace';

const store = useWorkspaceStore();
const { agentState } = storeToRefs(store);

const currentTurn = computed(() => agentState.value?.current_turn || null);
const queue = computed(() => agentState.value?.knowledge_queue || []);
const memoryScope = computed(() => agentState.value?.memory_scope || null);
const health = computed(() => agentState.value?.context_health || null);
const recent = computed(() => agentState.value?.recent_decisions || []);

onMounted(() => {
  void store.fetchAgentState();
});
</script>

<template>
  <section class="h-full overflow-y-auto p-10">
    <div class="mx-auto max-w-5xl space-y-8">
      <header>
        <p class="font-sans text-[10px] uppercase tracking-widest text-primary/70">Agent State</p>
        <h2 class="font-serif text-3xl text-on-surface">Accumulation Control</h2>
      </header>

      <section class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
        <h3 class="stitch-label mb-4">Current Turn</h3>
        <div v-if="currentTurn" class="space-y-3">
          <p class="font-sans text-sm text-on-surface-variant">{{ currentTurn.user_visible_summary }}</p>
          <div class="flex flex-wrap gap-2 text-[11px] uppercase tracking-widest">
            <span class="rounded bg-primary-fixed px-3 py-1 text-primary">{{ currentTurn.route }}</span>
            <span class="rounded bg-surface px-3 py-1 text-on-surface-variant">{{ currentTurn.intent }}</span>
            <span class="rounded bg-surface px-3 py-1 text-on-surface-variant">{{ Math.round(currentTurn.confidence * 100) }}%</span>
          </div>
        </div>
        <p v-else class="font-serif italic text-on-surface-variant/70">No current agent turn.</p>
      </section>

      <section class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
        <h3 class="stitch-label mb-4">Knowledge Queue</h3>
        <div v-if="queue.length" class="space-y-3">
          <article v-for="item in queue" :key="item.item_id" class="rounded bg-surface p-4">
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="font-serif text-lg">{{ item.title }}</p>
                <p class="font-sans text-xs text-on-surface-variant">{{ item.reason }}</p>
              </div>
              <span class="rounded bg-primary-fixed px-3 py-1 font-sans text-[10px] uppercase tracking-widest text-primary">{{ item.state }}</span>
            </div>
          </article>
        </div>
        <p v-else class="font-serif italic text-on-surface-variant/70">No knowledge items waiting.</p>
      </section>

      <section class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
        <h3 class="stitch-label mb-4">Memory Scope</h3>
        <div v-if="memoryScope" class="space-y-4">
          <p class="font-serif text-sm text-on-surface-variant">
            {{ memoryScope.profile_context_summary || 'No profile or scope context influenced this turn.' }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="scopeId in memoryScope.detected_scope_ids"
              :key="scopeId"
              class="rounded bg-primary-fixed px-3 py-1 font-sans text-[10px] uppercase tracking-widest text-primary"
            >
              {{ scopeId }}
            </span>
            <span
              v-for="layer in memoryScope.profile_layers_used"
              :key="layer"
              class="rounded bg-surface px-3 py-1 font-sans text-[10px] uppercase tracking-widest text-on-surface-variant"
            >
              {{ layer }}
            </span>
          </div>
        </div>
        <p v-else class="font-serif italic text-on-surface-variant/70">No memory scope metadata recorded.</p>
      </section>

      <section class="grid gap-6 md:grid-cols-2">
        <div class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
          <h3 class="stitch-label mb-4">Context Health</h3>
          <dl v-if="health" class="grid grid-cols-2 gap-3 font-sans text-sm">
            <dt>Active nodes</dt><dd>{{ health.active_node_count }}</dd>
            <dt>Summary nodes</dt><dd>{{ health.summary_node_count }}</dd>
            <dt>Pending drafts</dt><dd>{{ health.pending_draft_count }}</dd>
            <dt>Failed items</dt><dd>{{ health.failed_item_count }}</dd>
            <dt>Symbol conflicts</dt><dd>{{ health.symbol_conflict_count }}</dd>
          </dl>
        </div>

        <div class="rounded-lg border border-outline-variant/20 bg-surface-container-low p-6">
          <h3 class="stitch-label mb-4">Recent Decisions</h3>
          <div v-if="recent.length" class="space-y-3">
            <article v-for="decision in recent" :key="decision.message_id" class="border-l-2 border-primary/40 pl-3">
              <p class="font-sans text-xs uppercase tracking-widest text-primary">{{ decision.route }}</p>
              <p class="font-serif text-sm text-on-surface-variant">{{ decision.result }}</p>
            </article>
          </div>
          <p v-else class="font-serif italic text-on-surface-variant/70">No decisions recorded.</p>
        </div>
      </section>
    </div>
  </section>
</template>
```

- [ ] **Step 9: Wire App navigation**

In `frontend/src/App.vue`, import:

```ts
import AgentStatePage from './components/agent/AgentStatePage.vue'
```

Add side nav button after Library:

```vue
<button 
  @click="activeTab = 'agent'"
  class="flex flex-col items-center gap-1 group transition-all"
  :class="activeTab === 'agent' ? 'text-primary-fixed' : 'text-slate-500 hover:text-slate-300'"
>
  <span class="material-symbols-outlined text-2xl" :style="activeTab === 'agent' ? 'font-variation-settings: \\'FILL\\' 1;' : ''">schema</span>
  <span class="font-sans text-[9px] uppercase tracking-tighter">Agent</span>
</button>
```

In main workspace content, branch rendering:

```vue
<AgentStatePage v-if="activeTab === 'agent'" />
<template v-else>
  <!-- existing chat empty/non-empty content and footer -->
</template>
```

Keep `ReaderPanel` unchanged in the right panel.

- [ ] **Step 10: Connect ChatMessage review event**

In `ChatMessage.vue`, extend emits:

```ts
(e: 'review-state', messageId: string): void
```

Render plan strip:

```vue
<div
  v-if="isAssistant && message.assistant_context.orchestration_plan"
  class="mt-6 rounded-lg border border-outline-variant/20 bg-surface-container-low p-4"
  data-agent-plan-strip
>
  <p class="font-sans text-[10px] uppercase tracking-widest text-primary/70">
    Agent: {{ message.assistant_context.orchestration_plan.route }}
  </p>
  <p class="mt-1 font-serif text-sm text-on-surface-variant">
    {{ message.assistant_context.orchestration_plan.user_visible_summary }}
  </p>
  <p
    v-if="message.assistant_context.orchestration_plan.profile_context_summary"
    class="mt-2 font-sans text-[11px] text-on-surface-variant/80"
  >
    {{ message.assistant_context.orchestration_plan.profile_context_summary }}
  </p>
  <button
    class="mt-3 rounded bg-primary-fixed px-3 py-1 font-sans text-[10px] uppercase tracking-widest text-primary"
    @click="emit('review-state', message.message_id)"
  >
    Review
  </button>
</div>
```

In `App.vue`, pass:

```vue
@review-state="handleReviewState"
```

Add:

```ts
const handleReviewState = (messageId: string) => store.openAgentStateForMessage(messageId)
```

- [ ] **Step 11: Run frontend tests**

Run:

```bash
cd frontend && npm run test
```

Expected: pass.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/stores/workspace.ts frontend/src/App.vue frontend/src/components/chat/ChatMessage.vue frontend/src/components/agent/AgentStatePage.vue frontend/src/stores/workspace.test.ts frontend/src/App.test.ts frontend/src/components/agent/AgentStatePage.test.ts
git commit -m "feat: add agent state workspace"
```

---

## Task 6: Integration Verification And Documentation Update

**Owner:** Subagent F

**Files:**

- Modify: `docs/PROJECT.md`
- Optional Modify: `docs/superpowers/specs/2026-04-18-agent-orchestration-state-panel-design.md`

- [ ] **Step 1: Run backend verification**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend verification**

Run:

```bash
cd frontend && npm run test
```

Expected: all frontend tests pass.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: build succeeds and writes `frontend/dist`.

- [ ] **Step 4: Update project docs**

In `docs/PROJECT.md`, update "Web Workspace" or "current implementation" section with:

```markdown
4. Agent State workspace
   - The Reader remains focused on Markdown knowledge nodes.
   - Agent State shows current orchestration route, memory scope metadata, knowledge queue, context health, and recent agent decisions.
   - Chat cards show a compact plan strip and link to Agent State for review.
```

In current implementation section, add:

```markdown
7. Transparent orchestration plan
   - Assistant turns may include `assistant_context.orchestration_plan`.
   - The Agent State API summarizes the latest plan, memory scope metadata, queue items, context health, and recent decisions.
   - V1 records detected scope ids and profile layers used as audit metadata only; it does not write Scope Memory files.
```

- [ ] **Step 5: Commit docs**

```bash
git add docs/PROJECT.md docs/superpowers/specs/2026-04-18-agent-orchestration-state-panel-design.md
git commit -m "docs: document agent state implementation"
```

- [ ] **Step 6: Final status**

Report:

- Backend tests command and result.
- Frontend tests command and result.
- Frontend build command and result.
- Any skipped items or risks.

---

## Parallelization Guidance

Recommended order:

1. Subagent A completes Task 1 first.
2. Subagent B starts Task 2 after Task 1 dataclasses exist.
3. Task 3 starts after Task 2.
4. Subagent C can start Task 4 after Task 1 and Task 3 message persistence are available.
5. Subagent D can start frontend API/store after Task 4 schemas are stable.
6. Subagent E can start UI component work after Subagent D adds types and store fields.
7. Subagent F runs integration after all code tasks merge.

Possible parallel work:

- Subagent E can create `AgentStatePage.vue` with mocked store data while D works on API/store, as long as E does not edit `services/api.ts` or `stores/workspace.ts`.
- Subagent C can draft tests for `/api/agent-state` while B works on planner, but should wait to implement route until Task 1 persistence lands.

Conflict-prone files:

- `src/math_im_book/domain/models.py`
- `src/math_im_book/api/schemas.py`
- `frontend/src/services/api.ts`
- `frontend/src/stores/workspace.ts`
- `frontend/src/App.vue`

Only one subagent should own each conflict-prone file at a time.

## Acceptance Criteria

The implementation is complete when:

1. Existing sessions still load if they do not have `orchestration_plan`.
2. New assistant turns include `assistant_context.orchestration_plan`.
3. Broad exploratory questions can route to `answer_then_suggest_drafts` without starting a knowledge job.
4. Existing `expand_with_drafts` planner responses still work and still queue knowledge jobs.
5. `/api/agent-state` returns current turn, memory scope metadata, knowledge queue, context health, and recent decisions.
6. Chat cards show a compact agent plan strip when a plan exists.
7. Clicking `Review` opens the dedicated Agent State workspace.
8. Reader remains focused on Markdown knowledge nodes.
9. New plans can carry `detected_scope_ids`, `profile_layers_used`, and `profile_context_summary` without requiring a Scope Memory store.
10. Backend tests pass.
11. Frontend tests pass.
12. Frontend build passes.

## Future Suggestions And Deferred Work

Do not implement these in V1:

- Automatic `USER.md` mutation.
- Profile observation generation.
- Profile patch application.
- Scope Memory storage under `data/memory/scopes/` or `data/memory/projects/`.
- Scope detection backed by a persisted `data/memory/scopes/index.json`.
- Scope-specific learning state updates.
- Cross-subject or cross-project memory retrieval.
- Durable `data/agent_state/knowledge_queue.jsonl`.
- Knowledge queue approve/dismiss/retry actions.
- Full route-specific UI actions.
- Graph visualization.

The V1 goal is transparency and state visibility, not full self-evolution.

Recommended future sequence:

1. Scope Memory V1
   - Add `data/memory/scopes/index.json`.
   - Add Markdown files for subject/project scoped learning state.
   - Implement read-only `ScopeMemoryStore.load_for_question(question)`.
   - Inject only matched scope summaries into planner context.

2. Profile Observation Pipeline
   - Add `ProfileObservation` records after completed turns.
   - Classify each observation destination as `global_user`, `scope_memory`, `knowledge`, or `session_only`.
   - Show observations in Agent State without applying them.

3. Patch Proposal And Approval
   - Generate `ProfilePatchProposal` for `USER.md` and Scope Memory separately.
   - Add approve/reject/defer actions in Agent State.
   - Apply section-level Markdown patches with change history.

4. Auto Low-Risk Evolution
   - Auto-apply low-risk language/format preferences.
   - Keep subject background, mathematical ability, and persistence-policy changes approval-gated.
   - Add rollback for profile and scope-memory changes.

5. Provider Abstraction
   - Introduce a `MemoryProvider` style interface only after file-backed `USER.md` and Scope Memory prove useful.
   - Keep built-in file memory always available.
   - Allow one external profile/memory provider at a time to avoid conflicting context.

6. Knowledge/Memory Boundary Review
   - Add a periodic review that catches misplaced content.
   - Move subject facts from Scope Memory into Knowledge nodes.
   - Move global preferences accidentally written to Scope Memory into `USER.md`.
   - Keep raw session-specific details in chat archive.
