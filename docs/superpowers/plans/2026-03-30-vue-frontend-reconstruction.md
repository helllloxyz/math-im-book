# Vue Frontend Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current vanilla JS/CSS workspace with a modern Vue 3 + Tailwind CSS application in a `frontend/` directory, specifically optimized for LaTeX rendering and a professional "Math Reader" experience.

**Architecture:** A three-column grid layout (Explorer, Chat, Reader) powered by Vue 3 Composition API, Vite for bundling, and KaTeX for mathematical rendering. The frontend will communicate with the existing FastAPI backend via a Vite proxy.

**Tech Stack:** Vue 3, Vite, Tailwind CSS, @tailwindcss/typography, KaTeX, Lucide Vue (icons).

---

## Task 1: Project Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`

- [ ] **Step 1: Create the frontend directory and package.json**

```json
{
  "name": "math-im-book-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "katex": "^0.16.8",
    "lucide-vue-next": "^0.300.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "@tailwindcss/typography": "^0.5.10",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vue-tsc": "^1.8.0"
  }
}
```

- [ ] **Step 2: Initialize Tailwind and PostCSS**

`frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ['Charter', 'Merriweather', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
```

`frontend/postcss.config.js`:
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 3: Configure Vite with API Proxy**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: Create index.html and basic directory structure**

`frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>math-im-book</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
  </head>
  <body class="bg-slate-50 antialiased">
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 5: Run npm install**

Run: `cd frontend && npm install`

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "chore: scaffold vue frontend project"
```

---

## Task 2: Core Layout Shell

**Files:**
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/style.css`

- [ ] **Step 1: Set up the main entry point**

`frontend/src/main.ts`:
```typescript
import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

createApp(App).mount('#app')
```

`frontend/src/style.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #app {
  height: 100%;
  margin: 0;
}
```

- [ ] **Step 2: Create the App shell with the three-column grid**

`frontend/src/App.vue`:
```vue
<template>
  <div class="flex h-screen overflow-hidden text-slate-900 font-sans">
    <!-- Slim Rail -->
    <aside class="w-14 bg-slate-900 flex flex-col items-center py-6 space-y-6 text-slate-400 shrink-0">
      <div class="p-2 text-white bg-slate-800 rounded-xl cursor-pointer">
        <MessageSquare class="w-6 h-6" />
      </div>
      <div class="p-2 hover:text-white transition-colors cursor-pointer">
        <BookOpen class="w-6 h-6" />
      </div>
    </aside>

    <!-- Explorer Sidebar -->
    <div class="w-72 bg-white border-r border-slate-200 flex flex-col shadow-sm shrink-0">
      <div class="p-4 border-b border-slate-100 h-1/2 overflow-y-auto">
        <h2 class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Sessions</h2>
        <div class="text-sm text-slate-500 italic">No sessions loaded.</div>
      </div>
      <div class="p-4 flex-1 overflow-y-auto">
        <h2 class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Outline</h2>
        <div class="text-sm text-slate-500 italic">Loading outline...</div>
      </div>
    </div>

    <!-- Center Chat -->
    <main class="flex-1 flex flex-col bg-white relative min-w-0">
      <header class="h-14 border-b border-slate-100 flex items-center px-8 justify-between shrink-0">
        <div class="text-sm font-medium text-slate-700">New Conversation</div>
      </header>
      <div class="flex-1 overflow-y-auto p-8">
        <!-- Messages will go here -->
      </div>
      <footer class="p-6">
        <!-- Composer will go here -->
        <div class="max-w-3xl mx-auto h-24 bg-slate-50 border border-slate-200 rounded-2xl"></div>
      </footer>
    </main>

    <!-- Right Reader -->
    <aside class="w-[448px] bg-slate-50 border-l border-slate-200 overflow-y-auto shrink-0">
      <div class="p-10 bg-white min-h-full shadow-sm">
        <div class="text-sm text-slate-400 italic">Select a node to read.</div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { MessageSquare, BookOpen } from 'lucide-vue-next'
</script>
```

- [ ] **Step 3: Run dev server to verify layout**

Run: `cd frontend && npm run dev`
Expected: View the three-column layout in the browser.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add basic layout shell"
```

---

## Task 3: State Management & API Services

**Files:**
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/stores/workspace.ts`

- [ ] **Step 1: Create the API client**

`frontend/src/services/api.ts`:
```typescript
export const api = {
  async getSessions() {
    const res = await fetch('/api/sessions')
    return res.json()
  },
  async getOutline() {
    const res = await fetch('/api/outline')
    return res.json()
  },
  async getNode(id: string) {
    const res = await fetch(`/api/nodes/${encodeURIComponent(id)}`)
    return res.json()
  },
  async getSession(id: string) {
    const res = await fetch(`/api/sessions/${encodeURIComponent(id)}`)
    return res.json()
  },
  async ask(payload: any) {
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    return res.json()
  },
  async fork(sessionId: string, payload: any) {
    const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/fork`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    return res.json()
  }
}
```

- [ ] **Step 2: Create the reactive workspace store**

`frontend/src/stores/workspace.ts`:
```typescript
import { reactive } from 'vue'
import { api } from '@/services/api'

export const workspace = reactive({
  sessions: [] as any[],
  outline: [] as any[],
  currentSession: null as any,
  currentNode: null as any,
  loading: false,

  async fetchOutline() {
    const data = await api.getOutline()
    this.outline = data.nodes || []
  },

  async fetchSessions() {
    const data = await api.getSessions()
    this.sessions = data.sessions || []
  },

  async selectSession(id: string) {
    this.loading = true
    try {
      this.currentSession = await api.getSession(id)
    } finally {
      this.loading = false
    }
  },

  async selectNode(id: string) {
    this.currentNode = (await api.getNode(id)).node
  }
})
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/stores/workspace.ts
git commit -m "feat: add api services and workspace store"
```

---

## Task 4: Explorer Components (Sessions & Outline)

**Files:**
- Create: `frontend/src/components/explorer/SessionTree.vue`
- Create: `frontend/src/components/explorer/BookOutline.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Implement SessionTree**

`frontend/src/components/explorer/SessionTree.vue`:
```vue
<template>
  <div class="space-y-1">
    <div 
      v-for="s in workspace.sessions" 
      :key="s.session_id"
      @click="workspace.selectSession(s.session_id)"
      class="px-3 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors"
      :class="workspace.currentSession?.session_id === s.session_id ? 'bg-blue-50 text-blue-700 border border-blue-100' : 'text-slate-600 hover:bg-slate-50'"
    >
      {{ s.session_id }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { workspace } from '@/stores/workspace'
</script>
```

- [ ] **Step 2: Implement BookOutline**

`frontend/src/components/explorer/BookOutline.vue`:
```vue
<template>
  <div class="space-y-3">
    <div v-for="node in workspace.outline" :key="node.id">
      <div 
        @click="workspace.selectNode(node.id)"
        class="text-sm font-medium cursor-pointer hover:text-blue-600 transition-colors"
        :class="workspace.currentNode?.id === node.id ? 'text-blue-600' : 'text-slate-700'"
      >
        {{ node.title || node.id }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { workspace } from '@/stores/workspace'
</script>
```

- [ ] **Step 3: Integrate components into App.vue**

Update `App.vue` to use the new components and call `fetchOutline` and `fetchSessions` on `onMounted`.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: implement explorer components"
```

---

## Task 5: Chat Interface & KaTeX Integration

**Files:**
- Create: `frontend/src/components/chat/MathText.vue`
- Create: `frontend/src/components/chat/ChatMessage.vue`
- Create: `frontend/src/components/chat/ChatComposer.vue`

- [ ] **Step 1: Create a MathText component for KaTeX rendering**

`frontend/src/components/chat/MathText.vue`:
```vue
<template>
  <div v-html="renderedContent" class="inline-block"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import katex from 'katex'

const props = defineProps<{ content: string, display?: boolean }>()

const renderedContent = computed(() => {
  try {
    return katex.renderToString(props.content, {
      throwOnError: false,
      displayMode: props.display
    })
  } catch (e) {
    return props.content
  }
})
</script>
```

- [ ] **Step 2: Implement ChatMessage with basic LaTeX parsing**

`frontend/src/components/chat/ChatMessage.vue`:
```vue
<template>
  <div class="flex items-start space-x-4">
    <div 
      class="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center text-xs font-bold"
      :class="message.role === 'assistant' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'"
    >
      {{ message.role === 'assistant' ? 'AI' : 'U' }}
    </div>
    <div class="flex-1 pt-1">
      <div class="prose prose-slate prose-sm max-w-none text-slate-800">
        {{ message.content }}
      </div>
      <!-- Actions omitted for brevity in plan, but will be in implementation -->
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ message: any }>()
</script>
```

- [ ] **Step 3: Implement ChatComposer**

`frontend/src/components/chat/ChatComposer.vue` will handle the `api.ask` call and update `workspace.currentSession`.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: implement chat components with basic katex support"
```

---

## Task 6: Math Reader Panel

**Files:**
- Create: `frontend/src/components/reader/ReaderPanel.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Implement the ReaderPanel with Typography and KaTeX**

`frontend/src/components/reader/ReaderPanel.vue`:
```vue
<template>
  <div v-if="workspace.currentNode" class="p-10 bg-white min-h-full shadow-sm">
    <article class="prose prose-slate max-w-none">
      <div class="text-[10px] font-bold text-blue-600 uppercase tracking-tighter mb-2">
        {{ workspace.currentNode.type }}
      </div>
      <h1 class="text-2xl font-serif text-slate-900 border-b border-slate-100 pb-4 mb-8 tracking-tight">
        {{ workspace.currentNode.title }}
      </h1>
      <div class="text-base text-slate-700 leading-relaxed whitespace-pre-wrap font-serif">
        {{ workspace.currentNode.detail }}
      </div>
    </article>
  </div>
  <div v-else class="p-10 text-slate-400 italic">
    Select a node to read.
  </div>
</template>

<script setup lang="ts">
import { workspace } from '@/stores/workspace'
</script>
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: implement reader panel"
```

---

## Task 7: Final Polishing & Integration

- [ ] **Step 1: Enhance LaTeX parsing in Chat and Reader**
Implement a robust regex-based parser that replaces `$ ... $` and `$$ ... $$` with `<MathText />` components or calls `katex.renderToString`.

- [ ] **Step 2: Add visual feedback (Loading states, Transitions)**

- [ ] **Step 3: Clean up existing static files**
Once the Vue frontend is verified, the old `src/math_im_book/api/static/` files can be removed or archived, and `app.py` updated to serve the new `frontend/dist`.

- [ ] **Step 4: Final end-to-end verification**
Run the FastAPI backend and the Vite dev server, verifying that all flows (Ask, Fork, Read) work as expected.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: final polish and integration"
```
