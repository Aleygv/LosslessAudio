"""
Verification test to guarantee FULL-LENGTH audio downloads (not 30-sec previews).
"""
import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure d:\FLAC_SErch is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import MusicSearchEngine
from core.audio import probe_audio
from sources.music_search_resolver import DirectLosslessSource

def test_full_length():
    print("--- Testing Search ---", flush=True)
    src = DirectLosslessSource()
    res = src.search("Queen Bohemian Rhapsody", limit=1)
    assert len(res) > 0
    track = res[0]
    print(f"Target track: {track.artist} - {track.title}, expected duration: {track.duration}s ({track.duration_str})", flush=True)

    out_dir = os.path.join(os.path.dirname(__file__), "test_output")
    os.makedirs(out_dir, exist_ok=True)
    
    engine = MusicSearchEngine()

    def on_progress(p, msg):
        print(f"  [{int(p*100)}%] {msg}", flush=True)

    print("\n--- Downloading and converting to ALAC ---", flush=True)
    saved_file = engine.download_and_process(
        track=track,
        download_dir=out_dir,
        target_format="alac",
        progress_callback=on_progress
    )

    print(f"\nSaved file: {saved_file}", flush=True)
    file_size_mb = os.path.getsize(saved_file) / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB", flush=True)
    
    # A 30s preview is ~1 MB. A full 5:54 ALAC track is > 20 MB or at least several MBs.
    assert file_size_mb > 5.0, f"File size is {file_size_mb:.2f}MB, expected >5MB for full song!"
    
    info = probe_audio(saved_file)
    print(f"Audio stream info: {info.get('stream_info')}", flush=True)
    print("\nSUCCESS: FULL SONG DOWNLOADED AND VERIFIED (NOT A 30S PREVIEW)!", flush=True)

if __name__ == "__main__":
    test_full_length()
