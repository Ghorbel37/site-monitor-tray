import threading
import time
import argparse
import requests
import urllib3
from PIL import Image, ImageDraw
import pystray

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser(description="Site uptime monitor")
parser.add_argument("--url",  default="https://127.0.0.1:80", help="URL to monitor")
parser.add_argument("--name", default="", help="Friendly site name shown in notifications (defaults to URL)")
parser.add_argument("--interval", type=int, default=5, help="Check interval in seconds (default: 5)")
args = parser.parse_args()

URL            = args.url
SITE_NAME      = args.name or args.url
CHECK_INTERVAL = args.interval

running = True
icon = None


def make_icon(color):
    img = Image.new("RGB", (64, 64), color="white")
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return img


ICON_UP      = make_icon("green")
ICON_DOWN    = make_icon("red")
ICON_UNKNOWN = make_icon("gray")


def notify(tray_icon, title, message):
    tray_icon.notify(title, message)


def check_website(tray_icon):
    global running
    print(f"Monitoring {SITE_NAME} ({URL}) every {CHECK_INTERVAL}s ...")

    last_status = None   # None = unknown, True = up, False = down

    while running:
        is_up = False
        try:
            r = requests.get(URL, timeout=5, verify=False)
            is_up = (r.status_code == 200)
        except Exception:
            is_up = False

        if is_up != last_status:
            if is_up:
                tray_icon.icon = ICON_UP
                tray_icon.title = f"Site Monitor – {SITE_NAME} UP"
                notify(tray_icon, f"{SITE_NAME} is UP!", f"{SITE_NAME} is now reachable.")
            else:
                tray_icon.icon = ICON_DOWN
                tray_icon.title = f"Site Monitor – {SITE_NAME} DOWN"
                if last_status is not None:   # skip notification on first poll
                    notify(tray_icon, f"{SITE_NAME} is DOWN!", f"{SITE_NAME} is not responding.")
            last_status = is_up

        time.sleep(CHECK_INTERVAL)


def on_quit(icon, item):
    global running
    running = False
    icon.stop()


def main():
    global icon
    icon = pystray.Icon(
        "Site Monitor",
        ICON_UNKNOWN,
        "Site Monitor – checking…",
        menu=pystray.Menu(pystray.MenuItem("Quit", on_quit)),
    )

    t = threading.Thread(target=check_website, args=(icon,), daemon=True)
    t.start()

    icon.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        running = False
        if icon:
            icon.stop()
        print("\nStopped.")