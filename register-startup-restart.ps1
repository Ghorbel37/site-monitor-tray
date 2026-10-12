# Registers a "SiteNotifier" task that starts the tray app at every logon
# and restarts it up to 3 times (1 minute apart) if it crashes.
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

$actionArgs = @{ Execute = $exePath }
if ($arguments) { $actionArgs.Argument = $arguments }
$action  = New-ScheduledTaskAction @actionArgs
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
