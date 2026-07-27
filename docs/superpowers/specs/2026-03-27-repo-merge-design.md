# Repo merge design (2026-03-27)

## Context

- The `master` working tree at `/Users/liang/projects/math-im-book` currently hosts only documentation, the `plan/` stub, and the new tooling scripts.
- The backend prototype (`pyproject.toml`, `src/`, `tests/`, `data/`, `docs/`, etc.) exists as untracked files inside the `feat/milestone-a-backend` worktree at `/Users/liang/.config/superpowers/worktrees/math-im-book/milestone-a-backend`. That branch commit only contains the `spec/` folder, so a simple `git merge` would not bring the backend code.
- The goal is to merge everything into the primary repository root so the project can be built, tested, and run from `/Users/liang/projects/math-im-book` without managing a separate worktree.

## Options considered

1. **Git merge the `feat/milestone-a-backend` branch.** This would preserve history but does nothing useful here because the branch commit does not contain the backend files; they remain untracked in the parallel worktree.
2. **Manually copy the backend assets from the worktree into the root.** This guarantees the runnable backend and documentation exist where the user is working. It forgoes any granular commit history but aligns with the user request to “全部合并.”
3. **Import the backend into a `backend/` subdirectory.** This keeps the existing doc-only layout but adds a segregated backend, at the cost of deviating from the user’s desire for a unified root layout.

Recommendation: option 2. It delivers the required backend resources directly into the main workspace with minimal complexity and no ambiguous history assumptions.

## Implementation plan

1. Copy the configuration files from the feature worktree: `.gitignore`, `.python-version`, `pyproject.toml`, and `README.md`. Before overwriting anything, save a backup of any existing root files (if they appear later) and run a quick `diff` so we can manually merge sections rather than blindly overwriting. After the copy, we will confirm the combined files still reflect the doc-guided instructions and the backend requirements by reviewing the merged content with `git diff`.
2. Copy the backend source tree (`src/math_im_book`) while excluding generated artifacts such as `__pycache__`.
3. Copy the tests (`tests/`), again skipping `__pycache__` directories so only committed tests remain.
4. Copy `docs/superpowers/plans/*` from the worktree to the root so the plan archives live alongside the new backend content. Create `docs/superpowers/plans` if it does not already exist; for each plan file, compare against any existing version with `diff` and only replace if the worktree version is the intended backend plan, otherwise leave the existing stub or merge the contents manually. After the copy, ensure the directory listing contains the expected plan filenames by running `ls docs/superpowers/plans`.
5. Ensure `data/` contains the richer structure (`chats/`, `knowledge/`, `credentials/`, `drafts/`) required by the backend, creating missing subdirectories and preserving existing knowledge/chat data. Only create or populate the `credentials/` and `drafts/` directories if they are absent; do not delete or overwrite existing files under `data/chats` and `data/knowledge`. After the copy, confirm via `ls` (and optionally `find data/chats -maxdepth 1`) that the historic chat/knowledge folders remain unchanged and that the new directories exist.
6. Verify the repo is still runnable by checking `git status`, ensuring the new files are tracked, and preparing to run `pytest -q` later.

## Verification approach

- After merging, run `pip install -e '.[dev]'` inside a Python 3.10 virtual environment and `pytest -q` to verify the backend imports and basic tests pass (this will happen after the structural merge; `pytest` does not require API secrets).  
- Confirm the configuration, data, and plan copies by running targeted checks: `git diff --stat` on the copied config files, `ls data/credentials data/drafts` to ensure the directories exist, and `ls docs/superpowers/plans` plus `diff` on the newly copied plan files.  
- If `scripts/run.sh` is executed later, source `scripts/key.sh` (which already ships as a placeholder with instructions) and populate the secrets manually; the spec does not create new secrets, it merely documents that `scripts/key.sh` must be filled before hitting endpoints that require credentials.

## Notes

- This spec is being written without a separate spec-document-reviewer prompt in the repo, so downstream review will rely on this doc plus the final `git status` snapshot. If a formal review tool becomes available later, we can revisit the doc.
