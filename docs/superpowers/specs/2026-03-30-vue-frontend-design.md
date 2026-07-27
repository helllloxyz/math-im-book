# Vue Frontend Design: Math Chat & Reader Workspace

## 1. Context & Goal
The current vanilla JS/CSS frontend is functional but lacks the visual polish and component-based structure required for a professional mathematical learning environment. This design replaces it with a **Vue 3 + Tailwind CSS** application.

The primary goal is to provide a "conversation-led writing workspace" where users can explore math through chat and see their knowledge accumulate into a structured, LaTeX-rendered book.

## 2. Tech Stack
- **Vue 3:** Composition API for logic encapsulation.
- **Vite:** Fast development server and optimized production builds.
- **Tailwind CSS:** Utility-first styling with `@tailwindcss/typography` for book content.
- **KaTeX:** High-performance LaTeX rendering for both chat and reader panels.
- **Vue Router:** Client-side routing for sessions and nodes.
- **Existing API:** No changes to the FastAPI backend or its endpoints.

## 3. Architecture & Components

### 3.1 Layout Shell (`App.vue`)
A three-column grid layout with a persistent navigation rail.
- **Widths:** Left (14rem/72px rail + 18rem/288px explorer), Center (Flexible), Right (28rem/448px reader).

### 3.2 Navigation & Explorer
- **`Sidebar.vue`**: Slim vertical rail with icons (Chat, Book, Settings).
- **`Explorer.vue`**: Sidebar containing:
  - **`SessionTree.vue`**: Hierarchical list of chat sessions and forks.
  - **`BookOutline.vue`**: Hierarchical tree of the current knowledge graph.

### 3.3 Chat Interface (`ChatInterface.vue`)
- **`MessageCard.vue`**: Renders user and assistant messages.
  - Supports Markdown + KaTeX.
  - Actions: `Fork`, `Copy`, `Regenerate`.
- **`ChatComposer.vue`**: Multi-line input for questions.
- **`BranchHeader.vue`**: Displays the current session focus and parent-child relationships.

### 3.4 Math Reader (`Reader.vue`)
- **`NodeContent.vue`**: Renders the "accumulated" math chapter.
  - Uses `@tailwindcss/typography` for "Prose" styling.
  - Serif fonts for body text, KaTeX for formulas.
- **`NodeReferences.vue`**: Lists related sessions and incoming/outgoing node links.

## 4. Design Aesthetics
- **Color Palette:** Neutral/Slate tones for the UI, with blue accents for actions.
- **Typography:**
  - UI: Inter or similar sans-serif.
  - Book: Computer Modern or a high-quality serif (e.g., Charter, Merriweather) for a classical "math book" feel.
- **Spacing:** Generous white space and clear borders for a modern, calm interface.

## 5. Interaction Model
- **Clicking a session** in the Explorer updates the Center (Chat).
- **Clicking an outline node** or an inline reference updates the Right (Reader).
- **Forking an answer** creates a new session and switches the Center focus.

## 6. Integration & Development
- **Directory:** `frontend/` in the project root.
- **Vite Proxy:** `vite.config.ts` will proxy `/api` to `http://localhost:3000`.
- **Build Output:** The FastAPI app can be configured to serve the built Vue app's `index.html` and static assets.

## 7. Deferred Items (Out of Scope)
- Full Markdown editor (Reader remains read-only).
- Graph visualization of nodes.
- Real-time collaborative editing.
