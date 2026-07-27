# Strategy Agent Prompting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add session-level strategy agents with a cache-friendly prompt compiler while keeping per-question answer styles as optional lightweight overrides.

**Architecture:** Introduce a new file-backed `strategy_agents` configuration layer and a dedicated `AnswerPromptCompiler` that assembles `base contract + strategy agent + context + question + optional answer style override`. Store `strategy_agent_id` in session metadata, default new sessions to `top-down`, and keep per-question `answer_style_id` optional and local to each ask/regenerate request.

**Tech Stack:** FastAPI, Pydantic, file-backed JSON/Markdown config, pytest, Vue 3, Pinia, Vitest

---

### Task 1: Add Strategy Agent Domain Models And Config Loaders

**Files:**
- Create: `data/config/strategy_agents/index.json`
- Create: `data/config/strategy_agents/top-down.md`
- Create: `data/config/strategy_agents/raw.md`
- Create: `src/math_im_book/storage/strategy_agents.py`
- Modify: `src/math_im_book/domain/models.py`
- Test: `tests/api/test_schemas.py`

- [ ] **Step 1: Write the failing schema test for strategy-agent response models**

Add assertions in `tests/api/test_schemas.py` that validate a response payload shaped like:

```python
payload = {
    "default_agent_id": "top-down",
    "agents": [
        {
            "strategy_agent_id": "top-down",
            "label": "Top Down",
            "description": "Overview-first teaching guidance.",
            "instructions": "# Top Down\n...",
            "is_default": True,
        },
        {
            "strategy_agent_id": "raw",
            "label": "Raw",
            "description": "Minimal guidance.",
            "instructions": "# Raw\n...",
            "is_default": False,
        },
    ],
}
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_schemas.py -v -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: FAIL because `StrategyAgentSchema` and `StrategyAgentsResponseSchema` do not exist yet.

- [ ] **Step 3: Add the new domain models**

Modify `src/math_im_book/domain/models.py` to add:

```python
@dataclass(slots=True)
class StrategyAgent:
    agent_id: str
    label: str
    instructions: str
    description: str | None = None
    is_default: bool = False


@dataclass(slots=True)
class StrategyAgentCatalog:
    default_agent_id: str = "top-down"
    agents: list[StrategyAgent] = field(default_factory=list)

    def get(self, agent_id: str) -> StrategyAgent:
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        raise KeyError(agent_id)
```

- [ ] **Step 4: Add strategy-agent config files**

Create `data/config/strategy_agents/index.json` with:

```json
{
  "default_agent_id": "top-down",
  "agents": [
    {
      "agent_id": "top-down",
      "label": "Top Down",
      "description": "Overview-first teaching guidance."
    },
    {
      "agent_id": "raw",
      "label": "Raw",
      "description": "Minimal built-in guidance."
    }
  ]
}
```

Create `data/config/strategy_agents/top-down.md` and `data/config/strategy_agents/raw.md` in English. The top-down file should include the stable conversation protocol. The raw file should stay minimal.

- [ ] **Step 5: Add the file-backed strategy-agent repository**

Create `src/math_im_book/storage/strategy_agents.py` following the same repository shape as `src/math_im_book/storage/answer_styles.py`:

- load `index.json`
- read one Markdown file per agent id
- return defaults if files are missing or invalid
- expose `load()` and `get(agent_id)`

- [ ] **Step 6: Add API schema models for strategy agents**

Modify `src/math_im_book/api/schemas.py` to add:

```python
class StrategyAgentSchema(BaseModel):
    strategy_agent_id: str
    label: str
    description: str | None = None
    instructions: str
    is_default: bool = False


class StrategyAgentsResponseSchema(BaseModel):
    default_agent_id: str = "top-down"
    agents: list[StrategyAgentSchema] = Field(default_factory=list)
```

- [ ] **Step 7: Re-run the schema test**

Run: `.venv/bin/pytest tests/api/test_schemas.py -v -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add data/config/strategy_agents src/math_im_book/domain/models.py src/math_im_book/storage/strategy_agents.py src/math_im_book/api/schemas.py tests/api/test_schemas.py
git commit -m "feat: add strategy agent prompt config"
```

### Task 2: Add Prompt Compiler And Update Orchestrator Prompt Assembly

**Files:**
- Create: `src/math_im_book/services/prompt_compiler.py`
- Modify: `src/math_im_book/services/orchestrator.py`
- Modify: `src/math_im_book/storage/answer_styles.py`
- Test: `tests/services/test_orchestrator.py`

- [ ] **Step 1: Write the failing orchestrator tests**

Add tests in `tests/services/test_orchestrator.py` for:

1. default strategy uses the `top-down` stable prefix
2. `raw` omits top-down-only guidance
3. optional `answer_style_id="concise"` adds a short late override instead of replacing the prefix
4. base contract instructs the model to answer in the user's language

Use assertions shaped like:

```python
assert "Respond in the user's language" in request.system_instruction
assert "Start with a short overview" in top_down_request.system_instruction
assert "Start with a short overview" not in raw_request.system_instruction
assert concise_request.system_instruction.startswith(default_request.system_instruction)
assert "For this question, answer in a more concise style." in concise_request.system_instruction
```

- [ ] **Step 2: Run the orchestrator test file to verify failure**

Run: `.venv/bin/pytest tests/services/test_orchestrator.py -v -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: FAIL because there is no compiler and no strategy-agent-aware prompt assembly.

- [ ] **Step 3: Narrow answer-style responsibility**

Modify `src/math_im_book/storage/answer_styles.py` so the default catalog represents lightweight per-question overrides only.

Changes:

- remove `default` from the catalog
- keep `concise`, `step-by-step`, `intuitive`, and `rigorous`
- update default catalog metadata so `default_style_id` is empty or `None`-equivalent in repository logic
- keep Markdown bodies short and English-only

Do not make answer styles carry the main teaching strategy anymore.

- [ ] **Step 4: Create the prompt compiler**

Create `src/math_im_book/services/prompt_compiler.py` with a focused class, for example:

```python
class AnswerPromptCompiler:
    def compile(
        self,
        *,
        strategy_agent: StrategyAgent,
        answer_style: AnswerStyle | None,
        context: str,
        question: str,
    ) -> str:
        ...
```

Implementation rules:

- keep the base contract in English
- include a line that says to answer in the user's language unless they request otherwise
- put base contract and strategy agent before context and question
- append the per-question style override only when `answer_style` is not `None`
- use fixed headings or separators

- [ ] **Step 5: Rewire the orchestrator**

Modify `src/math_im_book/services/orchestrator.py` to:

- accept a `strategy_agent_repository`
- instantiate and use `AnswerPromptCompiler`
- fetch the active session strategy agent or default to `top-down`
- append per-question answer style only when provided
- remove the current `_answer_style_system_instruction()` logic

- [ ] **Step 6: Re-run the orchestrator tests**

Run: `.venv/bin/pytest tests/services/test_orchestrator.py -v -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/math_im_book/services/prompt_compiler.py src/math_im_book/services/orchestrator.py src/math_im_book/storage/answer_styles.py tests/services/test_orchestrator.py
git commit -m "feat: add strategy agent prompt compiler"
```

### Task 3: Persist Strategy Agents In Sessions And Expose Them Through The API

**Files:**
- Modify: `src/math_im_book/domain/models.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`
- Test: `tests/storage/test_sessions.py`
- Test: `tests/storage/test_sessions_metadata.py`
- Test: `tests/api/test_sessions_api.py`

- [ ] **Step 1: Write the failing session storage test**

Extend `tests/storage/test_sessions.py` to assert:

```python
record = SessionRecord(
    session_id="chat-1",
    strategy_agent_id="top-down",
    default_answer_style_id=None,
    ...
)
...
assert loaded.strategy_agent_id == "top-down"
assert loaded.default_answer_style_id is None
```

- [ ] **Step 2: Write the failing API tests**

Extend `tests/api/test_sessions_api.py` to assert:

1. `GET /api/strategy-agents` returns `top-down` and `raw`
2. `GET /api/sessions/{id}` returns `strategy_agent_id`
3. new sessions default to `top-down`
4. session payloads return `default_answer_style_id` as `null` when unset

- [ ] **Step 3: Run the targeted backend tests and confirm failures**

Run:

```bash
.venv/bin/pytest tests/storage/test_sessions.py tests/storage/test_sessions_metadata.py tests/api/test_sessions_api.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: FAIL because session models and API schemas do not expose the new fields yet.

- [ ] **Step 4: Add strategy-agent fields to the session models**

Modify `src/math_im_book/domain/models.py` so `ChatSession` includes:

```python
strategy_agent_id: str = "top-down"
default_answer_style_id: str | None = None
```

Update any related record dataclasses in `src/math_im_book/storage/sessions.py` to match.

- [ ] **Step 5: Update session persistence**

Modify `src/math_im_book/storage/sessions.py` so session JSON read/write includes:

- `strategy_agent_id`
- nullable `default_answer_style_id`

Rules:

- default missing `strategy_agent_id` to `top-down`
- default missing `default_answer_style_id` to `None`
- do not inject per-question styles into stored message content

- [ ] **Step 6: Add API schema fields**

Modify `src/math_im_book/api/schemas.py`:

- add `strategy_agent_id` to `SessionSchema` and `SessionListItemSchema`
- change `default_answer_style_id` from required string `"default"` to `str | None = None`
- add strategy-agent response models if not already added in Task 1

- [ ] **Step 7: Expose the strategy-agent endpoint and wire session defaults**

Modify `src/math_im_book/api/app.py` to:

- instantiate `FileStrategyAgentRepository(Path("data/config/strategy_agents"))`
- add `GET /api/strategy-agents`
- pass the repository into `KnowledgeOrchestrator`
- ensure new sessions default to `strategy_agent_id="top-down"`

- [ ] **Step 8: Re-run the targeted backend tests**

Run:

```bash
.venv/bin/pytest tests/storage/test_sessions.py tests/storage/test_sessions_metadata.py tests/api/test_sessions_api.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/math_im_book/domain/models.py src/math_im_book/storage/sessions.py src/math_im_book/api/schemas.py src/math_im_book/api/app.py tests/storage/test_sessions.py tests/storage/test_sessions_metadata.py tests/api/test_sessions_api.py
git commit -m "feat: persist session strategy agents"
```

### Task 4: Wire Strategy Agents And Optional Answer Styles Through The Frontend

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Modify: `frontend/src/stores/workspace.test.ts`
- Modify: `frontend/src/components/chat/ChatComposer.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`

- [ ] **Step 1: Write the failing frontend store tests**

Add tests in `frontend/src/stores/workspace.test.ts` for:

1. `fetchStrategyAgents()` loads `top-down` and `raw`
2. `newSession()` defaults to `top-down`
3. ask requests omit `answer_style_id` when no style is selected
4. ask requests include the style id when the user explicitly selects one

Use expectations shaped like:

```ts
expect(store.selectedStrategyAgentId).toBe('top-down')
expect(api.askStream).toHaveBeenCalledWith(
  'Explain the proof.',
  'chat-1',
  expect.any(Object),
  undefined,
  expect.any(Object)
)
```

- [ ] **Step 2: Run the frontend store test to verify failure**

Run: `cd frontend && npm run test -- src/stores/workspace.test.ts`

Expected: FAIL because strategy-agent state and nullable answer-style behavior do not exist yet.

- [ ] **Step 3: Add API client support**

Modify `frontend/src/services/api.ts` to:

- add strategy-agent types
- add `getStrategyAgents()`
- update session types to include `strategy_agent_id`
- make `default_answer_style_id` nullable
- keep `ask()` and `askStream()` style arguments optional

- [ ] **Step 4: Add workspace store state and fetchers**

Modify `frontend/src/stores/workspace.ts` to:

- store `strategyAgents`
- store `selectedStrategyAgentId`
- load strategy agents on startup
- default new sessions to `top-down`
- keep `selectedAnswerStyleId` empty by default
- only pass `answer_style_id` when the user selected one

- [ ] **Step 5: Update the composer UI**

Modify `frontend/src/components/chat/ChatComposer.vue` so:

- answer style selection remains optional
- no style is preselected
- the selector reflects the lighter override semantics

If the new-session strategy selection is rendered somewhere else in the app, wire `top-down` as the preselected option there.

- [ ] **Step 6: Load strategy agents during app startup**

Modify `frontend/src/App.vue` so the initial data-loading path also calls:

```ts
store.fetchStrategyAgents()
```

Keep the startup sequence consistent with the existing provider/style/session fetches.

- [ ] **Step 7: Update frontend tests affected by session shape**

Modify `frontend/src/App.test.ts` and any related snapshots/assertions so session fixtures include:

- `strategy_agent_id`
- nullable `default_answer_style_id`

- [ ] **Step 8: Re-run the targeted frontend tests**

Run:

```bash
cd frontend && npm run test -- src/stores/workspace.test.ts src/App.test.ts
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/stores/workspace.ts frontend/src/stores/workspace.test.ts frontend/src/components/chat/ChatComposer.vue frontend/src/App.vue frontend/src/App.test.ts
git commit -m "feat: add strategy agent session controls"
```

### Task 5: Full Verification And Cleanup

**Files:**
- Verify modified files only

- [ ] **Step 1: Run the targeted backend suite**

Run:

```bash
.venv/bin/pytest tests/api/test_schemas.py tests/storage/test_sessions.py tests/storage/test_sessions_metadata.py tests/api/test_sessions_api.py tests/services/test_orchestrator.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS.

- [ ] **Step 2: Run the targeted frontend suite**

Run:

```bash
cd frontend && npm run test -- src/stores/workspace.test.ts src/App.test.ts
```

Expected: PASS.

- [ ] **Step 3: Inspect the final prompt behavior manually**

Verify in code and tests:

- `top-down` builds a stable session prefix
- `raw` does not include top-down guidance
- base contract instructs the assistant to answer in the user's language
- per-question style override is appended late
- user message content remains unchanged in session storage

- [ ] **Step 4: Review changed files**

Run:

```bash
git diff --stat
git diff -- src/math_im_book frontend/src tests data/config/strategy_agents
```

Expected: only the planned files changed.

- [ ] **Step 5: Commit final polish if needed**

```bash
git add .
git commit -m "test: finalize strategy agent prompting coverage"
```

- [ ] **Step 6: Summarize residual risks**

Document any remaining risks, especially:

- prompt-cache behavior is inferred from stable-prefix structure, not directly measured
- old answer-style fixtures may need cleanup if hidden assumptions remain
- UX around choosing strategy agent at session creation may need one manual pass after implementation
