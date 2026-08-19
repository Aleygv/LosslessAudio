"""
Audio conversion and FFmpeg management module.
Supports converting to ALAC (.m4a) and FLAC (.flac), preserving sample rate and bit depth.
Gracefully handles environments without FFmpeg (such as Android) by direct stream preservation.
"""
import os
import shutil
import subprocess
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_CACHED_FFMPEG_PATH: Optional[str] = None


def is_ffmpeg_available() -> bool:
    """Returns True if a valid FFmpeg binary is available on the system."""
    return get_ffmpeg_path() is not None


def get_ffmpeg_path() -> Optional[str]:
    """Find or obtain the path to a usable ffmpeg executable, or None if unavailable."""
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
    except Exception:
        pass

    # 3. Check local bin/ folder
    local_bin = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ffmpeg.exe")
    if os.path.exists(local_bin):
        _CACHED_FFMPEG_PATH = local_bin
        return local_bin

    return None


def convert_audio(
    input_path: str,
    output_path: str,
    target_format: str = "flac",  # "alac" or "flac"
    progress_callback=None
) -> str:
    """
    Converts input audio file to target lossless format (ALAC .m4a or FLAC .flac).
    If FFmpeg is not installed (e.g. Android), directly copies and preserves the audio stream.
    """
    ffmpeg_exe = get_ffmpeg_path()
    target_format = target_format.lower()

    if target_format == "alac":
        if not output_path.lower().endswith(".m4a"):
            output_path = os.path.splitext(output_path)[0] + ".m4a"
        codec_args = ["-c:a", "alac"]
    elif target_format == "flac":
        if not output_path.lower().endswith(".flac"):
            output_path = os.path.splitext(output_path)[0] + ".flac"
        codec_args = ["-c:a", "flac", "-compression_level", "8"]
    else:
        target_format = "flac"
        if not output_path.lower().endswith(".flac"):
            output_path = os.path.splitext(output_path)[0] + ".flac"
        codec_args = ["-c:a", "flac"]

    # Fallback if FFmpeg is not available (e.g. on Android without binaries)
    if not ffmpeg_exe:
        logger.info(f"FFmpeg not present; preserving audio stream directly to: {output_path}")
        input_ext = os.path.splitext(input_path)[1].lower()
        if input_ext == os.path.splitext(output_path)[1].lower():
            shutil.copy2(input_path, output_path)
            return output_path
        else:
            direct_output = os.path.splitext(output_path)[0] + input_ext
            shutil.copy2(input_path, direct_output)
            return direct_output

    # If input is already in the target format, direct copy
    input_ext = os.path.splitext(input_path)[1].lower()
    if (target_format == "flac" and input_ext == ".flac") or (target_format == "alac" and input_ext in [".m4a", ".alac"]):
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
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            startupinfo=startupinfo
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            logger.warning(f"FFmpeg transcode warning: {stderr}. Falling back to direct copy.")
            shutil.copy2(input_path, output_path)
            return output_path

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            shutil.copy2(input_path, output_path)
            return output_path

        return output_path
    except Exception as ex:
        logger.warning(f"Conversion exception: {ex}. Using direct copy.")
        shutil.copy2(input_path, output_path)
        return output_path


def probe_audio(file_path: str) -> Dict[str, Any]:
    """Inspects audio file using ffprobe/ffmpeg if available or basic stat."""
    info = {
        "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        "raw_info": ""
    }
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        return info

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        cmd = [ffmpeg_exe, "-i", file_path]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            startupinfo=startupinfo
        )
        _, stderr = process.communicate()
        info["raw_info"] = stderr
        for line in stderr.splitlines():
            if "Audio:" in line:
                info["stream_info"] = line.strip()
    except Exception:
        pass
    return info
