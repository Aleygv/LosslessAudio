"""
Internet Archive (Archive.org) Lossless FLAC Source.
Searches millions of digitized albums, concerts, and lossless soundboard/vinyl recordings.
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
        return "Archive.org Lossless"

    def search(self, query: str, limit: int = 4) -> List[TrackInfo]:
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
            resp = requests.get(search_url, params=params, headers=headers, timeout=2.5)
            if resp.status_code != 200:
                return results

            docs = resp.json().get("response", {}).get("docs", [])
            
            def fetch_doc(doc):
                doc_results = []
                identifier = doc.get("identifier")
                if not identifier:
                    return doc_results
                try:
                    meta_url = f"https://archive.org/metadata/{identifier}"
                    meta_resp = requests.get(meta_url, headers=headers, timeout=2.0)
                    if meta_resp.status_code == 200:
                        meta_json = meta_resp.json()
                        files = meta_json.get("files", [])
                        server = meta_json.get("server")
                        dir_path = meta_json.get("dir")
                        server_url = f"https://{server}{dir_path}" if server and dir_path else f"https://archive.org/download/{identifier}"
                        flac_files = [f for f in files if f.get("name", "").lower().endswith(".flac")]
                        cover_url = f"https://archive.org/services/img/{identifier}"
                        creator = doc.get("creator", "Unknown Artist")
                        album_title = doc.get("album") or doc.get("title") or "Archive Master"
                        year = int(doc.get("year", 0)) if str(doc.get("year", "")).isdigit() else None

                        for f in flac_files[:2]:
                            fname = f.get("name", "")
                            t_title = f.get("title") or fname.rsplit(".", 1)[0]
                            dur = int(float(f.get("length", 0)))
                            dl_link = f"{server_url}/{fname}"
                            doc_results.append(
                                TrackInfo(
                                    id=f"ia_{identifier}_{fname}",
                                    title=t_title,
                                    artist=creator,
                                    album=album_title,
                                    year=year,
                                    duration=dur,
                                    cover_url=cover_url,
                                    source="Archive.org FLAC",
                                    quality_label="Lossless FLAC",
                                    quality_tier=QualityTier.LOSSLESS_FLAC,
                                    is_lossless=True,
                                    download_url=dl_link
                                )
                            )
                except Exception:
                    pass
                return doc_results

            with ThreadPoolExecutor(max_workers=min(len(docs) or 1, 4)) as pool:
                for res_list in pool.map(fetch_doc, docs):
                    results.extend(res_list)

        except Exception as e:
            logger.debug(f"ArchiveSource search notice: {e}")
        return results[:limit]

    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        if not track.download_url:
            raise RuntimeError(f"No download URL available for {track.title}")

        dest_file = os.path.join(temp_dir, f"{track.id}.flac")
        if progress_callback:
            progress_callback(0.1, "Загрузка прямого FLAC с Archive.org...")

        resp = requests.get(track.download_url, stream=True, timeout=30)
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_callback:
                        frac = min(0.1 + 0.75 * (downloaded / total_size), 0.85)
                        progress_callback(frac, f"Скачивание FLAC ({downloaded / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB)...")

        if progress_callback:
            progress_callback(0.88, "FLAC файл успешно получен")
        return dest_file
