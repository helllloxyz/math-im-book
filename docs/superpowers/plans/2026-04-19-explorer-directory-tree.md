# Explorer Directory Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VS Code style user-managed folder trees for chat sessions and knowledge nodes while keeping fork relationships, knowledge references, ids, and physical storage paths stable.

**Architecture:** Add a file-backed Explorer store at `data/explorer/index.json` that owns folders and item locations. Expose Explorer trees through new FastAPI endpoints, then update the Vue left rail to render folders and leaf items from those trees. Missing locations are synthesized at read time so existing sessions and knowledge nodes keep working without migration rewrites.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, pytest, Vue 3, Pinia, TypeScript, Vitest.

---

## File Structure

- Create `src/math_im_book/storage/explorer.py`: file-backed Explorer repository, dataclasses, validation, tree builders, path cache calculation.
- Modify `src/math_im_book/api/schemas.py`: Explorer request/response schemas.
- Modify `src/math_im_book/api/app.py`: inject Explorer store, expose Explorer endpoints, inherit session folder on fork.
- Modify `src/math_im_book/services/knowledge_jobs.py`: ensure completed knowledge nodes receive an initial system Explorer location.
- Create `tests/storage/test_explorer.py`: storage and validation coverage.
- Modify `tests/api/test_sessions_api.py`: fork folder inheritance API coverage.
- Create `tests/api/test_explorer_api.py`: endpoint coverage for folders, moves, trees, and scope validation.
- Modify `frontend/src/services/api.ts`: Explorer types and client methods.
- Modify `frontend/src/stores/workspace.ts`: Explorer state and actions.
- Create `frontend/src/components/explorer/ExplorerTree.vue`: reusable compact folder/item tree.
- Modify `frontend/src/components/explorer/SessionTree.vue`: session wrapper around `ExplorerTree`.
- Modify `frontend/src/components/explorer/BookOutline.vue`: knowledge wrapper around `ExplorerTree`.
- Create `frontend/src/components/explorer/ExplorerTree.test.ts`: reusable tree behavior coverage.
- Modify `frontend/src/components/explorer/SessionTree.test.ts`: session-specific actions.
- Modify `frontend/src/components/explorer/BookOutline.test.ts`: knowledge-specific rendering and selection.

## Task 1: Explorer Storage

**Files:**
- Create: `src/math_im_book/storage/explorer.py`
- Test: `tests/storage/test_explorer.py`

- [ ] **Step 1: Write failing storage tests**

Create `tests/storage/test_explorer.py`:

```python
from pathlib import Path

import pytest

from math_im_book.storage.explorer import (
    ExplorerFolderConflictError,
    ExplorerInvalidMoveError,
    ExplorerStore,
)


def test_create_folder_rejects_duplicate_sibling_names(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)

    with pytest.raises(ExplorerFolderConflictError):
        store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)


def test_same_folder_name_is_allowed_in_different_scopes(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    knowledge = store.create_folder(scope="knowledge", name="Archive", parent_folder_id=None)
    sessions = store.create_folder(scope="sessions", name="Archive", parent_folder_id=None)

    assert knowledge.folder_id != sessions.folder_id
    assert knowledge.scope == "knowledge"
    assert sessions.scope == "sessions"


def test_move_item_sets_user_locked_location_and_cached_path(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="knowledge", name="Linear Algebra", parent_folder_id=None)

    location = store.move_item(
        item_type="knowledge_node",
        item_id="linear-map",
        folder_id=folder.folder_id,
        sort_order=2000,
        location_source="user",
    )

    assert location.item_type == "knowledge_node"
    assert location.item_id == "linear-map"
    assert location.folder_id == folder.folder_id
    assert location.user_locked is True
    assert location.path_cached == "/Linear Algebra/linear-map"


def test_cross_scope_move_is_rejected(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Chats", parent_folder_id=None)

    with pytest.raises(ExplorerInvalidMoveError):
        store.move_item(
            item_type="knowledge_node",
            item_id="linear-map",
            folder_id=folder.folder_id,
            sort_order=1000,
            location_source="user",
        )


def test_delete_non_empty_folder_is_rejected(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")
    folder = store.create_folder(scope="sessions", name="Course", parent_folder_id=None)
    store.move_item(
        item_type="session",
        item_id="chat-1",
        folder_id=folder.folder_id,
        sort_order=1000,
        location_source="user",
    )

    with pytest.raises(ExplorerInvalidMoveError):
        store.delete_folder(folder.folder_id)


def test_synthesized_locations_are_not_persisted_until_moved(tmp_path: Path) -> None:
    store = ExplorerStore(tmp_path / "explorer" / "index.json")

    tree = store.build_tree(
        scope="sessions",
        items=[
            {
                "item_type": "session",
                "item_id": "chat-1",
                "title": "Vector Spaces",
            }
        ],
    )

    assert tree[0]["kind"] == "item"
    assert tree[0]["item"]["item_id"] == "chat-1"
    assert store.load_payload()["locations"] == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/storage/test_explorer.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'math_im_book.storage.explorer'`.

- [ ] **Step 3: Implement Explorer storage**

Create `src/math_im_book/storage/explorer.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


VALID_SCOPES = {"sessions", "knowledge"}
ITEM_SCOPE = {"session": "sessions", "knowledge_node": "knowledge"}
VALID_LOCATION_SOURCES = {"user", "agent", "system"}


class ExplorerError(ValueError):
    pass


class ExplorerFolderConflictError(ExplorerError):
    pass


class ExplorerInvalidMoveError(ExplorerError):
    pass


@dataclass(slots=True)
class ExplorerFolder:
    folder_id: str
    scope: str
    name: str
    parent_folder_id: str | None
    created_at: str
    updated_at: str
    sort_order: int = 1000


@dataclass(slots=True)
class ExplorerItemLocation:
    item_type: str
    item_id: str
    folder_id: str | None
    sort_order: int
    path_cached: str
    location_source: str
    user_locked: bool
    updated_at: str


class ExplorerStore:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def load_payload(self) -> dict[str, object]:
        if not self.index_path.exists():
            return {"version": 1, "folders": [], "locations": []}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def create_folder(
        self,
        *,
        scope: str,
        name: str,
        parent_folder_id: str | None,
        sort_order: int = 1000,
    ) -> ExplorerFolder:
        self._validate_scope(scope)
        cleaned_name = self._clean_name(name)
        payload = self.load_payload()
        folders = self._folders(payload)
        if parent_folder_id is not None:
            parent = self._folder_by_id(folders, parent_folder_id)
            if parent is None or parent.scope != scope:
                raise ExplorerInvalidMoveError("Parent folder is not in the requested scope")
        self._raise_for_duplicate_folder_name(
            folders=folders,
            scope=scope,
            parent_folder_id=parent_folder_id,
            name=cleaned_name,
            excluded_folder_id=None,
        )
        now = self._now()
        folder = ExplorerFolder(
            folder_id=f"folder-{uuid4().hex[:8]}",
            scope=scope,
            name=cleaned_name,
            parent_folder_id=parent_folder_id,
            created_at=now,
            updated_at=now,
            sort_order=sort_order,
        )
        payload["folders"] = [*[asdict(item) for item in folders], asdict(folder)]
        self._save_payload(payload)
        return folder

    def rename_folder(self, folder_id: str, name: str) -> ExplorerFolder:
        payload = self.load_payload()
        folders = self._folders(payload)
        folder = self._folder_by_id(folders, folder_id)
        if folder is None:
            raise KeyError(folder_id)
        cleaned_name = self._clean_name(name)
        self._raise_for_duplicate_folder_name(
            folders=folders,
            scope=folder.scope,
            parent_folder_id=folder.parent_folder_id,
            name=cleaned_name,
            excluded_folder_id=folder.folder_id,
        )
        folder.name = cleaned_name
        folder.updated_at = self._now()
        payload["folders"] = [asdict(item) for item in folders]
        payload["locations"] = [
            asdict(self._refresh_location_path(location, folders))
            for location in self._locations(payload)
        ]
        self._save_payload(payload)
        return folder

    def delete_folder(self, folder_id: str) -> None:
        payload = self.load_payload()
        folders = self._folders(payload)
        locations = self._locations(payload)
        if any(folder.parent_folder_id == folder_id for folder in folders):
            raise ExplorerInvalidMoveError("Cannot delete a folder that contains folders")
        if any(location.folder_id == folder_id for location in locations):
            raise ExplorerInvalidMoveError("Cannot delete a folder that contains items")
        remaining = [folder for folder in folders if folder.folder_id != folder_id]
        if len(remaining) == len(folders):
            raise KeyError(folder_id)
        payload["folders"] = [asdict(folder) for folder in remaining]
        payload["locations"] = [asdict(location) for location in locations]
        self._save_payload(payload)

    def move_item(
        self,
        *,
        item_type: str,
        item_id: str,
        folder_id: str | None,
        sort_order: int,
        location_source: str,
    ) -> ExplorerItemLocation:
        expected_scope = self._scope_for_item_type(item_type)
        if location_source not in VALID_LOCATION_SOURCES:
            raise ExplorerInvalidMoveError("Invalid location source")
        payload = self.load_payload()
        folders = self._folders(payload)
        if folder_id is not None:
            folder = self._folder_by_id(folders, folder_id)
            if folder is None or folder.scope != expected_scope:
                raise ExplorerInvalidMoveError("Target folder is not in the item scope")
        now = self._now()
        locations = [
            location
            for location in self._locations(payload)
            if not (location.item_type == item_type and location.item_id == item_id)
        ]
        location = ExplorerItemLocation(
            item_type=item_type,
            item_id=item_id,
            folder_id=folder_id,
            sort_order=sort_order,
            path_cached=self._path_for(folder_id, folders, item_id),
            location_source=location_source,
            user_locked=location_source == "user",
            updated_at=now,
        )
        payload["folders"] = [asdict(folder) for folder in folders]
        payload["locations"] = [*[asdict(item) for item in locations], asdict(location)]
        self._save_payload(payload)
        return location

    def ensure_item_location(
        self,
        *,
        item_type: str,
        item_id: str,
        folder_id: str | None = None,
        location_source: str = "system",
    ) -> ExplorerItemLocation:
        existing = self.find_location(item_type=item_type, item_id=item_id)
        if existing is not None:
            return existing
        return self.move_item(
            item_type=item_type,
            item_id=item_id,
            folder_id=folder_id,
            sort_order=1000,
            location_source=location_source,
        )

    def find_location(
        self, *, item_type: str, item_id: str
    ) -> ExplorerItemLocation | None:
        for location in self._locations(self.load_payload()):
            if location.item_type == item_type and location.item_id == item_id:
                return location
        return None

    def build_tree(
        self, *, scope: str, items: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        self._validate_scope(scope)
        payload = self.load_payload()
        folders = [folder for folder in self._folders(payload) if folder.scope == scope]
        locations = {
            (location.item_type, location.item_id): location
            for location in self._locations(payload)
            if self._scope_for_item_type(location.item_type) == scope
        }
        folder_nodes: dict[str | None, list[dict[str, object]]] = {None: []}
        for folder in folders:
            folder_nodes.setdefault(folder.folder_id, [])
            folder_nodes.setdefault(folder.parent_folder_id, []).append(
                {
                    "kind": "folder",
                    "folder": asdict(folder),
                    "children": folder_nodes[folder.folder_id],
                }
            )
        for item in items:
            item_type = str(item["item_type"])
            item_id = str(item["item_id"])
            location = locations.get((item_type, item_id))
            folder_id = location.folder_id if location is not None else None
            folder_nodes.setdefault(folder_id, []).append(
                {
                    "kind": "item",
                    "location": asdict(location)
                    if location is not None
                    else {
                        "item_type": item_type,
                        "item_id": item_id,
                        "folder_id": None,
                        "sort_order": 1000,
                        "path_cached": f"/{item_id}",
                        "location_source": "system",
                        "user_locked": False,
                        "updated_at": "",
                    },
                    "item": item,
                }
            )
        self._sort_tree(folder_nodes[None])
        return folder_nodes[None]

    def _refresh_location_path(
        self, location: ExplorerItemLocation, folders: list[ExplorerFolder]
    ) -> ExplorerItemLocation:
        location.path_cached = self._path_for(location.folder_id, folders, location.item_id)
        return location

    def _path_for(
        self, folder_id: str | None, folders: list[ExplorerFolder], item_name: str
    ) -> str:
        folder_by_id = {folder.folder_id: folder for folder in folders}
        names: list[str] = []
        current = folder_id
        while current is not None:
            folder = folder_by_id.get(current)
            if folder is None:
                break
            names.append(folder.name)
            current = folder.parent_folder_id
        return "/" + "/".join([*reversed(names), item_name])

    @staticmethod
    def _sort_tree(nodes: list[dict[str, object]]) -> None:
        nodes.sort(
            key=lambda node: (
                0 if node["kind"] == "folder" else 1,
                (
                    node.get("folder", {}).get("sort_order", 1000)  # type: ignore[union-attr]
                    if node["kind"] == "folder"
                    else node.get("location", {}).get("sort_order", 1000)  # type: ignore[union-attr]
                ),
                (
                    node.get("folder", {}).get("name", "")  # type: ignore[union-attr]
                    if node["kind"] == "folder"
                    else node.get("item", {}).get("title", "")  # type: ignore[union-attr]
                ),
            )
        )
        for node in nodes:
            if node["kind"] == "folder":
                ExplorerStore._sort_tree(node["children"])  # type: ignore[arg-type]

    def _save_payload(self, payload: dict[str, object]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _folders(payload: dict[str, object]) -> list[ExplorerFolder]:
        return [ExplorerFolder(**item) for item in payload.get("folders", [])]  # type: ignore[arg-type]

    @staticmethod
    def _locations(payload: dict[str, object]) -> list[ExplorerItemLocation]:
        return [
            ExplorerItemLocation(**item)
            for item in payload.get("locations", [])  # type: ignore[arg-type]
        ]

    @staticmethod
    def _folder_by_id(
        folders: list[ExplorerFolder], folder_id: str
    ) -> ExplorerFolder | None:
        return next((folder for folder in folders if folder.folder_id == folder_id), None)

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise ExplorerInvalidMoveError("Folder name is required")
        if "/" in cleaned:
            raise ExplorerInvalidMoveError("Folder name cannot contain /")
        return cleaned

    @staticmethod
    def _validate_scope(scope: str) -> None:
        if scope not in VALID_SCOPES:
            raise ExplorerInvalidMoveError("Invalid explorer scope")

    @staticmethod
    def _scope_for_item_type(item_type: str) -> str:
        try:
            return ITEM_SCOPE[item_type]
        except KeyError as exc:
            raise ExplorerInvalidMoveError("Invalid explorer item type") from exc

    @staticmethod
    def _raise_for_duplicate_folder_name(
        *,
        folders: list[ExplorerFolder],
        scope: str,
        parent_folder_id: str | None,
        name: str,
        excluded_folder_id: str | None,
    ) -> None:
        for folder in folders:
            if folder.folder_id == excluded_folder_id:
                continue
            if (
                folder.scope == scope
                and folder.parent_folder_id == parent_folder_id
                and folder.name == name
            ):
                raise ExplorerFolderConflictError("Folder name already exists")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
```

- [ ] **Step 4: Run storage tests and verify they pass**

Run:

```bash
.venv/bin/pytest tests/storage/test_explorer.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS all tests in `tests/storage/test_explorer.py`.

- [ ] **Step 5: Commit storage layer**

```bash
git add src/math_im_book/storage/explorer.py tests/storage/test_explorer.py
git commit -m "feat: add explorer storage"
```

## Task 2: Explorer API Schemas and Endpoints

**Files:**
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`
- Test: `tests/api/test_explorer_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/api/test_explorer_api.py`:

```python
from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import KnowledgeNode
from math_im_book.storage.explorer import ExplorerStore
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore, SessionRecord


def test_sessions_explorer_synthesizes_existing_session_at_root(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(SessionRecord(session_id="chat-1", title="Vector Spaces"))
    client = TestClient(
        create_app(
            session_store=session_store,
            explorer_store=ExplorerStore(tmp_path / "explorer" / "index.json"),
        )
    )

    response = client.get("/api/explorer/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "sessions"
    assert body["tree"][0]["kind"] == "item"
    assert body["tree"][0]["item"]["session_id"] == "chat-1"


def test_create_folder_and_move_session(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(SessionRecord(session_id="chat-1", title="Vector Spaces"))
    client = TestClient(
        create_app(
            session_store=session_store,
            explorer_store=ExplorerStore(tmp_path / "explorer" / "index.json"),
        )
    )

    folder_response = client.post(
        "/api/explorer/folders",
        json={"scope": "sessions", "name": "Course", "parent_folder_id": None},
    )
    folder_id = folder_response.json()["folder"]["folder_id"]
    move_response = client.patch(
        "/api/explorer/items/session/chat-1/location",
        json={"folder_id": folder_id, "sort_order": 1000},
    )
    tree_response = client.get("/api/explorer/sessions")

    assert folder_response.status_code == 200
    assert move_response.status_code == 200
    assert move_response.json()["location"]["user_locked"] is True
    folder = tree_response.json()["tree"][0]
    assert folder["kind"] == "folder"
    assert folder["children"][0]["item"]["session_id"] == "chat-1"


def test_cross_scope_move_returns_400(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves addition and scalar multiplication.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        )
    )
    client = TestClient(
        create_app(
            repository=repository,
            explorer_store=ExplorerStore(tmp_path / "explorer" / "index.json"),
        )
    )
    folder_id = client.post(
        "/api/explorer/folders",
        json={"scope": "sessions", "name": "Chats", "parent_folder_id": None},
    ).json()["folder"]["folder_id"]

    response = client.patch(
        "/api/explorer/items/knowledge_node/linear-map/location",
        json={"folder_id": folder_id, "sort_order": 1000},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Target folder is not in the item scope"


def test_knowledge_explorer_returns_foldered_node(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="linear-map",
            title="Linear Map",
            type="atomic",
            summary="Preserves addition and scalar multiplication.",
            detail="Detail",
            parent_id=None,
            source="chat:1",
            status="ready",
        )
    )
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    client = TestClient(create_app(repository=repository, explorer_store=explorer_store))
    folder_id = client.post(
        "/api/explorer/folders",
        json={"scope": "knowledge", "name": "Linear Algebra", "parent_folder_id": None},
    ).json()["folder"]["folder_id"]
    client.patch(
        "/api/explorer/items/knowledge_node/linear-map/location",
        json={"folder_id": folder_id, "sort_order": 1000},
    )

    response = client.get("/api/explorer/knowledge")

    assert response.status_code == 200
    folder = response.json()["tree"][0]
    assert folder["folder"]["name"] == "Linear Algebra"
    assert folder["children"][0]["item"]["id"] == "linear-map"
```

- [ ] **Step 2: Run API tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/api/test_explorer_api.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'explorer_store'`.

- [ ] **Step 3: Add schemas**

Append these schema classes in `src/math_im_book/api/schemas.py` near the existing outline/session schemas:

```python
class ExplorerFolderSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: str
    scope: Literal["sessions", "knowledge"]
    name: str
    parent_folder_id: str | None = None
    created_at: str
    updated_at: str
    sort_order: int = 1000


class ExplorerItemLocationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: Literal["session", "knowledge_node"]
    item_id: str
    folder_id: str | None = None
    sort_order: int = 1000
    path_cached: str
    location_source: Literal["user", "agent", "system"]
    user_locked: bool = False
    updated_at: str


class ExplorerTreeNodeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["folder", "item"]
    folder: ExplorerFolderSchema | None = None
    location: ExplorerItemLocationSchema | None = None
    item: dict[str, object] | None = None
    children: list["ExplorerTreeNodeSchema"] = Field(default_factory=list)


class ExplorerTreeResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["sessions", "knowledge"]
    tree: list[ExplorerTreeNodeSchema] = Field(default_factory=list)


class ExplorerFolderCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["sessions", "knowledge"]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    parent_folder_id: str | None = None


class ExplorerFolderUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExplorerFolderResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: ExplorerFolderSchema


class ExplorerItemLocationUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder_id: str | None = None
    sort_order: int = 1000


class ExplorerItemLocationResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: ExplorerItemLocationSchema
```

- [ ] **Step 4: Add app wiring and endpoints**

Modify imports in `src/math_im_book/api/app.py`:

```python
from math_im_book.storage.explorer import (
    ExplorerFolderConflictError,
    ExplorerInvalidMoveError,
    ExplorerStore,
)
```

Add schema imports from `schemas.py`:

```python
    ExplorerFolderCreateSchema,
    ExplorerFolderResponseSchema,
    ExplorerFolderUpdateSchema,
    ExplorerItemLocationResponseSchema,
    ExplorerItemLocationUpdateSchema,
    ExplorerTreeResponseSchema,
```

Extend `create_app` signature:

```python
def create_app(
    repository: MarkdownKnowledgeRepository | None = None,
    session_store: FileSessionStore | None = None,
    knowledge_job_repository: InMemoryKnowledgeJobRepository | None = None,
    credential_registry: FileCredentialRegistry | None = None,
    provider_options_repository: FileProviderOptionsRepository | None = None,
    answer_style_repository: FileAnswerStyleRepository | None = None,
    strategy_agent_repository: FileStrategyAgentRepository | None = None,
    user_profile_repository: FileUserProfileRepository | None = None,
    explorer_store: ExplorerStore | None = None,
) -> FastAPI:
```

After session store initialization, add:

```python
    explorer = explorer_store or ExplorerStore(Path("data/explorer/index.json"))
```

Add helpers before `return app`:

```python
    def _session_explorer_items() -> list[dict[str, object]]:
        records = sessions.list_recent_records()
        tree_metadata = _session_tree_metadata(records)
        items: list[dict[str, object]] = []
        for record in records:
            items.append(
                {
                    "item_type": "session",
                    "item_id": record.session_id,
                    "session_id": record.session_id,
                    "title": record.title,
                    "icon": record.icon,
                    "message_count": record.message_count,
                    "branch": _branch_context_to_schema(record.branch_context).model_dump(),
                    "branch_depth": tree_metadata.get(record.session_id, {}).get("branch_depth", 0),
                    "child_session_ids": tree_metadata.get(record.session_id, {}).get("child_session_ids", []),
                }
            )
        return items

    def _knowledge_explorer_items() -> list[dict[str, object]]:
        return [
            {
                "item_type": "knowledge_node",
                "item_id": node.id,
                "id": node.id,
                "title": node.title,
                "type": node.type,
                "summary": node.summary,
                "parent_id": node.parent_id,
                "status": node.status,
            }
            for node in knowledge_repository.list_nodes()
        ]
```

Add endpoints before `/api/agent-state`:

```python
    @app.get("/api/explorer/sessions", response_model=ExplorerTreeResponseSchema)
    def get_sessions_explorer() -> ExplorerTreeResponseSchema:
        return ExplorerTreeResponseSchema.model_validate(
            {
                "scope": "sessions",
                "tree": explorer.build_tree(scope="sessions", items=_session_explorer_items()),
            }
        )

    @app.get("/api/explorer/knowledge", response_model=ExplorerTreeResponseSchema)
    def get_knowledge_explorer() -> ExplorerTreeResponseSchema:
        return ExplorerTreeResponseSchema.model_validate(
            {
                "scope": "knowledge",
                "tree": explorer.build_tree(scope="knowledge", items=_knowledge_explorer_items()),
            }
        )

    @app.post("/api/explorer/folders", response_model=ExplorerFolderResponseSchema)
    def create_explorer_folder(
        payload: ExplorerFolderCreateSchema,
    ) -> ExplorerFolderResponseSchema:
        try:
            folder = explorer.create_folder(
                scope=payload.scope,
                name=payload.name,
                parent_folder_id=payload.parent_folder_id,
            )
        except ExplorerFolderConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ExplorerInvalidMoveError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExplorerFolderResponseSchema.model_validate({"folder": folder})

    @app.patch("/api/explorer/folders/{folder_id}", response_model=ExplorerFolderResponseSchema)
    def rename_explorer_folder(
        folder_id: str,
        payload: ExplorerFolderUpdateSchema,
    ) -> ExplorerFolderResponseSchema:
        try:
            folder = explorer.rename_folder(folder_id, payload.name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Folder not found") from exc
        except ExplorerFolderConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ExplorerInvalidMoveError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExplorerFolderResponseSchema.model_validate({"folder": folder})

    @app.delete("/api/explorer/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_explorer_folder(folder_id: str) -> Response:
        try:
            explorer.delete_folder(folder_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Folder not found") from exc
        except ExplorerInvalidMoveError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.patch(
        "/api/explorer/items/{item_type}/{item_id}/location",
        response_model=ExplorerItemLocationResponseSchema,
    )
    def move_explorer_item(
        item_type: str,
        item_id: str,
        payload: ExplorerItemLocationUpdateSchema,
    ) -> ExplorerItemLocationResponseSchema:
        try:
            location = explorer.move_item(
                item_type=item_type,
                item_id=item_id,
                folder_id=payload.folder_id,
                sort_order=payload.sort_order,
                location_source="user",
            )
        except ExplorerInvalidMoveError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExplorerItemLocationResponseSchema.model_validate({"location": location})
```

- [ ] **Step 5: Run API tests and fix type import errors**

Run:

```bash
.venv/bin/pytest tests/api/test_explorer_api.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS all tests in `tests/api/test_explorer_api.py`.

- [ ] **Step 6: Commit API endpoints**

```bash
git add src/math_im_book/api/app.py src/math_im_book/api/schemas.py tests/api/test_explorer_api.py
git commit -m "feat: expose explorer tree api"
```

## Task 3: Fork Folder Inheritance and Knowledge Job Initial Locations

**Files:**
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/services/knowledge_jobs.py`
- Test: `tests/api/test_sessions_api.py`
- Test: `tests/services/test_knowledge_jobs.py`

- [ ] **Step 1: Write failing fork inheritance test**

Append to `tests/api/test_sessions_api.py`:

```python
def test_forked_session_inherits_parent_explorer_folder(tmp_path) -> None:
    knowledge_repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    session_store = FileSessionStore(tmp_path / "sessions")
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    session_store.save_record(
        SessionRecord(
            session_id="chat-root",
            title="Root",
            messages=[
                SessionMessage(
                    message_id="msg-1",
                    role="user",
                    content="What is a vector space?",
                    created_at="2026-04-19T00:00:00Z",
                )
            ],
        )
    )
    folder = explorer_store.create_folder(
        scope="sessions",
        name="Course",
        parent_folder_id=None,
    )
    explorer_store.move_item(
        item_type="session",
        item_id="chat-root",
        folder_id=folder.folder_id,
        sort_order=1000,
        location_source="user",
    )
    client = TestClient(
        create_app(
            repository=knowledge_repository,
            session_store=session_store,
            explorer_store=explorer_store,
        )
    )

    response = client.post(
        "/api/sessions/chat-root/fork",
        json={
            "fork_anchor": {"type": "message", "message_id": "msg-1"},
            "focus_question": "Explore a branch",
        },
    )

    assert response.status_code == 200
    child_session_id = response.json()["session_id"]
    child_location = explorer_store.find_location(
        item_type="session",
        item_id=child_session_id,
    )
    assert child_location is not None
    assert child_location.folder_id == folder.folder_id
    assert child_location.location_source == "system"
    assert child_location.user_locked is False
```

- [ ] **Step 2: Run fork inheritance test and verify it fails**

Run:

```bash
.venv/bin/pytest tests/api/test_sessions_api.py::test_forked_session_inherits_parent_explorer_folder -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: FAIL because `child_location is None`.

- [ ] **Step 3: Implement fork folder inheritance**

In `src/math_im_book/api/app.py`, after `sessions.save_record(child_record)` in `fork_session`, add:

```python
        parent_location = explorer.find_location(
            item_type="session",
            item_id=session_id,
        )
        if parent_location is not None:
            explorer.ensure_item_location(
                item_type="session",
                item_id=child_session_id,
                folder_id=parent_location.folder_id,
                location_source="system",
            )
```

- [ ] **Step 4: Run fork inheritance test and verify it passes**

Run:

```bash
.venv/bin/pytest tests/api/test_sessions_api.py::test_forked_session_inherits_parent_explorer_folder -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS.

- [ ] **Step 5: Write failing knowledge job location test**

Append to `tests/services/test_knowledge_jobs.py`:

```python
def test_completed_knowledge_job_ensures_explorer_location(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    explorer_store = ExplorerStore(tmp_path / "explorer" / "index.json")
    jobs = InMemoryKnowledgeJobRepository(
        repository,
        auto_start=False,
        explorer_store=explorer_store,
    )
    job = jobs.submit_compile_job(
        session_id="chat-1",
        question="What is a vector space?",
        anchors=[],
        selected_node_ids=[],
        draft_requests=[
            PendingDraftRequest(
                title="Vector Space",
                draft_type="definition",
                reason="Reusable definition.",
            )
        ],
    )

    jobs.run_job(job.job_id)

    node_id = repository.list_nodes()[0].id
    location = explorer_store.find_location(item_type="knowledge_node", item_id=node_id)
    assert location is not None
    assert location.location_source == "system"
    assert location.user_locked is False
```

- [ ] **Step 6: Run knowledge job test and verify it fails**

Run:

```bash
.venv/bin/pytest tests/services/test_knowledge_jobs.py::test_completed_knowledge_job_ensures_explorer_location -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: FAIL with `TypeError: InMemoryKnowledgeJobRepository.__init__() got an unexpected keyword argument 'explorer_store'`.

- [ ] **Step 7: Add optional Explorer store to knowledge jobs**

Modify `src/math_im_book/services/knowledge_jobs.py` imports:

```python
from math_im_book.storage.explorer import ExplorerStore
```

Extend `InMemoryKnowledgeJobRepository.__init__`:

```python
        explorer_store: ExplorerStore | None = None,
```

Set:

```python
        self.explorer_store = explorer_store
```

In `_compile_job`, immediately after `self.repository.save_node(result.node)`, add:

```python
                if self.explorer_store is not None:
                    self.explorer_store.ensure_item_location(
                        item_type="knowledge_node",
                        item_id=result.node.id,
                        location_source="system",
                    )
```

In `src/math_im_book/api/app.py`, when creating the default `InMemoryKnowledgeJobRepository`, pass `explorer_store=explorer`. If the user supplied a custom knowledge job repository, do not mutate it.

- [ ] **Step 8: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/api/test_sessions_api.py::test_forked_session_inherits_parent_explorer_folder tests/services/test_knowledge_jobs.py::test_completed_knowledge_job_ensures_explorer_location -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS both tests.

- [ ] **Step 9: Commit inheritance and job locations**

```bash
git add src/math_im_book/api/app.py src/math_im_book/services/knowledge_jobs.py tests/api/test_sessions_api.py tests/services/test_knowledge_jobs.py
git commit -m "feat: keep explorer locations for forks and knowledge jobs"
```

## Task 4: Frontend API and Store

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Test: `frontend/src/services/api.test.ts`
- Test: `frontend/src/stores/workspace.test.ts`

- [ ] **Step 1: Write failing API client test**

Append to `frontend/src/services/api.test.ts`:

```typescript
const mockAxiosClient = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    create: () => mockAxiosClient,
  },
}));

it('fetches explorer trees', async () => {
  mockAxiosClient.get
    .mockResolvedValueOnce({ data: { scope: 'sessions', tree: [] } })
    .mockResolvedValueOnce({ data: { scope: 'knowledge', tree: [] } });

  const sessions = await api.getSessionExplorer();
  const knowledge = await api.getKnowledgeExplorer();

  expect(mockAxiosClient.get).toHaveBeenNthCalledWith(1, '/explorer/sessions');
  expect(mockAxiosClient.get).toHaveBeenNthCalledWith(2, '/explorer/knowledge');
  expect(sessions.scope).toBe('sessions');
  expect(knowledge.scope).toBe('knowledge');
});
```

If `api.test.ts` already imports `api` before the axios mock, move the `vi.hoisted` and `vi.mock('axios', ...)` block above `import { api } from './api';`. Keep the existing `askStream` tests on `fetch`; mocking axios does not affect `askStream`.

- [ ] **Step 2: Run API client test and verify it fails**

Run:

```bash
cd frontend && npm run test -- api.test.ts
```

Expected: FAIL because `api.getSessionExplorer` is not a function.

- [ ] **Step 3: Add frontend Explorer types and client methods**

Add to `frontend/src/services/api.ts`:

```typescript
export type ExplorerScope = 'sessions' | 'knowledge';
export type ExplorerItemType = 'session' | 'knowledge_node';

export interface ExplorerFolder {
  folder_id: string;
  scope: ExplorerScope;
  name: string;
  parent_folder_id?: string | null;
  created_at: string;
  updated_at: string;
  sort_order: number;
}

export interface ExplorerItemLocation {
  item_type: ExplorerItemType;
  item_id: string;
  folder_id?: string | null;
  sort_order: number;
  path_cached: string;
  location_source: 'user' | 'agent' | 'system';
  user_locked: boolean;
  updated_at: string;
}

export interface ExplorerTreeNode {
  kind: 'folder' | 'item';
  folder?: ExplorerFolder | null;
  location?: ExplorerItemLocation | null;
  item?: Record<string, any> | null;
  children: ExplorerTreeNode[];
}

export interface ExplorerTreeResponse {
  scope: ExplorerScope;
  tree: ExplorerTreeNode[];
}
```

Add methods to `api`:

```typescript
  async getSessionExplorer(): Promise<ExplorerTreeResponse> {
    const response = await client.get<ExplorerTreeResponse>('/explorer/sessions');
    return response.data;
  },

  async getKnowledgeExplorer(): Promise<ExplorerTreeResponse> {
    const response = await client.get<ExplorerTreeResponse>('/explorer/knowledge');
    return response.data;
  },

  async createExplorerFolder(payload: {
    scope: ExplorerScope;
    name: string;
    parent_folder_id?: string | null;
  }): Promise<ExplorerFolder> {
    const response = await client.post<{ folder: ExplorerFolder }>('/explorer/folders', payload);
    return response.data.folder;
  },

  async renameExplorerFolder(folderId: string, name: string): Promise<ExplorerFolder> {
    const response = await client.patch<{ folder: ExplorerFolder }>(
      `/explorer/folders/${folderId}`,
      { name }
    );
    return response.data.folder;
  },

  async deleteExplorerFolder(folderId: string): Promise<void> {
    await client.delete(`/explorer/folders/${folderId}`);
  },

  async moveExplorerItem(
    itemType: ExplorerItemType,
    itemId: string,
    payload: { folder_id?: string | null; sort_order?: number }
  ): Promise<ExplorerItemLocation> {
    const response = await client.patch<{ location: ExplorerItemLocation }>(
      `/explorer/items/${itemType}/${itemId}/location`,
      payload
    );
    return response.data.location;
  },
```

- [ ] **Step 4: Add store state and actions**

Modify `frontend/src/stores/workspace.ts` imports:

```typescript
  type ExplorerTreeNode,
  type ExplorerScope,
  type ExplorerItemType,
```

Add state:

```typescript
  const sessionExplorerTree = ref<ExplorerTreeNode[]>([]);
  const knowledgeExplorerTree = ref<ExplorerTreeNode[]>([]);
```

Add actions:

```typescript
  async function fetchSessionExplorer() {
    try {
      sessionExplorerTree.value = (await api.getSessionExplorer()).tree;
    } catch (error) {
      console.error('Failed to fetch session explorer:', error);
    }
  }

  async function fetchKnowledgeExplorer() {
    try {
      knowledgeExplorerTree.value = (await api.getKnowledgeExplorer()).tree;
    } catch (error) {
      console.error('Failed to fetch knowledge explorer:', error);
    }
  }

  async function createExplorerFolder(
    scope: ExplorerScope,
    name: string,
    parentFolderId: string | null = null
  ) {
    await api.createExplorerFolder({
      scope,
      name,
      parent_folder_id: parentFolderId,
    });
    if (scope === 'sessions') await fetchSessionExplorer();
    if (scope === 'knowledge') await fetchKnowledgeExplorer();
  }

  async function moveExplorerItem(
    itemType: ExplorerItemType,
    itemId: string,
    folderId: string | null
  ) {
    await api.moveExplorerItem(itemType, itemId, {
      folder_id: folderId,
      sort_order: 1000,
    });
    if (itemType === 'session') await fetchSessionExplorer();
    if (itemType === 'knowledge_node') await fetchKnowledgeExplorer();
  }
```

In `fetchSessions`, after `sessions.value = await api.getSessions();`, add:

```typescript
      await fetchSessionExplorer();
```

In `fetchOutline`, after `outline.value = await api.getOutline();`, add:

```typescript
      await fetchKnowledgeExplorer();
```

Return the new state/actions from the store.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend && npm run test -- api.test.ts workspace.test.ts
```

Expected: PASS focused frontend tests.

- [ ] **Step 6: Commit frontend API/store**

```bash
git add frontend/src/services/api.ts frontend/src/services/api.test.ts frontend/src/stores/workspace.ts frontend/src/stores/workspace.test.ts
git commit -m "feat: add explorer state to frontend"
```

## Task 5: Reusable Explorer Tree Component

**Files:**
- Create: `frontend/src/components/explorer/ExplorerTree.vue`
- Test: `frontend/src/components/explorer/ExplorerTree.test.ts`

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/components/explorer/ExplorerTree.test.ts`:

```typescript
import { describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';

import ExplorerTree from './ExplorerTree.vue';

describe('ExplorerTree', () => {
  const tree = [
    {
      kind: 'folder',
      folder: {
        folder_id: 'folder-1',
        scope: 'knowledge',
        name: 'Linear Algebra',
        parent_folder_id: null,
        created_at: '2026-04-19T00:00:00Z',
        updated_at: '2026-04-19T00:00:00Z',
        sort_order: 1000,
      },
      children: [
        {
          kind: 'item',
          item: {
            item_id: 'linear-map',
            id: 'linear-map',
            title: 'Linear Map',
            type: 'atomic',
          },
          location: {
            item_type: 'knowledge_node',
            item_id: 'linear-map',
            folder_id: 'folder-1',
            sort_order: 1000,
            path_cached: '/Linear Algebra/linear-map',
            location_source: 'agent',
            user_locked: false,
            updated_at: '2026-04-19T00:00:00Z',
          },
          children: [],
        },
      ],
    },
  ];

  it('renders compact folder rows and expands items', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: 'linear-map',
      },
    });

    expect(wrapper.text()).toContain('Linear Algebra');
    expect(wrapper.text()).toContain('Linear Map');
    expect(wrapper.find('[data-explorer-folder="folder-1"]').exists()).toBe(true);
    expect(wrapper.find('[data-explorer-item="linear-map"]').classes()).toContain('tree-item-active');

    await wrapper.get('[data-explorer-folder-toggle="folder-1"]').trigger('click');
    expect(wrapper.text()).not.toContain('Linear Map');
  });

  it('emits select and create-folder actions', async () => {
    const wrapper = mount(ExplorerTree, {
      props: {
        tree,
        currentItemId: null,
      },
    });

    await wrapper.get('[data-explorer-item="linear-map"]').trigger('click');
    await wrapper.get('[data-explorer-create-folder="folder-1"]').trigger('click');

    expect(wrapper.emitted('select-item')?.[0]).toEqual(['knowledge_node', 'linear-map']);
    expect(wrapper.emitted('create-folder')?.[0]).toEqual(['folder-1']);
  });
});
```

- [ ] **Step 2: Run component test and verify it fails**

Run:

```bash
cd frontend && npm run test -- ExplorerTree.test.ts
```

Expected: FAIL because `ExplorerTree.vue` does not exist.

- [ ] **Step 3: Implement ExplorerTree.vue**

Create `frontend/src/components/explorer/ExplorerTree.vue`:

```vue
<template>
  <div class="space-y-0.5">
    <ExplorerTreeRow
      v-for="node in tree"
      :key="nodeKey(node)"
      :node="node"
      :depth="0"
      :current-item-id="currentItemId"
      @select-item="handleSelectItem"
      @create-folder="emit('create-folder', $event)"
      @move-item="handleMoveItem"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, ref } from 'vue';
import type { ExplorerTreeNode, ExplorerItemType } from '../../services/api';

defineProps<{
  tree: ExplorerTreeNode[];
  currentItemId?: string | null;
}>();

const emit = defineEmits<{
  (event: 'select-item', itemType: ExplorerItemType, itemId: string): void;
  (event: 'create-folder', parentFolderId: string | null): void;
  (event: 'move-item', itemType: ExplorerItemType, itemId: string): void;
}>();

const nodeKey = (node: ExplorerTreeNode) =>
  node.kind === 'folder'
    ? `folder:${node.folder?.folder_id}`
    : `item:${node.location?.item_type}:${node.location?.item_id}`;

const handleSelectItem = (itemType: ExplorerItemType, itemId: string) => {
  emit('select-item', itemType, itemId);
};

const handleMoveItem = (itemType: ExplorerItemType, itemId: string) => {
  emit('move-item', itemType, itemId);
};

const ExplorerTreeRow = defineComponent({
  name: 'ExplorerTreeRow',
  props: {
    node: { type: Object as () => ExplorerTreeNode, required: true },
    depth: { type: Number, required: true },
    currentItemId: { type: String, required: false },
  },
  emits: ['select-item', 'create-folder', 'move-item'],
  setup(props, { emit }) {
    const expanded = ref(true);
    const isFolder = computed(() => props.node.kind === 'folder');
    const folder = computed(() => props.node.folder);
    const location = computed(() => props.node.location);
    const item = computed(() => props.node.item || {});
    const itemId = computed(() => String(location.value?.item_id || item.value.item_id || item.value.id || ''));
    const itemType = computed(() => String(location.value?.item_type || item.value.item_type || 'knowledge_node') as ExplorerItemType);
    const title = computed(() =>
      isFolder.value
        ? folder.value?.name || 'Untitled Folder'
        : String(item.value.title || itemId.value || 'Untitled')
    );
    const isSelected = computed(() => !isFolder.value && props.currentItemId === itemId.value);
    const icon = computed(() => {
      if (isFolder.value) return expanded.value ? 'folder_open' : 'folder';
      if (itemType.value === 'session') return 'chat_bubble';
      return item.value.type === 'theorem' ? 'account_tree' : 'description';
    });

    return () =>
      h('div', { class: 'select-none' }, [
        h(
          'div',
          {
            class: [
              'group flex h-7 items-center gap-1.5 rounded-md px-2 text-left text-[12px] transition-colors hover:bg-surface-container-high',
              isSelected.value ? 'tree-item-active text-on-surface' : 'text-on-surface-variant/75',
            ],
            style: { paddingLeft: `${props.depth * 14 + 8}px` },
            ...(isFolder.value
              ? { 'data-explorer-folder': folder.value?.folder_id }
              : { 'data-explorer-item': itemId.value }),
            onClick: () => {
              if (!isFolder.value) emit('select-item', itemType.value, itemId.value);
            },
          },
          [
            h(
              'button',
              {
                type: 'button',
                class: 'flex h-4 w-4 items-center justify-center text-on-surface-variant/60',
                ...(isFolder.value
                  ? { 'data-explorer-folder-toggle': folder.value?.folder_id }
                  : {}),
                onClick: (event: MouseEvent) => {
                  event.stopPropagation();
                  if (isFolder.value) expanded.value = !expanded.value;
                },
              },
              isFolder.value
                ? h('span', { class: 'material-symbols-outlined text-[16px]' }, expanded.value ? 'keyboard_arrow_down' : 'chevron_right')
                : h('span', { class: 'block h-4 w-4' })
            ),
            h('span', { class: 'material-symbols-outlined text-[15px] text-on-surface-variant/60' }, icon.value),
            h('span', { class: 'min-w-0 flex-1 truncate' }, title.value),
            isFolder.value &&
              h(
                'button',
                {
                  type: 'button',
                  class: 'hidden h-5 w-5 items-center justify-center rounded text-on-surface-variant/50 hover:bg-surface-container group-hover:flex',
                  'data-explorer-create-folder': folder.value?.folder_id || '',
                  onClick: (event: MouseEvent) => {
                    event.stopPropagation();
                    emit('create-folder', folder.value?.folder_id || null);
                  },
                },
                h('span', { class: 'material-symbols-outlined text-[14px]' }, 'create_new_folder')
              ),
          ]
        ),
        isFolder.value &&
          expanded.value &&
          props.node.children.map((child) =>
            h(ExplorerTreeRow as any, {
              node: child,
              depth: props.depth + 1,
              currentItemId: props.currentItemId,
              onSelectItem: (itemType: ExplorerItemType, childItemId: string) => emit('select-item', itemType, childItemId),
              onCreateFolder: (parentFolderId: string | null) => emit('create-folder', parentFolderId),
              onMoveItem: (itemType: ExplorerItemType, childItemId: string) => emit('move-item', itemType, childItemId),
            })
          ),
      ]);
  },
});
</script>
```

Add this CSS to `frontend/src/style.css` if no matching class exists:

```css
.tree-item-active {
  background-color: color-mix(in srgb, var(--color-primary, #264761) 8%, transparent);
  box-shadow: inset 2px 0 0 color-mix(in srgb, var(--color-primary, #264761) 90%, transparent);
}
```

- [ ] **Step 4: Run component test**

Run:

```bash
cd frontend && npm run test -- ExplorerTree.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit ExplorerTree**

```bash
git add frontend/src/components/explorer/ExplorerTree.vue frontend/src/components/explorer/ExplorerTree.test.ts frontend/src/style.css
git commit -m "feat: add reusable explorer tree"
```

## Task 6: Replace Session and Knowledge Trees

**Files:**
- Modify: `frontend/src/components/explorer/SessionTree.vue`
- Modify: `frontend/src/components/explorer/BookOutline.vue`
- Test: `frontend/src/components/explorer/SessionTree.test.ts`
- Test: `frontend/src/components/explorer/BookOutline.test.ts`

- [ ] **Step 1: Update tests to expect Explorer tree state**

In `SessionTree.test.ts`, set `store.sessionExplorerTree` instead of relying only on `store.sessions`:

```typescript
store.sessionExplorerTree = [
  {
    kind: 'item',
    item: {
      item_type: 'session',
      item_id: 'chat-1',
      session_id: 'chat-1',
      title: 'Spectral Theorem',
      icon: 'sigma',
      message_count: 3,
    },
    location: {
      item_type: 'session',
      item_id: 'chat-1',
      folder_id: null,
      sort_order: 1000,
      path_cached: '/chat-1',
      location_source: 'system',
      user_locked: false,
      updated_at: '',
    },
    children: [],
  },
] as any;
```

In `BookOutline.test.ts`, set `store.knowledgeExplorerTree`:

```typescript
store.knowledgeExplorerTree = [
  {
    kind: 'item',
    item: {
      item_type: 'knowledge_node',
      item_id: 'vector-space',
      id: 'vector-space',
      title: 'Vector Space',
      type: 'atomic',
      summary: 'A set closed under vector addition and scalar multiplication.',
      status: 'ready',
    },
    location: {
      item_type: 'knowledge_node',
      item_id: 'vector-space',
      folder_id: null,
      sort_order: 1000,
      path_cached: '/vector-space',
      location_source: 'system',
      user_locked: false,
      updated_at: '',
    },
    children: [],
  },
] as any;
```

- [ ] **Step 2: Run existing component tests and verify they fail**

Run:

```bash
cd frontend && npm run test -- SessionTree.test.ts BookOutline.test.ts
```

Expected: FAIL because components still read `sessions` and `outline`.

- [ ] **Step 3: Update BookOutline.vue**

Replace recursive local tree construction with `ExplorerTree`:

```vue
<template>
  <ExplorerTree
    :tree="knowledgeExplorerTree"
    :current-item-id="currentNode?.id || null"
    @select-item="handleSelectItem"
    @create-folder="handleCreateFolder"
  />
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import ExplorerTree from './ExplorerTree.vue';
import { useWorkspaceStore } from '../../stores/workspace';
import type { ExplorerItemType } from '../../services/api';

const store = useWorkspaceStore();
const { knowledgeExplorerTree, currentNode } = storeToRefs(store);

const handleSelectItem = (itemType: ExplorerItemType, itemId: string) => {
  if (itemType === 'knowledge_node') {
    store.selectNode(itemId);
  }
};

const handleCreateFolder = async (parentFolderId: string | null) => {
  const name = window.prompt('Folder name');
  if (!name) return;
  await store.createExplorerFolder('knowledge', name, parentFolderId);
};
</script>
```

- [ ] **Step 4: Update SessionTree.vue**

Use `ExplorerTree` for rendering and keep icon/delete actions out of the first tree replacement if they conflict with the reusable row. Preserve selection behavior:

```vue
<template>
  <ExplorerTree
    :tree="sessionExplorerTree"
    :current-item-id="currentSession?.session_id || null"
    @select-item="handleSelectItem"
    @create-folder="handleCreateFolder"
  />
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia';
import ExplorerTree from './ExplorerTree.vue';
import { useWorkspaceStore } from '../../stores/workspace';
import type { ExplorerItemType } from '../../services/api';

const store = useWorkspaceStore();
const { sessionExplorerTree, currentSession } = storeToRefs(store);

const handleSelectItem = (itemType: ExplorerItemType, itemId: string) => {
  if (itemType === 'session') {
    store.selectSession(itemId);
  }
};

const handleCreateFolder = async (parentFolderId: string | null) => {
  const name = window.prompt('Folder name');
  if (!name) return;
  await store.createExplorerFolder('sessions', name, parentFolderId);
};
</script>
```

- [ ] **Step 5: Run focused component tests**

Run:

```bash
cd frontend && npm run test -- ExplorerTree.test.ts SessionTree.test.ts BookOutline.test.ts
```

Expected: PASS after the tests assert the first-version Explorer behavior: row rendering, item selection, and folder creation. Session icon picker and delete menu assertions should be removed from these two focused tests because the first Explorer replacement does not include those row actions.

- [ ] **Step 6: Commit component replacement**

```bash
git add frontend/src/components/explorer/SessionTree.vue frontend/src/components/explorer/BookOutline.vue frontend/src/components/explorer/SessionTree.test.ts frontend/src/components/explorer/BookOutline.test.ts
git commit -m "feat: render sessions and knowledge as explorer trees"
```

## Task 7: Full Verification

**Files:**
- Run verification against the files changed in Tasks 1-6.

- [ ] **Step 1: Run backend test suite**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: PASS.

- [ ] **Step 2: Run frontend test suite**

Run:

```bash
cd frontend && npm run test
```

Expected: PASS.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS and `frontend/dist/` updated.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intentional source/test changes and existing untracked `tree_view.html` if the user has not added it.

- [ ] **Step 5: Record final status**

Run:

```bash
git log --oneline -5
```

Expected: recent commits include the Explorer storage, API, frontend state, tree component, and component replacement commits from this plan.
