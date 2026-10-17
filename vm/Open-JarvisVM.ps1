param([switch]$AdminRetry)
$ErrorActionPreference='Stop'
try {
    $taskIdentity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $taskPrincipal=[Security.Principal.WindowsPrincipal]::new($taskIdentity)
    if (-not $taskPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        if ($AdminRetry) { throw 'Hyper-V 启动需要管理员权限，请允许 Windows 的权限提示。' }
        $taskPowerShell=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
        Start-Process -FilePath $taskPowerShell -ArgumentList @('-NoProfile','-ExecutionPolicy','RemoteSigned','-WindowStyle','Hidden','-File',('"'+$PSCommandPath+'"'),'-AdminRetry') -Verb RunAs -WindowStyle Hidden
        exit 0
    }
    Import-Module Hyper-V
    $taskRecord=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'vm.json') -Raw | ConvertFrom-Json
    if ($taskRecord.id -ne '3a7ba255-bbce-4edf-aa76-954fbee3150d' -or $taskRecord.name -ne 'Jarvis-WeChat') { throw '贾维斯虚拟机记录不匹配。' }
    $taskVm=Get-VM -Id $taskRecord.id
    if ($taskVm.Name -ne 'Jarvis-WeChat') { throw '虚拟机身份不匹配。' }
    if ($taskVm.State -eq 'Off' -or $taskVm.State -eq 'Saved') { Start-VM -VM $taskVm }
    elseif ($taskVm.State -eq 'Paused') { Resume-VM -VM $taskVm }
    elseif ($taskVm.State -ne 'Running') { throw ('虚拟机正在转换状态：'+$taskVm.State+'。请稍后再试。') }
    # This is the interactive console the user explicitly requested to see.
    Start-Process -FilePath (Join-Path $env:SystemRoot 'System32/vmconnect.exe') -ArgumentList @('localhost','Jarvis-WeChat')
} catch {
    $taskLog=Join-Path $PSScriptRoot 'VM-launch-error.txt'
    $_.Exception.Message | Set-Content -LiteralPath $taskLog -Encoding utf8
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show(('启动失败：'+$_.Exception.Message+"`n记录："+$taskLog),'贾维斯虚拟机') | Out-Null
    exit 1
}
