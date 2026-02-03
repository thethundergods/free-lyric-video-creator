"""Video renderer for karaoke-style lyrics video with word-by-word highlighting."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from moviepy import VideoClip, AudioFileClip, VideoFileClip

from lyrics_timer import LyricsTimer
from utils import resource_path

# Default background video (looping)
DEFAULT_BG_VIDEO = "Red to Blue Squares - HD Video Background Loop [pVNbWKa6qbg].mp4"


# Resolution presets (width, height)
RESOLUTIONS = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}


class VideoRenderer:
    # Colors
    BG_COLOR = (18, 18, 18)  # Fallback dark background
    TEXT_COLOR = (255, 255, 255)  # White for unhighlighted text
    HIGHLIGHT_COLOR = (255, 200, 50)  # Yellow/gold for highlighted words
    SHADOW_COLOR = (0, 0, 0, 180)  # Semi-transparent black shadow

    # Video settings (base values for 1080p, scaled for other resolutions)
    FPS = 30

    # Loading bar settings
    GAP_THRESHOLD = 5.0  # Show bar if gap > 5 seconds

    # Timing adjustment
    HIGHLIGHT_OFFSET = 0.5  # Highlight 500ms ahead of actual timing

    def __init__(self, lyrics_timer: LyricsTimer, audio_path: str, resolution: str = "1080p"):
        self.lyrics = lyrics_timer
        self.audio_path = audio_path

        # Set resolution-dependent values
        self.WIDTH, self.HEIGHT = RESOLUTIONS.get(resolution, RESOLUTIONS["1080p"])
        scale = self.HEIGHT / 1080  # Scale factor based on 1080p as base

        # Scaled settings
        self.FONT_SIZE = int(72 * scale)
        self.LINE_SPACING = int(120 * scale)
        self.SHADOW_OFFSET = max(2, int(4 * scale))
        self.SHADOW_BLUR = max(2, int(3 * scale))
        self.BAR_HEIGHT = max(10, int(20 * scale))
        self.BAR_Y = int(40 * scale)
        self.HORIZONTAL_PADDING = int(100 * scale)  # Padding on each side

        self.font = self._get_font()

        # Build line data for scrolling calculations
        self._build_line_data()

        # Calculate timing info
        self._calculate_timing_info()

        # Load background video if available
        bg_path = resource_path(DEFAULT_BG_VIDEO)
        if os.path.exists(bg_path):
            self.bg_clip = VideoFileClip(bg_path)
            self.bg_duration = self.bg_clip.duration
        else:
            self.bg_clip = None
            self.bg_duration = 0

    def _build_line_data(self):
        """Build line data with timing info for smooth scrolling, wrapping long lines."""
        self.lines = []
        current_line_words = []
        max_width = self.WIDTH - (2 * self.HORIZONTAL_PADDING)
        prev_was_newline = False

        def get_line_width(words):
            """Calculate the width of a line of words."""
            if not words:
                return 0
            line_text = ' '.join(w.word for w in words)
            bbox = self.font.getbbox(line_text)
            return bbox[2] - bbox[0] if bbox else 0

        for word in self.lyrics.words:
            if word.word == '\n':
                if current_line_words:
                    self.lines.append(current_line_words)
                    current_line_words = []
                elif prev_was_newline:
                    # Consecutive newline = blank line (verse break)
                    self.lines.append([])  # Empty line for spacing
                prev_was_newline = True
            else:
                prev_was_newline = False
                # Check if adding this word would exceed max width
                test_words = current_line_words + [word]
                if get_line_width(test_words) > max_width and current_line_words:
                    # Line would be too long, wrap to new line
                    self.lines.append(current_line_words)
                    current_line_words = [word]
                else:
                    current_line_words.append(word)

        # Don't forget last line
        if current_line_words:
            self.lines.append(current_line_words)

    def _calculate_timing_info(self):
        """Calculate first word time, gaps, etc."""
        self.first_word_time = None
        self.last_word_time = None
        self.gaps = []  # List of (start_time, end_time) for gaps > threshold

        # Find first and last timed words
        timed_words = [(w.start_time, w.index) for w in self.lyrics.words
                       if w.word != '\n' and w.start_time is not None]
        timed_words.sort()

        if timed_words:
            self.first_word_time = timed_words[0][0]
            self.last_word_time = timed_words[-1][0]

            # Find gaps
            for i in range(1, len(timed_words)):
                prev_time = timed_words[i-1][0]
                curr_time = timed_words[i][0]
                if curr_time - prev_time > self.GAP_THRESHOLD:
                    self.gaps.append((prev_time, curr_time))

    def _get_font(self) -> ImageFont.FreeTypeFont:
        """Get a bold sans-serif font."""
        font_options = [
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", None),
            ("/System/Library/Fonts/Helvetica.ttc", 1),
            ("/Library/Fonts/Arial Bold.ttf", None),
            ("/System/Library/Fonts/Avenir Next.ttc", 10),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", None),
            ("C:/Windows/Fonts/arialbd.ttf", None),
        ]

        for path, index in font_options:
            if os.path.exists(path):
                try:
                    if index is not None:
                        return ImageFont.truetype(path, self.FONT_SIZE, index=index)
                    else:
                        return ImageFont.truetype(path, self.FONT_SIZE)
                except (OSError, Exception):
                    continue

        try:
            return ImageFont.truetype("Arial Bold", self.FONT_SIZE)
        except:
            return ImageFont.load_default()

    def _get_line_timing(self, line_words):
        """Get start and end time for a line based on its words."""
        start_time = None
        end_time = None

        for word in line_words:
            if word.start_time is not None:
                if start_time is None:
                    start_time = word.start_time
                end_time = word.start_time

        return start_time, end_time

    def _calculate_scroll_offset(self, time: float) -> float:
        """Calculate vertical scroll offset for smooth continuous scrolling."""
        if not self.lines or self.first_word_time is None:
            return 0

        # Calculate total content height
        total_lines = len(self.lines)
        total_height = total_lines * self.LINE_SPACING

        # Intro phase: scroll from bottom to center
        if time < self.first_word_time:
            # Start with lines off-screen at bottom
            # At t=0, offset should be negative (lines below screen)
            # At t=first_word_time, first line should be at center
            intro_duration = self.first_word_time
            if intro_duration > 0:
                progress = time / intro_duration
                # Start offset: lines are below screen (negative offset pushes them down)
                start_offset = -self.HEIGHT  # Lines start below screen
                end_offset = 0  # First line at center
                return start_offset + (end_offset - start_offset) * progress
            return 0

        # Main phase: scroll based on current position in lyrics
        # Find current line and calculate smooth scroll
        current_line_idx = 0
        line_progress = 0.0

        for i, line_words in enumerate(self.lines):
            start_time, end_time = self._get_line_timing(line_words)
            if start_time is None:
                continue

            if time >= start_time:
                current_line_idx = i
                # Get next line's start time for smooth transition
                next_start = None
                for j in range(i + 1, len(self.lines)):
                    next_start_time, _ = self._get_line_timing(self.lines[j])
                    if next_start_time is not None:
                        next_start = next_start_time
                        break

                if next_start and next_start > start_time:
                    line_progress = min(1.0, (time - start_time) / (next_start - start_time))
                elif end_time and end_time > start_time:
                    # Last line or gap - use word timings
                    line_progress = min(1.0, (time - start_time) / max(1.0, end_time - start_time + 1.0))
                else:
                    line_progress = 0.5

        # Calculate smooth scroll offset
        base_offset = current_line_idx * self.LINE_SPACING
        within_line_offset = line_progress * self.LINE_SPACING

        return base_offset + within_line_offset

    def _get_loading_bar_progress(self, time: float, duration: float) -> float:
        """Get loading bar progress (0-1) or -1 if no bar should be shown."""
        if self.first_word_time is None:
            return -1

        # Only show bar during intro
        if time < self.first_word_time:
            if self.first_word_time > 0:
                return time / self.first_word_time
            return -1

        return -1

    def _draw_loading_bar(self, draw, time: float, duration: float):
        """Draw the loading bar if needed."""
        progress = self._get_loading_bar_progress(time, duration)
        if progress < 0:
            return

        # Draw bar background (subtle)
        bar_width = self.WIDTH - 200
        bar_x = 100
        draw.rectangle(
            [bar_x, self.BAR_Y, bar_x + bar_width, self.BAR_Y + self.BAR_HEIGHT],
            fill=(255, 255, 255, 50)
        )

        # Draw progress
        fill_width = int(bar_width * progress)
        if fill_width > 0:
            draw.rectangle(
                [bar_x, self.BAR_Y, bar_x + fill_width, self.BAR_Y + self.BAR_HEIGHT],
                fill=self.HIGHLIGHT_COLOR
            )

    def _draw_text_with_shadow(self, img, draw, x, y, text, color, opacity=1.0):
        """Draw text with a shadow effect."""
        # Draw shadow directly (simpler, faster)
        shadow_alpha = int(150 * opacity)
        shadow_color = (0, 0, 0, shadow_alpha)
        for ox, oy in [(2, 2), (3, 3), (4, 4)]:
            draw.text((x + ox, y + oy), text, font=self.font, fill=shadow_color)

        # Draw main text with opacity
        if opacity < 1.0:
            alpha = int(255 * opacity)
            if len(color) == 3:
                color = color + (alpha,)
            else:
                color = color[:3] + (alpha,)

        draw.text((x, y), text, font=self.font, fill=color)

    def _get_current_line_info(self, time: float):
        """Get current line index and progress through that line."""
        current_line_idx = -1
        line_progress = 0.0

        for i, line_words in enumerate(self.lines):
            start_time, end_time = self._get_line_timing(line_words)
            if start_time is None:
                continue

            if time >= start_time:
                current_line_idx = i
                # Get next line's start time for progress
                next_start = None
                for j in range(i + 1, len(self.lines)):
                    next_start_time, _ = self._get_line_timing(self.lines[j])
                    if next_start_time is not None:
                        next_start = next_start_time
                        break

                if next_start and next_start > start_time:
                    line_progress = min(1.0, (time - start_time) / (next_start - start_time))
                elif end_time and end_time > start_time:
                    line_progress = min(1.0, (time - start_time) / max(1.0, end_time - start_time + 1.0))
                else:
                    line_progress = 0.5

        return current_line_idx, line_progress

    def _get_line_opacity(self, line_idx: int, current_line_idx: int, line_progress: float, y_position: float) -> float:
        """Calculate opacity for a line based on current line, progress, and screen position."""
        # Fade zone at top of screen
        FADE_ZONE_TOP = 150  # Start fading 150px from top

        # Position-based fade (for lines going off top)
        position_opacity = 1.0
        if y_position < FADE_ZONE_TOP:
            if y_position < 0:
                position_opacity = 0.0
            else:
                position_opacity = y_position / FADE_ZONE_TOP

        if current_line_idx < 0:
            return position_opacity

        # How many lines above the current line is this?
        lines_above = current_line_idx - line_idx

        # Line-based fade
        if lines_above < 2:
            # Current line, one above, or below - full opacity (unless position fade)
            line_opacity = 1.0
        elif lines_above == 2:
            # Two lines above - fade out as current line progresses
            line_opacity = 1.0 - line_progress
        else:
            # More than 2 lines above - already faded
            line_opacity = 0.0

        # Return minimum of both fades
        return min(position_opacity, line_opacity)

    def _render_frame(self, time: float) -> np.ndarray:
        """Render a single frame at the given time."""
        # Use background video frame or solid color
        if self.bg_clip:
            bg_time = time % self.bg_duration
            bg_frame = self.bg_clip.get_frame(bg_time)
            img = Image.fromarray(bg_frame).convert('RGBA')
            # Resize background to match output resolution
            if img.size != (self.WIDTH, self.HEIGHT):
                img = img.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
        else:
            img = Image.new('RGBA', (self.WIDTH, self.HEIGHT), self.BG_COLOR + (255,))

        draw = ImageDraw.Draw(img)

        # Draw loading bar
        self._draw_loading_bar(draw, time, self.bg_duration)

        if not self.lines:
            return np.array(img.convert('RGB'))

        # Get current line info for fade calculations
        current_line_idx, line_progress = self._get_current_line_info(time)

        # Calculate scroll offset
        scroll_offset = self._calculate_scroll_offset(time)

        # Center Y position
        center_y = self.HEIGHT // 2

        # Draw each line
        for line_idx, line_words in enumerate(self.lines):
            # Calculate Y position with scrolling
            base_y = center_y + (line_idx * self.LINE_SPACING) - scroll_offset

            # Skip if completely off screen
            if base_y < -self.FONT_SIZE * 2 or base_y > self.HEIGHT + self.FONT_SIZE:
                continue

            # Calculate opacity for this line (based on position and line index)
            opacity = self._get_line_opacity(line_idx, current_line_idx, line_progress, base_y)

            # Skip fully faded lines
            if opacity <= 0:
                continue

            # Calculate line width for centering
            line_text = ' '.join(w.word for w in line_words)
            bbox = self.font.getbbox(line_text)
            line_width = bbox[2] - bbox[0] if bbox else 0

            # Center horizontally
            start_x = (self.WIDTH - line_width) // 2
            x = start_x

            # Draw each word
            for word in line_words:
                word_text = word.word

                # Word is highlighted if its time has passed (stays highlighted)
                # Add offset so highlight appears slightly ahead of audio
                adjusted_time = time + self.HIGHLIGHT_OFFSET
                is_highlighted = (word.start_time is not None and word.start_time <= adjusted_time)

                # Choose color with opacity
                if is_highlighted:
                    base_color = self.HIGHLIGHT_COLOR
                else:
                    base_color = self.TEXT_COLOR

                # Apply opacity
                if opacity < 1.0:
                    alpha = int(255 * opacity)
                    color = base_color[:3] + (alpha,) if len(base_color) == 3 else base_color[:3] + (alpha,)
                else:
                    color = base_color

                # Draw word with shadow
                self._draw_text_with_shadow(img, draw, x, base_y, word_text, color, opacity)

                # Move x position for next word
                word_bbox = self.font.getbbox(word_text + ' ')
                x += word_bbox[2] - word_bbox[0] if word_bbox else 0

        return np.array(img.convert('RGB'))

    def render(self, output_path: str, progress_callback=None):
        """Render the full video to the output path."""
        audio = AudioFileClip(self.audio_path)
        duration = audio.duration

        def make_frame(t):
            frame = self._render_frame(t)
            if progress_callback:
                progress_callback(t / duration)
            return frame

        video = VideoClip(make_frame, duration=duration)
        video = video.with_audio(audio)

        video.write_videofile(
            output_path,
            fps=self.FPS,
            codec='libx264',
            audio_codec='aac',
            threads=4,
            preset='medium',
            logger=None
        )

        audio.close()
        video.close()
        if self.bg_clip:
            self.bg_clip.close()

        return output_path


def render_preview_frame(lyrics_timer: LyricsTimer, time: float, width: int = 800, height: int = 450) -> Image.Image:
    """Render a single preview frame (smaller resolution for UI)."""
    renderer = VideoRenderer.__new__(VideoRenderer)
    renderer.lyrics = lyrics_timer
    renderer.WIDTH = width
    renderer.HEIGHT = height
    renderer.FONT_SIZE = 36
    renderer.LINE_SPACING = 60
    renderer.SHADOW_OFFSET = 2
    renderer.SHADOW_BLUR = 2
    renderer.BAR_HEIGHT = 10
    renderer.BAR_Y = 20
    renderer.GAP_THRESHOLD = 5.0
    renderer.HIGHLIGHT_OFFSET = 0.5
    renderer.HORIZONTAL_PADDING = 50  # Scaled for preview
    renderer.BG_COLOR = VideoRenderer.BG_COLOR
    renderer.TEXT_COLOR = VideoRenderer.TEXT_COLOR
    renderer.HIGHLIGHT_COLOR = VideoRenderer.HIGHLIGHT_COLOR
    renderer.SHADOW_COLOR = VideoRenderer.SHADOW_COLOR
    renderer.font = renderer._get_font()
    renderer.bg_clip = None
    renderer.bg_duration = 0
    renderer._build_line_data()
    renderer._calculate_timing_info()

    frame_array = renderer._render_frame(time)
    return Image.fromarray(frame_array)
