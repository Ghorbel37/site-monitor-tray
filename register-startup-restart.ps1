$exePath  = Resolve-Path -Path (Join-Path $PSScriptRoot "dist\site_notifier.exe")
$arguments = '--url https://localhost:8443 --name "Local server" --interval 5'
$taskName  = "SiteNotifier"

$action  = New-ScheduledTaskAction -Execute $exePath -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName   $taskName `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -RunLevel   Highest `
    -Force

Write-Host "Task '$taskName' registered. It will run at every logon."
