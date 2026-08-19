"""
Mobile Web Application & PWA Server for Lossless Studio.
Allows opening the mobile interface on any Android smartphone via Wi-Fi (e.g. http://192.168.x.x:8550)
or installing it as a PWA (Progressive Web App) with instant FLAC/ALAC downloads!
"""
import os
import sys
import socket
import threading
from typing import List
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


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8550
    print("\n" + "=" * 60)
    print("⚡ LOSSLESS STUDIO MOBILE WEB SERVER")
    print("=" * 60)
    print(f"📱 Откройте на телефоне (в браузере Chrome/Samsung/любом):")
    print(f"👉 http://{local_ip}:{port}")
    print(f"👉 или http://localhost:{port} (на компьютере)")
    print("\n💡 Совет: Нажмите в браузере телефона «Добавить на главный экран»,")
    print("чтобы приложение установилось как нативная иконка на смартфон!")
    print("=" * 60 + "\n")

    ft.app(
        target=mobile_main,
        view=ft.AppView.WEB_BROWSER,
        host="0.0.0.0",
        port=port,
    )
