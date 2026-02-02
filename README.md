# FREE Lyric Video Creator

Create karaoke-style lyric videos. Actually free.

No ads. No subscriptions. No AI. No bullshit.

## Download

Get the latest release: [Releases](https://github.com/thethundergods/free-lyric-video-creator/releases)

## Features

- Load any audio file (MP3, WAV, OGG, FLAC, M4A)
- Type or paste lyrics
- Tap spacebar to time each word as it plays
- Export to video (480p, 720p, 1080p)

## How to Use

1. Load an audio file
2. Paste or type your lyrics
3. Play the audio and tap SPACE on each word as it's sung
4. Export your video

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| SPACE | Mark current word |
| DELETE | Unmark last word |
| P | Play/Pause |
| S | Stop |
| LEFT/RIGHT | Seek 5 seconds |
| L | Load audio |
| T | Load lyrics file |
| V | Paste lyrics |
| E | Export video |

## Run from Source

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## License

MIT License - see [LICENSE](LICENSE)

## Why This Exists

I paid for a "lifetime license" for another lyric video app. Then they decided "lifetime" meant "yearly."

So I made my own.

---

Made with spite and [pygame](https://www.pygame.org/)
