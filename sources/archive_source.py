"""
Internet Archive (Archive.org) Lossless FLAC Source.
Searches millions of digitized albums, concerts, and lossless soundboard/vinyl recordings.
"""
import os
import requests
import logging
from typing import List, Callable, Optional
from sources.base import BaseSource
from core.models import TrackInfo, QualityTier

logger = logging.getLogger(__name__)


class ArchiveSource(BaseSource):
    @property
    def name(self) -> str:
        return "Archive.org Lossless"

    def search(self, query: str, limit: int = 5) -> List[TrackInfo]:
        results = []
        try:
            search_url = "https://archive.org/advancedsearch.php"
            q_str = f'({query}) AND mediatype:(audio) AND format:(FLAC)'
            params = {
                "q": q_str,
                "fl[]": "identifier,title,creator,album,year,downloads",
                "sort[]": "downloads desc",
                "rows": limit,
                "page": 1,
                "output": "json"
            }
            headers = {"User-Agent": "ALAC-FLAC-Lossless/1.0"}
            resp = requests.get(search_url, params=params, headers=headers, timeout=4.0)
            if resp.status_code != 200:
                return results

            docs = resp.json().get("response", {}).get("docs", [])
            for doc in docs:
                identifier = doc.get("identifier")
                if not identifier:
                    continue

                meta_url = f"https://archive.org/metadata/{identifier}"
                meta_resp = requests.get(meta_url, headers=headers, timeout=3.0)
                if meta_resp.status_code != 200:
                    continue

                meta_json = meta_resp.json()
                files = meta_json.get("files", [])
                server = meta_json.get("server")
                dir_path = meta_json.get("dir")
                server_url = f"https://{server}{dir_path}" if server and dir_path else f"https://archive.org/download/{identifier}"

                flac_files = [f for f in files if f.get("name", "").lower().endswith(".flac")]
                if not flac_files:
                    continue

                cover_url = f"https://archive.org/services/img/{identifier}"
                creator = doc.get("creator", "Unknown Artist")
                if isinstance(creator, list):
                    creator = ", ".join(creator)

                for flac_f in flac_files[:2]:
                    track_name = flac_f.get("title") or flac_f.get("name", "").replace(".flac", "").replace("_", " ")
                    raw_duration = flac_f.get("length", 0)
                    try:
                        duration = int(float(raw_duration))
                    except (ValueError, TypeError):
                        duration = 0

                    download_file_url = f"{server_url}/{flac_f['name']}"
                    is_24bit = "24bit" in download_file_url.lower() or "24-bit" in download_file_url.lower() or "96k" in download_file_url.lower()
                    q_label = "Hi-Res FLAC 24-bit" if is_24bit else "Lossless FLAC 16-bit"
                    tier = QualityTier.HI_RES_24BIT if is_24bit else QualityTier.LOSSLESS_FLAC

                    track = TrackInfo(
                        id=f"ia_{identifier}_{flac_f['name']}",
                        title=track_name,
                        artist=creator,
                        album=doc.get("album") or doc.get("title") or "Archive Audio",
                        duration=duration,
                        year=str(doc.get("year", "")),
                        cover_url=cover_url,
                        source="Archive.org FLAC",
                        quality_label=q_label,
                        quality_tier=tier,
                        is_lossless=True,
                        download_url=download_file_url,
                        extra_data={"identifier": identifier, "filename": flac_f['name']}
                    )
                    results.append(track)
                    if len(results) >= limit:
                        return results

        except Exception as e:
            logger.debug(f"ArchiveSource search notice: {e}")
        return results

    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        if not track.download_url:
            raise ValueError("No download URL provided for Archive track.")

        dest_file = os.path.join(temp_dir, f"raw_archive_{track.clean_filename_base}.flac")
        if progress_callback:
            progress_callback(0.1, "Подключение к Archive.org...")

        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(track.download_url, headers=headers, stream=True, timeout=20) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and progress_callback:
                            fraction = min(0.1 + 0.8 * (downloaded / total_size), 0.9)
                            mb_down = downloaded / (1024 * 1024)
                            mb_tot = total_size / (1024 * 1024)
                            progress_callback(fraction, f"Скачивание FLAC ({mb_down:.1f}/{mb_tot:.1f} MB)...")

        if progress_callback:
            progress_callback(0.95, "Скачивание завершено")
        return dest_file
