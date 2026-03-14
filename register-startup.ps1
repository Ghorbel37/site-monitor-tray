$exePath  = Resolve-Path -Path (Join-Path $PSScriptRoot "dist\site_notifier.exe")
$arguments = '--url https://localhost:8443 --name "Local server" --interval 5'
$taskName  = "SiteNotifier"

# Use cmd /c start so Task Scheduler spawns the exe detached and exits immediately.
# Task Scheduler only tracks the short-lived cmd process; the exe runs freely on its own.
$action  = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c start `"`" `"$exePath`" $arguments"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask `
    -TaskName   $taskName `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -RunLevel   Highest `
    -Force

Write-Host "Task '$taskName' registered. It will run at every logon."
