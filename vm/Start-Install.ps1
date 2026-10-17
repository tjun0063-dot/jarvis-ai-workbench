$ErrorActionPreference='Stop'
Import-Module Hyper-V
$taskRecord=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'vm.json') -Raw | ConvertFrom-Json
$taskVm=Get-VM -Id $taskRecord.id
if ($taskVm.Name -ne 'Jarvis-WeChat') { throw '虚拟机身份不匹配，未启动' }
Start-VM -VM $taskVm
Write-Output '虚拟机已启动。请在 Hyper-V 管理器连接 Jarvis-WeChat，安装系统并完成初始登录。'
