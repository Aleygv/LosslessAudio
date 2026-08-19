"""
Main Application Window - Lossless Music Studio (ALAC / FLAC Hi-Res Downloader).
Completely redesigned for high-fidelity audio grabbing with premium aesthetics,
batch downloading, search history, quick discovery chips, and seamless file management.
"""
import os
import sys
import threading
import subprocess
import ctypes
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import List, Dict, Any
from PIL import Image, ImageTk

from config import load_config, save_config
from core.models import TrackInfo, QualityTier
from core.engine import MusicSearchEngine
from core.audio import get_ffmpeg_path
from ui.styles import COLORS, FONT_FAMILY
from ui.track_card import TrackCard
from ui.context_menu import attach_context_menu


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        if sys.platform == "win32":
            try:
                myappid = "antigravity.losslessstudio.grabber.2.0"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        self.title("Lossless Music Studio • Hi-Res ALAC & FLAC Downloader")
        self.geometry("1140x860")
        self.minsize(940, 700)
        self.configure(fg_color=COLORS["bg_dark"])

        self.config = load_config()
        self.engine = MusicSearchEngine()

        self.current_results: List[TrackInfo] = []
        self.downloaded_history: List[Dict[str, Any]] = []
        self.active_cards: List[TrackCard] = []
        self.is_searching = False
        self.is_batch_downloading = False

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self._set_window_icon()
        self._build_ui()
        self._check_ffmpeg()
        self._bind_shortcuts()

    def _set_window_icon(self):
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        ico_path = os.path.join(assets_dir, "app_icon.ico")
        png_path = os.path.join(assets_dir, "app_icon.png")

        try:
            if os.path.exists(ico_path) and sys.platform == "win32":
                self.iconbitmap(ico_path)
            elif os.path.exists(png_path):
                img = ImageTk.PhotoImage(Image.open(png_path))
                self.iconphoto(True, img)
        except Exception:
            pass

    def _bind_shortcuts(self):
        self.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self.bind("<Control-o>", lambda e: self._open_download_folder())
        self.bind("<Escape>", lambda e: self._clear_search())

    def _build_ui(self):
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # =========================================================================
        # 1. HEADER SECTION (Logo, Subtitle, Quick Actions)
        # =========================================================================
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=24, pady=(16, 6), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        # Logo + App Name
        brand_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="w")

        title_lbl = ctk.CTkLabel(
            brand_frame,
            text="⚡ LOSSLESS STUDIO",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        title_lbl.pack(side="left")

        ver_badge = ctk.CTkLabel(
            brand_frame,
            text=" PRO ",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            fg_color=COLORS["accent_primary"],
            text_color="#FFFFFF",
            corner_radius=4,
            height=18
        )
        ver_badge.pack(side="left", padx=8)

        sub_lbl = ctk.CTkLabel(
            header_frame,
            text="✦ Hi-Res 24-bit 96kHz • Apple ALAC (.m4a) • Studio FLAC (.flac) • Deezer • Apple Music • Archive",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLORS["text_secondary"]
        )
        sub_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Top Right Badges & Folder button
        top_actions = ctk.CTkFrame(header_frame, fg_color="transparent")
        top_actions.grid(row=0, column=1, rowspan=2, sticky="e")

        self.ffmpeg_badge = ctk.CTkLabel(
            top_actions,
            text="● Проверка FFmpeg...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLORS["accent_success"],
            fg_color=COLORS["badge_bg"],
            corner_radius=6,
            height=28,
            padx=10
        )
        self.ffmpeg_badge.pack(side="left", padx=(0, 8))

        open_folder_btn = ctk.CTkButton(
            top_actions,
            text="📁 Папка загрузок",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            width=135,
            height=30,
            fg_color=COLORS["badge_bg"],
            hover_color=COLORS["card_hover"],
            corner_radius=8,
            command=self._open_download_folder
        )
        open_folder_btn.pack(side="left")

        # =========================================================================
        # 2. CONTROL PANEL (Path, Format Segment, Lossless Switch)
        # =========================================================================
        control_panel = ctk.CTkFrame(
            self,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
        )
        control_panel.grid(row=1, column=0, padx=24, pady=(6, 8), sticky="ew")
        control_panel.grid_columnconfigure(1, weight=1)

        # Path Label + Entry + Browse
        dir_lbl = ctk.CTkLabel(
            control_panel,
            text="📂 Сохранять в:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        dir_lbl.grid(row=0, column=0, padx=(14, 6), pady=10, sticky="w")

        self.dir_entry = ctk.CTkEntry(
            control_panel,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=32,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            text_color=COLORS["text_primary"]
        )
        self.dir_entry.insert(0, self.config.get("download_dir", ""))
        self.dir_entry.grid(row=0, column=1, padx=6, pady=10, sticky="ew")
        attach_context_menu(self.dir_entry)

        browse_btn = ctk.CTkButton(
            control_panel,
            text="Обзор...",
            width=80,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLORS["badge_bg"],
            hover_color=COLORS["card_hover"],
            corner_radius=6,
            command=self._browse_directory
        )
        browse_btn.grid(row=0, column=2, padx=(2, 14), pady=10)

        # Separator Line (visual)
        sep = ctk.CTkFrame(control_panel, width=1, height=26, fg_color=COLORS["border"])
        sep.grid(row=0, column=3, padx=(0, 14), pady=10)

        # Target Format Selector
        fmt_lbl = ctk.CTkLabel(
            control_panel,
            text="Формат:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        fmt_lbl.grid(row=0, column=4, padx=(0, 6), pady=10)

        self.format_segmented = ctk.CTkSegmentedButton(
            control_panel,
            values=["ALAC (.m4a)", "FLAC (.flac)"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            selected_color=COLORS["accent_primary"],
            selected_hover_color=COLORS["accent_hover"],
            height=32,
            command=self._on_format_changed
        )
        initial_fmt = "ALAC (.m4a)" if self.config.get("target_format") == "alac" else "FLAC (.flac)"
        self.format_segmented.set(initial_fmt)
        self.format_segmented.grid(row=0, column=5, padx=(0, 14), pady=10)

        # Lossless Only Switch
        self.lossless_only_var = ctk.BooleanVar(value=self.config.get("only_lossless", False))
        self.lossless_switch = ctk.CTkSwitch(
            control_panel,
            text="Только Lossless / 24-bit",
            variable=self.lossless_only_var,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            progress_color=COLORS["accent_success"],
            command=self._apply_filter
        )
        self.lossless_switch.grid(row=0, column=6, padx=(0, 14), pady=10)

        # =========================================================================
        # 3. SEARCH BAR & QUICK DISCOVERY CHIPS
        # =========================================================================
        search_section = ctk.CTkFrame(self, fg_color="transparent")
        search_section.grid(row=2, column=0, padx=24, pady=(0, 6), sticky="ew")
        search_section.grid_columnconfigure(0, weight=1)

        # Main Search Input Row
        search_row = ctk.CTkFrame(
            search_section,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
        )
        search_row.grid(row=0, column=0, sticky="ew")
        search_row.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Введите трек, исполнителя или альбом (например, Pink Floyd - Time, Hans Zimmer, Daft Punk)...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            height=44,
            fg_color="transparent",
            border_width=0,
            text_color=COLORS["text_primary"]
        )
        self.search_entry.grid(row=0, column=0, padx=(14, 6), pady=4, sticky="ew")
        self.search_entry.bind("<Return>", lambda event: self._start_search())
        attach_context_menu(self.search_entry)

        # Clear button ✕
        self.clear_btn = ctk.CTkButton(
            search_row,
            text="✕",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=36,
            height=36,
            fg_color="transparent",
            hover_color=COLORS["card_hover"],
            text_color=COLORS["text_muted"],
            command=self._clear_search
        )
        self.clear_btn.grid(row=0, column=1, padx=(0, 4), pady=4)

        # Paste button 📋
        paste_btn = ctk.CTkButton(
            search_row,
            text="📋 Вставить",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            width=85,
            height=36,
            fg_color=COLORS["badge_bg"],
            hover_color=COLORS["card_hover"],
            corner_radius=8,
            command=lambda: self._paste_to_entry(self.search_entry)
        )
        paste_btn.grid(row=0, column=2, padx=(0, 6), pady=4)

        # Search Button 🔍
        self.search_btn = ctk.CTkButton(
            search_row,
            text="🔍 Найти в Lossless",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            width=150,
            height=36,
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            corner_radius=8,
            command=self._start_search
        )
        self.search_btn.grid(row=0, column=3, padx=(0, 6), pady=4)

        # Quick Suggestions / Discovery Chips Row
        chips_frame = ctk.CTkFrame(search_section, fg_color="transparent")
        chips_frame.grid(row=1, column=0, pady=(6, 0), sticky="ew")

        ctk.CTkLabel(
            chips_frame,
            text="Быстрый поиск:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLORS["text_muted"]
        ).pack(side="left", padx=(4, 8))

        suggestions = [
            ("🎬 Hans Zimmer", "Hans Zimmer"),
            ("🎸 Pink Floyd", "Pink Floyd"),
            ("🎹 Daft Punk", "Daft Punk"),
            ("🎤 The Weeknd", "The Weeknd"),
            ("⚡ Cyberpunk 2077", "Cyberpunk 2077"),
            ("🌌 Interstellar", "Hans Zimmer Interstellar"),
            ("🎻 Ludovico Einaudi", "Ludovico Einaudi"),
            ("🔥 Queen", "Queen Bohemian Rhapsody"),
        ]

        for label, query in suggestions:
            chip_btn = ctk.CTkButton(
                chips_frame,
                text=label,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                height=26,
                fg_color=COLORS["pill_bg"],
                hover_color=COLORS["card_hover"],
                text_color=COLORS["text_secondary"],
                corner_radius=13,
                command=lambda q=query: self._search_query(q)
            )
            chip_btn.pack(side="left", padx=3)

        # =========================================================================
        # 4. VIEW TABS & RESULTS SCROLL AREA
        # =========================================================================
        results_container = ctk.CTkFrame(self, fg_color="transparent")
        results_container.grid(row=3, column=0, padx=24, pady=4, sticky="nsew")
        results_container.grid_rowconfigure(1, weight=1)
        results_container.grid_columnconfigure(0, weight=1)

        # Toolbar above results (Stats, Batch Download, Clear)
        self.results_toolbar = ctk.CTkFrame(results_container, fg_color="transparent")
        self.results_toolbar.grid(row=0, column=0, pady=(0, 6), sticky="ew")
        self.results_toolbar.grid_columnconfigure(0, weight=1)

        # Left: Results Count / Mode switcher
        self.results_count_lbl = ctk.CTkLabel(
            self.results_toolbar,
            text="✨ Готов к поиску",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        self.results_count_lbl.grid(row=0, column=0, sticky="w")

        # Right: Batch Download Button
        self.download_all_btn = ctk.CTkButton(
            self.results_toolbar,
            text="⚡ Скачать ВСЕ треки",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            width=170,
            height=32,
            fg_color=COLORS["accent_success"],
            hover_color=COLORS["accent_success_hover"],
            corner_radius=8,
            state="disabled",
            command=self._download_all_visible
        )
        self.download_all_btn.grid(row=0, column=1, padx=(0, 6), sticky="e")

        self.clear_results_btn = ctk.CTkButton(
            self.results_toolbar,
            text="🧹 Очистить",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            width=90,
            height=32,
            fg_color=COLORS["badge_bg"],
            hover_color=COLORS["card_hover"],
            corner_radius=8,
            command=self._clear_results_view
        )
        self.clear_results_btn.grid(row=0, column=2, sticky="e")

        # Scrollable Results Container
        self.results_frame = ctk.CTkScrollableFrame(
            results_container,
            fg_color="transparent",
            corner_radius=0
        )
        self.results_frame.grid(row=1, column=0, sticky="nsew")
        self.results_frame.grid_columnconfigure(0, weight=1)

        self._show_welcome_state()

        # =========================================================================
        # 5. BOTTOM STATUS BAR
        # =========================================================================
        self.status_bar = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], height=34, corner_radius=0)
        self.status_bar.grid(row=4, column=0, sticky="ew")

        self.status_text = ctk.CTkLabel(
            self.status_bar,
            text="✨ Система готова к работе. Введите запрос для поиска Lossless музыки.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLORS["text_secondary"]
        )
        self.status_text.pack(side="left", padx=16, pady=6)

        self.session_counter_lbl = ctk.CTkLabel(
            self.status_bar,
            text="Скачано за сессию: 0",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLORS["text_muted"]
        )
        self.session_counter_lbl.pack(side="right", padx=16, pady=6)

    def _show_welcome_state(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        self.download_all_btn.configure(state="disabled")
        self.results_count_lbl.configure(text="✨ Готов к поиску")

        welcome_card = ctk.CTkFrame(
            self.results_frame,
            fg_color=COLORS["card_bg"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"]
        )
        welcome_card.pack(fill="x", padx=20, pady=30)

        # Header in Card
        hero_title = ctk.CTkLabel(
            welcome_card,
            text="🎧 Студийный поиск и загрузка Lossless музыки",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=COLORS["text_primary"]
        )
        hero_title.pack(pady=(24, 8))

        hero_subtitle = ctk.CTkLabel(
            welcome_card,
            text="Максимальное исходное качество: Hi-Res 24-bit / 96kHz • Apple ALAC (.m4a) • Studio FLAC (.flac)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLORS["accent_primary"]
        )
        hero_subtitle.pack(pady=(0, 20))

        # 3 Feature Columns
        features_frame = ctk.CTkFrame(welcome_card, fg_color="transparent")
        features_frame.pack(fill="x", padx=24, pady=(0, 24))
        features_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Feature 1: Apple ALAC
        col1 = ctk.CTkFrame(features_frame, fg_color=COLORS["input_bg"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        col1.grid(row=0, column=0, padx=6, pady=4, sticky="nsew")
        ctk.CTkLabel(col1, text="🍏 Apple ALAC (.m4a)", font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"), text_color=COLORS["accent_alac"]).pack(pady=(12, 4))
        ctk.CTkLabel(col1, text="100% совместимо с Apple Music,\niTunes, iPhone, iPad и Mac.\nВшитые обложки и теги.", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLORS["text_secondary"], justify="center").pack(pady=(0, 12), padx=8)

        # Feature 2: Studio FLAC
        col2 = ctk.CTkFrame(features_frame, fg_color=COLORS["input_bg"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        col2.grid(row=0, column=1, padx=6, pady=4, sticky="nsew")
        ctk.CTkLabel(col2, text="💎 Studio FLAC (.flac)", font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"), text_color=COLORS["accent_flac"]).pack(pady=(12, 4))
        ctk.CTkLabel(col2, text="Без сжатия с потерями,\nдля Android, Windows, Hi-Fi\nплееров и звуковых карт.", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLORS["text_secondary"], justify="center").pack(pady=(0, 12), padx=8)

        # Feature 3: Full Metadata
        col3 = ctk.CTkFrame(features_frame, fg_color=COLORS["input_bg"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        col3.grid(row=0, column=2, padx=6, pady=4, sticky="nsew")
        ctk.CTkLabel(col3, text="🏷 Полные метаданные", font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"), text_color=COLORS["accent_gold"]).pack(pady=(12, 4))
        ctk.CTkLabel(col3, text="Оригинальные названия,\nальбомы, год выпуска и\nHD обложки высокого разрешения.", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLORS["text_secondary"], justify="center").pack(pady=(0, 12), padx=8)

    def _check_ffmpeg(self):
        try:
            get_ffmpeg_path()
            self.ffmpeg_badge.configure(
                text="● FFmpeg подключен",
                text_color=COLORS["accent_success"]
            )
        except Exception:
            self.ffmpeg_badge.configure(
                text="⚠ FFmpeg не найден",
                text_color=COLORS["accent_error"]
            )

    def _browse_directory(self):
        folder = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if folder:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, folder)
            self.config["download_dir"] = folder
            save_config(self.config)
            self.set_status(f"Папка сохранения изменена: {folder}")

    def _open_download_folder(self):
        folder = self.dir_entry.get().strip() or self.config.get("download_dir")
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.run(["xdg-open", folder])

    def _on_format_changed(self, value):
        fmt = "alac" if "ALAC" in value else "flac"
        self.config["target_format"] = fmt
        save_config(self.config)
        self.set_status(f"Формат сохранения установлен: {fmt.upper()}")

    def _apply_filter(self):
        self.config["only_lossless"] = self.lossless_only_var.get()
        save_config(self.config)
        self._render_results()

    def set_status(self, text: str):
        self.after(0, lambda: self.status_text.configure(text=text))

    def _search_query(self, query: str):
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, query)
        self._start_search()

    def _clear_search(self):
        self.search_entry.delete(0, "end")
        self.search_entry.focus_set()

    def _clear_results_view(self):
        self.current_results.clear()
        self.active_cards.clear()
        self._show_welcome_state()
        self.set_status("Результаты очищены.")

    def _start_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return

        if self.is_searching:
            return

        self.is_searching = True
        self.search_btn.configure(state="disabled", text="Поиск...")
        self.set_status(f"🔎 Идет поиск «{query}» по всем источникам...")

        # Clear results and show modern loading animation
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        loading_box = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        loading_box.pack(pady=50)

        pbar = ctk.CTkProgressBar(loading_box, width=340, mode="indeterminate", progress_color=COLORS["accent_primary"])
        pbar.pack(pady=(0, 14))
        pbar.start()

        ctk.CTkLabel(
            loading_box,
            text=f"🔎 Поиск «{query}» в Deezer, Apple Music, Archive и Hi-Res базах...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLORS["text_secondary"]
        ).pack()

        def _worker():
            try:
                results = self.engine.search_all(query, status_callback=self.set_status)
                self.current_results = results
                self.after(0, self._render_results)
            except Exception as e:
                self.set_status(f"Ошибка поиска: {e}")
            finally:
                self.is_searching = False
                self.after(0, lambda: self.search_btn.configure(state="normal", text="🔍 Найти в Lossless"))

        threading.Thread(target=_worker, daemon=True).start()

    def _render_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        filtered = self.current_results
        if self.lossless_only_var.get():
            filtered = [r for r in filtered if r.is_lossless or r.quality_tier in [QualityTier.HI_RES_24BIT, QualityTier.LOSSLESS_FLAC, QualityTier.LOSSLESS_ALAC]]

        if not filtered:
            self.download_all_btn.configure(state="disabled")
            self.results_count_lbl.configure(text="Ничего не найдено")
            empty_card = ctk.CTkFrame(self.results_frame, fg_color=COLORS["card_bg"], corner_radius=12, border_width=1, border_color=COLORS["border"])
            empty_card.pack(fill="x", padx=20, pady=40)
            ctk.CTkLabel(
                empty_card,
                text="🔍 Ничего не найдено по вашему запросу.\nПопробуйте изменить название трека или имя исполнителя.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                text_color=COLORS["text_secondary"],
                justify="center"
            ).pack(pady=30)
            self.set_status("Результатов не найдено.")
            return

        self.results_count_lbl.configure(text=f"✨ Найдено треков: {len(filtered)}")
        self.download_all_btn.configure(state="normal", text=f"⚡ Скачать ВСЕ ({len(filtered)})")
        self.set_status(f"Найдено {len(filtered)} треков студийного качества.")

        self.active_cards.clear()
        for track in filtered:
            card = TrackCard(
                self.results_frame,
                track=track,
                on_download_click=self._handle_download
            )
            card.pack(fill="x", pady=4)
            self.active_cards.append(card)

    def _download_all_visible(self):
        if not self.active_cards or self.is_batch_downloading:
            return

        self.is_batch_downloading = True
        self.download_all_btn.configure(state="disabled", text="Загрузка списка...")
        total = len(self.active_cards)
        self.set_status(f"⚡ Запуск пакетного скачивания {total} треков...")

        def _batch_worker():
            for idx, card in enumerate(self.active_cards, 1):
                try:
                    self.set_status(f"Скачивание [{idx}/{total}]: {card.track.artist} - {card.track.title}")
                    card._on_download_press()
                except Exception:
                    pass
            self.is_batch_downloading = False
            self.set_status("✓ Пакетное скачивание завершено!")
            self.after(0, lambda: self.download_all_btn.configure(state="normal" if self.active_cards else "disabled", text=f"⚡ Скачать ВСЕ ({len(self.active_cards)})"))

        threading.Thread(target=_batch_worker, daemon=True).start()

    def _handle_download(self, track: TrackInfo, card: TrackCard):
        download_dir = self.dir_entry.get().strip() or self.config.get("download_dir")
        target_fmt = "alac" if "ALAC" in self.format_segmented.get() else "flac"

        def _worker():
            try:
                saved_file = self.engine.download_and_process(
                    track=track,
                    download_dir=download_dir,
                    target_format=target_fmt,
                    progress_callback=card.update_progress
                )
                card.set_downloaded_path(saved_file)
                self.downloaded_history.append({
                    "track": track,
                    "path": saved_file,
                    "format": target_fmt.upper()
                })
                self.after(0, lambda: self.session_counter_lbl.configure(text=f"Скачано за сессию: {len(self.downloaded_history)}"))
                self.set_status(f"✓ Успешно сохранено: {os.path.basename(saved_file)}")
            except Exception as e:
                card.set_error(str(e))
                self.set_status(f"Ошибка загрузки «{track.title}»: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _paste_to_entry(self, entry_widget: ctk.CTkEntry):
        try:
            text = self.clipboard_get()
            if text:
                entry_widget.delete(0, "end")
                entry_widget.insert(0, text.strip())
                self.set_status("Текст успешно вставлен из буфера")
        except Exception:
            self.set_status("Буфер обмена пуст")


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
