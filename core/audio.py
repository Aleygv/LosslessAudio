"""
Audio conversion and FFmpeg management module.
Supports converting to ALAC (.m4a) and FLAC (.flac) only when source audio is genuine lossless (WAV/FLAC/ALAC/PCM).
Prevents fake bloating / upscaling of lossy MP3/Opus files into giant fake FLAC containers.
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


def probe_audio(file_path: str) -> Dict[str, Any]:
    """Probes audio file sample rate, bit depth, and duration."""
    info = {"sample_rate": 44100, "bit_depth": 16, "channels": 2, "duration": 0}
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe or not os.path.exists(file_path):
        return info

    try:
        cmd = [ffmpeg_exe, "-i", file_path]
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo)
        _, stderr = p.communicate()
        for line in stderr.splitlines():
            if "Hz" in line:
                for token in line.split(","):
                    token = token.strip()
                    if "Hz" in token:
                        sr_str = token.replace("Hz", "").strip()
                        if sr_str.isdigit():
                            info["sample_rate"] = int(sr_str)
                    if "s16" in token:
                        info["bit_depth"] = 16
                    elif "s24" in token or "24 bits" in token:
                        info["bit_depth"] = 24
                    elif "s32" in token:
                        info["bit_depth"] = 32
    except Exception:
        pass
    return info


def convert_audio(
    input_path: str,
    output_path: str,
    target_format: str = "flac",  # "alac" or "flac"
    progress_callback=None
) -> str:
    """
    Processes audio stream into the final file.
    CRITICAL RULE: If the source audio is lossy (e.g. MP3, Opus, AAC), it is preserved in its native
    container without bloating it into a fake 50MB FLAC file.
    If the source is genuine Lossless (FLAC, WAV, ALAC), it packages it into bit-perfect FLAC or ALAC.
    """
    ffmpeg_exe = get_ffmpeg_path()
    input_ext = os.path.splitext(input_path)[1].lower()
    target_format = target_format.lower()

    # Detect if input is already Lossless
    is_source_lossless = input_ext in [".flac", ".wav", ".alac", ".aif", ".aiff"]

    if not is_source_lossless:
        # Source is lossy (e.g. mp3, opus, web stream)
        # DO NOT inflate it into a 50MB fake FLAC! Keep original native container at 5MB!
        direct_ext = input_ext if input_ext in [".mp3", ".m4a"] else ".mp3"
        direct_output = os.path.splitext(output_path)[0] + direct_ext

        if ffmpeg_exe:
            cmd = [
                ffmpeg_exe, "-y",
                "-i", input_path,
                "-vn",
                "-c:a", "copy",
                direct_output
            ]
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
                return direct_output
            except Exception:
                pass

        shutil.copy2(input_path, direct_output)
        return direct_output

    # Source IS genuine lossless (FLAC / WAV / ALAC)
    if target_format == "alac":
        if not output_path.lower().endswith(".m4a"):
            output_path = os.path.splitext(output_path)[0] + ".m4a"
        codec_args = ["-c:a", "alac"]
    else:
        if not output_path.lower().endswith(".flac"):
            output_path = os.path.splitext(output_path)[0] + ".flac"
        codec_args = ["-c:a", "flac", "-compression_level", "8"]

    if not ffmpeg_exe:
        shutil.copy2(input_path, output_path)
        return output_path

    # If already in requested format, direct bit-copy
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

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
        return output_path
    except Exception as e:
        logger.error(f"Lossless conversion failed: {e}. Preserving original file.")
        shutil.copy2(input_path, output_path)
        return output_path
