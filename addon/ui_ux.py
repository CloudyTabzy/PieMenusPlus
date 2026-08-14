"""Shared presentation and context helpers for Pie Menus Plus.

Blender owns the native pie container, including its background styling.  The
helpers in this module therefore focus on the presentation details that an
add-on can control reliably across Blender 4.2 and newer releases: labels,
spacing, icons, and context-aware visibility.
"""

from __future__ import annotations

import bpy

from .utils import get_addon_preferences


PIE_THEME_ITEMS = (
    (
        "NATIVE",
        "Native",
        "Keep Blender's normal pie proportions and full labels",
    ),
    (
        "COMPACT",
        "Compact",
        "Use tighter spacing and shorter labels for small or crowded pies",
    ),
    (
        "FOCUS",
        "Focus",
        "Keep names prominent and use stronger status cues for unavailable actions",
    ),
)

PIE_LABEL_MODE_ITEMS = (
    (
        "FULL",
        "Full Labels",
        "Show the complete action name beside its icon",
    ),
    (
        "COMPACT",
        "Compact Labels",
        "Use concise labels where a shorter equivalent is available",
    ),
    (
        "SLOT_FIRST",
        "Slot + Label",
        "Prefix configurable entries with their slot number",
    ),
    (
        "ICON_ONLY",
        "Icons Only",
        "Hide labels when the icon is clear enough for the workflow",
    ),
)


_COMPACT_LABELS = {
    "Proportional Toggle": "Proportional",
    "Snap Toggle": "Snap",
    "X-Ray Toggle": "X-Ray",
    "Isolate Toggle": "Isolate",
    "Face Orientation Overlay": "Face Orientation",
    "Animation Playback": "Playback",
}


def _get_pref(name, default):
    """Read a preference without making UI drawing depend on registration order."""
    try:
        return getattr(get_addon_preferences(), name, default)
    except (AttributeError, KeyError, RuntimeError, TypeError):
        return default


def pie_theme():
    return _get_pref("pie_theme", "NATIVE")


def pie_label_mode():
    return _get_pref("pie_label_mode", "FULL")


def context_filtering_enabled():
    return bool(_get_pref("context_filtering", True))


def show_unavailable_actions():
    return bool(_get_pref("show_unavailable_actions", False))


def show_sculpt_brush_previews():
    return bool(_get_pref("show_sculpt_brush_previews", True))


def format_pie_label(label, slot=None):
    """Return a preference-aware label for a pie item.

    ``slot`` is intentionally optional so the helper can be reused for normal
    pie actions as well as configurable sculpt slots.
    """
    text = str(label or "")
    mode = pie_label_mode()

    if mode == "ICON_ONLY":
        return ""

    if mode == "SLOT_FIRST" and slot is not None and text:
        return f"{slot}: {text}"

    if mode == "COMPACT" or pie_theme() == "COMPACT":
        return _COMPACT_LABELS.get(text, text)

    return text


def configure_pie_layout(pie):
    """Apply safe, native-layout presentation choices to a pie layout."""
    theme = pie_theme()
    if theme == "COMPACT":
        pie.scale_y = 1.0
    elif theme == "FOCUS":
        pie.scale_y = 1.25
    return pie


def context_allows_menu(context, *, modes=None, object_types=None,
                        require_object=False, require_selection=False,
                        area_types=None):
    """Return whether a menu is useful in the current context.

    Filtering is opt-out in preferences.  When disabled, callers retain the
    old behavior and can draw their own warning or fallback content.
    """
    if not context_filtering_enabled():
        return True

    if modes and getattr(context, "mode", None) not in set(modes):
        return False

    if area_types:
        area = getattr(context, "area", None)
        if area is None or getattr(area, "type", None) not in set(area_types):
            return False

    obj = getattr(context, "object", None)
    if require_object and obj is None:
        return False

    if object_types and (obj is None or getattr(obj, "type", None) not in set(object_types)):
        return False

    if require_selection and not getattr(context, "selected_objects", ()):
        return False

    return True


def draw_unavailable(layout, text, *, icon="ERROR"):
    """Draw a disabled explanation when the user asks to see unavailable items."""
    if not show_unavailable_actions():
        return

    row = layout.row()
    row.enabled = False
    row.alert = pie_theme() == "FOCUS"
    row.label(text=text, icon=icon)


def context_summary(context):
    """Return a compact, human-readable context summary for diagnostics."""
    mode = getattr(context, "mode", "Unknown")
    obj = getattr(context, "object", None)
    object_name = getattr(obj, "name", "No active object") if obj else "No active object"
    object_type = getattr(obj, "type", "-") if obj else "-"
    selected = len(getattr(context, "selected_objects", ()) or ())
    return f"{mode}  |  {object_type}: {object_name}  |  {selected} selected"


def blender_version_label():
    """Return a stable version label without assuming a fixed release length."""
    version = getattr(bpy.app, "version", ())
    if len(version) >= 2:
        return ".".join(str(part) for part in version[:3])
    return "Unknown"
