[CmdletBinding(SupportsShouldProcess)]
param([switch]$Restore)
$ErrorActionPreference='Stop'
$taskRecordPath=Join-Path $PSScriptRoot 'relay-firewall-before.json'
if ($Restore) {
    $taskRecord=Get-Content -LiteralPath $taskRecordPath -Raw | ConvertFrom-Json
    if ($PSCmdlet.ShouldProcess('Jarvis relay firewall snapshot','Restore original TCP port filter and relay program scope')) {
        Get-NetFirewallRule -Name $taskRecord.blockName | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -LocalPort $taskRecord.blockPorts | Out-Null
        Set-NetFirewallRule -Name 'Jarvis-VM-Relay' -Program $taskRecord.allowProgram | Out-Null
        Write-Output '已恢复桥接修复前的防火墙端口和程序范围。'
    }
    exit
}
$taskConfig=Get-Content -LiteralPath (Join-Path $PSScriptRoot '../workbench/data/vm-relay.json') -Raw | ConvertFrom-Json
$taskVmRecord=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'vm.json') -Raw | ConvertFrom-Json
$taskVm=Get-VM -Id $taskVmRecord.id
if ($taskVm.Name -ne 'Jarvis-WeChat') { throw '虚拟机身份不匹配' }
$taskSwitch=Get-VMSwitch -Name 'Default Switch'
if ($taskSwitch.SwitchType -ne 'Internal') { throw '桥仅允许使用默认内部虚拟交换机' }
$taskAlias='vEthernet (Default Switch)'
$taskIPs=@(Get-NetIPAddress -InterfaceAlias $taskAlias -AddressFamily IPv4 | Where-Object IPAddress -eq $taskConfig.bind)
if ($taskIPs.Count -ne 1) { throw '桥绑定的 IP 已变化，未修改规则' }
$taskListener=Get-NetTCPConnection -State Listen -LocalPort 8791 -LocalAddress $taskConfig.bind
$taskManagement=Get-NetTCPConnection -State Listen -LocalPort 8790 -LocalAddress '127.0.0.1'
if ($taskListener.OwningProcess -ne $taskManagement.OwningProcess) { throw '桥和工作台进程不一致' }
$taskProcess=Get-CimInstance Win32_Process -Filter ('ProcessId='+$taskListener.OwningProcess)
$taskNode=[IO.Path]::GetFullPath($taskProcess.ExecutablePath)
if ($taskNode -ne 'C:\Program Files\nodejs\node.exe' -or $taskProcess.CommandLine -notmatch 'server\.mjs') { throw '监听进程不是已核对的工作台 Node 程序' }
$taskBlocks=@(Get-NetFirewallRule -PolicyStore ActiveStore -Name 'TCP Query User*' | Where-Object {
    $taskApp=$_ | Get-NetFirewallApplicationFilter
    $taskPort=$_ | Get-NetFirewallPortFilter
    $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Block' -and $taskApp.Program -eq $taskNode -and $taskPort.Protocol -eq 'TCP' -and ($taskPort.LocalPort -join ',') -eq 'Any' -and $_.PolicyStoreSourceType -eq 'Local'
})
if ($taskBlocks.Count -ne 1) { throw '未唯一匹配当前 Node 的 TCP 全端口阻断规则，未修改' }
$taskAllow=Get-NetFirewallRule -Name 'Jarvis-VM-Relay'
$taskAllowPort=$taskAllow | Get-NetFirewallPortFilter
$taskAllowInterface=$taskAllow | Get-NetFirewallInterfaceFilter
$taskAllowAddress=$taskAllow | Get-NetFirewallAddressFilter
if ($taskAllowPort.Protocol -ne 'TCP' -or ($taskAllowPort.LocalPort -join ',') -ne '8791' -or ($taskAllowInterface.InterfaceAlias -join ',') -ne $taskAlias -or ($taskAllowAddress.LocalAddress -join ',') -ne $taskConfig.bind) { throw '原桥接允许范围不符合预期，未修改' }
$taskRecord=@{blockName=$taskBlocks[0].Name;blockPorts=@(($taskBlocks[0] | Get-NetFirewallPortFilter).LocalPort);allowProgram=($taskAllow | Get-NetFirewallApplicationFilter).Program;node=$taskNode;bind=$taskConfig.bind;port=8791}
if (Test-Path -LiteralPath $taskRecordPath) {
    $taskOriginal=Get-Content -LiteralPath $taskRecordPath -Raw | ConvertFrom-Json
    if ($taskOriginal.blockName -ne $taskRecord.blockName -or ($taskOriginal.blockPorts -join ',') -ne ($taskRecord.blockPorts -join ',') -or $taskOriginal.allowProgram -ne $taskRecord.allowProgram -or $taskOriginal.node -ne $taskNode -or $taskOriginal.bind -ne $taskConfig.bind) { throw '已有原规则备份与当前规则不一致，未修改' }
    $taskRecord=$taskOriginal
}
if ($PSCmdlet.ShouldProcess('Current Node TCP block rule + Jarvis-VM-Relay','Exclude only TCP 8791 from the block and narrow the allow rule to this program on the VM subnet')) {
    if (-not (Test-Path -LiteralPath $taskRecordPath)) { $taskRecord | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $taskRecordPath -Encoding UTF8 }
    try {
        Set-NetFirewallRule -Name 'Jarvis-VM-Relay' -Program $taskNode -RemoteAddress ($taskConfig.bind+'/'+$taskIPs[0].PrefixLength) | Out-Null
        Get-NetFirewallRule -Name $taskBlocks[0].Name | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -LocalPort @('1-8790','8792-65535') | Out-Null
        $taskVerify=Get-NetFirewallRule -Name $taskBlocks[0].Name | Get-NetFirewallPortFilter
        if (($taskVerify.LocalPort -join ',') -ne '1-8790,8792-65535') { throw 'TCP 端口例外核验未通过' }
    } catch {
        Get-NetFirewallRule -Name $taskRecord.blockName | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -LocalPort $taskRecord.blockPorts | Out-Null
        Set-NetFirewallRule -Name 'Jarvis-VM-Relay' -Program $taskRecord.allowProgram | Out-Null
        throw
    }
    Write-Output '已保存原规则并修复 TCP 8791 例外；允许规则限定为工作台程序、虚拟网卡与虚拟机网段。'
}
