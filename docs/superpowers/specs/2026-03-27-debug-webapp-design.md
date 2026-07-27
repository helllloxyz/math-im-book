# Debug Webapp Skill 设计文档

## 1. 目标

本文档定义一个可跨项目复用的 `debug-webapp` skill，用于把 `Codex CLI + Playwright CLI + Skills` 组织成一个稳定的网页服务自我调试闭环。

目标能力是：

1. 面向“当前工作目录中的开发中服务”工作，而不是固定某个项目模板
2. 第一版支持 `单仓库单服务`
3. 自动发现启动入口，优先使用仓库中的 `start.sh`、`dev.sh` 等脚本
4. 启动本地服务并等待 `localhost` ready
5. 调用官方 Playwright skill 进行真实浏览器复现与证据采集
6. 支持 Codex 基于证据修复代码并回归验证

本文档不包含具体实现代码，只定义设计边界、组件职责和工作流。

## 2. 非目标

第一版明确不做以下内容：

1. 不支持 `同仓库前端 + 后端双服务` 编排
2. 不做常驻 orchestrator 或后台守护进程
3. 不强制每个仓库编写专用 skill
4. 不把 Playwright 包装成测试框架层的完整替代品
5. 不在第一版中解决数据库迁移、登录态编排、复杂 seed 管理等高级环境问题

## 3. 总体方案

系统拆成两层：

1. `Playwright skill`
   作为浏览器执行层，负责打开页面、交互、截图、抓取 console、network 与 trace。
2. `debug-webapp skill`
   作为调试闭环层，负责服务发现、服务启动、ready 检查、日志采集、失败回退、修复后回归验证。

设计原则：

1. 浏览器执行和服务编排分离
2. 默认零配置，但允许特殊仓库通过可选覆盖文件微调
3. 先自动发现，再给出选择理由，失败后自动回退到下一个候选
4. 不允许跳过证据采集直接宣称“修好了”

## 4. 适用范围

第一版只支持以下场景：

1. 当前目录就是要调试的仓库
2. 仓库中存在一个主要 web 服务入口
3. 服务启动后可通过本地 `localhost` 访问
4. 可通过页面访问、首页响应或健康检查判断 ready

典型适用对象：

1. 单体 FastAPI 服务
2. 由单个脚本启动的本地 web 应用
3. 开发中需要通过浏览器观察页面或接口行为的本地服务

## 5. 闭环状态机

`debug-webapp` 固定采用以下状态机：

1. `discover`
2. `start`
3. `wait`
4. `inspect`
5. `reproduce`
6. `collect`
7. `diagnose`
8. `fix`
9. `verify`
10. `stop`

状态约束如下：

1. 未发现可用服务入口时，不进入浏览器调试
2. 服务未 ready 时，不进入 Playwright 交互
3. 复现失败或页面异常时，必须收集服务日志和浏览器证据
4. 代码修复后，必须重跑原始复现路径
5. 本轮启动的服务结束后，需要清理本轮创建的进程

## 6. 自动发现与选择

### 6.1 发现目标

发现器输出候选启动命令，而不是直接执行自由推断。

每个候选都必须是结构化记录，至少包含：

1. `command`
2. `workdir`
3. `reason`
4. `score`
5. `expected_port`
6. `expected_url`
7. `healthcheck_hint`

### 6.2 发现优先级

发现顺序固定如下：

1. 显式脚本：
   `start.sh`、`dev.sh`、`run.sh`、`scripts/start.sh`、`scripts/dev.sh`
2. `Makefile` 目标：
   `make dev`、`make start`、`make run`
3. Node 入口：
   `package.json` 中的 `dev`、`start`
4. Python Web 入口：
   `uvicorn`、`fastapi run`、`flask run`、`manage.py runserver` 等明显的 web 启动模式
5. 可选覆盖文件：
   `.codex/devserver.json`

### 6.3 选择策略

选择策略采用“折中模式”：

1. 先静态发现候选
2. 对候选打分并排序
3. 自动选择得分最高的候选
4. 记录选择理由
5. 若启动失败或 ready 检查失败，则清理并回退到下一个候选
6. 若全部候选失败，则终止自动调试并输出失败报告

打分因素优先考虑：

1. 强约定脚本名命中
2. README 或脚本内容中的开发入口证据
3. 命令是否明显启动 web 服务
4. 是否能推断端口或 URL
5. 候选是否位于仓库根目录或标准脚本目录

## 7. 启动与观察性

### 7.1 启动

选中候选后，启动流程需要：

1. 在指定 `workdir` 执行命令
2. 将 `stdout` 和 `stderr` 落盘
3. 记录 PID
4. 将本轮运行目录作为唯一证据目录

建议证据目录格式：

`artifacts/debug-runs/<timestamp>/`

### 7.2 Ready 检查

ready 检查顺序如下：

1. 优先检查推断出的健康检查 URL
2. 若无显式健康检查，检查推断出的首页 URL
3. 若仍无明确 URL，则退化为端口探测

ready 检查失败时：

1. 记录错误
2. 停止当前候选
3. 自动尝试下一候选

### 7.3 轻量检查

服务 ready 后，进入 Playwright 前先执行轻量检查：

1. 获取首页响应状态
2. 检查标题或基础 HTML 是否可读取
3. 确认关键静态资源未立即 404

这样可以在进入复杂页面交互前尽快暴露明显启动错误。

## 8. 浏览器复现与证据采集

官方 Playwright skill 负责：

1. 打开页面
2. 获取快照
3. 执行点击、输入、跳转等交互
4. 截图
5. 记录 console
6. 记录 network
7. 录制 trace

`debug-webapp` skill 负责定义何时必须采集这些证据。

每轮至少应保留：

1. `service.log`
2. `playwright-console.log`
3. `playwright-network.json`
4. `trace.zip`
5. `screenshots/`
6. `summary.json`

规则如下：

1. 页面异常时，不能只看浏览器 console，必须联合服务日志分析
2. 页面成功加载但功能失败时，必须优先检查 network 失败请求
3. 如果需要多轮修复，证据应按轮次分目录保存

## 9. 修复与回归验证

`debug-webapp` 不只负责复现，也必须约束修复后的回归验证。

修复协议：

1. `diagnose`
   明确问题类型，例如启动失败、页面渲染失败、接口请求失败或交互逻辑失败
2. `fix`
   直接修改当前仓库代码
3. `re-run`
   若服务仍存活且可用，则复用；否则重新启动
4. `verify`
   重跑原始复现路径与关键交互

判定结果只能是以下四种之一：

1. `fixed`
2. `not fixed`
3. `blocked by environment`
4. `could not reproduce`

通过条件：

1. 原始问题不再出现
2. 不引入新的 console error、资源加载错误或 5xx 接口错误
3. 页面关键交互结果与预期一致

## 10. 通用 Skill 形态

为支持多个项目复用，该方案应做成全局 skill，而非仓库私有 skill。

建议结构：

```text
$CODEX_HOME/skills/debug-webapp/
  SKILL.md
  references/
    workflow.md
    heuristics.md
    artifacts.md
  scripts/
    discover_service.sh
    start_service.sh
    wait_ready.sh
    stop_service.sh
    summarize_run.sh
```

职责定义：

1. `SKILL.md`
   定义流程、约束、回退策略和完成判定标准
2. `discover_service.sh`
   输出结构化候选服务记录
3. `start_service.sh`
   启动服务并记录 PID、日志和运行目录
4. `wait_ready.sh`
   执行 URL 与端口级 ready 检查
5. `stop_service.sh`
   清理本轮启动的服务
6. `summarize_run.sh`
   汇总本轮证据，输出机器可读结论

## 11. 可选仓库覆盖

默认情况下，所有仓库都走自动发现。

仅在特殊仓库中允许使用可选覆盖文件：

`.codex/devserver.json`

覆盖文件只做微调，不取代通用流程。适用内容包括：

1. 指定默认端口
2. 指定健康检查 URL
3. 指定应忽略的候选脚本
4. 指定首页 URL

第一版不要求每个仓库都维护这个文件。

## 12. 风险与边界

主要风险：

1. 某些仓库存在过时脚本，可能导致自动发现命中错误候选
2. 某些服务启动成功但首页不可用，ready 推断可能不足
3. 单服务假设不适用于前后端联调仓库
4. 自动化浏览器复现依赖页面结构稳定性

缓解策略：

1. 保留候选排序与选择理由
2. 启动失败后自动回退
3. 所有失败都保留证据包
4. 将双服务支持留到后续版本

## 13. 后续实现边界

后续实现阶段应优先完成：

1. 自动发现脚本
2. 启动与停止脚本
3. ready 检查脚本
4. 证据目录协议
5. `SKILL.md` 的标准工作流

待后续扩展的内容：

1. 同仓库双服务支持
2. 登录态与 seed 管理
3. 更强的健康检查推断
4. 更细粒度的浏览器复现模板
