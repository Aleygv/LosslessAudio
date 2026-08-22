"""
Deezer Hi-Fi / Studio Lossless FLAC Source.
Downloads bit-perfect 1411 kbps 16-bit / 44.1 kHz FLAC master audio files directly from Deezer CDN
using Blowfish-CBC chunk decryption and ARL token authentication.
"""
import os
import hashlib
import requests
import logging
from typing import List, Callable, Optional
from Crypto.Cipher import Blowfish

from sources.base import BaseSource
from core.models import TrackInfo, QualityTier
from config import load_config

logger = logging.getLogger(__name__)

DEEZER_BLOWFISH_SECRET = b"g4el58wc0zvf9na1"


def get_deezer_blowfish_key(track_id: str) -> bytes:
    """Derives Blowfish 128-bit decryption key from track ID."""
    md5_id = hashlib.md5(track_id.encode("utf-8")).hexdigest().encode("utf-8")
    key = bytearray(16)
    for i in range(16):
        key[i] = md5_id[i] ^ md5_id[i + 16] ^ DEEZER_BLOWFISH_SECRET[i]
    return bytes(key)


def decrypt_deezer_stream(encrypted_data: bytes, blowfish_key: bytes) -> bytes:
    """
    Decrypts Deezer audio stream chunks.
    Every 3rd 2048-byte chunk in the stream is encrypted with Blowfish-CBC (IV: 0..7).
    """
    chunk_size = 2048
    decrypted = bytearray()
    num_chunks = len(encrypted_data) // chunk_size

    for i in range(num_chunks):
        chunk = encrypted_data[i * chunk_size:(i + 1) * chunk_size]
        if i % 3 == 0 and len(chunk) == chunk_size:
            cipher = Blowfish.new(blowfish_key, Blowfish.MODE_CBC, iv=b"\x00\x01\x02\x03\x04\x05\x06\x07")
            decrypted.extend(cipher.decrypt(chunk))
        else:
            decrypted.extend(chunk)

    remainder = encrypted_data[num_chunks * chunk_size:]
    decrypted.extend(remainder)
    return bytes(decrypted)


class DeezerSource(BaseSource):
    @property
    def name(self) -> str:
        return "Deezer Hi-Fi"

    def search(self, query: str, limit: int = 8) -> List[TrackInfo]:
        results = []
        try:
            url = "https://api.deezer.com/search"
            params = {"q": query, "limit": limit}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(url, params=params, headers=headers, timeout=2.5)
            if resp.status_code != 200:
                return results

            cfg = load_config()
            has_arl = bool(cfg.get("deezer_arl"))

            data = resp.json().get("data", [])
            for item in data:
                track_id = str(item.get("id"))
                title = item.get("title", "")
                artist = item.get("artist", {}).get("name", "Unknown Artist")
                album = item.get("album", {}).get("title", "")
                duration = item.get("duration", 0)
                
                cover_url = (
                    item.get("album", {}).get("cover_xl")
                    or item.get("album", {}).get("cover_big")
                    or item.get("album", {}).get("cover_medium")
                    or ""
                )

                preview_url = item.get("preview", "")
                quality_label = "True FLAC 1411k" if has_arl else "FLAC / Studio Catalog"

                track = TrackInfo(
                    id=f"dz_{track_id}",
                    title=title,
                    artist=artist,
                    album=album,
                    duration=duration,
                    cover_url=cover_url,
                    source="Deezer Hi-Fi",
                    quality_label=quality_label,
                    quality_tier=QualityTier.LOSSLESS_FLAC,
                    is_lossless=True,
                    download_url=preview_url,
                    extra_data={
                        "deezer_id": track_id,
                        "isrc": item.get("isrc", ""),
                        "preview_url": preview_url,
                        "md5_origin": item.get("md5_image", "")
                    }
                )
                results.append(track)
        except Exception as e:
            logger.debug(f"Deezer search notice: {e}")
        return results

    def download_track(
        self,
        track: TrackInfo,
        temp_dir: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        cfg = load_config()
        arl = cfg.get("deezer_arl", "").strip()
        dz_id = track.extra_data.get("deezer_id") if track.extra_data else track.id.replace("dz_", "")

        # 1. Try Direct Deezer Hi-Fi FLAC download if ARL is available
        if arl and dz_id:
            try:
                dest_file = os.path.join(temp_dir, f"dz_{track.clean_filename_base}.flac")
                if progress_callback:
                    progress_callback(0.1, "Запрос сессии Deezer Hi-Fi FLAC...")

                session = requests.Session()
                session.cookies.set("arl", arl, domain=".deezer.com")
                session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

                user_resp = session.get("https://www.deezer.com/ajax/gw-light.php?method=deezer.getUserData&api_version=1.0&api_token=", timeout=5)
                if user_resp.status_code == 200:
                    api_token = user_resp.json().get("results", {}).get("checkForm", "")
                    
                    track_post = session.post(
                        f"https://www.deezer.com/ajax/gw-light.php?method=song.getData&api_version=1.0&api_token={api_token}",
                        json={"sng_id": dz_id},
                        timeout=5
                    )
                    if track_post.status_code == 200:
                        song_data = track_post.json().get("results", {})
                        track_token = song_data.get("TRACK_TOKEN")
                        
                        media_resp = session.post(
                            "https://media.deezer.com/v1/get_url",
                            json={
                                "license_token": track_token,
                                "media": [{"type": "FULL", "formats": [{"cipher": "BF_CBC_STRIPE", "format": "FLAC"}, {"cipher": "BF_CBC_STRIPE", "format": "MP3_320"}]}],
                                "track_tokens": [track_token]
                            },
                            timeout=5
                        )
                        if media_resp.status_code == 200:
                            media_data = media_resp.json().get("data", [])
                            if media_data and "media" in media_data[0] and media_data[0]["media"]:
                                stream_url = media_data[0]["media"][0]["sources"][0]["url"]
                                
                                if progress_callback:
                                    progress_callback(0.3, "Загрузка 1411 kbps FLAC потока...")

                                raw_stream = session.get(stream_url, timeout=30).content
                                if len(raw_stream) > 100000:
                                    if progress_callback:
                                        progress_callback(0.8, "Дешифрование аудиопотока (Blowfish)...")

                                    blowfish_key = get_deezer_blowfish_key(dz_id)
                                    decrypted_flac = decrypt_deezer_stream(raw_stream, blowfish_key)
                                    with open(dest_file, "wb") as f:
                                        f.write(decrypted_flac)

                                    if progress_callback:
                                        progress_callback(0.95, "Оригинальный FLAC расшифрован")
                                    return dest_file
            except Exception as e:
                logger.warning(f"Deezer Hi-Fi download attempt error: {e}")

        # 2. Fallback to full-length audio stream (never download 30s preview)
        from core.resolver import resolve_and_download_full_stream
        return resolve_and_download_full_stream(track, temp_dir, progress_callback)
