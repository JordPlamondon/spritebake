"""
Blender render script for spritebake.
Called internally - renders animation frames to PNG files.
"""

import bpy
import sys
import os


def get_args():
    """Parse CLI arguments after '--' separator."""
    argv = sys.argv
    if "--" not in argv:
        return {"output": "/tmp/frames", "frames": 8, "size": 128,
                "start": None, "end": None, "neutralize_bg": True}

    argv = argv[argv.index("--") + 1:]
    args = {"output": "/tmp/frames", "frames": 8, "size": 128,
            "start": None, "end": None, "neutralize_bg": True}

    i = 0
    while i < len(argv):
        if argv[i] == "--output" and i + 1 < len(argv):
            args["output"] = argv[i + 1]
            i += 2
        elif argv[i] == "--frames" and i + 1 < len(argv):
            args["frames"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--size" and i + 1 < len(argv):
            args["size"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--start" and i + 1 < len(argv):
            args["start"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--end" and i + 1 < len(argv):
            args["end"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--no-neutralize-bg":
            args["neutralize_bg"] = False
            i += 1
        else:
            i += 1

    return args


def setup_render(size, neutralize_bg=True):
    """Configure Blender render settings for sprite output."""
    scene = bpy.context.scene

    # Use Eevee for speed
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'

    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    if scene.world:
        scene.world.use_nodes = False
        scene.world.color = (0, 0, 0)

    # Neutralize background materials to prevent color bleed
    if neutralize_bg:
        bg_keywords = ['floor', 'ground', 'background', 'plane', 'bg']
        for mat in bpy.data.materials:
            if any(kw in mat.name.lower() for kw in bg_keywords):
                mat.use_nodes = False
                mat.diffuse_color = (0, 0, 0, 0)
                mat.blend_method = 'BLEND'


def main():
    args = get_args()
    scene = bpy.context.scene

    frame_start = args["start"] if args["start"] is not None else scene.frame_start
    frame_end = args["end"] if args["end"] is not None else scene.frame_end
    num_frames = args["frames"]

    print("spritebake render script")
    print(f"  Output: {args['output']}")
    print(f"  Frame range: {frame_start}-{frame_end}")
    print(f"  Frames: {num_frames}")
    print(f"  Size: {args['size']}x{args['size']}")
    print(f"  Camera: {scene.camera.name if scene.camera else 'None'}")
    print(f"  Neutralize BG: {args['neutralize_bg']}")

    # Calculate evenly-spaced frames
    total = frame_end - frame_start + 1
    if total <= num_frames:
        frames = list(range(frame_start, frame_end + 1))
    else:
        step = total / num_frames
        frames = [int(frame_start + i * step) for i in range(num_frames)]

    print(f"  Rendering: {frames}")

    setup_render(args["size"], args["neutralize_bg"])
    os.makedirs(args["output"], exist_ok=True)

    for i, frame in enumerate(frames):
        scene.frame_set(frame)
        path = os.path.join(args["output"], f"frame_{i:04d}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {i + 1}/{len(frames)}: {path}")

    print(f"\nDone: {len(frames)} frames")


if __name__ == "__main__":
    main()
