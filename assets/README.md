# Local assets

These directories are **not versioned** (except this README and `.gitkeep` files).
Add your own files before running the pipeline.

## Layout

```
assets/
├── lyrics/              # Input lyrics (.txt)
├── references/<name>/   # Vocal reference clips (.wav) for voice conversion
├── voices/<name>/       # Trained RVC models (model.pth, model.index) — create locally
├── avatars/<variant>/   # avatar.png and/or avatar.mp4 for lip-sync — create locally
├── avatar.png           # Default avatar (fallback)
└── avatar.mp4           # Default avatar video (fallback)
```

Variant scripts create `voices/` and `avatars/` subfolders automatically (`mkdir -p`); those folders have no versioned placeholders.

## What goes where

| Folder | Format | Purpose |
|--------|--------|---------|
| `lyrics/` | `.txt` | Lyrics for `00_generate_lyrics.py` or variants |
| `references/<tag>/` | `.wav` | Vocal samples for RVC / Seed-VC |
| `voices/<tag>/` | `.pth`, `.index` | Pre-trained RVC model |
| `avatars/<tag>/` | `.png`, `.mp4` | Virtual character for lip-sync |

## Legal notice

Only use voices, lyrics, and images you have the right to use (your own, licensed, or fully synthetic).
Do not distribute real artist clips, copyrighted lyrics, or voice models trained on third-party voices without authorization.
