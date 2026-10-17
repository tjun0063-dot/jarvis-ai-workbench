$ErrorActionPreference='Stop'
$taskComputer=Get-CimInstance Win32_ComputerSystem
if ($taskComputer.Model -ne 'Virtual Machine' -or $taskComputer.Manufacturer -notlike '*Microsoft*') { throw '此安装脚本只能在 Hyper-V 虚拟机内运行' }
$taskMedia=[IO.Path]::GetFullPath($PSScriptRoot)
$taskDestination='C:\Jarvis'
if (Test-Path -LiteralPath $taskDestination) { throw 'C:\Jarvis 已存在，未覆盖；保留原配置和客户端' }
$taskManifest=Get-Content -LiteralPath (Join-Path $taskMedia 'payload-manifest.json') -Raw | ConvertFrom-Json
foreach ($taskFile in $taskManifest.files) {
    $taskFull=[IO.Path]::GetFullPath((Join-Path $taskMedia $taskFile.path))
    if (-not $taskFull.StartsWith($taskMedia.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw '部署路径越界' }
    if ((Get-FileHash -LiteralPath $taskFull -Algorithm SHA256).Hash -ne $taskFile.sha256) { throw '部署文件核验失败' }
}
New-Item -ItemType Directory -Path $taskDestination | Out-Null
foreach ($taskItem in Get-ChildItem -LiteralPath $taskMedia -Force) { Copy-Item -LiteralPath $taskItem.FullName -Destination $taskDestination -Recurse }
$taskInstaller=Join-Path $taskDestination 'python-installer.exe'
$taskSignature=Get-AuthenticodeSignature -LiteralPath $taskInstaller
if ($taskSignature.Status -ne 'Valid' -or $taskSignature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Python 官方签名未通过，未运行' }
$taskProcess=Start-Process -FilePath $taskInstaller -ArgumentList '/quiet','InstallAllUsers=0','PrependPath=0','Include_launcher=0','Include_test=0',('TargetDir='+$taskDestination+'\python') -WindowStyle Hidden -Wait -PassThru
if ($taskProcess.ExitCode -notin 0,3010) { throw '虚拟机 Python 安装失败' }
$taskPython=Join-Path $taskDestination 'python/python.exe'
& $taskPython -m venv (Join-Path $taskDestination 'workbench/.wechat-venv')
if ($LASTEXITCODE -ne 0) { throw '隔离环境创建失败' }
& (Join-Path $taskDestination 'workbench/.wechat-venv/Scripts/python.exe') -m pip install --no-index --find-links (Join-Path $taskDestination 'wheels') -r (Join-Path $taskDestination 'workbench/requirements-wechat.txt')
if ($LASTEXITCODE -ne 0) { throw '离线微信连接器安装失败' }
Write-Output '安装完成。打开 C:\Jarvis\Open-WeChat.cmd，扫码登录贾维斯；再运行 C:\Jarvis\Start-Agent.cmd。'
Write-Output '登录与手机确认由你完成。请在虚拟机内部保持账号登录、桌面解锁。'
