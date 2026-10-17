$ErrorActionPreference = 'Stop'
$taskBundled = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
$taskShell = if (Test-Path -LiteralPath $taskBundled) { $taskBundled } else { Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe' }
$taskConnect = Join-Path $PSScriptRoot 'Connect-Muse.ps1'
Start-Process -FilePath $taskShell -ArgumentList @('-NoProfile','-File',('"' + $taskConnect + '"')) -WindowStyle Normal | Out-Null
