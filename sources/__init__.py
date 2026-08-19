from sources.base import BaseSource
from sources.deezer_source import DeezerSource
from sources.archive_source import ArchiveSource
from sources.music_search_resolver import DirectLosslessSource
from sources.web_source import WebLosslessSource
from sources.fallback_source import HighQualityStreamSource

__all__ = [
    "BaseSource",
    "DeezerSource",
    "ArchiveSource",
    "DirectLosslessSource",
    "WebLosslessSource",
    "HighQualityStreamSource",
]
