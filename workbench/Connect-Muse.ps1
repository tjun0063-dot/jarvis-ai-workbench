param([switch]$RetryApproved)
$ErrorActionPreference = 'Stop'
try {
    Write-Host 'Connect the muse.ai personal agent (not Muse Code).'
    Write-Host 'This reads only muse.ai cookies from your open Chrome and saves them locally.'
    Write-Host 'It uses Vercel agent-browser once to transfer the session to the local muse-cli adapter.'
    Write-Host 'The workbench can then read Muse chats/goals and send instructions using your account.'
    Write-Host 'No cookie values are displayed or sent to a third-party relay.'
    Write-Host 'Chrome remote debugging temporarily gives the local connector access to the browser.'
    Write-Host '1. In Chrome open chrome://inspect/#remote-debugging and enable remote debugging.'
    Write-Host '2. Keep your logged-in https://muse.ai/ tab open.'
    Write-Host '3. Allow the Chrome connection prompt when it appears.'
    if (-not $RetryApproved) {
        $taskApproval = Read-Host 'Type YES to approve this one-time session transfer, or Enter to cancel'
        if ($taskApproval -cne 'YES') { Write-Host 'Cancelled.'; exit 0 }
    } else {
        Write-Host 'Retrying the same session transfer you already approved. No second YES is needed.'
    }
    $taskPrivate = Join-Path $PSScriptRoot 'data\muse-personal'
    [void](New-Item -Path $taskPrivate -ItemType Directory -Force)
    if ((Get-Item -LiteralPath $taskPrivate).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Private directory cannot be a junction.' }
    $taskSid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $taskAcl = New-Object Security.AccessControl.DirectorySecurity
    $taskAcl.SetAccessRuleProtection($true,$false)
    $taskAcl.SetOwner($taskSid)
    $taskAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($taskSid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    $taskAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-18'),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    Set-Acl -LiteralPath $taskPrivate -AclObject $taskAcl
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    & (Join-Path $PSScriptRoot '.muse-venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'connect_personal_muse.py')
    if ($LASTEXITCODE -ne 0) { throw 'Muse connection was not completed. The previous login was not replaced.' }
    Write-Host 'You may now turn OFF Chrome remote debugging; later Muse requests use the saved login.'
} catch { Write-Host $_ -ForegroundColor Red }
Read-Host 'Press Enter to close'
