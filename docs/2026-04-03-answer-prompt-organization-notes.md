# Answer Prompt Organization Notes

## Background

Observed behavior:

- User asks a broad learning question such as `学习下线性代数`.
- Assistant returns a fairly long overview that expands multiple subtopics.
- This feels mismatched for a concise exploration flow where the user should get:
  - a short abstract summary first
  - the main concepts and their relationships
  - a few heuristic follow-up questions
  - room to explore gradually

The current prompt setup does not explicitly encode that behavior.

## Current Prompt Management

The current answer prompting path is file-based and centered on answer styles.

### Configuration

- Style index: [`data/config/answer_styles/index.json`](/mnt/e/code/math-im-book/data/config/answer_styles/index.json)
- Style instruction bodies:
  - [`data/config/answer_styles/default.md`](/mnt/e/code/math-im-book/data/config/answer_styles/default.md)
  - [`data/config/answer_styles/concise.md`](/mnt/e/code/math-im-book/data/config/answer_styles/concise.md)
  - [`data/config/answer_styles/step-by-step.md`](/mnt/e/code/math-im-book/data/config/answer_styles/step-by-step.md)
  - [`data/config/answer_styles/intuitive.md`](/mnt/e/code/math-im-book/data/config/answer_styles/intuitive.md)
  - [`data/config/answer_styles/rigorous.md`](/mnt/e/code/math-im-book/data/config/answer_styles/rigorous.md)

### Loading

- Repository loader: [`src/math_im_book/storage/answer_styles.py`](/mnt/e/code/math-im-book/src/math_im_book/storage/answer_styles.py)
- Domain types: [`src/math_im_book/domain/models.py`](/mnt/e/code/math-im-book/src/math_im_book/domain/models.py)

This layer:

- reads `index.json`
- loads one Markdown file per style id
- falls back to hard-coded defaults if files are missing or invalid

### API and UI Exposure

- API endpoint: [`src/math_im_book/api/app.py:166`](/mnt/e/code/math-im-book/src/math_im_book/api/app.py:166)
- Frontend store fetch: [`frontend/src/stores/workspace.ts:328`](/mnt/e/code/math-im-book/frontend/src/stores/workspace.ts:328)
- Frontend selector UI: [`frontend/src/components/chat/ChatComposer.vue:55`](/mnt/e/code/math-im-book/frontend/src/components/chat/ChatComposer.vue:55)

### Runtime Prompt Assembly

- Assembly point: [`src/math_im_book/services/orchestrator.py:320`](/mnt/e/code/math-im-book/src/math_im_book/services/orchestrator.py:320)

Current assembly logic:

1. Start with base string:
   - `Answer math questions clearly and directly using the provided context.`
2. Append the default style instructions
3. If a non-default style is selected, append that style instructions too

This means `concise` is currently applied as:

- `base + default + concise`

not as:

- `base + concise`

## Current Limitation

The current system has a single explicit axis: `answer style`.

That is enough for differences like:

- concise vs detailed
- intuitive vs rigorous
- step-by-step vs balanced

But it is not enough for the more subtle behavior the product likely wants for open-ended learning prompts.

The missing distinction is between:

1. **Verbosity**
   - how long the answer should be
2. **Teaching organization**
   - how ideas should be introduced and sequenced
3. **Interaction affordances**
   - whether the assistant should end with prompts, choices, next questions, or examples

Right now those concerns are implicitly mixed together inside style files.

## Why The Linear Algebra Example Feels Off

For a user prompt like `学习下线性代数`, the current concise/default style combination does not explicitly require:

- top-down structure
- a short abstract framing first
- concept map over exhaustive explanation
- restraint against enumerating many subtopics
- heuristic follow-up questions
- progressive exploration

So the model naturally drifts toward a generic survey response:

- definition
- topic list
- several sections
- resources

This is not necessarily wrong. It is just not aligned with the intended exploratory interaction.

## Recommended Prompt Boundary

The more stable design is to split prompting into multiple layers instead of treating everything as a style.

### 1. Base Contract

This should contain stable, global rules:

- answer the user directly
- remain mathematically correct
- preserve notation where possible
- use provided context faithfully
- avoid unsupported claims

This layer should stay small and durable.

### 2. Teaching Strategy

This should control how the explanation is organized.

Examples:

- `overview-first`
- `guided-discovery`
- `problem-solving`
- `formal-derivation`

This is the missing layer for the current issue.

For example, an `overview-first` strategy could say:

- start with a 2-4 sentence big-picture description
- name only the main concepts
- emphasize relationships between them
- avoid detailed expansion unless the user asks
- end with a small number of good next questions

### 3. Verbosity

This should only control length and density.

Examples:

- `concise`
- `balanced`
- `detailed`

This avoids overloading `concise` with organizational rules it should not own.

### 4. Output Affordances

This layer should represent optional reply behaviors.

Examples:

- include heuristic follow-up questions
- include one concrete example
- use numbered steps
- avoid long bullet lists

These should be modular flags or composable prompt fragments rather than hidden inside one broad style label.

## Proposed Mental Model

Prompt assembly should eventually look more like:

1. base contract
2. teaching strategy
3. verbosity
4. optional affordances

Instead of:

1. base
2. default style
3. selected style

## Suggested Target Behavior For Broad Learning Questions

For prompts like:

- `学习下线性代数`
- `我想学傅里叶变换`
- `帮我理解群论`

The intended response in a concise exploratory mode would be closer to:

1. one short framing sentence about what the subject studies
2. three to four central concepts
3. explicit relationships among those concepts
4. no full expansion of every item
5. two or three heuristic follow-up questions

Example interaction shape:

- “线性代数主要研究向量、矩阵，以及矩阵表示的线性变换。”
- “你可以先把它看成两条主线：一条是解线性方程组，一条是研究空间中的变换。”
- “核心概念先抓住：向量、矩阵、线性变换、特征值。”
- “如果你愿意，我们可以下一步选一个入口继续：从几何直觉、矩阵运算，还是特征值开始？”

That shape is currently not encoded anywhere in the prompt system.

## Pragmatic Migration Options

### Option A: Minimal Change

Keep the existing answer-style system and add one or two new styles, for example:

- `guided-concise`
- `overview-first`

Those styles would explicitly encode:

- top-down first
- short abstract framing
- concept relationships over exhaustive detail
- gradual exploration
- heuristic follow-up questions

Pros:

- lowest implementation cost
- easy to test quickly
- no major data model changes

Cons:

- style labels become overloaded
- prompt semantics will get messy over time
- future combinations become awkward

### Option B: Structured Prompt Composition

Refactor configuration into separate dimensions.

Possible layout:

- `data/config/prompts/base.md`
- `data/config/prompts/pedagogy/overview-first.md`
- `data/config/prompts/pedagogy/guided-discovery.md`
- `data/config/prompts/verbosity/concise.md`
- `data/config/prompts/verbosity/balanced.md`
- `data/config/prompts/affordances/heuristic-questions.md`

Pros:

- clear boundaries
- easier to reason about prompt behavior
- supports composition without semantic overload

Cons:

- larger implementation change
- UI and API will need a new model
- more decisions about defaults and compatibility

## Recommendation

Recommended sequence:

1. Short term: validate behavior with a minimal new style such as `overview-first` or `guided-concise`
2. Medium term: if the product direction proves useful, split prompt configuration into:
   - base contract
   - teaching strategy
   - verbosity
   - optional affordances

This keeps the near-term experiment cheap while preserving a cleaner long-term direction.

## Open Design Questions

These questions should be answered before implementing the larger refactor:

1. Is the desired behavior global, or only for a “concise learning” mode?
2. Should heuristic follow-up questions always appear, or only for broad/open-ended prompts?
3. Should top-down organization be the default for all conceptual questions, or only for certain styles?
4. Should the UI expose multiple prompt dimensions, or should composition remain internal?
5. How should backward compatibility work for existing sessions that only store `default_answer_style_id`?

## Concrete Next Step Candidates

If this is picked up later, the next concrete tasks are:

1. Draft one new prompt file that encodes `overview-first + concise + heuristic questions`
2. Test it manually against broad learning prompts
3. Decide whether that is enough, or whether multi-axis prompt composition is justified
