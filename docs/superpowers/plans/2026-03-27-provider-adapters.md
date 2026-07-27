# Provider Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-chat provider selection so a request can use either a Gemini API configuration or any OpenAI-compatible chat-completions endpoint.

**Architecture:** Keep the knowledge routing local, then hand the final natural-language rendering to a provider adapter selected from a `ProviderProfile`. Credentials are resolved by `credential_id`, sessions can remember the selected provider profile, and adapters normalize responses into one internal text result.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, httpx, pytest

---

### Task 1: Add provider and session contracts
### Task 2: Add credential registry and provider adapters
### Task 3: Extend orchestrator with optional external rendering
### Task 4: Extend `/api/ask` for session-scoped provider selection
### Task 5: Add fixtures, docs, and full verification
