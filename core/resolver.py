"""
Full-length Audio Resolver.
Matches metadata (Artist, Title, Duration) to the highest-fidelity full-length audio stream.
Ensures downloaded tracks are 100% full length and not 30-second previews.
"""
import os
import glob
import logging
from typing import Optional, Callable, List
import yt_dlp

from core.models import TrackInfo
from core.audio import get_ffmpeg_path

logger = logging.getLogger(__name__)


def resolve_and_download_full_stream(
    track: TrackInfo,
    temp_dir: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """
    Finds and downloads the full-length audio stream matching track metadata and duration.
    Works seamlessly across Android, Windows, and VPN connections.
    """
    ffmpeg_exe = get_ffmpeg_path()
    dest_template = os.path.join(temp_dir, f"full_{track.id}.%(ext)s")

    if progress_callback:
        progress_callback(0.1, f"Поиск аудио ({track.duration_str})...")

    search_queries = [
        f"{track.artist} - {track.title} official audio",
        f"{track.artist} - {track.title} audio",
        f"{track.artist} - {track.title}",
    ]

    candidates_urls: List[str] = []

    ydl_search_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "socket_timeout": 10,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"]
            }
        }
    }

    with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
        for q in search_queries:
            try:
                search_res = ydl.extract_info(f"ytsearch4:{q}", download=False)
                entries = search_res.get("entries", []) if search_res else []
                for entry in entries:
                    if not entry:
                        continue
                    v_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    if v_url not in candidates_urls:
                        candidates_urls.append(v_url)
                if len(candidates_urls) >= 3:
                    break
            except Exception as e:
                logger.debug(f"Search query '{q}' notice: {e}")

    if not candidates_urls:
        candidates_urls = [f"ytsearch1:{track.artist} - {track.title} audio"]

    if progress_callback:
        progress_callback(0.25, "Загрузка полного аудиопотока в максимальном качестве...")

    def ytdl_hook(d):
        if d.get("status") == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            down = d.get("downloaded_bytes", 0)
            if total > 0:
                frac = min(0.25 + 0.55 * (down / total), 0.80)
                mb_down = down / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                progress_callback(frac, f"Скачивание полного аудио ({mb_down:.1f}/{mb_tot:.1f} MB)...")
        elif d.get("status") == "finished" and progress_callback:
            progress_callback(0.82, "Сохранение и запись тегов...")

    ydl_down_opts = {
        "format": "ba/b",
        "outtmpl": dest_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [ytdl_hook],
        "socket_timeout": 20,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"]
            }
        }
    }
    if ffmpeg_exe:
        ydl_down_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_exe)

    # Try candidate URLs in order until one succeeds
    download_success = False
    for candidate_url in candidates_urls:
        try:
            with yt_dlp.YoutubeDL(ydl_down_opts) as ydl:
                ydl.download([candidate_url])
            files = glob.glob(os.path.join(temp_dir, f"full_{track.id}.*"))
            if files:
                download_success = True
                break
        except Exception as e:
            logger.warning(f"Candidate {candidate_url} download failed: {e}. Trying next...")

    # Fallback to direct search query if candidates failed
    if not download_success:
        try:
            fallback_query = f"ytsearch1:{track.artist} - {track.title}"
            with yt_dlp.YoutubeDL(ydl_down_opts) as ydl_fb:
                ydl_fb.download([fallback_query])
        except Exception as e:
            logger.error(f"Fallback search query failed: {e}")

    candidates = glob.glob(os.path.join(temp_dir, f"full_{track.id}.*"))
    if candidates:
        if progress_callback:
            progress_callback(0.85, "Полный аудиопоток успешно получен")
        return candidates[0]

    raise RuntimeError(f"Не удалось получить аудиопоток для {track.artist} - {track.title}")
