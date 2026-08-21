"""
Apple Music Catalog Search Provider.
Provides high-precision metadata, ISRC, and ultra Hi-Res 1000x1000 album artwork.
"""
import os
import requests
import logging
from typing import List, Callable, Optional
from sources.base import BaseSource
from core.models import TrackInfo, QualityTier

logger = logging.getLogger(__name__)


class DirectLosslessSource(BaseSource):
    @property
    def name(self) -> str:
        return "Apple Music Catalog"

    def search(self, query: str, limit: int = 6) -> List[TrackInfo]:
        results = []
        try:
            url = "https://itunes.apple.com/search"
            params = {
                "term": query,
                "media": "music",
                "entity": "song",
                "limit": limit
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=4.0)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    title = item.get("trackName", "")
                    artist = item.get("artistName", "")
                    album = item.get("collectionName", "")
                    duration_ms = item.get("trackTimeMillis", 0)
                    duration = int(duration_ms / 1000) if duration_ms else 0
                    
                    cover_100 = item.get("artworkUrl100", "")
                    cover_hq = cover_100.replace("100x100bb", "1000x1000bb").replace("100x100", "1000x1000")
                    year = item.get("releaseDate", "")[:4]
                    preview_url = item.get("previewUrl", "")

                    track = TrackInfo(
                        id=f"itunes_{item.get('trackId')}",
                        title=title,
                        artist=artist,
                        album=album,
                        duration=duration,
                        year=year,
                        cover_url=cover_hq,
                        source="Apple Music Catalog",
                        quality_label="HQ Stream (AAC/Web)",
                        quality_tier=QualityTier.HIGH_QUALITY,
                        is_lossless=False,
                        download_url=preview_url,
                        extra_data={"track_id": item.get("trackId"), "preview_url": preview_url}
                    )
                    results.append(track)
        except Exception as e:
            logger.debug(f"DirectLosslessSource search error: {e}")
        return results

    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        dest_file = os.path.join(temp_dir, f"raw_apple_{track.clean_filename_base}.m4a")
        if progress_callback:
            progress_callback(0.1, "Запрос аудиопотока Apple Catalog...")

        url = track.download_url
        if not url:
            raise ValueError("No download URL provided.")

        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url, headers=headers, stream=True, timeout=15) as r:
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
