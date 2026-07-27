```markdown
# Design System Document: The Scholarly Monograph

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Scriptorium"**

This design system rejects the frantic, "app-like" density of modern software in favor of the quiet, authoritative presence of a high-end mathematical journal. We are building a digital environment that prioritizes the "Aha!" moment over the "Click" count. 

By utilizing **intentional asymmetry** and **high-contrast typography scales**, we move away from standard grid-locked templates. The layout should feel like a physical desk—layers of high-grade paper and mathematical surfaces arranged with purpose. We break the "template" look by using generous vertical rhythm (the "breath" between thoughts) and tonal depth rather than structural lines. The result is a UI that feels curated, rigorous, and intellectually spacious.

---

## 2. Colors: Tonal Architecture
Our palette is a study in "Dusty Blue" and "Cool Stone." It is designed to reduce eye strain during prolonged periods of intense concentration.

*   **Primary (`#264761`):** Use for high-emphasis actions and primary brand touchpoints.
*   **Primary Container (`#3F5F7A`):** Our signature "Dusty Blue." This is the intellectual heart of the system, used for focus states and significant content backdrops.
*   **Surface Hierarchy:** We utilize a "No-Line" rule. Boundaries are defined by shifting from `surface` (`#f8f9fb`) to `surface-container-low` (`#f2f4f6`). 

**The "No-Line" Rule:** 
Explicitly prohibit 1px solid borders for sectioning content. To separate a navigation sidebar from a main workspace, use a background shift from `surface` to `surface-container-low`. The eye should perceive a change in "weight" rather than a hard edge.

**Glass & Gradient Rule:** 
For floating panels or symbol registries, use Glassmorphism. Apply a backdrop-blur (12px+) to `surface-container-lowest` at 85% opacity. This prevents the UI from feeling "stuck" on top of the math; it allows the complexity of the equations to subtly bleed through, maintaining context.

---

## 3. Typography: The Dual-Type System
We employ a sophisticated hierarchy that separates *functional* interaction from *intellectual* content.

*   **The Intellectual Core (Serif - Newsreader/Georgia):** 
    All "Math Surfaces," long-form articles, and chat responses use the Serif family. This signals rigor and history. 
    *   *Display-lg/md:* Use for theorem titles or major historical figures. 
    *   *Body-lg:* Your default for "the conversation." High line-height (1.6) is mandatory.
*   **The Functional Shell (Sans-Serif - Inter):** 
    Used exclusively for labels, navigation, and inputs. 
    *   *Label-md/sm:* Small-caps or increased letter spacing (0.05em) for a "blueprint" aesthetic.
    
**Identity through Scale:** 
Maintain a high contrast between `headline-lg` and `body-md`. This mimics the layout of a 19th-century monograph where the title is an event, and the text is a texture.

---

## 4. Elevation & Depth: Tonal Layering
Traditional shadows are too "digital" for this system. We use **Tonal Layering** to create hierarchy.

*   **The Layering Principle:** 
    Place a `surface-container-lowest` (#ffffff) card on a `surface-container-low` (#f2f4f6) background. The contrast is enough to create a "lift" without a single pixel of shadow.
*   **Ambient Shadows:** 
    When a floating element (like a symbol picker) is required, use an extra-diffused shadow: `box-shadow: 0 12px 40px rgba(29, 39, 51, 0.06)`. Note the tint—the shadow is a deep blue-gray, not black.
*   **The Ghost Border:** 
    For "Math Surfaces" where containment is critical for readability, use the `outline-variant` at 20% opacity. It should be felt more than seen.

---

## 5. Components: Rigorous Utility

### Chat Containers (The Article Style)
*   **Style:** `surface-container-lowest` background, 20px (`xl`) corner radius.
*   **Rule:** No dividers between messages. Use 32px of vertical spacing to separate the user's inquiry from the system's proof.

### Math Surfaces (Block Math)
*   **Style:** Background `surface-container-low` (#f6f8fb) with a `ghost border` using `#D9E2EC`.
*   **Radius:** 8px (`DEFAULT`).
*   **Layout:** Centered equations with generous internal padding (min 24px).

### Symbol Registries (White Cards)
*   **Style:** `surface-container-lowest` cards. 
*   **Interaction:** On hover, shift background to `primary-fixed` (#cce5ff) subtly.

### Buttons & Inputs
*   **Primary Button:** `primary` background with `on-primary` (white) text. Roundedness: `full`.
*   **Tertiary Button:** No background, `primary` text, Serif font. Used for "Read Theorem Details."
*   **Inputs:** `surface-container-highest` background, no border. The bottom edge should have a 2px `primary` line only when focused.

### Forbid Divider Lines
Do not use horizontal rules (`<hr>`). Use white space from the spacing scale (16px, 32px, 64px) or a change in surface tier to denote a new section.

---

## 6. Do’s and Don’ts

### Do:
*   **Do** allow equations to breathe. High information density is achieved through clear typography, not crowding.
*   **Do** use asymmetrical layouts (e.g., a wide left margin for "margin notes" or "symbol definitions").
*   **Do** use "Quiet Motion." Transitions should be slow (300ms+) and use "Expressive" easing (cubic-bezier 0.4, 0, 0.2, 1).

### Don't:
*   **Don't** use pure black `#000000` for text. Use `on-surface` (#1D2733) to keep the "ink-on-paper" feel.
*   **Don't** use 1px solid borders to create grids. It breaks the scholarly atmosphere and feels like a spreadsheet.
*   **Don't** use vibrant, saturated colors. Every color must feel like it has been aged in a library.

### Accessibility Note:
Ensure that while we use "Ghost Borders" and tonal shifts, the contrast ratio between the `surface` and `on-surface` remains at least 4.5:1 for all mathematical proofs and body text. Rigor requires readability.```