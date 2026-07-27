# Answer Style Prompting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable per-turn answer styles with a stable default prompt prefix for cache-friendly conversations.

**Architecture:** Store the session's default answer style as structured metadata, load Markdown-backed answer style instructions from config, and append per-turn style overrides only when the user selects a non-default style. Expose style metadata through the API and add a composer selector in the Vue frontend.

**Tech Stack:** FastAPI, Pydantic, file-backed session storage, Vue 3, Pinia, Vitest, pytest

---

### Task 1: Backend Answer Style Model And Prompt Assembly

**Files:**
- Create: `data/config/answer_styles/index.json`
- Create: `data/config/answer_styles/default.md`
- Create: `data/config/answer_styles/concise.md`
- Create: `data/config/answer_styles/step-by-step.md`
- Create: `data/config/answer_styles/intuitive.md`
- Create: `data/config/answer_styles/rigorous.md`
- Create: `src/math_im_book/storage/answer_styles.py`
- Modify: `src/math_im_book/domain/models.py`
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`
- Modify: `src/math_im_book/services/orchestrator.py`
- Test: `tests/api/test_schemas.py`
- Test: `tests/api/test_sessions_api.py`
- Test: `tests/services/test_orchestrator.py`

- [ ] **Step 1: Write failing backend tests**
- [ ] **Step 2: Run targeted pytest commands and confirm failures**
- [ ] **Step 3: Add answer style config files and repository loader**
- [ ] **Step 4: Add session/schema fields and `/api/answer-styles` response shape**
- [ ] **Step 5: Update `/api/ask` and orchestrator prompt assembly to use default prefix plus per-turn override**
- [ ] **Step 6: Re-run targeted backend tests until green**

### Task 2: Frontend Style Selector And Session Wiring

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Modify: `frontend/src/components/chat/ChatComposer.vue`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`
- Modify: `frontend/src/stores/workspace.test.ts`

- [ ] **Step 1: Write failing frontend tests for answer style loading and ask payloads**
- [ ] **Step 2: Run targeted Vitest commands and confirm failures**
- [ ] **Step 3: Add answer style types and API client methods**
- [ ] **Step 4: Load styles into the workspace store and send selected style per ask**
- [ ] **Step 5: Add the composer style selector and current-style display**
- [ ] **Step 6: Re-run targeted frontend tests until green**

### Task 3: End-To-End Verification

**Files:**
- Verify existing modified files only

- [ ] **Step 1: Run backend targeted tests**
- [ ] **Step 2: Run frontend targeted tests**
- [ ] **Step 3: Inspect changed files and ensure no style text is persisted into chat message content**
- [ ] **Step 4: Summarize verification results and residual risks**
