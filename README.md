# Math IM Book

Math IM Book 是一个面向个人学习的交互式数学知识工作台。它把数学对话、分支探索、知识卡片和概念关联放在同一个本地 Web 应用中：你可以连续追问、从任意回答创建分支，并把值得保留的定义、直觉、例子和证明沉淀到知识库。

项目采用 FastAPI + Vue 3，数据保存在本地文件中。日常运行时只有一个 Python 进程和一个端口，不依赖 Docker、数据库或 `.env` 文件。

## 主要能力

- 支持 Gemini，以及 DeepSeek、OpenRouter、GLM 等 OpenAI 兼容接口
- 流式数学问答，支持 Markdown、KaTeX 公式和多种阅读主题
- 会话级教学策略与单轮回答风格
- 从回答创建分支、复制回答、重试最后一次回答
- 自动或手动把对话内容沉淀为可复用知识笔记
- 对话与知识库的文件夹、搜索、拖放、重命名和分类图标
- 查看回答采用的策略、上下文范围和知识生成状态
- 全部会话、知识与配置均保存在项目目录下，方便备份和迁移

## 快速开始

需要预先安装：

- Python 3.10、3.11、3.12 或 3.13
- Node.js 20.19+、22.13+ 或 24+（包含 npm）
- Git（使用源码压缩包时可不安装）
- 至少一个受支持模型服务的 API Key

### Linux / macOS

```bash
git clone <repository-url>
cd math-im-book
chmod +x scripts/setup.sh scripts/run.sh
./scripts/setup.sh
./scripts/run.sh
```

### Windows

在 PowerShell 或命令提示符中运行：

```powershell
git clone <repository-url>
cd math-im-book
.\scripts\setup.bat
.\scripts\run.bat
```

浏览器打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。首次使用需要点击左下角设置按钮，添加模型服务的 API Key 并选择默认模型。

安装脚本只需在首次安装、更新代码或依赖发生变化后运行；平时直接运行 `run.sh` 或 `run.bat`。按 `Ctrl+C` 停止应用。

## 文档

- [跨平台安装与部署指南](docs/INSTALLATION.md)：Windows、Linux、局域网访问、更新、备份、手动安装与故障排查
- [完整使用教程](docs/USER_GUIDE.md)：模型配置、对话、分支、划词操作、知识库、文件管理与高级定制
- [开发手册](docs/DEVELOPMENT_PLAYBOOK.md)：项目结构、开发约束和测试策略
- [项目设计](docs/PROJECT.md)：产品目标、对象模型和内部流程

## 启动参数

启动脚本接受两个可选参数：监听地址和端口。

```bash
# 仅本机访问（默认）
./scripts/run.sh

# 指定端口
./scripts/run.sh 127.0.0.1 9000

# 允许局域网设备访问
./scripts/run.sh 0.0.0.0 8000
```

Windows 使用相同参数：

```powershell
.\scripts\run.bat 0.0.0.0 8000
```

应用本身没有用户登录和访问控制，并且 API Key 以明文保存在本机。除非已经由外部软件提供访问保护，否则不要直接暴露到公网。代理、HTTPS 和域名配置不属于本项目启动脚本的职责。

## 数据与隐私

运行数据位于 `data/`：

- `data/credentials/credentials.json`：API Key 和模型服务配置
- `data/chats/`：对话与分支历史
- `data/knowledge/`：生成的 Markdown 知识笔记
- `data/explorer/index.json`：文件夹、位置和分类图标
- `data/config/`：回答风格、教学策略和默认模型等版本化配置

`data/credentials/`、`data/chats/` 和 `data/knowledge/` 已被 Git 忽略。不要把包含个人数据或 API Key 的文件提交到公开仓库。升级或迁移前建议在应用停止后备份整个 `data/` 目录。

## 开源发布提示

公开仓库还应在发布前完成以下一次性事项：

- 选择并加入明确的 `LICENSE`；许可证属于项目所有者的法律选择，本仓库暂不替你预设
- 把 README 中的 `<repository-url>` 替换为实际仓库地址
- 检查 Git 已跟踪文件中是否含有个人对话、测试密钥、域名或机器专用配置
- 当前 `data/explorer/index.json` 含本机文件夹和会话位置；发布前应备份后清空，并决定是否改为不跟踪的运行数据
- 确认根目录的 `Session-chat-245-chat-245.md` 和 `user_sepc_record.md` 是否确实要作为公开示例保留
- 在干净的 Windows 和 Linux 环境各执行一次安装流程

## 开发与测试

```bash
# 后端测试
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest -v -o cache_dir=/tmp/math-im-book-pytest-cache

# 前端测试和构建
cd frontend
npm run test
npm run build
```

Windows 后端测试命令为：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -v
```
