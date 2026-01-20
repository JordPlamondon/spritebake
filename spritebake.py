#!/usr/bin/env python3
"""
spritebake - Convert Blender animations to sprite sheets.

Usage:
    spritebake model.blend -o sprite.png
    spritebake model.blend -o sprite.png --frames 16 --remove-bg
"""

import argparse
import subprocess
import tempfile
import shutil
import sys
import math
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Error: Pillow and numpy required. Install with: pip install Pillow numpy")
    sys.exit(1)


def find_blender():
    """Find Blender executable."""
    locations = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "blender",
    ]
    for loc in locations:
        if Path(loc).exists() or shutil.which(loc):
            return loc
    return None


def render_frames(blender_path, blend_file, output_dir, frames, size, start, end,
                  neutralize_bg=True):
    """Run Blender to render animation frames."""
    script_dir = Path(__file__).parent
    render_script = script_dir / "render_frames.py"

    cmd = [
        blender_path, "-b", str(blend_file), "-P", str(render_script), "--",
        "--output", str(output_dir),
        "--frames", str(frames),
        "--size", str(size),
    ]

    if start is not None:
        cmd.extend(["--start", str(start)])
    if end is not None:
        cmd.extend(["--end", str(end)])
    if not neutralize_bg:
        cmd.append("--no-neutralize-bg")

    print("Running Blender...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Blender error:\n{result.stderr}")
        return False

    for line in result.stdout.split('\n'):
        if line.strip() and not line.startswith('Fra:') and not line.startswith('Saved:'):
            print(line)

    return True


def is_empty_frame(img, threshold=0.001):
    """Check if frame is empty (solid color or fully transparent)."""
    arr = np.array(img.convert('RGBA'))
    total = arr.shape[0] * arr.shape[1]
    alpha = arr[:, :, 3]

    opaque = np.sum(alpha > 128) / total
    transparent = np.sum(alpha < 10) / total

    # Silhouette on transparent bg = not empty
    if opaque > threshold and transparent > 0.5:
        return False

    if opaque < threshold:
        return True

    # Check RGB variance for solid color frames
    rgb = arr[:, :, :3]
    bg = rgb[0, 0]
    diff = np.abs(rgb.astype(int) - bg.astype(int))
    diff_ratio = np.sum(np.any(diff > 20, axis=2)) / total

    return diff_ratio < threshold


def is_mostly_transparent(img, threshold=0.80):
    """Check if image is mostly transparent."""
    arr = np.array(img.convert('RGBA'))
    alpha = arr[:, :, 3]
    transparent = np.sum(alpha < 10)
    total = arr.shape[0] * arr.shape[1]
    return transparent / total > threshold


def needs_background_removal(img):
    """Check if image needs background removal.

    Returns True if the image has a solid/opaque background.
    Returns False if the image already has good transparency.

    Strategy: Check ALL four corners AND overall transparency.
    Only skip if corners are ALL transparent.
    """
    arr = np.array(img.convert('RGBA'))
    alpha = arr[:, :, 3]
    h, w = alpha.shape

    # Check each corner individually (3x3 areas)
    cs = 3  # corner sample size
    corner_regions = [
        alpha[:cs, :cs],           # top-left
        alpha[:cs, -cs:],          # top-right
        alpha[-cs:, :cs],          # bottom-left
        alpha[-cs:, -cs:]          # bottom-right
    ]

    # ALL four corners must be fully transparent to skip
    for corner in corner_regions:
        if np.mean(corner) > 10:  # If any corner has opacity > 10
            return True  # Needs background removal

    # Double-check: overall image should be >40% transparent
    total_transparent = np.sum(alpha < 10) / (h * w)
    if total_transparent < 0.4:
        return True  # Not enough transparency, needs removal

    return False  # All corners transparent + good overall transparency


def stitch_spritesheet(frames_dir, output_path, cols=None, remove_bg=False, target_size=None):
    """Combine frames into a sprite sheet."""
    frames_dir = Path(frames_dir)
    frame_files = sorted(frames_dir.glob("frame_*.png"))

    if not frame_files:
        print("Error: No frames found")
        return False

    images = [Image.open(f) for f in frame_files]

    # Downscale if target_size specified and frames are larger
    if target_size and images[0].width > target_size:
        print(f"  Downscaling {len(images)} frames from {images[0].width}x{images[0].height} to {target_size}x{target_size}")
        images = [img.resize((target_size, target_size), Image.LANCZOS) for img in images]

    if remove_bg:
        try:
            from rembg import remove, new_session

            # Auto-detect which frames need background removal
            frames_needing_removal = []
            frames_empty = []
            for i, img in enumerate(images):
                if is_empty_frame(img):
                    frames_empty.append(i)
                elif needs_background_removal(img):
                    frames_needing_removal.append(i)

            # Replace empty frames with transparent
            for i in frames_empty:
                images[i] = Image.new('RGBA', images[i].size, (0, 0, 0, 0))

            if frames_empty:
                print(f"  {len(frames_empty)} empty frames replaced with transparent")

            if frames_needing_removal:
                print(f"Removing backgrounds ({len(frames_needing_removal)}/{len(images)} frames need processing)...")
                session = new_session()

                def process_frame(args):
                    idx, img = args
                    return idx, remove(img, session=session)

                num_workers = min(len(frames_needing_removal), os.cpu_count() or 4)

                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    futures = {executor.submit(process_frame, (i, images[i])): i
                               for i in frames_needing_removal}
                    done = 0
                    for future in as_completed(futures):
                        idx, result = future.result()
                        images[idx] = result
                        done += 1
                        print(f"\r  Processing: {done}/{len(frames_needing_removal)}", end="", flush=True)
                    print()
            else:
                print("Backgrounds already transparent, skipping rembg")

        except ImportError:
            print("Warning: rembg not installed. pip install 'rembg[cpu]'")

    w, h = images[0].width, images[0].height
    n = len(images)

    if cols is None:
        cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    sheet = Image.new('RGBA', (cols * w, rows * h), (0, 0, 0, 0))

    for i, img in enumerate(images):
        x = (i % cols) * w
        y = (i // cols) * h
        sheet.paste(img, (x, y), img)

    sheet.save(output_path, 'PNG')
    print(f"Saved: {output_path} ({cols * w}x{rows * h})")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert Blender animations to sprite sheets",
        epilog="Example: %(prog)s model.blend -o sprite.png --frames 16 --remove-bg"
    )

    parser.add_argument("input", help="Input .blend file")
    parser.add_argument("-o", "--output", required=True, help="Output PNG path")
    parser.add_argument("--frames", type=int, default=8, help="Number of frames (default: 8)")
    parser.add_argument("--size", type=int, default=128, help="Frame size in px (default: 128)")
    parser.add_argument("--cols", type=int, help="Grid columns (default: auto)")
    parser.add_argument("--frame-start", type=int, help="Start frame (default: scene start)")
    parser.add_argument("--frame-end", type=int, help="End frame (default: scene end)")
    parser.add_argument("--keep-frames", action="store_true", help="Save individual frames to {output}_frames/")
    parser.add_argument("--remove-bg", action="store_true", help="Remove background with AI (requires rembg)")
    parser.add_argument("--no-bg-neutralize", action="store_true", help="Keep original background colors")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    blender = find_blender()
    if not blender:
        print("Error: Blender not found")
        sys.exit(1)

    print(f"Using Blender: {blender}")

    with tempfile.TemporaryDirectory() as temp_dir:
        frames_dir = Path(temp_dir) / "frames"
        frames_dir.mkdir()

        if not render_frames(blender, input_path, frames_dir, args.frames, args.size,
                            args.frame_start, args.frame_end,
                            neutralize_bg=not args.no_bg_neutralize):
            sys.exit(1)

        if not stitch_spritesheet(frames_dir, args.output, args.cols, args.remove_bg, target_size=args.size):
            sys.exit(1)

        if args.keep_frames:
            keep_dir = Path(args.output).parent / f"{Path(args.output).stem}_frames"
            shutil.copytree(frames_dir, keep_dir)
            print(f"Frames saved to: {keep_dir}")

    print("Done!")


if __name__ == "__main__":
    main()
