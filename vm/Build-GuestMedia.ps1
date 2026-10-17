param([switch]$RefreshConfig,[string]$OutputName='Jarvis-Setup-v2.iso')
$ErrorActionPreference='Stop'
if ($OutputName -notmatch '^Jarvis-Setup(?:-[a-zA-Z0-9-]+)?\.iso$') { throw '部署光盘文件名无效' }
$taskRoot=[IO.Path]::GetFullPath($PSScriptRoot)
$taskStage=Join-Path $taskRoot 'payload'
if ((Test-Path -LiteralPath $taskStage) -and -not $RefreshConfig) { throw '已有部署目录，未覆盖；配置桥接后可用 -RefreshConfig 重新生成部署光盘' }
$taskOutputs=Split-Path $taskRoot -Parent
$taskSourceClient=Join-Path $taskOutputs 'wechat-assistant-4.1.8.107'
$taskManifest=Get-Content -LiteralPath (Join-Path $taskSourceClient 'preparation.json') -Raw | ConvertFrom-Json
foreach ($taskFile in $taskManifest.launchFiles) {
    if ((Get-FileHash -LiteralPath (Join-Path $taskSourceClient ('client/'+$taskFile.path)) -Algorithm SHA256).Hash -ne $taskFile.sha256) { throw '微信兼容客户端已变化，未打包' }
}
if (-not $RefreshConfig) {
New-Item -ItemType Directory -Path (Join-Path $taskStage 'workbench'),(Join-Path $taskStage 'wechat-assistant-4.1.8.107') -Force | Out-Null
foreach ($taskGuestFile in Get-ChildItem -LiteralPath (Join-Path $taskRoot 'guest') -File) { Copy-Item -LiteralPath $taskGuestFile.FullName -Destination $taskStage }
Copy-Item -LiteralPath (Join-Path $taskRoot 'media/python-3.12.10-amd64.exe') -Destination (Join-Path $taskStage 'python-installer.exe')
$taskPowerShell=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell'
Copy-Item -LiteralPath $taskPowerShell -Destination (Join-Path $taskStage 'powershell') -Recurse
Copy-Item -LiteralPath (Join-Path $taskRoot 'wheels') -Destination (Join-Path $taskStage 'wheels') -Recurse
foreach ($taskFile in @('wechat_assistant.py','vm_agent.py','requirements-wechat.txt')) {
    Copy-Item -LiteralPath (Join-Path $taskOutputs ('workbench/'+$taskFile)) -Destination (Join-Path $taskStage 'workbench')
}
foreach ($taskFile in @('client','preparation.json','Launch-Assistant.ps1')) {
    Copy-Item -LiteralPath (Join-Path $taskSourceClient $taskFile) -Destination (Join-Path $taskStage 'wechat-assistant-4.1.8.107') -Recurse
}
} elseif (-not (Test-Path -LiteralPath (Join-Path $taskStage 'payload-manifest.json'))) { throw '不存在完整的原部署目录，不能刷新配置' }
foreach ($taskGuestFile in Get-ChildItem -LiteralPath (Join-Path $taskRoot 'guest') -File) { Copy-Item -LiteralPath $taskGuestFile.FullName -Destination $taskStage -Force }
$taskBootstrapZip=Join-Path $taskRoot 'media/python-3.12.10-embed-amd64.zip'
if ((Get-FileHash -LiteralPath $taskBootstrapZip -Algorithm SHA256).Hash -ne '4ACBED6DD1C744B0376E3B1CF57CE906F9DC9E95E68824584C8099A63025A3C3') { throw 'Python 官方便携运行时与已核验下载不一致' }
$taskBootstrap=Join-Path $taskStage 'bootstrap-python'
if (-not (Test-Path -LiteralPath $taskBootstrap)) { Expand-Archive -LiteralPath $taskBootstrapZip -DestinationPath $taskBootstrap }
$taskBootstrapSignature=Get-AuthenticodeSignature -LiteralPath (Join-Path $taskBootstrap 'python.exe')
if ($taskBootstrapSignature.Status -ne 'Valid' -or $taskBootstrapSignature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Python 便携运行时官方签名未通过' }
foreach ($taskFile in @('wechat_assistant.py','vm_agent.py','requirements-wechat.txt')) { Copy-Item -LiteralPath (Join-Path $taskOutputs ('workbench/'+$taskFile)) -Destination (Join-Path $taskStage 'workbench') -Force }
$taskVcFile=Join-Path $taskRoot 'media/vc_redist.x64.exe'
$taskVcRecord=Get-Content -LiteralPath (Join-Path $taskRoot 'media/vc-redist.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $taskVcFile -Algorithm SHA256).Hash -ne $taskVcRecord.sha256) { throw 'Microsoft 运行库下载记录与文件不一致' }
$taskVcSignature=Get-AuthenticodeSignature -LiteralPath $taskVcFile
if ($taskVcSignature.Status -ne 'Valid' -or $taskVcSignature.SignerCertificate.Subject -notmatch 'CN=Microsoft Corporation(?:,|$)') { throw 'Microsoft 运行库官方签名核验未通过' }
Copy-Item -LiteralPath $taskVcFile -Destination (Join-Path $taskStage 'vc_redist.x64.exe') -Force
if (Test-Path -LiteralPath (Join-Path $taskRoot 'vm-agent.json')) {
    Copy-Item -LiteralPath (Join-Path $taskRoot 'vm-agent.json') -Destination (Join-Path $taskStage 'workbench/vm-agent.json')
} else { Write-Output '桥接尚未配置：此光盘可安装依赖，但连接器须先获得 Configure-HostRelay.ps1 生成的配置。' }
$taskFiles=@(Get-ChildItem -LiteralPath $taskStage -File -Recurse | Where-Object { $_.Name -ne 'payload-manifest.json' } | ForEach-Object { @{path=[IO.Path]::GetRelativePath($taskStage,$_.FullName);sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash} })
@{files=$taskFiles} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskStage 'payload-manifest.json') -Encoding UTF8
$env:PYTHONUTF8='1'
& (Join-Path $taskOutputs 'workbench/.wechat-venv/Scripts/python.exe') (Join-Path $taskRoot 'build_iso.py') $taskStage (Join-Path $taskRoot ('media/'+$OutputName))
if ($LASTEXITCODE -ne 0) { throw '部署光盘打包失败' }
