"""Compatibility helpers for Blender 4.2 through current Blender releases.

Blender's Python API intentionally evolves between releases.  Keep feature
detection here so the operators and menus can share the same fallbacks without
hard-coding a maximum Blender version.
"""

import logging
from typing import Any, Optional

import bpy


log = logging.getLogger(__name__)


def get_operator(idname: str) -> Optional[Any]:
    """Return a Blender operator if it is registered in this build."""
    try:
        namespace, name = idname.split('.', 1)
        operator_namespace = getattr(bpy.ops, namespace, None)
        return getattr(operator_namespace, name, None)
    except (AttributeError, ValueError):
        return None


def call_operator(idname: str, **kwargs: Any) -> bool:
    """Call an operator when available and report whether it completed."""
    operator = get_operator(idname)
    if operator is None:
        return False

    try:
        result = operator(**kwargs)
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        log.debug("Operator %s is unavailable: %s", idname, exc)
        return False

    return not isinstance(result, set) or 'CANCELLED' not in result


def set_snap_uv_element(tool_settings: Any, element: str) -> bool:
    """Set the UV snap enum across builds that use a string or a set."""
    if not hasattr(tool_settings, 'snap_uv_element'):
        return False

    try:
        tool_settings.snap_uv_element = {element}
    except (TypeError, ValueError):
        try:
            tool_settings.snap_uv_element = element
        except (AttributeError, TypeError, ValueError):
            return False
    return True


def set_snap_enabled(tool_settings: Any, enabled: bool, uv: bool = False) -> bool:
    """Set the regular or UV snapping toggle with an older-build fallback."""
    property_name = 'use_snap_uv' if uv and hasattr(tool_settings, 'use_snap_uv') else 'use_snap'
    if not hasattr(tool_settings, property_name):
        return False

    try:
        setattr(tool_settings, property_name, enabled)
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def set_absolute_grid_snap(tool_settings: Any, enabled: bool = True) -> bool:
    """Set absolute grid snapping when the current build exposes it."""
    for property_name in ('use_snap_grid_absolute', 'use_snap_uv_grid_absolute'):
        if not hasattr(tool_settings, property_name):
            continue
        try:
            setattr(tool_settings, property_name, enabled)
            return True
        except (AttributeError, TypeError, ValueError):
            continue
    return False


def draw_snap_toggle(layout: Any, tool_settings: Any, uv: bool = False,
                     text: str = 'Snap Toggle') -> Any:
    """Draw a snapping toggle using the property available in this build."""
    property_name = 'use_snap_uv' if uv and hasattr(tool_settings, 'use_snap_uv') else 'use_snap'
    return layout.prop(tool_settings, property_name, text=text)


def select_edge_loop_or_ring(ring: bool) -> bool:
    """Use the renamed edge-selection operators with a legacy fallback."""
    modern_operator = 'mesh.select_edge_ring_multi' if ring else 'mesh.select_edge_loop_multi'
    if call_operator(modern_operator):
        return True
    return call_operator('mesh.loop_multi_select', ring=ring)


_LEGACY_BRUSH_TOOLS = {
    'SCULPT': {
        'Draw': 'DRAW',
        'Draw Sharp': 'DRAW_SHARP',
        'Clay': 'CLAY',
        'Clay Strips': 'CLAY_STRIPS',
        'Clay Thumb': 'CLAY_THUMB',
        'Layer': 'LAYER',
        'Inflate': 'INFLATE',
        'Inflate/Deflate': 'INFLATE',
        'Blob': 'BLOB',
        'Crease': 'CREASE',
        'Crease Sharp': 'CREASE',
        'Crease Polish': 'CREASE',
        'Smooth': 'SMOOTH',
        'Flatten': 'FLATTEN',
        'Flatten/Contrast': 'FLATTEN',
        'Fill': 'FILL',
        'Fill/Deepen': 'FILL',
        'Scrape': 'SCRAPE',
        'Scrape/Fill': 'SCRAPE',
        'Scrape Multiplane': 'SCRAPE',
        'Cloth': 'CLOTH',
        'Face Sets': 'DRAW_FACE_SETS',
        'Face Set Paint': 'DRAW_FACE_SETS',
        'Elastic Deform': 'ELASTIC_DEFORM',
        'Pinch': 'PINCH',
        'Grab': 'GRAB',
        'Snake Hook': 'SNAKE_HOOK',
        'Thumb': 'THUMB',
        'Pose': 'POSE',
        'Nudge': 'NUDGE',
        'Rotate': 'ROTATE',
        'Simplify': 'SIMPLIFY',
    },
    'TEXTURE_PAINT': {
        'Draw': 'DRAW',
        'Soft': 'SOFTEN',
        'Blur': 'BLUR',
        'Fill': 'FILL',
        'Mask': 'MASK',
        'Airbrush': 'DRAW',
        'Clone': 'CLONE',
        'Smear': 'SMEAR',
    },
    'VERTEX_PAINT': {
        'Draw': 'MIX',
        'Blur': 'BLUR',
        'Average': 'AVERAGE',
        'Smear': 'SMEAR',
    },
    'WEIGHT_PAINT': {
        'Draw': 'MIX',
        'Blur': 'BLUR',
        'Average': 'AVERAGE',
        'Smear': 'SMEAR',
    },
}


_ESSENTIALS_BRUSH_ALIASES = {
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


_ESSENTIALS_BRUSH_CATEGORIES = {
    'mesh_sculpt': 'SCULPT',
    'mesh_texture': 'TEXTURE_PAINT',
    'mesh_vertex': 'VERTEX_PAINT',
    'mesh_weight': 'WEIGHT_PAINT',
}


def _brush_name(asset_path: str, brush_name: Optional[str]) -> str:
    if brush_name:
        return brush_name
    normalized = asset_path.rstrip('/\\').replace('\\', '/')
    if '/Brush/' in normalized:
        return normalized.split('/Brush/', 1)[1]
    return normalized.rsplit('/', 1)[-1]


def _asset_path_candidates(asset_path: str, brush_name: Optional[str]):
    """Return modern Essentials paths plus the legacy path supplied by users."""
    normalized = asset_path.strip().replace('\\', '/')
    if not normalized:
        return ()

    candidates = []
    category_key = None
    lowered = normalized.lower()
    for key in _ESSENTIALS_BRUSH_CATEGORIES:
        if f'/{key}/' in f'/{lowered}/' or f'essentials_brushes-{key}.blend' in lowered:
            category_key = key
            break

    if category_key:
        name = _brush_name(normalized, brush_name)
        names = (
            _ESSENTIALS_BRUSH_ALIASES.get(name, (name,))
            if category_key == 'mesh_sculpt'
            else (name,)
        )
        for name_variant in names:
            candidates.append(
                f'brushes/essentials_brushes-{category_key}.blend/Brush/{name_variant}'
            )

    candidates.append(normalized)
    return tuple(dict.fromkeys(candidates))


def activate_brush(asset_path: str, paint_mode: str,
                   brush_name: Optional[str] = None) -> bool:
    """Activate an Essentials brush with modern and legacy API fallbacks."""
    for candidate in _asset_path_candidates(asset_path, brush_name):
        if call_operator(
            'brush.asset_activate',
            asset_library_type='ESSENTIALS',
            asset_library_identifier='',
            relative_asset_identifier=candidate,
            use_toggle=False,
        ):
            return True
        # The optional toggle argument is not exposed by some early asset
        # browser builds even though the activation operator is present.
        if call_operator(
            'brush.asset_activate',
            asset_library_type='ESSENTIALS',
            asset_library_identifier='',
            relative_asset_identifier=candidate,
        ):
            return True

    tool_name = _LEGACY_BRUSH_TOOLS.get(paint_mode, {}).get(
        _brush_name(asset_path, brush_name)
    )
    if not tool_name:
        return False

    property_name = {
        'SCULPT': 'sculpt_tool',
        'TEXTURE_PAINT': 'texture_paint_tool',
        'VERTEX_PAINT': 'vertex_paint_tool',
        'WEIGHT_PAINT': 'weight_paint_tool',
    }.get(paint_mode)
    if property_name is None:
        return False

    if call_operator(
        'paint.brush_select',
        paint_mode=paint_mode,
        **{property_name: tool_name},
    ):
        return True
    if call_operator(
        'paint.brush_select',
        **{property_name: tool_name},
    ):
        return True

    # Blender builds that removed paint.brush_select still expose the brush
    # datablock on tool settings. Use it when it is already available.
    settings_name = {
        'SCULPT': 'sculpt',
        'TEXTURE_PAINT': 'image_paint',
        'VERTEX_PAINT': 'vertex_paint',
        'WEIGHT_PAINT': 'weight_paint',
    }.get(paint_mode)
    settings = getattr(bpy.context.tool_settings, settings_name, None)
    brush = bpy.data.brushes.get(_brush_name(asset_path, brush_name))
    if settings is not None and brush is not None and hasattr(settings, 'brush'):
        try:
            settings.brush = brush
            return True
        except (AttributeError, TypeError, ValueError):
            pass

    return False


def shade_auto_smooth(angle: float) -> bool:
    """Use the old auto-smooth operator or its 4.1+ replacement."""
    operator = get_operator('object.shade_auto_smooth')
    if operator is not None:
        try:
            result = operator(use_auto_smooth=True, angle=angle)
            if not isinstance(result, set) or 'CANCELLED' not in result:
                return True
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    operator = get_operator('object.shade_smooth_by_angle')
    if operator is not None:
        try:
            result = operator(angle=angle, keep_sharp_edges=True)
        except TypeError:
            result = operator(angle=angle)
        except (AttributeError, RuntimeError, ValueError):
            return False
        return not isinstance(result, set) or 'CANCELLED' not in result

    return call_operator('object.shade_smooth')


def clear_custom_normals() -> bool:
    """Clear custom normals when the legacy operator is available."""
    return call_operator('mesh.customdata_custom_splitnormals_clear')


def remove_uv_layers(mesh: Any) -> bool:
    """Remove UV data using the operator or the modern collection API."""
    if call_operator('mesh.uv_texture_remove'):
        return True

    uv_layers = getattr(mesh, 'uv_layers', None)
    if uv_layers is not None and hasattr(uv_layers, 'clear'):
        uv_layers.clear()
        return True
    return False


def import_file(filepath: str, file_type: str) -> bool:
    """Import OBJ/FBX through the current operator namespace."""
    candidates = {
        'obj': ('wm.obj_import', 'import_scene.obj'),
        'fbx': ('wm.fbx_import', 'import_scene.fbx'),
    }.get(file_type.lower(), ())

    for idname in candidates:
        if call_operator(idname, filepath=filepath):
            return True
    return False


def set_grease_pencil_mode(mode: str) -> bool:
    """Set Grease Pencil mode across the legacy and new mode identifiers."""
    mode_names = {
        'EDIT': ('EDIT_GREASE_PENCIL', 'EDIT_GPENCIL'),
        'SCULPT': ('SCULPT_GREASE_PENCIL', 'SCULPT_GPENCIL'),
        'PAINT': ('PAINT_GREASE_PENCIL', 'PAINT_GPENCIL'),
        'WEIGHT': ('WEIGHT_GREASE_PENCIL', 'WEIGHT_GPENCIL'),
    }.get(mode, ())

    for mode_name in mode_names:
        if call_operator('object.mode_set', mode=mode_name):
            return True

    legacy_operator = {
        'EDIT': ('grease_pencil.editmode_toggle', 'gpencil.editmode_toggle'),
        'SCULPT': ('grease_pencil.sculptmode_toggle', 'gpencil.sculptmode_toggle'),
        'PAINT': ('grease_pencil.paintmode_toggle', 'gpencil.paintmode_toggle'),
        'WEIGHT': ('grease_pencil.weightmode_toggle', 'gpencil.weightmode_toggle'),
    }.get(mode, ())
    return any(call_operator(idname) for idname in legacy_operator)
