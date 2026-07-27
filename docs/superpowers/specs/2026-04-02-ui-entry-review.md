# UI Entry Review: Interaction Completeness and Simplification Audit

**Date:** 2026-04-02

## Scope

Review the project from the current UI entrypoints outward, using a user-facing perspective first, then checking whether the main interaction trunks are complete and whether the implementation behind them is reasonable or obviously oversimplified.

## Current Interaction Surfaces

### 1. Chat Workspace

- Empty-state prompt shortcuts in the center panel
- Freeform question input in the composer
- Answer style selector
- Provider/model configuration modal
- Assistant message actions:
  - `Fork`
  - `Copy`
  - `Retry`

### 2. Session and Branch Navigation

- Left rail tab switch:
  - `chat`
  - `book`
- Session tree
- New conversation
- Conversation icon picker
- Delete conversation

### 3. Knowledge / Reader Flow

- Book outline tree
- Reader panel for node details
- Node dependency navigation
- Incoming reference navigation
- Related discussion jump links

### 4. Global Configuration

- Credential creation
- Provider type selection
- Base URL entry for compatible providers

## Major Findings

### 1. Retry Interaction Is Semantically Wrong

**Problem**

The UI presents `Retry` as if it regenerates the selected assistant answer, but the implementation simply finds the last user message in the session and submits it again.

**Impact**

- The action is not scoped to the clicked answer
- It appends a new round instead of replacing/regenerating the intended reply
- In a long branch, the user can easily get a result for the wrong conversational point

**Relevant code**

- `frontend/src/components/chat/ChatMessage.vue`
- `frontend/src/App.vue`

### 2. Fork Creates an Immediate “Empty Branch” Experience

**Problem**

After `Fork`, the frontend immediately switches to the returned child session, but the fork endpoint returns a session record with `messages=[]`. The inherited history only appears after reloading that session from storage.

**Impact**

- The user sees a fresh empty conversation right after forking
- It looks like branch history was lost
- This is especially damaging because branch/fork is a primary workflow concept in the product

**Observed behavior**

- Immediate fork response: `0` messages
- Reloaded fork session: inherited history becomes visible

**Relevant code**

- `frontend/src/stores/workspace.ts`
- `src/math_im_book/api/app.py`

### 3. Error Handling Is Largely Invisible to Users

**Problem**

Most request failures only go to `console.error`. The UI usually has no visible error state, no toast, no inline banner, and no recovery guidance.

The composer also clears the input before the request succeeds, so a failed question submission can destroy the user’s draft.

**Impact**

- Failed sends feel like no-op or data loss
- Session and node selection failures are silent from the user’s perspective
- Provider/config problems are difficult to diagnose in the UI

**Relevant code**

- `frontend/src/components/chat/ChatComposer.vue`
- `frontend/src/stores/workspace.ts`

### 4. “Knowledge Accumulation” Is Only Superficially Complete

**Problem**

The product presents itself as a conversation-led writing workspace where chat accumulates into a structured math book. In reality, when the system expands knowledge, the node persisted to disk is mostly placeholder content. The high-value answer stays in chat history, not in the saved knowledge node.

**Impact**

- Reader/book surfaces become much less useful than the chat surface
- The knowledge base does not actually improve proportionally with usage
- The main product promise, chat turning into reusable knowledge, is not truly fulfilled

**Relevant code**

- `src/math_im_book/services/orchestrator.py`
- `src/math_im_book/services/planner.py`

### 5. Answer Style Is Presented Like a Session Mode but Behaves Like a Global Temporary Setting

**Problem**

The UI makes answer style feel like part of the current conversation context, but the selected style is stored only in frontend state. Session persistence still defaults to `default`, and reloading or switching sessions does not reliably restore the session’s actual style.

**Impact**

- The user expectation of “this branch uses style X” is broken
- Session history and future replies can drift apart
- The interface implies a session-level contract that the implementation does not honor

**Relevant code**

- `frontend/src/stores/workspace.ts`
- `src/math_im_book/api/app.py`

### 6. Reader Panel Contains Multiple Placeholder-Level Interactions

**Problem**

The Reader header exposes actions such as `Search`, `Print`, and `Share`, but those buttons are not wired to meaningful behavior.

Reference surfaces are also underpowered:

- dependency links show raw `node_id`
- related discussions show truncated session ids instead of meaningful titles
- there is little preview context for deciding where to jump next

**Impact**

- The panel looks more complete than it is
- Navigation quality is low even when the data exists
- It increases the gap between visual polish and functional depth

**Relevant code**

- `frontend/src/components/reader/ReaderPanel.vue`
- `frontend/src/components/reader/NodeReferences.vue`

### 7. Session / Branch UX Is Functional but Thin

**Problem**

The session tree basically supports select, delete, and icon change, but branch semantics are not surfaced clearly enough.

Missing or weak signals include:

- no branch header explaining lineage in the main panel
- no visible distinction between root conversations and forks beyond indentation
- no inline explanation of current branch focus or fork anchor

**Impact**

- Branching exists technically but is cognitively expensive
- Users can fork, but understanding branch structure requires inference

**Relevant code**

- `frontend/src/components/explorer/SessionTree.vue`
- `frontend/src/App.vue`

### 8. Global Settings UI Overstates State Quality

**Problem**

The credential list shows `Active` status uniformly, even though the UI is not truly indicating “currently selected”, “valid”, or “reachable”.

**Impact**

- The user may infer connection health or active selection that the system has not verified
- This is another case of presentational confidence exceeding implementation confidence

**Relevant code**

- `frontend/src/components/explorer/GlobalSettings.vue`

## Main Trunk Assessment

### Chat Trunk

**Status:** partially complete

What works:

- asking questions
- loading session messages
- basic assistant actions
- provider selection

What is incomplete or weak:

- retry semantics
- error feedback
- preservation of failed drafts
- branch context visibility

### Branch / Session Trunk

**Status:** mechanically available, conceptually underexplained

What works:

- session list
- branch hierarchy rendering
- fork creation
- deletion guard for parents with children

What is incomplete or weak:

- immediate post-fork experience
- branch lineage explanation
- branch-specific context display

### Knowledge / Reader Trunk

**Status:** visually strong, functionally shallow

What works:

- outline browsing
- node detail rendering
- node relationship links

What is incomplete or weak:

- action buttons are placeholders
- references are low-context
- saved node quality is insufficient for the reader to become a real destination

### Knowledge Accumulation Trunk

**Status:** structurally present, substantively incomplete

What works:

- nodes can be created
- sessions can reference nodes
- outline can be refreshed

What is incomplete or weak:

- generated nodes are placeholder-like
- no visible pending-draft workflow
- no robust user-in-the-loop curation path

### Configuration Trunk

**Status:** usable but simplified

What works:

- local credential creation
- provider/model/base URL selection

What is incomplete or weak:

- weak state semantics
- no connection test
- no clear distinction between saved, selected, valid, and currently effective

## Test Notes

### Verified

- `frontend`: `npm run test` passed

### Observed backend/frontend contract drift

Running:

```bash
.venv/bin/pytest -q tests/api/test_frontend_workspace_flow.py tests/api/test_frontend_branching.py tests/api/test_frontend_reader_panel.py tests/services/test_orchestrator.py
```

resulted in 2 failures tied to frontend shell contract expectations around the reader/book wording. This suggests the UI shell is evolving without keeping existing contract tests aligned.

## Suggested Priority Order

1. Fix `Retry` semantics and `Fork` post-action behavior
2. Add visible request failure states and preserve unsent/failed user drafts
3. Make answer style genuinely session-scoped if that is the intended UX
4. Replace placeholder node persistence with real knowledge-node generation
5. Remove or wire up dead Reader actions
6. Improve branch context visibility and navigation labeling

