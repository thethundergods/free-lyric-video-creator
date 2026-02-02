# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FREE Lyric Video Creator is a Python desktop application for creating karaoke-style lyric videos. Users load audio, enter lyrics, tap spacebar to time each word to the music, then export to video or upload directly to YouTube.

## Development Commands

### Setup
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate      # Windows
pip install -r requirements.txt
pip install pyobjc-framework-Cocoa  # macOS only, for dock icon
```

### Run
```bash
python main.py
# Or with a file to open:
python main.py path/to/audio.mp3
```

### Build Standalone Executable
```bash
# Windows
build_windows.bat

# macOS - app bundle already provided as "FREE Lyric Video Creator.app"
```

## Architecture

The application is built with pygame for the UI and consists of these modules:

- **main.py** - Entry point and main UI (`LyricVideoCreator` class). Handles pygame event loop, button/keyboard input, draws the lyrics display with word coloring, and orchestrates other modules.

- **audio_player.py** - `AudioPlayer` class wrapping pygame.mixer for audio playback with play/pause/seek/position tracking.

- **lyrics_timer.py** - Data model for lyrics. `TimedWord` stores individual words with timestamps. `LyricsTimer` manages the word list, timing operations (mark/unmark), and provides queries like `get_word_at_time()` for rendering.

- **video_renderer.py** - `VideoRenderer` class renders the final video using PIL for text drawing and moviepy for video composition. Implements karaoke-style highlighting with smooth scrolling, text shadows, and loading bars.

- **dialogs.py** - Cross-platform dialog system. Uses AppleScript on macOS and tkinter on Windows/Linux for file dialogs, message boxes, and text input.

- **youtube_uploader.py** - `YouTubeUploader` class for OAuth2 authentication and video upload to YouTube via Google API.

## Data Flow

1. User loads audio file -> `AudioPlayer.load()`
2. User enters lyrics -> `LyricsTimer.load_lyrics()` parses into `TimedWord` objects
3. During playback, user taps SPACE -> `LyricsTimer.mark_word()` records timestamp
4. Export -> `VideoRenderer` iterates frame-by-frame, highlighting words based on timing
5. Upload -> `YouTubeUploader.authenticate()` then `upload()`

## Project Files

- `.lvproject` - Project save format (JSON with audio path + word timings)
- `.json` - Standalone timing data export
- `credentials/client_secrets.json` - Required for YouTube upload (user-provided OAuth2 credentials)
- `credentials/token.pickle` - Cached YouTube auth token

## Key Keyboard Shortcuts

SPACE=mark word, DELETE=unmark, P=play/pause, S=stop, LEFT/RIGHT=seek 5s, L=load audio, T=load lyrics, V=paste lyrics, E=export, U=upload
