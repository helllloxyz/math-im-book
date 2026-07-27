# Environment Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up the development environment and ensure both backend and frontend can start correctly using `scripts/run.sh`.

**Architecture:** Initialize a Python virtual environment for the backend and install npm dependencies for the frontend.

**Tech Stack:** Python 3.10, FastAPI, Uvicorn, Node.js, Vite, Vue.

---

### Task 1: Backend Environment Setup

**Files:**
- Create: `.venv` (directory)
- Modify: N/A

- [ ] **Step 1: Create Python virtual environment**

Run: `python3.10 -m venv .venv`
Expected: `.venv` directory created.

- [ ] **Step 2: Install backend dependencies**

Run: `.venv/bin/pip install -e ".[dev]"`
Expected: Successful installation of dependencies from `pyproject.toml`.

- [ ] **Step 3: Verify backend can start**

Run: `PYTHONPATH=src .venv/bin/python -m uvicorn math_im_book.api.app:create_app --host 0.0.0.0 --port 8016 --factory`
Expected: "Application startup complete." (Wait for output, then terminate with Ctrl+C or kill).

- [ ] **Step 4: Commit (optional - usually .venv is gitignored)**

Since `.venv` is likely in `.gitignore`, no commit needed for the environment itself, but I'll check `.gitignore`.

### Task 2: Frontend Environment Setup

**Files:**
- Modify: `frontend/node_modules` (indirectly)

- [ ] **Step 1: Install frontend dependencies**

Run: `cd frontend && npm install`
Expected: Successful installation of npm packages.

- [ ] **Step 2: Verify frontend can start**

Run: `cd frontend && npm run dev -- --port 8017`
Expected: "VITE v... ready in ... ms" and "Local: http://localhost:8017/".

### Task 3: Full Project Startup

**Files:**
- Modify: N/A

- [ ] **Step 1: Run the startup script**

Run: `./scripts/run.sh`
Expected: Both backend and frontend start successfully. Since this script waits for the processes, I will check if they are running and then terminate.

- [ ] **Step 2: Verify services are responsive**

Run: `curl http://localhost:8016/health` (assuming there's a health check) and check `http://localhost:8017`.
