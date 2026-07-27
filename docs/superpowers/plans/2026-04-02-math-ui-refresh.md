# Math UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the frontend into a more cohesive desktop-first math/physics chat workspace without changing the core workflow.

**Architecture:** Introduce a shared visual token layer first, then update the shell and highest-traffic chat surfaces to consume the new system. After the primary surfaces are stable, align secondary navigation, reader, and settings panels to the same visual grammar.

**Tech Stack:** Vue 3, TypeScript, Tailwind CSS v4, Pinia, Vitest, KaTeX

---

## File Map

- Modify: `frontend/src/style.css`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/chat/ChatComposer.vue`
- Modify: `frontend/src/components/chat/ChatMessage.vue`
- Modify: `frontend/src/components/chat/MathText.vue`
- Modify: `frontend/src/components/explorer/SessionTree.vue`
- Modify: `frontend/src/components/explorer/BookOutline.vue`
- Modify: `frontend/src/components/reader/ReaderPanel.vue`
- Modify: `frontend/src/components/reader/NodeReferences.vue`
- Modify: `frontend/src/components/chat/ModelSettings.vue`
- Modify: `frontend/src/components/explorer/GlobalSettings.vue`
- Verify: `frontend/src/components/chat/ModelSettings.test.ts`
- Verify: `frontend/src/components/explorer/SessionTree.test.ts`

### Task 1: Establish global visual tokens

**Files:**
- Modify: `frontend/src/style.css`

- [ ] Step 1: Add CSS custom properties for surfaces, text, borders, accent, and math surfaces.
- [ ] Step 2: Adjust the global page background and base text color.
- [ ] Step 3: Replace existing transition timing and loading styles with quieter defaults.
- [ ] Step 4: Add shared KaTeX display styling for formula blocks.
- [ ] Step 5: Run `npm run build` from `frontend/` and fix any CSS issues.

### Task 2: Rebalance the app shell

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] Step 1: Update rail, sidebar, main panel, and reader panel backgrounds to match the new token system.
- [ ] Step 2: Remove glow-heavy active states and decorative indicators.
- [ ] Step 3: Replace the center empty state with math/physics-oriented heading, supporting text, and example prompts.
- [ ] Step 4: Simplify loading indicators and header emphasis.
- [ ] Step 5: Run `npm run build` from `frontend/`.

### Task 3: Refresh the composer and messages

**Files:**
- Modify: `frontend/src/components/chat/ChatComposer.vue`
- Modify: `frontend/src/components/chat/ChatMessage.vue`
- Modify: `frontend/src/components/chat/MathText.vue`

- [ ] Step 1: Update the composer input, placeholder, helper text, and send button styling.
- [ ] Step 2: Remove low-value branding copy from the composer.
- [ ] Step 3: Restyle user and assistant messages to reduce generic IM bubble feel.
- [ ] Step 4: Make assistant content spacing and action controls quieter and more readable.
- [ ] Step 5: Ensure display formulas inherit the new shared formula styling.
- [ ] Step 6: Run `npm run test` and `npm run build` from `frontend/`.

### Task 4: Align navigation components

**Files:**
- Modify: `frontend/src/components/explorer/SessionTree.vue`
- Modify: `frontend/src/components/explorer/BookOutline.vue`
- Verify: `frontend/src/components/explorer/SessionTree.test.ts`

- [ ] Step 1: Update selected and hover states to use the new shared navigation language.
- [ ] Step 2: Quiet badges, type labels, and utility menus.
- [ ] Step 3: Keep tree depth cues while reducing SaaS-style chrome.
- [ ] Step 4: Run `npm run test -- SessionTree` if needed, then `npm run build`.

### Task 5: Polish reader and references

**Files:**
- Modify: `frontend/src/components/reader/ReaderPanel.vue`
- Modify: `frontend/src/components/reader/NodeReferences.vue`

- [ ] Step 1: Rework reader surface hierarchy so it reads as a calm secondary workspace.
- [ ] Step 2: Update metadata, summary, symbol registry, and references presentation.
- [ ] Step 3: Align formulas and prose rhythm with the new global styling.
- [ ] Step 4: Run `npm run build` from `frontend/`.

### Task 6: Unify modal settings surfaces

**Files:**
- Modify: `frontend/src/components/chat/ModelSettings.vue`
- Modify: `frontend/src/components/explorer/GlobalSettings.vue`
- Verify: `frontend/src/components/chat/ModelSettings.test.ts`

- [ ] Step 1: Standardize modal shell, headers, form controls, and action buttons.
- [ ] Step 2: Replace bright dashboard accents with the new calm accent system.
- [ ] Step 3: Simplify informational panels and status tags.
- [ ] Step 4: Run `npm run test -- ModelSettings` if needed, then `npm run build`.

### Task 7: Final verification

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/components/chat/ChatComposer.vue`
- Modify: `frontend/src/components/chat/ChatMessage.vue`
- Modify: `frontend/src/components/chat/MathText.vue`
- Modify: `frontend/src/components/explorer/SessionTree.vue`
- Modify: `frontend/src/components/explorer/BookOutline.vue`
- Modify: `frontend/src/components/reader/ReaderPanel.vue`
- Modify: `frontend/src/components/reader/NodeReferences.vue`
- Modify: `frontend/src/components/chat/ModelSettings.vue`
- Modify: `frontend/src/components/explorer/GlobalSettings.vue`

- [ ] Step 1: Run `npm run test` from `frontend/`.
- [ ] Step 2: Run `npm run build` from `frontend/`.
- [ ] Step 3: Manually inspect desktop shell balance, empty state, chat readability, formula rendering, reader hierarchy, and modal consistency.
- [ ] Step 4: Summarize any residual visual follow-up work.
