# Spotify Word-Synced TTML & Vocal Isolation Studio

Local GPU-accelerated pipeline to generate word-synced `.ttml` lyrics for **Spicetify / Spicy Lyrics** and isolate clean vocal stems from any audio or video file.

## Features
- **One-Click Spicetify Playbar Button:** Generates word-synced `.ttml` for the currently playing Spotify track by matching exact track duration against studio audio.
- **Hard Mode (Right-Click / Shift+Click):** Runs a 4-stage isolation stack (**BS-Roformer** $\rightarrow$ **Mel-Band Roformer Karaoke** $\rightarrow$ **UVR-DeEcho-DeReverb** $\rightarrow$ **UVR-DeNoise**) plus `SequenceMatcher` word-level anchoring for heavily reverbed or distorted tracks.
- **Standalone Voice Isolator (`Isolate-Voices.bat`):** Drag-and-drop any `.mp4`, `.mp3`, `.wav`, or `.flac` file to extract `1_All_Voices_Clean.wav`, `2_Lead_Voice.wav`, and `3_Secondary_Voices.wav`.

## Prerequisites
- **Windows 10/11** with an **NVIDIA GPU** (CUDA)
- **Python 3.10 – 3.13** (added to `PATH`)
- **FFmpeg** (`winget install Gyan.FFmpeg`)
- **Spicetify** + **Spicy Lyrics** (for in-Spotify button integration)

## Quick Setup
1. Clone or download this repository.
2. Run **`setup.bat`** to create the virtual environment, install PyTorch CUDA + dependencies, register the background Spicetify bridge, and install the Spicetify playbar extension.
3. Optional: Edit `config.json` (created on first run) to customize `ttml_output_dir` and `stems_output_dir`.

## Usage
- **Inside Spotify:** Left-click the sparkle-lyrics button in the bottom playbar for standard mode, or **Right-Click / Shift+Click** for **Hard Mode**.
- **Manual URL / `.txt` Alignment:** Double-click `Generate-TTML.bat` and paste a Spotify or YouTube track URL.
- **Voice Isolation & Denoise:** Drag and drop any audio or video file onto `Isolate-Voices.bat`.
