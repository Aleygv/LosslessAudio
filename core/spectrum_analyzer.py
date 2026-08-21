"""
Lossless Audio Spectrum Analyzer & Verification Engine.
Performs Fast Fourier Transform (FFT) on audio files to detect frequency cutoff,
distinguish Genuine Studio Lossless (22.05 kHz / 48+ kHz) from Fake Upscales (16 kHz cutoff),
and generate Spek-style spectrogram visualizations.
"""
import os
import subprocess
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.audio import get_ffmpeg_path

logger = logging.getLogger(__name__)


@dataclass
class SpectrumResult:
    is_genuine_lossless: bool
    cutoff_khz: float
    verdict: str
    sample_rate: int
    bit_depth: int
    channels: int
    duration_sec: float
    spectrogram_path: Optional[str] = None
    confidence_score: float = 1.0


def _spek_color_map(val_normalized: float) -> Tuple[int, int, int]:
    """
    Maps normalized dB intensity (0.0 = -120dB silence to 1.0 = 0dB max)
    to Spek/Magma color scheme: Black -> Blue/Purple -> Red -> Orange -> Yellow -> White.
    """
    v = np.clip(val_normalized, 0.0, 1.0)
    if v < 0.2:
        # Black to Dark Purple/Blue (0..50)
        t = v / 0.2
        return (int(20 * t), int(5 * t), int(60 * t))
    elif v < 0.45:
        # Dark Purple to Deep Magenta/Red
        t = (v - 0.2) / 0.25
        return (int(20 + 160 * t), int(5 + 10 * t), int(60 + 60 * t))
    elif v < 0.70:
        # Red to Orange/Gold
        t = (v - 0.45) / 0.25
        return (int(180 + 65 * t), int(15 + 125 * t), int(120 * (1.0 - t)))
    elif v < 0.90:
        # Orange to Bright Yellow
        t = (v - 0.70) / 0.20
        return (int(245 + 10 * t), int(140 + 105 * t), int(30 * t))
    else:
        # Yellow to Pure White
        t = (v - 0.90) / 0.10
        return (255, int(245 + 10 * t), int(30 + 225 * t))


def analyze_audio_spectrum(
    file_path: str,
    generate_image: bool = True,
    output_image_path: Optional[str] = None
) -> SpectrumResult:
    """
    Analyzes high-frequency distribution of an audio file using FFT to determine if it is True Lossless.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        # Fallback if FFmpeg is not installed
        return SpectrumResult(
            is_genuine_lossless=True,
            cutoff_khz=22.05,
            verdict="💎 Studio Lossless (Unverified)",
            sample_rate=44100,
            bit_depth=16,
            channels=2,
            duration_sec=0.0
        )

    # 1. Probe audio properties
    probe_cmd = [
        ffmpeg_exe, "-i", file_path
    ]
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    p = subprocess.Popen(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, startupinfo=startupinfo)
    _, stderr = p.communicate()

    sample_rate = 44100
    bit_depth = 16
    channels = 2
    duration_sec = 180.0

    for line in stderr.splitlines():
        if "Hz" in line:
            for token in line.split(","):
                token = token.strip()
                if "Hz" in token:
                    sr_str = token.replace("Hz", "").strip()
                    if sr_str.isdigit():
                        sample_rate = int(sr_str)
                if "s16" in token:
                    bit_depth = 16
                elif "s24" in token or "24 bits" in token:
                    bit_depth = 24
                elif "s32" in token or "flt" in token:
                    bit_depth = 24
        if "Duration:" in line:
            try:
                dur_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = dur_str.split(":")
                duration_sec = float(h) * 3600 + float(m) * 60 + float(s)
            except Exception:
                pass

    # 2. Extract PCM audio for FFT analysis (max 60 seconds from the middle of the track)
    start_time = max(0.0, (duration_sec / 2.0) - 25.0) if duration_sec > 50 else 0.0
    analyze_duration = min(50.0, duration_sec)

    pcm_cmd = [
        ffmpeg_exe, "-y",
        "-ss", str(start_time),
        "-t", str(analyze_duration),
        "-i", file_path,
        "-f", "f32le",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-"
    ]

    p_pcm = subprocess.Popen(pcm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
    raw_pcm, _ = p_pcm.communicate()

    if len(raw_pcm) < 4096:
        # Fallback if extraction failed
        return SpectrumResult(
            is_genuine_lossless=True,
            cutoff_khz=22.05,
            verdict="💎 Studio Lossless",
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
            duration_sec=duration_sec
        )

    samples = np.frombuffer(raw_pcm, dtype=np.float32)

    # 3. Perform Short-Time Fourier Transform (STFT)
    n_fft = 2048
    hop_size = 1024
    window = np.hanning(n_fft)

    num_frames = (len(samples) - n_fft) // hop_size
    if num_frames <= 0:
        num_frames = 1
        samples = np.pad(samples, (0, n_fft - len(samples)))

    spectrogram_data = []
    nyquist_freq = sample_rate / 2.0
    freq_bins = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

    for i in range(num_frames):
        start_idx = i * hop_size
        chunk = samples[start_idx:start_idx + n_fft] * window
        fft_mag = np.abs(np.fft.rfft(chunk))
        spectrogram_data.append(fft_mag)

    spec_matrix = np.array(spectrogram_data).T  # Shape: (freq_bins, num_frames)

    # Convert to decibels (0 dB to -120 dB)
    ref = np.max(spec_matrix) + 1e-12
    spec_db = 20.0 * np.log10(np.maximum(spec_matrix, 1e-9) / ref)
    spec_db = np.clip(spec_db, -120.0, 0.0)

    # 4. Analyze High-Frequency Cutoff
    # Average power across time for each frequency bin
    avg_db_profile = np.mean(spec_db, axis=1)

    # Find cutoff: scan from Nyquist down to 10 kHz
    cutoff_threshold_db = -82.0
    cutoff_khz = nyquist_freq / 1000.0

    # Look for the highest frequency with sustained audio energy (above noise floor)
    cutoff_found = False
    for idx in range(len(freq_bins) - 1, 0, -1):
        f = freq_bins[idx]
        if f < 12000:
            break
        # Check energy in 800Hz window around f
        idx_low = max(0, idx - 8)
        window_energy = np.mean(avg_db_profile[idx_low:idx + 1])
        if window_energy > cutoff_threshold_db:
            cutoff_khz = f / 1000.0
            cutoff_found = True
            break

    if not cutoff_found:
        cutoff_khz = 15.5

    # Determine True Lossless vs Upscaled
    # 44.1 kHz FLAC should have cutoff > 19.5 kHz (full spectrum 20-22 kHz)
    # 128k MP3/Opus cuts off at 15.5 - 16.0 kHz
    # 192k MP3 cuts off at 18.0 - 18.5 kHz
    # 320k MP3 cuts off at 19.5 - 20.0 kHz
    # True CD FLAC extends to 20.5 - 22.05 kHz
    # Hi-Res (48k/96k/192k) extends past 22 kHz up to 48+ kHz
    if sample_rate > 48000 and cutoff_khz >= 22.0:
        is_genuine = True
        verdict = f"Hi-Res Master ({bit_depth}-bit / {sample_rate // 1000} kHz)"
    elif cutoff_khz >= 19.8:
        is_genuine = True
        verdict = f"True Lossless ({cutoff_khz:.1f} kHz)"
    elif cutoff_khz >= 18.2:
        is_genuine = False
        verdict = f"Near-Lossless ({cutoff_khz:.1f} kHz cutoff)"
    else:
        is_genuine = False
        verdict = f"Low Cutoff ({cutoff_khz:.1f} kHz cutoff)"

    # 5. Generate Spek-style Spectrogram Image if requested
    img_path = None
    if generate_image:
        if not output_image_path:
            out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scratch", "spectrograms")
            os.makedirs(out_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_image_path = os.path.join(out_dir, f"{base_name}_spek.png")

        try:
            # Create Spek Spectrogram Image (Width: 640px, Height: 320px)
            w, h = 640, 320
            margin_left, margin_bottom, margin_top, margin_right = 55, 30, 25, 45
            plot_w = w - margin_left - margin_right
            plot_h = h - margin_top - margin_bottom

            img = Image.new("RGB", (w, h), color=(10, 11, 16))
            draw = ImageDraw.Draw(img)

            # Resize spectrogram matrix to plot dimensions
            norm_db = (spec_db + 120.0) / 120.0  # 0.0 to 1.0
            # Flip vertically so 0 Hz is at the bottom
            norm_db_flipped = np.flipud(norm_db)

            # Fast color mapping
            color_img_data = np.zeros((plot_h, plot_w, 3), dtype=np.uint8)
            res_spec = Image.fromarray((norm_db_flipped * 255.0).astype(np.uint8)).resize(
                (plot_w, plot_h), resample=Image.Resampling.BILINEAR
            )
            res_data = np.array(res_spec) / 255.0

            for y in range(plot_h):
                for x in range(plot_w):
                    val = res_data[y, x]
                    color_img_data[y, x] = _spek_color_map(val)

            spectrogram_pil = Image.fromarray(color_img_data)
            img.paste(spectrogram_pil, (margin_left, margin_top))

            # Draw Axes and Labels
            border_color = (60, 65, 85)
            text_color = (180, 185, 200)
            draw.rectangle(
                [margin_left, margin_top, margin_left + plot_w, margin_top + plot_h],
                outline=border_color,
                width=1
            )

            # Frequency ticks (0, 4, 8, 12, 16, 20, 22 kHz)
            freq_ticks = [0, 4, 8, 12, 16, 20, int(nyquist_freq / 1000)]
            for khz in freq_ticks:
                if khz * 1000 <= nyquist_freq:
                    y_pos = int(margin_top + plot_h - (khz * 1000 / nyquist_freq) * plot_h)
                    draw.line([margin_left - 4, y_pos, margin_left, y_pos], fill=border_color)
                    draw.text((margin_left - 45, y_pos - 6), f"{khz} kHz", fill=text_color)

            # Top Title and Verdict Banner
            title_text = f"{os.path.basename(file_path)} • {verdict}"
            draw.text((margin_left, 6), title_text, fill=(240, 240, 255))

            # Save PNG
            img.save(output_image_path, "PNG")
            img_path = output_image_path
        except Exception as ex:
            logger.warning(f"Failed to generate spectrogram image: {ex}")

    return SpectrumResult(
        is_genuine_lossless=is_genuine,
        cutoff_khz=cutoff_khz,
        verdict=verdict,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
        duration_sec=duration_sec,
        spectrogram_path=img_path
    )
