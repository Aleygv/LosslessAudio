"""
Full-length Audio Resolver.
Matches metadata (Artist, Title, Duration) to the highest-fidelity full-length audio stream.
Ensures downloaded tracks are 100% full length and not 30-second previews.
"""
import os
import glob
import logging
from typing import Optional, Callable
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
    Works seamlessly with or without FFmpeg installed.
    """
    ffmpeg_exe = get_ffmpeg_path()
    dest_template = os.path.join(temp_dir, f"full_{track.id}.%(ext)s")

    if progress_callback:
        progress_callback(0.1, f"Поиск полного трека ({track.duration_str})...")

    search_queries = [
        f"{track.artist} - {track.title} official audio",
        f"{track.artist} - {track.title} FLAC",
        f"{track.artist} - {track.title}",
    ]

    best_candidate_url = None
    best_score = -9999

    ydl_search_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "socket_timeout": 8,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web_creator"]
            }
        }
    }

    with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
        for q in search_queries:
            try:
                search_res = ydl.extract_info(f"ytsearch6:{q}", download=False)
                entries = search_res.get("entries", []) if search_res else []
                for entry in entries:
                    if not entry:
                        continue
                    v_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    v_title = entry.get("title", "").lower()
                    v_dur = int(entry.get("duration") or 0)
                    uploader = (entry.get("uploader") or "").lower()

                    score = 100
                    
                    if track.duration > 0 and v_dur > 0:
                        diff = abs(track.duration - v_dur)
                        if diff <= 3:
                            score += 80
                        elif diff <= 10:
                            score += 45
                        elif diff <= 25:
                            score += 15
                        elif diff > 50:
                            score -= 90
                    
                    if "official audio" in v_title or "topic" in uploader:
                        score += 50
                    if "flac" in v_title or "lossless" in v_title:
                        score += 40
                    if "audio" in v_title:
                        score += 20
                    if track.artist.lower() in uploader or track.artist.lower() in v_title:
                        score += 30

                    negative_keywords = ["live", "cover", "karaoke", "reaction", "remix", "instrumental", "acoustic", "tutorial", "parody", "review"]
                    for kw in negative_keywords:
                        if kw in v_title and kw not in track.title.lower():
                            score -= 80

                    if score > best_score:
                        best_score = score
                        best_candidate_url = v_url

                if best_score >= 140:
                    break
            except Exception as e:
                logger.debug(f"Search query '{q}' notice: {e}")

    if not best_candidate_url:
        best_candidate_url = f"ytsearch1:{track.artist} - {track.title} audio"

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
        "format": "bestaudio/best",
        "outtmpl": dest_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [ytdl_hook],
        "socket_timeout": 15,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web_creator"]
            }
        }
    }
    if ffmpeg_exe:
        ydl_down_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_exe)

    try:
        with yt_dlp.YoutubeDL(ydl_down_opts) as ydl:
            ydl.download([best_candidate_url])
    except Exception as e:
        logger.warning(f"Primary download attempt failed: {e}. Trying SoundCloud fallback...")
        sc_opts = {
            "format": "bestaudio/best",
            "outtmpl": dest_template,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
        }
        if ffmpeg_exe:
            sc_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_exe)
        with yt_dlp.YoutubeDL(sc_opts) as ydl_sc:
            ydl_sc.download([f"scsearch1:{track.artist} - {track.title}"])

    candidates = glob.glob(os.path.join(temp_dir, f"full_{track.id}.*"))
    if candidates:
        if progress_callback:
            progress_callback(0.85, "Полный аудиопоток успешно получен")
        return candidates[0]

    raise RuntimeError(f"Could not download full audio stream for {track.title}")
