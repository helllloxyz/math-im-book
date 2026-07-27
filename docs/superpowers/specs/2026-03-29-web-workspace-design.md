# Math IM Book Web Workspace Design

## 1. Context

This document refines the web workspace direction for `math-im-book` based on:

- [web_spec.md](/mnt/e/code/math-im-book/spec/web_spec.md)
- [System_design.md](/mnt/e/code/math-im-book/spec/plan/System_design.md)
- [MVP_scope.md](/mnt/e/code/math-im-book/spec/plan/MVP_scope.md)
- [2026-03-27-milestone-b-branching.md](/mnt/e/code/math-im-book/docs/superpowers/plans/2026-03-27-milestone-b-branching.md)

The goal is not to design a generic knowledge-management platform. The goal is to design a usable web workspace for a conversation-driven system that gradually grows into a math book.

## 2. Design Goal

The workspace should make the following product feeling obvious:

`I ask and explore in the middle, I know my branch and chapter context on the left, and I see the result accumulating into book-like Markdown on the right.`

This implies three constraints:

1. The product is `conversation-led`, not editor-led.
2. The product is `book-oriented`, but book structure should not hijack the conversation flow.
3. The UI should show branch context and knowledge accumulation without turning into a heavy management console.

## 3. Rejected Directions

### 3.1 Lightweight chat page

This is simple to build, but too weak for this product. It hides chapter placement, reference visibility, and accumulation into Markdown.

### 3.2 Balanced management console

This exposes more data, but pushes the product toward a knowledge-management backend. It would make all three columns compete equally for attention and weaken the conversation-first experience.

### 3.3 Book-first editor

This may be appropriate in later drafting stages, but it is too early for MVP. The current product phase is still exploration and accumulation, not direct chapter authoring.

## 4. Chosen Product Shape

The web UI should be a `conversation-led writing workspace`.

Visually it still uses a three-column layout, but the interaction priority must be explicit:

1. `Center`: produce and continue the current conversation
2. `Right`: read the current Markdown accumulation and references
3. `Left`: locate branch context and chapter placement

This means the workspace is visually three-column, but behaviorally centered around the current conversation.

## 5. Confirmed Interaction Decisions

The following choices were explicitly confirmed during design discussion:

1. Default mode is `conversation-led`
2. The left column prioritizes `Chat Chain / Fork Tree` over the book outline
3. The right column prioritizes `Markdown preview` over metadata inspection
4. Clicking a chapter in the outline updates the right column only
5. Clicking a chapter must not force the center column to switch sessions
6. Chapter-to-chat relationships are many-to-many, and users should choose whether to switch chat context
7. MVP Markdown is `read-only preview`, not an editor
8. `/compact` is not part of the core MVP interaction loop yet
9. Answer-level actions should be minimal: `Fork`, `Copy`, `Regenerate`
10. `Continue asking` is handled by the chat input itself, not by a dedicated button
11. `View references` should not be a separate action button; references should appear inline as clickable links in the answer body

## 6. Information Architecture

The workspace is organized into three functional zones.

### 6.1 Left Column: Context Locator

The left column answers:

`Which thread am I in, and where does this knowledge belong in the book?`

It is split vertically into two areas.

#### Top: Chat Chain / Fork Tree

This is the primary navigator in MVP.

It should show:

- current session / branch
- parent-child branch relationships
- summary or focus label for each branch
- creation time
- message count
- ability to identify the main line

This section supports the product need for branch isolation and keeps the branching model visible without forcing users to understand backend internals.

#### Bottom: Book Outline

This is a secondary navigator.

It should show:

- hierarchical book structure
- chapter / section / subsection nesting
- generation status: `not generated` / `generated`
- whether the chapter has related chat sessions

This section answers destination, not active working context.

### 6.2 Center Column: Conversation Workspace

The center column answers:

`What am I working on right now?`

This is the dominant area of the UI.

Recommended vertical structure:

- current branch header
- conversation history
- answer cards
- bottom input box

The branch header should show only lightweight context:

- current branch name
- relation to parent or main line
- current focus label when available

Each answer card should emphasize readable content, not controls. Inline references should be embedded in the answer body and remain clickable.

Answer card actions should be limited to:

- `Fork`
- `Copy`
- `Regenerate`

No dedicated `Continue asking` button is needed.

### 6.3 Right Column: Accumulation Reader

The right column answers:

`What has this conversation accumulated into?`

This column is not a control panel. It is a reading-oriented accumulation surface.

Recommended structure:

- top: Markdown preview
- bottom: related references and chat links

The top area should feel like reading notes or a draft chapter, not inspecting internal data structures.

The bottom area can include:

- referenced nodes
- source chat list
- related chapters
- lightweight node status

Metadata exists to support reading, not to replace it.

## 7. Primary Interaction Flows

### 7.1 Ask a question

1. The user asks in the center input
2. The answer appears in the current conversation
3. Inline references are rendered inside the answer body
4. The right column updates to the most relevant Markdown preview when available

The center remains the main production surface.

### 7.2 Click a reference inside the answer

1. The user clicks an inline reference
2. The center conversation stays in place
3. The right column switches to the referenced node or chapter preview
4. The lower-right related-info area shows source chats and related links

This is a reading-context change, not a conversation-context change.

### 7.3 Click a chapter in the outline

1. The user clicks a chapter in the left-bottom outline
2. The right column switches to that chapter's Markdown preview
3. The center conversation does not switch
4. The right column may show related chat sessions, but the user must explicitly choose whether to open one

This preserves the many-to-many relationship between chapters and chat sessions.

### 7.4 Fork from an answer

1. The user clicks `Fork`
2. A new branch session is created
3. The center column switches to the new branch
4. The left-top branch tree highlights the new branch
5. The right column should remain stable unless the new branch explicitly changes reading context

This keeps branch switching and reading context loosely coupled.

## 8. Visual Hierarchy

The workspace must avoid equal visual weight across all columns.

### 8.1 Center is strongest

The user's eye should first land on:

- current answer
- input box
- current branch header

### 8.2 Right is secondary

The right column should feel like a calm reading surface:

- strong typography
- readable spacing
- clear heading hierarchy
- visible inline links

It should not look like a JSON inspector or admin panel.

### 8.3 Left is quiet but persistent

The left column should be visually lighter:

- compact tree rows
- low-noise status markers
- indentation and spacing instead of loud chips

It should support orientation, not compete for attention.

## 9. Screen States

### 9.1 First entry

- center: welcome state and input
- left: recent chats and outline
- right: empty-state accumulation panel

### 9.2 Active conversation

- center: current thread grows naturally
- left-top: active branch highlighted
- right: current or selected Markdown preview

### 9.3 Reading mode inside the workspace

- triggered by clicking an outline node or inline reference
- right updates
- center remains stable

### 9.4 After fork

- center switches branch
- left-top updates branch highlight
- right stays stable by default

## 10. MVP Scope

### 10.1 Must-have

- one main workspace page
- top global bar
- left-top branch tree
- left-bottom outline tree
- center conversation flow
- inline references in answers
- answer actions: `Fork`, `Copy`, `Regenerate`
- right-side read-only Markdown preview
- related chat list in the right column

### 10.2 Explicitly deferred

- full Markdown editor
- dedicated graph view
- dedicated symbol-management page
- dedicated branch-management center
- heavy command system
- `/compact` as a central UI flow

## 11. Alignment With Existing Work

This design aligns with current repository direction:

- existing branching work already prioritizes visible session hierarchy
- the current frontend already has node detail, branch panels, and session loading primitives
- the chosen direction simplifies the center action model instead of expanding it
- the design keeps the MVP boundary consistent with the existing system documents that emphasize conversation-led accumulation over heavy front-end complexity

## 12. Implementation Guidance Boundary

This document is intentionally a product-and-UI design spec, not an implementation plan.

It defines:

- the dominant page model
- interaction boundaries
- panel responsibilities
- MVP and non-MVP scope

It does not yet define:

- exact API changes
- exact component decomposition
- test cases
- rollout order inside the codebase

Those belong in the implementation planning phase.
