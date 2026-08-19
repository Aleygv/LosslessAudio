"""
Search and Download Engine orchestrator.
Manages multi-threaded search across all sources and coordinates audio pipeline.
"""
import os
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Optional

from core.models import TrackInfo, QualityTier
from core.audio import convert_audio, probe_audio
from core.metadata import tag_audio_file
from core.resolver import resolve_and_download_full_stream
from sources.deezer_source import DeezerSource
from sources.archive_source import ArchiveSource
from sources.music_search_resolver import DirectLosslessSource
from sources.web_source import WebLosslessSource
from sources.fallback_source import HighQualityStreamSource
from sources.base import BaseSource

logger = logging.getLogger(__name__)


class MusicSearchEngine:
    def __init__(self):
        self.sources: List[BaseSource] = [
            DirectLosslessSource(),
            DeezerSource(),
            ArchiveSource(),
            WebLosslessSource(),
            HighQualityStreamSource(),
        ]

    def search_all(
        self,
        query: str,
        limit_per_source: int = 8,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> List[TrackInfo]:
        """
        Runs parallel search across all sources and returns unified list of tracks.
        """
        all_results: List[TrackInfo] = []
        if not query or not query.strip():
            return all_results

        query = query.strip()
        if status_callback:
            status_callback(f"Поиск '{query}' по всем источникам...")

        with ThreadPoolExecutor(max_workers=len(self.sources)) as executor:
            future_to_source = {
                executor.submit(source.search, query, limit_per_source): source
                for source in self.sources
            }

            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    res = future.result()
                    if res:
                        all_results.extend(res)
                        if status_callback:
                            status_callback(f"Найдено {len(res)} треков в {source.name}")
                except Exception as e:
                    logger.debug(f"Error searching {source.name}: {e}")

        # Sort results: Hi-Res 24-bit first, then FLAC/ALAC lossless, then HQ stream
        def sort_key(track: TrackInfo):
            tier_priority = {
                QualityTier.HI_RES_24BIT: 0,
                QualityTier.LOSSLESS_ALAC: 1,
                QualityTier.LOSSLESS_FLAC: 2,
                QualityTier.HIGH_QUALITY: 3,
                QualityTier.UNKNOWN: 4
            }
            return (tier_priority.get(track.quality_tier, 5), -track.duration)

        all_results.sort(key=sort_key)
        return all_results

    def download_and_process(
        self,
        track: TrackInfo,
        download_dir: str,
        target_format: str = "alac",  # "alac" or "flac"
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Downloads the full-length track, converts to target format (ALAC .m4a or FLAC .flac),
        and embeds full ID3/Vorbis/MP4 metadata and cover artwork.
        """
        os.makedirs(download_dir, exist_ok=True)
        target_format = target_format.lower()
        target_ext = ".m4a" if target_format == "alac" else ".flac"

        with tempfile.TemporaryDirectory() as temp_dir:
            if progress_callback:
                progress_callback(0.05, f"Подготовка: {track.artist} - {track.title}")

            # 1. Download full audio stream
            # If Archive.org with direct .flac link, download directly
            if "archive.org" in (track.download_url or "").lower() and track.download_url.lower().endswith(".flac"):
                source_instance = ArchiveSource()
                raw_file = source_instance.download_track(track, temp_dir, progress_callback)
            else:
                # Use Full-Length Audio Resolver to ensure full song is downloaded (not a 30s preview)
                raw_file = resolve_and_download_full_stream(track, temp_dir, progress_callback)

            if not os.path.exists(raw_file):
                raise RuntimeError("Downloaded raw audio file does not exist.")

            # 2. Conversion to ALAC or FLAC
            final_filename = f"{track.clean_filename_base}{target_ext}"
            final_path = os.path.join(download_dir, final_filename)

            # Avoid collision
            counter = 1
            base_name_without_ext = track.clean_filename_base
            while os.path.exists(final_path):
                final_path = os.path.join(download_dir, f"{base_name_without_ext} ({counter}){target_ext}")
                counter += 1

            if progress_callback:
                progress_callback(0.85, f"Кодирование в {target_format.upper()}...")

            converted_path = convert_audio(raw_file, final_path, target_format=target_format)

            # 3. Metadata & Cover tagging
            if progress_callback:
                progress_callback(0.92, "Вшивание официальных метаданных и обложки...")

            tag_audio_file(converted_path, track)

            if progress_callback:
                progress_callback(1.0, f"Готово! Сохранено: {os.path.basename(converted_path)}")

            return converted_path
