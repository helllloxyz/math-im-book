# Reader References Navigation Design

## 1. Context
The right-side Reader panel is primarily a markdown knowledge reader. Its main job is to help the user read the currently selected node's title, summary, detail, and symbol registry without turning the panel into a second explorer or a second chat surface.

The current `References & Context` section does not meet that bar:
- node references render as raw `node_id`
- related discussions render as truncated `sessionId`
- the section exposes almost no context before click
- the list has no information hierarchy beyond three headings

The user explicitly chose a **navigation panel** direction:
- the Reader remains content-first
- the lower section may contain more items, but each group should be collapsible
- only the most important entries should be visible by default
- implementation should stay within current scope and current data where possible

Search / Print / Share remain out of scope for this design.

## 2. Goal
Turn `References & Context` into a compact post-reading navigation panel that helps the user decide where to go next without overwhelming the Reader body.

Success looks like:
- users can scan the section and understand what each item is before clicking
- groups are structured and collapsible instead of dumping full lists
- visible content defaults to a short preview of the most relevant entries
- the first implementation uses current project data as much as possible

## 3. Non-Goals
- redesigning the full Reader shell
- implementing Reader toolbar actions
- introducing graph views, search, filters, ranking controls, or chat transcript previews
- building a generic reusable card system for all app surfaces

## 4. Recommended Approach
Use a **three-group navigation panel** under the Reader body:
- `Dependencies`
- `Referenced By`
- `Related Discussions`

Each group behaves the same way:
- collapsed when empty by omission
- rendered as a compact section when data exists
- shows the top `N` entries by default (`N=3`, fixed for the first implementation)
- exposes `Show all` / `Show less` when the group exceeds the preview size
- preserves the source order provided by the backend for the first implementation

Each item should be a **navigation card**, not a plain text row. The card should still stay visually lightweight so the Reader body remains dominant.

This is the recommended approach because it improves scanability and click confidence without introducing a second dense browsing surface.

## 5. Information Architecture

### 5.1 Reader Panel Hierarchy
The Reader panel hierarchy should remain:
1. node metadata
2. title and summary
3. markdown detail
4. symbol registry
5. references navigation panel

This keeps references clearly subordinate to the actual knowledge content.

### 5.2 Group Semantics
`Dependencies`
- nodes directly referenced by the current node
- helps the user backtrack to prerequisites

`Referenced By`
- nodes that depend on the current node
- helps the user move forward through the book

`Related Discussions`
- sessions associated with the current node and its immediate reference neighborhood
- helps the user jump from formal knowledge back to conversational exploration

## 6. Card Content Design

### 6.1 Node Reference Cards
Each node card should use two lines of information plus optional helper text:
- primary line: node title
- secondary line: prefer node summary; if unavailable, fall back to `reason`
- tertiary metadata, optional: node type or status only if already present and visually cheap

`node_id` should not be the visible primary label. It may remain available as a tiny fallback only if title lookup fails.

### 6.2 Related Discussion Cards
Each discussion card should use:
- primary line: session title
- secondary line: lightweight context with an explicit priority order:
  - first choice: backend-provided `preview`
  - second choice: `focus_question`
  - third choice: `"N messages"` derived from message count
  - otherwise omit the line

Raw truncated `sessionId` should not be the primary label. It may remain as a final fallback if the session title is unavailable.

### 6.3 Preview Density
Cards should remain compact:
- one clickable card per item
- no embedded transcript blocks
- no multi-message previews
- no full markdown rendering inside cards

The goal is "good enough to choose", not "read here instead of navigating".

## 7. Data Strategy

### 7.1 What Current APIs Already Provide
Current node payload already includes:
- current node title, summary, type, status
- `references[]` with `node_id` and `reason`
- `incoming_references[]` with `node_id` and `reason`
- `related_session_ids[]`

Current session APIs already include:
- `title`
- `messages`
- `branch.focus_question`
- message count can be derived

This means the current state is missing **display-ready joined data**, not missing the entire underlying dataset.

### 7.2 Recommended API Shape
Keep the Reader frontend simple by returning display-ready objects from the node endpoint instead of forcing the frontend to fan out into many secondary requests.

Recommended additions to `/api/nodes/{node_id}` response:
- `references_display[]`
- `incoming_references_display[]`
- `related_discussions[]`

For `related_discussions[].preview`, the first implementation should use a deterministic backend rule:
- inspect the session's visible messages in reverse order
- pick the newest non-empty message content, regardless of role
- normalize whitespace to single spaces
- trim to a short single-line preview, target 100 characters max
- if no non-empty message content exists, omit `preview`

Suggested shape:

```json
{
  "references_display": [
    {
      "node_id": "banach-fixed-point",
      "title": "Banach Fixed Point Theorem",
      "summary": "Guarantees convergence of contraction iterates.",
      "reason": "Used to justify contraction mapping convergence.",
      "type": "theorem",
      "status": "draft"
    }
  ],
  "related_discussions": [
    {
      "session_id": "sess-123",
      "title": "Convergence of iterative schemes",
      "preview": "Can the same contraction argument survive after rescaling?",
      "message_count": 6,
      "focus_question": "Why does the proof still hold after normalization?"
    }
  ]
}
```

This keeps the existing fields intact for compatibility while providing richer display fields for the Reader.

Ordering rules for the first implementation:
- `references_display[]`: preserve the current node's existing `references[]` order
- `incoming_references_display[]`: preserve the repository order returned by `list_incoming_references`
- `related_discussions[]`: preserve the order already returned by `list_related_session_ids`

Display text priority rules:
- node card title: `title` -> `node_id`
- node card secondary text: `summary` -> `reason` -> omitted
- discussion card title: `title` -> `focus_question` -> `session_id`
- discussion card secondary text: `preview` -> `focus_question` when not already used as title -> `"N messages"` -> omitted

### 7.3 Scope-Controlled Fallback
If the first iteration must stay even smaller, frontend fan-out is acceptable only as a temporary path:
- for node references, resolve titles/summaries from the existing outline cache if present
- for related discussions, resolve titles from the sessions list if present

But this should be treated as a fallback, not the desired end state, because:
- it couples Reader rendering to unrelated caches
- it creates partial rendering depending on navigation history
- it makes testing more brittle

## 8. Frontend Component Design

### 8.1 Component Boundaries
Keep `ReaderPanel.vue` content-first and localize navigation logic under `NodeReferences.vue`.

Recommended structure:
- `ReaderPanel.vue`
  - still owns the main reading surface
- `NodeReferences.vue`
  - owns the overall references navigation section
- `ReferenceGroup.vue`
  - shared collapse and preview-count behavior for one group
- optional small card components if the file becomes too large:
  - `NodeReferenceCard.vue`
  - `DiscussionReferenceCard.vue`

If `NodeReferences.vue` remains readable, separate card files are optional. The main requirement is to avoid mixing group state, collapse logic, and card rendering into a single unwieldy block.

### 8.2 Interaction Behavior
For each group:
- default to preview mode on initial render
- `Show all` expands the full list inline
- `Show less` returns to preview count
- expanded/collapsed state resets when the selected node changes

Card click behavior remains unchanged:
- node cards call `store.selectNode(node_id)`
- discussion cards call `store.selectSession(session_id)`

No modal, no side drawer, no in-place drill-down.

### 8.3 Visual Tone
This section should look like secondary navigation:
- smaller than the main article typography
- clear group headings
- compact cards with one strong title line and one quiet support line
- avoid oversized illustrations, large badges, or decorative clutter

## 9. Error Handling and Empty States
- empty groups should not render
- if title or summary lookup fails, fall back gracefully:
  - node card title -> `node_id`
  - discussion card title -> session focus question -> `session_id`
- if preview text is unavailable, omit the line instead of inserting noisy placeholders
- if a card target fails to load after click, rely on existing store-level error handling rather than adding special Reader-local error UI

## 10. Testing Strategy

### 10.1 Backend
Add API tests covering:
- node response includes display-ready reference data
- related discussion entries include title fallback behavior
- missing referenced node/session does not break the node endpoint

### 10.2 Frontend
Add component or store-backed tests covering:
- groups render only when data exists
- each group shows preview count first
- `Show all` / `Show less` toggles item visibility
- node cards render title/summary instead of raw `node_id` when data exists
- discussion cards render session title instead of truncated `sessionId` when data exists
- click actions still call the correct store methods

### 10.3 Regression
Retain the current fallback Reader shell assertions in `tests/api/test_frontend_reader_panel.py` and extend them only for meaningful copy or structural expectations. The broader frontend shell tests in `tests/api/test_frontend_panels.py` should remain untouched unless this feature changes top-level workspace structure, which it should not.

## 11. Incremental Delivery
Implement in two passes:

Pass 1:
- add display-ready data to the node API
- render grouped collapsible sections
- replace raw IDs with titles and summaries

Pass 2, only if needed later:
- improve discussion preview quality
- tune ranking or ordering within groups
- add richer metadata if real user need appears

This keeps the first change aligned with the user's scope request: improve the current navigation panel using what the system already knows, without turning it into a large new subsystem.
