# Explorer Directory Tree Design

## Context

The product needs a VS Code Explorer style organization layer for both chats and knowledge nodes. The current implementation has two partial trees:

- Chat sessions expose fork relationships through `branch.parent_session_id` and `child_session_ids`.
- Knowledge nodes expose a loose hierarchy through `parent_id`.

Those relationships are not the same as a user-managed directory tree. A user should be able to create folders, move chats or knowledge nodes into folders, and reorganize the left rail without changing the underlying session history, fork graph, Markdown file path, or knowledge references.

`tree_view.html` is only a visual reference for the directory portion: compact rows, chevrons, folder/file icons, nested indentation, hover actions, and an active-row marker.

## Goals

1. Add a user-managed Explorer directory tree for conversations.
2. Add a user-managed Explorer directory tree for knowledge nodes.
3. Let the agent assign default knowledge locations asynchronously.
4. Keep physical storage paths stable.
5. Keep fork relationships, knowledge hierarchy, references, and Explorer folders as separate concepts.
6. Support manual correction by the user without the agent immediately overriding it.

## Non-Goals

1. Do not move Markdown files under nested filesystem folders.
2. Do not replace session fork metadata.
3. Do not make `KnowledgeNode.parent_id` carry UI folder semantics.
4. Do not require drag and drop in the first implementation.
5. Do not redesign the whole shell from `tree_view.html`; only the directory tree interaction is in scope.

## Recommended Approach

Use a dedicated Explorer index with stable folder ids and stable item locations.

The item id remains the durable identity:

- `session_id` for chats.
- `node_id` for knowledge nodes.

The Explorer path is mutable presentation and organization metadata. It must not be used as the canonical identity for links, citations, fork anchors, session inheritance, or Markdown storage.

## Data Model

Add two storage concepts.

```text
ExplorerFolder
  folder_id: string
  scope: "sessions" | "knowledge"
  name: string
  parent_folder_id: string | null
  created_at: string
  updated_at: string
  sort_order: number

ExplorerItemLocation
  item_type: "session" | "knowledge_node"
  item_id: string
  folder_id: string | null
  sort_order: number
  path_cached: string
  location_source: "user" | "agent" | "system"
  user_locked: boolean
  updated_at: string
```

`folder_id = null` means the item is at the scope root. A system-created `Unsorted` folder may also exist for items the agent cannot place confidently.

`path_cached` is a read optimization and display aid, not the source of truth. The folder tree remains authoritative.

`user_locked` prevents asynchronous agent organization from moving a user-corrected item. The first version can set it to `true` for any user-initiated move.

## Storage

Use file-backed storage consistent with the rest of the app.

Preferred shape:

```text
data/explorer/
  index.json
```

Suggested payload:

```json
{
  "version": 1,
  "folders": [
    {
      "folder_id": "folder-linear-algebra",
      "scope": "knowledge",
      "name": "Linear Algebra",
      "parent_folder_id": null,
      "created_at": "2026-04-19T00:00:00Z",
      "updated_at": "2026-04-19T00:00:00Z",
      "sort_order": 1000
    }
  ],
  "locations": [
    {
      "item_type": "knowledge_node",
      "item_id": "linear-map",
      "folder_id": "folder-linear-algebra",
      "sort_order": 1000,
      "path_cached": "/Linear Algebra/Linear Map",
      "location_source": "agent",
      "user_locked": false,
      "updated_at": "2026-04-19T00:00:00Z"
    }
  ]
}
```

This avoids rewriting:

```text
data/knowledge/<node_id>.md
data/chats/sessions/<session_id>/
```

Existing knowledge Markdown front matter may later include a cached `folder_id` or `path`, but that cache must not become authoritative.

## Relationship Boundaries

Keep these relationships separate:

- `SessionBranch.parent_session_id`: automatic fork parent.
- Explorer session location: manual or agent-suggested folder placement.
- `KnowledgeNode.parent_id`: semantic knowledge parent, if used by planning or book structure.
- Explorer knowledge location: UI folder placement.
- `references` and `incoming_references`: knowledge graph links.
- Physical file path: stable persistence implementation detail.

This separation prevents a user moving a chat in the left rail from changing fork behavior, and prevents a knowledge node being reorganized from breaking references or citations.

## API Design

Add Explorer endpoints while keeping existing session and outline endpoints for compatibility.

```text
GET    /api/explorer/sessions
GET    /api/explorer/knowledge
POST   /api/explorer/folders
PATCH  /api/explorer/folders/{folder_id}
DELETE /api/explorer/folders/{folder_id}
PATCH  /api/explorer/items/{item_type}/{item_id}/location
```

`GET /api/explorer/sessions` returns a tree containing folders and session leaf items. Session leaf payloads should include the same list-level data currently shown by `GET /api/sessions`: title, icon, message count, last message preview, branch depth, and fork metadata.

`GET /api/explorer/knowledge` returns a tree containing folders and knowledge node leaf items. Knowledge leaf payloads should include the same list-level data currently shown by `GET /api/outline`: title, type, summary, status, and node id.

Folder creation accepts:

```json
{
  "scope": "knowledge",
  "name": "Linear Algebra",
  "parent_folder_id": null
}
```

Item move accepts:

```json
{
  "folder_id": "folder-linear-algebra",
  "sort_order": 2000,
  "location_source": "user"
}
```

The backend should reject moves to folders in the wrong scope.

Folder names must be unique within the same `scope` and `parent_folder_id`.
The same name may appear in different parent folders or different scopes.

Folder deletion should be conservative in the first version:

- Reject deleting a non-empty folder.
- Allow deleting an empty folder.

Move-with-children and recursive delete can be added later.

## UI Design

Use one reusable Explorer tree component for both scopes.

Each row follows the directory reference:

```text
chevron | folder/file/type icon | title | hover actions
```

Rows should be compact, stable-height, and support:

- Expand and collapse folders.
- Select item.
- Create folder from section header or folder row.
- Create new chat from the sessions section.
- Move item through a first-version menu or dialog.
- Rename folder.
- Delete empty folder.

Active rows should use a subtle background and a left-side active indicator. The visual treatment should be adapted to the current design system rather than copying the full `tree_view.html` shell.

Creating a knowledge node from the Explorer is out of scope for the first implementation. The first version should move existing generated nodes; creation remains handled by chat selection, suggested drafts, and knowledge jobs.

The first implementation can avoid drag and drop. A menu-based move keeps behavior testable and avoids introducing a frontend interaction dependency before the data model is stable.

## Session Explorer Behavior

Chats can be manually organized into folders.

Forks remain automatic. A forked session should inherit the parent session folder by default unless the user chooses a different location. This keeps fork creation predictable while still allowing manual organization.

The UI may show fork metadata as secondary information, but Explorer indentation must represent folders, not fork ancestry.

If a session has no location record, the Explorer service should synthesize a root-level location. This supports migration without rewriting old sessions.

## Knowledge Explorer Behavior

Knowledge nodes can be manually organized into folders.

When the agent creates a node, it should provide a target folder when it can do so confidently. If it cannot, the node goes to `Unsorted` or root.

Agent placement is asynchronous:

1. A knowledge job creates the Markdown node using stable `node_id`.
2. The node appears in the Explorer using an initial system location.
3. A later organization step may move it if `user_locked` is false.
4. If the user moves it, future agent organization should not override that location without explicit user action.

This allows answers and knowledge persistence to complete without blocking on perfect book organization.

## Migration

Existing sessions:

- Keep their current storage under `data/chats/sessions/`.
- On first Explorer read, synthesize root-level locations for sessions missing from the Explorer index.
- Do not infer folder nesting from fork depth.

Existing knowledge nodes:

- Keep their current files under `data/knowledge/<node_id>.md`.
- On first Explorer read, synthesize locations from existing `parent_id` only if this is useful and unambiguous.
- Otherwise place them at root or `Unsorted`.
- Do not rewrite Markdown files during migration.

## Testing

Backend tests should cover:

- Creating folders for each scope.
- Rejecting duplicate sibling folder names within the same scope and parent.
- Moving a session into a session folder.
- Moving a knowledge node into a knowledge folder.
- Rejecting cross-scope moves.
- Rejecting deletion of non-empty folders.
- Synthesizing root locations for old sessions and nodes.
- Preserving session fork metadata after moves.
- Preserving knowledge references after moves.

Frontend tests should cover:

- Rendering folders and leaf items with compact Explorer rows.
- Expanding and collapsing folders.
- Selecting session and knowledge leaf items.
- Creating a folder from the section header.
- Opening a move action and sending the selected target folder.
- Showing active row state.

## Open Implementation Notes

The design intentionally leaves drag and drop, recursive folder deletion, custom sorting UI, and full agent reorganizer behavior for later iterations. The first implementation should establish the storage boundary and visible tree interactions before adding heavier organization automation.
