# Site Notifier

A lightweight Windows system-tray app that monitors a URL and notifies you when it goes up or down.

## Features

- Green/red tray icon reflecting current site status
- Desktop notification + sound on UP and DOWN transitions
- Configurable URL, friendly name, and check interval via CLI args
- Runs silently in the background (no console window)
- Shutdown via tray **Quit** menu

## Requirements

- Windows
- Python 3.11+ (or use the prebuilt `.exe` in `dist/`)

## Install dependencies

```bash
uv pip install -r requirements.txt
```

## Run

```bash
uv run site_notifier.py --url https://localhost:8443 --name "Local server" --interval 5
```

| Argument | Default | Description |
|---|---|---|
| `--url` | `https://127.0.0.1:80` | URL to monitor |
| `--name` | *(URL)* | Friendly name shown in notifications |
| `--interval` | `5` | Check interval in seconds |

## Build standalone exe

```bash
uv pip install pyinstaller
uv run pyinstaller --onefile --noconsole --hidden-import pystray._win32 --name site_notifier site_notifier.py
```

Output: `dist/site_notifier.exe` - no Python installation required on the target machine.

## Auto-start on login

### Option 1 - Startup folder (simplest)

1. Press `Win + R`, type `shell:startup`, hit Enter
2. Create a shortcut to `dist\site_notifier.exe` in that folder
3. Right-click the shortcut → Properties → set **Target** to:
   ```
   C:\path\to\site_notifier.exe --url https://localhost:8443 --name "Local server" --interval 5
   ```

### Option 2 - Task Scheduler (recommended)

Two scripts are provided depending on whether you want crash auto-restart:

| Script | Behaviour |
|---|---|
| `register-startup.ps1` | Launches the exe detached via `cmd /c start`. Task Scheduler exits immediately and does **not** track the process. Simple and lightweight. |
| `register-startup-restart.ps1` | Task Scheduler tracks the process directly and **auto-restarts** it up to 3 times (1 min apart) if it crashes. |

Run the chosen script once in an elevated PowerShell:

```powershell
# Simple launch (no restart on crash)
.\register-startup.ps1

# With auto-restart on crash
.\register-startup-restart.ps1
```

Both register a task named `SiteNotifier` that launches at every logon with no console window.

To remove the task:

```powershell
Unregister-ScheduledTask -TaskName "SiteNotifier" -Confirm:$false
```
