"""
High Quality / Hi-Res Stream Fallback Source using yt-dlp.
Finds the highest bitrate original audio stream (Opus 160-256kbps / AAC / FLAC)
and packages it cleanly into lossless ALAC or FLAC containers with tags.
"""
import os
import glob
import logging
from typing import List, Callable, Optional
from sources.base import BaseSource
from core.models import TrackInfo, QualityTier
from core.audio import get_ffmpeg_path

logger = logging.getLogger(__name__)


class HighQualityStreamSource(BaseSource):
    @property
    def name(self) -> str:
        return "HQ / Hi-Res Stream"

    def search(self, query: str, limit: int = 5) -> List[TrackInfo]:
        results = []
        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "default_search": f"ytsearch{limit}",
                "skip_download": True,
                "socket_timeout": 2.5,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "ios", "web"]
                    }
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                entries = info.get("entries", []) if info else []

                for entry in entries:
                    if not entry:
                        continue
                    video_id = entry.get("id")
                    title = entry.get("title", "")
                    uploader = entry.get("uploader") or entry.get("channel", "Unknown Artist")
                    duration = entry.get("duration", 0)
                    thumbnails = entry.get("thumbnails", [])
                    cover_url = thumbnails[-1].get("url") if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                    artist = uploader
                    if " - " in title:
                        parts = title.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()

                    for tag in ["(Official Audio)", "(Official Music Video)", "[Official Video]", "(Audio)", "[HQ]", "(Lossless Audio)"]:
                        title = title.replace(tag, "").strip()

                    track = TrackInfo(
                        id=f"ytdl_{video_id}",
                        title=title,
                        artist=artist,
                        album="Master Collection",
                        duration=int(duration or 0),
                        cover_url=cover_url,
                        source="HQ Audio Stream",
                        quality_label="HQ Stream -> Lossless",
                        quality_tier=QualityTier.HIGH_QUALITY,
                        is_lossless=False,
                        download_url=f"https://www.youtube.com/watch?v={video_id}",
                        extra_data={"video_id": video_id}
                    )
                    results.append(track)
        except Exception as e:
            logger.debug(f"HighQualityStreamSource search notice: {e}")
        return results

    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        import yt_dlp
        from core.resolver import resolve_and_download_full_stream

        dest_template = os.path.join(temp_dir, f"raw_{track.id}.%(ext)s")
        ffmpeg_exe = get_ffmpeg_path()

        def ytdl_hook(d):
            if d.get("status") == "downloading" and progress_callback:
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                if total_bytes > 0:
                    fraction = min(0.1 + 0.75 * (downloaded / total_bytes), 0.85)
                    progress_callback(fraction, "Скачивание полного аудиопотока...")
            elif d.get("status") == "finished" and progress_callback:
                progress_callback(0.88, "Обработка аудиопотока...")

        ydl_opts = {
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
            ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_exe)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([track.download_url])

            candidates = glob.glob(os.path.join(temp_dir, f"raw_{track.id}.*"))
            if candidates:
                if progress_callback:
                    progress_callback(0.92, "Аудиопоток готов")
                return candidates[0]
        except Exception as e:
            logger.warning(f"Direct stream download failed for {track.title}: {e}. Resolving candidate...")

        # Automatic fallback to full resolver
        return resolve_and_download_full_stream(track, temp_dir, progress_callback)
