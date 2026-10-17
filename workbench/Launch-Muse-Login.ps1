$ErrorActionPreference = 'Stop'
$taskBundledShell = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
$taskShell = if (Test-Path -LiteralPath $taskBundledShell) { $taskBundledShell } else { Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe' }
$taskLogin = Join-Path $PSScriptRoot 'Open-Muse-Login.ps1'
Start-Process -FilePath $taskShell -ArgumentList @('-NoProfile','-File',('"' + $taskLogin + '"')) -WindowStyle Normal | Out-Null
