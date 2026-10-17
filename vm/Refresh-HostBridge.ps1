$ErrorActionPreference='Stop'
Import-Module Hyper-V
$taskRoot=[IO.Path]::GetFullPath($PSScriptRoot)
$taskDir=[IO.Path]::GetFullPath((Join-Path $taskRoot '../workbench'))
$taskConfigPath=Join-Path $taskDir 'data/vm-relay.json'
$taskGuestPath=Join-Path $taskRoot 'vm-agent.json'
$taskConfig=Get-Content -LiteralPath $taskConfigPath -Raw | ConvertFrom-Json
$taskGuest=Get-Content -LiteralPath $taskGuestPath -Raw | ConvertFrom-Json
if($taskConfig.vmId -ne '3a7ba255-bbce-4edf-aa76-954fbee3150d' -or (Get-VM -Id $taskConfig.vmId).Name -ne 'Jarvis-WeChat'){throw '虚拟机身份不匹配'}
if((Get-VMSwitch -Name 'Default Switch').SwitchType -ne 'Internal'){throw '交换机范围不正确'}
$taskIp=@(Get-NetIPAddress -InterfaceAlias 'vEthernet (Default Switch)' -AddressFamily IPv4 | Where-Object IPAddress -notlike '169.254.*')
if($taskIp.Count -ne 1){throw '虚拟地址不唯一'}
$taskNewBind=$taskIp[0].IPAddress
$taskRule=Get-NetFirewallRule -Name 'Jarvis-VM-Relay'
$taskPort=$taskRule | Get-NetFirewallPortFilter
$taskAddress=$taskRule | Get-NetFirewallAddressFilter
$taskInterface=$taskRule | Get-NetFirewallInterfaceFilter
$taskApp=$taskRule | Get-NetFirewallApplicationFilter
if(($taskPort.LocalPort -join ',') -ne '8791' -or $taskPort.Protocol -ne 'TCP' -or ($taskAddress.LocalAddress -join ',') -ne $taskConfig.bind -or $taskApp.Program -ne 'C:\Program Files\nodejs\node.exe'){throw '原防火墙范围不匹配'}
if($taskConfig.token -ne $taskGuest.token){throw '配置密钥不匹配'}
if($taskConfig.bind -ne $taskNewBind){
    if(Get-NetTCPConnection -LocalPort 8790,8791 -State Listen -ErrorAction SilentlyContinue){throw '地址变化但服务仍运行，请先停止工作台再同步。'}
    $taskStamp=[guid]::NewGuid().ToString('N').Substring(0,12)
    $taskConfigBackup=$taskConfigPath+'.before-address-'+$taskStamp
    $taskGuestBackup=$taskGuestPath+'.before-address-'+$taskStamp
    Copy-Item -LiteralPath $taskConfigPath -Destination $taskConfigBackup
    Copy-Item -LiteralPath $taskGuestPath -Destination $taskGuestBackup
    @{local=@($taskAddress.LocalAddress);remote=@($taskAddress.RemoteAddress);interface=@($taskInterface.InterfaceAlias)} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $taskRoot ('relay-address-before-'+$taskStamp+'.json')) -Encoding utf8
    try {
        Set-NetFirewallRule -Name 'Jarvis-VM-Relay' -InterfaceAlias 'vEthernet (Default Switch)' -LocalAddress $taskNewBind -RemoteAddress ($taskNewBind+'/'+$taskIp[0].PrefixLength) | Out-Null
        $taskConfig.bind=$taskNewBind
        $taskGuest.relay='http://'+$taskNewBind+':8791'
        $taskConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskConfigPath -Encoding utf8
        $taskGuest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskGuestPath -Encoding utf8
    } catch {
        Set-NetFirewallRule -Name 'Jarvis-VM-Relay' -LocalAddress @($taskAddress.LocalAddress) -RemoteAddress @($taskAddress.RemoteAddress) -InterfaceAlias @($taskInterface.InterfaceAlias) | Out-Null
        Copy-Item -LiteralPath $taskConfigBackup -Destination $taskConfigPath -Force
        Copy-Item -LiteralPath $taskGuestBackup -Destination $taskGuestPath -Force
        throw
    }
}
if(-not (Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue)){
    $taskNode=Start-Process -FilePath 'C:\Program Files\nodejs\node.exe' -ArgumentList @('server.mjs') -WorkingDirectory $taskDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskDir 'data/server-stdout.log') -RedirectStandardError (Join-Path $taskDir 'data/server-stderr.log')
    Write-Output ('工作台启动进程：'+$taskNode.Id)
}
Write-Output ('通信桥绑定：'+$taskNewBind+':8791；来宾配置需从本次光盘同步。')
