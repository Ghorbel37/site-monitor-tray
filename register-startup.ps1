# Registers a "SiteNotifier" task that starts the tray app at every logon.
# Run once in an elevated PowerShell. Sites are read from the config file
# (sites.toml next to the exe, else %APPDATA%\SiteMonitorTray\sites.toml).
param(
    [string]$ExePath,
    [string]$ConfigPath
)

if (-not $ExePath) {
    $candidates = @(
        (Join-Path $PSScriptRoot "site_notifier.exe"),
        (Join-Path $PSScriptRoot "dist\site_notifier.exe")
    )
    $ExePath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $ExePath) { throw "site_notifier.exe not found next to this script or in dist\. Pass -ExePath." }
}
$exePath   = (Resolve-Path $ExePath).Path
$arguments = if ($ConfigPath) { "--config `"$((Resolve-Path $ConfigPath).Path)`"" } else { "" }
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
