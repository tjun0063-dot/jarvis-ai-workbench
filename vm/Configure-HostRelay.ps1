[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference='Stop'
Import-Module Hyper-V
$taskVm=Get-VM -Name 'Jarvis-WeChat'
$taskSwitch=Get-VMSwitch -Name 'Default Switch'
if ($taskSwitch.SwitchType -ne 'Internal') { throw '仅允许 Hyper-V 默认内部网络' }
$taskAlias='vEthernet ('+$taskSwitch.Name+')'
$taskIPs=@(Get-NetIPAddress -InterfaceAlias $taskAlias -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' })
if ($taskIPs.Count -ne 1) { throw '不能唯一确定虚拟网络地址，未配置桥接' }
$taskIP=$taskIPs[0]
$taskWorkbench=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../workbench'))
$taskConfig=Join-Path $taskWorkbench 'data/vm-relay.json'
if (Test-Path -LiteralPath $taskConfig) { throw '桥接配置已存在，未覆盖密钥；若虚拟网络地址变化需更新部署配置' }
if ($PSCmdlet.ShouldProcess($taskAlias,'仅在虚拟网络地址配置微信桥，并添加限定接口的 TCP 8791 入站规则')) {
    $taskBytes=[byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($taskBytes)
    $taskToken=[Convert]::ToHexString($taskBytes).ToLowerInvariant()
    @{enabled=$true;bind=$taskIP.IPAddress;token=$taskToken;vmId=$taskVm.Id.ToString()} | ConvertTo-Json | Set-Content -LiteralPath $taskConfig -Encoding UTF8
    $taskState=Get-Content -LiteralPath (Join-Path $taskWorkbench 'data/state.json') -Raw | ConvertFrom-Json
    $taskChats=@($taskState.contacts.PSObject.Properties.Value | Where-Object { $_.channel -eq 'wechat-account' -and $_.allowed -and $_.chat } | ForEach-Object { @{chat=$_.chat;kind=$_.kind} } | Sort-Object { $_.chat } -Unique)
    @{relay=('http://'+$taskIP.IPAddress+':8791');token=$taskToken;account='贾维斯';listenChats=$taskChats} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'vm-agent.json') -Encoding UTF8
    $taskRule='Jarvis-VM-Relay'
    if (-not (Get-NetFirewallRule -Name $taskRule -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -Name $taskRule -DisplayName 'Jarvis VM relay (Hyper-V only)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8791 -LocalAddress $taskIP.IPAddress -RemoteAddress ($taskIP.IPAddress+'/'+$taskIP.PrefixLength) -InterfaceAlias $taskAlias -Profile Any | Out-Null
    }
    @{account='贾维斯';mode='friends-and-mentions';transport='vm'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskWorkbench 'data/assistant.json') -Encoding UTF8
    Write-Output '已配置虚拟网络桥。重新启动工作台，并运行 Build-GuestMedia.ps1 生成带连接配置的部署光盘。密钥不会显示。'
}
