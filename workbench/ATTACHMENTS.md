# 工作台附件回传

Codex、ChatGPT 账号模式和 muse.ai 个人智能体共用附件存储与发送通道。可直接在任务中要求“生成 PPT 并发给我”“把生成的图片发给我”等，不需要用户输入文件路径或切换专用模型。

## 部署与使用

主机启动 `server.mjs`。在贾维斯虚拟机中打开 `Jarvis-Setup-attachments3.iso` 部署光盘，运行 `Update-Attachments.cmd`，确认显示 `Jarvis Attachment Update v3`。更新程序校验文件清单，停止原连接器，替换代码并启动后台进程，保留微信账号、模型登录和本机任务。微信主窗口必须可读；后台启动程序会先启用讲述人。本次 v3 更新启动后默认暂停窗口操作，请回主机工作台点击“恢复监听”；以后普通启动保持原有行为。

v2 修复首版批处理使用 LF 导致 Windows cmd.exe 截断命令的问题。更新入口使用 ASCII/CRLF，在持续显示的 `cmd /d /k` 窗口执行，结束后打开 `%LOCALAPPDATA%/JarvisGuest/Attachment-launch-result.txt`。日志在 Python 启动前创建，包含解释器缺失、文件缺失和 Python 原始错误；`-X utf8` 显式保证隔离模式下重定向的中文日志编码正确。打包时所有 `.cmd` 均转换为 CRLF 后计算清单哈希。

v3 增加主机“暂停窗口操作 / 恢复监听”按钮。必须有来宾 `controlProtocol: 1` 才启用，暂停状态须在来宾确认后显示。暂停时连接器保持运行，只发送缓存状态心跳，不读取微信控件、不发送文字或文件；模型任务仍可完成，结果保留在任务中。恢复后可使用 `/result` 取回未发送的结果。切换时若有回复正在发送，会提示先等待该次发送完成；该按钮不取消模型任务。主机服务重启后，已暂停来宾的认证心跳可恢复暂停状态。

主机状态 `vmRelay.supportsFiles === true` 表示来宾已声明附件协议 v1；普通心跳在线并不代表支持文件。旧连接器会收到明确的更新提示，任务文件仍保留。

微信私聊直接提交任务，群聊仍需 @贾维斯。模型完成后先回复正文，再发送逐个附件。群文件前有“回复 发起人：附件名”的消息，使用原任务的成员路由。微信窗口和剪贴板操作在虚拟机内串行执行，模型任务仍可并发。

`/result` 取回自己的最近完成任务：部分回传失败时只重试未完成文件；全部回传成功后主动再次取回会重发全部附件。重试不重新运行模型。工作台会话内的附件链接可直接下载文件，需要当前本机管理会话的认证 Cookie。

## 范围

- 不根据扩展名限制附件。图片、视频、PPT、PDF、Office、压缩文件等均经微信通用 `SendFiles` 接口提交；显示为文件还是媒体由微信决定。微信自身可能拒绝某些类型或大小。
- 当前单个文件最多 100 MiB、每任务最多 20 个、总计 300 MiB。通用发送能力不等于为所有模型增加图片或视频生成能力，必须有实际生成的文件。
- WhatsApp 有文档附件发送实现，但当前账号未连接，尚未做真实账号验收。iLink 独立入口当前只传文字，遇到附件会明确报错，不会声称文件已发送。
- 当前实现是助手向用户发送任务产物；手机向模型上传、解析附件是另一条通道。
- 微信成功确认表示连接器已调用客户端发送接口。对方最终接收、平台过滤和大文件上传仍需在手机端检查。

## 文件来源与隔离

Codex 在项目内执行，将交付文件放在 `<project>/.jarvis-outbox/<task-id>/`；GPT 账号模式以本轮输出目录作为可写工作区。仅收集当前任务目录，拒绝符号链接、硬链接和目录越界，再复制为 `data/attachments/<task-id>/<artifact-id>` 的持久副本。附件名称、字节数和 SHA-256 存入任务。项目目录本身不是 Windows 用户隔离，保持原有执行权限边界。

Muse 使用 `/home/hatch/.jarvis-outbox/<task-id>/`，返回明确的 `workbench-artifacts` 清单。只接受属于本任务目录的路径，使用已登录网关的 `fs.stat` 和分块 `fs.read` 取原字节。不能使用默认 `fs.export`，该接口只导出 PDF。未配置文件工具的文本模型可返回 `workbench-files` 文本或 Base64 文件块，工作台只解码数据，不执行模型返回的代码。

## 主机到虚拟机

主机通过 `/v1/poll` 提供 `send_file` 元数据命令；来宾通过 `/v1/file` 请求原始字节。这两个接口都需要专用桥接密钥，文件请求还须匹配当前 runId 和未过期、未确认的命令 ID。没有任意路径读取或任意 URL 下载接口。

来宾将文件写入 `%LOCALAPPDATA%/JarvisGuest/attachments/<command-id>/<filename>`，校验大小、SHA-256、有效期和路径后才调用微信。文件缓存在 24 小时后由后续下载清理，给客户端上传留出时间；缓存总量限制为 2 GiB。

## 验证记录

- Node：`test_artifacts.mjs`（存储、类型、校验、群成员隔离、重试、桥接文件授权）以及既有工作台测试。
- Python：`test_file_transfer.py`、`test_muse_artifacts.py`、既有微信/Muse 测试。
- 来宾安装器：`work/test_attachment_update.py`；真实 cmd.exe 启动、成功/失败退出码及缺失文件日志：`work/test_attachment_launcher.py`。
- 三个真实模型的文件输出与认证下载：`work/live-attachments-validation.json`；6 个文件的 PNG/PPTX/MP4/UTF-8 格式检查：`work/live-attachment-format-validation.json`。
- GPT 继续旧会话时的新目录隔离：`work/live-gpt-attachment-resume-validation.json`。
- 更新 ISO 的 19 个文件均经回读 SHA-256 校验。用户已确认通过手机收到 GPT 生成的 PPTX 且可以打开；图片、视频已做模型生成及原字节下载验证，尚未逐项做手机端收件验收。
- 窗口暂停：`test_ui_pause.py` 使用真实驱动循环和模拟微信控件验证暂停时无扫描和发送、同一进程恢复扫描；`test_vm_relay.mjs` 验证确认、发送阻止和重启后状态恢复。
