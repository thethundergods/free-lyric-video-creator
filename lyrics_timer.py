"""Lyrics timing data model and management."""
import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimedWord:
    """A word with its timing information."""
    word: str
    start_time: Optional[float] = None  # None means not yet timed
    index: int = 0  # Position in the word list


@dataclass
class TimedLine:
    """A line of lyrics with timing information."""
    text: str
    start_time: Optional[float] = None
    index: int = 0


@dataclass
class LyricsTimer:
    """Manages lyrics and their timing data."""
    words: list[TimedWord] = field(default_factory=list)
    current_index: int = 0  # Next word to be timed

    def load_lyrics(self, text: str):
        """Parse lyrics text into words."""
        # Split on whitespace, preserving line structure for display
        self.words = []
        self.current_index = 0

        # Split into words, keeping track of line breaks
        lines = text.split('\n')
        word_index = 0

        for line in lines:
            line_words = re.findall(r'\S+', line)
            if line_words:
                # Line has words
                for word in line_words:
                    self.words.append(TimedWord(word=word, index=word_index))
                    word_index += 1
                # Add line break after words
                self.words.append(TimedWord(word='\n', index=word_index))
                word_index += 1
            else:
                # Empty line (verse break) - add blank line marker
                self.words.append(TimedWord(word='\n', index=word_index))
                word_index += 1

        # Remove trailing line breaks
        while self.words and self.words[-1].word == '\n':
            self.words.pop()

    def get_lines(self) -> list[list[TimedWord]]:
        """Get words organized by lines for display."""
        lines = []
        current_line = []

        for word in self.words:
            if word.word == '\n':
                if current_line:
                    lines.append(current_line)
                    current_line = []
            else:
                current_line.append(word)

        if current_line:
            lines.append(current_line)

        return lines

    def mark_word(self, timestamp: float) -> bool:
        """Mark the next untimed word with the given timestamp. Returns True if successful."""
        # Find the next untimed word
        for i, word in enumerate(self.words):
            if word.word != '\n' and word.start_time is None:
                word.start_time = timestamp
                self.current_index = i + 1
                return True
        return False

    def unmark_last(self) -> bool:
        """Remove timing from the last timed word. Returns True if successful."""
        # Find the last timed word
        for i in range(len(self.words) - 1, -1, -1):
            if self.words[i].word != '\n' and self.words[i].start_time is not None:
                self.words[i].start_time = None
                self.current_index = i
                return True
        return False

    def get_next_untimed_index(self) -> int:
        """Get the index of the next word to be timed."""
        for i, word in enumerate(self.words):
            if word.word != '\n' and word.start_time is None:
                return i
        return len(self.words)

    def get_timed_count(self) -> int:
        """Get the number of timed words."""
        return sum(1 for w in self.words if w.word != '\n' and w.start_time is not None)

    def get_total_words(self) -> int:
        """Get total number of words (excluding line breaks)."""
        return sum(1 for w in self.words if w.word != '\n')

    def is_complete(self) -> bool:
        """Check if all words have been timed."""
        return self.get_timed_count() == self.get_total_words()

    def get_word_at_time(self, time: float) -> tuple[Optional[TimedWord], float]:
        """
        Get the word being sung at the given time.
        Returns (word, progress) where progress is 0-1 for fill animation.
        """
        current_word = None
        next_time = None

        # Find the current word (last word with start_time <= time)
        for i, word in enumerate(self.words):
            if word.word == '\n' or word.start_time is None:
                continue
            if word.start_time <= time:
                current_word = word
                # Find next timed word for progress calculation
                for j in range(i + 1, len(self.words)):
                    if self.words[j].word != '\n' and self.words[j].start_time is not None:
                        next_time = self.words[j].start_time
                        break
            else:
                break

        if current_word is None:
            return None, 0.0

        # Calculate progress within the word
        if next_time is not None:
            word_duration = next_time - current_word.start_time
            if word_duration > 0:
                progress = min(1.0, (time - current_word.start_time) / word_duration)
            else:
                progress = 1.0
        else:
            # Last word - assume 1 second duration
            progress = min(1.0, (time - current_word.start_time) / 1.0)

        return current_word, progress

    def save(self, file_path: str):
        """Save timing data to JSON file."""
        data = {
            'words': [
                {'word': w.word, 'start_time': w.start_time, 'index': w.index}
                for w in self.words
            ]
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, file_path: str) -> bool:
        """Load timing data from JSON file. Returns True on success."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.words = [
                TimedWord(word=w['word'], start_time=w['start_time'], index=w['index'])
                for w in data['words']
            ]
            self.current_index = self.get_next_untimed_index()
            return True
        except Exception as e:
            print(f"Error loading timing data: {e}")
            return False

    def get_lyrics_text(self) -> str:
        """Reconstruct the lyrics text from words."""
        result = []
        prev_was_newline = False
        for word in self.words:
            if word.word == '\n':
                # Remove trailing space before newline
                if result and result[-1].endswith(' '):
                    result[-1] = result[-1].rstrip()
                result.append('\n')
                prev_was_newline = True
            else:
                result.append(word.word + ' ')
                prev_was_newline = False
        return ''.join(result).strip()

    def get_visible_lines(self) -> list[TimedLine]:
        """Get lyrics as lines for video rendering."""
        lines = []
        current_line_words = []
        line_index = 0

        for word in self.words:
            if word.word == '\n':
                if current_line_words:
                    # Create line from accumulated words
                    text = ' '.join(w.word for w in current_line_words)
                    start_time = current_line_words[0].start_time
                    lines.append(TimedLine(text=text, start_time=start_time, index=line_index))
                    line_index += 1
                    current_line_words = []
            else:
                current_line_words.append(word)

        # Don't forget the last line
        if current_line_words:
            text = ' '.join(w.word for w in current_line_words)
            start_time = current_line_words[0].start_time
            lines.append(TimedLine(text=text, start_time=start_time, index=line_index))

        return lines

    def get_line_at_time(self, time: float) -> tuple[Optional[TimedLine], int]:
        """Get the line being sung at the given time."""
        lines = self.get_visible_lines()
        current_line = None
        current_idx = -1

        for i, line in enumerate(lines):
            if line.start_time is not None and line.start_time <= time:
                current_line = line
                current_idx = i

        return current_line, current_idx
