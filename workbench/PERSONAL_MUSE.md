# muse.ai 个人智能体接入

这里连接的是 https://muse.ai/ 上的个人智能体，包括已有会话、目标与云端任务。Muse Code、Meta Model API 是其他产品，不会自动接管这些记录。

本机已准备 muse-cli 0.3.2 的隔离 Python 环境，以及 Vercel agent-browser 0.39.1 的本地工具目录。前者是社区协议客户端，平台变化可能需要更新；不需要申请模型 API 密钥。

## 一次性连接

1. 在你已登录 Muse 的 Chrome 中打开 `chrome://inspect/#remote-debugging`，允许当前浏览器实例远程调试，保持 Muse 标签页打开。
2. 工作台点击“连接 Chrome 登录”，或打开同目录 `Connect-Muse.cmd`。窗口解释范围，需要本人输入 `YES` 才开始。
3. 若 Chrome 弹出连接许可，请本人确认。程序只选择 HTTPS、主机名严格为 `muse.ai` 的标签页，从当前页取得 Cookie，再按 `muse.ai` / `.muse.ai` 精确域名筛选，要求存在 `hatch_sess`，不显示值。保存到本机 `data/muse-personal/cookies.txt`。目录 ACL 限当前用户及 SYSTEM；不写入聊天、日志或第三方中继。
4. 保存完成后可关闭远程调试。后续请求由社区客户端直接连接 Muse，不再切换桌面窗口。回到工作台点击“检查 Muse 连接”，再点击左侧“刷新 Muse 目录”。

网页登录本身不等于授权工作台。本机一次性接入需要 Chrome 调试授权；准备完成与真实账号验证是两个阶段，界面只有实际连接检查成功或收到真实回复后才显示已连接。

## 会话与手机使用

点击 Muse 原会话可以导入最近的文字并继续同一个远端会话。目标目录先以只读方式展示。新工作台会话在 Muse 创建独立聊天；创建未返回 ID 时拒绝发送，不会回退到个人主聊天。每个工作台会话同一时间处理一项指令，群里不同成员使用各自会话。

手机使用 `/muse 问题或任务`，群里仍需 @贾维斯。Muse 云端任务可能持续运行；收到第一条回复只表示指令已得到回复，不代表所有后台目标已经完成。等待超时也不代表远端停止，应检查原会话后再决定是否重发。

Muse 原目录只出现在受本机登录 Cookie 保护的管理页面，不通过好友目录命令公开。好友仍只能看到归属自己工作区的工作台会话；主号私人目录访问保留原来的显式授权规则。

## 来源

- https://github.com/nikships/muse-cli （MIT；当前安装版本 0.3.2，Python 依赖锁定记录见 tools/personal-muse-requirements.lock.txt）
- https://github.com/vercel-labs/agent-browser （Apache-2.0；当前安装版本 0.39.1，npm 锁定记录见 tools/personal-muse-browser/package-lock.json）
- 官方个人产品说明：https://introducing.muse.ai/
- 官方 Gadget SDK（另一条需要手机配对的路线，本实现未安装该设备服务）：https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux

2026-10-16：用户已经输入 YES，随后开启远程调试，并明确要求重试同一连接。重试复用同一授权，未再次索取凭据；本机保存成功，真实连接检查通过。原目录读取成功（测试前 2 个会话、6 个目标）。两个独立 Muse 原生会话同时进行两轮应用测试，分别准确返回自己的随机测试标记；只读历史导入检查取得 4 条消息，同时保留用户消息与助手回复。结果记录见 ../../work/live-personal-muse-validation.json。微信虚拟机保持连接、心跳正常；GPT 账号模式保持就绪。
