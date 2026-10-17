param([string]$SetupIsoPath=(Join-Path $PSScriptRoot 'media/Jarvis-Setup-v2.iso'))
$ErrorActionPreference='Stop'
Import-Module Hyper-V
$taskRecord=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'vm.json') -Raw | ConvertFrom-Json
$taskVm=Get-VM -Id $taskRecord.id
if ($taskVm.Name -ne 'Jarvis-WeChat') { throw '虚拟机身份不匹配' }
$taskSetup=[IO.Path]::GetFullPath($SetupIsoPath)
if (-not (Test-Path -LiteralPath $taskSetup)) { throw '部署光盘尚未生成' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'vm-agent.json'))) { throw '通信桥配置尚未完成' }
$taskDrives=@(Get-VMDvdDrive -VM $taskVm)
if (-not ($taskDrives | Where-Object Path -eq $taskSetup)) {
    $taskOld=@($taskDrives | Where-Object { $_.Path -and [IO.Path]::GetDirectoryName($_.Path) -eq (Join-Path $PSScriptRoot 'media') -and [IO.Path]::GetFileName($_.Path) -match '^Jarvis-Setup(?:-[a-zA-Z0-9-]+)?\.iso$' })
    if ($taskOld.Count -gt 1) { throw '存在多张部署光盘，未自动更换' }
    if ($taskOld.Count -eq 1) { Set-VMDvdDrive -VMDvdDrive $taskOld[0] -Path $taskSetup }
    else { Add-VMDvdDrive -VM $taskVm -Path $taskSetup }
}
Write-Output '部署光盘已挂载。请在虚拟机内刷新光盘文件夹，按工作台指示选择安装或更新入口。'

