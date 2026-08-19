"""
Main Mobile Application Entrypoint for Flet / Android APK build.
"""
import flet as ft
from mobile_app import main as mobile_main

if __name__ == "__main__":
    ft.app(target=mobile_main)
