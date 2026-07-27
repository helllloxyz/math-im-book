# Self-Evolving USER.md Design

## 1. Goal

The system should behave like a long-term mathematical learning and writing agent, not like a chat app that occasionally saves answers.

`USER.md` is the long-term user profile layer. It records how this user learns, what background knowledge they already have, how much detail they usually need, and what kinds of content should become durable knowledge. The profile should guide agent orchestration: whether the system answers directly, asks for clarification, reuses existing knowledge, creates pending drafts, writes knowledge nodes first, or suggests saving an explanation.

The core principle is:

```text
Answers belong to Chat.
Facts belong to Knowledge.
Preferences belong to USER.md.
```

And for persistence:

```text
Persisting knowledge is not saving an answer.
It is extracting reusable mathematical content with clear boundaries.
```

## 2. Product Problem

The current flow can feel backwards:

1. The user asks a question.
2. The assistant answers immediately.
3. A background job later tries to compile a knowledge node.
4. The generated node may contain process text such as "compiled from the question".

This creates a conceptual mismatch. If the answer already exists, the later knowledge node feels like an afterthought. If the knowledge node is meant to be a reusable source, it should often exist before the final answer cites it.

The product design already points toward a different flow: first judge whether existing knowledge is enough; if knowledge is missing, create bounded pending drafts or knowledge nodes; then answer with explicit references when appropriate.

`USER.md` should help the agent make that judgment in a user-specific way.

## 3. Layering

### 3.1 USER.md

Long-term user profile and orchestration policy.

It stores:

- Learning preferences.
- Mathematical background.
- Preferred explanation depth.
- Persistence preferences.
- Notation habits.
- Agent orchestration preferences.
- Observed patterns that the system has learned over time.

It must not store mathematical facts that belong in the knowledge base.

### 3.2 Project Or Book Context

Current local goal and scope, such as "learning linear algebra" or "writing differential geometry notes".

It can override or narrow `USER.md` for the current project. For example, the user may generally prefer intuitive explanations, but a specific book project may request rigorous theorem-first writing.

### 3.3 Knowledge Base

Durable mathematical content:

- Definitions.
- Theorems.
- Proof sketches.
- Canonical examples.
- Counterexamples.
- Bridge explanations.
- Notation decisions.
- Stable overview nodes.

Knowledge nodes should be readable as part of a growing mathematical book or notebook.

### 3.4 Chat Session

The interaction layer:

- Questions.
- Answers.
- Temporary explanations.
- Follow-up exploration.
- Forks.
- User feedback.

Chat is the primary interface, but it is not the durable source of mathematical truth.

## 4. USER.md Shape

The file should remain human-readable Markdown, because the user may inspect it and because Markdown fits the rest of the repository.

Recommended initial shape:

```markdown
# USER.md

## Background
- Comfortable with: linear algebra basics, calculus, basic proof language.
- Weak spots: abstract algebra, category theory.
- Preferred prerequisite level: undergraduate math.

## Learning Style
- Prefer top-down explanations for new topics.
- Start with intuition, then formal definition.
- Avoid repeating elementary definitions unless they are central to the current topic.
- Use examples when introducing an abstract object.

## Answer Depth
- Broad conceptual questions: medium-length overview.
- Specific definitions: precise and compact.
- Proof questions: step-by-step with key lemmas explicit.
- Applications: start from the motivating problem.

## Knowledge Persistence Policy
- Persist stable reusable facts, not one-off conversational phrasing.
- Persist definitions, theorem statements, proof skeletons, canonical examples, notation decisions, and bridge explanations.
- Do not persist broad introductory answers until enough subnodes exist.
- Do not persist speculative or uncertain explanations without confirmation.

## Agent Orchestration
- For broad exploratory questions, answer first and optionally suggest knowledge nodes.
- For key definitions or notation-sensitive topics, create or verify knowledge nodes before answering.
- For missing prerequisites, identify the gap and offer a small draft list.
- If the system is unsure whether to persist, ask or mark as pending draft rather than silently saving.

## Language And Tone
- Default language: Chinese.
- Keep explanations concise but not terse.
- Prefer mathematical clarity over motivational prose.

## Learned Observations
- The system may add dated observations here after repeated evidence.
```

## 5. Agent Orchestration Paths

The planner should not only choose between `reuse_answer` and `expand_with_drafts`. It should choose an orchestration path.

### 5.1 reuse_answer

Use when existing knowledge nodes can support the answer.

Behavior:

- Load active knowledge nodes.
- Answer directly.
- Cite the reused nodes.
- Do not create new knowledge nodes.

### 5.2 answer_only

Use when the question is useful to answer, but the result is not durable enough to persist.

Examples:

- Clarifying a small point.
- Giving a quick intuition.
- Answering a broad exploratory question for the first time.
- Responding to a one-off conversational request.

Behavior:

- Answer in chat.
- No knowledge job.
- No fake source link.

### 5.3 answer_then_suggest_drafts

Use when the user asks a broad or exploratory question that may lead to useful knowledge, but should not immediately become a formal node.

Example:

```text
用户：线性代数
```

Behavior:

- Give a medium-length overview.
- Suggest possible knowledge nodes, such as "向量空间", "线性映射", "矩阵表示".
- Let the user choose whether to generate them, or defer the decision to `/compact`.

### 5.4 draft_first_then_answer

Use when the answer depends on a stable definition, theorem, notation choice, proof skeleton, or bridge concept.

Example:

```text
用户：什么是向量空间的基？请给正式定义和例子。
```

Behavior:

- Create or verify the relevant knowledge node.
- Then answer using that node.
- Attach ready references, not pending links that look like sources.

### 5.5 ask_before_persist

Use when the agent is unsure whether content should become durable knowledge.

Behavior:

- Answer the user if possible.
- Ask for confirmation before writing nodes, or create visible pending drafts that are not yet formal knowledge.

## 6. Persistence Boundary

The system should persist content when it is stable, reusable, and has clear boundaries.

### 6.1 Persist By Default

- Definitions.
- Theorem statements.
- Proof skeletons.
- Canonical examples.
- Counterexamples.
- Notation decisions.
- Bridge explanations between concepts.
- Stable summaries after enough subnodes exist.

### 6.2 Do Not Auto-Persist

- One-off chat answers.
- Conversational phrasing.
- Study advice tied only to the current moment.
- Broad first-pass overviews without supporting subnodes.
- Long answers with unclear title or boundary.
- Provider fallback or process text.
- Speculative or uncertain explanations.

### 6.3 Pending Or Review First

- Intuitive analogies.
- Learning routes.
- Topic summaries.
- Cross-topic synthesis.
- Personal notes.
- Explanations that may be useful but are not yet stable.

These can become pending drafts and later be promoted during `/compact`.

## 7. Background-Aware Explanation

The same question should produce different orchestration depending on the user profile.

For a beginner asking "什么是线性代数":

- Prefer `answer_then_suggest_drafts`.
- Start with intuition and high-level structure.
- Avoid dumping a full chapter.
- Suggest a few foundational nodes.

For a mathematically strong user asking the same:

- Prefer `answer_only`.
- Give a compact structural description.
- Avoid repeating elementary matrix arithmetic.

For a user writing a book:

- Prefer `answer_then_suggest_drafts` or `draft_first_then_answer`.
- Produce a chapter-level structure.
- Suggest bounded knowledge nodes that can become part of the book.

## 8. Self-Evolving USER.md

`USER.md` should be system-maintained and self-evolving, but updates must be conservative.

### 8.1 Evidence Sources

The system can infer profile changes from:

- Repeated user corrections.
- Explicit user preferences.
- Regeneration choices.
- Follow-up questions that reveal missing background.
- Frequent requests for more rigor, more intuition, shorter answers, or more examples.
- Manual edits to generated knowledge nodes.

### 8.2 Update Policy

The system should not rewrite `USER.md` after every turn.

Recommended rules:

- Update only after explicit user instruction or repeated evidence.
- Prefer appending dated learned observations over rewriting stable sections.
- Promote observations into stable preferences during `/compact` or a profile review step.
- Keep every update small and explainable.
- Do not infer sensitive personal information.
- Do not treat one confused question as proof of weak background.

### 8.3 Update Modes

The system can support three modes:

```text
observe
Collect candidate observations but do not modify USER.md automatically.

suggest
Show proposed USER.md changes and ask for confirmation.

auto
Apply low-risk updates automatically, while keeping a visible change log.
```

The recommended default is `suggest` for early versions. Once stable, low-risk observations can move to `auto`.

## 9. Prompt And Planner Integration

`USER.md` should feed two major components.

### 9.1 Planner

The planner uses `USER.md` to decide:

- Whether the question is broad, specific, proof-oriented, notation-sensitive, or exploratory.
- Whether existing knowledge is enough.
- Whether the user likely needs prerequisite expansion.
- Whether the answer should be persisted.
- Which orchestration path to choose.

### 9.2 Answer Prompt Compiler

The answer compiler uses `USER.md` to decide:

- Language.
- Explanation depth.
- Amount of prerequisite detail.
- Whether to lead with intuition or formalism.
- Whether to suggest next knowledge nodes.

### 9.3 Knowledge Compiler And Compact

The knowledge compiler and `/compact` use `USER.md` to decide:

- Which pending drafts deserve promotion.
- Whether to split or merge knowledge nodes.
- Whether a broad overview has enough supporting nodes to become durable.
- How much explanatory detail belongs in a node for this user.

## 10. Priority Order

Recommended instruction priority:

```text
System correctness and safety
> Project or book context
> USER.md
> Session strategy agent
> Answer style
> One-off user wording
```

`USER.md` should influence defaults, but it must not override mathematical correctness or explicit current-session instructions.

## 11. Relationship To Existing Concepts

### 11.1 Answer Styles

Answer styles are per-response presentation controls.

Examples:

- concise
- intuitive
- rigorous
- step-by-step

They should not decide what gets persisted.

### 11.2 Strategy Agents

Strategy agents control local organization strategy for the current session or answer.

Examples:

- top-down
- raw

They should not replace long-term user profile.

### 11.3 USER.md

`USER.md` is long-term and cross-session.

It controls defaults for:

- Background assumptions.
- Explanation level.
- Orchestration.
- Persistence policy.
- Profile evolution.

## 12. UX Implications

The bottom links under assistant messages should distinguish different meanings:

- Reused source: a ready knowledge node used to answer.
- Suggested draft: a candidate node that may be generated.
- Pending write: a knowledge node being compiled.
- Failed write: knowledge persistence failed, while the chat answer remains usable.

These should not all look like generic "links". Otherwise users cannot tell whether the answer is citing existing knowledge or merely saving something after the fact.

## 13. First Implementation Slice

The first implementation should stay small:

1. Add a single global `data/config/USER.md`.
2. Load it into the planner prompt.
3. Load it into the answer prompt compiler.
4. Add planner output paths beyond `reuse_answer` and `expand_with_drafts`.
5. Stop auto-persisting broad first-pass overview answers.
6. Make knowledge links show whether they are sources, suggestions, pending writes, or failed writes.
7. Add a profile update proposal mechanism, but do not fully automate rewrites yet.

This is enough to correct the current product mismatch without building a complex memory system.

## 14. Open Decisions

1. Should the first version use only global `data/config/USER.md`, or also allow project-specific overrides later?
2. Should automatic profile updates start in `observe`, `suggest`, or `auto` mode?
3. Should broad overview answers show suggested drafts inline, in a side panel, or under the answer card?
4. Should `/compact` be the main moment when candidate observations get promoted into `USER.md`?
5. Should the user be able to inspect the profile change history?

## 15. Recommended Defaults

Use these defaults until the product proves otherwise:

- Store the first profile at `data/config/USER.md`.
- Start with `suggest` mode for profile updates.
- Treat broad first-pass conceptual questions as `answer_then_suggest_drafts`, not automatic persistence.
- Treat definitions, proof skeletons, canonical examples, notation decisions, and bridge explanations as persistence candidates.
- Make `/compact` responsible for promoting repeated observations into durable profile changes.
- Never write provider fallback or process text into user-visible knowledge nodes.
