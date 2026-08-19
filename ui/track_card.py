"""
Compact & Pixel-Perfect Track Card Widget.
Features 52x52 rounded cover thumbnail, inline Hi-Res badges,
clean horizontal alignment with no vertical wasted space, and dynamic progress bar.
"""
import io
import os
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor
import customtkinter as ctk
from PIL import Image
from typing import Callable, Optional

from core.models import TrackInfo, QualityTier
from ui.styles import COLORS, FONT_FAMILY

_IMAGE_CACHE = {}
_IMAGE_POOL = ThreadPoolExecutor(max_workers=8)


class TrackCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        track: TrackInfo,
        on_download_click: Callable[[TrackInfo, "TrackCard"], None],
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLORS["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            height=72,
            **kwargs
        )
        self.track = track
        self.on_download_click = on_download_click
        self.is_downloading = False
        self.downloaded_file_path: Optional[str] = None

        self._build_ui()
        self._load_cover_cached()
        self._bind_hover_effects()

    def _build_ui(self):
        # Prevent frame from blowing up vertically
        self.pack_propagate(False)

        # 1. Left: Cover Art Thumbnail (50x50)
        self.cover_frame = ctk.CTkFrame(
            self,
            width=50,
            height=50,
            fg_color=COLORS["input_bg"],
            corner_radius=8
        )
        self.cover_frame.pack(side="left", padx=(10, 10), pady=10)
        self.cover_frame.pack_propagate(False)

        self.cover_label = ctk.CTkLabel(
            self.cover_frame,
            text="💿",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18),
            text_color=COLORS["text_muted"]
        )
        self.cover_label.place(relx=0.5, rely=0.5, anchor="center")

        # 2. Right: Action Buttons (fixed width, vertically centered)
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(side="right", padx=(8, 12), pady=8)

        self.download_btn = ctk.CTkButton(
            self.action_frame,
            text="⬇ Скачать",
            width=105,
            height=32,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            corner_radius=6,
            command=self._on_download_press
        )
        self.download_btn.pack(side="top", pady=2)

        self.open_file_btn = ctk.CTkButton(
            self.action_frame,
            text="📁 В папке",
            width=105,
            height=26,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLORS["badge_bg"],
            hover_color=COLORS["card_hover"],
            corner_radius=6,
            command=self._on_open_file
        )

        # 3. Center: Track Details & Badges (fills remaining width)
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=8)

        # Line 1: Title + Badges
        self.title_row = ctk.CTkFrame(self.info_frame, fg_color="transparent", height=24)
        self.title_row.pack(fill="x", anchor="w")

        clean_title = self.track.title[:55]
        self.title_label = ctk.CTkLabel(
            self.title_row,
            text=clean_title,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.title_label.pack(side="left", padx=(0, 6))

        # Quality Badge
        badge_bg, badge_fg, badge_text = self._get_badge_info()
        self.badge_label = ctk.CTkLabel(
            self.title_row,
            text=f" {badge_text} ",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            fg_color=badge_bg,
            text_color=badge_fg,
            corner_radius=4,
            height=18
        )
        self.badge_label.pack(side="left", padx=2)

        # Source Badge
        source_icon = self._get_source_icon()
        self.source_label = ctk.CTkLabel(
            self.title_row,
            text=f" {source_icon} {self.track.source} ",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            fg_color=COLORS["badge_bg"],
            text_color=COLORS["text_secondary"],
            corner_radius=4,
            height=18
        )
        self.source_label.pack(side="left", padx=2)

        # Line 2: Artist • Album • Year • Duration
        album_str = f" • 💿 {self.track.album}" if self.track.album else ""
        year_str = f" ({self.track.year})" if self.track.year else ""
        dur_str = f" • ⏱ {self.track.duration_str}" if self.track.duration > 0 else ""
        sub_text = f"👤 {self.track.artist}{album_str}{year_str}{dur_str}"

        self.subtitle_label = ctk.CTkLabel(
            self.info_frame,
            text=sub_text[:85],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLORS["text_secondary"],
            anchor="w"
        )
        self.subtitle_label.pack(fill="x", anchor="w", pady=(1, 0))

        # Line 3: Slim Progress Bar & Status (hidden by default)
        self.status_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent", height=14)
        
        self.progress_bar = ctk.CTkProgressBar(
            self.status_frame,
            height=4,
            fg_color=COLORS["input_bg"],
            progress_color=COLORS["accent_primary"],
            corner_radius=2
        )
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLORS["text_muted"],
            anchor="w"
        )

    def _get_badge_info(self):
        tier = self.track.quality_tier
        if tier == QualityTier.HI_RES_24BIT:
            return (COLORS["accent_gold_bg"], COLORS["accent_gold"], "✦ Hi-Res 24-bit")
        elif tier == QualityTier.LOSSLESS_FLAC:
            return (COLORS["accent_flac_bg"], COLORS["accent_flac"], "✦ FLAC Lossless")
        elif tier == QualityTier.LOSSLESS_ALAC:
            return (COLORS["accent_alac_bg"], COLORS["accent_alac"], "✦ ALAC Lossless")
        elif self.track.is_lossless:
            return (COLORS["accent_flac_bg"], COLORS["accent_flac"], "✦ Lossless")
        else:
            return (COLORS["badge_bg"], COLORS["accent_alac"], "✦ HQ Stream")

    def _get_source_icon(self) -> str:
        src = (self.track.source or "").lower()
        if "deezer" in src:
            return "🟣"
        elif "apple" in src:
            return "🍎"
        elif "archive" in src:
            return "🏛"
        elif "stream" in src or "hq" in src:
            return "⚡"
        return "🎵"

    def _bind_hover_effects(self):
        def _on_enter(event):
            if not self.is_downloading:
                self.configure(fg_color=COLORS["card_hover"], border_color=COLORS["border_focus"])

        def _on_leave(event):
            if not self.is_downloading:
                self.configure(fg_color=COLORS["card_bg"], border_color=COLORS["border"])

        self.bind("<Enter>", _on_enter)
        self.bind("<Leave>", _on_leave)

    def _load_cover_cached(self):
        url = self.track.cover_url
        if not url:
            return

        if url in _IMAGE_CACHE:
            self.cover_label.configure(image=_IMAGE_CACHE[url], text="")
            return

        def _fetch():
            try:
                resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    img_data = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                    img_data = img_data.resize((50, 50), Image.Resampling.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(50, 50))
                    _IMAGE_CACHE[url] = ctk_img
                    self.after(0, lambda: self.cover_label.configure(image=ctk_img, text=""))
            except Exception:
                pass

        _IMAGE_POOL.submit(_fetch)

    def _on_download_press(self):
        if self.is_downloading:
            return
        self.is_downloading = True
        self.configure(border_color=COLORS["accent_primary"])
        self.download_btn.configure(
            state="disabled",
            text="Загрузка...",
            fg_color=COLORS["badge_bg"],
            text_color=COLORS["text_secondary"]
        )
        
        # Replace subtitle with progress bar for ultra clean compact look
        self.subtitle_label.pack_forget()
        self.status_frame.pack(fill="x", expand=True, pady=(2, 0))
        self.progress_bar.pack(fill="x", expand=True, pady=(0, 2))
        self.status_label.pack(fill="x", expand=True)
        
        self.on_download_click(self.track, self)

    def update_progress(self, fraction: float, message: str):
        def _update():
            self.progress_bar.set(fraction)
            self.status_label.configure(text=message)
            if fraction >= 1.0:
                self.is_downloading = False
                self.configure(border_color=COLORS["accent_success"])
                self.progress_bar.configure(progress_color=COLORS["accent_success"])
                self.download_btn.configure(
                    state="normal",
                    text="✓ Скачано",
                    fg_color=COLORS["accent_success"],
                    hover_color=COLORS["accent_success_hover"],
                    text_color="#FFFFFF"
                )
                self.status_label.configure(text=message, text_color=COLORS["accent_success"])
                self.download_btn.pack_forget()
                self.open_file_btn.pack(side="top", pady=2)
        self.after(0, _update)

    def set_downloaded_path(self, path: str):
        self.downloaded_file_path = path

    def _on_open_file(self):
        if self.downloaded_file_path and os.path.exists(self.downloaded_file_path):
            if os.name == "nt":
                subprocess.run(f'explorer /select,"{os.path.normpath(self.downloaded_file_path)}"')
            else:
                subprocess.run(["xdg-open", os.path.dirname(self.downloaded_file_path)])
        else:
            download_dir = os.path.dirname(self.downloaded_file_path) if self.downloaded_file_path else None
            if download_dir and os.path.exists(download_dir):
                if os.name == "nt":
                    os.startfile(download_dir)
                else:
                    subprocess.run(["xdg-open", download_dir])

    def set_error(self, err_msg: str):
        def _err():
            self.is_downloading = False
            self.configure(border_color=COLORS["accent_error"])
            self.progress_bar.configure(progress_color=COLORS["accent_error"])
            self.download_btn.configure(
                state="normal",
                text="Повторить",
                fg_color=COLORS["accent_error"],
                hover_color="#DC2626",
                text_color="#FFFFFF"
            )
            self.status_label.configure(text=f"Ошибка: {err_msg[:45]}", text_color=COLORS["accent_error"])
        self.after(0, _err)
