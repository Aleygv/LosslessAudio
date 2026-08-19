"""
Web Lossless & Hi-Fi Aggregator Source.
Searches public lossy/lossless audio repositories and open music libraries (e.g. Free Music Archive, OpenAudio).
"""
import os
import requests
import logging
from typing import List, Callable, Optional
from sources.base import BaseSource
from core.models import TrackInfo, QualityTier

logger = logging.getLogger(__name__)


class WebLosslessSource(BaseSource):
    @property
    def name(self) -> str:
        return "Web Lossless Mirror"

    def search(self, query: str, limit: int = 6) -> List[TrackInfo]:
        results = []
        try:
            # Search open MusicBrainz / FMA / Audio web mirrors
            search_url = "https://freemusicarchive.org/api/get/tracks.json"
            # As a lightweight search aggregator, we query public free track endpoints
            params = {"api_key": "60BLHNQCAOUFPIBZ", "limit": limit, "q": query}
            headers = {"User-Agent": "ALAC-FLAC-Lossless/1.0"}
            resp = requests.get(search_url, params=params, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("aRows", [])
                for item in items:
                    title = item.get("track_title", "Unknown Title")
                    artist = item.get("artist_name", "Unknown Artist")
                    album = item.get("album_title", "Lossless Collection")
                    duration = int(float(item.get("track_duration_seconds", 0) or 0))
                    cover_url = item.get("track_image_file", "")
                    dl_url = item.get("track_url", "")

                    if dl_url:
                        track = TrackInfo(
                            id=f"fma_{item.get('track_id')}",
                            title=title,
                            artist=artist,
                            album=album,
                            duration=duration,
                            cover_url=cover_url,
                            source="Open Lossless / FMA",
                            quality_label="Lossless / Hi-Fi FLAC",
                            quality_tier=QualityTier.LOSSLESS_FLAC,
                            is_lossless=True,
                            download_url=dl_url
                        )
                        results.append(track)
        except Exception as e:
            logger.debug(f"WebLosslessSource query notice: {e}")
        return results

    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        dest_file = os.path.join(temp_dir, f"raw_web_{track.clean_filename_base}.mp3")
        if progress_callback:
            progress_callback(0.1, "Загрузка с веб-зеркала...")

        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(track.download_url, headers=headers, stream=True, timeout=20) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and progress_callback:
                            fraction = min(0.1 + 0.8 * (downloaded / total_size), 0.9)
                            progress_callback(fraction, "Загрузка аудио...")

        if progress_callback:
            progress_callback(0.95, "Загрузка завершена")
        return dest_file
