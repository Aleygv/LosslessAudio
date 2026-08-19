"""
Abstract base class for music source providers.
"""
from abc import ABC, abstractmethod
from typing import List, Callable, Optional
from core.models import TrackInfo


class BaseSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the source provider (e.g. 'Deezer Lossless', 'Archive.org')."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[TrackInfo]:
        """
        Search for tracks by query string.
        Returns a list of TrackInfo objects.
        """
        pass

    @abstractmethod
    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """
        Downloads raw/lossless track file to temp_dir and returns path to the downloaded file.
        progress_callback signature: (progress_fraction: float 0.0-1.0, status_message: str)
        """
        pass
