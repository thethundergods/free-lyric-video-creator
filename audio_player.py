"""Audio player module using pygame mixer."""
import pygame


class AudioPlayer:
    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.file_path = None
        self.duration = 0
        self._paused = False
        self._start_offset = 0
        self._pause_pos = 0

    def load(self, file_path: str) -> bool:
        """Load an audio file. Returns True on success."""
        try:
            pygame.mixer.music.load(file_path)
            self.file_path = file_path
            # Get duration using Sound object (temporary load)
            sound = pygame.mixer.Sound(file_path)
            self.duration = sound.get_length()
            sound.stop()
            del sound
            self._start_offset = 0
            self._pause_pos = 0
            self._paused = False
            return True
        except Exception as e:
            print(f"Error loading audio: {e}")
            return False

    def play(self, start_pos: float = 0):
        """Start playback from position (in seconds)."""
        if self.file_path:
            self._start_offset = start_pos
            pygame.mixer.music.play(start=start_pos)
            self._paused = False

    def pause(self):
        """Pause playback."""
        if pygame.mixer.music.get_busy():
            self._pause_pos = self.get_position()
            pygame.mixer.music.pause()
            self._paused = True

    def unpause(self):
        """Resume playback."""
        if self._paused:
            pygame.mixer.music.unpause()
            self._paused = False

    def toggle_pause(self):
        """Toggle between play and pause."""
        if self._paused:
            self.unpause()
        elif pygame.mixer.music.get_busy():
            self.pause()
        else:
            # Not playing, start from pause position or beginning
            self.play(self._pause_pos if self._pause_pos > 0 else 0)

    def stop(self):
        """Stop playback."""
        pygame.mixer.music.stop()
        self._paused = False
        self._pause_pos = 0

    def get_position(self) -> float:
        """Get current playback position in seconds."""
        if self._paused:
            return self._pause_pos
        if pygame.mixer.music.get_busy():
            # pygame returns position in milliseconds from start of play call
            return self._start_offset + (pygame.mixer.music.get_pos() / 1000.0)
        return self._pause_pos

    def set_position(self, pos: float):
        """Seek to position (in seconds)."""
        was_playing = pygame.mixer.music.get_busy() or self._paused
        self.stop()
        if was_playing:
            self.play(pos)
        else:
            self._pause_pos = pos

    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return pygame.mixer.music.get_busy() and not self._paused

    def is_paused(self) -> bool:
        """Check if audio is paused."""
        return self._paused

    def cleanup(self):
        """Clean up resources."""
        pygame.mixer.music.stop()
        pygame.mixer.quit()
