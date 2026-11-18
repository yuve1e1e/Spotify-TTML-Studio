# Spotify Word-Synced TTML & Vocal Isolation Studio

Local GPU-accelerated tool to generate word-synced `.ttml` lyrics for **Spicetify / Spicy Lyrics** and isolate clean vocal stems from any audio or video file.

## How It Works (Simple Overview)
1. **Matches Your Song:** When you click the button in Spotify (or paste a link), the script reads the song's title and exact duration and grabs the matching studio-length audio.
2. **Removes the Music:** An AI vocal-separation model strips out all instruments and background beats so only the singer's voice remains.
3. **Syncs Every Word:** It fetches the lyrics from LRCLIB (or transcribes them with AI if unavailable) and aligns each individual word to the exact millisecond it is sung, saving a ready-to-load `.ttml` file.
4. **100% Local Bridge:** A tiny, silent local server (`127.0.0.1:8765`) runs on your own PC so the button inside Spotify can talk to the Python script—no audio or personal data is ever uploaded to third-party servers.

## What `setup.bat` Installs
- **System Prerequisites (Optional Auto-Install via `winget`):**
  - **Python 3.12**, **FFmpeg** (audio extraction), and **Deno** (used by `yt-dlp` to resolve YouTube streams).
- **Self-Contained Virtual Environment (`./venv`):**
  - Installs PyTorch (CUDA), WhisperX, `audio-separator`, `yt-dlp`, `requests`, and `audioread` strictly inside a local `venv` folder inside this repository so your global Windows Python installation stays clean.
- **AI Models (Downloaded Automatically on First Use):**
  - *Standard Mode:* **BS-Roformer** (~640 MB) + **WhisperX `large-v3` / Wav2Vec2** (~3 GB).
  - *Hard Mode & Voice Isolator:* **Mel-Band Roformer Karaoke**, **UVR-DeEcho-DeReverb**, and **UVR-DeNoise** (~1 GB total).
- **Spicetify Integration:**
  - Copies `generate_ttml.js` into your Spicetify `Extensions` folder and places a lightweight `TTMLBridge.vbs` launcher in your Windows Startup folder so the Spotify playbar button works automatically.

## Hardware Safety & Resource Usage
- **Completely Safe for Your PC:** Running local AI audio models puts the same type of normal workload on your GPU as playing a modern 3D game or rendering a video. Modern GPUs have built-in firmware thermal and power limits that prevent overheating or hardware damage.
- **Zero Drain When Idle:** When you are not actively generating lyrics or isolating a clip, the background bridge uses ~15 MB of RAM and **0% GPU / 0% CPU**. AI models are loaded into VRAM only while a song is processing (~15–45 seconds) and are immediately unloaded afterward.
- **No System or Driver Tweaks:** Nothing in this project overclocks your GPU, alters fan curves, or modifies Windows hardware settings.

## Quick Setup
1. Clone or download this repository.
2. Double-click **`setup.bat`**. If Python, FFmpeg, or Deno are missing, type **`Y`** when prompted to download and install them automatically.
3. Optional: Edit `config.json` (generated automatically on first run) to change where `.ttml` files or isolated stems are saved.

## Usage
- **Inside Spotify (Spicetify + Spicy Lyrics):**
  - **Left-Click** the sparkle-lyrics button on the bottom playbar to generate word-synced `.ttml` for the currently playing song.
  - **Right-Click** (or **Shift + Left-Click**) to run **Hard Mode** (4-stage vocal/reverb/noise isolation + word-level anchoring for difficult tracks).
- **Manual URL / `.txt` Lyrics:** Run **`Generate-TTML.bat`** and paste a Spotify or YouTube track URL.
- **Voice Isolation & Denoise:** Drag and drop any `.mp4`, `.mp3`, `.wav`, or `.flac` file onto **`Isolate-Voices.bat`** to output `1_All_Voices_Clean.wav`, `2_Lead_Voice.wav`, and `3_Secondary_Voices.wav`.
