[CmdletBinding(SupportsShouldProcess)]
param([string]$IsoPath=(Join-Path $PSScriptRoot 'media/Windows11-LTSC-Eval-zh-CN.iso'))
$ErrorActionPreference='Stop'
Import-Module Hyper-V
$taskName='Jarvis-WeChat'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'machines'))
$taskVmPath=Join-Path $taskRoot $taskName
$taskIso=[IO.Path]::GetFullPath($IsoPath)
if (-not (Test-Path -LiteralPath $taskIso -PathType Leaf)) { throw 'Windows ISO 尚未下载完成' }
$taskRecord=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'media/download.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $taskIso -Algorithm SHA256).Hash -ne $taskRecord.sha256) { throw 'ISO 与已核验下载记录不一致' }
if (Get-VM -Name $taskName -ErrorAction SilentlyContinue) { throw '同名虚拟机已经存在，未覆盖' }
if (Test-Path -LiteralPath $taskVmPath) { throw '目标虚拟机目录已存在，未覆盖' }
$taskSwitch=Get-VMSwitch -Name 'Default Switch' -ErrorAction SilentlyContinue
if (-not $taskSwitch -or $taskSwitch.SwitchType -ne 'Internal') { throw 'Hyper-V Default Switch 尚未就绪；请先重启，不会桥接物理网卡' }
if ($PSCmdlet.ShouldProcess($taskVmPath,'创建 Jarvis-WeChat：2 核、4 GB 内存、64 GB 动态虚拟硬盘，挂载 Windows ISO')) {
    New-Item -ItemType Directory -Path $taskVmPath -Force | Out-Null
    $taskVm=New-VM -Name $taskName -Generation 2 -MemoryStartupBytes 4GB -NewVHDPath (Join-Path $taskVmPath 'system.vhdx') -NewVHDSizeBytes 64GB -Path $taskVmPath -SwitchName $taskSwitch.Name
    Set-VMProcessor -VMName $taskName -Count 2
    Set-VMMemory -VMName $taskName -DynamicMemoryEnabled $true -MinimumBytes 2GB -StartupBytes 4GB -MaximumBytes 4GB
    Set-VM -Name $taskName -AutomaticStartAction Nothing -AutomaticStopAction Save
    Set-VMFirmware -VMName $taskName -EnableSecureBoot On -SecureBootTemplate MicrosoftWindows
    Set-VMKeyProtector -VMName $taskName -NewLocalKeyProtector
    Enable-VMTPM -VMName $taskName
    Add-VMDvdDrive -VMName $taskName -Path $taskIso
    $taskDvd=Get-VMDvdDrive -VMName $taskName
    Set-VMFirmware -VMName $taskName -FirstBootDevice $taskDvd
    @{name=$taskName;id=$taskVm.Id.ToString();directory=$taskVmPath;iso=$taskIso} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'vm.json') -Encoding UTF8
    Write-Output '已创建，尚未启动。安装系统时请只操作虚拟机里的 64 GB 虚拟磁盘。'
}
