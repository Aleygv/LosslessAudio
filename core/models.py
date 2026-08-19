"""
Data models for track metadata, quality levels, and search results.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class QualityTier(Enum):
    HI_RES_24BIT = "Hi-Res 24-bit"
    LOSSLESS_FLAC = "FLAC Lossless"
    LOSSLESS_ALAC = "ALAC Lossless"
    HIGH_QUALITY = "HQ Audio"
    UNKNOWN = "Unknown"


@dataclass
class TrackInfo:
    id: str
    title: str
    artist: str
    album: str = "Single"
    duration: int = 0  # in seconds
    year: str = ""
    track_number: int = 1
    cover_url: str = ""
    source: str = ""
    quality_label: str = "FLAC Lossless"
    quality_tier: QualityTier = QualityTier.LOSSLESS_FLAC
    is_lossless: bool = True
    download_url: str = ""
    bitrate: Optional[str] = None
    sample_rate: Optional[str] = None
    bit_depth: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_str(self) -> str:
        if not self.duration or self.duration <= 0:
            return "--:--"
        mins = self.duration // 60
        secs = self.duration % 60
        return f"{mins}:{secs:02d}"

    @property
    def clean_filename_base(self) -> str:
        """Safe filename without invalid characters."""
        raw = f"{self.artist} - {self.title}".strip()
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            raw = raw.replace(char, "_")
        return raw[:150]  # Avoid extremely long paths
