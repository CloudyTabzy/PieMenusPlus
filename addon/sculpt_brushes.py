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
