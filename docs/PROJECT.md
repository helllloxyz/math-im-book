# Math IM Book - Project Design (Consolidated)

本文档是对现有 `spec/` 与 `docs/` 中分散设计记录的收束版本，用来回答两个问题：

1. 这个项目到底要做成什么样的产品
2. 这个产品由哪些核心模块组成，以及它们如何协作

注意：本文档刻意不追溯历史讨论过程，也不依赖你保留那些过程型文档。

## 1. 一句话目标

做一个“对话驱动的数学知识演化工作台”：用户在对话中探索，系统把可复用的数学知识逐步沉淀成接近书稿结构的 Markdown 知识库，并且在长期使用中保持上下文可控、符号一致、引用可追溯。

## 2. MVP 要验证的核心判断

第一阶段不追求“自动写书”，只验证这件事是否成立：

用户可以通过对话逐步构建数学知识库；系统能复用已有知识；在知识缺失时能受控地产生新增内容；并通过分支、引用、符号表与 compact 机制维持长期可用性。

## 3. 设计原则与约束

1. 对话是主入口（conversation-led）
   - 默认动作是“问与答”，不是“编辑与管理”。

2. 受控生长，而不是无边界生成
   - 知识不足时先表达“缺口”和“待沉淀条目”，再扩展。

3. 分支优先（branch-first）
   - 深挖应通过 fork 切出新分支，避免把所有探索污染到同一条上下文里。

4. 数学一致性优先
   - 符号、定义、命名需要跨轮次稳定，允许提示冲突与对齐。

5. 上下文可控
   - 不把所有历史全量塞回模型；能区分 active vs summary 的知识集合。

6. 读者体验优先的“积累面”
   - 知识的呈现应像“正在形成的书稿/笔记”，而不是 JSON 检查器。

## 4. 核心对象模型（最小闭环）

### 4.1 Chat Session（会话/分支）

承载用户问题、回答历史、分支关系、以及本分支的工作上下文。

关键性质（偏产品约束）：
- 已提交的历史是追加式（append-only）
- 只允许编辑最后一轮用户输入 / 只允许重生成最后一条回答
- fork 不复制父会话历史，通过“锚点”继承可见历史

### 4.2 Knowledge Node（知识节点）

长期可复用的数学知识单元，最终会组成“像书一样”的层次结构。

最低要求：
- 有标题（topic）
- 有 summary（便于激活与浏览）
- 有 detail（可阅读的正文 Markdown）
- 能被引用、能被追溯来源

### 4.3 Symbol Registry（符号表）

维护当前工作语境下重要符号约定，至少满足：
- 能记录关键符号及其含义
- 回答时优先复用既有约定
- 发现明显冲突时提示或对齐

### 4.4 Pending Draft（待沉淀条目）

表达“本轮需要补的知识，但尚未沉淀为正式知识节点”的中间态。

它的价值是“边界”：
- 告诉用户系统准备补什么
- 防止模型一次性扩写太多，导致结构失控

### 4.5 Reference（引用）

回答与知识节点之间的可追溯关联。

用于支持：
- 回答里直接点出复用来源（inline references）
- Reader/右侧面板进行依赖导航（Dependencies / Referenced By）

### 4.6 Fork Anchor（分支锚点）

fork 时的不可变锚点，用来定义子分支“继承父历史的截止位置”。

锚点可以是：
- 某条已提交的 message
- 某个 knowledge node（并记录其来源 message，保证父历史切割稳定）

### 4.7 Orchestration Plan（编排计划）

每一轮回答前产生的结构化意图与路由判定。
- 记录意图（intent）、置信度（confidence）、持久化决策（persistence decision）与路由（route）。
- 提供用户可见的摘要（user-visible summary），用于透明化 Agent 思考过程。

### 4.8 Agent State（代理状态）

管理与展示 Agent 的后台任务、规划、画像进化与环境健康度。
- Knowledge Queue：待生成或生成中的知识节点队列。
- Memory Scope：当前识别的领域范围与参与决策的画像层级。
- Context Health：当前分支的上下文健康状况（节点数、符号冲突等）。

### 4.9 USER.md（用户画像）

长期的用户学习偏好与背景知识库，引导 Agent 的解释深度与持久化策略。
- 自进化机制：通过 Observation -> Patch Proposal -> Applied 链路受控更新。

## 5. 主流程（闭环）

### 5.1 Ask（用户提问）

输入：一个问题 + 当前分支（可带会话级配置）

系统要完成的最小动作：
1. 识别用户意图与问题范围（宽泛学习 vs 精确定义/证明/例子）
2. 选择本轮激活的知识集合（active nodes）与只用摘要的集合（summary nodes）
3. 注入符号约束（Symbol Registry）
4. 判定走哪条路：复用已有知识 or 受控扩展

### 5.2 Reuse（可复用时）

目标：直接回答，并明确引用了哪些知识节点。

输出组织建议：
- summary -> detail -> hyperlink/references

### 5.3 Extend（知识不足时）

目标：新增内容必须“有边界、有归属”。

建议行为：
1. 先生成 Pending Draft 清单（准备补哪些节点/段落）
2. 按需生成并沉淀为 Knowledge Node（落盘）
3. 再用这些新节点回答当前问题，并带引用

### 5.4 Fork（继续深挖）

当用户从某个回答片段或引用继续问：
- 创建新分支会话
- 继承父分支“可见历史”到锚点（不复制文件/消息实体）
- 子分支只携带与新目标相关的 active context

### 5.5 Compact（整理收束）

`/compact` 的产品目标是抑制长期探索带来的膨胀与漂移。

MVP 级别至少需要做到：
- 压缩非活跃分支的上下文
- 合并明显重复的小片段
- 对近期新增内容做基础符号对齐
- 生成更适合长期保留的 summary 视图

## 6. 配置与 Prompt 分层（长期可维护性）

Prompt 不应该只靠“一个 style 文件”承载所有行为，推荐分层（从稳定到易变）：

1. Base Contract（稳定、短）
   - 正确性、语言、引用使用、避免无根据断言等全局规则

2. Teaching Strategy（会话级策略）
   - 例如 overview-first / top-down / guided-discovery 等
   - 解决“如何组织讲解与推进”的问题

3. Answer Style（每轮可选的轻量覆盖）
   - 例如 concise / rigorous / intuitive / step-by-step
   - 解决“这次回答更短还是更严谨”的问题

4. Optional Affordances（可选回复特性）
   - 例如是否给 follow-up questions、是否给一个例子等

核心思想：把“组织方式”和“篇幅/口味”拆开，避免 style 文件被迫同时承担结构、交互与长度控制。

## 7. Web Workspace（信息架构）

总体形态：三栏，但交互优先级明确，避免变成管理控制台。

1. 左栏：Context Locator
   - 上：Chat Chain / Fork Tree（主导航）
   - 下：Book Outline（目的地导航）

2. 中栏：Conversation Workspace（主生产面）
   - 历史对话 + 回答卡片 + 输入框
   - 回答动作尽量少：Fork / Copy / Regenerate
   - 引用应尽量内联可点击（不依赖额外“查看引用”按钮）
   - 每一轮回答下方附带轻量级的 Orchestration Plan Strip，支持进入 Agent State 深度查看。

3. Agent State Workspace（透明化管控面）
   - 独立页面，展示当前规划、知识队列、画像进化建议与上下文健康度。
   - 用户审批 Pending Drafts 与 Profile Patches 的核心场所。

4. 右栏：Accumulation Reader（读者优先）
   - 主体是 Markdown 阅读
   - 下方是“读后导航”，建议三组：Dependencies / Referenced By / Related Discussions

一个关键约束：点击章节/引用主要改变“右侧阅读上下文”，不应强制切换中栏会话上下文（保持松耦合）。

## 8. 迭代路线（概念层）

1. Phase 1：跑通闭环
   - 对话驱动、复用、受控扩展、沉淀、fork、符号表、基础 compact、三域界面

2. Phase 2：增强语义调度与整理
   - 更稳的激活集规划、更强意图识别、更聪明 draft、更自然 fork 建议、更强 compact、更强符号协调、基础桥接节点

3. Phase 3：走向书稿化
   - 更成熟的章节结构、主线重排、跨主题桥接、导出呈现、成熟 Branch View、细致知识状态管理

## 9. 明确的非目标（第一阶段）

- 不做完整 DAG/图谱可视化平台
- 不做复杂版本管理/diff/合并系统
- 不做高度自治的多代理自演化
- 不做形式化证明验证平台
- 不做后台预测式大规模预生成
- 不做过强自动重构（避免不可控）

## 10. 代码实况校验（截至 2026-04-11）

这一节把“文档里的设计”落到当前仓库已经实现的具体形态，并点出偏差与缺口，方便后续继续收敛。

### 10.1 已实现的核心闭环部件

0. 模块入口映射（最小）
   - Backend HTTP：`src/math_im_book/api/app.py`，schema：`src/math_im_book/api/schemas.py`
   - Backend orchestration：`src/math_im_book/services/orchestrator.py`
   - Planner（LLM JSON planner + fallback）：`src/math_im_book/services/planner.py`
   - Context selection（active/summary）：`src/math_im_book/services/context_selector.py`
   - Symbols：`src/math_im_book/services/symbols.py`
   - Prompt compile：`src/math_im_book/services/prompt_compiler.py`
   - Knowledge jobs：`src/math_im_book/services/knowledge_jobs.py`
   - Providers：`src/math_im_book/services/providers.py`
   - Storage (sessions)：`src/math_im_book/storage/sessions.py`
   - Storage (knowledge markdown)：`src/math_im_book/storage/markdown.py`
   - Storage (configs)：`src/math_im_book/storage/answer_styles.py` / `strategy_agents.py` / `provider_options.py`
   - Frontend store：`frontend/src/stores/workspace.ts`
   - Frontend API client：`frontend/src/services/api.ts`
   - Frontend panels：`frontend/src/components/explorer/*` / `chat/*` / `reader/*`

1. Session 目录式存储 + 可见历史继承
   - 形态：`data/chats/sessions/<session_id>/session.json` + `messages.jsonl`（可选 `working_turn.json`）+ `data/chats/sessions_index.json`。
   - 可见历史：子分支会递归继承父分支已提交消息，并在 fork anchor 处截断，然后再拼接本地消息。

2. Fork（message/node 锚点）
   - `message` 锚点：必须指向已提交的 assistant message，且该 message 必须带 `assistant_context.referenced_node_ids`（否则无法推导 active nodes）。
   - `node` 锚点：以 node 为 active，并用其直接引用 + incoming 引用作为 summary neighborhood；同时记录 `source_message_id` 作为父历史截断点。

3. Compact（当前实现是启发式、非 LLM）
   - `/compact` 目前会追加一条 assistant message（`action_type="compact"`），并在 `assistant_context.compact_summary` 中写入 focus/active/summary/symbol snapshot 等摘要信息。
   - summary nodes 会并入近期引用到的 node ids，并对 summary nodes 做一个非常轻的“同父节点 + summary 词项重叠”合并建议（只写入 summary，不重写知识节点内容）。

4. 受控扩展：Pending Draft + Knowledge Job
   - 当 planner 选择 `expand_with_drafts`，系统会创建一个知识编译 job，并先返回“queued/running”的回答，等待前端轮询 job。
   - job 完成后会写入一个新的 knowledge node，并把 answer anchors 从 `pending` 更新为 `ready`。

5. Prompt 分层（已落地）
   - Base contract（固定前缀）+ Strategy agent（会话/每次请求可选）+ Context block + Question block + 可选 answer style override（非 default 时追加）。

6. 知识节点的文件形态（Markdown + YAML front-matter）
   - 位置：`data/knowledge/<node_id>.md`
   - front-matter 中包含：`id/title/type/summary/parent_id/source/symbols/symbol_scopes/references/status`，正文是 `detail`。
   - incoming references 通过扫描全量节点的 `references[]` 得到（缓存加速）。

7. Web Workspace 与 Reader 引用导航（数据侧支持）
   - Node API 直接返回 display-ready 的 `references_display` / `incoming_references_display` / `related_discussions`，用于右侧 Reader 的“读后导航”。

8. API surface（用于产品验收对齐）
   - Ask：`POST /api/ask`，以及 `POST /api/ask/stream`
   - Jobs：`GET /api/knowledge-jobs/{job_id}`
   - Sessions：`GET/PATCH/DELETE /api/sessions/{id}`，`POST /api/sessions/{id}/fork`，`POST /api/sessions/{id}/compact`，`GET /api/sessions`
   - Knowledge：`GET /api/outline`，`GET /api/nodes/{node_id}`
   - Prompt config：`GET /api/answer-styles`，`GET /api/strategy-agents`
   - Providers：`GET /api/provider-options`，`PUT /api/provider-options/default-options`，以及 credentials 的 `GET/POST/PUT`

### 10.2 当前实现与本文设计的关键偏差/缺口

1. Knowledge Node 的 `source`
   - 设计上它应指向产生它的 session 或可追溯来源；当前自动编译节点使用 `"chat:auto"`，需要后续补齐可追溯链路（至少写入触发的 session_id）。

2. Knowledge Job 目前是 in-memory
   - job 状态不落盘；服务重启会丢。若后续要做稳定闭环，需要把 job 记录持久化或改成同步生成。

3. “受控扩展 -> 沉淀 -> 立刻复用回答”的体验仍偏弱
   - 当前扩展分支先返回 “compilation queued” 的占位内容，等 job 完成后才有真正可复用节点。若要更符合产品直觉，可能需要把“本轮回答”和“沉淀动作”更紧密地合并成一次体验（例如 job 完成后自动更新/补一条回答）。

4. Compact 目前不做知识内容重写
   - 设计里 compact 被视为“整理收束”的关键机制；当前实现只做摘要与轻量合并建议，不会真正生成更稳定的汇总节点或对齐符号到知识正文层。
