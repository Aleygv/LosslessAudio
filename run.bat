@echo off
title Lossless Music Grabber (ALAC / FLAC)
echo Starting Lossless Music Grabber...
python app.py
if errorlevel 1 (
    echo.
    echo Application stopped with an error. Press any key to exit...
    pause > nul
)
