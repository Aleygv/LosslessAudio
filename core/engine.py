"""
Main Search & Download Engine for Lossless Audio Grabber.
Aggregates True Studio Lossless sources (Archive.org FLAC, Deezer/Qobuz/Tidal, Web Lossless).
Handles multi-threaded searches, audio conversion, metadata tagging, and automated spectrum verification.
"""
import os
import tempfile
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Optional, Tuple

from core.models import TrackInfo, QualityTier
from core.audio import convert_audio
from core.metadata import tag_audio_file
from core.resolver import resolve_and_download_full_stream
from core.spectrum_analyzer import analyze_audio_spectrum, SpectrumResult

from sources.base import BaseSource
from sources.music_search_resolver import DirectLosslessSource
from sources.deezer_source import DeezerSource
from sources.archive_source import ArchiveSource
from sources.web_source import WebLosslessSource
from sources.fallback_source import HighQualityStreamSource

logger = logging.getLogger(__name__)


class MusicSearchEngine:
    def __init__(self):
        self.sources: List[BaseSource] = [
            ArchiveSource(),
            DeezerSource(),
            DirectLosslessSource(),
            WebLosslessSource(),
            HighQualityStreamSource(),
        ]

    def search_all(
        self,
        query: str,
        limit_per_source: int = 4,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> List[TrackInfo]:
        """
        Executes parallel search across all Lossless audio sources.
        Returns a sorted, deduplicated list of TrackInfo objects.
        """
        all_results: List[TrackInfo] = []
        seen_keys = set()

        if status_callback:
            status_callback(f"Поиск «{query}» во всех Lossless источниках...")

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
                        for track in res:
                            key = f"{track.artist.lower().strip()}_{track.title.lower().strip()}_{track.quality_tier.value}"
                            if key not in seen_keys:
                                seen_keys.add(key)
                                all_results.append(track)
                        if status_callback:
                            status_callback(f"Найдено {len(res)} треков в {source.name}")
                except Exception as e:
                    logger.debug(f"Error searching {source.name}: {e}")

        # Sort: Hi-Res 24-bit first, then FLAC/ALAC lossless, then HQ stream
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
        target_format: str = "flac",  # "alac" or "flac"
        progress_callback: Optional[Callable[[float, str, Optional[str]], None]] = None
    ) -> Tuple[str, SpectrumResult]:
        """
        Downloads the full-length track, converts to target format (ALAC .m4a or FLAC .flac),
        embeds full metadata and artwork, and verifies frequency spectrum.
        Returns: (final_file_path, SpectrumResult)
        """
        os.makedirs(download_dir, exist_ok=True)
        target_format = target_format.lower()
        target_ext = ".m4a" if target_format == "alac" else ".flac"

        with tempfile.TemporaryDirectory() as temp_dir:
            if progress_callback:
                progress_callback(0.05, f"Подготовка: {track.artist} - {track.title}", None)

            # 1. Download master audio stream
            if "archive.org" in (track.download_url or "").lower() and track.download_url.lower().endswith(".flac"):
                source_instance = ArchiveSource()
                raw_file = source_instance.download_track(track, temp_dir, lambda f, m: progress_callback(f, m, None) if progress_callback else None)
            elif track.source == "HQ Audio Stream" and track.download_url:
                source_instance = HighQualityStreamSource()
                raw_file = source_instance.download_track(track, temp_dir, lambda f, m: progress_callback(f, m, None) if progress_callback else None)
            else:
                raw_file = resolve_and_download_full_stream(track, temp_dir, lambda f, m: progress_callback(f, m, None) if progress_callback else None)

            if not os.path.exists(raw_file):
                raise RuntimeError("Скачанный аудиопоток не найден.")

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
                progress_callback(0.85, f"Кодирование в {target_format.upper()}...", None)

            converted_path = convert_audio(raw_file, final_path, target_format=target_format)

            # 3. Metadata & Cover tagging
            if progress_callback:
                progress_callback(0.92, "Вшивание официальных метаданных и обложки...", None)

            tag_audio_file(converted_path, track)

            # 4. Automatic FFT Lossless Spectrum Analysis
            if progress_callback:
                progress_callback(0.96, "Анализ частотного спектра (FFT)...", None)

            spectrum_result = analyze_audio_spectrum(converted_path, generate_image=True)

            if progress_callback:
                progress_callback(1.0, f"✓ {spectrum_result.verdict}", spectrum_result.spectrogram_path)

            return converted_path, spectrum_result
