
我把你的补充理解为：USER.md 是长期用户画像，不是某本书的局部配置；它要影响 agent 编排、解释深度、默认落盘边界，而不是
  只改语气。

• Updated Plan
  └ ✔ Explore project context in spec/docs
    ✔ Ask clarifying question
    □ Propose approaches and recommendation
    □ Present design for approval

• 我觉得整体目标可以重新收束成一句话：

  这个系统不是“聊天记录自动变知识库”，而是一个长期陪用户学习/写作的数学 agent；它要根据用户习惯和知识背景，决定每一轮是
  解释、追问、引用、整理，还是沉淀成可复用知识节点。

  这里 USER.md 的角色很关键，但它不是“内容库”，而是 agent 编排协议的长期用户层。

  一、整体分层

  我建议把系统分成四层心智：

  1. USER.md：长期用户画像
     记录用户怎么学、背景到什么程度、偏好什么解释方式、哪些内容对他来说不用展开、什么东西值得沉淀。
  2. Project / Book Context：当前书或主题的目标
     比如当前是在学线性代数、写微分几何笔记、整理物理数学基础。它决定当前知识树的边界。
  3. Knowledge Base：稳定数学事实
     定义、命题、证明、例子、桥接说明、章节概览。它是长期可复用内容，不应混入“这次我是怎么回答你的”这种过程文本。
  4. Chat Session：交互与探索过程
     回答、追问、分支、临时解释、用户反馈。它是知识生长的入口，但不是所有内容都应该落盘。

  这样可以避免现在的问题：assistant 先答完，然后后台把“回答的副产品”硬塞进知识库。

  二、USER.md 应该记录什么

  我建议 USER.md 分成这几块：

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
  - Persist definitions, theorem statements, proof skeletons, canonical examples, notation decisions, and bridge
  explanations.
  - Do not persist broad introductory answers until enough subnodes exist.
  - Do not persist speculative or uncertain explanations without user confirmation.

  ## Agent Orchestration
  - For broad exploratory questions, answer first and optionally suggest knowledge nodes.
  - For key definitions or notation-sensitive topics, create or verify knowledge nodes before answering.
  - For missing prerequisites, identify the gap and offer a small draft list.
  - If the system is unsure whether to persist, ask or mark as pending draft rather than silently saving.

  ## Language And Tone
  - Default language: Chinese.
  - Keep explanations concise but not terse.
  - Prefer mathematical clarity over motivational prose.

  重点是 USER.md 要影响 planner，不是只影响 final answer。

  三、agent 编排应该怎么变

  现在的流程大概是：

  问问题 -> planner 判断 expand -> 先回答 -> 后台编译知识点

  更合理的流程应该是：

  问问题
  -> 读取 USER.md
  -> 读取当前 book/project context
  -> 检索已有 knowledge summaries
  -> 判断问题类型
  -> 判断用户背景下是否需要展开
  -> 判断是否值得落盘
  -> 选择编排路径

  编排路径可以先收敛成五种：

  reuse_answer
  已有知识足够，直接引用知识节点回答。

  answer_only
  问题适合即时解释，但不值得落盘。

  answer_then_suggest_drafts
  宽泛或探索性问题，先回答，再建议可整理的知识点。

  draft_first_then_answer
  关键定义、证明、符号约定、桥接知识，先生成/确认知识节点，再基于节点回答。

  ask_before_persist
  系统判断不确定，先问用户是否要沉淀。

  这个比现在只有 reuse_answer / expand_with_drafts 更贴近真实使用。

  四、什么该落盘，什么不该落盘

  我建议用“稳定性 + 复用性 + 边界清晰度”三条判断。

  应该落盘：

  - 定义：向量空间、基、线性映射、拓扑空间。
  - 命题/定理：秩-零化度定理、谱定理。
  - 证明骨架：某个定理的关键证明路线。
  - canonical example：标准例子、反例、计算模板。
  - 符号约定：本文用 (V) 表示向量空间，(T) 表示线性算子。
  - 桥接解释：为什么矩阵就是线性映射在基下的表示。
  - 章节/主题概览：但最好在已有若干子节点后生成，而不是第一次问就生成。

  不应该自动落盘：

  - 一次性的寒暄或普通答疑。
  - “我建议你可以这样学”这种临时学习建议。
  - 宽泛问题的第一版概览，除非用户明确要保存。
  - 没有清晰标题和边界的长回答。
  - 依赖当前聊天语境、脱离上下文就读不懂的内容。
  - provider fallback 生成的过程文案，比如“compiled from question”。

  灰区内容：

  - 类比、直觉解释、学习路线、总结。
  - 这些可以先进 Pending Draft，由用户确认或等 /compact 时整理。
  - 也可以挂到已有节点的 notes 或 intuition section，而不是新建正式节点。

  五、用户背景如何影响回答

  同一个问题“什么是线性代数”，不同用户应该走不同路径。

  初学者：

  answer_only 或 answer_then_suggest_drafts
  先讲空间、向量、线性变换的直觉，再建议生成几个基础节点。

  数学背景强：

  answer_only
  简短说明：研究有限维/一般向量空间及线性映射的结构，核心对象是线性算子、子空间、商空间、对偶、谱结构。
  不需要展开矩阵加法这种基础。

  正在写书的人：

  answer_then_suggest_drafts 或 draft_first_then_answer
  先给章节级组织建议，再列出可落盘节点：向量空间、线性映射、基与坐标、矩阵表示。

  所以 USER.md 不是装饰，它会直接改变路线。

  六、推荐的产品原则

  我建议把核心原则写成：

  回答属于 Chat，事实属于 Knowledge，偏好属于 USER.md。

  再加一句：

  落盘不是保存回答，而是提炼可复用知识。
