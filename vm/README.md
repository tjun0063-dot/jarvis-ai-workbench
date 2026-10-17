# 贾维斯微信虚拟机

微信桌面自动化运行在独立的 Hyper-V 虚拟机中，主机保留工作台、模型登录和项目目录。主机管理页只监听 `127.0.0.1:8790`；来宾通过 Hyper-V Default Switch 的私网桥连接主机 TCP 8791。

## 环境要求

- Windows 11 专业版或企业版，并已启用 Hyper-V。
- Node.js 20+、Python 3.12 和 PowerShell 7。
- 一套合法授权的 Windows 虚拟机系统。
- 一个单独用于助手的微信账号。

虚拟机安装、微信登录和手机确认需要在本机完成。仓库不提供 Windows ISO、微信客户端、虚拟磁盘或账号凭据。

## 部署顺序

1. 以管理员身份运行 `Enable-HyperV.ps1`，保存工作后重启 Windows。
2. 准备 Windows ISO，再运行 `Create-JarvisVM.ps1` 和 `Start-Install.ps1`。
3. 在虚拟机中完成 Windows 安装，保持来宾桌面登录和解锁。
4. 主机运行 `Configure-HostRelay.ps1`，生成本机桥接密钥和来宾配置。
5. 主机运行 `Configure-AutoRelay.ps1`，将防火墙规则限制为 Node、TCP 8791 和本地子网，同时启用地址自动发现。
6. 运行 `Build-GuestMedia.ps1 -RefreshConfig` 和 `Attach-SetupMedia.ps1`，把部署光盘挂载到虚拟机。
7. 在虚拟机中运行部署光盘里的安装入口，然后登录助手微信并启动连接器。
8. 在工作台确认“已连接”，分别测试私聊 `/help` 和群聊 `@贾维斯 /status`。

## 地址自动发现

主机工作台启动时精确读取 `vEthernet (Default Switch)` 的唯一私有 IPv4 地址。虚拟机连接器启动时读取与来宾地址位于同一子网的唯一私有默认网关，并将它作为主机桥地址。两端继续要求固定端口 8791 和 256 位随机 Bearer 密钥。

首次部署自动发现组件后，Hyper-V Default Switch 在普通重启后更换地址，不再需要重新制作地址同步光盘。地址缺失、不是私网、跨子网或出现多个候选时，连接器会拒绝启动。

## 运行要求

- 虚拟机必须保持运行。
- 来宾用户桌面必须保持登录和解锁。
- 可以关闭 Hyper-V 连接窗口；不要关闭虚拟机或退出微信。
- 工作台暂停监听后可以操作虚拟机其他窗口，恢复监听后再接收新消息。

## 安全边界

- 管理页面只绑定本机回环地址。
- 虚拟机桥只接受通过随机密钥认证的请求。
- 防火墙规则限定 Node.js、TCP 8791 和本地子网。
- 来宾不复制主机的聊天数据库、Codex 凭据、Muse Cookie 或私人项目。
- `workbench/data/`、`vm/media/`、`vm/machines/`、`vm-agent.json` 和 `vm-relay.json` 都不得提交 Git。

本项目依赖桌面 UI 自动化，微信客户端更新可能改变控件结构。请先在专用账号和隔离虚拟机中验证，并遵守相关平台条款。
