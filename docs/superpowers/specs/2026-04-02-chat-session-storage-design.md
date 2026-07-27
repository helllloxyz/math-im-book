# Chat Session Storage Redesign

## 1. Context

The current chat storage already writes one JSON file per session under `data/chats/sessions/`, but the file mixes session metadata, branch metadata, and full message history in one document. That shape is workable for a prototype, but it is a poor fit for the product constraints now confirmed for branching and editing behavior.

The confirmed behavior is:

1. Chat history is append-only once committed.
2. Only the last user turn may be edited.
3. Only the last assistant answer may be regenerated.
4. Forking must not copy historical messages.
5. A fork anchor is immutable after the fork is created.
6. There is no compatibility requirement with the old storage format.

This design replaces the current session file format with a directory-based storage model optimized for simple structure, stable fork semantics, and cheap append operations.

## 2. Design Goal

The storage model should satisfy four properties:

1. Keep committed history immutable.
2. Keep the editable tail isolated from committed history.
3. Make fork creation O(1) by reusing parent history through anchors instead of copying messages.
4. Keep common reads fast enough for session listing, session loading, and branch tree rendering.

## 3. Rejected Directions

### 3.1 Single JSON file per session

This keeps the fewest files, but every committed message append rewrites the whole file. It also couples immutable history to the editable tail and makes fork reuse less explicit.

### 3.2 Global event log for all chats

This is flexible, but too heavy for the current product scope. It adds replay and projection complexity without clear product value yet.

## 4. Chosen Storage Shape

The system should use a per-session directory with three files plus one global index.

```text
data/chats/
  sessions_index.json
  sessions/
    <session_id>/
      session.json
      messages.jsonl
      working_turn.json
```

### 4.1 `session.json`

This file stores durable session metadata and branch metadata only. It does not store message history.

Suggested shape:

```json
{
  "version": 2,
  "session_id": "chat-root",
  "title": "Linear Map Basics",
  "icon": "function",
  "created_at": "2026-04-02T09:00:00Z",
  "updated_at": "2026-04-02T09:12:00Z",
  "message_count": 8,
  "last_committed_message_id": "msg_0008",
  "provider_profile": {
    "provider_type": "gemini",
    "model": "gemini-2.5-flash",
    "credential_id": "gemini-main",
    "base_url": null,
    "options": {}
  },
  "branch": {
    "branch_id": "branch_ab12cd34",
    "parent_session_id": "chat-parent",
    "root_session_id": "chat-root",
    "focus_question": "Can we generalize this?",
    "fork_anchor": {
      "type": "message",
      "message_id": "msg_0008",
      "node_id": null,
      "source_message_id": null
    },
    "active_node_ids": ["linear-map"],
    "summary_node_ids": ["vector-space"],
    "active_symbols": {
      "T": "linear map from V to W"
    }
  }
}
```

### 4.2 `messages.jsonl`

This file stores committed history only. It is append-only and never rewritten for ordinary message writes.

Each line is one committed message:

```json
{"message_id":"msg_0007","role":"user","content":"What is a linear map?","created_at":"2026-04-02T09:10:00Z"}
{"message_id":"msg_0008","role":"assistant","content":"A linear map preserves addition and scalar multiplication.","provider_name":"gemini","raw_response_meta":{},"assistant_context":{"action_type":"reuse_answer","referenced_node_ids":["linear-map"],"symbol_conflicts":[],"alignment_notes":[],"compact_summary":null},"created_at":"2026-04-02T09:10:02Z"}
```

### 4.3 `working_turn.json`

This file stores the only mutable portion of a session: the last turn being edited or regenerated.

Suggested shape:

```json
{
  "state": "user_editing | awaiting_answer | answered",
  "user_message": {
    "message_id": "draft_user_01",
    "content": "Can we express this with matrices?",
    "edited_from_message_id": "msg_0007",
    "created_at": "2026-04-02T09:11:00Z"
  },
  "assistant_message": {
    "message_id": "draft_assistant_01",
    "content": null,
    "regenerated_from_message_id": "msg_0008",
    "provider_name": null,
    "raw_response_meta": {},
    "assistant_context": null,
    "created_at": null
  }
}
```

If there is no mutable tail, the file may be absent or contain `null`. The implementation should pick one rule and apply it consistently.

### 4.4 `sessions_index.json`

This file is a lightweight summary index for session listing and tree rendering. It avoids reading every session directory during `GET /api/sessions`.

Each entry should store only list-level information:

```json
{
  "sessions": [
    {
      "session_id": "chat-root",
      "title": "Linear Map Basics",
      "icon": "function",
      "updated_at": "2026-04-02T09:12:00Z",
      "message_count": 8,
      "last_preview": "A linear map preserves addition...",
      "parent_session_id": null,
      "root_session_id": "chat-root"
    }
  ]
}
```

## 5. Field Design

### 5.1 Session fields

The session metadata should include:

- `version`
- `session_id`
- `title`
- `icon`
- `created_at`
- `updated_at`
- `message_count`
- `last_committed_message_id`
- `provider_profile`
- `branch`

### 5.2 Message fields

Every committed message must include:

- `message_id`
- `role`
- `content`
- `created_at`

Assistant messages may also include:

- `provider_name`
- `raw_response_meta`
- `assistant_context`

The `message_id` must be stable and globally unique enough for fork anchoring and turn editing. Message positions must not be used as storage identifiers.

### 5.3 Branch fields

The old `branch_context` shape should be replaced internally and externally by `branch`.

Suggested branch fields:

- `branch_id`
- `parent_session_id`
- `root_session_id`
- `focus_question`
- `fork_anchor`
- `active_node_ids`
- `summary_node_ids`
- `active_symbols`

The `fork_anchor` should be a structured object rather than multiple partially overlapping top-level fields:

```json
{
  "type": "message | node",
  "message_id": "msg_0008",
  "node_id": "linear-map",
  "source_message_id": "msg_0008"
}
```

Rules:

1. Forks anchored on conversation state use `type="message"` and `message_id`.
2. Forks anchored on knowledge nodes use `type="node"` and `node_id`.
3. Node-based forks should also store `source_message_id` when the node came from an assistant answer, so the parent-history cutoff is stable.

## 6. Fork Semantics

Forking should create a new session directory with:

- its own `session.json`
- an empty `messages.jsonl`
- no committed history copied from the parent
- an empty or absent `working_turn.json`

The child session stores only branch metadata pointing at the parent and the immutable fork anchor.

Fork rules:

1. Fork creation must be O(1) with no historical message copying.
2. A fork anchor must be immutable once written.
3. A fork may only target committed history, never `working_turn`.
4. A child session's own later edits or regenerations must not mutate parent history.

## 7. Read Semantics

The API should expose the session's visible history, not only its locally committed messages.

To build visible history for a session:

1. Load the current session metadata.
2. If there is a parent session, recursively load the parent's visible committed history.
3. Cut the inherited parent history at the child's immutable fork anchor.
4. Append the child's committed `messages.jsonl`.
5. Append the child's `working_turn` if present.

This creates a clear distinction between:

- `committed local history`
- `inherited visible history`
- `mutable tail`

The API should use visible history when returning session detail to the frontend.

## 8. Write Semantics

### 8.1 Ordinary ask flow

The system should:

1. Write the new user turn into `working_turn.json`.
2. Generate the assistant answer into `working_turn.json`.
3. Commit both messages by appending them to `messages.jsonl`.
4. Clear `working_turn.json`.
5. Update `session.json`.
6. Update `sessions_index.json`.

### 8.2 Edit the last user message

The system should only allow editing the latest unfinished or reconstructed tail. It must not rewrite committed historical lines in `messages.jsonl`.

If the current last turn is still mutable, update `working_turn.json` directly.

### 8.3 Regenerate the last assistant answer

Regeneration should operate only on `working_turn.json`. The regenerated answer replaces the draft assistant payload there until committed.

### 8.4 Commit boundary

Once a turn is committed into `messages.jsonl`, it becomes immutable storage history. Any later user-visible change must create a new mutable tail rather than patch a committed line.

## 9. Performance Expectations

The design should keep the following operations cheap:

1. Append a committed turn without rewriting large history files.
2. List sessions without scanning every message file.
3. Create forks without copying historical payloads.

Acceptable tradeoff:

Loading one session may require parent-chain reconstruction, but this is acceptable because:

- branch depth is expected to stay modest
- the inherited history is immutable and therefore cacheable
- session listing remains cheap through `sessions_index.json`

An in-memory cache keyed by `session_id` and `updated_at` is acceptable for visible-history reconstruction, but it is an optimization rather than a requirement of the first implementation.

## 10. API Impact

There is no compatibility requirement for the old storage or old API fork fields.

The API should move directly to the new model:

1. Session responses should expose `branch`, not `branch_context`.
2. Message payloads should expose `message_id` and `created_at`.
3. Fork requests should accept stable anchor identifiers, not message indexes.
4. Session detail responses should return visible history including inherited committed messages and the mutable tail.

## 11. Migration Position

No backward-compatibility path is required. The codebase should be updated directly to the new storage and schema model.

This means:

1. The current `FileSessionStore` can be reshaped around session directories.
2. The existing single-file session JSON format does not need fallback readers.
3. Tests should be updated to target the new directory structure and fork semantics only.

## 12. Testing Requirements

The implementation must cover:

1. Creating a fresh session directory structure.
2. Appending committed messages to `messages.jsonl`.
3. Reading visible history from a root session.
4. Reading visible history from a forked child session.
5. Editing only the mutable tail.
6. Regenerating only the mutable tail assistant answer.
7. Rejecting forks from mutable tail state.
8. Listing sessions from `sessions_index.json`.
9. Deleting sessions while preserving child-branch constraints.

## 13. Final Decision

The chat storage should be redesigned as a per-session directory with:

- immutable committed history in `messages.jsonl`
- mutable tail state in `working_turn.json`
- durable metadata in `session.json`
- lightweight session listing data in `sessions_index.json`

Forks should reuse parent history through immutable anchors and should never copy committed messages.
