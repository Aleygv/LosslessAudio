"""
Full-length Audio Resolver.
Matches metadata (Artist, Title, Duration) to the highest-fidelity full-length audio stream.
Supports Deezer Hi-Fi FLAC resolving when ARL is available, with resilient audio stream fallback.
"""
import os
import glob
import logging
from typing import Optional, Callable, List
import yt_dlp

from core.models import TrackInfo
from core.audio import get_ffmpeg_path
from config import load_config

logger = logging.getLogger(__name__)


def resolve_and_download_full_stream(
    track: TrackInfo,
    temp_dir: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """
    Finds and downloads the full-length audio stream matching track metadata and duration.
    First attempts Deezer Hi-Fi FLAC if ARL is available, then falls back to multi-client audio stream.
    """
    cfg = load_config()
    arl = cfg.get("deezer_arl", "").strip()

    # 1. If ARL is configured, attempt Deezer Hi-Fi matching first
    if arl:
        try:
            from sources.deezer_source import DeezerSource
            dz_source = DeezerSource()
            query = f"{track.artist} {track.title}"
            dz_results = dz_source.search(query, limit=3)
            if dz_results:
                top_match = dz_results[0]
                if progress_callback:
                    progress_callback(0.2, f"Deezer Hi-Fi FLAC: {top_match.title}")
                dest_file = dz_source.download_track(top_match, temp_dir, progress_callback)
                if os.path.exists(dest_file) and os.path.getsize(dest_file) > 100000:
                    return dest_file
        except Exception as e:
            logger.debug(f"Deezer Hi-Fi auto-match notice: {e}")

    # 2. Resilient Audio Stream Resolver
    ffmpeg_exe = get_ffmpeg_path()
    dest_template = os.path.join(temp_dir, f"full_{track.id}.%(ext)s")

    if progress_callback:
        progress_callback(0.1, f"Поиск аудио: {track.artist} - {track.title}...")

    def ytdl_hook(d):
        if d.get("status") == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            down = d.get("downloaded_bytes", 0)
            if total > 0:
                frac = min(0.25 + 0.55 * (down / total), 0.80)
                mb_down = down / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                progress_callback(frac, f"Скачивание ({mb_down:.1f}/{mb_tot:.1f} MB)...")
        elif d.get("status") == "finished" and progress_callback:
            progress_callback(0.85, "Запись метаданных и сохранение...")

    ydl_down_opts = {
        "format": "ba/b",
        "outtmpl": dest_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [ytdl_hook],
        "socket_timeout": 15,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }
    if ffmpeg_exe:
        ydl_down_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_exe)

    search_targets = [
        f"ytsearch1:{track.artist} - {track.title} official audio",
        f"ytsearch1:{track.artist} - {track.title}",
        f"ytsearch1:{track.title} {track.artist}"
    ]

    for target in search_targets:
        try:
            with yt_dlp.YoutubeDL(ydl_down_opts) as ydl:
                ydl.download([target])
            files = glob.glob(os.path.join(temp_dir, f"full_{track.id}.*"))
            if files:
                return files[0]
        except Exception as e:
            logger.warning(f"Download query '{target}' notice: {e}")

    candidates = glob.glob(os.path.join(temp_dir, f"full_{track.id}.*"))
    if candidates:
        return candidates[0]

    raise RuntimeError(f"Не удалось получить аудиопоток для {track.artist} - {track.title}")
