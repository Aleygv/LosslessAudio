"""
Lossless Music Studio - Mobile Android Application (Flet / Flutter).
Designed for touch screens, Android 13/14/15 scoped storage,
instant Lossless / Hi-Res search, and 1-tap FLAC / ALAC downloading.
"""
import os
import sys
import threading
from pathlib import Path
from typing import List, Optional
import flet as ft

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import TrackInfo, QualityTier
from core.engine import MusicSearchEngine
from config import load_config, save_config


def get_android_music_dir() -> str:
    """Returns the optimal music storage path for Android or fallback desktop."""
    android_candidates = [
        "/storage/emulated/0/Music/LosslessMusic",
        "/storage/emulated/0/Download/LosslessMusic",
        "/sdcard/Music/LosslessMusic",
    ]
    for path in android_candidates:
        parent = os.path.dirname(path)
        if os.path.exists(parent):
            os.makedirs(path, exist_ok=True)
            return path

    desktop_path = str(Path.home() / "Music" / "LosslessMusic")
    os.makedirs(desktop_path, exist_ok=True)
    return desktop_path


def main(page: ft.Page):
    page.title = "Lossless Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0B0C10"
    page.padding = 12
    page.scroll = ft.ScrollMode.ADAPTIVE

    config = load_config()
    engine = MusicSearchEngine()
    active_format = config.get("target_format", "flac")
    download_dir = get_android_music_dir()

    # --- UI Elements ---

    # 1. AppBar
    page.app_bar = ft.AppBar(
        leading=ft.Icon(ft.Icons.HEADPHONES_ROUNDED, color="#818CF8", size=28),
        leading_width=40,
        title=ft.Row(
            [
                ft.Text("LOSSLESS STUDIO", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Container(
                    content=ft.Text(" FLAC ", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor="#059669",
                    border_radius=4,
                    padding=ft.Padding(4, 2, 4, 2),
                ),
            ],
            spacing=8,
        ),
        center_title=False,
        bgcolor="#12131C",
    )

    # Status / SnackBar helper
    def show_snackbar(message: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor="#DC2626" if is_error else "#10B981",
            duration=3000,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    # 2. Search Box with Clear & Paste
    search_field = ft.TextField(
        hint_text="Введите название трека или автора...",
        hint_style=ft.TextStyle(color="#71717A", size=13),
        text_size=14,
        color=ft.Colors.WHITE,
        bgcolor="#161722",
        border_color="#27273A",
        border_radius=12,
        content_padding=14,
        dense=True,
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        expand=True,
    )

    def on_paste_click(e):
        try:
            val = page.get_clipboard()
            if val:
                search_field.value = val.strip()
                page.update()
        except Exception:
            pass

    def on_clear_click(e):
        search_field.value = ""
        page.update()

    search_actions = ft.Row(
        [
            ft.IconButton(
                icon=ft.Icons.CONTENT_PASTE_ROUNDED,
                icon_color="#A1A1AA",
                tooltip="Вставить из буфера",
                on_click=on_paste_click,
            ),
            ft.IconButton(
                icon=ft.Icons.CLEAR_ROUNDED,
                icon_color="#71717A",
                tooltip="Очистить",
                on_click=on_clear_click,
            ),
        ],
        spacing=0,
    )

    # Search bar row
    search_row = ft.Container(
        content=ft.Row(
            [
                search_field,
                search_actions,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor="#161722",
        border_radius=12,
        border=ft.border.all(1, "#27273A"),
        padding=ft.Padding(8, 2, 8, 2),
    )

    # 3. Format & Filter Options
    format_dropdown = ft.Dropdown(
        value=active_format.upper(),
        options=[
            ft.dropdown.Option("FLAC", "💎 FLAC (.flac)"),
            ft.dropdown.Option("ALAC", "🍏 ALAC (.m4a)"),
        ],
        text_size=12,
        bgcolor="#161722",
        border_color="#27273A",
        border_radius=8,
        content_padding=10,
        width=150,
        dense=True,
    )

    lossless_only_switch = ft.Switch(
        label="Только Hi-Res",
        label_style=ft.TextStyle(size=12, color="#A1A1AA", weight=ft.FontWeight.BOLD),
        value=False,
        active_color="#10B981",
    )

    options_row = ft.Row(
        [
            ft.Row([ft.Text("Формат:", size=12, color="#71717A"), format_dropdown], spacing=6),
            lossless_only_switch,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    # 4. Search Trigger Button
    search_btn = ft.ElevatedButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SEARCH_ROUNDED, color=ft.Colors.WHITE, size=18),
                ft.Text("Найти в Lossless / FLAC", weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.WHITE),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        bgcolor="#6366F1",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding(0, 12, 0, 12),
        ),
        width=float("inf"),
    )

    # 5. Quick Suggestion Chips
    def on_chip_click(query_text: str):
        search_field.value = query_text
        page.update()
        trigger_search()

    chips_list = [
        "Hans Zimmer",
        "Pink Floyd",
        "Daft Punk",
        "The Weeknd",
        "Cyberpunk 2077",
        "Queen",
        "Ludovico Einaudi",
    ]

    chips_row = ft.Row(
        [
            ft.Chip(
                label=ft.Text(name, size=11, color="#A1A1AA"),
                bgcolor="#1E202C",
                on_click=lambda e, q=name: on_chip_click(q),
            )
            for name in chips_list
        ],
        scroll=ft.ScrollMode.HIDDEN,
    )

    # 6. Results List
    results_column = ft.Column(spacing=8, expand=True)
    loading_indicator = ft.ProgressBar(color="#6366F1", bgcolor="#161722", visible=False)
    status_label = ft.Text("✨ Введите название песни для поиска", size=12, color="#71717A")

    # --- Build Track Card for Mobile ---
    def build_track_card(track: TrackInfo) -> ft.Container:
        # Tier colors
        if track.quality_tier == QualityTier.HI_RES_24BIT:
            badge_bg = "#451A03"
            badge_fg = "#F59E0B"
            badge_text = "✦ Hi-Res 24-bit"
        elif track.quality_tier == QualityTier.LOSSLESS_FLAC:
            badge_bg = "#064E3B"
            badge_fg = "#10B981"
            badge_text = "✦ FLAC Lossless"
        elif track.quality_tier == QualityTier.LOSSLESS_ALAC:
            badge_bg = "#083344"
            badge_fg = "#06B6D4"
            badge_text = "✦ ALAC Lossless"
        else:
            badge_bg = "#1F2030"
            badge_fg = "#818CF8"
            badge_text = "✦ HQ Stream"

        # Image thumbnail
        cover_img = ft.Image(
            src=track.cover_url if track.cover_url else "https://via.placeholder.com/64/161722/FFFFFF?text=🎵",
            width=50,
            height=50,
            fit=ft.ImageFit.COVER,
            border_radius=8,
            error_content=ft.Icon(ft.Icons.MUSIC_NOTE_ROUNDED, color="#71717A", size=24),
        )

        progress_bar = ft.ProgressBar(value=0, color="#6366F1", bgcolor="#12131C", visible=False, height=4)
        progress_text = ft.Text("", size=10, color="#71717A", visible=False)

        download_icon_btn = ft.IconButton(
            icon=ft.Icons.DOWNLOAD_ROUNDED,
            icon_color="#6366F1",
            icon_size=24,
            tooltip="Скачать в FLAC",
        )

        def download_worker(e):
            download_icon_btn.visible = False
            progress_bar.visible = True
            progress_text.visible = True
            progress_text.value = "Загрузка..."
            page.update()

            def _progress_cb(fraction: float, msg: str):
                progress_bar.value = fraction
                progress_text.value = msg[:30]
                if fraction >= 1.0:
                    progress_text.value = "✓ Сохранено в Музыку"
                    progress_text.color = "#10B981"
                    download_icon_btn.icon = ft.Icons.CHECK_CIRCLE_ROUNDED
                    download_icon_btn.icon_color = "#10B981"
                    download_icon_btn.visible = True
                    show_snackbar(f"✓ Скачано: {track.artist} - {track.title}")
                page.update()

            def _run():
                try:
                    fmt = format_dropdown.value.lower() if format_dropdown.value else "flac"
                    saved_path = engine.download_and_process(
                        track=track,
                        download_dir=download_dir,
                        target_format=fmt,
                        progress_callback=_progress_cb,
                    )
                except Exception as ex:
                    progress_text.value = f"Ошибка: {str(ex)[:25]}"
                    progress_text.color = "#EF4444"
                    download_icon_btn.visible = True
                    download_icon_btn.icon = ft.Icons.REFRESH_ROUNDED
                    download_icon_btn.icon_color = "#EF4444"
                    show_snackbar(f"Ошибка: {ex}", is_error=True)
                    page.update()

            threading.Thread(target=_run, daemon=True).start()

        download_icon_btn.on_click = download_worker

        dur_str = f" • ⏱ {track.duration_str}" if track.duration > 0 else ""
        sub_info = f"{track.artist}{dur_str}"

        card_content = ft.Container(
            content=ft.Row(
                [
                    cover_img,
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(track.title[:38], size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, no_wrap=True),
                                    ft.Container(
                                        content=ft.Text(badge_text, size=9, weight=ft.FontWeight.BOLD, color=badge_fg),
                                        bgcolor=badge_bg,
                                        border_radius=4,
                                        padding=ft.Padding(4, 2, 4, 2),
                                    ),
                                ],
                                spacing=6,
                            ),
                            ft.Text(sub_info[:45], size=11, color="#A1A1AA", no_wrap=True),
                            progress_bar,
                            progress_text,
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    download_icon_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#161722",
            border_radius=10,
            border=ft.border.all(1, "#27273A"),
            padding=8,
        )
        return card_content

    # --- Search Logic ---
    def trigger_search(e=None):
        query = search_field.value.strip() if search_field.value else ""
        if not query:
            show_snackbar("Введите запрос для поиска", is_error=True)
            return

        search_btn.disabled = True
        loading_indicator.visible = True
        status_label.value = f"🔎 Поиск «{query}» в Lossless источниках..."
        results_column.controls.clear()
        page.update()

        def _search_thread():
            try:
                results = engine.search_all(query)
                if lossless_only_switch.value:
                    results = [r for r in results if r.is_lossless or r.quality_tier in [QualityTier.HI_RES_24BIT, QualityTier.LOSSLESS_FLAC, QualityTier.LOSSLESS_ALAC]]

                def _render():
                    loading_indicator.visible = False
                    search_btn.disabled = False
                    if not results:
                        status_label.value = "Ничего не найдено. Попробуйте другой запрос."
                        results_column.controls.append(
                            ft.Container(
                                content=ft.Text("🔍 Треки не найдены", size=13, color="#71717A"),
                                alignment=ft.alignment.center,
                                padding=20,
                            )
                        )
                    else:
                        status_label.value = f"✨ Найдено треков: {len(results)}"
                        for track in results:
                            results_column.controls.append(build_track_card(track))
                    page.update()

                page.call_soon(_render)
            except Exception as ex:
                def _error():
                    loading_indicator.visible = False
                    search_btn.disabled = False
                    status_label.value = f"Ошибка поиска: {ex}"
                    page.update()
                page.call_soon(_error)

        threading.Thread(target=_search_thread, daemon=True).start()

    search_btn.on_click = trigger_search
    search_field.on_submit = trigger_search

    # Assemble Layout
    page.add(
        search_row,
        chips_row,
        options_row,
        search_btn,
        loading_indicator,
        status_label,
        results_column,
    )


if __name__ == "__main__":
    ft.app(target=main)
