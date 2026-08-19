"""
Automated GUI headless verification test.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow
from core.models import TrackInfo, QualityTier

def test_gui_launch():
    print("Testing GUI window initialization...", flush=True)
    app = MainWindow()
    app.update()

    print("Testing search results rendering...", flush=True)
    mock_tracks = [
        TrackInfo(
            id="mock_1",
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            duration=354,
            year="1975",
            source="Apple ALAC / Lossless",
            quality_label="ALAC 24-bit / 96kHz",
            quality_tier=QualityTier.HI_RES_24BIT,
            is_lossless=True
        ),
        TrackInfo(
            id="mock_2",
            title="Hotel California",
            artist="Eagles",
            album="Hotel California",
            duration=390,
            year="1976",
            source="Archive.org FLAC",
            quality_label="FLAC 16-bit / 1411 kbps",
            quality_tier=QualityTier.LOSSLESS_FLAC,
            is_lossless=True
        )
    ]
    app.current_results = mock_tracks
    app._render_results()
    app.update()

    print(f"Cards rendered: {len(app.active_cards)}", flush=True)
    assert len(app.active_cards) == 2, "Expected 2 cards rendered"

    print("Testing format toggle...", flush=True)
    app._on_format_changed("FLAC (.flac)")
    assert app.config["target_format"] == "flac"
    
    app._on_format_changed("ALAC (.m4a)")
    assert app.config["target_format"] == "alac"

    print("Closing GUI window...", flush=True)
    app.destroy()
    print("GUI VERIFICATION PASSED PERFECTLY!", flush=True)

if __name__ == "__main__":
    test_gui_launch()
