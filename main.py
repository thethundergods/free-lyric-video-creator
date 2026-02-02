"""
FREE Lyric Video Creator

Controls:
- SPACE: Mark current word with timestamp
- DELETE/BACKSPACE: Unmark last timed word
- P: Play/Pause audio
- S: Stop and reset to beginning
- LEFT/RIGHT: Seek backward/forward 5 seconds
- E: Export video
- U: Upload to YouTube
- L: Load audio file
- T: Load lyrics text file
- V: Paste lyrics from clipboard
- J: Save timing data
- K: Load timing data
- R: Reset all timings
- ESC: Quit

Or use the buttons!
"""
import os
import sys
import subprocess
import platform

# Set app name and icon for macOS (must be before pygame import)
APP_NAME = "FREE Lyric Video Creator"
IS_MAC = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'

if IS_MAC:
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle

        # Set app name
        bundle = NSBundle.mainBundle()
        if bundle:
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            if info:
                info['CFBundleName'] = APP_NAME

        # Set dock icon
        icon_path = os.path.join(os.path.dirname(__file__), 'AppIcon.icns')
        if os.path.exists(icon_path):
            app = NSApplication.sharedApplication()
            icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
            if icon:
                app.setApplicationIconImage_(icon)
    except ImportError:
        pass

import pygame
import dialogs
from pygame import QUIT, KEYDOWN, MOUSEBUTTONDOWN, VIDEORESIZE
from pygame import K_SPACE, K_DELETE, K_BACKSPACE
from pygame import K_p, K_s, K_LEFT, K_RIGHT, K_e, K_u, K_l, K_t, K_v, K_j, K_k, K_r, K_ESCAPE

from audio_player import AudioPlayer
from lyrics_timer import LyricsTimer
from video_renderer import VideoRenderer, render_preview_frame
from youtube_uploader import YouTubeUploader, setup_instructions


class Button:
    """Simple clickable button."""
    def __init__(self, x, y, width, height, text, callback, color=(60, 60, 60), hover_color=(80, 80, 80)):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False

    def draw(self, screen, font):
        color = self.hover_color if self.is_hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=5)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 1, border_radius=5)

        text_surface = font.render(self.text, True, (250, 250, 250))
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.callback()
                return True
        return False


class LyricVideoCreator:
    # Colors
    BG_COLOR = (20, 20, 20)
    TEXT_COLOR = (250, 250, 250)  # #fafafa
    TIMED_COLOR = (100, 200, 100)  # Green for timed words
    CURRENT_COLOR = (255, 215, 0)  # Gold for current word
    DIM_COLOR = (100, 100, 100)
    STATUS_BG = (40, 40, 40)
    PANEL_COLOR = (30, 30, 30)

    # Layout
    WIDTH = 1150
    HEIGHT = 750
    MARGIN = 20
    LINE_HEIGHT = 36
    BUTTON_PANEL_WIDTH = 160

    def __init__(self, initial_file=None):
        pygame.init()
        pygame.display.set_caption("FREE Lyric Video Creator")

        # Set dock/window icon
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            icon = pygame.image.load(icon_path)
            pygame.display.set_icon(icon)

        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.audio = AudioPlayer()
        self.lyrics = LyricsTimer()
        self.uploader = YouTubeUploader()

        self.font = pygame.font.SysFont('Arial', 24)
        self.small_font = pygame.font.SysFont('Arial', 16)
        self.title_font = pygame.font.SysFont('Arial', 28, bold=True)
        self.button_font = pygame.font.SysFont('Arial', 14)

        self.audio_file = None
        self.running = True
        self.status_message = "Load audio and lyrics to get started"
        self.status_time = 0

        # Create buttons
        self.buttons = self._create_buttons()

        # Load initial file if provided
        if initial_file:
            self._load_initial_file(initial_file)

    def _create_buttons(self):
        """Create all UI buttons."""
        buttons = []
        x = self.WIDTH - self.BUTTON_PANEL_WIDTH + 10
        y = 60
        w = self.BUTTON_PANEL_WIDTH - 20
        h = 32
        gap = 8

        # File operations
        buttons.append(Button(x, y, w, h, "Load Audio (L)", self.load_audio))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Load Lyrics (T)", self.load_lyrics_file))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Paste Lyrics (V)", self.paste_lyrics))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Type Lyrics", self.type_lyrics))
        y += h + gap + 10

        # Playback controls
        buttons.append(Button(x, y, w, h, "Play / Pause (P)", self.toggle_play, color=(50, 80, 50)))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Stop (S)", self.stop_audio))
        y += h + gap
        buttons.append(Button(x, y, w//2 - 2, h, "<< 5s", self.seek_back))
        buttons.append(Button(x + w//2 + 2, y, w//2 - 2, h, "5s >>", self.seek_forward))
        y += h + gap + 10

        # Timing controls
        buttons.append(Button(x, y, w, h, "Mark Word (SPACE)", self.mark_word, color=(80, 80, 50)))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Unmark Last (DEL)", self.unmark_word))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Reset All Timings", self.reset_timings, color=(80, 50, 50)))
        y += h + gap + 10

        # Project save/load
        buttons.append(Button(x, y, w, h, "Save Project", self.save_project, color=(50, 70, 50)))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Open Project", self.load_project, color=(50, 70, 50)))
        y += h + gap + 10

        # Export
        buttons.append(Button(x, y, w, h, "Export Video (E)", self.export_video, color=(50, 50, 80)))

        return buttons

    def _load_initial_file(self, file_path):
        """Load a file passed as command line argument."""
        if not os.path.exists(file_path):
            return

        ext = os.path.splitext(file_path)[1].lower()

        # Audio file
        if ext in ('.mp3', '.wav', '.ogg', '.flac', '.m4a'):
            if self.audio.load(file_path):
                self.audio_file = file_path
                self.set_status(f"Loaded: {os.path.basename(file_path)}")

                # Try to load matching timing file
                timing_path = os.path.splitext(file_path)[0] + '.json'
                if os.path.exists(timing_path):
                    if self.lyrics.load(timing_path):
                        self.set_status(f"Loaded audio and timing data")

                # Try to load matching lyrics file
                lyrics_path = os.path.splitext(file_path)[0] + '.txt'
                if os.path.exists(lyrics_path) and not self.lyrics.words:
                    try:
                        with open(lyrics_path, 'r', encoding='utf-8') as f:
                            self.lyrics.load_lyrics(f.read())
                        self.set_status(f"Loaded audio and lyrics")
                    except:
                        pass

        # Timing JSON file
        elif ext == '.json':
            if self.lyrics.load(file_path):
                self.set_status(f"Loaded timing: {os.path.basename(file_path)}")

                # Try to find matching audio
                for audio_ext in ('.mp3', '.wav', '.ogg', '.flac', '.m4a'):
                    audio_path = os.path.splitext(file_path)[0] + audio_ext
                    if os.path.exists(audio_path):
                        if self.audio.load(audio_path):
                            self.audio_file = audio_path
                            self.set_status(f"Loaded timing and audio")
                        break

        # Lyrics text file
        elif ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.lyrics.load_lyrics(f.read())
                self.set_status(f"Loaded lyrics: {os.path.basename(file_path)}")
            except:
                pass

        # Lyric Video project file
        elif ext == '.lvproject':
            self._open_project(file_path)

    def set_status(self, message: str, duration: float = 3.0):
        """Set a status message to display."""
        self.status_message = message
        self.status_time = pygame.time.get_ticks() + duration * 1000

    def load_audio(self):
        """Open file dialog to load audio."""
        file_path = dialogs.askopenfilename(
            title="Select Audio File",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            if self.audio.load(file_path):
                self.audio_file = file_path
                self.set_status(f"Loaded: {os.path.basename(file_path)}")
            else:
                self.set_status("Failed to load audio file")

    def load_lyrics_file(self):
        """Open file dialog to load lyrics from text file."""
        file_path = dialogs.askopenfilename(
            title="Select Lyrics File",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                self.lyrics.load_lyrics(text)
                self.set_status(f"Loaded {self.lyrics.get_total_words()} words")
            except Exception as e:
                self.set_status(f"Failed to load lyrics: {e}")

    def paste_lyrics(self):
        """Get lyrics from clipboard."""
        text = dialogs.get_clipboard()
        if text.strip():
            self.lyrics.load_lyrics(text)
            self.set_status(f"Pasted {self.lyrics.get_total_words()} words")
        else:
            self.set_status("Clipboard is empty")

    def type_lyrics(self):
        """Open text editor to type/edit lyrics."""
        # Get existing lyrics if any
        existing = self.lyrics.get_lyrics_text() if self.lyrics.words else ""

        text = dialogs.asktextarea(
            "FREE Lyric Video Creator",
            "Enter or edit lyrics:",
            default=existing
        )
        if text and text.strip():
            self.lyrics.load_lyrics(text)
            self.set_status(f"Loaded {self.lyrics.get_total_words()} words")

    def toggle_play(self):
        """Toggle play/pause."""
        if self.audio_file:
            self.audio.toggle_pause()
            state = "Playing" if self.audio.is_playing() else "Paused"
            self.set_status(state, 1.0)
        else:
            self.set_status("Load audio first")

    def stop_audio(self):
        """Stop playback."""
        if self.audio_file:
            self.audio.stop()
            self.set_status("Stopped", 1.0)

    def seek_back(self):
        """Seek backward 5 seconds."""
        if self.audio_file:
            pos = max(0, self.audio.get_position() - 5)
            self.audio.set_position(pos)
            self.set_status(f"Seek: {pos:.1f}s", 1.0)

    def seek_forward(self):
        """Seek forward 5 seconds."""
        if self.audio_file:
            pos = min(self.audio.duration, self.audio.get_position() + 5)
            self.audio.set_position(pos)
            self.set_status(f"Seek: {pos:.1f}s", 1.0)

    def mark_word(self):
        """Mark current word with timestamp."""
        if self.lyrics.words and self.audio.is_playing():
            pos = self.audio.get_position()
            if self.lyrics.mark_word(pos):
                count = self.lyrics.get_timed_count()
                total = self.lyrics.get_total_words()
                self.set_status(f"Marked word ({count}/{total})", 1.0)
        elif not self.lyrics.words:
            self.set_status("Load lyrics first")
        elif not self.audio.is_playing():
            self.set_status("Start playback first")

    def unmark_word(self):
        """Unmark last timed word."""
        if self.lyrics.unmark_last():
            count = self.lyrics.get_timed_count()
            total = self.lyrics.get_total_words()
            self.set_status(f"Unmarked word ({count}/{total})", 1.0)
        else:
            self.set_status("No words to unmark")

    def reset_timings(self):
        """Reset all timing data."""
        if not self.lyrics.words:
            self.set_status("No lyrics loaded")
            return

        if self.lyrics.get_timed_count() == 0:
            self.set_status("No timings to reset")
            return

        result = dialogs.askyesno(
            "Reset Timings",
            f"Reset all {self.lyrics.get_timed_count()} word timings?"
        )
        if result:
            for word in self.lyrics.words:
                word.start_time = None
            self.lyrics.current_index = 0
            self.set_status("All timings reset")

    def save_timing(self):
        """Save timing data to JSON file."""
        if not self.lyrics.words:
            self.set_status("No lyrics to save")
            return

        # Default to same name as audio file
        default_name = ""
        if self.audio_file:
            default_name = os.path.splitext(os.path.basename(self.audio_file))[0] + ".json"

        file_path = dialogs.asksaveasfilename(
            title="Save Timing Data",
            defaultextension=".json",
            initialfile=default_name
        )
        if file_path:
            self.lyrics.save(file_path)
            self.set_status(f"Saved: {os.path.basename(file_path)}")

    def load_timing(self):
        """Load timing data from JSON file."""
        file_path = dialogs.askopenfilename(
            title="Load Timing Data",
            filetypes=[("JSON files", "*.json")]
        )
        if file_path:
            if self.lyrics.load(file_path):
                self.set_status(f"Loaded: {os.path.basename(file_path)}")
            else:
                self.set_status("Failed to load timing data")

    def save_project(self):
        """Save project (audio path + lyrics + timing) to file."""
        if not self.audio_file and not self.lyrics.words:
            self.set_status("Nothing to save")
            return

        # Default name from audio file
        default_name = ""
        if self.audio_file:
            default_name = os.path.splitext(os.path.basename(self.audio_file))[0] + ".lvproject"

        file_path = dialogs.asksaveasfilename(
            title="Save Project",
            defaultextension=".lvproject",
            initialfile=default_name
        )
        if file_path:
            import json
            project_data = {
                "version": 1,
                "audio_file": self.audio_file,
                "words": [
                    {"word": w.word, "start_time": w.start_time, "index": w.index}
                    for w in self.lyrics.words
                ]
            }
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, indent=2, ensure_ascii=False)
                self.set_status(f"Project saved: {os.path.basename(file_path)}")
            except Exception as e:
                self.set_status(f"Save failed: {e}")

    def load_project(self):
        """Load project from file."""
        file_path = dialogs.askopenfilename(
            title="Open Project",
            filetypes=[("Lyric Video Project", "*.lvproject")]
        )
        if file_path:
            self._open_project(file_path)

    def _open_project(self, file_path):
        """Internal method to open a project file."""
        import json
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            # Load audio if specified and exists
            audio_path = project_data.get("audio_file")
            if audio_path:
                # Try relative path from project file first
                if not os.path.isabs(audio_path):
                    audio_path = os.path.join(os.path.dirname(file_path), audio_path)

                if os.path.exists(audio_path):
                    if self.audio.load(audio_path):
                        self.audio_file = audio_path
                else:
                    self.set_status(f"Audio file not found: {os.path.basename(audio_path)}")

            # Load words/timing
            from lyrics_timer import TimedWord
            self.lyrics.words = [
                TimedWord(word=w["word"], start_time=w["start_time"], index=w["index"])
                for w in project_data.get("words", [])
            ]
            self.lyrics.current_index = self.lyrics.get_next_untimed_index()

            self.set_status(f"Project loaded: {os.path.basename(file_path)}")
        except Exception as e:
            self.set_status(f"Failed to load project: {e}")

    def export_video(self):
        """Export the lyric video."""
        if not self.audio_file:
            self.set_status("Load an audio file first")
            return

        if not self.lyrics.words:
            self.set_status("Load lyrics first")
            return

        if not self.lyrics.is_complete():
            result = dialogs.askyesno(
                "Incomplete Timing",
                f"Only {self.lyrics.get_timed_count()}/{self.lyrics.get_total_words()} words are timed. Export anyway?"
            )
            if not result:
                return

        # Ask for resolution
        resolution = dialogs.askchoice(
            "Video Resolution",
            "Select video resolution:",
            ["1080p (1920x1080)", "720p (1280x720)", "480p (854x480)"]
        )
        if not resolution:
            return

        # Extract resolution key (e.g., "1080p" from "1080p (1920x1080)")
        resolution_key = resolution.split()[0]

        # Default to same name as audio file
        default_name = os.path.splitext(os.path.basename(self.audio_file))[0] + ".mp4"

        file_path = dialogs.asksaveasfilename(
            title="Export Video",
            defaultextension=".mp4",
            initialfile=default_name
        )
        if file_path:
            self.set_status(f"Rendering video ({resolution_key})...")
            pygame.display.flip()

            try:
                renderer = VideoRenderer(self.lyrics, self.audio_file, resolution=resolution_key)

                def progress(p):
                    self.screen.fill(self.BG_COLOR)
                    text = self.title_font.render(f"Rendering: {int(p * 100)}%", True, self.TEXT_COLOR)
                    rect = text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
                    self.screen.blit(text, rect)
                    pygame.display.flip()

                    # Process events to prevent "not responding"
                    for event in pygame.event.get():
                        if event.type == QUIT:
                            pass  # Don't quit during render

                renderer.render(file_path, progress_callback=progress)
                self.set_status(f"Exported: {os.path.basename(file_path)}")
                dialogs.showinfo("Export Complete", f"Video saved to: {file_path}")
            except Exception as e:
                self.set_status(f"Export failed: {e}")
                dialogs.showerror("Export Error", str(e))

    def upload_youtube(self):
        """Upload video to YouTube."""
        if not self.uploader.is_configured():
            setup_instructions()
            self.set_status("YouTube API not configured. See console.")
            dialogs.showinfo(
                "YouTube Setup Required",
                "YouTube API not configured. See console/terminal for setup instructions."
            )
            return

        # First export if needed
        export_path = dialogs.askopenfilename(
            title="Select Video to Upload",
            filetypes=[("MP4 video", "*.mp4")]
        )
        if not export_path:
            return

        title = dialogs.askstring("YouTube Upload", "Video title:")
        if not title:
            return

        description = dialogs.askstring("YouTube Upload", "Description (optional):") or ""

        self.set_status("Authenticating with YouTube...")
        pygame.display.flip()

        if not self.uploader.authenticate():
            self.set_status("YouTube authentication failed")
            return

        self.set_status("Uploading to YouTube...")
        pygame.display.flip()

        def progress(p):
            self.screen.fill(self.BG_COLOR)
            text = self.title_font.render(f"Uploading: {int(p * 100)}%", True, self.TEXT_COLOR)
            rect = text.get_rect(center=(self.WIDTH // 2, self.HEIGHT // 2))
            self.screen.blit(text, rect)
            pygame.display.flip()

        url = self.uploader.upload(
            export_path, title, description,
            privacy="unlisted",
            progress_callback=progress
        )

        if url:
            self.set_status(f"Uploaded! {url}")
            # Copy URL to clipboard
            subprocess.run(['pbcopy'], input=url.encode(), check=True)
            dialogs.showinfo("Upload Complete", f"Video uploaded! {url} (URL copied to clipboard)")
        else:
            self.set_status("Upload failed")

    def handle_event(self, event):
        """Handle pygame events."""
        if event.type == QUIT:
            self.running = False
            return

        if event.type == VIDEORESIZE:
            self.WIDTH, self.HEIGHT = event.w, event.h
            self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
            self.buttons = self._create_buttons()  # Recreate buttons for new layout
            return

        # Handle button events
        for button in self.buttons:
            if button.handle_event(event):
                return

        if event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                self.running = False

            elif event.key == K_l:
                self.load_audio()

            elif event.key == K_t:
                self.load_lyrics_file()

            elif event.key == K_v:
                self.paste_lyrics()

            elif event.key == K_j:
                self.save_timing()

            elif event.key == K_k:
                self.load_timing()

            elif event.key == K_r:
                self.reset_timings()

            elif event.key == K_SPACE:
                self.mark_word()

            elif event.key in (K_DELETE, K_BACKSPACE):
                self.unmark_word()

            elif event.key == K_p:
                self.toggle_play()

            elif event.key == K_s:
                self.stop_audio()

            elif event.key == K_LEFT:
                self.seek_back()

            elif event.key == K_RIGHT:
                self.seek_forward()

            elif event.key == K_e:
                self.export_video()

    def draw(self):
        """Draw the UI."""
        self.screen.fill(self.BG_COLOR)

        # Button panel background
        panel_x = self.WIDTH - self.BUTTON_PANEL_WIDTH
        pygame.draw.rect(self.screen, self.PANEL_COLOR, (panel_x, 0, self.BUTTON_PANEL_WIDTH, self.HEIGHT))
        pygame.draw.line(self.screen, (60, 60, 60), (panel_x, 0), (panel_x, self.HEIGHT), 1)

        # Title
        title = self.title_font.render("FREE Lyric Video Creator", True, self.TEXT_COLOR)
        self.screen.blit(title, (self.MARGIN, self.MARGIN))

        # Panel title
        panel_title = self.small_font.render("Controls", True, self.DIM_COLOR)
        self.screen.blit(panel_title, (panel_x + 10, 20))

        # Draw buttons
        for button in self.buttons:
            button.draw(self.screen, self.button_font)

        # Audio info
        content_width = panel_x - self.MARGIN * 2
        y = self.MARGIN + 45

        if self.audio_file:
            audio_text = f"Audio: {os.path.basename(self.audio_file)}"
            audio_surface = self.small_font.render(audio_text, True, self.TEXT_COLOR)
        else:
            audio_surface = self.small_font.render("No audio loaded", True, self.DIM_COLOR)
        self.screen.blit(audio_surface, (self.MARGIN, y))

        # Time display
        y += 22
        if self.audio_file:
            pos = self.audio.get_position()
            dur = self.audio.duration
            state = "PLAYING" if self.audio.is_playing() else "PAUSED" if self.audio.is_paused() else "STOPPED"
            time_text = f"{self._format_time(pos)} / {self._format_time(dur)}  [{state}]"
            time_color = self.TIMED_COLOR if self.audio.is_playing() else self.TEXT_COLOR
            time_surface = self.small_font.render(time_text, True, time_color)
            self.screen.blit(time_surface, (self.MARGIN, y))

        # Progress bar
        y += 25
        bar_width = content_width
        bar_height = 12
        pygame.draw.rect(self.screen, self.DIM_COLOR, (self.MARGIN, y, bar_width, bar_height), border_radius=6)
        if self.audio.duration > 0:
            progress = self.audio.get_position() / self.audio.duration
            fill_width = int(bar_width * progress)
            if fill_width > 0:
                pygame.draw.rect(self.screen, self.TIMED_COLOR, (self.MARGIN, y, fill_width, bar_height), border_radius=6)

        # Lyrics display
        y += 30
        lyrics_area_height = self.HEIGHT - y - 70

        if not self.lyrics.words:
            no_lyrics = self.font.render("No lyrics loaded", True, self.DIM_COLOR)
            self.screen.blit(no_lyrics, (self.MARGIN, y + 50))
        else:
            # Get the next word index to time
            next_untimed = self.lyrics.get_next_untimed_index()
            current_time = self.audio.get_position()
            current_word, _ = self.lyrics.get_word_at_time(current_time) if self.audio.is_playing() else (None, 0)

            # Calculate scroll to keep current/next word visible
            start_y = y
            x = self.MARGIN
            visible_start = 0

            # Find where to start drawing (scroll to current position)
            if next_untimed > 20:
                visible_start = max(0, next_untimed - 10)

            word_idx = 0
            for word in self.lyrics.words:
                if word_idx < visible_start:
                    if word.word == '\n':
                        pass
                    word_idx += 1
                    continue

                if word.word == '\n':
                    x = self.MARGIN
                    y += self.LINE_HEIGHT
                    word_idx += 1
                    continue

                if y > self.HEIGHT - 90:
                    break

                # Determine color
                if current_word and word.index == current_word.index:
                    color = self.CURRENT_COLOR
                elif word.start_time is not None:
                    color = self.TIMED_COLOR
                elif word.index == next_untimed:
                    color = self.TEXT_COLOR
                else:
                    color = self.DIM_COLOR

                word_surface = self.font.render(word.word, True, color)
                word_width = word_surface.get_width()

                # Wrap to next line if needed
                if x + word_width > content_width:
                    x = self.MARGIN
                    y += self.LINE_HEIGHT

                self.screen.blit(word_surface, (x, y))
                x += word_width + 10
                word_idx += 1

        # Status bar
        y = self.HEIGHT - 50
        pygame.draw.rect(self.screen, self.STATUS_BG, (0, y, panel_x, 50))

        # Stats
        stats = f"Words timed: {self.lyrics.get_timed_count()} / {self.lyrics.get_total_words()}"
        stats_surface = self.small_font.render(stats, True, self.TEXT_COLOR)
        self.screen.blit(stats_surface, (self.MARGIN, y + 8))

        # Keyboard hint
        hint = "SPACE=mark | DEL=unmark | P=play/pause | Arrow keys=seek"
        hint_surface = self.small_font.render(hint, True, self.DIM_COLOR)
        self.screen.blit(hint_surface, (self.MARGIN, y + 28))

        # Status message
        if pygame.time.get_ticks() < self.status_time:
            status_surface = self.small_font.render(self.status_message, True, self.CURRENT_COLOR)
            status_rect = status_surface.get_rect(right=panel_x - 10, centery=y + 25)
            self.screen.blit(status_surface, status_rect)

        pygame.display.flip()

    def _format_time(self, seconds):
        """Format seconds as mm:ss."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def run(self):
        """Main loop."""
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle_event(event)

                self.draw()
                self.clock.tick(30)

        finally:
            self.audio.cleanup()
            pygame.quit()


def main():
    # Check for command line argument (file to open)
    initial_file = None
    if len(sys.argv) > 1:
        initial_file = sys.argv[1]
        if not os.path.isabs(initial_file):
            initial_file = os.path.abspath(initial_file)

    app = LyricVideoCreator(initial_file)
    app.run()


if __name__ == '__main__':
    main()
