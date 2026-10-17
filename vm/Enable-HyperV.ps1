[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference='Stop'
$taskIdentity=[Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]::new($taskIdentity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw '请在管理员 PowerShell 中运行此脚本' }
if ($PSCmdlet.ShouldProcess('本机 Hyper-V 可选组件','启用组件，保留当前会话，不自动重启')) {
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All -NoRestart
    Write-Output 'Hyper-V 已启用 / 已请求启用。请保存工作后自行重启，再运行 Create-JarvisVM.ps1。'
}
