"""
Blender render script for spritebake.
Called internally - renders animation frames to PNG files.
"""

import bpy
import sys
import os
import math
from mathutils import Vector


def get_scene_bounds():
    """Calculate bounding box of all visible mesh objects."""
    scene = bpy.context.scene
    min_co = [float('inf')] * 3
    max_co = [float('-inf')] * 3

    for obj in scene.objects:
        if obj.type == 'MESH' and obj.visible_get():
            for corner in obj.bound_box:
                world_corner = obj.matrix_world @ Vector(corner)
                for i in range(3):
                    min_co[i] = min(min_co[i], world_corner[i])
                    max_co[i] = max(max_co[i], world_corner[i])

    # If no meshes found, use a default box around origin
    if min_co[0] == float('inf'):
        min_co = [-1, -1, -1]
        max_co = [1, 1, 1]

    center = [(min_co[i] + max_co[i]) / 2 for i in range(3)]
    size_x = max_co[0] - min_co[0]
    size_y = max_co[1] - min_co[1]
    size_z = max_co[2] - min_co[2]

    return center, (size_x, size_y, size_z)


def ensure_camera(center, sizes):
    """Create a camera if none exists, positioned to frame the scene."""
    scene = bpy.context.scene

    if scene.camera is not None:
        return False  # Already have a camera

    size_x, size_y, size_z = sizes
    max_size = max(size_x, size_z)  # For front view, we care about width (X) and height (Z)

    # Create camera
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "AutoCamera"

    # Set to orthographic
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = max_size * 1.2  # Add 20% margin

    # Position camera in front (negative Y axis, looking toward +Y)
    distance = max(max_size, size_y) * 2  # Far enough to not clip
    camera.location = (center[0], center[1] - distance, center[2])
    camera.rotation_euler = (math.pi / 2, 0, 0)  # 90 degrees around X

    # Set as active camera
    scene.camera = camera

    print("[AUTO_CAMERA] Created orthographic front-view camera")
    return True


def ensure_light(scene_center, scene_size):
    """Create a light if none exists in the scene."""
    scene = bpy.context.scene

    # Check if any lights exist
    lights = [obj for obj in scene.objects if obj.type == 'LIGHT']
    if lights:
        return False  # Already have lights

    # Add a sun light for even illumination
    bpy.ops.object.light_add(type='SUN')
    sun = bpy.context.object
    sun.name = "AutoSun"
    sun.data.energy = 3.0

    # Position above and in front of subject, angled down at 45 degrees
    sun.location = (scene_center[0], scene_center[1] - scene_size * 2, scene_center[2] + scene_size * 2)
    sun.rotation_euler = (math.radians(45), 0, 0)

    print("[AUTO_LIGHT] Created sun light for scene without one")
    return True


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


def setup_render(size, neutralize_bg=True, render_scale=2):
    """Configure Blender render settings for sprite output."""
    scene = bpy.context.scene

    # Use Eevee for speed
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'

    # Render at higher resolution, downscale later for cleaner sprites
    render_size = size * render_scale
    scene.render.resolution_x = render_size
    scene.render.resolution_y = render_size
    print(f"[RENDER] Rendering at {render_size}x{render_size}, will downscale to {size}x{size}")

    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    # EEVEE performance optimizations (with fallbacks for different Blender versions)
    eevee = scene.eevee

    # Settings that exist in most versions
    try:
        eevee.use_gtao = False              # Ambient Occlusion
    except AttributeError:
        pass
    try:
        eevee.use_bloom = False             # Bloom/glow (removed in 4.x)
    except AttributeError:
        pass
    try:
        eevee.use_ssr = False               # Screen Space Reflections (removed in 4.x)
    except AttributeError:
        pass
    try:
        eevee.use_motion_blur = False       # Motion blur (moved in 4.x)
    except AttributeError:
        pass
    try:
        eevee.use_volumetric_lights = False # Volumetrics (removed in 4.x)
    except AttributeError:
        pass
    try:
        eevee.use_volumetric_shadows = False
    except AttributeError:
        pass
    try:
        eevee.shadow_cube_size = '256'      # Reduced from 512 (removed in 4.x)
    except AttributeError:
        pass
    try:
        eevee.shadow_cascade_size = '256'   # (removed in 4.x)
    except AttributeError:
        pass
    try:
        eevee.taa_render_samples = 8        # Reduced from 64
    except AttributeError:
        pass

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

    # Get scene bounds for auto-camera/light positioning
    center, sizes = get_scene_bounds()
    max_size = max(sizes[0], sizes[2])

    # Create camera if none exists
    ensure_camera(center, sizes)

    # Create light if none exists
    ensure_light(center, max_size)

    # Try to find and relink missing textures
    blend_dir = os.path.dirname(bpy.data.filepath)
    if blend_dir:
        try:
            bpy.ops.file.find_missing_files(directory=blend_dir)
            print(f"[TEXTURES] Searched for missing files in: {blend_dir}")
        except Exception as e:
            print(f"[TEXTURES] Could not search for missing files: {e}")

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
