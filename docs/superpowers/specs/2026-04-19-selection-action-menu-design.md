# Selection Action Menu Design

## Summary

Add a selection-first action menu for chat messages and knowledge node content. The user selects text, presses `Ctrl+Q`, and chooses from a two-level menu that either fills the chat composer with a prompt draft or starts a background knowledge-node generation job.

This avoids browser context-menu conflicts and keeps the two actions distinct:

- Continue asking: compose a draft question for the user to edit and send manually.
- Knowledge node: directly submit a compile job from the selected text.

## Goals

- Open a lightweight popup from selected text using `Ctrl+Q`.
- Support selections inside chat message content and reader knowledge-node content.
- Close the popup when the user clicks blank space, presses `Esc`, loses the selection, or changes context.
- Provide two-level prompt presets to reduce manual typing.
- Keep continuing questions editable and manually sent.
- Generate knowledge nodes directly without creating a fake chat turn.

## Non-Goals

- Do not replace browser right-click behavior.
- Do not auto-send follow-up questions.
- Do not support arbitrary page selections outside chat messages and reader content.
- Do not introduce a full message or node selection model; the feature is based on text selection.

## User Interaction

The user selects text in either:

- A chat message body.
- The current knowledge node body in the reader panel.

Pressing `Ctrl+Q` opens a floating menu near the selection. The menu has a left column for primary actions and a right column for prompt presets.

Primary actions:

- `继续问`
- `知识节点`

`继续问` presets:

- `怎么理解`
- `形象解释`
- `具体说明`

`知识节点` presets:

- `定义`
- `形象解释`
- `应用例子`
- `证明`

When the user chooses a `继续问` preset, the app writes a prompt draft into the composer and does not send it. For chat-message selections, the draft goes into the current conversation. For knowledge-node selections, the app starts a new conversation state first, then writes the draft into the composer.

When the user chooses a `知识节点` preset, the app submits a background knowledge generation job immediately. It does not write into the composer.

## Prompt Drafts

Prompt preset ids should be stable and independent of Chinese UI labels.

Continue asking:

- `understand`: `请解释我该如何理解下面选中的内容：`
- `intuition_question`: `请给出下面选中内容的形象解释和直觉图景：`
- `detail`: `请具体说明下面选中内容的关键步骤和容易误解的点：`

Knowledge nodes:

- `definition`: `将下面选中内容整理为定义型知识节点。`
- `intuition_node`: `将下面选中内容整理为形象解释型知识节点。`
- `example`: `将下面选中内容整理为应用例子型知识节点。`
- `proof`: `将下面选中内容整理为证明型知识节点。`

The composed follow-up draft should be concise and editable:

```text
请解释我该如何理解下面选中的内容：

> selected text
```

Knowledge-node generation should pass the selected text and prompt kind as structured fields, not only as a preformatted natural-language prompt.

## Frontend Design

Add a global `SelectionActionMenu` component under `App.vue`.

Responsibilities:

- Listen for `Ctrl+Q` and `Meta+Q`.
- Read `window.getSelection()`.
- Validate that the selection is non-empty and belongs to an allowed source region.
- Capture source metadata from DOM data attributes.
- Position the menu near the selected range.
- Handle outside click, `Esc`, scroll/context changes, and action selection.

Allowed source regions:

- Chat message content: `data-selection-source="chat-message"` plus `data-message-id`.
- Reader node content: `data-selection-source="knowledge-node"` plus `data-node-id`.

Selection payload:

```ts
interface SelectionActionPayload {
  text: string;
  sourceType: 'chat-message' | 'knowledge-node';
  messageId?: string;
  nodeId?: string;
  rect: DOMRect;
}
```

The component should ignore selections inside the composer textarea, settings controls, sidebars, and unrelated page chrome.

`ChatComposer` should use a store-backed draft value rather than only local state:

- Add `draftQuestion` to the workspace store.
- Add `setDraftQuestion(question: string)`.
- Bind the composer textarea with a computed v-model.
- On submit, clear `draftQuestion`.

Action behavior:

- Chat source + `继续问`: call `setDraftQuestion(composePrompt(...))`.
- Knowledge-node source + `继续问`: call `newSession()`, then `setDraftQuestion(composePrompt(...))`.
- Any source + `知识节点`: call `generateKnowledgeFromSelection(payload, presetId)`.

## Backend/API Design

Add a dedicated endpoint:

```http
POST /api/selection/knowledge-drafts
```

Request:

```json
{
  "selected_text": "...",
  "prompt_kind": "definition",
  "source": {
    "type": "knowledge-node",
    "session_id": null,
    "message_id": null,
    "node_id": "compactness"
  },
  "conversation_model": {
    "provider_type": "openai_compatible",
    "credential_id": "main",
    "model": "deepseek-chat"
  }
}
```

Response:

```json
{
  "job_id": "...",
  "status": "pending",
  "anchors": []
}
```

Validation:

- `selected_text` must be non-empty after trimming.
- `prompt_kind` must be one of `definition`, `intuition_node`, `example`, `proof`.
- `source.type` must be `chat-message` or `knowledge-node`.
- `knowledge-node` sources require `node_id`.
- `chat-message` sources require `session_id` and `message_id`.
- Referenced sessions, messages, and nodes must exist.

Implementation should submit a compile job through `KnowledgeJobRepository.submit_compile_job()`. Knowledge-node selections should pass `selected_node_ids=[node_id]`. Chat-message selections should use node ids referenced by the source message when available; otherwise, allow an empty node list while preserving session/message source metadata.

The compile job should create one draft candidate from the prompt kind:

- `definition`: draft type `definition`
- `intuition_node`: draft type `atomic`
- `example`: draft type `atomic`
- `proof`: draft type `proof`

The generated content must include the selected text as source material. The prompt kind should guide title, summary, detail, and node type.

## Store Flow

Add workspace store action:

```ts
async function generateKnowledgeFromSelection(payload, promptKind)
```

It should:

- Call the new API with selected text, prompt kind, source metadata, and current selected provider profile.
- Store or surface a lightweight pending state.
- Reuse existing knowledge job polling behavior where possible.
- Refresh outline after completion.
- Select the created node when the job resolves to a ready anchor with `node_id`.
- Set `errorMessage` on submission or polling failure.

If existing polling is tightly coupled to assistant messages, extract a small helper that can poll a knowledge job without requiring a session message id.

## UI State and Accessibility

- The menu should be keyboard dismissible with `Esc`.
- It should not trap focus unless later expanded into a richer command palette.
- Buttons should have clear text labels and `type="button"`.
- The popup should clamp within the viewport.
- `Ctrl+Q` should call `preventDefault()` only after a valid selection payload is found.
- Empty selection should do nothing and leave browser behavior alone.

## Error Handling

Frontend:

- If selection cannot be resolved to an allowed source, do nothing.
- If knowledge generation submission fails, show `errorMessage`.
- If the job fails, show the existing knowledge job failure message style.

Backend:

- Return `400` for invalid request payloads.
- Return `404` for missing referenced node/session/message.
- Return `503` or existing provider error behavior when compile cannot start because provider configuration is missing.

## Testing

Frontend tests:

- `Ctrl+Q` opens the menu for chat-message selections.
- `Ctrl+Q` opens the menu for reader-node selections.
- Empty selections and selections outside allowed regions do not open the menu.
- Outside click and `Esc` close the menu.
- Chat-message `继续问` fills the current composer.
- Knowledge-node `继续问` calls `newSession()` and fills the composer.
- `知识节点` presets call the store generation action and do not fill the composer.
- Composer submits and clears a store-backed draft.

Backend tests:

- New API rejects empty selected text.
- New API rejects unsupported prompt kinds.
- Knowledge-node source submits a job with selected node ids.
- Chat-message source submits a job with session/message source metadata.
- Missing node/session/message references return `404`.

## Open Implementation Notes

- The existing `KnowledgeJobRepository` may need a small extension so selection-based jobs can preserve source metadata and selected text cleanly.
- Existing job polling in the store is currently oriented around assistant message anchors. If reuse is awkward, introduce a separate polling path for selection jobs instead of forcing fake message ids into the flow.
- The visual design should match the app's existing dark/light material style, with compact two-column menu dimensions and no right-click dependency.
