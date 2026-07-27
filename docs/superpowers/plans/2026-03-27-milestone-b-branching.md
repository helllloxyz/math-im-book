# Milestone B Branching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first usable branching and context-control layer so users can fork from a node or answer reference, keep a local focus, and avoid dragging the entire session context into every follow-up question.

**Architecture:** Extend the existing session model with explicit branch metadata and fork context, then add a context selector that computes active nodes and summary-only nodes for each ask. Expose the new branch state through small HTTP endpoints and wire the workspace UI so users can fork from an existing anchor and continue in the new branch without losing the main session.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, pytest, vanilla JS, filesystem-backed JSON/Markdown storage

---

### Task 1: Add Branch Metadata to Session Storage

**Files:**
- Modify: `src/math_im_book/domain/models.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Modify: `src/math_im_book/api/schemas.py`
- Create: `tests/storage/test_sessions_branches.py`
- Modify: `tests/api/test_schemas.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_session_store_round_trips_branch_metadata() -> None:
    ...


def test_session_schema_supports_branch_context() -> None:
    ...


def test_session_store_loads_legacy_records_without_branch_fields() -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/storage/test_sessions_branches.py tests/api/test_schemas.py`
Expected: FAIL because branch metadata types and schema fields do not exist yet

- [ ] **Step 3: Write minimal implementation**

Add branch-aware session types with only the fields Milestone B needs now:
- `branch_id`
- `parent_session_id`
- `root_session_id`
- `forked_from_node_id`
- `forked_from_message_index`
- `focus_question`
- `active_node_ids`
- `summary_node_ids`

Persist them in the existing JSON session store and expose them through API schemas without changing the knowledge-node storage format.
Loading an old session JSON file without the new fields must still succeed and default to an empty branch context.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/storage/test_sessions_branches.py tests/api/test_schemas.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/domain/models.py src/math_im_book/storage/sessions.py src/math_im_book/api/schemas.py tests/storage/test_sessions_branches.py tests/api/test_schemas.py
git commit -m "feat: add branch metadata to sessions"
```

### Task 2: Add Fork API and Session Listing Support

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Create: `tests/api/test_fork_api.py`
- Modify: `tests/api/test_sessions_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_fork_endpoint_creates_child_session_with_branch_context() -> None:
    ...


def test_sessions_list_includes_branch_relationship_fields() -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_fork_api.py tests/api/test_sessions_api.py`
Expected: FAIL because the fork endpoint and branch list fields do not exist yet

- [ ] **Step 3: Write minimal implementation**

Add `POST /api/sessions/{session_id}/fork` that accepts a small fork payload:
- optional `forked_from_node_id`
- optional `forked_from_message_index`
- required `focus_question`

The endpoint should create a new child session that:
- points back to the parent session
- carries a new `branch_id`
- records the fork anchor
- initializes the first branch context snapshot:
  - the local `focus_question`
  - the fork anchor
  - inherited symbol constraints from the anchor node set
  - related node summaries that will be visible before the first follow-up ask
- may start with empty messages, but must not start with empty branch context

Also extend `GET /api/sessions` and `GET /api/sessions/{id}` so the frontend can see branch relationships without loading raw JSON files.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_fork_api.py tests/api/test_sessions_api.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py src/math_im_book/api/schemas.py src/math_im_book/storage/sessions.py tests/api/test_fork_api.py tests/api/test_sessions_api.py
git commit -m "feat: add fork session api"
```

### Task 3: Add Context Selection for Branched Sessions

**Files:**
- Create: `src/math_im_book/services/context_selector.py`
- Modify: `src/math_im_book/storage/markdown.py`
- Create: `tests/services/test_context_selector.py`
- Modify: `tests/storage/test_markdown_repository.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_context_selector_prefers_fork_anchor_and_related_nodes() -> None:
    ...


def test_context_selector_demotes_unrelated_nodes_to_summary_scope() -> None:
    ...


def test_context_selector_uses_fixed_tiebreak_order_and_one_hop_reference_depth() -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/services/test_context_selector.py tests/storage/test_markdown_repository.py`
Expected: FAIL because no branch-aware context selection service exists

- [ ] **Step 3: Write minimal implementation**

Implement a deterministic selector that:
- starts from the fork anchor node when present
- expands one hop through direct references and incoming references
- adds strong lexical matches from the current question
- returns two buckets: `active_node_ids` and `summary_node_ids`

Keep the first version small and deterministic; do not add embeddings or vector search.
Pin the behavior with a fixed test graph and exact expected node IDs, including ordering and tie-breaks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/services/test_context_selector.py tests/storage/test_markdown_repository.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/services/context_selector.py src/math_im_book/storage/markdown.py tests/services/test_context_selector.py tests/storage/test_markdown_repository.py
git commit -m "feat: add branch context selector"
```

### Task 4: Make `/api/ask` Branch-Aware

**Files:**
- Modify: `src/math_im_book/services/orchestrator.py`
- Modify: `src/math_im_book/services/planner.py`
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/api/schemas.py`
- Create: `tests/services/test_orchestrator_branching.py`
- Modify: `tests/api/test_routes.py`
- Modify: `tests/api/test_provider_integration.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_orchestrator_uses_branch_context_to_limit_selected_nodes() -> None:
    ...


def test_ask_endpoint_returns_branch_context_and_focus_metadata() -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/services/test_orchestrator_branching.py tests/api/test_routes.py tests/api/test_provider_integration.py`
Expected: FAIL because ask responses do not yet include or honor branch context

- [ ] **Step 3: Write minimal implementation**

Before planning an answer:
- load the current session branch metadata
- compute branch context through the context selector
- restrict strong reuse decisions to active nodes
- allow summary-only nodes to influence the answer without becoming full active context

Return the computed branch context in the ask/session response so the frontend can surface the current local focus.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/services/test_orchestrator_branching.py tests/api/test_routes.py tests/api/test_provider_integration.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/services/orchestrator.py src/math_im_book/services/planner.py src/math_im_book/api/app.py src/math_im_book/api/schemas.py tests/services/test_orchestrator_branching.py tests/api/test_routes.py tests/api/test_provider_integration.py
git commit -m "feat: make ask branch aware"
```

### Task 5: Expose Forking in the Workspace UI

**Files:**
- Modify: `src/math_im_book/api/static/app.js`
- Modify: `src/math_im_book/api/static/app.css`
- Modify: `src/math_im_book/api/app.py`
- Create: `tests/api/test_frontend_branching.py`
- Modify: `tests/api/test_frontend_workspace_links.py`
- Modify: `tests/api/test_frontend_sessions_panel.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_frontend_page_exposes_fork_controls_and_branch_panels() -> None:
    ...


def test_frontend_static_js_contains_fork_flow_hooks() -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_frontend_branching.py tests/api/test_frontend_workspace_links.py tests/api/test_frontend_sessions_panel.py`
Expected: FAIL because the workspace has no fork UI yet

- [ ] **Step 3: Write minimal implementation**

Add the smallest usable branching UI:
- a fork action on node detail and answer references
- a branch focus panel showing current `focus_question`
- recent sessions list grouped visually by parent/child relationship
- a load flow that swaps the active session to the new branch immediately after fork

Do not introduce a JS build tool; stay in the existing static-file setup.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_frontend_branching.py tests/api/test_frontend_workspace_links.py tests/api/test_frontend_sessions_panel.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/static/app.js src/math_im_book/api/static/app.css src/math_im_book/api/app.py tests/api/test_frontend_branching.py tests/api/test_frontend_workspace_links.py tests/api/test_frontend_sessions_panel.py
git commit -m "feat: add fork controls to workspace"
```

### Task 6: Document and Verify the Milestone B Slice

**Files:**
- Modify: `README.md`
- Create: `tests/api/test_branching_examples.py`

- [ ] **Step 1: Write the failing test**

```python
def test_branching_example_flow_is_supported() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/api/test_branching_examples.py`
Expected: FAIL because the documented branch flow is not yet covered

- [ ] **Step 3: Write minimal implementation**

Document one end-to-end branching flow in the README:
1. ask in a main session
2. fork from a node
3. continue in the child session
4. inspect the branch context

Add the acceptance-style test for the same flow.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_branching_examples.py`
Expected: PASS

- [ ] **Step 5: Run full verification**

Run: `.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add README.md tests/api/test_branching_examples.py
git commit -m "docs: describe milestone b branch flow"
```
