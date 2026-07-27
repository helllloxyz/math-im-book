# Reader References Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw `node_id` and truncated `sessionId` rows in the Reader's `References & Context` section with compact, collapsible navigation groups backed by display-ready API data.

**Architecture:** Extend the node API to return display-ready reference and discussion objects while preserving existing fields for compatibility. Keep the Reader content-first by localizing the new navigation behavior inside `NodeReferences.vue` and a small group component, with deterministic ordering and fallback logic enforced by backend tests and frontend component tests.

**Tech Stack:** FastAPI, Pydantic, file-backed session/knowledge storage, Vue 3, Pinia, TypeScript, Vitest, pytest

---

## File Structure

**Backend**
- Modify: `src/math_im_book/api/schemas.py`
  - Add display-oriented schema types for node references and related discussions.
- Modify: `src/math_im_book/api/app.py`
  - Build display-ready node response payloads and discussion previews.
- Test: `tests/api/test_schemas.py`
  - Lock the new schema shape.
- Test: `tests/api/test_nodes_api.py`
  - Verify the node endpoint returns enriched reference/discussion data with correct fallbacks and ordering.

**Frontend**
- Modify: `frontend/src/services/api.ts`
  - Add TS types for the enriched node response.
- Create: `frontend/src/components/reader/ReferenceGroup.vue`
  - Own preview-size and `Show all` / `Show less` behavior for one group.
- Modify: `frontend/src/components/reader/NodeReferences.vue`
  - Render three groups from display-ready data using compact cards.
- Test: `frontend/src/components/reader/NodeReferences.test.ts`
  - Cover preview mode, expansion, fallback labels, and click behavior.
- Test: `tests/api/test_frontend_reader_panel.py`
  - Preserve coarse Reader shell expectations and extend only if meaningful bundle copy changes.

## Task 1: Extend API and Type Contracts

**Files:**
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `frontend/src/services/api.ts`
- Test: `tests/api/test_schemas.py`

- [ ] **Step 1: Write the failing schema test**

```python
def test_node_response_schema_supports_display_ready_reference_fields() -> None:
    node_response = NodeResponseSchema(
        node={
            "id": "linear-map",
            "title": "Linear Map",
            "type": "atomic",
            "summary": "A linear map preserves addition and scalar multiplication.",
            "detail": "A map T: V -> W is linear when ...",
            "source": "chat:1",
            "references": [{"node_id": "vector-space", "reason": "Uses vector spaces."}],
            "incoming_references": [],
            "related_session_ids": ["chat-1"],
            "references_display": [
                {
                    "node_id": "vector-space",
                    "title": "Vector Space",
                    "summary": "Defines the ambient space.",
                    "reason": "Uses vector spaces.",
                    "type": "atomic",
                    "status": "ready",
                }
            ],
            "incoming_references_display": [],
            "related_discussions": [
                {
                    "session_id": "chat-1",
                    "title": "Linear algebra warmup",
                    "preview": "Why is scalar multiplication required?",
                    "message_count": 4,
                    "focus_question": "What makes a map linear?",
                }
            ],
            "status": "ready",
            "symbols": {},
            "symbol_scopes": {},
        }
    )

    assert node_response.model_dump()["node"]["references_display"][0]["title"] == "Vector Space"
    assert node_response.model_dump()["node"]["related_discussions"][0]["message_count"] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/api/test_schemas.py -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: FAIL because `KnowledgeNodeSchema` does not yet accept `references_display`, `incoming_references_display`, or `related_discussions`.

- [ ] **Step 3: Write minimal backend and frontend contract changes**

```python
class DisplayNodeReferenceSchema(BaseModel):
    node_id: str
    title: str | None = None
    summary: str | None = None
    reason: str | None = None
    type: str | None = None
    status: str | None = None


class RelatedDiscussionSchema(BaseModel):
    session_id: str
    title: str | None = None
    preview: str | None = None
    message_count: int | None = None
    focus_question: str | None = None


class KnowledgeNodeSchema(BaseModel):
    ...
    references: list[NodeReferenceSchema] = Field(default_factory=list)
    incoming_references: list[NodeReferenceSchema] = Field(default_factory=list)
    related_session_ids: list[str] = Field(default_factory=list)
    references_display: list[DisplayNodeReferenceSchema] = Field(default_factory=list)
    incoming_references_display: list[DisplayNodeReferenceSchema] = Field(default_factory=list)
    related_discussions: list[RelatedDiscussionSchema] = Field(default_factory=list)
```

```ts
export interface DisplayNodeReference {
  node_id: string;
  title?: string;
  summary?: string;
  reason?: string;
  type?: string;
  status?: string;
}

export interface RelatedDiscussion {
  session_id: string;
  title?: string;
  preview?: string;
  message_count?: number;
  focus_question?: string;
}

export interface KnowledgeNode {
  // existing fields omitted for brevity in the plan
  references: NodeReference[];
  incoming_references: NodeReference[];
  related_session_ids: string[];
  references_display: DisplayNodeReference[];
  incoming_references_display: DisplayNodeReference[];
  related_discussions: RelatedDiscussion[];
}
```

- [ ] **Step 4: Run schema test to verify it passes**

Run: `.venv/bin/pytest -q tests/api/test_schemas.py -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/schemas.py frontend/src/services/api.ts tests/api/test_schemas.py
git commit -m "feat: add reader reference display schemas"
```

## Task 2: Build Display-Ready Node API Data

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Test: `tests/api/test_nodes_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_get_node_returns_display_ready_reference_entries(tmp_path: Path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    app = create_app(repository=repository, session_store=session_store)
    client = TestClient(app)
    seed_reader_reference_fixture(repository, session_store)

    response = client.get("/api/nodes/linear-map")

    assert response.status_code == 200
    payload = response.json()["node"]
    assert payload["references_display"][0]["title"] == "Vector Space"
    assert payload["incoming_references_display"][0]["title"] == "Linear Operator"


def test_get_node_returns_related_discussion_titles_previews_and_counts(tmp_path: Path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    app = create_app(repository=repository, session_store=session_store)
    client = TestClient(app)
    seed_reader_reference_fixture(repository, session_store)

    response = client.get("/api/nodes/linear-map")

    discussion = response.json()["node"]["related_discussions"][0]
    assert discussion["title"] == "Linear algebra warmup"
    assert discussion["preview"] == "Why is scalar multiplication required?"
    assert discussion["message_count"] == 4


def test_get_node_discussion_title_falls_back_to_focus_question_then_session_id(tmp_path: Path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    app = create_app(repository=repository, session_store=session_store)
    client = TestClient(app)
    seed_reader_reference_fixture(repository, session_store, include_untitled_session=True)

    discussions = client.get("/api/nodes/linear-map").json()["node"]["related_discussions"]
    assert discussions[1]["title"] == "How should linearity be stated?"


def test_get_node_discussion_title_falls_back_to_session_id_when_no_title_or_focus_question(tmp_path: Path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    app = create_app(repository=repository, session_store=session_store)
    client = TestClient(app)
    seed_reader_reference_fixture(repository, session_store, include_id_only_session=True)

    discussions = client.get("/api/nodes/linear-map").json()["node"]["related_discussions"]
    assert discussions[2]["title"] == "chat-id-only"


def test_get_node_preserves_reference_order_and_tolerates_missing_targets(tmp_path: Path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    app = create_app(repository=repository, session_store=session_store)
    client = TestClient(app)
    seed_reader_reference_fixture(repository, session_store)

    response = client.get("/api/nodes/linear-map")

    payload = response.json()["node"]
    assert [entry["node_id"] for entry in payload["references_display"]] == [
        "vector-space",
        "missing-node",
        "basis",
    ]
    assert payload["references_display"][1]["title"] is None
    assert payload["related_discussions"][0]["session_id"] == "chat-1"


def test_get_node_tolerates_missing_related_session_records(tmp_path: Path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    app = create_app(repository=repository, session_store=session_store)
    client = TestClient(app)
    seed_reader_reference_fixture(repository, session_store, include_missing_session_reference=True)

    response = client.get("/api/nodes/linear-map")
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/api/test_nodes_api.py -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: FAIL because the node endpoint does not yet include display-ready arrays.

- [ ] **Step 3: Implement minimal node enrichment helpers**

```python
def _build_display_node_reference(node_id: str, reason: str, repository: MarkdownKnowledgeRepository) -> dict[str, str | None]:
    try:
        target = repository.get_node(node_id)
    except FileNotFoundError:
        return {"node_id": node_id, "title": None, "summary": None, "reason": reason, "type": None, "status": None}
    return {
        "node_id": node_id,
        "title": target.title,
        "summary": target.summary,
        "reason": reason,
        "type": target.type,
        "status": target.status,
    }


def _discussion_preview(messages: list[SessionMessage]) -> str | None:
    for message in reversed(messages):
        text = " ".join(message.content.split())
        if text:
            return text[:100]
    return None
```

Implementation notes:
- Preserve existing `references`, `incoming_references`, and `related_session_ids`.
- Preserve backend source ordering exactly as specified in the design.
- For related discussions, load each session record, use `record.title`, fall back to `record.branch_context.focus_question`, and derive `message_count` from visible messages.
- If a referenced node or session is missing, omit only the unavailable display fields rather than failing the endpoint.
- Keep backend tests self-contained by creating temporary markdown knowledge files and session records under `tmp_path`, including:
  - one current node
  - two valid referenced nodes
  - one missing referenced node id
  - one valid related session
  - one untitled related session with `focus_question`
  - one related session with neither title nor `focus_question`, to force the `session_id` fallback
  - one missing related session id that still appears in the node's related-session list
- Add the enriched fields directly onto the frontend `KnowledgeNode` type so `api.getNode()` and `store.currentNode` stay strongly typed without casts.
- Mirror the existing API test pattern in files like `tests/api/test_sessions_api.py`: construct `MarkdownKnowledgeRepository(tmp_path / "knowledge")`, `FileSessionStore(tmp_path / "sessions")`, then pass them into `create_app(...)`.
- Define `seed_reader_reference_fixture(...)` in `tests/api/test_nodes_api.py` unless it becomes large enough to justify extraction. The helper should:
  - write the current node plus referenced nodes into `tmp_path / "knowledge"`
  - create session records in `tmp_path / "sessions"`
  - support flags for `include_untitled_session`, `include_id_only_session`, and `include_missing_session_reference`

- [ ] **Step 4: Run focused backend tests**

Run: `.venv/bin/pytest -q tests/api/test_nodes_api.py tests/api/test_schemas.py -o cache_dir=/tmp/math-im-book-pytest-cache`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/math_im_book/api/app.py tests/api/test_nodes_api.py tests/api/test_schemas.py
git commit -m "feat: enrich reader node payloads"
```

## Task 3: Add Collapsible Reader Reference Groups

**Files:**
- Create: `frontend/src/components/reader/ReferenceGroup.vue`
- Modify: `frontend/src/components/reader/NodeReferences.vue`
- Test: `frontend/src/components/reader/NodeReferences.test.ts`

- [ ] **Step 1: Write the failing frontend component tests**

```ts
it('shows only the first three items until expanded', () => {
  // mount NodeReferences with 4 dependencies
  expect(screen.getAllByRole('button', { name: /vector/i })).toHaveLength(1);
  expect(screen.getByRole('button', { name: /show all/i })).toBeInTheDocument();
});

it('renders discussion titles instead of truncated session ids', () => {
  expect(screen.getByText('Linear algebra warmup')).toBeInTheDocument();
  expect(screen.queryByText(/Session chat-1/i)).not.toBeInTheDocument();
});

it('renders node card titles and summaries instead of raw node ids when display data exists', () => {
  expect(screen.getByText('Vector Space')).toBeInTheDocument();
  expect(screen.getByText('Defines the ambient space.')).toBeInTheDocument();
  expect(screen.queryByText(/^vector-space$/i)).not.toBeInTheDocument();
});

it('calls the correct store action when a discussion card is clicked', async () => {
  await user.click(screen.getByRole('button', { name: /linear algebra warmup/i }));
  expect(selectSession).toHaveBeenCalledWith('chat-1');
});

it('calls the correct store action when a node card is clicked', async () => {
  await user.click(screen.getByRole('button', { name: /vector space/i }));
  expect(selectNode).toHaveBeenCalledWith('vector-space');
});

it('uses preview before focus question before message count for discussion secondary text', () => {
  expect(screen.getByText('Why is scalar multiplication required?')).toBeInTheDocument();
  expect(screen.getByText('How should linearity be stated?')).toBeInTheDocument();
  expect(screen.getByText('2 messages')).toBeInTheDocument();
});

it('resets expanded groups when the selected node changes', async () => {
  await user.click(screen.getByRole('button', { name: /show all/i }));
  await rerenderWithDifferentNode();
  expect(screen.queryByRole('button', { name: /show less/i })).not.toBeInTheDocument();
});

it('returns to preview mode after clicking show less', async () => {
  await user.click(screen.getByRole('button', { name: /show all/i }));
  await user.click(screen.getByRole('button', { name: /show less/i }));
  expect(screen.queryByRole('button', { name: /show less/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/components/reader/NodeReferences.test.ts`

Expected: FAIL because `NodeReferences.vue` still renders raw IDs and has no preview/expand behavior.

- [ ] **Step 3: Implement the minimal Reader component split**

```vue
<!-- ReferenceGroup.vue -->
<script setup lang="ts">
const props = defineProps<{
  title: string;
  items: Array<{ id: string }>;
  previewCount?: number;
}>();
const expanded = ref(false);
const visibleItems = computed(() => expanded.value ? props.items : props.items.slice(0, 3));
</script>
```

```vue
<!-- NodeReferences.vue -->
<ReferenceGroup
  title="Dependencies"
  :items="dependencyItems"
>
  <template #default="{ item }">
    <button @click="store.selectNode(item.node_id)">
      {{ item.title || item.node_id }}
    </button>
  </template>
</ReferenceGroup>
```

Implementation notes:
- Keep `References & Context` below the symbol registry.
- Render only non-empty groups.
- Use fixed preview size `3`.
- Reset each group's expanded state when the selected node changes.
- Make the reset deterministic by keying each `ReferenceGroup` by the current node id or by explicitly watching node id changes and resetting local `expanded` state.
- `ReferenceGroup.vue` contract:
  - props: `title`, `items`, optional `previewCount`
  - slot payload: `{ item }` for rendering each visible card row
  - internal responsibility: preview slicing plus `Show all` / `Show less`
  - parent responsibility: map raw API data into `items` with stable `id`
- Card text priority must match the spec:
  - node title: `title -> node_id`
  - node secondary text: `summary -> reason -> omitted`
  - discussion title: `title -> focus_question -> session_id`
  - discussion secondary text: `preview -> focus_question when not used as title -> "N messages" -> omitted`

- [ ] **Step 4: Run focused frontend tests**

Run: `cd frontend && npm run test -- src/components/reader/NodeReferences.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/reader/ReferenceGroup.vue frontend/src/components/reader/NodeReferences.vue frontend/src/components/reader/NodeReferences.test.ts
git commit -m "feat: add reader reference navigation groups"
```

## Task 4: Regression and End-to-End Verification

**Files:**
- Modify: `tests/api/test_frontend_reader_panel.py`
- Optionally Modify: `frontend/src/components/reader/NodeReferences.test.ts`

- [ ] **Step 1: Add any minimal regression assertions needed for bundled Reader copy**

```python
def test_frontend_bundle_keeps_reader_reference_navigation_labels() -> None:
    client = TestClient(create_app())

    _, _, _, script = fetch_frontend_bundle(client)

    assert "Related Discussions" in script
    assert "Show all" in script
```

- [ ] **Step 2: Run the regression test to verify current failure mode**
- [ ] **Step 2: Run source-backed tests before rebuilding the frontend**

Run:

```bash
cd frontend && npm run test -- src/components/reader/NodeReferences.test.ts
cd /mnt/d/gitee/math-im-book && .venv/bin/pytest -q tests/api/test_schemas.py tests/api/test_nodes_api.py -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS for source-backed tests; bundle-backed Reader assertions are intentionally deferred until after rebuild.

- [ ] **Step 3: Run production build for bundle-backed API tests**

Run: `cd frontend && npm run build`

Expected: PASS and emit updated assets to `frontend/dist`

- [ ] **Step 4: Re-run bundle-backed regression tests**

Run:

```bash
cd /mnt/d/gitee/math-im-book && .venv/bin/pytest -q tests/api/test_frontend_reader_panel.py -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/dist tests/api/test_frontend_reader_panel.py
git commit -m "test: verify reader navigation rendering"
```

## Execution Notes
- Do not implement Search / Print / Share.
- Do not add config for preview size; keep `3` fixed in this iteration.
- Do not persist per-group expansion state across node changes.
- Prefer backend enrichment over frontend fan-out; only use cached fallback data if a blocker appears.
- If `NodeReferences.vue` stays readable after the group extraction, do not split further.
