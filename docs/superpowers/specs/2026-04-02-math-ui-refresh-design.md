# Math UI Refresh Design

**Goal**

Refresh the Vue frontend so it reads as a consumer-friendly math/physics chatbot with a more professional, long-session desktop reading experience.

**Product Direction**

- The product remains chat-first, not a paper reader.
- The target user is doing sustained math or physics exploration, derivation, and explanation.
- The interface should feel approachable on first use and increasingly credible during extended reading.

**Visual Thesis**

An approachable modern chat workspace with a calm professional layer: restrained color, quieter motion, stronger typography, clearer formula treatment, and consistent panel hierarchy.

**Constraints**

- Desktop-first only for this phase.
- Keep the existing three-column information architecture.
- Do not change core workflows or data flow.
- Prefer Tailwind and existing component structure.

## Current Problems

1. The top-level layout is structurally good but visually reads as a generic AI SaaS shell.
2. Chat, navigation, reader, and settings components do not fully share the same visual grammar.
3. Formula presentation is functional but not yet a defining product strength.
4. The empty state reads like product marketing instead of a math/physics work entry point.
5. Reader and settings surfaces feel like they come from different products.

## Design Principles

1. Keep the UI friendly, but reduce decorative energy.
2. Let formulas, explanations, and context carry the product identity.
3. Use one accent color system across the app.
4. Establish hierarchy with spacing, border, and subtle background changes before shadows.
5. Keep interaction affordances obvious, but visually quiet.

## Visual System

### Color

Adopt a single blue-gray accent system with neutral surfaces.

```css
:root {
  --bg-app: #f4f6f8;
  --bg-panel: #fbfcfd;
  --bg-elevated: #ffffff;
  --bg-muted: #eef2f5;

  --text-strong: #1d2733;
  --text-primary: #314052;
  --text-secondary: #5f6f82;
  --text-muted: #8a97a6;

  --border-soft: #e3e8ee;
  --border-strong: #cfd7e3;

  --accent: #3f5f7a;
  --accent-hover: #324e66;
  --accent-soft: #e8f0f6;

  --math-soft: #f6f8fb;
  --math-border: #d9e2ec;
}
```

Rules:

- Use one accent only.
- Remove blue glow shadows.
- Use red/green/yellow only for explicit states.

### Typography

- UI surfaces: sans-serif.
- Reading surfaces: serif for long-form text and contextual summaries.
- Do not switch the entire product to serif.
- Use stronger line-height and spacing instead of heavy weights.

### Spacing

- Outer panels: 24px to 32px rhythm.
- Inner controls: 12px to 20px rhythm.
- Long-form content gets larger vertical spacing than UI controls.

### Shape and Elevation

- Panels and modals: 16px radius.
- Buttons and inputs: 10px to 12px radius.
- Default to no shadow or very light shadow.
- Use border and background before elevation.

### Motion

- Keep only subtle fade and small translate transitions.
- Remove playful bounce and rotation effects from core UI.
- Loading indicators should read as calm system status.

## Information Architecture

### Left Rail

- Keep as compact mode navigation.
- Use dark blue-gray, not near-black.
- Active state uses surface contrast instead of glow.
- Add tooltip semantics for mode clarity.

### Explorer Sidebar

- Keep as a secondary organizational layer.
- Use a very light panel background.
- Normalize section headings.
- Remove bright decorative indicators.

### Main Chat Area

- This remains the primary work surface.
- Preserve familiar chat behavior.
- Make responses read more like explanation blocks than support bubbles.

### Reader Panel

- Keep as the secondary contextual workspace.
- Reduce visual weight slightly so the chat column remains primary.
- Improve chapter and symbol presentation.

## Component Design

### App.vue

- Rebalance panel backgrounds and borders.
- Replace the current empty state with a math/physics work entry state.
- Reduce loading animation intensity.
- Normalize top bar icon emphasis.

### ChatComposer.vue

- Keep the current composer interaction pattern.
- Replace the placeholder with math/physics-oriented prompts.
- Remove low-value branding text.
- Use restrained accent button styling.

### ChatMessage.vue

- Keep distinct user and assistant messages.
- Reduce generic IM bubble styling.
- Improve assistant content readability and structure.
- Keep actions available but visually quieter.

### MathText.vue and KaTeX

- Standardize display formula surfaces across chat and reader.
- Allow horizontal scrolling without looking like a code block.
- Increase block formula breathing room.

### SessionTree.vue

- Keep the branching structure.
- Make it read as a question tree instead of a message log.
- Quiet the badge and menu surfaces.

### BookOutline.vue

- Make it read like a living table of contents.
- Align selected and hover states with SessionTree.
- Reduce icon and type-label noise.

### ReaderPanel.vue

- Keep serif-based reading.
- Make metadata more note-like and less dashboard-like.
- Treat summary as contextual lead-in.
- Strengthen Symbol Registry as a product-specific module.

### NodeReferences.vue

- Present references more like scholarly cross-links.
- Keep related sessions but make them less pill-heavy.

### ModelSettings.vue and GlobalSettings.vue

- Unify modal language across both dialogs.
- Remove bright admin-dashboard styling.
- Keep inputs modern but quieter.

## Execution Scope

### Phase 1

- Global tokens and motion cleanup
- App shell rebalance
- Chat composer and chat message refresh
- Formula surface normalization

### Phase 2

- Session tree and outline polish
- Reader panel and references polish
- Settings modal unification

## Testing Expectations

- Run frontend unit tests after changes.
- Run a production build to catch class or type regressions.
- Manually inspect desktop layout balance, empty state, message readability, and reader rhythm.

## Acceptance Criteria

1. The app still feels immediately usable as a chat product.
2. The visual language is consistent across shell, chat, reader, and settings.
3. The empty state and formulas clearly signal math/physics specialization.
4. The main chat column remains the visual primary workspace.
5. The interface supports long reading sessions without feeling loud or generic.
