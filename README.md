# spritebake

Convert Blender animations to sprite sheets.

## Install

```bash
pip install -r requirements.txt
```

Requires [Blender](https://www.blender.org/download/) 4.x installed.

## Usage

```bash
# Basic
python3 spritebake.py model.blend -o sprite.png

# With transparent background (AI-powered)
python3 spritebake.py model.blend -o sprite.png --remove-bg

# More options
python3 spritebake.py model.blend -o sprite.png --frames 16 --size 256 --remove-bg
```

## Options

| Flag | Description |
|------|-------------|
| `-o, --output` | Output PNG path (required) |
| `--frames N` | Number of frames (default: 8) |
| `--size N` | Frame size in pixels (default: 128) |
| `--cols N` | Grid columns (default: auto) |
| `--remove-bg` | Remove background with AI |
| `--keep-frames` | Save individual frames |
| `--frame-start N` | Start frame |
| `--frame-end N` | End frame |

## Examples

```bash
# 16-frame sprite sheet at 256px
python3 spritebake.py character.blend -o character.png --frames 16 --size 256

# 4-column grid with transparent background
python3 spritebake.py walk.blend -o walk.png --frames 8 --cols 4 --remove-bg

# Keep individual frames for inspection
python3 spritebake.py model.blend -o output.png --keep-frames
```

## How it works

1. Renders evenly-spaced frames from your animation using Blender
2. Optionally removes backgrounds using [rembg](https://github.com/danielgatis/rembg) AI
3. Stitches frames into a grid sprite sheet

## License

MIT
