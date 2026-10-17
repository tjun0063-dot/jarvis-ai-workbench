# Jarvis AI Workbench

一个运行在 Windows 上的本地 AI 工作台。它把 Codex、ChatGPT 账号模式、muse.ai 个人智能体和 DeepSeek 接到统一的项目、会话与任务目录，并可通过专用微信号“贾维斯”从手机提交任务、收取文字和文件结果。

## 目前能力

- 统一选择 Codex、GPT、Muse、DeepSeek，并继续已有项目和会话。
- 微信私聊与群聊 `@贾维斯` 指令，按群聊和发送人隔离任务。
- 最多 4 个任务并行执行，结果始终回到原发起人。
- 发送图片、视频、PPT、PDF、表格、压缩包及其他微信支持的文件。
- `/材料` 模式可连续收集多条说明、图片、视频和文件，使用 `/开始` 合并为一个任务。
- Hyper-V 独立虚拟机运行微信窗口自动化，避免占用主机桌面。
- 窗口监听可暂停和恢复，电脑显示器关闭时仍能继续运行。

## 目录

- `workbench/`：本地主服务、Web 工作台、模型适配器、微信桥及测试。
- `vm/`：Hyper-V 部署脚本与虚拟机来宾端连接器。
- `tools/`：更新光盘的构建与校验工具。
- `config/`：不含凭据的配置示例。

## 本地启动

需要 Windows 11、Node.js 20+、Python 3.12、Codex CLI，以及启用 Hyper-V 的专业版或企业版 Windows。

```powershell
cd workbench
npm install
npm test
npm start
```

工作台默认只监听 `127.0.0.1:8790`。首次运行会在 `workbench/data/` 创建本机状态；该目录已被 Git 忽略。

虚拟机安装和更新流程见 [vm/README.md](vm/README.md)。Muse 个人账号接入见 [workbench/PERSONAL_MUSE.md](workbench/PERSONAL_MUSE.md)。附件边界见 [workbench/ATTACHMENTS.md](workbench/ATTACHMENTS.md)。

## 微信材料模式

```text
@贾维斯 /材料
@贾维斯 请根据随后材料制作两页汇报
（继续发送图片、视频、文档等）
@贾维斯 /开始
```

材料会话按“聊天 + 发送人”隔离，30 分钟后过期。每次最多 20 个文件，单个文件最多 100MB，总计最多 300MB。当前文件材料可由 Codex 和 ChatGPT 账号模式直接读取；其他模型会明确提示切换，分段文字材料不受影响。

## 安全边界

仓库不包含微信客户端、Windows ISO、虚拟机磁盘、登录 Cookie、API 密钥、桥接令牌、聊天记录或生成文件。请从 `config/*.example.json` 复制本机配置，并在本机填写随机令牌。不要提交 `workbench/data/`、`vm/media/`、`vm/machines/` 或任何真实账号配置。

本项目使用桌面 UI 自动化连接个人微信客户端。微信客户端更新可能导致连接器失效；请自行遵守所使用平台的条款，并先在专用账号与隔离虚拟机中测试。

