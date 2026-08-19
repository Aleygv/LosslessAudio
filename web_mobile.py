"""
Mobile Web Application & PWA Server for Lossless Studio.
Allows opening the mobile interface on PC browser or any Android smartphone via Wi-Fi.
"""
import os
import sys
import socket
import webbrowser
import threading
import time
import flet as ft

# Add workspace directory to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mobile_app import main as mobile_main


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def get_free_port(start_port: int = 8550) -> int:
    for p in range(start_port, start_port + 20):
        if is_port_available(p):
            return p
    return start_port


def auto_open_browser(url: str):
    time.sleep(1.2)
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = get_free_port(8550)
    local_url = f"http://localhost:{port}"
    phone_url = f"http://{local_ip}:{port}"

    print("=" * 60)
    print("  LOSSLESS STUDIO - MOBILE WEB SERVER")
    print("=" * 60)
    print(f"  PC Browser URL:  {local_url}")
    print(f"  Phone Wi-Fi URL: {phone_url}")
    print("=" * 60)

    threading.Thread(target=auto_open_browser, args=(local_url,), daemon=True).start()

    ft.app(
        target=mobile_main,
        view=ft.AppView.WEB_BROWSER,
        host="0.0.0.0",
        port=port,
    )
