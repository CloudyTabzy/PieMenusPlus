"""Shared data for the configurable sculpt brush workflow."""


CUSTOM_SCULPT_BRUSH_SLOTS = (
    (1, "Left", "Draw"),
    (2, "Right", "Blob"),
    (3, "Bottom", "Clay"),
    (4, "Top", "Clay Strips"),
    (5, "Top-Left", "Inflate"),
    (6, "Top-Right", "Smooth"),
    (7, "Bottom-Left", "Crease"),
    (8, "Bottom-Right", "Flatten"),
)

DEFAULT_CUSTOM_SCULPT_BRUSHES = {
    slot: f"Brushes/mesh_sculpt/{brush_name}"
    for slot, _direction, brush_name in CUSTOM_SCULPT_BRUSH_SLOTS
}


# Blender has renamed several Essentials assets over time. Keep the friendly
# name first and use the variants for activation and preview lookup.
SCULPT_BRUSH_NAME_ALIASES = {
    'Inflate': ('Inflate/Deflate', 'Inflate'),
    'Crease': ('Crease Sharp', 'Crease Polish', 'Crease'),
    'Flatten': ('Flatten/Contrast', 'Flatten'),
    'Fill': ('Fill/Deepen', 'Fill'),
    'Scrape': ('Scrape/Fill', 'Scrape'),
    'Multi-plane Scrape': ('Scrape Multiplane', 'Multi-plane Scrape'),
    'Face Sets': ('Face Set Paint', 'Face Sets'),
    'Elastic Deform': ('Elastic Grab', 'Elastic Snake Hook', 'Elastic Deform'),
    'Pinch': ('Pinch/Magnify', 'Pinch'),
    'Slide Relax': ('Relax Slide', 'Slide Relax'),
    'Displacement Eraser': (
        'Erase Multires Displacement',
        'Displacement Eraser',
    ),
    'Displacement Smear': (
        'Smear Multires Displacement',
        'Displacement Smear',
    ),
    'Multires Displacement Eraser': (
        'Erase Multires Displacement',
        'Multires Displacement Eraser',
    ),
    'Multires Displacement Smear': (
        'Smear Multires Displacement',
        'Multires Displacement Smear',
    ),
    'Rotate': ('Twist', 'Rotate'),
    'Cloth': ('Grab Cloth', 'Cloth'),
}


SCULPT_BRUSH_PRESETS = {
    "BALANCED": {
        1: "Brushes/mesh_sculpt/Draw",
        2: "Brushes/mesh_sculpt/Clay",
        3: "Brushes/mesh_sculpt/Clay Strips",
        4: "Brushes/mesh_sculpt/Smooth",
        5: "Brushes/mesh_sculpt/Inflate",
        6: "Brushes/mesh_sculpt/Grab",
        7: "Brushes/mesh_sculpt/Crease",
        8: "Brushes/mesh_sculpt/Flatten",
    },
    "DETAILING": {
        1: "Brushes/mesh_sculpt/Draw Sharp",
        2: "Brushes/mesh_sculpt/Crease",
        3: "Brushes/mesh_sculpt/Clay Strips",
        4: "Brushes/mesh_sculpt/Smooth",
        5: "Brushes/mesh_sculpt/Inflate",
        6: "Brushes/mesh_sculpt/Pinch",
        7: "Brushes/mesh_sculpt/Scrape",
        8: "Brushes/mesh_sculpt/Flatten",
    },
    "CHARACTER": {
        1: "Brushes/mesh_sculpt/Grab",
        2: "Brushes/mesh_sculpt/Clay",
        3: "Brushes/mesh_sculpt/Clay Strips",
        4: "Brushes/mesh_sculpt/Smooth",
        5: "Brushes/mesh_sculpt/Inflate",
        6: "Brushes/mesh_sculpt/Grab",
        7: "Brushes/mesh_sculpt/Crease",
        8: "Brushes/mesh_sculpt/Mask",
    },
}


def custom_sculpt_brush_property(slot: int) -> str:
    return f"custom_sculpt_brush_{slot}"


def custom_sculpt_brush_defaults():
    """Return a copy so callers cannot mutate the shared defaults."""
    return dict(DEFAULT_CUSTOM_SCULPT_BRUSHES)


def sculpt_brush_name_from_path(asset_path: str) -> str:
    """Extract a friendly brush name from a legacy or modern asset path."""
    normalized = (asset_path or '').strip().rstrip('/\\').replace('\\', '/')
    if not normalized:
        return 'Unassigned'
    if '/Brush/' in normalized:
        name = normalized.split('/Brush/', 1)[1]
    else:
        name = normalized.rsplit('/', 1)[-1]

    for friendly_name, variants in SCULPT_BRUSH_NAME_ALIASES.items():
        if name in variants:
            return friendly_name
    return name
