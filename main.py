"""
FREE Lyric Video Creator

Controls:
- SPACE: Mark current word with timestamp
- DELETE/BACKSPACE: Unmark last timed word
- P: Play/Pause audio
- S: Stop and reset to beginning
- LEFT/RIGHT: Seek backward/forward 5 seconds
- E: Export video
- L: Load audio file
- T: Load lyrics text file
- V: Paste lyrics from clipboard
- J: Save timing data
- K: Load timing data
- R: Reset all timings
- ESC: Quit

Or use the buttons!
"""
import copy
import math
import os
import sys
import platform
import threading
import time as _time
import webbrowser

from utils import resource_path


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
        icon_path = resource_path('AppIcon.icns')
        if os.path.exists(icon_path):
            app = NSApplication.sharedApplication()
            icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
            if icon:
                app.setApplicationIconImage_(icon)
    except ImportError:
        pass

import pygame
import dialogs
from pygame import QUIT, KEYDOWN, MOUSEBUTTONDOWN, MOUSEBUTTONUP, MOUSEMOTION, VIDEORESIZE, TEXTINPUT
from pygame import K_SPACE, K_DELETE, K_BACKSPACE
from pygame import K_RETURN, K_HOME, K_END, K_UP, K_DOWN
from pygame import K_a, K_p, K_s, K_LEFT, K_RIGHT, K_e, K_l, K_t, K_v, K_j, K_k, K_r, K_ESCAPE

from audio_player import AudioPlayer
from lyrics_timer import LyricsTimer
from video_renderer import VideoRenderer, RenderCancelled, render_preview_frame, RESOLUTIONS


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

        # Text
        text_color = (250, 250, 250)
        text_surface = font.render(self.text, True, text_color)
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
    # Colors — classic dark
    BG_COLOR = (20, 20, 20)
    TEXT_COLOR = (250, 250, 250)
    TIMED_COLOR = (100, 200, 100)
    CURRENT_COLOR = (255, 215, 0)
    DIM_COLOR = (100, 100, 100)
    STATUS_BG = (40, 40, 40)
    PANEL_COLOR = (30, 30, 30)
    ACCENT_COLOR = (60, 60, 60)
    ACCENT_GLOW = (255, 215, 0)

    # Layout
    WIDTH = 1150
    HEIGHT = 750
    MARGIN = 20
    LINE_HEIGHT = 36
    BUTTON_PANEL_WIDTH = 160

    def __init__(self, initial_file=None):
        pygame.init()
        pygame.display.set_caption("FREE Lyric Video Creator")

        # Set dock/window icon (try BMP first for Python 3.14 pygame compatibility)
        for icon_name in ['icon.bmp', 'icon.png']:
            icon_path = resource_path(icon_name)
            if os.path.exists(icon_path):
                try:
                    icon = pygame.image.load(icon_path)
                    pygame.display.set_icon(icon)
                    break
                except pygame.error:
                    continue

        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.audio = AudioPlayer()
        self.lyrics = LyricsTimer()

        _font_path = pygame.font.match_font('arial') or pygame.font.match_font('helvetica')
        _font_path_bold = pygame.font.match_font('arial', bold=True) or pygame.font.match_font('helvetica', bold=True) or _font_path
        if _font_path:
            self.font = pygame.font.Font(_font_path, 24)
            self.small_font = pygame.font.Font(_font_path, 16)
            self.title_font = pygame.font.Font(_font_path_bold, 28)
            self.button_font = pygame.font.Font(_font_path, 14)
            self.label_font = pygame.font.Font(_font_path_bold, 11)
        else:
            self.font = pygame.font.Font(None, 24)
            self.small_font = pygame.font.Font(None, 16)
            self.title_font = pygame.font.Font(None, 28)
            self.button_font = pygame.font.Font(None, 14)
            self.label_font = pygame.font.Font(None, 11)

        self.audio_file = None
        self.running = True
        self.status_message = "Load audio and lyrics to get started"
        self.status_time = 0

        # Inline lyrics editor state
        self.editing = False
        self.edit_text = ""
        self.edit_cursor = 0
        self.edit_scroll_y = 0
        self.edit_saved_lyrics = ""
        self.edit_sel_start = None  # None = no selection, int = anchor position
        self.edit_last_click_time = 0  # for double-click detection
        self._edit_dragging = False
        self._edit_drag_origin = 0
        self.edit_buttons = []

        # Smooth scroll state for lyrics display
        self.lyrics_scroll_y = 0.0

        # Cached wrap results for hit-testing (set by _draw_editor)
        self._edit_lines = ['']
        self._edit_line_starts = [0]
        self._edit_top_y = 0
        self._edit_line_h = 36

        # Create buttons
        self.buttons = self._create_buttons()

        # Load initial file if provided
        if initial_file:
            self._load_initial_file(initial_file)

    def _create_buttons(self):
        """Create all UI buttons."""
        buttons = []
        self.panel_labels = []  # (label_text, y_position)
        x = self.WIDTH - self.BUTTON_PANEL_WIDTH + 10
        y = 60
        w = self.BUTTON_PANEL_WIDTH - 20
        h = 32
        gap = 8
        # FILE section
        self.panel_labels.append(("FILE", y - 14))
        buttons.append(Button(x, y, w, h, "Load Audio (L)", self.load_audio))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Load Lyrics (T)", self.load_lyrics_file))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Paste Lyrics (V)", self.paste_lyrics))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Type Lyrics", self.type_lyrics))
        y += h + gap + 14

        # PLAYBACK section
        self.panel_labels.append(("PLAYBACK", y - 14))
        buttons.append(Button(x, y, w, h, "Play / Pause (P)", self.toggle_play, color=(50, 80, 50)))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Stop (S)", self.stop_audio))
        y += h + gap
        buttons.append(Button(x, y, w//2 - 2, h, "<< 5s", self.seek_back))
        buttons.append(Button(x + w//2 + 2, y, w//2 - 2, h, "5s >>", self.seek_forward))
        y += h + gap + 14

        # TIMING section
        self.panel_labels.append(("TIMING", y - 14))
        buttons.append(Button(x, y, w, h, "Mark Word (SPACE)", self.mark_word, color=(80, 80, 50)))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Unmark Last (DEL)", self.unmark_word))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Reset All Timings", self.reset_timings, color=(80, 50, 50)))
        y += h + gap + 14

        # PROJECT section
        self.panel_labels.append(("PROJECT", y - 14))
        buttons.append(Button(x, y, w, h, "Save Project", self.save_project, color=(50, 70, 50)))
        y += h + gap
        buttons.append(Button(x, y, w, h, "Open Project", self.load_project, color=(50, 70, 50)))
        y += h + gap + 14

        # EXPORT section
        self.panel_labels.append(("EXPORT", y - 14))
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
        """Enter inline edit mode for lyrics."""
        existing = self.lyrics.get_lyrics_text() if self.lyrics.words else ""
        self.edit_saved_lyrics = existing
        self.edit_text = existing
        self.edit_cursor = len(self.edit_text)
        self.edit_scroll_y = 0
        self.edit_sel_start = None
        self._edit_dragging = False
        self._edit_drag_origin = 0
        self.editing = True
        self.edit_buttons = [
            Button(0, 0, 100, 32, "Save", self._confirm_edit, color=(50, 80, 50)),
            Button(0, 0, 100, 32, "Cancel", self._cancel_edit, color=(80, 50, 50)),
        ]
        pygame.key.set_repeat(400, 50)

    def _confirm_edit(self):
        """Save edited lyrics and exit edit mode."""
        text = self.edit_text.strip()
        if text:
            self.lyrics.load_lyrics(text)
            self.set_status(f"Loaded {self.lyrics.get_total_words()} words")
        else:
            self.set_status("No lyrics entered")
        self._exit_edit_mode()

    def _cancel_edit(self):
        """Discard edits and exit edit mode."""
        self._exit_edit_mode()
        self.set_status("Edit cancelled", 1.5)

    def _exit_edit_mode(self):
        """Shared cleanup when leaving edit mode."""
        self.editing = False
        self.edit_text = ""
        self.edit_cursor = 0
        self.edit_scroll_y = 0
        self.edit_sel_start = None
        self._edit_dragging = False
        self.edit_buttons = []
        pygame.key.set_repeat(0)

    def _handle_edit_key(self, event):
        """Handle a KEYDOWN event while in edit mode."""
        mods = event.mod
        ctrl = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)

        if event.key == K_RETURN:
            if ctrl:
                self._confirm_edit()
            else:
                self._editor_insert('\n')
            return

        if event.key == K_ESCAPE:
            self._cancel_edit()
            return

        if event.key == K_BACKSPACE:
            if not self._delete_selection():
                if self.edit_cursor > 0:
                    self.edit_text = self.edit_text[:self.edit_cursor - 1] + self.edit_text[self.edit_cursor:]
                    self.edit_cursor -= 1
            return

        if event.key == K_DELETE:
            if not self._delete_selection():
                if self.edit_cursor < len(self.edit_text):
                    self.edit_text = self.edit_text[:self.edit_cursor] + self.edit_text[self.edit_cursor + 1:]
            return

        shift = mods & pygame.KMOD_SHIFT

        if event.key == K_LEFT:
            if shift:
                if self.edit_sel_start is None:
                    self.edit_sel_start = self.edit_cursor
                if self.edit_cursor > 0:
                    self.edit_cursor -= 1
            else:
                self.edit_sel_start = None
                if self.edit_cursor > 0:
                    self.edit_cursor -= 1
            return

        if event.key == K_RIGHT:
            if shift:
                if self.edit_sel_start is None:
                    self.edit_sel_start = self.edit_cursor
                if self.edit_cursor < len(self.edit_text):
                    self.edit_cursor += 1
            else:
                self.edit_sel_start = None
                if self.edit_cursor < len(self.edit_text):
                    self.edit_cursor += 1
            return

        if event.key == K_UP:
            if shift:
                if self.edit_sel_start is None:
                    self.edit_sel_start = self.edit_cursor
                self._editor_move_vertical(-1)
            else:
                self.edit_sel_start = None
                self._editor_move_vertical(-1)
            return

        if event.key == K_DOWN:
            if shift:
                if self.edit_sel_start is None:
                    self.edit_sel_start = self.edit_cursor
                self._editor_move_vertical(1)
            else:
                self.edit_sel_start = None
                self._editor_move_vertical(1)
            return

        if event.key == K_HOME:
            if shift:
                if self.edit_sel_start is None:
                    self.edit_sel_start = self.edit_cursor
            else:
                self.edit_sel_start = None
            line_start = self.edit_text.rfind('\n', 0, self.edit_cursor)
            self.edit_cursor = line_start + 1 if line_start != -1 else 0
            return

        if event.key == K_END:
            if shift:
                if self.edit_sel_start is None:
                    self.edit_sel_start = self.edit_cursor
            else:
                self.edit_sel_start = None
            line_end = self.edit_text.find('\n', self.edit_cursor)
            self.edit_cursor = line_end if line_end != -1 else len(self.edit_text)
            return

        if ctrl and event.key == K_a:
            self.edit_sel_start = 0
            self.edit_cursor = len(self.edit_text)
            return

        if ctrl and event.key == K_v:
            clipboard = dialogs.get_clipboard()
            if clipboard:
                self._editor_insert(clipboard)
            return

    def _has_selection(self):
        """Return True if there is an active selection."""
        return self.edit_sel_start is not None and self.edit_sel_start != self.edit_cursor

    def _get_selection_range(self):
        """Return (start, end) of the current selection, ordered."""
        if self.edit_sel_start is None:
            return self.edit_cursor, self.edit_cursor
        return min(self.edit_sel_start, self.edit_cursor), max(self.edit_sel_start, self.edit_cursor)

    def _delete_selection(self):
        """Delete the selected text. Returns True if there was a selection."""
        if not self._has_selection():
            return False
        start, end = self._get_selection_range()
        self.edit_text = self.edit_text[:start] + self.edit_text[end:]
        self.edit_cursor = start
        self.edit_sel_start = None
        return True

    def _editor_insert(self, text):
        """Insert text at cursor position, replacing selection if any."""
        self._delete_selection()
        self.edit_text = self.edit_text[:self.edit_cursor] + text + self.edit_text[self.edit_cursor:]
        self.edit_cursor += len(text)

    def _editor_move_vertical(self, direction):
        """Move cursor up (-1) or down (+1) by one logical line."""
        text = self.edit_text
        # Find current line start and column
        line_start = text.rfind('\n', 0, self.edit_cursor)
        col = self.edit_cursor - (line_start + 1) if line_start != -1 else self.edit_cursor

        if direction == -1:
            # Move up
            if line_start == -1:
                return  # Already on first line
            prev_line_start = text.rfind('\n', 0, line_start)
            prev_start = prev_line_start + 1 if prev_line_start != -1 else 0
            prev_len = line_start - prev_start
            self.edit_cursor = prev_start + min(col, prev_len)
        else:
            # Move down
            line_end = text.find('\n', self.edit_cursor)
            if line_end == -1:
                return  # Already on last line
            next_start = line_end + 1
            next_line_end = text.find('\n', next_start)
            next_len = (next_line_end if next_line_end != -1 else len(text)) - next_start
            self.edit_cursor = next_start + min(col, next_len)

    def _hit_test_editor(self, x, y):
        """Given pixel coordinates, return the source-text cursor position."""
        lines = self._edit_lines
        line_starts = self._edit_line_starts
        top_y = self._edit_top_y
        line_h = self._edit_line_h

        # Compute row from y coordinate (account for scroll)
        row = int((y - top_y + self.edit_scroll_y) // line_h)
        row = max(0, min(row, len(lines) - 1))

        # Walk characters in the row to find closest column
        line = lines[row]
        col = len(line)  # default to end of line
        local_x = x - self.MARGIN
        for i in range(len(line)):
            char_x = self.font.size(line[:i + 1])[0]
            prev_x = self.font.size(line[:i])[0] if i > 0 else 0
            mid = (prev_x + char_x) / 2
            if local_x < mid:
                col = i
                break

        return line_starts[row] + col

    def _find_word_bounds(self, pos):
        """Return (start, end) of the word at source-text position pos."""
        text = self.edit_text
        start = pos
        end = pos
        while start > 0 and text[start - 1] not in (' ', '\n'):
            start -= 1
        while end < len(text) and text[end] not in (' ', '\n'):
            end += 1
        return start, end

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

            render_cancelled = [False]
            render_start = [0.0]
            eta_display = [""]
            eta_last_update = [0.0]

            try:
                renderer = VideoRenderer(self.lyrics, self.audio_file, resolution=resolution_key)
                vid_w, vid_h = RESOLUTIONS.get(resolution_key, RESOLUTIONS["1080p"])
                output_filename = os.path.basename(file_path)

                # Cancel text-link rect (updated each frame in progress())
                cancel_rect = [pygame.Rect(0, 0, 0, 0)]
                cancel_hovered = [False]

                # Social link rects/urls for hover + click (populated each frame)
                social_rects = []  # list of (pygame.Rect, url)

                # Pre-load social icon images
                _social_icons = {}
                for _name in ("instagram", "youtube", "spotify"):
                    _path = resource_path(f"icon_{_name}.png")
                    if os.path.exists(_path):
                        _social_icons[_name] = pygame.image.load(_path).convert_alpha()

                def progress(p, frame=None, frame_num=0, total_frames=0):
                    self.screen.fill(self.BG_COLOR)
                    cx, cy = self.WIDTH // 2, self.HEIGHT // 2

                    # --- Title + info ---
                    title_surf = self.title_font.render("Exporting Video", True, self.TEXT_COLOR)
                    self.screen.blit(title_surf, title_surf.get_rect(center=(cx, int(self.HEIGHT * 0.10))))

                    info_text = f"{vid_w} \u00d7 {vid_h}  \u00b7  {output_filename}"
                    info_surf = self.small_font.render(info_text, True, self.DIM_COLOR)
                    self.screen.blit(info_surf, info_surf.get_rect(center=(cx, int(self.HEIGHT * 0.15))))

                    # --- Circular progress ring ---
                    ring_radius = 60
                    ring_width = 5
                    pulse = math.sin(pygame.time.get_ticks() / 400.0) * 2
                    r = int(ring_radius + pulse)
                    ring_cy = int(self.HEIGHT * 0.30)
                    ring_rect = pygame.Rect(cx - r, ring_cy - r, r * 2, r * 2)

                    # Track (full circle)
                    pygame.draw.arc(self.screen, self.DIM_COLOR, ring_rect,
                                    0, math.tau, ring_width)
                    # Progress arc (sweeps clockwise from top)
                    if p > 0:
                        start = math.pi / 2
                        end = start + p * math.tau
                        pygame.draw.arc(self.screen, self.TIMED_COLOR, ring_rect,
                                        start, end, ring_width)

                    # Percentage inside ring
                    pct_text = f"{int(p * 100)}%"
                    pct_surf = self.title_font.render(pct_text, True, self.TEXT_COLOR)
                    self.screen.blit(pct_surf, pct_surf.get_rect(center=(cx, ring_cy)))

                    # --- Frame count + ETA ---
                    now = _time.monotonic()
                    if render_start[0] == 0.0:
                        render_start[0] = now

                    if p >= 0.02 and now - eta_last_update[0] >= 3.0:
                        elapsed = now - render_start[0]
                        remaining = (elapsed / p) * (1.0 - p)
                        mins, secs = divmod(int(remaining), 60)
                        eta_display[0] = f"{mins}:{secs:02d}"
                        eta_last_update[0] = now

                    if eta_display[0]:
                        eta_part = f"  \u2014  Estimated time left: {eta_display[0]}"
                    else:
                        eta_part = "  \u2014  Estimated time left: calculating..."

                    frame_text = f"Frame {frame_num:,} / {total_frames:,}{eta_part}"
                    frame_surf = self.small_font.render(frame_text, True, self.DIM_COLOR)
                    self.screen.blit(frame_surf, frame_surf.get_rect(center=(cx, int(self.HEIGHT * 0.44))))

                    # --- Thumbnail preview ---
                    thumb_y = int(self.HEIGHT * 0.48)
                    if frame is not None:
                        thumb_h = int(self.HEIGHT * 0.22)
                        thumb_w = int(thumb_h * vid_w / vid_h)
                        thumb_surf = pygame.image.frombuffer(
                            frame.tobytes(), (frame.shape[1], frame.shape[0]), 'RGB'
                        )
                        thumb_surf = pygame.transform.smoothscale(thumb_surf, (thumb_w, thumb_h))
                        thumb_x = cx - thumb_w // 2
                        border = 2
                        pygame.draw.rect(self.screen, self.DIM_COLOR,
                                         (thumb_x - border, thumb_y - border,
                                          thumb_w + border * 2, thumb_h + border * 2),
                                         border_radius=4)
                        self.screen.blit(thumb_surf, (thumb_x, thumb_y))

                    # --- Cancel text link ---
                    cancel_label = "Cancel (Esc)"
                    cancel_color = self.TEXT_COLOR if cancel_hovered[0] else self.DIM_COLOR
                    cancel_surf = self.small_font.render(cancel_label, True, cancel_color)
                    cancel_x = cx - cancel_surf.get_width() // 2
                    cancel_y = int(self.HEIGHT * 0.73)
                    self.screen.blit(cancel_surf, (cancel_x, cancel_y))
                    ul_y = cancel_y + cancel_surf.get_height() + 1
                    pygame.draw.line(self.screen, cancel_color,
                                     (cancel_x, ul_y),
                                     (cancel_x + cancel_surf.get_width(), ul_y), 1)
                    cancel_rect[0] = pygame.Rect(cancel_x, cancel_y,
                                                  cancel_surf.get_width(),
                                                  cancel_surf.get_height() + 4)

                    # --- RAIDEN promo section ---
                    promo_top = int(self.HEIGHT * 0.78)

                    # Divider line
                    div_w = min(400, self.WIDTH - 80)
                    pygame.draw.line(self.screen, (50, 50, 50),
                                     (cx - div_w // 2, promo_top),
                                     (cx + div_w // 2, promo_top), 1)

                    # Promo message (two lines for readability)
                    line1 = "Hope you're enjoying this free app! I built it to share songs"
                    line2 = "and lyrics with my band RAIDEN \u2014 check us out!"
                    line1_surf = self.small_font.render(line1, True, self.DIM_COLOR)
                    line2_surf = self.small_font.render(line2, True, self.DIM_COLOR)
                    self.screen.blit(line1_surf, line1_surf.get_rect(center=(cx, promo_top + 18)))
                    self.screen.blit(line2_surf, line2_surf.get_rect(center=(cx, promo_top + 36)))

                    # Social icons row (icon images only, no text labels)
                    icon_display_size = 28
                    icon_gap = 52
                    icon_y = promo_top + 66
                    mouse_pos = pygame.mouse.get_pos()

                    socials = [
                        ("instagram", "https://www.instagram.com/raiden.uruguay/"),
                        ("youtube", "https://www.youtube.com/channel/UCMXZ_2MJMHX00-RPPgcwSSg"),
                        ("spotify", "https://open.spotify.com/artist/7aeHdbSpQpe0pBxxFYwBrb"),
                    ]
                    social_rects.clear()
                    total_w = (len(socials) - 1) * icon_gap
                    start_x = cx - total_w // 2

                    for i, (kind, url) in enumerate(socials):
                        ix = start_x + i * icon_gap
                        hit_rect = pygame.Rect(ix - icon_display_size // 2 - 4,
                                               icon_y - icon_display_size // 2 - 4,
                                               icon_display_size + 8, icon_display_size + 8)
                        is_hovered = hit_rect.collidepoint(mouse_pos)
                        social_rects.append((hit_rect, url))

                        if kind in _social_icons:
                            icon_surf = pygame.transform.smoothscale(
                                _social_icons[kind],
                                (icon_display_size, icon_display_size))
                            if is_hovered:
                                # Brighten on hover
                                bright = pygame.Surface(icon_surf.get_size(), pygame.SRCALPHA)
                                bright.fill((60, 60, 60, 0))
                                icon_surf = icon_surf.copy()
                                icon_surf.blit(bright, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
                            else:
                                # Dim slightly when not hovered
                                icon_surf.set_alpha(180)
                            self.screen.blit(icon_surf,
                                             (ix - icon_display_size // 2,
                                              icon_y - icon_display_size // 2))

                    pygame.display.flip()

                    # Process events to prevent "not responding"
                    for event in pygame.event.get():
                        if event.type == QUIT:
                            pass  # Don't quit during render
                        elif event.type == KEYDOWN and event.key == K_ESCAPE:
                            if dialogs.askyesno("Cancel Export", "Cancel the video export?"):
                                render_cancelled[0] = True
                        elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                            if cancel_rect[0].collidepoint(event.pos):
                                if dialogs.askyesno("Cancel Export", "Cancel the video export?"):
                                    render_cancelled[0] = True
                            else:
                                for rect, url in social_rects:
                                    if rect.collidepoint(event.pos):
                                        webbrowser.open(url)
                                        break
                        elif event.type == MOUSEMOTION:
                            cancel_hovered[0] = cancel_rect[0].collidepoint(event.pos)
                            any_hovered = cancel_hovered[0] or any(
                                r.collidepoint(event.pos) for r, _ in social_rects)
                            pygame.mouse.set_cursor(
                                pygame.SYSTEM_CURSOR_HAND if any_hovered else pygame.SYSTEM_CURSOR_ARROW)

                renderer.render(file_path, progress_callback=progress,
                                check_cancelled=lambda: render_cancelled[0])
                self.set_status(f"Exported: {os.path.basename(file_path)}")
                dialogs.showinfo("Export Complete", f"Video saved to: {file_path}")
            except RenderCancelled:
                self.set_status("Export cancelled")
            except Exception as e:
                self.set_status(f"Export failed: {e}")
                dialogs.showerror("Export Error", str(e))

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

        # In edit mode, intercept all keyboard input
        if self.editing:
            if event.type == TEXTINPUT:
                self._editor_insert(event.text)
                return
            if event.type == KEYDOWN:
                self._handle_edit_key(event)
                return
            # Allow Save/Cancel button clicks and hover
            for btn in self.edit_buttons:
                if btn.handle_event(event):
                    return
            # Mouse interactions in editor
            if event.type == MOUSEBUTTONDOWN and event.button == 1:
                pos = self._hit_test_editor(event.pos[0], event.pos[1])
                now = pygame.time.get_ticks()
                if now - self.edit_last_click_time < 400:
                    # Double-click: select word at position
                    start, end = self._find_word_bounds(pos)
                    self.edit_sel_start = start
                    self.edit_cursor = end
                else:
                    # Single click: position cursor, clear selection
                    self.edit_cursor = pos
                    self.edit_sel_start = None
                self.edit_last_click_time = now
                self._edit_dragging = True
                self._edit_drag_origin = pos
                return
            if event.type == MOUSEMOTION and self._edit_dragging:
                pos = self._hit_test_editor(event.pos[0], event.pos[1])
                if self.edit_sel_start is None:
                    self.edit_sel_start = self._edit_drag_origin
                self.edit_cursor = pos
                return
            if event.type == MOUSEBUTTONUP and event.button == 1:
                self._edit_dragging = False
                return
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

        # Panel divider — 4px gradient shadow for depth
        for i in range(4):
            alpha = 40 - i * 10
            shadow_color = (0, 0, 0)
            shadow_surf = pygame.Surface((1, self.HEIGHT), pygame.SRCALPHA)
            shadow_surf.fill((*shadow_color, alpha))
            self.screen.blit(shadow_surf, (panel_x + i, 0))

        # Title
        title = self.title_font.render("FREE Lyric Video Creator", True, self.TEXT_COLOR)
        self.screen.blit(title, (self.MARGIN, self.MARGIN))

        # Title accent underline
        title_underline_y = self.MARGIN + title.get_height() + 4
        pygame.draw.line(self.screen, self.ACCENT_GLOW,
                         (self.MARGIN, title_underline_y),
                         (self.MARGIN + title.get_width(), title_underline_y), 2)

        # Panel header — uppercase "CONTROLS" with thin underline
        header_text = self.label_font.render("CONTROLS", True, self.DIM_COLOR)
        header_x = panel_x + 10
        header_y = 16
        self.screen.blit(header_text, (header_x, header_y))
        underline_y = header_y + header_text.get_height() + 3
        pygame.draw.line(self.screen, self.ACCENT_COLOR,
                         (header_x, underline_y),
                         (panel_x + self.BUTTON_PANEL_WIDTH - 10, underline_y), 1)

        # Panel section labels
        for label_text, label_y in self.panel_labels:
            label_surf = self.label_font.render(label_text, True, self.DIM_COLOR)
            self.screen.blit(label_surf, (panel_x + 10, label_y))
            line_y = label_y + label_surf.get_height() + 1
            pygame.draw.line(self.screen, self.ACCENT_COLOR,
                             (panel_x + 10 + label_surf.get_width() + 6, line_y),
                             (panel_x + self.BUTTON_PANEL_WIDTH - 10, line_y), 1)

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

        # Progress bar — thin pill with glow dot
        y += 25
        bar_width = content_width
        bar_height = 6
        bar_y = y + 3  # vertically center the thinner bar
        # Dark inset track
        pygame.draw.rect(self.screen, (30, 30, 30), (self.MARGIN, bar_y, bar_width, bar_height), border_radius=3)
        if self.audio.duration > 0:
            progress = self.audio.get_position() / self.audio.duration
            fill_width = int(bar_width * progress)
            if fill_width > 0:
                pygame.draw.rect(self.screen, self.TIMED_COLOR, (self.MARGIN, bar_y, fill_width, bar_height), border_radius=3)
                # Glow dot at leading edge
                dot_x = self.MARGIN + fill_width
                dot_y = bar_y + bar_height // 2
                pygame.draw.circle(self.screen, self.TIMED_COLOR, (dot_x, dot_y), 5)
                glow_surf = pygame.Surface((16, 16), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*self.TIMED_COLOR, 60), (8, 8), 8)
                self.screen.blit(glow_surf, (dot_x - 8, dot_y - 8))

        # Lyrics display / Editor
        y += 30
        lyrics_area_height = self.HEIGHT - y - 80

        if self.editing:
            self._draw_editor(y, content_width, lyrics_area_height)
        elif not self.lyrics.words:
            no_lyrics = self.font.render("No lyrics loaded", True, self.DIM_COLOR)
            self.screen.blit(no_lyrics, (self.MARGIN, y + 50))
        else:
            # Get the next word index to time
            next_untimed = self.lyrics.get_next_untimed_index()
            current_time = self.audio.get_position()
            is_playing = self.audio.is_playing()
            current_word, _ = self.lyrics.get_word_at_time(current_time) if is_playing else (None, 0)

            # Lookahead word for scroll target (500ms ahead)
            lookahead_word, _ = self.lyrics.get_word_at_time(current_time + 0.5) if is_playing else (None, 0)

            lyrics_top = y
            lyrics_area_center = lyrics_top + lyrics_area_height // 2

            # --- Layout pass: compute (x, y) for every word ---
            layout = []  # list of (word, lx, ly)
            lx = self.MARGIN
            ly = 0  # relative y (before scroll offset)
            target_y = 0

            for word in self.lyrics.words:
                if word.word == '\n':
                    lx = self.MARGIN
                    ly += self.LINE_HEIGHT
                    continue

                word_surface = self.font.render(word.word, True, self.TEXT_COLOR)
                word_width = word_surface.get_width()

                # Wrap to next line if needed
                if lx + word_width > content_width:
                    lx = self.MARGIN
                    ly += self.LINE_HEIGHT

                layout.append((word, lx, ly))

                # Scroll target uses lookahead word (500ms ahead) so the
                # view pre-scrolls before the highlight reaches a new line
                if lookahead_word and word.index == lookahead_word.index:
                    target_y = ly
                elif lookahead_word is None:
                    if current_word and word.index == current_word.index:
                        target_y = ly
                    elif current_word is None and word.index == next_untimed:
                        target_y = ly

                lx += word_width + 10

            # --- Snap scroll to target line ---
            scroll_target = target_y - (lyrics_area_center - lyrics_top)
            scroll_target = max(0, scroll_target)
            self.lyrics_scroll_y = scroll_target

            # --- Draw pass: clip to lyrics area and render words ---
            clip_rect = pygame.Rect(0, lyrics_top, panel_x, lyrics_area_height)
            self.screen.set_clip(clip_rect)

            for word, lx, ly in layout:
                draw_y = lyrics_top + ly - self.lyrics_scroll_y

                # Skip words fully outside clip area
                if draw_y + self.LINE_HEIGHT < lyrics_top or draw_y > lyrics_top + lyrics_area_height:
                    continue

                # Determine color
                is_current = current_word and word.index == current_word.index
                if is_current:
                    color = self.CURRENT_COLOR
                elif word.start_time is not None:
                    color = self.TIMED_COLOR
                elif word.index == next_untimed:
                    color = self.TEXT_COLOR
                else:
                    color = self.DIM_COLOR

                word_surface = self.font.render(word.word, True, color)

                # Semi-transparent gold pill behind the current word
                if is_current:
                    pill_pad_x, pill_pad_y = 4, 2
                    pill_w = word_surface.get_width() + pill_pad_x * 2
                    pill_h = word_surface.get_height() + pill_pad_y * 2
                    pill_surf = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
                    pygame.draw.rect(pill_surf, (255, 215, 0, 35), (0, 0, pill_w, pill_h), border_radius=6)
                    self.screen.blit(pill_surf, (lx - pill_pad_x, draw_y - pill_pad_y))

                self.screen.blit(word_surface, (lx, draw_y))

            self.screen.set_clip(None)

        # Status bar
        bar_h = 65
        y = self.HEIGHT - bar_h
        pygame.draw.rect(self.screen, self.STATUS_BG, (0, y, panel_x, bar_h))
        # 1px accent line at top edge
        pygame.draw.line(self.screen, self.ACCENT_COLOR, (0, y), (panel_x, y), 1)

        # Top row: stats (white, left-aligned)
        row1_y = y + 10
        stats = f"Words timed: {self.lyrics.get_timed_count()} / {self.lyrics.get_total_words()}"
        stats_surface = self.small_font.render(stats, True, self.TEXT_COLOR)
        self.screen.blit(stats_surface, (self.MARGIN, row1_y))

        # Bottom row: keyboard hint (grey, left-aligned)
        row2_y = y + 32
        if self.editing:
            mod_key = "Cmd" if IS_MAC else "Ctrl"
            hint = f"EDITING — {mod_key}+Enter=save | ESC=cancel | {mod_key}+V=paste"
            hint_surface = self.small_font.render(hint, True, self.CURRENT_COLOR)
        else:
            hint = "SPACE=mark | DEL=unmark | P=play/pause | Arrow keys=seek"
            hint_surface = self.small_font.render(hint, True, self.DIM_COLOR)
        self.screen.blit(hint_surface, (self.MARGIN, row2_y))

        # Status message (right-aligned, vertically centered)
        if pygame.time.get_ticks() < self.status_time:
            status_surface = self.small_font.render(self.status_message, True, self.CURRENT_COLOR)
            status_rect = status_surface.get_rect(right=panel_x - 10, centery=y + bar_h // 2)
            self.screen.blit(status_surface, status_rect)

        pygame.display.flip()

    def _wrap_edit_text(self, max_width):
        """Word-wrap edit_text and track cursor position through the wrap.

        Returns (lines, cursor_row, cursor_col) where lines is a list of
        strings (without trailing newlines) and cursor_row/col indicate
        the cursor position in the wrapped output.

        Each entry in line_starts tracks the source-text offset where that
        wrapped line begins, so the cursor can be mapped correctly across
        both hard newlines and soft word-wrap breaks.
        """
        lines = []
        line_starts = []
        src_pos = 0  # current position in self.edit_text

        for raw_line in self.edit_text.split('\n'):
            if not raw_line:
                lines.append('')
                line_starts.append(src_pos)
                src_pos += 1  # skip the '\n'
                continue

            # Greedy word-wrap within this paragraph
            words = raw_line.split(' ')
            current = ''
            line_offset = src_pos  # where this wrapped line starts in source

            for i, word in enumerate(words):
                test = (current + ' ' + word) if current else word
                test_width = self.font.size(test)[0]

                if test_width > max_width and current:
                    # Emit the current wrapped line
                    lines.append(current)
                    line_starts.append(line_offset)
                    line_offset += len(current) + 1  # +1 for the space
                    current = word
                else:
                    current = test

            # Emit remaining text in paragraph
            lines.append(current)
            line_starts.append(line_offset)

            src_pos += len(raw_line) + 1  # +1 for '\n'

        # Handle empty text
        if not lines:
            lines = ['']
            line_starts = [0]

        # Find cursor row/col
        cursor_row = 0
        cursor_col = 0
        for row in range(len(lines)):
            start = line_starts[row]
            end = start + len(lines[row])
            if start <= self.edit_cursor <= end:
                cursor_row = row
                cursor_col = self.edit_cursor - start
                break
        else:
            cursor_row = len(lines) - 1
            cursor_col = len(lines[-1])

        return lines, cursor_row, cursor_col, line_starts

    def _draw_editor(self, top_y, content_width, area_height):
        """Draw the inline text editor in the lyrics area."""
        # Reserve space for buttons below the text box
        btn_h = 32
        btn_gap = 10
        btn_area = btn_h + btn_gap * 2
        text_area_height = area_height - btn_area

        # Background for edit area
        edit_rect = pygame.Rect(self.MARGIN - 5, top_y - 5, content_width + 10, text_area_height + 10)
        pygame.draw.rect(self.screen, (30, 30, 30), edit_rect, border_radius=4)
        pygame.draw.rect(self.screen, (80, 80, 80), edit_rect, 1, border_radius=4)

        # Wrap text and find cursor
        wrap_width = content_width - 10  # small padding
        lines, cursor_row, cursor_col, line_starts = self._wrap_edit_text(wrap_width)

        line_h = self.LINE_HEIGHT

        # Cache for hit-testing
        self._edit_lines = lines
        self._edit_line_starts = line_starts
        self._edit_top_y = top_y
        self._edit_line_h = line_h

        # Auto-scroll to keep cursor visible
        cursor_pixel_y = cursor_row * line_h

        if cursor_pixel_y - self.edit_scroll_y < 0:
            self.edit_scroll_y = cursor_pixel_y
        elif cursor_pixel_y - self.edit_scroll_y >= text_area_height - line_h:
            self.edit_scroll_y = cursor_pixel_y - text_area_height + line_h * 2

        self.edit_scroll_y = max(0, self.edit_scroll_y)

        # Clip rendering to the edit area
        clip_rect = pygame.Rect(self.MARGIN, top_y, content_width, text_area_height)
        self.screen.set_clip(clip_rect)

        # Selection range in source text
        sel_start, sel_end = self._get_selection_range() if self._has_selection() else (0, 0)
        has_sel = self._has_selection()

        # Draw lines with selection highlight
        for row, line in enumerate(lines):
            draw_y = top_y + row * line_h - self.edit_scroll_y
            if draw_y + line_h < top_y or draw_y > top_y + text_area_height:
                continue  # off-screen

            # Draw selection highlight for this line
            if has_sel and line_starts[row] < sel_end and line_starts[row] + len(line) >= sel_start:
                ls = line_starts[row]
                # Clamp selection to this line
                local_start = max(0, sel_start - ls)
                local_end = min(len(line), sel_end - ls)
                if local_start < local_end:
                    x1 = self.MARGIN + self.font.size(line[:local_start])[0]
                    x2 = self.MARGIN + self.font.size(line[:local_end])[0]
                    sel_rect = pygame.Rect(x1, draw_y, x2 - x1, line_h - 2)
                    pygame.draw.rect(self.screen, (60, 60, 80), sel_rect)

            if line:
                text_surface = self.font.render(line, True, self.TEXT_COLOR)
                self.screen.blit(text_surface, (self.MARGIN, draw_y))

        # Draw blinking cursor (hide when selection is active)
        blink = (pygame.time.get_ticks() // 500) % 2 == 0
        if blink and not has_sel:
            cursor_line = lines[cursor_row] if cursor_row < len(lines) else ''
            cursor_x = self.MARGIN + self.font.size(cursor_line[:cursor_col])[0]
            cursor_y = top_y + cursor_row * line_h - self.edit_scroll_y
            pygame.draw.line(self.screen, self.CURRENT_COLOR, (cursor_x, cursor_y), (cursor_x, cursor_y + line_h - 4), 2)

        # Remove clip
        self.screen.set_clip(None)

        # Position and draw Save / Cancel buttons below the text box
        btn_y = top_y + text_area_height + btn_gap
        btn_w = 100
        if len(self.edit_buttons) >= 2:
            self.edit_buttons[0].rect = pygame.Rect(self.MARGIN, btn_y, btn_w, btn_h)
            self.edit_buttons[1].rect = pygame.Rect(self.MARGIN + btn_w + btn_gap, btn_y, btn_w, btn_h)
            for btn in self.edit_buttons:
                btn.draw(self.screen, self.button_font)

        # Keyboard hint next to buttons
        mod_key = "Cmd" if IS_MAC else "Ctrl"
        hint_text = f"{mod_key}+Enter = save  |  ESC = cancel"
        hint_surface = self.small_font.render(hint_text, True, self.DIM_COLOR)
        hint_x = self.MARGIN + (btn_w + btn_gap) * 2 + 10
        self.screen.blit(hint_surface, (hint_x, btn_y + 8))

    def _format_time(self, seconds):
        """Format seconds as mm:ss."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    def _update_cursor(self):
        """Set mouse cursor to hand if hovering over any clickable element."""
        mx, my = pygame.mouse.get_pos()
        active_buttons = self.edit_buttons if self.editing else self.buttons
        for btn in active_buttons:
            if btn.rect.collidepoint(mx, my):
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                return
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

    def run(self):
        """Main loop."""
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle_event(event)

                self._update_cursor()
                self.draw()
                self.clock.tick(30)

        finally:
            self.audio.cleanup()
            pygame.quit()


def main():
    # Ensure working directory is writable (app bundles launch inside read-only .app)
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.expanduser('~'))

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
