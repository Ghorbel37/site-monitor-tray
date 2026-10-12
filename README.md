# Site Monitor Tray

[![Build](https://github.com/Ghorbel37/site-monitor-tray/actions/workflows/build.yml/badge.svg)](https://github.com/Ghorbel37/site-monitor-tray/actions/workflows/build.yml)

A lightweight Windows system-tray app that watches one or more websites and notifies you when one goes down or comes back.

![Tray icon states](docs/tray-states.png)

## Features

- Watches any number of sites, each with its own interval, timeout and expected status codes
- One tray icon for all of them: green when everything is up, amber when some are down, red when all are down
- Tray menu lists every site with its last result (`HTTP 200`, `connection failed`, `TLS certificate error`...); click a site to open it in the browser
- Windows notification on every UP and DOWN change
- **Check now**, **Open config** and **Reload config** from the menu, no restart needed
- TLS certificates are verified by default; turn it off per site for local servers with self-signed certificates
- Runs silently in the background (no console window)

## Download

Get `site-monitor-tray-<version>-win64.zip` from the [latest release](https://github.com/Ghorbel37/site-monitor-tray/releases/latest). It holds `site_notifier.exe`, an example config and the two startup scripts. No Python needed.

## Configure

Sites live in a `sites.toml` file. The app looks for it in this order:

1. the path given with `--config`
2. `sites.toml` next to `site_notifier.exe` (or next to `site_notifier.py`)
3. `%APPDATA%\SiteMonitorTray\sites.toml`, created from the example on first start

```toml
[defaults]
interval = 30        # seconds between checks
timeout = 5          # seconds before a request counts as failed
verify_tls = true    # false accepts self-signed certificates

[[site]]
name = "Example"
url = "https://example.com"

[[site]]
name = "Local server"
url = "https://localhost:8443"
interval = 5
verify_tls = false        # local server with a self-signed certificate
expect_status = [200]     # only these HTTP codes count as UP
```

| Key | Default | Meaning |
|---|---|---|
| `name` | the URL | Name shown in the menu and notifications |
| `url` | *(required)* | `http://` or `https://` address to request |
| `interval` | `30` | Seconds between checks |
| `timeout` | `5` | Seconds to wait for an answer |
| `verify_tls` | `true` | Check the HTTPS certificate |
| `expect_status` | `[]` | HTTP codes that count as UP; empty means any code below 400 |

Any key can go in `[defaults]` and be overridden per site. After editing, choose **Reload config** in the tray menu.

## Run from source

Requires Python 3.11+.

```bash
uv pip install -r requirements.txt
uv run site_notifier.py                          # uses sites.toml as described above
uv run site_notifier.py --config C:\path\to\sites.toml
uv run site_notifier.py --url https://example.com --name "Example" --interval 10
uv run site_notifier.py --once                   # check every site once, print, exit
```

| Argument | Description |
|---|---|
| `--config PATH` | Config file to use |
| `--url URL` | Watch only this URL and ignore the config file |
| `--name NAME` | Friendly name for `--url` |
| `--interval SECONDS` | Interval for `--url` (default 30) |
| `--insecure` | For `--url`: accept invalid or self-signed certificates |
| `--once` | Check every site once, print the results and exit (exit code 1 if any is down) |
| `--version` | Print the version |

## Build the exe yourself

```bash
uv pip install pyinstaller==6.19.0
uv run pyinstaller --onefile --noconsole --hidden-import pystray._win32 --icon assets/app.ico --name site_notifier site_notifier.py
```

Output: `dist/site_notifier.exe`. The [Build workflow](.github/workflows/build.yml) does the same on every push and attaches the zip to the release when a `v*` tag is pushed.

The icons are drawn in code. `python tools/make_icons.py` regenerates `assets/app.ico` and `docs/tray-states.png`.

## Start at logon

### Option 1: Startup folder (simplest)

1. Press `Win + R`, type `shell:startup`, hit Enter
2. Create a shortcut to `site_notifier.exe` in that folder

Add `--config "C:\path\to\sites.toml"` to the shortcut's **Target** if the config is not in one of the default places.

### Option 2: Task Scheduler

| Script | Behaviour |
|---|---|
| `register-startup.ps1` | Launches the exe detached via `cmd /c start`. Task Scheduler exits immediately and does **not** track the process. |
| `register-startup-restart.ps1` | Task Scheduler tracks the process and **restarts** it up to 3 times (1 min apart) if it crashes. |

Run the chosen script once in an elevated PowerShell. Both find `site_notifier.exe` next to the script or in `dist\`; pass `-ExePath` or `-ConfigPath` to override.

```powershell
.\register-startup.ps1
.\register-startup-restart.ps1 -ConfigPath "C:\path\to\sites.toml"
```

Both register a task named `SiteNotifier` that launches at every logon with no console window. To remove it:

```powershell
Unregister-ScheduledTask -TaskName "SiteNotifier" -Confirm:$false
```

## Upgrading from 1.0

1.0 took one site on the command line. Those arguments still work (`--url`, `--name`, `--interval`), with three changes: certificates are now checked (add `--insecure` for a self-signed local server), any HTTP code below 400 counts as UP (1.0 wanted exactly 200), and the default interval is 30 seconds. To watch several sites, move them into `sites.toml` and re-run a startup script so the task no longer passes `--url`.

## License

[MIT](LICENSE)
