# Math IM Book - Development Playbook

这份文档不记录“做了什么功能”，只沉淀“在这个项目里怎么做事更稳、更快、更可维护”。目标是让后续迭代可以重复使用这些经验，而不是重复踩坑。

## 1. 开发定位与节奏

这个项目的核心不是把“知识管理系统”做大，而是把一个很窄但很难的闭环做稳：

对话探索 -> 受控补缺 -> 知识沉淀 -> 后续可复用 -> 分支隔离上下文 -> compact 抑制膨胀。

因此开发节奏推荐：
1. 先把闭环跑通（Phase 1），再增强智能性（Phase 2），最后考虑书稿化（Phase 3）
2. 每次改动尽量能被一个“用户动作”触发并验证（问一次、fork 一次、点一次引用、compact 一次）

## 2. 目录与边界（工程组织经验）

后端建议坚持四层划分（避免把逻辑揉成一团）：

1. `api/`：HTTP 输入输出与 schema，只做编排，不做业务判断
2. `domain/`：核心对象与不可变约束（数据结构、基本规则）
3. `services/`：编排层（上下文选择、规划、prompt 组装、落盘任务调度）
4. `storage/`：文件持久化与配置读取（JSON/Markdown），不掺杂业务策略

前端建议坚持三块：
1. `components/`：UI 表现
2. `stores/`：状态与流程（例如 workspace）
3. `services/`：API client、markdown/math 渲染等可测的纯服务

边界纪律带来的直接好处：
- 你可以在不改 UI 的情况下换存储格式
- 你可以在不改存储的情况下换 prompt 组织方式
- 你可以用小而稳定的测试覆盖住“契约”，而不是覆盖一堆 UI 细节

## 3. 存储与分支：让“长期可用”变简单

长期产品的默认敌人是“可变历史”和“复制粘贴继承”。

建议坚持这些可执行的存储规则：
1. 已提交历史 append-only（追加式），不回写
2. 把可变尾巴隔离出来（例如 working turn）
3. fork 不复制父历史，通过不可变锚点继承可见历史
4. 锚点只能指向已提交内容，且一旦写入不可变

这几个规则会显著降低：
- 分支之间互相污染
- “编辑/重生成”导致历史不可信
- 大文件反复重写带来的复杂度

在本仓库当前实现里，这套思想已经具体化为：
- `data/chats/sessions/<id>/session.json`（元数据与 branch）
- `messages.jsonl`（已提交历史）
- 可选 `working_turn.json`（可变尾巴）
- `sessions_index.json`（列表索引）

## 4. Prompt 经验：把可变性关进笼子

Prompt 设计最容易踩的坑是：把“所有行为”塞进一个 style，最后谁也说不清模型为什么这样答。

推荐实践：
1. Base Contract 越短越好，越稳定越好
2. 把“讲解组织方式”独立成 Teaching Strategy（会话级）
3. 把“篇幅/口味”独立成 Answer Style（每轮覆盖、轻量）
4. 尽量用文件化配置（index.json + markdown bodies），而不是散落在代码字符串里

一个重要细节：避免让 “default + concise” 叠加后产生矛盾指令。默认应该代表“稳定前缀”，覆盖才是“可选增量”。

本仓库当前实现的落地点（用于 review 时核对）：
- Strategy agents：`data/config/strategy_agents/`（`index.json` + `*.md`）
- Answer styles：`data/config/answer_styles/`（`index.json` + `*.md`，`default` 代表“无额外覆盖”）
- 编译器：把 `base + strategy + context + question + (optional style override)` 串起来

## 5. 上下文管理经验：显式区分 active vs summary

上下文膨胀不是模型问题，是系统设计问题。

实用策略（先做朴素版本也有效）：
1. 每轮明确 active nodes（必须展开的内容）
2. 其余只给 summary nodes（只给摘要，不给正文）
3. 把符号表作为独立约束注入，而不是散落在文本里
4. fork 时强制缩小继承的“语义起点”，而不是继承所有历史

## 6. UI 经验：三栏不是重点，优先级才是

三栏布局很容易做成“每栏都想抢注意力”的管理后台，结果用户不知道该看哪里。

建议坚持：
1. 中栏是主生产面（对话与输入）
2. 右栏是读者优先的积累面（Markdown 阅读 + 轻导航）
3. 左栏只做定位（分支树优先于书籍大纲）
4. “点击章节/引用”默认只改变阅读上下文，不强迫切会话（松耦合）
5. 回答卡片动作保持极少（Fork/Copy/Regenerate 足够覆盖主要需求）

## 7. 引用数据经验：把“可点击”当成一等公民

引用系统最好从一开始就避免“UI 自己拼装数据”：
1. 后端尽量返回 display-ready 的引用对象（title/summary/preview），减少前端 fan-out
2. Reader 的导航应是“读后决定下一步去哪”，不是把右栏变成第二个 explorer

## 8. 测试经验：优先锁住契约，不要被 UI 细节拖死

这类系统最关键的回归点是“契约”和“语义不变性”：
1. API schema/响应形状（尤其是 session、node、引用、配置 catalog）
2. prompt 组装结果（分层是否正确、覆盖是否是增量而非替换）
3. fork/继承历史的可见性规则（锚点切割是否稳定）
4. 存储读写的不可变性（append-only 是否被破坏）
5. 后台 job 的可观测性（queued/running/completed/failed 以及 anchor 状态变化）

UI 测试建议只覆盖：
- 关键交互（发问、切分支、点引用、切阅读节点）
- 关键渲染契约（引用可点击、阅读区分组、展开/收起）

## 9. 常见坑清单（用于 code review 自查）

1. 任何“自动扩写很多内容”的改动，都会让知识结构很快失控
2. 任何“把历史当作可编辑文本”的改动，都会让 fork/引用语义变脆
3. 任何“把 style 当成组织策略”的改动，都会让 prompt 难以维护
4. 任何“前端为了显示去额外拉一堆请求”的改动，都会让状态变复杂、测试变脆
5. 任何“把右栏做成管理控制台”的改动，都会削弱产品的对话主导体验

## 10. 当前实现的“事实表”（用于快速对齐）

当你发现文档与代码不一致时，先用这张事实表定位“到底谁错了”：

1. Ask/Regenerate/Stream/Jobs/Session/Outline/Node 这些能力都是 HTTP API 直接暴露的
2. fork 目前依赖 `assistant_context.referenced_node_ids` 来推导 active nodes（这会影响回答卡片是否必须产出引用）
3. compact 当前是启发式摘要，不会重写知识节点正文
4. 知识编译 job 当前是 in-memory，不落盘

## 11. 推荐的后续文档策略（避免再产生历史堆积）

只保留两类长期文档：
1. `docs/PROJECT.md`：产品目标、对象模型、主流程、约束与路线（面向未来一致性）
2. `docs/DEVELOPMENT_PLAYBOOK.md`：工程经验、边界纪律、测试策略、踩坑清单（面向未来迭代效率）

其他计划型/过程型文档：
- 要么在完成后删掉
- 要么只保留一份“当前阶段的实施计划”，完成即归档/删除
