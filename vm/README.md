# 贾维斯独立虚拟机

主机保留现有工作台、项目目录、Codex CLI 登录和模型执行。微信和桌面连接器放进独立 Hyper-V 虚拟机；窗口激活、输入、剪贴板操作只在来宾桌面进行。主机管理页仍为 http://127.0.0.1:8790，不向虚拟机或局域网开放管理 API。

当前硬件检查：Windows 10 专业版、6 核 / 12 线程、15.9 GB 内存、固件虚拟化及 SLAT 已开启，Hyper-V 已启用并重启生效。目标虚拟机 `Jarvis-WeChat`：第二代、2 个虚拟处理器、启动 4 GB / 动态 2–4 GB 内存、64 GB 动态虚拟硬盘、Microsoft Secure Boot 与虚拟 TPM。仅使用 Hyper-V Default Switch 内部网络，不桥接主机物理网卡。

## 当前完成情况

已准备主机通信桥、来宾连接器、离线依赖、虚拟机创建及光盘安装脚本。主桌面监听停止，工作台配置已切换为虚拟机模式。2026-10-12 用户已重启，Hypervisor 已启动。已创建并启动 Jarvis-WeChat，vmms / vmcompute 服务运行正常；Windows 安装控制台已打开。虚拟内部网卡通信桥已监听 TCP 8791，工作台管理页恢复在 127.0.0.1:8790。两次控制台截图捕获超时，无法确认安装画面；2026-10-13 用户确认已进入 Windows 桌面，来宾心跳及虚拟网络正常。微信连接器尚未安装或启动，主机桥仍显示等待虚拟机连接，微信后台收发尚未实测。

Windows ISO 下载完成：5,274,607,616 字节，SHA256 `FC323A7D0EF02919FC9150D0C61978CE3A2F32B1519BEDF8E510E392F37CDE57`，根目录及 sources 中的 setup.exe 微软签名均 Valid；记录见 media/download.json。这是本次下载的计算值，尚未与微软发布的整盘哈希表匹配。Python 安装器的 PSF 签名 Valid，MD5 与 Python 官方发布页一致。

Jarvis-Setup.iso 已生成并重新读回验证：715 个文件、1,129,540,704 字节的有效载荷哈希全部匹配。此光盘已包含桥接配置并挂载到虚拟机的第二个 DVD 驱动器，原 Windows 安装光盘保留。通信桥 / 路由 Node 11 项、微信路由 Python 10 项及联系人权限 API 检查通过；虚拟机真实安装、接收、回传和主桌面无干扰仍待实测。

Windows 11 企业版 LTSC 简体中文镜像来自[微软官方评估下载页](https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise)。这是 90 天评估系统，长期运行须另备有效许可及正式镜像。未修改或绕过 Windows 激活。安装镜像只用于虚拟机，不在主机运行其中的 setup.exe。

## 部署顺序

脚本使用本机 Codex 自带 PowerShell 7：`C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe`。不修改 Windows 执行策略。Hyper-V / 虚拟机 / 网络配置脚本须以管理员身份运行。

1. `Enable-HyperV.ps1` 启用可选组件，使用 `-NoRestart`；保存工作后由你手动重启。
2. `Create-JarvisVM.ps1` 核验 ISO 记录并创建新虚拟机；同名虚拟机或目录存在时拒绝覆盖。
3. `Start-Install.ps1` 启动该虚拟机。通过 Hyper-V 管理器连接它，安装 Windows，只选择来宾内 64 GB 虚拟磁盘。系统许可、初始登录和认证由你本人处理。
4. 主机运行 `Configure-HostRelay.ps1`。它只绑定 Default Switch 的虚拟网卡地址和 TCP 8791，添加限定接口、地址及虚拟子网的单条入站规则，不关闭防火墙；生成随机桥接密钥及来宾配置，不显示密钥。
5. 主机运行 `Build-GuestMedia.ps1 -RefreshConfig`，再运行 `Attach-SetupMedia.ps1`。重新启动现有工作台加载桥接配置。
6. 只在虚拟机光盘中运行 `Install-Jarvis.cmd`，离线安装 Python 和微信连接器至 `C:\Jarvis`。主机无法运行这个安装脚本；来宾部署目录已存在时拒绝覆盖。
7. 虚拟机内运行 `C:\Jarvis\Open-WeChat.cmd`，扫码登录贾维斯；再运行 `C:\Jarvis\Start-Agent.cmd`。手机号、密码、扫码和手机确认由你本人完成。
8. 工作台显示“已连接”后，分别验证好友 `/help`、群内两位成员 `@贾维斯 /status` 和真实任务 `/codex` 的往返。需要恢复停止的桥时，在主机点“连接虚拟机贾维斯”，再在来宾运行 Start-Agent.cmd。

## 运行边界

虚拟机需要持续运行，并保持来宾用户桌面登录和解锁；不启用自动登录、不改动来宾安全策略。关闭连接窗口是否仍可读需实测；Hyper-V 增强会话可能重定向剪贴板，日常使用请避免将主机剪贴板共享到来宾。仅隐藏 VM 连接窗口不等于关闭来宾系统。

来宾不复制主机聊天数据库、Windows 凭据、Codex 凭据或私人项目文件。通信桥只接收微信连接器事件和发送确认，只派发回复命令；联系人和群成员的项目隔离继续由主机执行。新旧回复目标不能跨连接器重启恢复：已保存结果可在重新连接后用 `/result` 获取。

桥通过虚拟内部网络 HTTP 传输，使用 256 位随机 Bearer 密钥；不是 TLS，不能用于公网部署。虚拟网卡地址在重启后可能变化，届时须检查绑定地址并同步更新来宾配置。`vm-agent.json`、主机 `data/vm-relay.json` 和带密钥的部署光盘属于本机凭据，不提交 GitHub。

主机点停止后桥拒绝新任务并让来宾连接器退出，模型任务及已完成结果保留。发送超时不自动重复发送，避免迟到回复造成重复；可通过 `/result` 取回。此部署尚未设置开机自动启动。



## 2026-10-13 安装入口修复

用户在来宾首次运行 Install-Jarvis.cmd 时，PowerShell 拒绝未签名的 Setup-Guest.ps1，安装未开始。v2 光盘改用 Python 官方便携运行时执行 setup_guest.py；Open-WeChat.cmd 也改用 launch_wechat.py。两个入口均不执行 .ps1，不修改执行策略。PowerShell 仅作固定的只读 WMI、签名及版本查询。保留虚拟机身份、路径范围、完整清单哈希、PSF / 腾讯发布者签名、版本及重复进程检查。

新的 Jarvis-Setup-v2.iso 替换第二张部署光盘，Windows 安装光盘保持挂载。文件篡改、路径越界、重复清单、文件缺失的 4 项测试通过；便携 Python 可运行，安装器真实拒绝在主机上运行。来宾安装、微信扫码和真实消息回传仍待用户重试后验证。


2026-10-13：用户在安装结束后按键关闭窗口，无法确认成功与否。增加光盘中的 Check-Installation.cmd：只读核验已安装的 Python、微信依赖、兼容客户端哈希及连接配置，结果保存到来宾 LocalAppData/JarvisGuest/Installation-result.txt 并用记事本显示。安装入口也增加明确成功 / 失败提示。当前部署光盘为 Jarvis-Setup-check.iso，来宾实际安装状态待此诊断确认。

用户确认来宾 C:\Jarvis 不存在，安装尚未成功。当前 Jarvis-Setup-logs.iso 的安装器将进度与失败详情保存到来宾 LocalAppData/JarvisGuest/Install-result.txt，并用记事本显示；子步骤失败保留输出，签名失败显示状态与发布者。在确认 Hyper-V 身份后，安装失败摘要尝试通过现有认证虚拟网卡桥反馈至工作台 listenerError，回传失败不影响本地错误记录。真正的安装失败原因仍待重试取得。

2026-10-13 根因已定位：来宾 PowerShell 的 Microsoft.PowerShell.Security 模块因 Security.types.ps1xml 的 AuthorizationManager 验证失败，Get-AuthenticodeSignature 无法加载，安装停在创建 C:\Jarvis 之前。现改为 ctypes 调用 Windows WinVerifyTrust 原生接口，从同一验证状态读取签名证书发布者，并通过版本资源 API 读取版本；不加载 PowerShell Security 模块，不修改执行策略或证书信任。Python / 微信真签名、发布者不匹配、未签名文件、签名文件被改动的 4 项实际 Windows API 测试通过，清单测试 4 项通过。新的 Jarvis-Setup-native.iso 已核验并挂载，来宾需重试确认安装。

2026-10-13：用户提供来宾 Install-result.txt 截图，显示离线依赖 Successfully installed 和安装器最终完成提示，确认 Python 与微信连接器已完成安装。下一步由用户在来宾 Open-WeChat.cmd 扫码登录贾维斯，再运行 Start-Agent.cmd；虚拟机内真实消息收发与多人并发仍待验证。

2026-10-13：用户反馈 Open-WeChat.cmd 显示按任意键后关闭，尚未得到具体启动错误。已给 launch_wechat.py 增加虚拟机内持久日志（LOCALAPPDATA/JarvisGuest/WeChat-launch-result.txt）和自动记事本显示，并核验启动后进程是否持续运行。新增 Update-Launcher.cmd 只更新 launch_wechat.py 与 Open-WeChat.cmd，先验证光盘清单哈希并保留旧文件备份，不重新安装或覆盖账号/连接配置。3 项检查通过（失败日志留存、修改文件拒绝更新、备份/配置保留）。Jarvis-Setup-launch.iso 内 758 个文件哈希读回通过，已替换挂载。用户下一步在虚拟机光盘刷新并运行 Update-Launcher.cmd；真实微信登录和消息收发仍待确认。

2026-10-13：用户截图显示 update_launcher.py 重试固定临时文件时 Errno 13 Permission denied。已在本机 Windows 临时目录复现：shutil.copy2 从只读源继承只读属性，无法替换只读目标，重试又不能覆盖上次只读临时文件。更新器改用 copyfile + 唯一临时文件，只为两份启动器目标移除只读属性；替换失败恢复原模式，保留首次备份和原连接配置。安装器后续也改用 copyfile，避免复制 DVD 文件只读属性。4 项检查通过，包含真实 Windows 只读源/目标/残留临时文件重试。Jarvis-Setup-writable.iso 的 758 个文件哈希读回核验通过，已挂载。无需重新安装，用户下一步在虚拟机光盘刷新并运行 Update-Launcher.cmd，随后反馈持久启动记录或完成微信扫码登录。

2026-10-13：用户确认微信已登录，但 Start-Agent.cmd 很快到 pause 并关闭；主机未收到 ready 或启动错误。发现 vm_agent.py 抛弃适配器 stderr，且早退时 daemon 回传线程可能来不及发送错误。修复为读取原始 stderr、显示 error/warning/ready 状态，退出前等待事件回传，并以失败退出码反映适配器失败。新增 launch_agent.py 记录 LOCALAPPDATA/JarvisGuest/Agent-result.txt，失败后自动记事本展示；Start-Agent.cmd 调用它。新增光盘 Update-Agent.cmd 只更新启动器和 vm_agent.py，保留既有配置与备份；沿用已修复只读属性的更新机制。2 项实际子进程/本地 HTTP 故障测试、4 项启动器测试、10 项微信路由测试通过。Jarvis-Setup-agentlog.iso 的 760 个文件哈希读回核验通过并挂载。实际来宾启动退出原因仍待用户运行光盘 Update-Agent.cmd 后确认，不宣称已修复连接失败。

2026-10-13：用户 Agent-result.txt 显示 DLL load failed while importing win32ui，找不到指定模块。PE 导入表确认该 pyd 依赖 mfc140u.dll、VCRUNTIME140(_1).dll；来宾缺少 VC++/MFC 运行库是优先诊断，具体导入需在来宾修复后验证。从 Microsoft Learn 官方入口 https://aka.ms/vc14/vc_redist.x64.exe 下载 x64 v14 Runtime 14.51.36247.0，18731856 bytes，SHA256 843068991DAAA1F73AD9F6239BCE4D0F6A07A51F18C37EA2A867E9BECA71295C。PowerShell 和原生 WinVerifyTrust 均确认 Valid / Microsoft Corporation。新增 Repair-Runtime.cmd/repair_runtime.py：先原生模块导入检查，缺失时核验文件哈希+发布者，通过 Windows RunAs 调用官方运行库安装器，安装后再次检查，失败/3010 均留存 LOCALAPPDATA/JarvisGuest/Runtime-repair-result.txt；成功更新连接器并启动。对新安装集成相同运行库检查。修正检查器将不存在的顶层 uiautomation 改成实际 wxauto4.uia 包。4 项修复逻辑检查、2 项连接器失败回传检查、4 项启动器检查通过；真实主机模块导入探测 NATIVE_IMPORTS_OK，不在主机安装运行库。主机桥监听 172.25.96.1:8791、来宾 172.25.108.137 和已有规则范围正常。桥的 urllib 通信改为仅私网 IP/8791 且绕过系统代理，避免密钥发送到代理和本地桥连接被代理影响。Jarvis-Setup-runtime2.iso 的 763 个文件哈希读回通过并挂载。下一步用户在虚拟机光盘刷新，运行 Repair-Runtime.cmd；Windows 安装确认和来宾真实连接结果待用户完成，未宣称已连接。

2026-10-14：来宾已不再报 win32ui DLL 加载失败；当前 Agent-result.txt 转为正确版本 4.1.8.107 但 wxauto4 找不到已登录主窗口。用户按要求展开聊天列表重试后仍失败，因此不能仅归因为托盘/最小化。静态读取本地库类定义确认期望主窗口 mmui::MainWindow / 微信、登录窗口 mmui::LoginWindow；WeChatMainWnd 支持 nickname/hwnd/resize 参数，未盲改第三方库。新增只读 Diagnose-WeChat.cmd/diagnose_wechat.py，首先执行 Hyper-V 来宾守卫，只枚举已安装兼容路径的 Weixin.exe 窗口，记录窗口类/标题/可见性/最小化、桌面 SessionId、进程完整性级别、主窗口直接 UIA 控件和读取错误；不展开消息内容、不点击或发送消息。另以不含认证密钥的 GET 测试配置中的私网 8791 桥，HTTP401 只用于判断可达，不建立 peer。日志留存在 LOCALAPPDATA/JarvisGuest/WeChat-window-diagnostics.txt，自动记事本展示。用既有 C:\Jarvis 运行时和 PowerShell 生成微型 Jarvis-Setup-windowdiag.iso，3 个文件/8645字节均核验通过，已挂载替换旧部署盘。语法与所用库 API 静态导入检查通过，未在主桌面枚举窗口。下一步用户虚拟机光盘刷新并运行 Diagnose-WeChat.cmd，具体窗口匹配/权限/会话失败原因仍待实际报告。

2026-10-14：用户真实诊断显示 HTTP 私网桥超时，Wechat/诊断均 SessionId=2，兼容路径有可见未最小化的原生窗口 Qt51514QWindowIcon / 微信。旧诊断错误地只对 Win32 class=mmui::MainWindow 的窗口读取 UIA，不能据此判断微信未登录；另 PyHANDLE 不支持 with，权限读取失败是诊断代码问题。修正：显式 Close 句柄，实际在本机当前诊断进程读取 RID8192 验证成功；对兼容微信 PID 的可见 Qt/微信窗口也读取 UIA ClassName，并限制容器深度3/总节点30，不读取消息/列表子项。两项树读取范围检查通过。查明主机 ActiveStore 有当前 C:\Program Files\nodejs\node.exe 的 Public TCP Any 显式 Block，覆盖既有 Jarvis-VM-Relay Allow。新增 Repair-HostRelayFirewall.ps1：守卫 VM身份/内部交换机/虚拟IP/8790与8791同进程和Node路径，备份具体原规则；为该 TCP Block 排除仅8791（仍阻断1-8790及8792-65535），并把已有8791 Allow 程序限定到当前Node，保持接口/IP/VM网段范围。第一轮 Windows规则ActiveStore不可写导致 Set-NetFirewallPortFilter找不到实例，已按catch回滚；改从PersistentStore定位同名规则后成功，回读端口范围/程序字段通过。可用脚本 -Restore 恢复备份，不关闭防火墙、不改UDP或其他Node程序规则。当前只确认主机规则修正，来宾连通性仍须复测。微型 Jarvis-Setup-windowdiag2.iso 三文件核验通过并挂载；下一步用户在VM光盘刷新重新运行 Diagnose-WeChat.cmd，提供HTTP结果及uia控件字段，以决定微信接入修复方式。

## 2026-10-14 无障碍启动测试

用户最新诊断确认主机桥 HTTP 401 可达；微信及诊断程序同桌面会话 SessionId 2、同 Medium 完整性级别 RID 8192。可见微信窗口的 UIA 仅有 Qt51514QWindowIcon Window 和空 Pane，没有 mmui::MainWindow，不能按已连接处理。

准备 Test-Accessibility.cmd：仅在 Hyper-V 来宾运行，先要求手动从托盘退出微信，启动 Windows 自带 Narrator 并核验实际进程路径，再通过原有文件哈希、腾讯签名、版本检查启动兼容微信；最多 3 分钟检测可读主窗口。检测通过才启动 C:\Jarvis\launch_agent.py；超时保存同次只读窗口诊断到 LocalAppData/JarvisGuest/Accessibility-result.txt。Narrator 保持运行用于此次试验，可能有朗读声；用户可用 Win+Ctrl+Enter 退出。此步骤是可验证的兼容性试验，不保证恢复 UIA。

6 项启动检查通过，涵盖空 Qt 树不能误判成功、运行中微信阻止错误启动顺序、主机拒绝执行、成功后才启动连接器、超时保留诊断、原生进程路径查询。既有启动器 4 项测试通过。Jarvis-Setup-accessibility.iso 的 7 个文件、25,369 字节有效载荷全部哈希读回匹配，已替换第二张部署光盘；来宾测试结果待用户反馈，主机 connected=false。

排查依据：https://github.com/Hello-Mr-Crab/pywechat/issues/270 （维护者建议登录前开启讲述人，同样空 UIA 症状也有失败案例）；微软讲述人开关：https://support.microsoft.com/en-us/accessibility/windows/narrator/appendix-b-narrator-keyboard-commands-and-touch-gestures 。

2026-10-14：用户首次无障碍测试停在启动 Narrator.exe，CreateProcess 返回 WinError 740，尚未启动微信。测试 v2 改用 os.startfile(path, 'open') 经 Windows ShellExecute 激活 UIAccess 应用；测试进程和微信连接器仍维持原来的普通权限。失败/用户取消时停止后续微信启动，日志提供虚拟机内 Win+Ctrl+Enter 手动启动讲述人的备用方式。新增标准启动和取消后不启动微信检查，共 8 项测试通过；主机未启动 Narrator。Jarvis-Setup-accessibility2.iso 的 7 个文件、25,882 字节载荷哈希读回通过，并已替换第二张部署光盘。真实来宾启动与 UIA 恢复仍待验证。

依据：Python os.startfile 文档 https://docs.python.org/3.13/library/os.html#os.startfile ，Windows ShellExecute https://learn.microsoft.com/en-us/windows/win32/shell/launch 。

2026-10-14：用户 v2 日志确认 Narrator 已启动，随后停在兼容客户端 SHA256 不匹配；原报错未显示路径，尚不能确认是自动更新还是其他变化。已将启动器报错补充为具体文件及实际/预期哈希。

v3 Test-Accessibility.cmd 在启动微信前调用 repair_client.restore：只在来宾运行，完整验证修复光盘，核验原程序与 DLL 的腾讯签名和版本，打印已变化文件的哈希、当前版本及签名结果；确认微信退出后，将旧 client 整个目录和旧 preparation.json 保留为唯一备份。先复制并逐文件校验原客户端，替换失败回滚程序和记录。未直接读取、修改或删除账号数据库、模型凭据和连接配置。兼容核心文件未变化时保持现状。恢复后继续原讲述人和 UIA 测试，不将文件恢复视为微信连接成功。

来源使用原部署 payload 的 31 个原始客户端文件，逐项与之前完整清单一致；两项腾讯签名和 4.1.8.107 版本核验通过。6 项恢复测试与 8 项无障碍启动检查通过，覆盖备份完整性、配置保留、篡改/未列出文件拒绝、进程竞态和替换失败回滚。Jarvis-Setup-accessibility3.iso 的 41 个文件、827,821,197 字节全部哈希读回匹配，已挂载到第二张部署 DVD。客户端实际变化原因、真实来宾恢复及 UIA 读取仍待下一次日志验证。

2026-10-14：按用户要求恢复已保存的 Jarvis-WeChat 并打开 vmconnect 控制台；桌面“贾维斯虚拟机.lnk”已建立、目标读回确认。Open-JarvisVM.ps1 校验固定 VM ID，支持关闭/保存状态启动、暂停恢复、运行状态直接连接；普通双击时 Hyper-V 操作由 Windows 正常权限提示提升，控制台保持可见。快捷方式使用系统 Windows PowerShell，避免快捷方式在不同用户上下文下将 profile 内的运行时路径重定向；源文件采用 UTF-8 BOM。

重启后 Default Switch 地址由 172.25.96.1 变成 172.31.112.1，旧防火墙接口记录也变成已过期 GUID。Refresh-HostBridge.ps1 核验固定 VM、Internal Switch、原 TCP 8791 / Node 程序 / 原 IP 后，保存原配置和防火墙范围，更新桥及来宾源配置的地址，重新限定当前虚拟网卡和 /20 子网；密钥未更换。工作台 Node 已重新启动，127.0.0.1:8790 API 读取通过，vmRelay configured=true / connected=false，等待来宾连接。

v4 无障碍入口新增 refresh_bridge.py：核验光盘和来宾 VM，限定 HTTP 私网 8791、贾维斯账号和原桥接密钥一致，仅同步地址，保留旧配置备份；然后执行已准备的兼容客户端恢复和真实 UIA 检测。桥接同步 3 项测试与启动流程 8 项检查通过。Jarvis-Setup-accessibility4.iso 的 43 个文件、827,823,644 字节全部哈希读回通过，已挂载第二张部署光盘。该光盘现含桥接凭据，只在本机保留。下一步仍需用户在虚拟机内退出微信、运行 Test-Accessibility.cmd v4，确认登录及真实连接，随后验证私聊/群聊并发。

2026-10-14：用户确认 v4 连接器已连接，主机 API 同时确认 configured=true、connected=true、心跳 stale=false。随后用户关闭了终端导致连接器停机；重新运行后真实私聊 /help 收件 2 / 发件 2，用户确认私聊可回复，但其他窗口和群内 @ 无回复。主机观测 listening=1、groups=0、waitingWindows=1。

修复会话发现：免打扰群的 [有人@我] 或 @贾维斯 预览变化可在未读数量为 0 时触发接入；VM 中优先在当前会话列表精确匹配唯一会话行并 double_click 打开独立窗口，再核对目标名称和类型；没有对应会话行时保留原库 AddListenChat 搜索退路。主桌面仍不打开或切换窗口。health 中 retrying 改为实际未接入的失败会话数，避免失败提示立刻被正常心跳清除。12 项微信路由/发现检查通过；真实群回复与多成员模型任务仍待更新后实测。

新增 background_agent.py：仅来宾可启动，DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP，将输出留存到 LocalAppData/JarvisGuest/Agent-background-*.txt，启动器可以关闭。Start-Agent.cmd 改为后台入口，Check-Agent.cmd 显示进程和最新日志，Stop-Agent.cmd 写专用停止请求，vm_agent 在轮询间隙正常停子进程。更新器先核验全部更新文件、拒绝运行中的旧连接器，再备份替换程序；配置和微信文件保持现状。真实 Windows 子进程测试确认启动器进程退出后子进程仍能输出并结束，既有 4 项更新器检查通过。此测试不证明来宾消息收发。

Jarvis-Setup-background.iso 的 9 个文件、35,548 字节全部哈希读回通过，已挂载。用户需先关闭旧前台终端，在来宾部署光盘运行 Update-Background.cmd，后续正常使用 C:\Jarvis\Start-Agent.cmd。后台运行仍要求微信及来宾桌面可访问，关闭终端不等于关闭虚拟机。

实际 Codex API 两条固定文本验证任务均遇到 request timed out，未得到模型输出，已停止自己创建的两条验证任务（状态 interrupted）；CLI 登录状态 ok=true，不能等同于模型执行可达。GPT/Muse API 尚未配置。本次不能声称多智能体执行已完成。

会话行 API 参考项目源码：https://github.com/fly000001/wxauto4/blob/main/wxauto4/ui/sessionbox.py 。

2026-10-14：用户退出微信后旧 C:\Jarvis\Open-WeChat.cmd 再次报核心文件哈希变化。此日志仍未提供具体当前版本，不能断言本次一定自动更新；本机历史已确认该客户端曾在退出/更新后变成 4.1.15.53。保持登录的进程能继续工作，与磁盘文件随后变化并不矛盾。

增加 Install-Recovery.cmd / install_recovery.py：核验完整光盘、拒绝仍运行的旧连接器后更新后台和日常启动器，记录当前程序版本/签名及文件差异，保留旧程序目录并恢复原始兼容客户端；将原始 client 和 preparation.json 完整留存到来宾 C:\Jarvis\recovery-media，复制后逐项清单核验。已有副本核验失败时拒绝覆盖。启动器发现核心文件变化且有本机恢复副本时执行同样的备份恢复，再重新核验，不绕过文件检查。安装入口随后开启讲述人和微信，等待用户登录及主界面可读后启动后台连接器。

本机副本留存/复用/篡改拒绝、自动恢复后重新核验 2 项新检查，客户端备份恢复 6 项检查，更新器 4 项检查均通过。Jarvis-Setup-recovery.iso 的 53 个文件、827,861,228 字节全部哈希读回通过，已挂载。来宾安装和下一次退出后自动恢复尚待用户实际验证；群聊修复仍未实测通过。

2026-10-14：用户确认关闭启动终端后，真实私聊 /help 和两位群成员 @ 指令均正常回复。主机统计 received=3 / sent=3 / groupReceived=2，listening=2 / groups=1，retrying=0 / waitingWindows=0，心跳正常。这一步完成实际来宾后台收发与群成员路由验证；4 并发队列继续启用。

Codex 请求超时排查使用 OpenAI Docs。实际 Windows 用户已有 HTTP 系统代理 127.0.0.1:7897；官方 Codex 服务无认证直连请求 6 秒超时，通过现有代理返回 HTTP 405。给测试子进程设置代理后，真实 Codex 返回 JARVIS_PROXY_OK。工作台新增 codex_network.mjs / data/codex-network.json，只给 Codex 子进程设置现有本机代理和 localhost 排除项，保留原模型、provider、登录状态和全局配置。尝试内置 provider 的 supports_websockets 覆盖被实际 CLI 拒绝，因此未使用该覆盖。Node 13 项检查通过。

增加严格形状校验的已认证 VM 扫描心跳恢复，以便主机服务重启后原后台进程自动重新接入。用户最初允许停止两条任务；操作时两条原任务已完成并送达，因此保留结果。随后不断收到新微信任务，用户另行明确授权停止当前所有任务并立即重启。已执行授权停止与重启，当前主机 Node PID 2408，虚拟机通过心跳自动恢复到已连接，仍监听 1 私聊 / 1 群。应用内同时提交两条固定文本验证，均 completed，结果为 JARVIS_APP_PROXY_A / B，无错误，证明代理修复已通过实际工作台模型执行。

用户最新偏好：没有 OpenAI API 和 Meta Model API 密钥，希望使用已有 ChatGPT / Meta AI 账号。下一步正在核实 ChatGPT 登录复用及 Muse Code 官方浏览器登录；尚未把 GPT/Muse 账号模式写入服务，尚未安装 Muse Code。本机未找到 muse 命令。相关主来源：https://learn.chatgpt.com/docs/auth ，https://learn.chatgpt.com/docs/config-file/config-reference ，https://dev.meta.ai/docs/muse-code/auth ，https://dev.meta.ai/docs/muse-code 。Meta Model API 的当前 muse-spark-1.3 / api.meta.ai/v1 配置已与官方文档核对，但用户不选择 API key 路径。

2026-10-15：ChatGPT 账号模式已上线，使用当前 codex login 经 Codex read-only 沙箱执行，独立保存 GPT 会话。真实应用两轮测试完成，第二轮正确返回仅第一轮出现的随机标记，详见 work/live-gpt-account-validation.json。无活跃任务时重载服务，微信来宾通过心跳自动恢复已连接，未更换来宾部署光盘。

Muse Code 官方 Windows 原生版本 1.4.8-R6256.1 已下载到工作台 tools/muse/muse.exe，大小 474286840 与官方 manifest 一致，SHA256 f9d7be3fce39eb23a1bdda019568e0ae7156514c75c408f54c8c4ddaa297800e 一致，Meta Platforms Authenticode 签名 Valid；未执行全局安装器、未修改 PATH 或执行策略。账号路径及本机官方登录入口已开发，15 项 Node 检查通过。生产固定 Meta provider、empty preset、禁用 shell/write/web 等工具，按工作台会话重放历史，JSONL 完成事件决定成功。官方 Echo 仅做格式验证，不能算真实模型成功；已打开官方登录窗口，等待本人授权，尚未验证 Meta 真实推理。

2026-10-16 更正：用户提供 https://muse.ai/ 并确认已在 Chrome 登录。此前错误接入 Muse Code，不能据此继续 Muse 个人智能体的原项目与目标。已撤销 /muse 到 Muse Code 的生产路由，原下载文件未删除。官方产品说明确认 Muse 个人智能体确为 Meta 产品；区别在个人智能体与编程 CLI，并非所属公司。

通过 GitHub 参考 nikships/muse-cli，隔离安装 PyPI muse-cli 0.3.2 及固定依赖；本地 npm 安装 Vercel agent-browser 0.39.1，未执行安装脚本或全局修改。新增个人智能体适配：新建独立聊天、发送指令、读取原会话、原会话继续、目标目录。无原聊天 ID 时拒绝发到主聊天；接口与目录遵循本机管理页认证和现有联系人工作区边界。Node 14 项与 Python 4 项通过。连接助手只在本人输入 YES 后运行，精确限制 Muse 域名和已登录 Cookie，凭据目录限当前用户与 SYSTEM；未调用导出、未读取浏览器凭据。已打开授权说明窗口，等待本人操作；hasSavedMuseLogin=false、museConnected=false，不声称真实接通。

工作台无运行任务时安全重载，当前 PID 9512，微信来宾已自动重连、心跳正常，GPT 账号模式仍就绪。详细连接说明见 ../workbench/PERSONAL_MUSE.md。

2026-10-16：用户说明已输入 YES 后才打开 Chrome 远程调试，要求重新连接。重试仅复用同一次授权，不重复索取许可；本机 Muse Cookie 保存成功（未输出值），/api/muse/check 返回 ok=true，原目录为 2 会话 / 6 目标。通过工作台同时提交两个 Muse 会话，各完成两轮，第二轮准确返回各自随机标记且远端 session 不同；只读原历史检查返回 4 条文本消息，用户与助手内容均正确。结果详见 work/live-personal-muse-validation.json，生产请求使用 muse.ai 个人智能体，不是 Muse Code。微信来宾及 GPT 均保持正常。后续 Muse 请求直接在后台连接，授权终端、Chrome 调试开关可以关闭。

2026-10-16 微信未收件排查：桥有心跳但监听为 0、waitingWindows=2，之后离线。重启来宾连接器后收到当前版本 4.1.8.107 主窗口不可访问的明确错误；用户确认微信聊天列表已展开。Muse 真实连接及原目录仍正常，近期无新微信任务进入执行队列。

主机新增 assistant_health.mjs，将通信心跳与窗口可读/收件分开；0 监听且有等待窗口时不再显示收件正常，窗口恢复前不清除警告。Node 16 项通过，无任务时安全重载至 PID 19896，再次核验 Muse 连接、目录成功。来宾日常 Open-WeChat、Start-Agent 入口增加讲述人前置检查；讲述人只认可与当前启动进程同桌面会话中的实例，防止把另一会话的讲述人当作就绪。Open-WeChat 使用已安装的隔离 Python 环境，保证 UIA 检查所需 pywin32 可用。后台启动前确认实际主窗口可读；只创建了进程时明确显示尚未确认连接。

新建 Fix-Listening.cmd / fix_listening.py：拒绝运行中的连接器和微信，不强杀客户端；核验光盘后备份并替换启动程序，保留账号、模型凭据、通信配置，先开启讲述人再打开兼容微信，等待本人登录和可读主界面后启动后台。启动前置与主机拒绝检查 5 项、无障碍测试 8 项、本机恢复 2 项、真正 detached 子进程 1 项通过。Jarvis-Setup-listenfix.iso 内 15 个代码文件、47656 字节全部哈希读回匹配，已替换部署 DVD；没有客户端数据库、主机历史或账号凭据。首次 ISO 检查因清单 SHA 字母大小写格式未匹配而停止，修正格式后才挂载。

已请用户在虚拟机托盘退出微信，刷新光盘运行 Fix-Listening.cmd；真实来宾恢复与手机收发尚待验证，当前不能标为故障已修复。

2026-10-16：用户运行 Fix-Listening.cmd 后报告“已连接主机工作台”。主机实际恢复 listening=2 / groups=1、waitingWindows=0、retrying=0、receiving=true，心跳正常。随后接到真实微信 Muse 任务 c139e3f8-26a7-45fe-a9f5-988a7655b0dd，任务 completed、deliveryStatus=sent、无执行或回传错误，收件 1 / 发件 2，pendingReplies=0。此项覆盖真实微信收件 → muse.ai 个人智能体 → 微信回传，记录见 work/live-wechat-muse-recovery-validation.json。没有将用户指令正文、回复正文或联系人资料写入该验证记录。故障现已实测恢复；保持来宾微信、同会话讲述人及解锁桌面运行，关闭启动终端不会停止监听。
