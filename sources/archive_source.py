"""
Internet Archive (Archive.org) Lossless FLAC Source.
Searches millions of digitized albums, soundboard recordings, and vinyl rips.
Returns 100% genuine uncompressed FLAC audio files.
"""
import os
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Callable, Optional
from sources.base import BaseSource
from core.models import TrackInfo, QualityTier

logger = logging.getLogger(__name__)


class ArchiveSource(BaseSource):
    @property
    def name(self) -> str:
        return "Archive.org FLAC"

    def search(self, query: str, limit: int = 5) -> List[TrackInfo]:
        results = []
        try:
            search_url = "https://archive.org/advancedsearch.php"
            params = {
                "q": f"{query.strip()} AND mediatype:(audio)",
                "fl[]": "identifier,title,creator,album,year,downloads,format",
                "sort[]": "downloads desc",
                "rows": limit * 2,
                "output": "json"
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(search_url, params=params, headers=headers, timeout=3.5)
            if resp.status_code != 200:
                return results

            docs = resp.json().get("response", {}).get("docs", [])
            for doc in docs:
                identifier = doc.get("identifier")
                if not identifier:
                    continue
                
                formats = doc.get("format", [])
                if isinstance(formats, str):
                    formats = [formats]
                
                # Check if this item has FLAC audio
                has_flac = any("flac" in str(f).lower() for f in formats)
                title = doc.get("title") or identifier
                creator = doc.get("creator") or "Archive Audio"
                album = doc.get("album") or "Archive Lossless"
                year = int(doc.get("year", 0)) if str(doc.get("year", "")).isdigit() else None
                cover_url = f"https://archive.org/services/img/{identifier}"
                dl_link = f"https://archive.org/download/{identifier}/{identifier}.flac"

                if has_flac:
                    results.append(
                        TrackInfo(
                            id=f"ia_{identifier}",
                            title=title,
                            artist=creator,
                            album=album,
                            year=year,
                            duration=0,
                            cover_url=cover_url,
                            source="Archive.org FLAC",
                            quality_label="True FLAC Lossless",
                            quality_tier=QualityTier.LOSSLESS_FLAC,
                            is_lossless=True,
                            download_url=dl_link,
                            extra_data={"identifier": identifier}
                        )
                    )
                if len(results) >= limit:
                    break

        except Exception as e:
            logger.debug(f"ArchiveSource search notice: {e}")
        return results

    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        identifier = track.extra_data.get("identifier") if track.extra_data else None
        if not identifier:
            identifier = track.id.replace("ia_", "")

        dest_file = os.path.join(temp_dir, f"ia_{track.clean_filename_base}.flac")
        if progress_callback:
            progress_callback(0.1, "Запрос файлов Archive.org...")

        # Get the exact FLAC file name from metadata
        meta_url = f"https://archive.org/metadata/{identifier}"
        headers = {"User-Agent": "Mozilla/5.0"}
        flac_url = track.download_url

        try:
            r_meta = requests.get(meta_url, headers=headers, timeout=5)
            if r_meta.status_code == 200:
                files = r_meta.json().get("files", [])
                for f in files:
                    if f.get("name", "").lower().endswith(".flac"):
                        server = r_meta.json().get("server")
                        dir_path = r_meta.json().get("dir")
                        if server and dir_path:
                            flac_url = f"https://{server}{dir_path}/{f.get('name')}"
                        else:
                            flac_url = f"https://archive.org/download/{identifier}/{f.get('name')}"
                        break
        except Exception:
            pass

        if progress_callback:
            progress_callback(0.2, "Загрузка оригинального FLAC аудиопотока...")

        with requests.get(flac_url, headers=headers, stream=True, timeout=30) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and progress_callback:
                            fraction = min(0.2 + 0.7 * (downloaded / total_size), 0.9)
                            mb_cur = downloaded / (1024 * 1024)
                            mb_tot = total_size / (1024 * 1024)
                            progress_callback(fraction, f"Скачивание FLAC ({mb_cur:.1f}/{mb_tot:.1f} MB)...")

        if progress_callback:
            progress_callback(0.95, "Оригинальный FLAC скачан")
        return dest_file
