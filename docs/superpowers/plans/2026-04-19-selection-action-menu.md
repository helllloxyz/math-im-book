# Selection Action Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `Ctrl+Q` selection action menu for chat and reader text that fills editable follow-up prompts or directly starts selection-based knowledge generation.

**Architecture:** Frontend selection handling is isolated in a global Vue component and store-backed composer draft state. Backend knowledge generation uses a dedicated API endpoint that submits existing compile jobs with structured selected text and prompt kind metadata. Existing job polling is reused where practical and split when assistant-message anchors are not available.

**Tech Stack:** FastAPI, Pydantic, pytest, Vue 3, Pinia, TypeScript, Vitest.

---

## Baseline Notes

- Worktree: `/Users/liang/.config/superpowers/worktrees/math-im-book/selection-action-menu`
- Frontend baseline: `npm run test -- --run` passes, 69 tests.
- Backend baseline: `.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache` has one expected setup failure when `frontend/dist` is missing. Run `npm run build` before full backend verification.

## File Structure

- Modify `src/math_im_book/api/schemas.py`: add selection knowledge request schemas.
- Modify `src/math_im_book/api/app.py`: add `/api/selection/knowledge-drafts` route and prompt-kind helpers.
- Modify `src/math_im_book/services/knowledge_jobs.py`: preserve source metadata and selected text in compile prompts.
- Add `tests/api/test_selection_knowledge_api.py`: route validation and job-submission tests.
- Modify `frontend/src/services/api.ts`: add selection request/response types and API client method.
- Modify `frontend/src/stores/workspace.ts`: add composer draft state and selection generation action.
- Modify `frontend/src/components/chat/ChatComposer.vue`: bind composer textarea to store-backed draft.
- Modify `frontend/src/components/chat/ChatMessage.vue`: mark selectable message body with source metadata.
- Modify `frontend/src/components/reader/ReaderPanel.vue`: mark selectable reader content with node metadata.
- Add `frontend/src/components/common/SelectionActionMenu.vue`: global `Ctrl+Q` menu.
- Modify `frontend/src/App.vue`: mount the global selection menu.
- Add frontend tests for the new component and store/composer behavior.

---

### Task 1: Backend Selection Knowledge API

**Files:**
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/services/knowledge_jobs.py`
- Add: `tests/api/test_selection_knowledge_api.py`

- [ ] **Step 1: Write failing API schema and route tests**

Create `tests/api/test_selection_knowledge_api.py`:

```python
from fastapi.testclient import TestClient

from math_im_book.api.app import create_app
from math_im_book.domain.models import KnowledgeNode, NodeReference, ProviderProfile, ProviderResult
from math_im_book.services.knowledge_jobs import InMemoryKnowledgeJobRepository
from math_im_book.services.providers import ProviderRequest
from math_im_book.storage.markdown import MarkdownKnowledgeRepository
from math_im_book.storage.sessions import FileSessionStore, SessionMessage, SessionRecord


class CompileGateway:
    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []

    def generate(self, profile: ProviderProfile, request: ProviderRequest) -> ProviderResult:
        self.requests.append(request)
        return ProviderResult(
            output_text='{"summary":"Selection summary.","detail":"Selection detail."}',
            provider_name="test",
        )


def test_selection_knowledge_rejects_empty_text(tmp_path) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "   ",
            "prompt_kind": "definition",
            "source": {"type": "knowledge-node", "node_id": "compactness"},
        },
    )

    assert response.status_code == 422


def test_selection_knowledge_rejects_unknown_prompt_kind(tmp_path) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "compactness",
            "prompt_kind": "summary",
            "source": {"type": "knowledge-node", "node_id": "compactness"},
        },
    )

    assert response.status_code == 422


def test_selection_knowledge_from_node_submits_job_with_anchor_node(tmp_path) -> None:
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    repository.save_node(
        KnowledgeNode(
            id="compactness",
            title="Compactness",
            type="definition",
            summary="Every open cover has a finite subcover.",
            detail="Compactness detail.",
            references=[],
            incoming_references=[],
            related_session_ids=[],
            status="ready",
            symbols={},
        )
    )
    gateway = CompileGateway()
    jobs = InMemoryKnowledgeJobRepository(repository, provider_gateway=gateway, auto_start=False)
    client = TestClient(create_app(repository=repository, knowledge_job_repository=jobs))

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "Every open cover has a finite subcover.",
            "prompt_kind": "definition",
            "source": {"type": "knowledge-node", "node_id": "compactness"},
            "conversation_model": {
                "provider_type": "openai_compatible",
                "credential_id": "test",
                "model": "test-model",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["anchors"][0]["label"] == "Compactness Definition"
    job = jobs.get_job(payload["job_id"])
    assert job is not None
    assert job.selected_node_ids == ["compactness"]
    assert "Every open cover" in job.question


def test_selection_knowledge_from_chat_message_preserves_source_metadata(tmp_path) -> None:
    session_store = FileSessionStore(tmp_path / "sessions")
    session_store.save_record(
        SessionRecord(
            session_id="chat-1",
            title="Topology",
            provider_profile=ProviderProfile(
                provider_type="openai_compatible",
                model="test-model",
                credential_id="test",
            ),
            messages=[
                SessionMessage(
                    message_id="msg-a",
                    role="assistant",
                    content="Compactness answer.",
                    created_at="2026-04-19T00:00:00Z",
                )
            ],
        )
    )
    repository = MarkdownKnowledgeRepository(tmp_path / "knowledge")
    jobs = InMemoryKnowledgeJobRepository(repository, provider_gateway=CompileGateway(), auto_start=False)
    client = TestClient(
        create_app(
            repository=repository,
            session_store=session_store,
            knowledge_job_repository=jobs,
        )
    )

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "compactness preserves finite subcovers",
            "prompt_kind": "proof",
            "source": {
                "type": "chat-message",
                "session_id": "chat-1",
                "message_id": "msg-a",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    job = jobs.get_job(payload["job_id"])
    assert job is not None
    assert job.session_id == "chat-1"
    assert job.source_message_id == "msg-a"
    assert job.draft_requests[0].draft_type == "proof"


def test_selection_knowledge_returns_404_for_missing_node(tmp_path) -> None:
    client = TestClient(create_app(repository=MarkdownKnowledgeRepository(tmp_path / "knowledge")))

    response = client.post(
        "/api/selection/knowledge-drafts",
        json={
            "selected_text": "missing",
            "prompt_kind": "definition",
            "source": {"type": "knowledge-node", "node_id": "missing-node"},
        },
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/pytest tests/api/test_selection_knowledge_api.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: fail because `/api/selection/knowledge-drafts` does not exist and schemas are missing.

- [ ] **Step 3: Add schemas**

In `src/math_im_book/api/schemas.py`, add near request schemas:

```python
class SelectionKnowledgeSourceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["chat-message", "knowledge-node"]
    session_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None
    message_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None
    node_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] | None = None


class SelectionKnowledgeDraftRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    prompt_kind: Literal["definition", "intuition_node", "example", "proof"]
    source: SelectionKnowledgeSourceSchema
    conversation_model: DefaultModelSelectionSchema | None = None
```

- [ ] **Step 4: Extend knowledge job prompt source material**

In `src/math_im_book/services/knowledge_jobs.py`, add a `selection_source_text` field to `KnowledgeJobRecord` and `submit_compile_job`, then include it in `_compiled_content()` user message:

```python
selection_source_text: str = ""
```

Add parameter:

```python
selection_source_text: str | None = None,
```

Store:

```python
selection_source_text=selection_source_text or "",
```

Append to provider prompt:

```python
+ (
    f"\nSelected source text:\n{job.selection_source_text}\n"
    if job.selection_source_text
    else ""
)
```

- [ ] **Step 5: Add route helpers and endpoint**

In `src/math_im_book/api/app.py`, import `SelectionKnowledgeDraftRequestSchema` and add helper constants/functions near existing draft compile route:

```python
_SELECTION_PROMPT_META = {
    "definition": ("Definition", "definition", "Turn the selected text into a definition knowledge node."),
    "intuition_node": ("Intuition", "atomic", "Turn the selected text into an intuition knowledge node."),
    "example": ("Application Example", "atomic", "Turn the selected text into an application example knowledge node."),
    "proof": ("Proof", "proof", "Turn the selected text into a proof knowledge node."),
}


def _selection_draft_request(prompt_kind: str, selected_text: str) -> PendingDraftRequest:
    label, draft_type, reason = _SELECTION_PROMPT_META[prompt_kind]
    title_seed = selected_text.strip().splitlines()[0][:48].strip(" .,:;，。；：")
    title = f"{title_seed} {label}" if title_seed else label
    return PendingDraftRequest(title=title, draft_type=draft_type, reason=reason)
```

Add endpoint before regenerate route:

```python
@app.post("/api/selection/knowledge-drafts", response_model=KnowledgeJobSchema)
def compile_selection_knowledge(
    payload: SelectionKnowledgeDraftRequestSchema,
) -> KnowledgeJobSchema:
    source = payload.source
    session_id: str | None = None
    source_message_id: str | None = None
    selected_node_ids: list[str] = []
    symbol_constraints: dict[str, str] = {}
    provider_profile = None

    if source.type == "knowledge-node":
        if source.node_id is None:
            raise HTTPException(status_code=400, detail="node_id is required")
        try:
            node = repository.get_node(source.node_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Knowledge node not found") from None
        selected_node_ids = [node.id]
    else:
        if source.session_id is None or source.message_id is None:
            raise HTTPException(status_code=400, detail="session_id and message_id are required")
        record = sessions.load_record(source.session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        message = next((item for item in record.messages if item.message_id == source.message_id), None)
        if message is None:
            raise HTTPException(status_code=404, detail="Message not found")
        session_id = record.session_id
        source_message_id = message.message_id
        selected_node_ids = list(message.assistant_context.referenced_node_ids)
        symbol_constraints = dict(record.branch_context.active_symbols)
        provider_profile = record.provider_profile

    if payload.conversation_model is not None:
        provider_profile = _resolve_provider_profile_from_selection(
            selection=payload.conversation_model,
            credential_registry=credentials,
            provider_options_payload=provider_options.load(),
        )

    draft = _selection_draft_request(payload.prompt_kind, payload.selected_text)
    anchor = AnswerAnchor(
        anchor_id=_slugify(draft.title),
        label=draft.title,
        status="pending",
        node_id=None,
    )
    job = resolved_knowledge_job_repository.submit_compile_job(
        session_id=session_id,
        source_message_id=source_message_id,
        question=f"{draft.reason}\n\nSelected text:\n{payload.selected_text}",
        anchors=[anchor],
        selected_node_ids=selected_node_ids,
        draft_requests=[draft],
        provider_profile=provider_profile,
        symbol_constraints=symbol_constraints,
        selection_source_text=payload.selected_text,
    )
    return KnowledgeJobSchema.model_validate(
        {
            "job_id": job.job_id,
            "status": job.status,
            "anchors": [_answer_anchor_to_schema(anchor).model_dump() for anchor in job.anchors],
            "error_message": job.error_message,
        }
    )
```

- [ ] **Step 6: Run backend task tests**

Run:

```bash
.venv/bin/pytest tests/api/test_selection_knowledge_api.py tests/services/test_knowledge_jobs.py -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: pass.

- [ ] **Step 7: Commit backend API task**

Run:

```bash
git add src/math_im_book/api/schemas.py src/math_im_book/api/app.py src/math_im_book/services/knowledge_jobs.py tests/api/test_selection_knowledge_api.py
git commit -m "feat: add selection knowledge draft API"
```

---

### Task 2: Frontend API, Store, and Composer Draft State

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Modify: `frontend/src/stores/workspace.test.ts`
- Modify: `frontend/src/components/chat/ChatComposer.vue`
- Modify: `frontend/src/components/chat/ChatComposer.test.ts`

- [ ] **Step 1: Write failing store and composer tests**

In `frontend/src/stores/workspace.test.ts`, add tests that verify `setDraftQuestion()` changes `draftQuestion`, and `generateKnowledgeFromSelection()` calls API with provider selection and refreshes outline on ready anchor.

In `frontend/src/components/chat/ChatComposer.test.ts`, add a test that calls `store.setDraftQuestion('请解释...')`, verifies the textarea displays it, submits, emits `ask`, and clears the textarea.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
npm run test -- --run src/stores/workspace.test.ts src/components/chat/ChatComposer.test.ts
```

Expected: fail because `draftQuestion`, `setDraftQuestion`, and selection API are missing.

- [ ] **Step 3: Add API types and client method**

In `frontend/src/services/api.ts`, add:

```ts
export type SelectionSourceType = 'chat-message' | 'knowledge-node';
export type SelectionKnowledgePromptKind = 'definition' | 'intuition_node' | 'example' | 'proof';

export interface SelectionKnowledgeSource {
  type: SelectionSourceType;
  session_id?: string | null;
  message_id?: string | null;
  node_id?: string | null;
}

export interface SelectionKnowledgeRequest {
  selected_text: string;
  prompt_kind: SelectionKnowledgePromptKind;
  source: SelectionKnowledgeSource;
  conversation_model?: DefaultModelSelection;
}
```

Add method:

```ts
async compileSelectionKnowledge(payload: SelectionKnowledgeRequest): Promise<KnowledgeJob> {
  const response = await client.post<KnowledgeJob>('/selection/knowledge-drafts', payload);
  return response.data;
},
```

- [ ] **Step 4: Add store draft state and action**

In `frontend/src/stores/workspace.ts`, add `draftQuestion = ref('')`, `setDraftQuestion(question: string)`, export both, and update `newSession()` to leave `draftQuestion` untouched unless explicitly cleared by caller.

Add selection payload type:

```ts
export interface SelectionActionPayload {
  text: string;
  sourceType: 'chat-message' | 'knowledge-node';
  messageId?: string;
  nodeId?: string;
}
```

Add action:

```ts
async function generateKnowledgeFromSelection(
  payload: SelectionActionPayload,
  promptKind: SelectionKnowledgePromptKind
) {
  loading.value = true;
  errorMessage.value = null;
  try {
    const conversationModel =
      selectedProviderProfile.value
        ? {
            ...(selectedProviderProfile.value.provider_id
              ? { provider_id: selectedProviderProfile.value.provider_id }
              : {}),
            provider_type: selectedProviderProfile.value.provider_type,
            credential_id: selectedProviderProfile.value.credential_id,
            model: selectedProviderProfile.value.model,
          }
        : undefined;
    const job = await api.compileSelectionKnowledge({
      selected_text: payload.text,
      prompt_kind: promptKind,
      source:
        payload.sourceType === 'knowledge-node'
          ? { type: 'knowledge-node', node_id: payload.nodeId || currentNode.value?.id || null }
          : {
              type: 'chat-message',
              session_id: currentSession.value?.session_id || null,
              message_id: payload.messageId || null,
            },
      conversation_model: conversationModel,
    });
    await pollStandaloneKnowledgeJob(job.job_id, 0);
  } catch (error) {
    errorMessage.value = 'Failed to start knowledge note generation.';
    console.error('Failed to generate knowledge from selection:', error);
  } finally {
    loading.value = false;
  }
}
```

Add `pollStandaloneKnowledgeJob(jobId: string, attempt: number)` that calls `api.getKnowledgeJob()`, refreshes outline on completed/ready anchors, selects first ready node, and retries while pending/running using the existing constants.

- [ ] **Step 5: Bind ChatComposer to store draft**

Replace local `question = ref('')` with a computed v-model over `draftQuestion`, and clear via `store.setDraftQuestion('')` after emitting ask.

- [ ] **Step 6: Run frontend task tests**

Run:

```bash
npm run test -- --run src/stores/workspace.test.ts src/components/chat/ChatComposer.test.ts
```

Expected: pass.

- [ ] **Step 7: Commit frontend store/API task**

Run:

```bash
git add frontend/src/services/api.ts frontend/src/stores/workspace.ts frontend/src/stores/workspace.test.ts frontend/src/components/chat/ChatComposer.vue frontend/src/components/chat/ChatComposer.test.ts
git commit -m "feat: add selection draft store flow"
```

---

### Task 3: Selection Action Menu UI

**Files:**
- Add: `frontend/src/components/common/SelectionActionMenu.vue`
- Add: `frontend/src/components/common/SelectionActionMenu.test.ts`
- Modify: `frontend/src/components/chat/ChatMessage.vue`
- Modify: `frontend/src/components/chat/ChatMessage.test.ts`
- Modify: `frontend/src/components/reader/ReaderPanel.vue`
- Modify: `frontend/src/components/reader/ReaderPanel.test.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Write failing component tests**

Create `SelectionActionMenu.test.ts` with tests that mock `window.getSelection()` for allowed source elements, dispatch `keydown` with `ctrlKey: true, key: 'q'`, assert menu opens, click `怎么理解`, and assert store draft is set. Add tests for `Esc`, outside click, and knowledge-node `继续问` calling `newSession()`.

Update `ChatMessage.test.ts` to assert rendered content wrapper has `data-selection-source="chat-message"` and `data-message-id`.

Update `ReaderPanel.test.ts` to assert reader content wrapper has `data-selection-source="knowledge-node"` and `data-node-id`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
npm run test -- --run src/components/common/SelectionActionMenu.test.ts src/components/chat/ChatMessage.test.ts src/components/reader/ReaderPanel.test.ts
```

Expected: fail because component and source markers are missing.

- [ ] **Step 3: Add source markers**

In `ChatMessage.vue`, wrap the `MarkdownContent` area for real message content with:

```vue
<div
  :data-selection-source="'chat-message'"
  :data-message-id="message.message_id"
>
  <MarkdownContent v-if="!isThinking" :content="message.content" />
</div>
```

Keep the thinking indicator outside or without selectable metadata.

In `ReaderPanel.vue`, add metadata to the markdown detail wrapper:

```vue
<div
  class="font-serif text-[17px] leading-relaxed text-on-surface"
  data-selection-source="knowledge-node"
  :data-node-id="node.id"
>
  <MarkdownContent :content="markdownDetail" />
</div>
```

- [ ] **Step 4: Implement `SelectionActionMenu.vue`**

Implement a focused component that:

- Registers document `keydown`, `pointerdown`, and `selectionchange` listeners on mount.
- Resolves selection source by walking from `selection.anchorNode` and `selection.focusNode` to a common allowed ancestor.
- Ignores textarea/input/select/button/contenteditable targets.
- Opens only for non-empty text.
- Uses `range.getBoundingClientRect()` for positioning and clamps the popup.
- Renders primary menu and active submenu.
- Calls `store.setDraftQuestion()` for chat follow-ups.
- Calls `store.newSession()` then `store.setDraftQuestion()` for knowledge-node follow-ups.
- Calls `store.generateKnowledgeFromSelection()` for knowledge-node presets.

Prompt composer helper:

```ts
const followUpPrompts = {
  understand: '请解释我该如何理解下面选中的内容：',
  intuition_question: '请给出下面选中内容的形象解释和直觉图景：',
  detail: '请具体说明下面选中内容的关键步骤和容易误解的点：',
} as const;

const composeFollowUp = (prompt: string, text: string) => `${prompt}\n\n> ${text.trim()}`;
```

- [ ] **Step 5: Mount in `App.vue`**

Import and mount:

```vue
<SelectionActionMenu />
```

near the end of the app shell so it can overlay chat and reader content.

- [ ] **Step 6: Run UI task tests**

Run:

```bash
npm run test -- --run src/components/common/SelectionActionMenu.test.ts src/components/chat/ChatMessage.test.ts src/components/reader/ReaderPanel.test.ts
```

Expected: pass.

- [ ] **Step 7: Commit selection menu UI task**

Run:

```bash
git add frontend/src/components/common/SelectionActionMenu.vue frontend/src/components/common/SelectionActionMenu.test.ts frontend/src/components/chat/ChatMessage.vue frontend/src/components/chat/ChatMessage.test.ts frontend/src/components/reader/ReaderPanel.vue frontend/src/components/reader/ReaderPanel.test.ts frontend/src/App.vue
git commit -m "feat: add ctrl q selection action menu"
```

---

### Task 4: Integration Verification and Polish

**Files:**
- Modify only files needed to fix integration issues found by verification.

- [ ] **Step 1: Run full frontend tests**

Run:

```bash
npm run test -- --run
```

Expected: pass.

- [ ] **Step 2: Build frontend**

Run:

```bash
npm run build
```

Expected: build succeeds and emits `frontend/dist`.

- [ ] **Step 3: Run full backend tests**

Run:

```bash
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache
```

Expected: pass now that `frontend/dist` exists.

- [ ] **Step 4: Manual smoke check**

Run:

```bash
.venv/bin/uvicorn math_im_book.api.app:create_app --factory --reload
```

Open the served app, select text in a chat message and reader node, press `Ctrl+Q`, confirm menu opens, follow-up presets fill the composer, outside click closes the menu, and knowledge-node presets submit a job without filling the composer.

- [ ] **Step 5: Commit any integration fixes**

If verification required code fixes, commit them:

```bash
git add <changed-files>
git commit -m "fix: polish selection action menu integration"
```

If no fixes were needed, do not create an empty commit.

