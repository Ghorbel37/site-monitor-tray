"""Site Monitor Tray: watch one or more websites from the Windows notification area."""

import argparse
import os
import subprocess
import sys
import threading
import time
import tomllib
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

import requests
import urllib3
from PIL import Image, ImageDraw
import pystray

__version__ = "1.2.0"

APP_NAME = "Site Monitor"
CONFIG_NAME = "sites.toml"

DEFAULTS = {
    "interval": 30,       # seconds between checks
    "timeout": 5,         # seconds before a request counts as failed
    "verify_tls": True,   # set to false only for self-signed / local certificates
    "expect_status": [],  # empty = any status below 400 counts as UP
}

EXAMPLE_CONFIG = """\
# Site Monitor Tray configuration.
# Edit this file, then choose "Reload config" in the tray menu.

[defaults]
interval = 30        # seconds between checks
timeout = 5          # seconds before a request counts as failed
verify_tls = true    # false accepts self-signed certificates

[[site]]
name = "Example"
url = "https://example.com"

# [[site]]
# name = "Local server"
# url = "https://localhost:8443"
# interval = 5
# verify_tls = false        # local server with a self-signed certificate
# expect_status = [200]     # only these HTTP codes count as UP
"""


# --------------------------------------------------------------------------- config

class ConfigError(Exception):
    pass


@dataclass
class Site:
    name: str
    url: str
    interval: float = DEFAULTS["interval"]
    timeout: float = DEFAULTS["timeout"]
    verify_tls: bool = DEFAULTS["verify_tls"]
    expect_status: list = field(default_factory=list)

    # Runtime state
    up: bool | None = None
    detail: str = "not checked yet"
    since: float | None = None


def _site_from_dict(raw, defaults, index):
    if not isinstance(raw, dict):
        raise ConfigError(f"site #{index} must be a table")
    url = raw.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ConfigError(f"site #{index}: 'url' must start with http:// or https://")
    unknown = set(raw) - {"name", "url", *DEFAULTS}
    if unknown:
        raise ConfigError(f"site #{index}: unknown key(s) {', '.join(sorted(unknown))}")
    merged = {**defaults, **raw}
    site = Site(
        name=str(merged.get("name") or url),
        url=url,
        interval=float(merged["interval"]),
        timeout=float(merged["timeout"]),
        verify_tls=bool(merged["verify_tls"]),
        expect_status=[int(c) for c in merged["expect_status"]],
    )
    if site.interval < 1 or site.timeout <= 0:
        raise ConfigError(f"site #{index}: interval must be >= 1 and timeout > 0")
    return site


def load_config(path):
    """Read a sites.toml file and return the list of sites it defines."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e

    defaults = dict(DEFAULTS)
    raw_defaults = data.get("defaults", {})
    unknown = set(raw_defaults) - set(DEFAULTS)
    if unknown:
        raise ConfigError(f"[defaults]: unknown key(s) {', '.join(sorted(unknown))}")
    defaults.update(raw_defaults)

    raw_sites = data.get("site", [])
    if not raw_sites:
        raise ConfigError(f"{path}: no [[site]] entries")
    return [_site_from_dict(raw, defaults, i) for i, raw in enumerate(raw_sites, 1)]


def app_dir():
    """Folder of the exe when frozen by PyInstaller, else of this script."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def user_config_path():
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    return Path(base) / "SiteMonitorTray" / CONFIG_NAME


def find_config(explicit):
    """Return (config path, created) and write a starter file if none exists."""
    if explicit:
        return Path(explicit), False
    portable = app_dir() / CONFIG_NAME
    if portable.exists():
        return portable, False
    path = user_config_path()
    if path.exists():
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    return path, True


# --------------------------------------------------------------------------- checks

def check_site(site, session=requests):
    """Request the site once. Returns (is_up, short detail text)."""
    try:
        r = session.get(site.url, timeout=site.timeout, verify=site.verify_tls)
    except requests.exceptions.SSLError:
        return False, "TLS certificate error"
    except requests.exceptions.Timeout:
        return False, f"no answer in {site.timeout:g}s"
    except requests.exceptions.ConnectionError:
        return False, "connection failed"
    except requests.exceptions.RequestException as e:
        return False, type(e).__name__

    if site.expect_status:
        ok = r.status_code in site.expect_status
    else:
        ok = r.status_code < 400
    return ok, f"HTTP {r.status_code}"


class Monitor:
    """Checks every site on its own thread and reports changes through on_change(site, previous)."""

    def __init__(self, sites, on_change):
        self.sites = sites
        self.on_change = on_change
        self._stop = threading.Event()
        self._wake = {id(s): threading.Event() for s in sites}
        self._threads = []

    def start(self):
        for site in self.sites:
            t = threading.Thread(target=self._run, args=(site,), daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self):
        self._stop.set()
        for ev in self._wake.values():
            ev.set()

    def check_now(self):
        for ev in self._wake.values():
            ev.set()

    def _run(self, site):
        session = requests.Session()
        wake = self._wake[id(site)]
        while not self._stop.is_set():
            up, detail = check_site(site, session)
            if self._stop.is_set():
                break
            previous = site.up
            site.detail = detail
            if up != previous:
                site.up = up
                site.since = time.time()
            self.on_change(site, previous)
            wake.wait(site.interval)
            wake.clear()


# --------------------------------------------------------------------------- icons

COLORS = {
    "up": (34, 165, 91),
    "down": (217, 58, 58),
    "partial": (232, 163, 23),
    "unknown": (138, 143, 152),
}


def make_icon(state, size=64):
    """Draw a round status badge with a glyph, supersampled for smooth edges."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((s * 0.04, s * 0.04, s * 0.96, s * 0.96), fill=COLORS[state] + (255,))
    w = int(s * 0.11)
    white = (255, 255, 255, 255)
    if state == "up":
        d.line([(s * 0.28, s * 0.52), (s * 0.44, s * 0.68), (s * 0.73, s * 0.35)],
               fill=white, width=w, joint="curve")
    elif state == "down":
        d.line([(s * 0.32, s * 0.32), (s * 0.68, s * 0.68)], fill=white, width=w)
        d.line([(s * 0.68, s * 0.32), (s * 0.32, s * 0.68)], fill=white, width=w)
    elif state == "partial":
        d.line([(s * 0.5, s * 0.24), (s * 0.5, s * 0.58)], fill=white, width=w)
        r = w * 0.65
        d.ellipse((s * 0.5 - r, s * 0.74 - r, s * 0.5 + r, s * 0.74 + r), fill=white)
    else:
        r = w * 0.55
        for x in (0.3, 0.5, 0.7):
            d.ellipse((s * x - r, s * 0.5 - r, s * x + r, s * 0.5 + r), fill=white)
    return img.resize((size, size), Image.LANCZOS)


ICONS = {state: make_icon(state) for state in COLORS}


def overall_state(sites):
    known = [s.up for s in sites if s.up is not None]
    if not known:
        return "unknown"
    if all(known) and len(known) == len(sites):
        return "up"
    if not any(known):
        return "down"
    return "partial"


# --------------------------------------------------------------------------- tray app

class TrayApp:
    def __init__(self, config_path, cli_sites=None, config_created=False):
        self.config_path = config_path
        self.config_created = config_created
        self.cli_sites = cli_sites
        self.monitor = None
        self.sites = []
        self.lock = threading.Lock()
        self.icon = pystray.Icon("site-monitor", ICONS["unknown"], APP_NAME,
                                 menu=pystray.Menu(self._menu_items))

    # -- lifecycle

    def run(self):
        self.icon.run(setup=self._setup)

    def _setup(self, icon):
        icon.visible = True
        if self.config_created:
            icon.notify(f"Created {self.config_path}. Add your sites there, then choose Reload config.",
                        f"{APP_NAME}: first start")
        self.load()

    def load(self):
        try:
            sites = self.cli_sites or load_config(self.config_path)
        except (OSError, ConfigError) as e:
            self._show_error(str(e))
            return
        if any(not s.verify_tls for s in sites):
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        with self.lock:
            if self.monitor:
                self.monitor.stop()
            self.sites = sites
            self.monitor = Monitor(sites, self._on_change)
        self._refresh()
        self.monitor.start()

    def _show_error(self, message):
        print(f"Config error: {message}", file=sys.stderr)
        self.icon.icon = ICONS["unknown"]
        self.icon.title = f"{APP_NAME}: config error"[:127]
        self.icon.notify(message[:250], f"{APP_NAME}: config error")

    # -- state changes

    def _on_change(self, site, previous):
        if site.up != previous and previous is not None:
            if site.up:
                self.icon.notify(f"{site.name} is reachable again ({site.detail}).",
                                 f"{site.name} is UP")
            else:
                self.icon.notify(f"{site.name} is not responding: {site.detail}.",
                                 f"{site.name} is DOWN")
        self._refresh()

    def _refresh(self):
        sites = self.sites
        state = overall_state(sites)
        up = sum(1 for s in sites if s.up)
        self.icon.icon = ICONS[state]
        if len(sites) == 1:
            s = sites[0]
            status = "checking..." if s.up is None else ("UP" if s.up else f"DOWN ({s.detail})")
            title = f"{APP_NAME}: {s.name} {status}"
        else:
            title = f"{APP_NAME}: {up}/{len(sites)} up"
            down = [s.name for s in sites if s.up is False]
            if down:
                title += " - down: " + ", ".join(down)
        self.icon.title = title[:127]   # Windows tooltip limit
        self.icon.update_menu()

    # -- menu

    def _menu_items(self):
        items = []
        for site in self.sites:
            if site.up is None:
                mark, status = "…", "checking"
            elif site.up:
                mark, status = "✔", site.detail
            else:
                mark, status = "✖", site.detail
            items.append(pystray.MenuItem(f"{mark}  {site.name}: {status}",
                                          self._opener(site.url)))
        if items:
            items.append(pystray.Menu.SEPARATOR)
        items += [
            pystray.MenuItem("Check now", self._check_now, default=True),
            pystray.MenuItem("Open config", self._open_config, visible=self.cli_sites is None),
            pystray.MenuItem("Show config in folder", self._show_config, visible=self.cli_sites is None),
            pystray.MenuItem("Reload config", self._reload, visible=self.cli_sites is None),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Site Monitor {__version__}", None, enabled=False),
            pystray.MenuItem("Quit", self._quit),
        ]
        return items

    @staticmethod
    def _opener(url):
        return lambda icon, item: webbrowser.open(url)

    def _check_now(self, icon, item):
        if self.monitor:
            self.monitor.check_now()

    def _open_config(self, icon, item):
        # .toml has no default app on Windows, so open it in Notepad
        path = str(Path(self.config_path).resolve())
        if sys.platform == "win32":
            subprocess.Popen(["notepad.exe", path])
        else:
            webbrowser.open(Path(path).as_uri())

    def _show_config(self, icon, item):
        path = Path(self.config_path).resolve()
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        else:
            webbrowser.open(path.parent.as_uri())

    def _reload(self, icon, item):
        self.load()

    def _quit(self, icon, item):
        if self.monitor:
            self.monitor.stop()
        icon.stop()


# --------------------------------------------------------------------------- CLI

def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Tray app that watches websites and notifies on up/down changes.")
    p.add_argument("--config", help=f"path to the config file (default: {CONFIG_NAME} next to the app, "
                                    f"else {user_config_path()})")
    p.add_argument("--url", help="watch this one URL instead of using a config file")
    p.add_argument("--name", default="", help="friendly name for --url (defaults to the URL)")
    p.add_argument("--interval", type=float, default=DEFAULTS["interval"],
                   help=f"seconds between checks for --url (default: {DEFAULTS['interval']})")
    p.add_argument("--insecure", action="store_true",
                   help="for --url: accept invalid or self-signed TLS certificates")
    p.add_argument("--once", action="store_true",
                   help="check every site once, print the result and exit (exit code 1 if any is down)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv)


def run_once(sites):
    if any(not s.verify_tls for s in sites):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    all_up = True
    for site in sites:
        up, detail = check_site(site)
        all_up &= up
        print(f"{'UP  ' if up else 'DOWN'}  {site.name:<30} {detail:<24} {site.url}")
    return 0 if all_up else 1


def main(argv=None):
    args = parse_args(argv)

    cli_sites = None
    if args.url:
        cli_sites = [Site(name=args.name or args.url, url=args.url, interval=args.interval,
                          verify_tls=not args.insecure)]
    config_path, created = (None, False) if cli_sites else find_config(args.config)

    if args.once:
        try:
            sites = cli_sites or load_config(config_path)
        except (OSError, ConfigError) as e:
            print(f"Config error: {e}", file=sys.stderr)
            return 2
        return run_once(sites)

    TrayApp(config_path, cli_sites, created).run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
