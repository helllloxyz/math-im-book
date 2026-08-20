# Math IM Book 跨平台安装与部署指南

本文面向希望在个人电脑、家庭局域网或普通 Linux 主机上运行 Math IM Book 的用户。项目不使用 Docker；安装过程只涉及 Python、Node.js 和项目源码。

## 1. 运行方式

项目包含两个部分：

1. Vue 前端在安装阶段构建到 `frontend/dist/`。
2. FastAPI 在运行阶段同时提供前端页面和 `/api` 接口。

因此日常使用只需要启动一个 Python 进程，默认地址为 `http://127.0.0.1:8000`。不需要单独启动 Vite，不需要数据库，也不需要维护开发、部署、生产三套重复脚本。

仓库只保留两种操作：

| 操作 | Linux / macOS | Windows | 什么时候运行 |
| --- | --- | --- | --- |
| 安装或更新依赖、构建前端 | `scripts/setup.sh` | `scripts/setup.bat` | 首次安装、拉取新代码或依赖变化后 |
| 启动应用 | `scripts/run.sh` | `scripts/run.bat` | 每次使用时 |

## 2. 系统要求

### 2.1 支持的平台

- Windows 10 / 11
- 常见 64 位 Linux 发行版，例如 Ubuntu、Debian、Fedora、Rocky Linux
- macOS 也可以使用与 Linux 相同的 shell 脚本

### 2.2 必需软件

| 软件 | 支持版本 | 用途 |
| --- | --- | --- |
| Python | 3.10-3.13 | FastAPI 后端和模型 SDK |
| Node.js | 20.19+、22.13+ 或 24+ | 安装和构建 Vue 前端 |
| npm | 随 Node.js 安装 | 按锁文件安装前端依赖 |
| Git | 任意较新版本，可选 | 克隆和更新源码 |

从源码压缩包安装时不需要 Git。Node.js 只在安装和重新构建前端时使用，日常启动不依赖 Node 进程。

安装软件后先检查版本：

```text
python --version
node --version
npm --version
git --version
```

Linux 上的 Python 命令通常是 `python3`；Windows 推荐使用官方安装器提供的 `py` 启动器。安装 Python 时需要包含 `venv` 和 `pip`，安装 Node.js 时需要包含 npm。

## 3. 获取源码

### 3.1 使用 Git

```bash
git clone https://github.com/helllloxyz/math-im-book.git
cd math-im-book
```

### 3.2 使用源码压缩包

在代码托管页面下载源码压缩包，完整解压后进入包含 `pyproject.toml`、`frontend/` 和 `scripts/` 的目录。不要只复制 `src/`，前端、默认配置和数据目录也是运行所需内容。

## 4. Linux / macOS 安装

首次安装执行：

```bash
chmod +x scripts/setup.sh scripts/run.sh
./scripts/setup.sh
```

脚本会依次完成：

1. 检查 Python 和 Node.js 版本。
2. 在项目根目录创建 `.venv/` Python 虚拟环境。
3. 安装后端运行依赖。
4. 使用 `npm ci` 按 `frontend/package-lock.json` 安装前端依赖。
5. 检查 TypeScript 并构建 `frontend/dist/`。
6. 创建缺失的本地数据目录。

看到 `Setup complete.` 即表示安装完成。启动应用：

```bash
./scripts/run.sh
```

浏览器打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。终端中按 `Ctrl+C` 停止。

## 5. Windows 安装

可以使用 PowerShell 或命令提示符。进入项目目录后执行：

```powershell
.\scripts\setup.bat
```

脚本会优先通过 `py -3` 查找兼容的 Python，也会兼容已加入 `PATH` 的 `python`。安装完成后启动：

```powershell
.\scripts\run.bat
```

浏览器打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。运行窗口需要保持打开；按 `Ctrl+C` 并确认即可停止。

`.bat` 脚本不受 PowerShell 脚本执行策略限制。如果双击运行，窗口会在程序停止或出错后关闭，不利于查看错误信息，因此首次安装建议从 PowerShell 或命令提示符启动。

## 6. 验证安装

应用启动后执行健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

Windows 没有可用的 `curl` 时，直接在浏览器打开 [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)。然后回到首页，确认可以看到 Mathbook 工作区。

首次提问前还需要在页面左下角的全局设置中配置 API Key，详见[完整使用教程](USER_GUIDE.md#2-首次配置模型服务)。

## 7. 监听地址和端口

两个启动脚本都接受相同的两个位置参数：

```text
run <监听地址> <端口>
```

### 7.1 默认仅本机访问

```bash
./scripts/run.sh
```

等价于：

```bash
./scripts/run.sh 127.0.0.1 8000
```

Windows：

```powershell
.\scripts\run.bat 127.0.0.1 8000
```

### 7.2 更换端口

```bash
./scripts/run.sh 127.0.0.1 9000
```

如果默认端口已被占用，选择一个未使用的端口即可。

### 7.3 局域网访问

Linux / macOS：

```bash
./scripts/run.sh 0.0.0.0 8000
```

Windows：

```powershell
.\scripts\run.bat 0.0.0.0 8000
```

同一局域网的设备使用运行主机的实际 IP 访问，例如 `http://192.168.1.20:8000`。必要时在操作系统防火墙中允许 TCP 8000 端口。

应用没有用户登录、权限隔离和请求限流，API Key 也保存在运行主机的本地文件中。局域网内存在不受信任设备时仍建议保持 `127.0.0.1`。不要在没有外部访问保护的情况下直接把端口暴露到公网。

代理、域名、HTTPS 和公网入口由外部代理软件负责，本项目不额外提供代理配置。

## 8. Linux 后台运行

个人主机需要关闭终端后继续运行时，可以使用系统已有的进程管理工具。最简单的临时方式是：

```bash
nohup ./scripts/run.sh 127.0.0.1 8000 > math-im-book.log 2>&1 &
echo $!
```

记录输出的进程号。停止时执行：

```bash
kill <进程号>
```

查看日志：

```bash
tail -f math-im-book.log
```

日常启动日志默认保持精简：保留启动地址以及警告、错误，不记录每个正常的页面和 API 请求。知识任务的进度和模型调用错误会显示在应用界面中；需要查看逐请求日志时，使用第 13 节的开发模式。

长期自动启动可交给你已经使用的 systemd、supervisor 或其他进程管理软件；项目本身不再维护另一份 `deploy.sh` 或 `run-production.sh`。

## 9. 更新项目

使用 Git 安装时：

```bash
git pull
./scripts/setup.sh
./scripts/run.sh
```

Windows：

```powershell
git pull
.\scripts\setup.bat
.\scripts\run.bat
```

重新运行安装脚本会复用 `.venv/`、更新依赖并重新构建前端，不会主动清空 `data/`。更新前仍建议先停止应用并备份数据。

使用源码压缩包更新时，不要直接覆盖唯一的数据副本。推荐先备份旧目录的 `data/`，解压新版本、运行安装脚本，再把备份数据迁移到新目录。

## 10. 数据备份与迁移

停止应用后备份整个 `data/` 目录最稳妥，其中包含凭据、对话、知识笔记、文件夹结构和自定义配置。

Linux / macOS 示例：

```bash
tar -czf math-im-book-data-backup.tar.gz data
```

Windows PowerShell 示例：

```powershell
Compress-Archive -Path data -DestinationPath math-im-book-data-backup.zip
```

恢复时先停止应用，把备份的 `data/` 放回项目根目录，再启动应用。备份文件包含明文 API Key，应当按敏感文件保管。

## 11. 为什么没有 `.env`

当前代码不读取 `.env`，也没有必须通过环境变量注入的配置：

- 监听地址和端口通过 `run.sh` / `run.bat` 的参数传入。
- API Key 和各供应商的 Base URL 由页面设置保存到 `data/credentials/credentials.json`。
- 默认模型、Markdown 主题位于 `data/config/provider_options.json`。
- 回答风格和教学策略位于 `data/config/` 下的版本化 JSON、Markdown 文件。

在这个单用户文件型项目中再加入 `.env` 会形成重复的配置来源，因此安装流程不创建 `.env` 或 `.env.example`。如果未来加入数据库密码、登录密钥或云端部署专用参数，再引入环境变量会更合适。

## 12. 手动安装

脚本无法使用时，可以按下面的等价步骤安装。

### 12.1 Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn math_im_book.api.app:create_app --factory --host 127.0.0.1 --port 8000 --log-level warning --no-access-log
```

如果 `python3` 不是 3.10-3.13，请改用实际命令，例如 `python3.12`。

### 12.2 Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn math_im_book.api.app:create_app --factory --host 127.0.0.1 --port 8000 --log-level warning --no-access-log
```

## 13. 开发模式

普通使用不要运行开发模式。需要修改代码时，开启两个终端：

终端一运行自动重载的后端：

```bash
.venv/bin/python -m uvicorn math_im_book.api.app:create_app --factory --reload --host 127.0.0.1 --port 8016
```

终端二运行 Vite：

```bash
cd frontend
npm run dev
```

开发页面使用 Vite 输出的地址；`frontend/vite.config.ts` 会把 `/api` 转发到 8016 端口。提交发布版本前执行后端测试和前端测试、构建。

## 14. 常见问题

### 页面显示 `Frontend not built`

前端产物不存在。重新执行 `setup.sh` 或 `setup.bat`，确认 `npm run build` 成功并生成 `frontend/dist/index.html`。

### 提示找不到 `.venv`

尚未执行安装脚本，或者启动脚本不在完整项目目录内。回到项目根目录执行对应平台的 `setup` 脚本。

### 现有 `.venv` Python 版本不兼容

`.venv` 只是可重新生成的依赖目录。确认路径确实是当前项目的 `.venv` 后将它删除，再重新执行安装脚本。不要删除整个项目目录或 `data/`。

### Node.js 版本过低

升级到 Node.js 20.19+、22.13+ 或 24+，再执行安装脚本。某些旧 Linux 发行版的软件仓库可能提供更早的 Node.js，需要使用该发行版推荐的新版安装方式。

### 端口已被占用

改用其他端口，例如：

```bash
./scripts/run.sh 127.0.0.1 9000
```

### 页面能打开但无法回答

依次检查：

1. 全局设置中是否已经保存供应商和 API Key。
2. 模型 ID 是否确实被对应供应商支持。
3. OpenAI 兼容供应商的 Base URL 是否正确，通常应包含版本路径，例如 `/v1`。
4. 默认会话模型是否来自已经保存的供应商配置。
5. 运行终端是否显示认证失败、限流或上游服务错误。

### Windows 防火墙询问是否允许访问

仅本机使用时无需开放公共网络访问。只有明确需要局域网访问时，才允许所选端口在可信的专用网络中入站。

### Linux 出现 `Permission denied`

为 shell 脚本增加执行权限：

```bash
chmod +x scripts/setup.sh scripts/run.sh
```

### 如何完全清空对话和知识历史

先停止应用并确认不再需要这些数据，然后执行：

```bash
.venv/bin/python scripts/clear_history.py
```

Windows：

```powershell
.\.venv\Scripts\python.exe scripts\clear_history.py
```

该操作会删除对话会话和生成的知识文件，并重置会话索引，但不会删除 API Key 和版本化配置。重要数据应先备份。
