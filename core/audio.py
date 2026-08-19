"""
Audio conversion and FFmpeg management module.
Supports converting to ALAC (.m4a) and FLAC (.flac), preserving sample rate and bit depth.
"""
import os
import shutil
import subprocess
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_CACHED_FFMPEG_PATH: Optional[str] = None


def get_ffmpeg_path() -> str:
    """Find or obtain the path to a usable ffmpeg executable."""
    global _CACHED_FFMPEG_PATH
    if _CACHED_FFMPEG_PATH and os.path.exists(_CACHED_FFMPEG_PATH):
        return _CACHED_FFMPEG_PATH

    # 1. Check system PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        _CACHED_FFMPEG_PATH = sys_ffmpeg
        return sys_ffmpeg

    # 2. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        img_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if img_ffmpeg and os.path.exists(img_ffmpeg):
            _CACHED_FFMPEG_PATH = img_ffmpeg
            return img_ffmpeg
    except Exception as e:
        logger.warning(f"Could not load imageio_ffmpeg: {e}")

    # 3. Check local bin/ folder
    local_bin = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffmpeg.exe")
    if os.path.exists(local_bin):
        _CACHED_FFMPEG_PATH = local_bin
        return local_bin

    raise RuntimeError("FFmpeg executable not found. Please ensure imageio-ffmpeg is installed or FFmpeg is on PATH.")


def convert_audio(
    input_path: str,
    output_path: str,
    target_format: str = "alac",  # "alac" or "flac"
    progress_callback=None
) -> str:
    """
    Converts input audio file to target lossless format (ALAC .m4a or FLAC .flac).
    Preserves highest possible sample rate and bit depth.
    """
    ffmpeg_exe = get_ffmpeg_path()
    target_format = target_format.lower()

    if target_format == "alac":
        # ALAC inside MP4/M4A container
        if not output_path.lower().endswith(".m4a"):
            output_path = os.path.splitext(output_path)[0] + ".m4a"
        codec_args = ["-c:a", "alac"]
    elif target_format == "flac":
        if not output_path.lower().endswith(".flac"):
            output_path = os.path.splitext(output_path)[0] + ".flac"
        codec_args = ["-c:a", "flac", "-compression_level", "8"]
    else:
        raise ValueError(f"Unsupported target format: {target_format}. Use 'alac' or 'flac'.")

    # If input is already in the target format and valid, we can either remux or re-encode
    input_ext = os.path.splitext(input_path)[1].lower()
    if (target_format == "flac" and input_ext == ".flac") or (target_format == "alac" and input_ext in [".m4a", ".alac"]):
        # Direct copy or remux
        cmd = [
            ffmpeg_exe, "-y",
            "-i", input_path,
            "-vn",
            "-c:a", "copy",
            output_path
        ]
    else:
        cmd = [
            ffmpeg_exe, "-y",
            "-i", input_path,
            "-vn",
            *codec_args,
            output_path
        ]

    logger.info(f"Running conversion: {' '.join(cmd)}")
    
    # Hide console window on Windows
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        startupinfo=startupinfo
    )
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        logger.error(f"FFmpeg error: {stderr}")
        raise RuntimeError(f"Audio conversion failed with code {process.returncode}: {stderr[:300]}")

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Converted output file is missing or empty.")

    return output_path


def probe_audio(file_path: str) -> Dict[str, Any]:
    """Inspects audio file using ffprobe/ffmpeg to check sample rate, bit depth, format."""
    ffmpeg_exe = get_ffmpeg_path()
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    cmd = [ffmpeg_exe, "-i", file_path]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        startupinfo=startupinfo
    )
    _, stderr = process.communicate()
    
    info = {
        "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        "raw_info": stderr
    }
    
    # Extract audio stream info
    for line in stderr.splitlines():
        if "Audio:" in line:
            info["stream_info"] = line.strip()
            if "Hz" in line:
                parts = line.split(",")
                for p in parts:
                    p = p.strip()
                    if "Hz" in p:
                        info["sample_rate"] = p
                    if "kb/s" in p or "flac" in p or "alac" in p:
                        info["codec_or_bitrate"] = p
    return info
