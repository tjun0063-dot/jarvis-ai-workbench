$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
try {
    $taskExecutable = Join-Path $taskRoot 'tools\muse\muse.exe'
    if (-not (Test-Path -LiteralPath $taskExecutable)) { throw 'Muse Code is not installed.' }
    $taskSignature = Get-AuthenticodeSignature -LiteralPath $taskExecutable
    if ($taskSignature.Status -ne 'Valid' -or $taskSignature.SignerCertificate.Subject -notmatch 'Meta Platforms') { throw 'Muse Code publisher signature is invalid.' }
    $taskNetwork = Join-Path $taskRoot 'data\codex-network.json'
    if (Test-Path -LiteralPath $taskNetwork) {
        $taskProxy = (Get-Content -LiteralPath $taskNetwork -Raw | ConvertFrom-Json).proxy
        if ($taskProxy) {
            $taskUri = [Uri]$taskProxy
            if ($taskUri.Scheme -ne 'http' -or $taskUri.Host -notin @('127.0.0.1','localhost','[::1]') -or $taskUri.UserInfo -or $taskUri.AbsolutePath -ne '/' -or $taskUri.Query -or $taskUri.Fragment) { throw 'Expected a local HTTP proxy.' }
            $env:HTTPS_PROXY = $taskProxy
            $env:HTTP_PROXY = $taskProxy
            $env:ALL_PROXY = $taskProxy
            $env:NO_PROXY = 'localhost,127.0.0.1,::1'
        }
    }
    $env:META_API_KEY = $null
    $env:MODEL_API_KEY = $null
    Write-Host 'Complete Meta account approval in the official browser page.'
    Write-Host 'If a paid plan is required, choose it yourself; this script does not enroll you.'
    & $taskExecutable login
    if ($LASTEXITCODE -ne 0) { throw "Muse login exited with code $LASTEXITCODE" }
    Write-Host 'Login command completed. Return to the workbench and test a Muse conversation.'
} catch { Write-Host $_ -ForegroundColor Red }
Read-Host 'Press Enter to close'
