# Provider Config Centering In GlobalSettings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move provider/model configuration management into `GlobalSettings` and restrict `ModelSettings` to selecting only preconfigured entries.

**Architecture:** Reuse the existing credential store as the provider configuration source by persisting provider metadata (`provider_id`, `default_model`, `base_url`) alongside keys. `GlobalSettings` becomes the configuration editor; `ModelSettings` consumes derived configured entries and only updates the active session profile from those entries.

**Tech Stack:** FastAPI (Python), Vue 3 + Pinia + TypeScript, Vitest

---

### Task 1: Extend Credential Summary Contract

**Files:**
- Modify: `src/math_im_book/api/schemas.py`
- Modify: `src/math_im_book/api/app.py`

- [ ] **Step 1: Add failing API schema test expectations via existing frontend integration tests**
- [ ] **Step 2: Extend credential summary payload to include `provider_id`, `default_model`, `base_url`**
- [ ] **Step 3: Ensure create/update credential writes preserve these fields**
- [ ] **Step 4: Run focused backend checks (or note if backend tests are not available in this run)**

### Task 2: Add Frontend Provider-Config Derivation In Store

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/stores/workspace.ts`
- Modify: `frontend/src/stores/workspace.test.ts`

- [ ] **Step 1: Write failing store tests for configured provider entry derivation and profile normalization**
- [ ] **Step 2: Implement derived configured entry list based on credentials + provider options**
- [ ] **Step 3: Update selected profile normalization to only allow configured entries**
- [ ] **Step 4: Run focused Vitest store tests**

### Task 3: Rework GlobalSettings To Manage Provider Config Entries

**Files:**
- Modify: `frontend/src/components/explorer/GlobalSettings.vue`
- Add/Modify: `frontend/src/components/explorer/GlobalSettings.test.ts`

- [ ] **Step 1: Write failing component tests for provider list, edit form, and save behavior**
- [ ] **Step 2: Replace current “credentials only” UX with provider-centric config editor**
- [ ] **Step 3: Keep provider scope to `deepseek`, `openrouter`, `glm`, `gemini`**
- [ ] **Step 4: Run focused component tests**

### Task 4: Restrict ModelSettings To Configured Entries Only

**Files:**
- Modify: `frontend/src/components/chat/ModelSettings.vue`
- Modify: `frontend/src/components/chat/ModelSettings.test.ts`

- [ ] **Step 1: Write failing tests to ensure only configured entries are selectable**
- [ ] **Step 2: Remove free provider/model editing and implement configured-profile selector**
- [ ] **Step 3: Ensure save updates `selectedProviderProfile` from selected configured entry**
- [ ] **Step 4: Run focused component tests**

### Task 5: Verify End-To-End Frontend Behavior

**Files:**
- Modify if needed based on failures

- [ ] **Step 1: Run targeted vitest suite for changed components and store**
- [ ] **Step 2: Run frontend build**
- [ ] **Step 3: Summarize verification results and remaining risks**
