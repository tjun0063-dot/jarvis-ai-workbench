$ErrorActionPreference='Stop'
Import-Module Hyper-V
$taskRoot=[IO.Path]::GetFullPath($PSScriptRoot)
$taskConfigPath=[IO.Path]::GetFullPath((Join-Path $taskRoot '../workbench/data/vm-relay.json'))
$taskConfig=Get-Content -LiteralPath $taskConfigPath -Raw | ConvertFrom-Json
$taskVm=Get-VM -Id $taskConfig.vmId
if($taskVm.Name -ne 'Jarvis-WeChat'){throw '虚拟机身份不匹配'}
if((Get-VMSwitch -Name 'Default Switch').SwitchType -ne 'Internal'){throw '交换机范围不正确'}
$taskIp=@(Get-NetIPAddress -InterfaceAlias 'vEthernet (Default Switch)' -AddressFamily IPv4 | Where-Object IPAddress -notlike '169.254.*')
if($taskIp.Count -ne 1){throw '虚拟地址不唯一'}
$taskRule=Get-NetFirewallRule -Name 'Jarvis-VM-Relay'
$taskPort=$taskRule | Get-NetFirewallPortFilter
$taskApp=$taskRule | Get-NetFirewallApplicationFilter
$taskNode=[IO.Path]::GetFullPath((Get-Command node -ErrorAction Stop).Source)
if(($taskPort.LocalPort -join ',') -ne '8791' -or $taskPort.Protocol -ne 'TCP' -or [IO.Path]::GetFullPath($taskApp.Program) -ne $taskNode){throw '原防火墙规则范围不匹配'}
Set-NetFirewallRule -Name 'Jarvis-VM-Relay' -Enabled True -Direction Inbound -Action Allow -Profile Any -InterfaceAlias Any -LocalAddress Any -RemoteAddress LocalSubnet -Program $taskNode | Out-Null
$taskConfig.bind=$taskIp[0].IPAddress
$taskConfig | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskConfigPath -Encoding utf8
$taskAddress=Get-NetFirewallRule -Name 'Jarvis-VM-Relay' | Get-NetFirewallAddressFilter
$taskInterface=Get-NetFirewallRule -Name 'Jarvis-VM-Relay' | Get-NetFirewallInterfaceFilter
if(($taskAddress.LocalAddress -join ',') -ne 'Any' -or ($taskAddress.RemoteAddress -join ',') -ne 'LocalSubnet' -or ($taskInterface.InterfaceAlias -join ',') -ne 'Any'){throw '自动发现防火墙规则回读失败'}
Write-Output ('自动桥接已启用；当前地址 '+$taskConfig.bind+':8791。以后重启由工作台和虚拟机自动发现。')
