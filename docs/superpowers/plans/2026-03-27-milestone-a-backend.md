# Milestone A Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal Python backend that can store markdown knowledge nodes, route a question into reuse or expansion mode, persist new knowledge, and expose the result through a small HTTP API.

**Architecture:** Use a small FastAPI app with a service layer and filesystem-backed repositories. Knowledge nodes and pending drafts live as Markdown files with YAML front matter; chat sessions live as JSON. The planner emits a stable `AgentAction`, the orchestrator turns it into an answer payload, and successful expansion writes new nodes back to the knowledge store for future reuse.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, pytest, PyYAML

---

### Task 1: Bootstrap Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `src/math_im_book/__init__.py`
- Create: `src/math_im_book/api/__init__.py`
- Create: `src/math_im_book/domain/__init__.py`
- Create: `src/math_im_book/services/__init__.py`
- Create: `src/math_im_book/storage/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from math_im_book.api.app import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL because `math_im_book.api.app` does not exist yet

- [ ] **Step 3: Write minimal implementation**

Create `src/math_im_book/api/app.py` with a `create_app()` factory and `/health` route.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS

### Task 2: Implement Knowledge Node Storage

**Files:**
- Create: `src/math_im_book/domain/models.py`
- Create: `src/math_im_book/storage/markdown.py`
- Create: `tests/storage/test_markdown_repository.py`
- Create: `data/knowledge/.gitkeep`

- [ ] **Step 1: Write the failing test**

```python
def test_repository_round_trips_markdown_knowledge_node(tmp_path):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/storage/test_markdown_repository.py -v`
Expected: FAIL because repository code is missing

- [ ] **Step 3: Write minimal implementation**

Implement `KnowledgeNode`, `NodeReference`, and `MarkdownKnowledgeRepository` that saves and loads Markdown files with YAML front matter.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/storage/test_markdown_repository.py -v`
Expected: PASS

### Task 3: Implement Routing Contract and Planner

**Files:**
- Create: `src/math_im_book/services/planner.py`
- Create: `tests/services/test_planner.py`
- Create: `tests/fixtures/query_cases.md`

- [ ] **Step 1: Write the failing test**

```python
def test_planner_returns_reuse_action_when_summary_matches_query():
    ...


def test_planner_returns_expand_action_when_definition_is_missing():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_planner.py -v`
Expected: FAIL because planner does not exist

- [ ] **Step 3: Write minimal implementation**

Implement `AgentAction`, `PendingDraftRequest`, and `QuestionPlanner`. Use a deterministic keyword overlap heuristic for the first version.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_planner.py -v`
Expected: PASS

### Task 4: Implement Answer Assembly and Ingestion

**Files:**
- Create: `src/math_im_book/services/orchestrator.py`
- Create: `tests/services/test_orchestrator.py`
- Create: `data/chats/.gitkeep`
- Create: `data/drafts/.gitkeep`

- [ ] **Step 1: Write the failing test**

```python
def test_orchestrator_reuses_existing_nodes_in_answer():
    ...


def test_orchestrator_generates_drafts_and_persists_new_node():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_orchestrator.py -v`
Expected: FAIL because orchestrator and persistence flow are missing

- [ ] **Step 3: Write minimal implementation**

Implement answer payloads using `summary + detail + hyperlink`, generate pending drafts for missing definition / bridge / detail, and persist a synthesized knowledge node after expansion.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_orchestrator.py -v`
Expected: PASS

### Task 5: Expose Minimal API Surface

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Create: `src/math_im_book/api/schemas.py`
- Create: `tests/api/test_routes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_ask_endpoint_returns_reuse_or_expand_payload():
    ...


def test_outline_endpoint_lists_knowledge_nodes():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_routes.py -v`
Expected: FAIL because the routes do not exist

- [ ] **Step 3: Write minimal implementation**

Add `POST /api/ask`, `GET /api/outline`, and `GET /api/nodes/{node_id}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_routes.py -v`
Expected: PASS

### Task 6: Add Fixtures, Docs, and Full Verification

**Files:**
- Create: `data/knowledge/examples/linear_map.md`
- Create: `data/knowledge/examples/vector_space.md`
- Create: `README.md`
- Modify: `tests/conftest.py`
- Create: `tests/test_examples.py`

- [ ] **Step 1: Write the failing test**

```python
def test_example_knowledge_files_are_loadable():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_examples.py -v`
Expected: FAIL because fixtures or loader wiring are incomplete

- [ ] **Step 3: Write minimal implementation**

Add example knowledge files, test fixtures, and README instructions for setup and running the API.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -v`
Expected: PASS
