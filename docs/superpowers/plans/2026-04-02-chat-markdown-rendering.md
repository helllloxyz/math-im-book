# Chat Markdown Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render chat messages and the reader panel with a shared `markdown-it + KaTeX` pipeline so Markdown structure displays correctly across the app.

**Architecture:** Introduce a single frontend Markdown renderer service responsible for Markdown parsing, HTML sanitization, and math rendering. Update chat and reader components to consume rendered HTML instead of the current plain-text-plus-math tokenization path, and cover the behavior with focused component tests.

**Tech Stack:** Vue 3, Vitest, markdown-it, KaTeX, DOMPurify

---

### Task 1: Add a failing chat Markdown rendering test

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.test.ts`
- Test: `frontend/src/components/chat/ChatMessage.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it('renders markdown structure for chat content', () => {
  const wrapper = mount(ChatMessage, {
    props: {
      message: {
        role: 'assistant',
        content: '# Title\n\n- one\n- two\n\n```ts\nconst x = 1\n```',
      },
    },
  })

  expect(wrapper.html()).toContain('<h1')
  expect(wrapper.html()).toContain('<ul')
  expect(wrapper.html()).toContain('<code')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/chat/ChatMessage.test.ts`
Expected: FAIL because the component still renders plain text spans instead of Markdown HTML.

- [ ] **Step 3: Write minimal implementation**

Create a shared Markdown renderer and switch `ChatMessage.vue` to render sanitized HTML for message content.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/components/chat/ChatMessage.test.ts`
Expected: PASS

### Task 2: Add a failing reader-panel rendering test

**Files:**
- Create: `frontend/src/components/reader/ReaderPanel.test.ts`
- Test: `frontend/src/components/reader/ReaderPanel.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
it('renders node detail as markdown html', () => {
  // mount ReaderPanel with a node detail containing heading/list/math
  expect(wrapper.html()).toContain('<h2')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/reader/ReaderPanel.test.ts`
Expected: FAIL because the reader still uses the old `parseMath` path.

- [ ] **Step 3: Write minimal implementation**

Switch `ReaderPanel.vue` to the shared Markdown renderer.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- src/components/reader/ReaderPanel.test.ts`
Expected: PASS

### Task 3: Introduce shared renderer and dependencies

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/services/markdown.ts`

- [ ] **Step 1: Add dependencies**

Add `markdown-it` and `dompurify`.

- [ ] **Step 2: Implement renderer**

Create a shared renderer with:
- `markdown-it` configured for links, typography, and fenced code blocks
- KaTeX plugin support for math in Markdown
- DOMPurify sanitization before injecting HTML

- [ ] **Step 3: Verify renderer-focused tests still pass**

Run: `cd frontend && npm run test -- src/components/chat/ChatMessage.test.ts src/components/reader/ReaderPanel.test.ts`
Expected: PASS

### Task 4: Run final verification

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.vue`
- Modify: `frontend/src/components/reader/ReaderPanel.vue`
- Modify: `frontend/src/components/chat/ChatMessage.test.ts`
- Create: `frontend/src/components/reader/ReaderPanel.test.ts`
- Create: `frontend/src/services/markdown.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Run targeted frontend tests**

Run: `cd frontend && npm run test -- src/components/chat/ChatMessage.test.ts src/components/reader/ReaderPanel.test.ts src/App.test.ts`
Expected: PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS
