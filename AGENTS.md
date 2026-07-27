# Repository Guidelines

## Project Structure & Module Organization
`src/math_im_book/` contains the Python backend. Keep API entrypoints in `api/`, core types in `domain/`, orchestration logic in `services/`, and file-backed persistence in `storage/`. Tests mirror that layout under `tests/api/`, `tests/services/`, and `tests/storage/`. Runtime data lives in `data/` (`knowledge/`, `chats/`, `credentials/`). Versioned prompt configuration now lives under `data/config/answer_styles/`; keep the style index in `index.json` and the prompt bodies in Markdown files named by style id. The Vue client lives in `frontend/src/` with `components/`, `services/`, and `stores/`; built assets are emitted to `frontend/dist/`. Product notes and plans live in `spec/` and `docs/`.

## Build, Test, and Development Commands
Set up the backend with `python3.10 -m venv .venv && .venv/bin/pip install -e '.[dev]'`. Run the API with `.venv/bin/uvicorn math_im_book.api.app:create_app --factory --reload`. Run backend tests with `.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache`.

For the frontend, work from `frontend/`: `npm install`, `npm run dev` for Vite, `npm run build` for a production bundle, and `npm run test` for Vitest. Build the frontend before manually checking `/` through the FastAPI app, since `create_app()` serves `frontend/dist`.

To clear all local runtime history data, run `python scripts/clear_history.py` from the repo root (or `.venv/bin/python scripts/clear_history.py`). This script removes all entries under `data/chats/sessions/` and `data/knowledge/`, then resets `data/chats/sessions_index.json` to an empty `{"sessions": []}` payload.

## Coding Style & Naming Conventions
Follow the existing style in the repo: 4 spaces in Python, 2 spaces in Vue/TypeScript blocks, and descriptive snake_case for Python modules like `context_selector.py`. Use PascalCase for Vue components like `ReaderPanel.vue`, camelCase for TS helpers and store actions, and keep tests named `test_<behavior>.py`. Prefer small, explicit functions over shared magic, and add comments only when the intent is not obvious from the code.

## Testing Guidelines
Backend tests use `pytest` with `tests/` and `src/` already configured in `pyproject.toml`. Frontend tests use `vitest`. Add or update tests with every behavior change, especially around API routes, orchestration, persistence, and prompt configuration flows like answer styles. Mirror the target module when adding tests, for example `src/math_im_book/services/planner.py` -> `tests/services/test_planner.py`.

## Commit & Pull Request Guidelines
Recent history mixes short imperative subjects (`update app`, `update web`) with conventional prefixes (`feat: ...`). Prefer concise imperative commit messages and use prefixes like `feat:`, `fix:`, or `docs:` when they add clarity. PRs should describe the user-visible change, list verification commands you ran, link related specs or issues, and include screenshots for frontend changes that affect layout or flow.

## Security & Configuration Tips
Do not commit secrets from `data/credentials/credentials.json`. Keep local chat and knowledge artifacts in `data/` out of review unless they are intentionally part of the change. `data/config/answer_styles/` is the exception: those Markdown prompt files and the style index are part of the application and should be reviewed and committed when changed.
