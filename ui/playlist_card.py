"""
Playlist card widget with cover art, track count badge, and expand button with caching.
"""
import io
import requests
from concurrent.futures import ThreadPoolExecutor
import customtkinter as ctk
from PIL import Image
from typing import Callable, Optional
from core.models import TrackInfo
from ui.styles import COLORS, FONT_FAMILY

_PLAYLIST_COVER_CACHE = {}
_PLAYLIST_POOL = ThreadPoolExecutor(max_workers=6)


class PlaylistCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        playlist_info: TrackInfo,
        on_open_click: Optional[Callable[[TrackInfo], None]] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLORS["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs
        )
        self.playlist = playlist_info
        self.on_open_click = on_open_click
        self._build_ui()
        self._load_cover_cached()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Cover Art
        self.cover_label = ctk.CTkLabel(
            self,
            text="📁",
            width=58,
            height=58,
            font=ctk.CTkFont(family=FONT_FAMILY, size=24),
            fg_color=COLORS["badge_bg"],
            corner_radius=8
        )
        self.cover_label.grid(row=0, column=0, rowspan=2, padx=(10, 12), pady=10, sticky="nsw")

        # 2. Title & Info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, padx=(0, 10), pady=(10, 2), sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            info_frame,
            text=self.playlist.title,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        title_lbl.pack(fill="x", anchor="w")

        artist_lbl = ctk.CTkLabel(
            info_frame,
            text=self.playlist.artist,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLORS["text_secondary"],
            anchor="w"
        )
        artist_lbl.pack(fill="x", anchor="w")

        # 3. Badges Row
        badge_frame = ctk.CTkFrame(self, fg_color="transparent")
        badge_frame.grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="w")

        count_text = self.playlist.album if self.playlist.album else "Плейлист"
        count_badge = ctk.CTkLabel(
            badge_frame,
            text=f"🎵 {count_text}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLORS["accent_primary"],
            fg_color=COLORS["badge_bg"],
            corner_radius=4,
            padx=8,
            pady=2
        )
        count_badge.pack(side="left", padx=(0, 6))

        # 4. Open Button
        self.open_btn = ctk.CTkButton(
            self,
            text="📂 Открыть треки",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            width=130,
            height=34,
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            corner_radius=6,
            command=self._on_open_press
        )
        self.open_btn.grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=10, sticky="e")

    def _on_open_press(self):
        if self.on_open_click:
            self.on_open_click(self.playlist)

    def _load_cover_cached(self):
        url = self.playlist.cover_url
        if not url:
            return

        if url in _PLAYLIST_COVER_CACHE:
            self.cover_label.configure(image=_PLAYLIST_COVER_CACHE[url], text="")
            return

        def _fetch():
            try:
                resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    img_data = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                    img_data = img_data.resize((58, 58), Image.Resampling.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(58, 58))
                    _PLAYLIST_COVER_CACHE[url] = ctk_img
                    self.after(0, lambda: self.cover_label.configure(image=ctk_img, text=""))
            except Exception:
                pass

        _PLAYLIST_POOL.submit(_fetch)
