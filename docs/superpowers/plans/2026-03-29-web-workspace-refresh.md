# Web Workspace Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the existing FastAPI workspace into a conversation-led writing workspace with branch-first navigation, read-only Markdown accumulation on the right, and a simplified answer action model.

**Architecture:** Reuse the existing single-page FastAPI + vanilla JS workspace rather than introducing a new frontend stack. Keep the existing branching/session APIs, add only the minimum node-preview metadata needed for the right rail, then rebuild the page shell and JS rendering so the center conversation is primary, the right rail is a reader, and the left rail is a quiet locator.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, pytest, vanilla JS, static CSS, filesystem-backed Markdown/JSON storage

---

## File Map

### Existing files to reuse

- `src/math_im_book/api/app.py`
  Owns the HTML shell, FastAPI routes, and node/session response shaping.
- `src/math_im_book/api/static/app.js`
  Owns all client-side rendering and event handling for the workspace.
- `src/math_im_book/api/static/app.css`
  Owns all workspace layout and panel styling.
- `src/math_im_book/api/schemas.py`
  Owns API response contracts for outline, node detail, and sessions.
- `src/math_im_book/storage/markdown.py`
  Owns filesystem-backed node loading and any repository helpers needed by the workspace.

### New or updated test coverage

- `tests/api/test_frontend_page.py`
  Update the core shell expectations to match the new workspace.
- `tests/api/test_frontend_panels.py`
  Replace symbol/compact-first expectations with the new three-zone panel structure.
- `tests/api/test_frontend_branching.py`
  Keep branch support, but assert it appears in the left rail and answer actions instead of in a primary branch-focus card.
- `tests/api/test_frontend_workspace_links.py`
  Move reference navigation expectations from a standalone references panel to inline answer links and right-rail preview behavior.
- `tests/api/test_frontend_node_panel.py`
  Reframe node detail checks around the right-rail reader and related-info area.
- `tests/api/test_frontend_sessions_panel.py`
  Keep recent session tree checks, but assert it is the dominant left-top navigator.
- `tests/api/test_nodes_api.py`
  Create focused API coverage for right-rail node preview metadata.
- `tests/storage/test_markdown_repository.py`
  Extend repository coverage for any related-chat aggregation helpers used by the UI.

### Optional support docs to update near the end

- `README.md`
  Update only if the workspace usage flow changes enough that the current README becomes misleading.

## Scope Notes

- This plan keeps the current `single static page + static JS/CSS` setup.
- This plan does **not** introduce a JS build step, React, or a Markdown editor.
- This plan does **not** make `/compact` a primary UI flow.
- This plan does **not** remove backend branching support; it only demotes non-MVP panels from first-class screen real estate.

## Task Order

### Task 1: Replace the HTML shell with the new three-zone workspace

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `tests/api/test_frontend_page.py`
- Modify: `tests/api/test_frontend_panels.py`
- Create: `tests/api/test_frontend_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_frontend_page_uses_three_zone_workspace_shell() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert 'id="workspace-left-rail"' in response.text
    assert 'id="workspace-center-column"' in response.text
    assert 'id="workspace-right-rail"' in response.text
    assert 'id="book-outline-panel"' in response.text
    assert 'id="markdown-preview-panel"' in response.text


def test_frontend_page_removes_answer_textarea_and_primary_compact_button() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert 'id="answer-text"' not in response.text
    assert 'id="compact-command-action"' not in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_frontend_page.py tests/api/test_frontend_panels.py tests/api/test_frontend_layout.py`
Expected: FAIL because the page still renders the old two-card shell with answer textarea, compact button, and symbol-heavy primary panels

- [ ] **Step 3: Write minimal implementation**

Update `_frontend_page()` in `src/math_im_book/api/app.py` to render:

- a top global bar
- `workspace-left-rail`
- `workspace-center-column`
- `workspace-right-rail`

Inside those columns:

- left top: `recent-sessions-panel`
- left bottom: `book-outline-panel`
- center: branch header, conversation list, composer
- right top: `markdown-preview-panel`
- right bottom: `related-context-panel`

Keep IDs stable and explicit; the JS tasks later will target these containers directly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_frontend_page.py tests/api/test_frontend_panels.py tests/api/test_frontend_layout.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py tests/api/test_frontend_page.py tests/api/test_frontend_panels.py tests/api/test_frontend_layout.py
git commit -m "feat: add three-zone workspace shell"
```

### Task 2: Add right-rail node preview metadata for reading and related chats

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/storage/markdown.py`
- Modify: `tests/storage/test_markdown_repository.py`
- Create: `tests/api/test_nodes_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_node_detail_api_includes_related_session_ids_for_workspace_reader(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path)
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves addition and scalar multiplication.",
            detail="# Linear Map\n\nReader-facing detail.",
            parent_id="linear-algebra",
            source="chat:session-1",
        )
    )
    repository.save_node(
        KnowledgeNode(
            id="kernel",
            title="Kernel",
            type="atomic",
            summary="The vectors mapped to zero.",
            detail="Kernel detail.",
            parent_id="linear-algebra",
            source="chat:session-2",
            references=[NodeReference(node_id="linear-map", reason="Builds on linear maps.")],
        )
    )

    client = TestClient(create_app(repository=repository))
    response = client.get("/api/nodes/linear-map")

    assert response.status_code == 200
    assert response.json()["node"]["related_session_ids"] == ["chat:session-1", "chat:session-2"]


def test_repository_lists_related_session_ids_from_node_and_incoming_refs(tmp_path) -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_nodes_api.py tests/storage/test_markdown_repository.py`
Expected: FAIL because node responses and repository helpers do not expose related session IDs yet

- [ ] **Step 3: Write minimal implementation**

Add a repository helper that aggregates stable related session IDs from:

- the selected node's `source`
- direct references
- incoming references

Expose the result through `GET /api/nodes/{node_id}` as `related_session_ids`.

Do not redesign the knowledge model yet. For MVP, a deterministic aggregation helper is enough to make the many-to-many relationship visible in the reader.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_nodes_api.py tests/storage/test_markdown_repository.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py src/math_im_book/api/schemas.py src/math_im_book/storage/markdown.py tests/storage/test_markdown_repository.py tests/api/test_nodes_api.py
git commit -m "feat: expose reader node metadata"
```

### Task 3: Rebuild the left rail around branch tree first and outline second

**Files:**
- Modify: `src/math_im_book/api/static/app.js`
- Modify: `src/math_im_book/api/static/app.css`
- Modify: `tests/api/test_frontend_sessions_panel.py`
- Modify: `tests/api/test_frontend_branching.py`
- Create: `tests/api/test_frontend_left_rail.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_frontend_left_rail_prioritizes_recent_session_tree_above_book_outline() -> None:
    client = TestClient(create_app())

    html = client.get("/").text
    script = client.get("/static/app.js").text

    assert 'id="recent-sessions-panel"' in html
    assert 'id="book-outline-panel"' in html
    assert "renderRecentSessions" in script
    assert "renderBookOutline" in script
    assert "recent-session-tree" in script


def test_frontend_keeps_branch_focus_in_header_not_primary_panel() -> None:
    client = TestClient(create_app())

    html = client.get("/").text

    assert 'id="branch-focus-panel"' not in html
    assert 'id="conversation-branch-header"' in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_frontend_sessions_panel.py tests/api/test_frontend_branching.py tests/api/test_frontend_left_rail.py`
Expected: FAIL because the current page still uses a separate branch-focus panel and the outline IDs/layout do not match the new left-rail design

- [ ] **Step 3: Write minimal implementation**

In `src/math_im_book/api/static/app.js`:

- rename `renderOutline` to `renderBookOutline`
- keep the existing session tree builder, but render it into the left-top rail
- move branch focus rendering into a center-column header area

In `src/math_im_book/api/static/app.css`:

- define left-rail layout with two stacked regions
- give the session tree the stronger visual weight
- keep the outline visually quieter

Do not change the session APIs in this task.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_frontend_sessions_panel.py tests/api/test_frontend_branching.py tests/api/test_frontend_left_rail.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/static/app.js src/math_im_book/api/static/app.css tests/api/test_frontend_sessions_panel.py tests/api/test_frontend_branching.py tests/api/test_frontend_left_rail.py
git commit -m "feat: prioritize branch tree in left rail"
```

### Task 4: Replace answer textarea and standalone references panel with conversation cards

**Files:**
- Modify: `src/math_im_book/api/static/app.js`
- Modify: `src/math_im_book/api/static/app.css`
- Modify: `tests/api/test_frontend_workspace_links.py`
- Create: `tests/api/test_frontend_answer_cards.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_frontend_renders_answer_cards_with_inline_reference_links_and_actions() -> None:
    client = TestClient(create_app())

    script = client.get("/static/app.js").text

    assert "renderConversationMessages" in script
    assert "renderAnswerCardActions" in script
    assert "Copy" in script
    assert "Regenerate" in script
    assert "reference-link" in script


def test_frontend_drops_standalone_answer_references_panel() -> None:
    client = TestClient(create_app())

    html = client.get("/").text

    assert 'id="answer-references-panel"' not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_frontend_workspace_links.py tests/api/test_frontend_answer_cards.py`
Expected: FAIL because the current workspace still uses `answer-references-panel` and a separate answer textarea flow

- [ ] **Step 3: Write minimal implementation**

Replace the current answer rendering with a conversation-card renderer that:

- renders user and assistant messages in the center timeline
- appends inline clickable reference links inside assistant cards
- exposes only `Fork`, `Copy`, and `Regenerate` as answer actions

Implementation constraints:

- `Fork` keeps using the existing fork endpoint
- `Copy` uses the browser clipboard API with a safe fallback
- `Regenerate` resubmits the latest user prompt in the current session

Do not add markdown-it or a new rendering library. Keep the first pass deterministic and string-based.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_frontend_workspace_links.py tests/api/test_frontend_answer_cards.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/static/app.js src/math_im_book/api/static/app.css tests/api/test_frontend_workspace_links.py tests/api/test_frontend_answer_cards.py
git commit -m "feat: render conversation answer cards"
```

### Task 5: Turn the right rail into a read-only Markdown reader

**Files:**
- Modify: `src/math_im_book/api/static/app.js`
- Modify: `src/math_im_book/api/static/app.css`
- Modify: `tests/api/test_frontend_node_panel.py`
- Create: `tests/api/test_frontend_reader_panel.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_frontend_right_rail_renders_markdown_preview_and_related_chats() -> None:
    client = TestClient(create_app())

    html = client.get("/").text
    script = client.get("/static/app.js").text

    assert 'id="markdown-preview-panel"' in html
    assert 'id="related-context-panel"' in html
    assert "renderMarkdownPreview" in script
    assert "renderRelatedChats" in script


def test_outline_and_reference_navigation_only_update_reader_context() -> None:
    client = TestClient(create_app())

    script = client.get("/static/app.js").text

    assert "loadReaderNode(" in script
    assert "currentReaderNodeId" in script
    assert "currentSessionId" in script
    assert "center conversation stays stable" not in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_frontend_node_panel.py tests/api/test_frontend_reader_panel.py`
Expected: FAIL because the current right-side UI is still a node-detail inspector rather than a Markdown reader with related chats

- [ ] **Step 3: Write minimal implementation**

Add reader-state rendering in `src/math_im_book/api/static/app.js`:

- `loadReaderNode(nodeId)`
- `renderMarkdownPreview(node)`
- `renderRelatedChats(node.related_session_ids || [])`

Behavioral rules:

- clicking an outline node updates the reader state only
- clicking an inline answer reference updates the reader state only
- clicking a related chat in the right rail is the only thing that should switch sessions intentionally

In `src/math_im_book/api/static/app.css`, make the right rail feel like a reading surface:

- readable line length
- strong heading hierarchy
- quieter metadata section

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_frontend_node_panel.py tests/api/test_frontend_reader_panel.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/static/app.js src/math_im_book/api/static/app.css tests/api/test_frontend_node_panel.py tests/api/test_frontend_reader_panel.py
git commit -m "feat: add markdown reader rail"
```

### Task 6: Demote non-MVP symbol and compact surfaces out of the primary workspace

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/api/static/app.js`
- Modify: `src/math_im_book/api/static/app.css`
- Modify: `tests/api/test_frontend_panels.py`
- Modify: `tests/api/test_frontend_page.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_frontend_primary_workspace_excludes_symbol_and_compact_panels() -> None:
    client = TestClient(create_app())

    html = client.get("/").text

    assert 'id="symbols-panel"' not in html
    assert 'id="symbol-conflicts-panel"' not in html
    assert 'id="compact-notes-panel"' not in html
    assert 'id="compact-summary-panel"' not in html


def test_frontend_static_js_no_longer_requires_compact_first_render_path() -> None:
    client = TestClient(create_app())

    script = client.get("/static/app.js").text

    assert "runCompactCommand" not in script
    assert 'question.startsWith("/compact")' not in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_frontend_panels.py tests/api/test_frontend_page.py`
Expected: FAIL because the current shell and JS still surface symbol and compact panels as first-class UI

- [ ] **Step 3: Write minimal implementation**

Remove symbol and compact UI from the primary shell and JS initialization path.

Important boundary:

- keep the backend APIs intact
- keep branch/session behavior intact
- do not delete reusable utility code unless it becomes dead and unreferenced

The point of this task is UI demotion, not backend removal.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -q tests/api/test_frontend_panels.py tests/api/test_frontend_page.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py src/math_im_book/api/static/app.js src/math_im_book/api/static/app.css tests/api/test_frontend_panels.py tests/api/test_frontend_page.py
git commit -m "refactor: demote non-mvp workspace panels"
```

### Task 7: Verify the refreshed workspace end-to-end and document the new flow

**Files:**
- Modify: `README.md`
- Create: `tests/api/test_frontend_workspace_flow.py`

- [ ] **Step 1: Write the failing test**

```python
def test_workspace_flow_supports_branch_first_navigation_and_reader_context() -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/api/test_frontend_workspace_flow.py`
Expected: FAIL because the new user-facing flow is not documented and not yet fully pinned by an acceptance-style test

- [ ] **Step 3: Write minimal implementation**

Document the updated workspace flow in `README.md`:

1. ask in the center conversation
2. fork from an answer when needed
3. browse chapter/node accumulation on the right
4. use the left rail to switch branches or inspect chapter placement
5. only switch sessions intentionally from the branch tree or related-chat links

Add one acceptance-style frontend test that asserts the HTML and JS expose the hooks needed for that flow.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -q tests/api/test_frontend_workspace_flow.py`
Expected: PASS

- [ ] **Step 5: Run focused verification**

Run: `.venv/bin/pytest -q tests/api/test_frontend_page.py tests/api/test_frontend_panels.py tests/api/test_frontend_branching.py tests/api/test_frontend_workspace_links.py tests/api/test_frontend_node_panel.py tests/api/test_frontend_sessions_panel.py tests/api/test_frontend_layout.py tests/api/test_frontend_left_rail.py tests/api/test_frontend_answer_cards.py tests/api/test_frontend_reader_panel.py tests/api/test_frontend_workspace_flow.py tests/api/test_nodes_api.py tests/storage/test_markdown_repository.py`
Expected: PASS

- [ ] **Step 6: Run full verification**

Run: `.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add README.md tests/api/test_frontend_workspace_flow.py
git commit -m "docs: describe refreshed web workspace"
```
