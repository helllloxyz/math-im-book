# Strategy Agent Prompt Design

## 1. Context

The current answer prompting system uses a single `answer_style` axis. That axis is doing too much work. It currently mixes:

- overall teaching organization
- verbosity preference
- interaction behavior
- per-question formatting hints

This is a poor fit for the product direction now confirmed.

The confirmed direction is:

1. Each chat session should have one fixed high-level guidance strategy.
2. That strategy should behave like an internal built-in agent specification.
3. The strategy should be chosen when a session is created.
4. The strategy should remain stable across the session.
5. Per-question answer styles should remain available, but only as small temporary overrides.
6. Prompt assembly should preserve a stable prefix as much as possible for cache-friendly multi-turn conversations.

## 2. Design Goal

The new prompt architecture should satisfy five properties:

1. Separate session-level teaching strategy from per-question style preference.
2. Keep the main prompt prefix stable across turns in the same session.
3. Allow lightweight per-question overrides without rewriting the session strategy.
4. Keep the external product model simple.
5. Prepare the backend for future prompt composition without forcing a large first-step UI redesign.

## 3. Chosen Model

The system should use three prompt layers:

1. `base contract`
2. `strategy agent`
3. optional per-question `answer style`

### 3.1 Base contract

The base contract is always present. It should be short, durable, and written in English.

It should define rules such as:

- answer the user's question directly
- remain mathematically correct
- use the provided context faithfully
- preserve active symbol meanings
- avoid unsupported claims
- respond in the user's language unless the user explicitly asks for another language

This layer should stay stable across all sessions and all turns.

### 3.2 Strategy agent

The strategy agent is a session-level built-in prompt specification.

It is not a separate runtime agent. It does not execute tools or perform an extra LLM pass. It is a structured instruction source that defines the conversation's overall teaching and interaction protocol.

The strategy agent should be:

- selected at session creation time
- stored in session metadata
- compiled into the stable prompt prefix
- written in English
- detailed enough to describe the expected interaction flow

The first version should support exactly two strategy agents:

1. `top-down`
2. `raw`

Rules:

- `top-down` is the default preselected option for new sessions
- `raw` provides minimal guidance beyond the base contract

### 3.3 Answer style

`answer_style` remains available, but only as a small per-question override.

It should:

- default to `None`
- only appear when the user explicitly selects it for the current question
- not redefine the session strategy
- remain lightweight and local in effect

Examples:

- `concise`
- `intuitive`
- `rigorous`

The style instruction should be appended near the question as a short override, not stored as part of the stable prefix.

## 4. Strategy Agent Behavior

### 4.1 `top-down`

`top-down` is the default teaching-oriented strategy.

Its instruction should define response behavior for broad categories of questions, for example:

- broad learning questions: begin with a short overview, identify main concepts, explain relationships before expanding details
- concept questions: start from the main idea before formal details
- procedural or computational questions: provide derivation steps when they materially help answer the question
- examples: include one when it makes the explanation clearer
- follow-up questions: prefer them for broad or exploratory prompts
- expansion control: avoid exhaustively expanding every branch unless the user asks

This strategy should act as the default session guidance for exploratory learning.

### 4.2 `raw`

`raw` is the minimal strategy.

It should:

- rely mostly on the base contract
- avoid strong teaching-flow constraints
- avoid enforcing a top-down structure
- stay closer to ordinary model behavior

It is intended for users who want fewer built-in response-shaping rules.

## 5. Prompt Compilation

Prompt assembly should move out of the current single-axis style logic and into a dedicated compiler.

The compiler should combine:

1. base contract
2. selected strategy agent instruction
3. fixed separators
4. conversation context
5. new question
6. optional per-question style override

Recommended compiled structure:

```text
[Base Contract]

[Strategy Agent]

[Conversation Context]
...

[New Question]
...

[Per-Question Style Override]
...
```

The implementation should preserve a stable prefix as much as possible.

That means:

- the base contract should be fixed
- the strategy agent instruction should be fixed for the session
- separators should be fixed strings
- per-question answer style should be short and appended late
- prompt compilation should avoid rephrasing or regenerating the stable instruction blocks per turn

## 6. Runtime Boundary

The strategy agent should be modeled as a built-in agent specification, not as an executable agent runtime.

Rejected interpretation:

- do not introduce a second hidden LLM call
- do not create a tool-using internal sub-agent
- do not execute strategy logic outside normal prompt assembly

Chosen interpretation:

- the system loads a strategy agent definition from config
- the compiler turns that definition into stable prompt text
- the orchestrator passes the compiled prompt to the provider in the normal answer flow

This keeps the architecture simple while preserving the intended product meaning of a built-in agent.

## 7. Data Model Changes

### 7.1 Session model

Session metadata should include:

- `strategy_agent_id: str`
- `default_answer_style_id: str | None`

Rules:

- `strategy_agent_id` is required
- new sessions default to `top-down`
- `default_answer_style_id` defaults to `None`

### 7.2 New domain object

Add a `StrategyAgent` model with:

- `agent_id`
- `label`
- `description`
- `instructions`
- `is_default`

`AnswerStyle` remains, but its meaning narrows to a lightweight per-question override fragment.

## 8. Configuration Layout

Add a new strategy-agent config directory:

```text
data/config/strategy_agents/
  index.json
  top-down.md
  raw.md
```

The existing answer-style config can remain in:

```text
data/config/answer_styles/
```

but it should now only hold lightweight style overrides rather than the main teaching strategy.

## 9. Backend Changes

### 9.1 Repository layer

Add a strategy-agent repository that mirrors the existing file-backed style loading pattern:

- load `index.json`
- load one Markdown file per agent id
- provide defaults when config files are missing or invalid

### 9.2 Compiler layer

Add a dedicated `AnswerPromptCompiler`.

Suggested responsibility:

- load the base contract
- load the selected strategy agent
- load the optional answer style
- produce the final prompt parts in a fixed order

The orchestrator should stop owning direct strategy/style string assembly.

### 9.3 Orchestrator layer

The orchestrator should:

1. determine the active session strategy agent
2. accept an optional per-question answer style
3. gather the conversation context
4. call the compiler
5. send the compiled prompt to the provider

## 10. API Changes

Add a new endpoint:

- `GET /api/strategy-agents`

This should return:

- available agents
- labels and descriptions
- which one is default

Existing answer-style APIs may remain, but they now describe per-question style overrides rather than the main answer behavior model.

Session APIs should expose:

- `strategy_agent_id`
- `default_answer_style_id`

Ask APIs should continue to accept:

- optional `answer_style_id`

## 11. Frontend Changes

The first version should keep the UI simple:

1. New session flow:
   - show strategy-agent choices
   - preselect `top-down`
   - allow switching to `raw`
2. Chat composer:
   - keep a lightweight answer-style selector
   - leave it empty by default
   - only send a style override when the user explicitly chooses one

This keeps the external interaction model simple while aligning the backend with the new prompt architecture.

## 12. Rejected Directions

### 12.1 Keep everything as answer styles

This keeps implementation simple in the short term, but it preserves the current semantic overload. It makes future strategy-level behavior hard to reason about and hard to expose cleanly in the product.

### 12.2 Fully dynamic multi-axis UI now

This would expose teaching strategy, verbosity, and interactivity as separate user-facing controls immediately. It is flexible, but too large for the first step and not necessary to validate the architecture.

### 12.3 Hidden internal runtime agent

This would add unnecessary complexity and latency. The problem is prompt structure, not multi-agent execution.

## 13. First Implementation Scope

The first implementation should be intentionally narrow:

1. Add `strategy_agent_id` to sessions.
2. Add file-backed `strategy_agents` config.
3. Add `top-down` and `raw`.
4. Add `AnswerPromptCompiler`.
5. Rewire the orchestrator to compile prompt parts through the compiler.
6. Keep `answer_style` as an optional per-question override.
7. Default new sessions to `top-down`.
8. Default per-question answer style to `None`.

Everything else should wait until this architecture is validated in use.

## 14. Verification Focus

Implementation verification should focus on:

1. new sessions default to `top-down`
2. prompt compilation keeps the stable prefix fixed across turns in the same session
3. per-question style overrides do not mutate stored user message text
4. `raw` omits the top-down teaching protocol
5. base contract always enforces answering in the user's language unless requested otherwise
