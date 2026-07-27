# Chat Session Storage Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-file session payload model with a directory-based storage model that separates immutable committed history from the mutable working turn and uses immutable fork anchors instead of copied history.

**Architecture:** Store each session under its own directory with `session.json`, `messages.jsonl`, and `working_turn.json`, plus a global `sessions_index.json` for listing. Update domain models, storage, and API schemas together so the system exposes `branch`, stable `message_id` anchors, and visible inherited history without any backward-compatibility layer.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, pytest, file-backed JSON/JSONL storage

---

## File Map

- Modify: `src/math_im_book/domain/models.py`
  Add the new session, branch, message, fork-anchor, and working-turn model shapes.
- Modify: `src/math_im_book/api/schemas.py`
  Replace `branch_context` with `branch`, add `message_id` and `created_at`, and replace index-based fork inputs with anchor-based fields.
- Modify: `src/math_im_book/storage/sessions.py`
  Rebuild the store around session directories, visible-history reconstruction, immutable committed messages, mutable working-turn persistence, and the global session index.
- Modify: `src/math_im_book/api/app.py`
  Update session read/write/fork flows to use the new store and new schema shape.
- Modify: `tests/storage/test_sessions.py`
  Cover directory creation, committed message append, and session metadata persistence.
- Modify: `tests/storage/test_sessions_branches.py`
  Cover parent/child branch persistence and visible-history reconstruction.
- Modify: `tests/storage/test_sessions_context.py`
  Cover assistant context persistence in committed message lines.
- Modify: `tests/storage/test_sessions_metadata.py`
  Cover session list index reads and metadata updates.
- Modify: `tests/api/test_schemas.py`
  Cover the new request/response schema contracts.
- Modify: `tests/api/test_fork_api.py`
  Cover message-id and node-anchor fork semantics and rejection of mutable-tail anchors.
- Modify: `tests/api/test_sessions_api.py`
  Cover visible-history reads and updated session payload shape.
- Modify: `tests/api/test_routes.py`
  Cover the new ask flow if it now stages through a mutable working turn before commit.

### Task 1: Replace Session Domain Shapes

**Files:**
- Modify: `src/math_im_book/domain/models.py`
- Test: `tests/api/test_schemas.py`

- [ ] **Step 1: Write the failing schema-level tests for the new domain-backed fields**

```python
def test_session_schema_uses_branch_and_message_ids() -> None:
    session = SessionSchema(
        session_id="chat-1",
        branch={"parent_session_id": None, "root_session_id": "chat-1"},
        messages=[
            {
                "message_id": "msg_0001",
                "role": "user",
                "content": "What is a linear map?",
                "created_at": "2026-04-02T09:00:00Z",
            }
        ],
    )

    dumped = session.model_dump()
    assert "branch" in dumped
    assert "branch_context" not in dumped
    assert dumped["messages"][0]["message_id"] == "msg_0001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/api/test_schemas.py -k "branch and message_ids"`
Expected: FAIL because the current schema still uses `branch_context` and message payloads do not require `message_id`.

- [ ] **Step 3: Update the domain models with the new storage concepts**

Implement focused dataclasses for:

```python
@dataclass(slots=True)
class SessionForkAnchor:
    type: str
    message_id: str | None = None
    node_id: str | None = None
    source_message_id: str | None = None


@dataclass(slots=True)
class SessionBranch:
    branch_id: str | None = None
    parent_session_id: str | None = None
    root_session_id: str | None = None
    focus_question: str | None = None
    fork_anchor: SessionForkAnchor | None = None
    active_node_ids: list[str] = field(default_factory=list)
    summary_node_ids: list[str] = field(default_factory=list)
    active_symbols: dict[str, str] = field(default_factory=dict)
```

Also add durable message-level identifiers and timestamps to the session message shape used in storage/API conversion.

- [ ] **Step 4: Run schema tests to verify the model changes support the new shape**

Run: `.venv/bin/pytest -q tests/api/test_schemas.py`
Expected: PASS for the updated branch and message fields, with unrelated failures still possible until later tasks land.

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/domain/models.py tests/api/test_schemas.py
git commit -m "feat: add new chat session domain models"
```

### Task 2: Replace API Schemas With The New Contracts

**Files:**
- Modify: `src/math_im_book/api/schemas.py`
- Test: `tests/api/test_schemas.py`

- [ ] **Step 1: Write the failing schema tests for fork-anchor requests**

```python
def test_fork_request_schema_accepts_message_anchor() -> None:
    payload = SessionForkRequestSchema(
        focus_question="Why?",
        fork_anchor={"type": "message", "message_id": "msg_0008"},
    )
    assert payload.fork_anchor.message_id == "msg_0008"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/api/test_schemas.py -k "fork_request_schema_accepts_message_anchor"`
Expected: FAIL because the current request schema still expects `forked_from_node_id` or `forked_from_message_index`.

- [ ] **Step 3: Implement the new request/response schema layer**

Update `src/math_im_book/api/schemas.py` to:

- expose `branch` instead of `branch_context`
- require `message_id` and `created_at` on session messages
- add a `SessionForkAnchorSchema`
- change `SessionForkRequestSchema` to accept `fork_anchor`
- remove old index-based fork validation

- [ ] **Step 4: Run the schema tests**

Run: `.venv/bin/pytest -q tests/api/test_schemas.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/schemas.py tests/api/test_schemas.py
git commit -m "feat: replace session api schemas with anchor-based contracts"
```

### Task 3: Rebuild Session Storage Around Directories

**Files:**
- Modify: `src/math_im_book/storage/sessions.py`
- Test: `tests/storage/test_sessions.py`
- Test: `tests/storage/test_sessions_context.py`
- Test: `tests/storage/test_sessions_metadata.py`

- [ ] **Step 1: Write the failing storage tests for the new on-disk shape**

```python
def test_save_record_creates_session_directory_and_metadata_files(tmp_path) -> None:
    store = FileSessionStore(tmp_path / "sessions")

    store.create_session(
        session_id="chat-1",
        title="Linear Maps",
        branch=SessionBranch(root_session_id="chat-1"),
    )

    session_dir = tmp_path / "sessions" / "chat-1"
    assert (session_dir / "session.json").exists()
    assert (session_dir / "messages.jsonl").exists()
    assert not (session_dir / "working_turn.json").exists()
```

- [ ] **Step 2: Run the targeted storage tests to verify they fail**

Run: `.venv/bin/pytest -q tests/storage/test_sessions.py tests/storage/test_sessions_context.py tests/storage/test_sessions_metadata.py`
Expected: FAIL because the current store still reads and writes one JSON file per session.

- [ ] **Step 3: Implement the directory-based store**

Add focused methods for:

- creating a session directory
- reading and writing `session.json`
- appending committed messages to `messages.jsonl`
- reading committed local messages
- reading and writing `working_turn.json`
- updating and reading `sessions_index.json`

Keep file responsibilities separate rather than reusing the old monolithic read/write path.

- [ ] **Step 4: Add helper methods for visible-history reconstruction**

Implement methods such as:

```python
def load_visible_messages(self, session_id: str) -> list[SessionMessage]: ...
def append_committed_turn(self, session_id: str, messages: list[SessionMessage]) -> None: ...
def save_working_turn(self, session_id: str, working_turn: SessionWorkingTurn | None) -> None: ...
```

- [ ] **Step 5: Run the storage tests**

Run: `.venv/bin/pytest -q tests/storage/test_sessions.py tests/storage/test_sessions_branches.py tests/storage/test_sessions_context.py tests/storage/test_sessions_metadata.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/math_im_book/storage/sessions.py tests/storage/test_sessions.py tests/storage/test_sessions_branches.py tests/storage/test_sessions_context.py tests/storage/test_sessions_metadata.py
git commit -m "feat: redesign file-backed chat session storage"
```

### Task 4: Implement Immutable Fork Anchors And Visible History

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Test: `tests/api/test_fork_api.py`
- Test: `tests/storage/test_sessions_branches.py`

- [ ] **Step 1: Write the failing fork tests for stable anchors**

```python
def test_fork_endpoint_creates_child_session_with_message_anchor(tmp_path) -> None:
    response = client.post(
        "/api/sessions/chat-root/fork",
        json={
            "focus_question": "Why?",
            "fork_anchor": {"type": "message", "message_id": "msg_0008"},
        },
    )

    assert response.status_code == 200
    assert response.json()["branch"]["fork_anchor"]["message_id"] == "msg_0008"
```

```python
def test_fork_endpoint_rejects_anchor_from_working_turn(tmp_path) -> None:
    response = client.post(
        "/api/sessions/chat-root/fork",
        json={
            "focus_question": "Why?",
            "fork_anchor": {"type": "message", "message_id": "draft_user_01"},
        },
    )

    assert response.status_code == 409
```

- [ ] **Step 2: Run the fork tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_fork_api.py tests/storage/test_sessions_branches.py`
Expected: FAIL because the current fork flow still uses node ids or message indexes and has no working-turn distinction.

- [ ] **Step 3: Replace `_fork_branch_context` with anchor-based logic**

Implement:

- lookup by committed `message_id`
- lookup by committed node anchor plus `source_message_id`
- parent-history cutoff based on immutable committed history only
- rejection when the target belongs to `working_turn`

- [ ] **Step 4: Run the fork and branch-history tests**

Run: `.venv/bin/pytest -q tests/api/test_fork_api.py tests/storage/test_sessions_branches.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py src/math_im_book/storage/sessions.py tests/api/test_fork_api.py tests/storage/test_sessions_branches.py
git commit -m "feat: add immutable fork anchors and visible history"
```

### Task 5: Route Ask Flow Through The Mutable Working Turn

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Test: `tests/api/test_routes.py`
- Test: `tests/api/test_sessions_api.py`

- [ ] **Step 1: Write the failing ask-flow tests**

```python
def test_ask_endpoint_commits_turn_and_returns_visible_history(tmp_path) -> None:
    response = client.post(
        "/api/ask",
        json={"question": "What is a linear map?", "session_id": "chat-ctx"},
    )

    assert response.status_code == 200
    session = response.json()["session"]
    assert session["messages"][-2]["role"] == "user"
    assert session["messages"][-1]["role"] == "assistant"
    assert session["messages"][-1]["message_id"]
```

- [ ] **Step 2: Run the targeted API tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_routes.py tests/api/test_sessions_api.py`
Expected: FAIL until the new storage-backed ask flow and session response shaping are implemented.

- [ ] **Step 3: Update the ask route and session detail route**

Implement this sequence:

1. create or load the session metadata
2. write the new user message to `working_turn`
3. get the provider answer into `working_turn`
4. commit the turn to `messages.jsonl`
5. clear `working_turn`
6. return the full visible-history session payload

- [ ] **Step 4: Run the targeted API tests**

Run: `.venv/bin/pytest -q tests/api/test_routes.py tests/api/test_sessions_api.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py src/math_im_book/storage/sessions.py tests/api/test_routes.py tests/api/test_sessions_api.py
git commit -m "feat: route session writes through mutable working turns"
```

### Task 6: Update Session Listing And Tree Metadata

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/storage/sessions.py`
- Test: `tests/storage/test_sessions_metadata.py`
- Test: `tests/api/test_sessions_api.py`

- [ ] **Step 1: Write the failing list-session tests**

```python
def test_list_sessions_reads_from_index_and_exposes_branch_tree_fields(tmp_path) -> None:
    response = client.get("/api/sessions")

    assert response.status_code == 200
    session = response.json()["sessions"][0]
    assert "branch" in session
    assert "branch_context" not in session
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `.venv/bin/pytest -q tests/storage/test_sessions_metadata.py tests/api/test_sessions_api.py -k "list_sessions"`
Expected: FAIL because the current implementation still scans per-session JSON files and returns the old branch field name.

- [ ] **Step 3: Implement index-backed session listing**

Update the storage and API layers so `GET /api/sessions` reads the global index, then enriches tree metadata only as needed for the response shape.

- [ ] **Step 4: Run the targeted tests**

Run: `.venv/bin/pytest -q tests/storage/test_sessions_metadata.py tests/api/test_sessions_api.py -k "list_sessions"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py src/math_im_book/storage/sessions.py tests/storage/test_sessions_metadata.py tests/api/test_sessions_api.py
git commit -m "feat: add index-backed session listing"
```

### Task 7: Run Full Verification

**Files:**
- Modify: none expected
- Test: `tests/storage/test_sessions.py`
- Test: `tests/storage/test_sessions_branches.py`
- Test: `tests/storage/test_sessions_context.py`
- Test: `tests/storage/test_sessions_metadata.py`
- Test: `tests/api/test_schemas.py`
- Test: `tests/api/test_fork_api.py`
- Test: `tests/api/test_sessions_api.py`
- Test: `tests/api/test_routes.py`

- [ ] **Step 1: Run the focused regression suite**

Run: `.venv/bin/pytest -q tests/storage/test_sessions.py tests/storage/test_sessions_branches.py tests/storage/test_sessions_context.py tests/storage/test_sessions_metadata.py tests/api/test_schemas.py tests/api/test_fork_api.py tests/api/test_sessions_api.py tests/api/test_routes.py`
Expected: PASS

- [ ] **Step 2: Run the broader backend suite**

Run: `.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache`
Expected: PASS

- [ ] **Step 3: Commit verification-only follow-up if needed**

```bash
git add <any-updated-test-files>
git commit -m "test: stabilize chat session storage redesign"
```
