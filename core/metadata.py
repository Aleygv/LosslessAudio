"""
Metadata tagging module for FLAC and ALAC (M4A) audio files using Mutagen.
Embeds Artist, Title, Album, Track number, Year, and Album Cover Artwork.
"""
import os
import logging
import requests
from typing import Optional
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from core.models import TrackInfo

logger = logging.getLogger(__name__)


def download_cover_bytes(cover_url: str) -> Optional[bytes]:
    """Downloads image bytes from the given URL."""
    if not cover_url:
        return None
    try:
        resp = requests.get(cover_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and len(resp.content) > 100:
            return resp.content
    except Exception as e:
        logger.warning(f"Failed to download cover art from {cover_url}: {e}")
    return None


def tag_audio_file(file_path: str, track: TrackInfo, cover_bytes: Optional[bytes] = None):
    """
    Tags the audio file with TrackInfo metadata and embeds cover art.
    Supports .flac and .m4a (ALAC).
    """
    if not os.path.exists(file_path):
        return

    ext = os.path.splitext(file_path)[1].lower()

    if cover_bytes is None and track.cover_url:
        cover_bytes = download_cover_bytes(track.cover_url)

    if ext == ".flac":
        _tag_flac(file_path, track, cover_bytes)
    elif ext in [".m4a", ".mp4", ".alac"]:
        _tag_m4a(file_path, track, cover_bytes)
    else:
        logger.warning(f"Unsupported format for tagging: {ext}")


def _tag_flac(file_path: str, track: TrackInfo, cover_bytes: Optional[bytes]):
    """Embeds Vorbis comments and cover art into a FLAC file."""
    try:
        audio = FLAC(file_path)
        audio["title"] = track.title
        audio["artist"] = track.artist
        audio["album"] = track.album or "Single"
        if track.year:
            audio["date"] = str(track.year)
        if track.track_number:
            audio["tracknumber"] = str(track.track_number)

        if cover_bytes:
            # Clear existing pictures
            audio.clear_pictures()
            image = Picture()
            image.type = 3  # Cover (front)
            image.mime = "image/jpeg" if cover_bytes.startswith(b"\xff\xd8") else "image/png"
            image.desc = "Front Cover"
            image.data = cover_bytes
            audio.add_picture(image)

        audio.save()
        logger.info(f"Successfully tagged FLAC file: {file_path}")
    except Exception as e:
        logger.error(f"Error tagging FLAC file {file_path}: {e}")


def _tag_m4a(file_path: str, track: TrackInfo, cover_bytes: Optional[bytes]):
    """Embeds MP4 tags and cover art into an ALAC/M4A file."""
    try:
        audio = MP4(file_path)
        # MP4 standard atom 4CC keys
        audio["\xa9nam"] = [track.title]             # Title
        audio["\xa9ART"] = [track.artist]            # Artist
        audio["\xa9alb"] = [track.album or "Single"] # Album
        audio["aART"] = [track.artist]               # Album Artist

        if track.year:
            audio["\xa9day"] = [str(track.year)]     # Year/Release Date

        if track.track_number:
            audio["trkn"] = [(track.track_number, 0)] # Track number

        if cover_bytes:
            image_format = (
                MP4Cover.FORMAT_JPEG
                if cover_bytes.startswith(b"\xff\xd8")
                else MP4Cover.FORMAT_PNG
            )
            audio["covr"] = [MP4Cover(cover_bytes, imageformat=image_format)]

        audio.save()
        logger.info(f"Successfully tagged M4A (ALAC) file: {file_path}")
    except Exception as e:
        logger.error(f"Error tagging M4A file {file_path}: {e}")
