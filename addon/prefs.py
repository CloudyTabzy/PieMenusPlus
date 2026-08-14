import json

import bpy
from bpy.props import (
    StringProperty, EnumProperty, BoolProperty, IntProperty, PointerProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup, Operator, AddonPreferences, Scene

# Optional private UI helper; the plain keymap string remains the fallback.
try:
    import rna_keymap_ui
except ImportError:
    rna_keymap_ui = None

from .utils import get_addon_preferences
from .dependencies import dependency_statuses
from .pie_ops.pie_timeline_scrub import (
    PIESPLUS_timeline_settings,
    draw_timeline_scrub_preferences,
)
from .sculpt_brushes import (
    CUSTOM_SCULPT_BRUSH_SLOTS,
    DEFAULT_CUSTOM_SCULPT_BRUSHES,
    custom_sculpt_brush_property,
)
from .ui_ux import PIE_LABEL_MODE_ITEMS, PIE_THEME_ITEMS


##################################
# Property Group
##################################


class PIESPLUS_property_group(PropertyGroup):
    def update_smoothAngle(self, context):
        if context.selected_objects:
            bpy.ops.pies_plus.auto_smooth()

    def update_uvSyncSelection(self, context):
        context.scene.tool_settings.use_uv_select_sync = self.uvSyncSelection

        if not get_addon_preferences().preserve_uv_selection_pref:
            return

        if not context.scene.tool_settings.use_uv_select_sync:
            old_area_type = context.area.type

            context.area.type = 'VIEW_3D'

            bpy.ops.mesh.select_all(action='SELECT')

            context.area.type = old_area_type

    smoothAngle: IntProperty(
        name="Smooth Angle",
        default=60,
        min=0,
        max=180,
        update=update_smoothAngle
    )

    uvSyncSelection: BoolProperty(
        name="UV Sync Selection",
        update=update_uvSyncSelection
    )


##################################
# Keymapping
##################################


class PIESPLUS_addon_keymaps:
    _addon_keymaps = []
    _keymaps = {}
    _event_fields = (
        'type', 'value', 'ctrl', 'shift', 'alt', 'oskey', 'key_modifier',
        'any', 'repeat', 'direction',
    )

    @classmethod
    def new_keymap(cls, name, kmi_name, kmi_value=None, km_name='3D View',
                   space_type="VIEW_3D", region_type="WINDOW",
                   event_type=None, event_value=None, ctrl=False, shift=False,
                   alt=False, key_modifier="NONE"):

        cls._keymaps.update({name: [kmi_name, kmi_value, km_name, space_type,
                                    region_type, event_type, event_value,
                                    ctrl, shift, alt, key_modifier]})

    @staticmethod
    def _definition_event(items):
        return {
            'type': items[5],
            'value': items[6],
            'ctrl': items[7],
            'shift': items[8],
            'alt': items[9],
            'key_modifier': items[10],
            'oskey': False,
            'any': False,
        }

    @staticmethod
    def _item_property_name(kmi):
        try:
            return getattr(kmi.properties, 'name', None)
        except (AttributeError, ReferenceError, RuntimeError):
            return None

    @staticmethod
    def _same_item(left, right):
        if left is right:
            return True
        try:
            return left.as_pointer() == right.as_pointer()
        except (AttributeError, ReferenceError, RuntimeError):
            return False

    @classmethod
    def _matches_definition(cls, kmi, items):
        if kmi is None or kmi.idname != items[0]:
            return False
        expected_name = items[1]
        return expected_name is None or cls._item_property_name(kmi) == expected_name

    @classmethod
    def _event_values(cls, source):
        if isinstance(source, dict):
            return {
                field: source.get(field, False if field not in {'type', 'value', 'key_modifier'} else None)
                for field in cls._event_fields
            }
        return {
            field: getattr(source, field, False if field not in {'type', 'value', 'key_modifier'} else None)
            for field in cls._event_fields
        }

    @classmethod
    def _same_event(cls, left, right):
        left_values = cls._event_values(left)
        right_values = cls._event_values(right)

        if (
            left_values['type'] != right_values['type']
            or left_values['value'] != right_values['value']
        ):
            return False

        # An item using Blender's "Any" modifier flag overlaps all modifier
        # combinations for the same key and event value.
        if left_values['any'] or right_values['any']:
            return True

        return all(
            left_values[field] == right_values[field]
            for field in ('ctrl', 'shift', 'alt', 'oskey', 'key_modifier')
        )

    @classmethod
    def find_keymap_item(cls, kc, keymap_name):
        items = cls._keymaps.get(keymap_name)
        if not items or kc is None:
            return None, None

        km = kc.keymaps.get(items[2])
        if km is None:
            return None, None

        for kmi in km.keymap_items:
            if cls._matches_definition(kmi, items):
                return km, kmi
        return km, None

    @classmethod
    def _find_tracked_item(cls, keymap_name):
        items = cls._keymaps.get(keymap_name)
        if not items:
            return None, None

        for km, kmi in cls._addon_keymaps:
            try:
                if cls._matches_definition(kmi, items):
                    return km, kmi
            except (ReferenceError, RuntimeError):
                continue
        return None, None

    @classmethod
    def add_hotkey(cls, kc, keymap_name):
        items = cls._keymaps.get(keymap_name)
        if not items:
            return None

        kmi_name, kmi_value, km_name, space_type, region_type = items[:5]
        event_type, event_value, ctrl, shift, alt, key_modifier = items[5:]
        km = kc.keymaps.new(name=km_name, space_type=space_type,
                            region_type=region_type)
        kmi = next(
            (
                item for item in km.keymap_items
                if cls._matches_definition(item, items)
            ),
            None,
        )
        if kmi is None:
            if not event_type:
                return None
            kmi = km.keymap_items.new(kmi_name, event_type, event_value,
                                      ctrl=ctrl, shift=shift, alt=alt,
                                      key_modifier=key_modifier)

        if kmi_value:
            kmi.properties.name = kmi_value

        kmi.active = True

        if not any(cls._same_item(existing, kmi) for _km, existing in cls._addon_keymaps):
            cls._addon_keymaps.append((km, kmi))
        return kmi

    @staticmethod
    def register_keymaps():
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon

        if not kc:
            return

        if PIESPLUS_addon_keymaps._addon_keymaps:
            PIESPLUS_addon_keymaps.unregister_keymaps()

        for keymap_name in PIESPLUS_addon_keymaps._keymaps.keys():
            PIESPLUS_addon_keymaps.add_hotkey(kc, keymap_name)

    @classmethod
    def unregister_keymaps(cls):
        for km, kmi in cls._addon_keymaps:
            try:
                km.keymap_items.remove(kmi)
            except (ReferenceError, RuntimeError, ValueError):
                pass

        cls._addon_keymaps.clear()

    @staticmethod
    def _item_to_string(kmi):
        try:
            return kmi.to_string()
        except (AttributeError, ReferenceError, RuntimeError):
            return "Shortcut unavailable"

    @classmethod
    def _status(cls, name, kc):
        items = cls._keymaps.get(name)
        km, kmi = cls.find_keymap_item(kc, name)
        scan_km = km
        # In background mode, and in some Blender preference views, add-on
        # keymaps are not mirrored into the user keyconfig.  Inspect the
        # add-on keyconfig as a safe fallback, while still treating an
        # existing user keymap with a missing item as a real user override.
        if kmi is None and kc is not getattr(bpy.context.window_manager.keyconfigs, 'addon', None):
            addon_kc = getattr(bpy.context.window_manager.keyconfigs, 'addon', None)
            addon_km, addon_kmi = cls.find_keymap_item(addon_kc, name)
            if addon_kmi is not None:
                km, kmi = addon_km, addon_kmi
        if scan_km is None:
            scan_km = km
        if km is None:
            state = 'missing'
            conflicts = []
        else:
            source = kmi if kmi is not None else cls._definition_event(items)
            conflicts = []
            for candidate in scan_km.keymap_items:
                try:
                    if not getattr(candidate, 'active', True):
                        continue
                    if cls._same_item(candidate, kmi):
                        continue
                    if cls._matches_definition(candidate, items):
                        continue
                    if cls._same_event(candidate, source):
                        conflicts.append(candidate)
                except (ReferenceError, RuntimeError):
                    continue
            state = 'missing' if kmi is None else ('disabled' if not kmi.active else 'ok')

        return {
            'name': name,
            'items': items,
            'keymap': km,
            'item': kmi,
            'state': state,
            'conflicts': conflicts,
            'shortcut': cls._item_to_string(kmi) if kmi else cls._format_definition(items),
        }

    @staticmethod
    def _format_definition(items):
        if not items:
            return "Shortcut unavailable"
        modifiers = []
        if items[7]:
            modifiers.append('Ctrl')
        if items[8]:
            modifiers.append('Shift')
        if items[9]:
            modifiers.append('Alt')
        if items[10] and items[10] != 'NONE':
            modifiers.append(str(items[10]).title())
        modifiers.append(str(items[5] or '?'))
        return '+'.join(modifiers)

    @classmethod
    def get_statuses(cls, wm=None):
        wm = wm or bpy.context.window_manager
        kc = getattr(wm.keyconfigs, 'user', None) if wm else None
        return [cls._status(name, kc) for name in cls._keymaps]

    @classmethod
    def get_summary(cls, wm=None):
        statuses = cls.get_statuses(wm)
        return {
            'total': len(statuses),
            'active': sum(status['state'] == 'ok' for status in statuses),
            'missing': sum(status['state'] == 'missing' for status in statuses),
            'disabled': sum(status['state'] == 'disabled' for status in statuses),
            'conflicts': sum(bool(status['conflicts']) for status in statuses),
        }

    @classmethod
    def _apply_event(cls, kmi, event):
        for field in cls._event_fields:
            if field not in event or event[field] is None:
                continue
            try:
                setattr(kmi, field, event[field])
            except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                pass

    @classmethod
    def _reset_item(cls, kmi, items):
        cls._apply_event(kmi, cls._definition_event(items))
        try:
            kmi.active = True
        except (AttributeError, ReferenceError, RuntimeError):
            pass
        if items[1]:
            try:
                kmi.properties.name = items[1]
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass

    @classmethod
    def restore_hotkey(cls, keymap_name, wm=None):
        items = cls._keymaps.get(keymap_name)
        wm = wm or bpy.context.window_manager
        if not items or wm is None:
            return False

        addon_kc = getattr(wm.keyconfigs, 'addon', None)
        user_kc = getattr(wm.keyconfigs, 'user', None)
        addon_km, addon_kmi = cls._find_tracked_item(keymap_name)
        if addon_kmi is None and addon_kc is not None:
            addon_km, addon_kmi = cls.find_keymap_item(addon_kc, keymap_name)
        if addon_kmi is None and addon_kc is not None:
            addon_kmi = cls.add_hotkey(addon_kc, keymap_name)
        if addon_kmi is not None:
            cls._reset_item(addon_kmi, items)

        _user_km, user_kmi = cls.find_keymap_item(user_kc, keymap_name)
        if user_kmi is not None:
            cls._reset_item(user_kmi, items)

        return addon_kmi is not None or user_kmi is not None

    @classmethod
    def restore_all_hotkeys(cls, wm=None):
        restored = 0
        for name in cls._keymaps:
            if cls.restore_hotkey(name, wm):
                restored += 1
        return restored

    @classmethod
    def capture_profile(cls, wm=None):
        wm = wm or bpy.context.window_manager
        user_kc = getattr(wm.keyconfigs, 'user', None) if wm else None
        addon_kc = getattr(wm.keyconfigs, 'addon', None) if wm else None
        entries = []

        for name in cls._keymaps:
            _km, kmi = cls.find_keymap_item(user_kc, name)
            if kmi is None:
                _km, kmi = cls._find_tracked_item(name)
            if kmi is None and addon_kc is not None:
                _km, kmi = cls.find_keymap_item(addon_kc, name)
            if kmi is None:
                continue

            event = {
                field: getattr(kmi, field, None)
                for field in cls._event_fields
            }
            entries.append({
                'name': name,
                'event': event,
                'active': bool(getattr(kmi, 'active', True)),
            })

        return {'version': 1, 'entries': entries}

    @classmethod
    def apply_profile(cls, profile, wm=None):
        wm = wm or bpy.context.window_manager
        user_kc = getattr(wm.keyconfigs, 'user', None) if wm else None
        applied = 0
        for entry in profile.get('entries', ()):
            name = entry.get('name')
            if name not in cls._keymaps:
                continue
            _km, kmi = cls.find_keymap_item(user_kc, name)
            if kmi is None:
                _km, kmi = cls._find_tracked_item(name)
            if kmi is None:
                continue
            cls._apply_event(kmi, entry.get('event', {}))
            try:
                kmi.active = bool(entry.get('active', True))
            except (AttributeError, ReferenceError, RuntimeError):
                pass
            applied += 1
        return applied

    @classmethod
    def get_hotkey_entry_item(cls, name, kc, km, col):
        if km is None:
            col.label(text=f"Keymap unavailable: {name}")
            operator = col.operator(
                PIESPLUS_OT_add_hotkey.bl_idname,
                text="Restore shortcut",
                icon='ADD',
            )
            operator.keymap_name = name
            return

        status = cls._status(name, kc)
        km_item = status['item']
        if km_item is None:
            col.label(text=f"No hotkey entry found for {name}", icon='ERROR')
            operator = col.operator(
                PIESPLUS_OT_add_hotkey.bl_idname,
                text="Restore shortcut",
                icon='ADD',
            )
            operator.keymap_name = name
            return

        status_row = col.row(align=True)
        if status['conflicts']:
            status_row.alert = True
            status_row.label(
                text=f"Conflict ({len(status['conflicts'])})",
                icon='ERROR',
            )
        elif status['state'] == 'disabled':
            status_row.label(text="Disabled", icon='PAUSE')
        else:
            status_row.label(text="Active", icon='CHECKMARK')
        status_row.label(text=cls._item_to_string(km_item))

        col.context_pointer_set('keymap', km)
        col.context_pointer_set('keymap_item', km_item)
        if rna_keymap_ui is not None:
            try:
                rna_keymap_ui.draw_kmi([], kc, km, km_item, col, 0)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                col.label(text=cls._item_to_string(km_item))
        else:
            col.label(text=cls._item_to_string(km_item))

        operator = col.operator(
            PIESPLUS_OT_add_hotkey.bl_idname,
            text="Restore this shortcut",
            icon='FILE_REFRESH',
        )
        operator.keymap_name = name


    @staticmethod
    def draw_keymap_items(wm, layout):
        kc = wm.keyconfigs.user
        addon_kc = wm.keyconfigs.addon
        for name, items in PIESPLUS_addon_keymaps._keymaps.items():
            if not items or items[0] not in {'wm.call_menu', 'wm.call_menu_pie'}:
                continue
            box = layout.box()
            box.label(text=name, icon='KEYINGSET')
            km, user_kmi = PIESPLUS_addon_keymaps.find_keymap_item(kc, name)
            display_kc = kc
            if user_kmi is None and addon_kc is not None:
                km = addon_kc.keymaps.get(items[2])
                display_kc = addon_kc
            PIESPLUS_addon_keymaps.get_hotkey_entry_item(name, display_kc, km, box.column())


class PIESPLUS_OT_add_hotkey(Operator):
    bl_idname = "pies_plus.add_hotkey"
    bl_label = "Restore Shortcut"
    bl_description = "Restore only this Pie Menus Plus shortcut without resetting the whole Blender keymap"
    bl_options = {'REGISTER', 'INTERNAL'}

    keymap_name: StringProperty()
    km_name: StringProperty()

    def execute(self, context):
        keymap_name = self.keymap_name or self.km_name
        if PIESPLUS_addon_keymaps.restore_hotkey(keymap_name, context.window_manager):
            context.preferences.is_dirty = True
            self.report({'INFO'}, f"Restored shortcut: {keymap_name}")
            return {'FINISHED'}
        self.report({'WARNING'}, f"Could not restore shortcut: {keymap_name}")
        return {'CANCELLED'}


class PIESPLUS_OT_restore_all_hotkeys(Operator):
    bl_idname = "pies_plus.restore_all_hotkeys"
    bl_label = "Restore Pie Menu Shortcuts"
    bl_description = "Restore Pie Menus Plus shortcuts without resetting unrelated Blender keymaps"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        restored = PIESPLUS_addon_keymaps.restore_all_hotkeys(context.window_manager)
        context.preferences.is_dirty = True
        self.report({'INFO'}, f"Restored {restored} Pie Menus Plus shortcuts")
        return {'FINISHED'}


class PIESPLUS_OT_open_keymap_editor(Operator):
    bl_idname = "pies_plus.open_keymap_editor"
    bl_label = "Open Blender Keymap Editor"
    bl_description = "Open Blender's full keymap editor for conflict resolution and advanced editing"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        context.preferences.active_section = 'KEYMAP'
        return {'FINISHED'}


class PIESPLUS_keymap_profile(PropertyGroup):
    name: StringProperty(name="Profile Name")
    data: StringProperty(name="Profile Data", maxlen=65535, options={'HIDDEN'})


class PIESPLUS_OT_save_keymap_profile(Operator):
    bl_idname = "pies_plus.save_keymap_profile"
    bl_label = "Save Keymap Profile"
    bl_description = "Save the current Pie Menus Plus shortcuts as a reusable profile"
    bl_options = {'REGISTER', 'INTERNAL'}

    profile_name: StringProperty(name="Profile Name", default="My Profile")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, _context):
        self.layout.prop(self, 'profile_name')

    def execute(self, context):
        profile_name = self.profile_name.strip()
        if not profile_name:
            self.report({'WARNING'}, "Enter a profile name")
            return {'CANCELLED'}

        prefs = get_addon_preferences()
        payload = json.dumps(
            PIESPLUS_addon_keymaps.capture_profile(context.window_manager),
            separators=(',', ':'),
        )
        profile = next(
            (item for item in prefs.keymap_profiles if item.name == profile_name),
            None,
        )
        if profile is None:
            profile = prefs.keymap_profiles.add()
            profile.name = profile_name
        profile.data = payload
        context.preferences.is_dirty = True
        self.report({'INFO'}, f"Saved keymap profile: {profile_name}")
        return {'FINISHED'}


class PIESPLUS_OT_load_keymap_profile(Operator):
    bl_idname = "pies_plus.load_keymap_profile"
    bl_label = "Load Keymap Profile"
    bl_description = "Apply a saved Pie Menus Plus keymap profile"
    bl_options = {'REGISTER', 'INTERNAL'}

    profile_index: IntProperty(min=0)

    def execute(self, context):
        prefs = get_addon_preferences()
        if self.profile_index >= len(prefs.keymap_profiles):
            self.report({'WARNING'}, "Keymap profile no longer exists")
            return {'CANCELLED'}

        profile = prefs.keymap_profiles[self.profile_index]
        try:
            payload = json.loads(profile.data)
        except (TypeError, ValueError, json.JSONDecodeError):
            self.report({'WARNING'}, f"Could not read keymap profile: {profile.name}")
            return {'CANCELLED'}

        applied = PIESPLUS_addon_keymaps.apply_profile(payload, context.window_manager)
        context.preferences.is_dirty = True
        self.report({'INFO'}, f"Loaded {profile.name} ({applied} shortcuts)")
        return {'FINISHED'}


class PIESPLUS_OT_delete_keymap_profile(Operator):
    bl_idname = "pies_plus.delete_keymap_profile"
    bl_label = "Delete Keymap Profile"
    bl_description = "Delete a saved Pie Menus Plus keymap profile"
    bl_options = {'REGISTER', 'INTERNAL'}

    profile_index: IntProperty(min=0)

    def execute(self, context):
        prefs = get_addon_preferences()
        if self.profile_index >= len(prefs.keymap_profiles):
            return {'CANCELLED'}
        name = prefs.keymap_profiles[self.profile_index].name
        prefs.keymap_profiles.remove(self.profile_index)
        context.preferences.is_dirty = True
        self.report({'INFO'}, f"Deleted keymap profile: {name}")
        return {'FINISHED'}


##################################
# Preferences
##################################


class PIESPLUS_MT_addon_prefs(AddonPreferences):
    bl_idname = __package__

    keymap_profiles: CollectionProperty(type=PIESPLUS_keymap_profile)

    tabs: EnumProperty(
        items=(
            ('general', "General", "Information & Settings"),
            ('keymaps', "Keymaps", "Keymap Customizing")
        )
    )

    # Select Tool Prefs

    default_tool_pref: EnumProperty(
        items=(
            ('builtin.select', "Tweak", "Tweak"),
            ('builtin.select_box', "Box", "Box Select"),
            ('builtin.select_circle', "Circle", "Circle Select"),
            ('builtin.select_lasso', "Lasso", "Lasso Select")
        )
    )

    # Shading Prefs
    auto_smooth_flat_pref: BoolProperty(
        description="Automatically set objects that have Auto Smooth+ removed to Shade Flat"
    )

    # Quick FWN Prefs
    fwn_keep_sharps_pref: BoolProperty(
        description="Toggles whether the FWN Modifier accounts for Sharps on each mesh",
        default=True
    )
    fwn_weight_value_pref: IntProperty(
        name="Weight",
        default=100,
        min=1,
        max=100
    )
    fwn_face_influence_pref: BoolProperty(
        description="Use influence of face for FWN"
    )

    # Snapping Prefs
    auto_enable_snap_pref: BoolProperty(
        description="Automatically enables snapping when you change any settings within the pie",
        default=True
    )

    # Origin / Cursor Prefs
    auto_enable_abs_grid_snap_pref: BoolProperty(
        description="Automatically enables Absolute Grid Snap when you switch to incremental snapping within the pie"
    )
    reset_3d_cursor_rot_pref: BoolProperty(
        description="Automatically reset 3D Cursor rotation when resetting the translation within the pie",
        default=True
    )

    # Edit Origin Prefs
    face_center_snap_pref: BoolProperty(
        description="Allows for snapping directly to the center of any face on the object being edited (WARNING: This operation can be very slow in bigger scenes)"
    )

    # Custom Sculpt Brushes (Blender 4.2+)
    custom_sculpt_brush_1: StringProperty(
        name="Brush 1 (Left)",
        description="Asset path for brush 1 (e.g., Brushes/mesh_sculpt/Draw)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[1]
    )
    custom_sculpt_brush_2: StringProperty(
        name="Brush 2 (Right)",
        description="Asset path for brush 2 (e.g., Brushes/mesh_sculpt/Blob)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[2]
    )
    custom_sculpt_brush_3: StringProperty(
        name="Brush 3 (Bottom)",
        description="Asset path for brush 3 (e.g., Brushes/mesh_sculpt/Clay)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[3]
    )
    custom_sculpt_brush_4: StringProperty(
        name="Brush 4 (Top)",
        description="Asset path for brush 4 (e.g., Brushes/mesh_sculpt/Clay Strips)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[4]
    )
    custom_sculpt_brush_5: StringProperty(
        name="Brush 5 (Top-Left)",
        description="Asset path for brush 5 (e.g., Brushes/mesh_sculpt/Inflate)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[5]
    )
    custom_sculpt_brush_6: StringProperty(
        name="Brush 6 (Top-Right)",
        description="Asset path for brush 6 (e.g., Brushes/mesh_sculpt/Smooth)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[6]
    )
    custom_sculpt_brush_7: StringProperty(
        name="Brush 7 (Bottom-Left)",
        description="Asset path for brush 7 (e.g., Brushes/mesh_sculpt/Crease)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[7]
    )
    custom_sculpt_brush_8: StringProperty(
        name="Brush 8 (Bottom-Right)",
        description="Asset path for brush 8 (e.g., Brushes/mesh_sculpt/Flatten)",
        default=DEFAULT_CUSTOM_SCULPT_BRUSHES[8]
    )

    timeline_scrub: PointerProperty(type=PIESPLUS_timeline_settings)

    # UI / UX preferences
    pie_theme: EnumProperty(
        name="Pie Menu Theme",
        items=PIE_THEME_ITEMS,
        default="NATIVE",
        description=(
            "Tune pie menu spacing, label presentation, and status emphasis; "
            "Blender controls the native pie background colors"
        ),
    )
    pie_label_mode: EnumProperty(
        name="Label Mode",
        items=PIE_LABEL_MODE_ITEMS,
        default="FULL",
    )
    context_filtering: BoolProperty(
        name="Context-aware Menu Filtering",
        default=True,
        description=(
            "Hide pie menus and configurable entries that cannot be useful "
            "in the current mode, selection, or editor"
        ),
    )
    show_unavailable_actions: BoolProperty(
        name="Explain Unavailable Actions",
        default=False,
        description=(
            "Show disabled explanations in place of actions that are empty or "
            "not available in the current context"
        ),
    )
    show_sculpt_brush_previews: BoolProperty(
        name="Show Sculpt Brush Thumbnails",
        default=True,
        description=(
            "Use loaded Blender brush preview thumbnails in the sculpt pie "
            "when available"
        ),
    )

    # Selection Prefs
    invert_selection_pref: BoolProperty(
        description="Only deselect all objects if all object are selected (versus deselecting if any selection is made)"
    )
    frame_selected_pref: BoolProperty(
        default=True,
        description="Also frame the selected object when isolating"
    )

    # Context Mode Prefs
    simple_context_mode_pref: BoolProperty(
        description="A simple version of the context mode pie, which removes xray and overlay toggle (in case you keep using it on accident)"
    )
    preserve_uv_selection_pref: BoolProperty(
        description="Selects all faces when you leave UV Sync so you don't need to select the mesh again as you would normally"
    )
    sculptors_haven_pref: BoolProperty(
        description="Move the sculpt mode button to the main array of context mode operators, so that you can quickly switch between the modes"
    )

    # Debug Prefs
    debug_context_logging: BoolProperty(
        name="Enable Context Logging",
        description="Log context member access for debugging",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()

        row = layout.row()
        row.prop(self, "tabs", expand=True)

        # Information
        if self.tabs == 'general':
            col = layout.column(align = True)
            box = col.box()
            box.scale_y = .9
            box.label(text="ACTIVE TOOLS")
            row = col.row()
            row.scale_x = 1.25
            row.label(text="Default Selection Tool")
            row.prop(self, "default_tool_pref", expand=True)

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="ORIGIN / CURSOR")
            col.prop(self, "face_center_snap_pref", text="[EXPERIMENTAL] Edit Origin Tool Snapping to Center of Faces")
            col.prop(self, "reset_3d_cursor_rot_pref", text="Reset 3D Cursor Rotation when Resetting Location")

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="SELECT MODE")
            col.prop(self, "preserve_uv_selection_pref", text="Select Entire Mesh in 3D View when Exiting UV Sync Mode")
            col.prop(self, "simple_context_mode_pref", text="Use Simple Select Mode Pie")
            col.prop(self, "sculptors_haven_pref", text="Add Sculpt Mode Button to Main Selection")

            col = layout.column(align=True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="OPTIONAL ADD-ONS")
            box.label(text="Status is detected dynamically from Blender's current operators")
            for status in dependency_statuses():
                row = box.row(align=True)
                row.alert = not status.available
                row.label(
                    text=status.spec.label,
                    icon='CHECKMARK' if status.available else 'ERROR',
                )
                row.label(text=status.state_label)
                if not status.available:
                    detail = box.row()
                    detail.label(text=status.message)

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="SELECTION")
            col.prop(self, "invert_selection_pref", text="Invert Selection Toggle")
            col.prop(self, "frame_selected_pref", text="Isolate & Frame Selected")

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="SHADING")
            col.prop(self, "auto_smooth_flat_pref", text="Shade Objects Flat when Auto Smooth+ is Removed")
            col.separator()
            row = col.row()
            row.label(text="Quick FWN Weight")
            row.scale_x = 4
            row.prop(self, "fwn_weight_value_pref")
            row = col.row()
            row.prop(self, "fwn_keep_sharps_pref", text="FWN Keep Sharps")
            row.prop(self, "fwn_face_influence_pref", text="FWN Face Influence")

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="SNAPPING")
            col.prop(self, "auto_enable_snap_pref", text="Enable Snapping when Changing Snap Pie Settings")
            col.prop(self, "auto_enable_abs_grid_snap_pref", text="Enable Absolute Grid Snap when Turning on Incremental Snapping")

            col = layout.column(align=True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="UI / UX", icon='PREFERENCES')
            box.label(text="Presentation, context filtering, and sculpt-pie readability")

            row = box.row(align=True)
            row.prop(self, "pie_theme", text="Theme")
            row.prop(self, "pie_label_mode", text="Labels")
            box.prop(self, "context_filtering")
            box.prop(self, "show_unavailable_actions")
            box.prop(self, "show_sculpt_brush_previews")
            box.label(
                text="Native Blender pie background colors remain unchanged",
                icon='INFO',
            )
            box.operator(
                'pies_plus.show_ui_ux_preview',
                text="Preview & Edit Sculpt Pie",
                icon='VIEWZOOM',
            )

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="DEBUG")
            col.prop(self, "debug_context_logging", text="Enable Context Logging")

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.scale_y = .9
            box.label(text="UI")

            view = context.preferences.view

            col = col.column()
            col.label(text = "Animation Timeout Recommended = 0        (Removes Animations)")
            col.prop(view, "pie_animation_timeout")
            col.label(text = "Radius Recommended = 125        (Fixes UI Clipping)")
            col.prop(view, "pie_menu_radius")
            col.separator(factor = 1.5)
            col.prop(view, "pie_tap_timeout")
            col.prop(view, "pie_initial_timeout")
            col.prop(view, "pie_menu_threshold")
            col.prop(view, "pie_menu_confirm")

        # Keymapping
        if self.tabs == 'keymaps':
            wm = context.window_manager

            summary = PIESPLUS_addon_keymaps.get_summary(wm)
            health = layout.box()
            health.label(text="KEYMAP HEALTH", icon='KEYINGSET')
            row = health.row(align=True)
            row.label(text=f"{summary['active']}/{summary['total']} active", icon='CHECKMARK')
            row.label(text=f"{summary['conflicts']} conflicts", icon='ERROR' if summary['conflicts'] else 'CHECKMARK')
            if summary['missing']:
                row.label(text=f"{summary['missing']} missing", icon='QUESTION')
            if summary['disabled']:
                row.label(text=f"{summary['disabled']} disabled", icon='PAUSE')

            actions = health.row(align=True)
            actions.operator(
                'pies_plus.restore_all_hotkeys',
                text="Restore Pie Shortcuts",
                icon='FILE_REFRESH',
            )
            actions.operator(
                'pies_plus.open_keymap_editor',
                text="Open Blender Keymap Editor",
                icon='PREFERENCES',
            )

            conflict_statuses = [
                status for status in PIESPLUS_addon_keymaps.get_statuses(wm)
                if status['conflicts']
            ]
            if conflict_statuses:
                conflicts = health.box()
                conflicts.label(text="Conflicts detected in the active user keymap", icon='ERROR')
                for status in conflict_statuses:
                    row = conflicts.row(align=True)
                    row.alert = True
                    row.label(text=status['name'], icon='ERROR')
                    row.label(text=status['shortcut'])
                    row.label(
                        text=', '.join(
                            getattr(item, 'idname', 'Unknown operator')
                            for item in status['conflicts'][:3]
                        ),
                    )
                conflicts.label(
                    text="Edit the highlighted entry below or use Blender's Keymap Editor to resolve it.",
                    icon='INFO',
                )
            else:
                health.label(text="No active shortcut conflicts detected", icon='CHECKMARK')

            profiles = layout.box()
            profiles.label(text="KEYMAP PROFILES", icon='PRESET')
            profiles.label(text="Profiles store Pie Menus Plus shortcuts only; unrelated Blender shortcuts are untouched")
            profiles.operator(
                'pies_plus.save_keymap_profile',
                text="Save Current Profile",
                icon='ADD',
            )
            if self.keymap_profiles:
                for index, profile in enumerate(self.keymap_profiles):
                    row = profiles.row(align=True)
                    row.label(text=profile.name, icon='FILE_BLEND')
                    load = row.operator(
                        'pies_plus.load_keymap_profile',
                        text="Load",
                        icon='IMPORT',
                    )
                    load.profile_index = index
                    delete = row.operator(
                        'pies_plus.delete_keymap_profile',
                        text="",
                        icon='X',
                    )
                    delete.profile_index = index
            else:
                profiles.label(text="No saved profiles yet")

            PIESPLUS_addon_keymaps.draw_keymap_items(wm, layout)

            col = layout.column(align = True)
            col.separator()
            box = col.box()
            box.label(text="CUSTOM SCULPT BRUSHES", icon='SCULPTMODE_HLT')
            box.label(text="Assign Essentials brushes to the eight sculpt pie slots")
            box.label(text="Use Choose for known brushes, or enter an asset path manually")

            preset_row = box.row(align=True)
            preset_row.label(text="Presets:")
            for preset, label in (
                ('BALANCED', 'Balanced'),
                ('DETAILING', 'Detailing'),
                ('CHARACTER', 'Character'),
            ):
                operator = preset_row.operator(
                    'pies_plus.set_custom_sculpt_brush_preset',
                    text=label,
                    icon='PRESET',
                )
                operator.preset = preset

            for slot, direction, brush_name in CUSTOM_SCULPT_BRUSH_SLOTS:
                row = box.row(align=True)
                row.label(text=f"{slot}. {direction}", icon='BRUSH_DATA')
                row.prop(
                    self,
                    custom_sculpt_brush_property(slot),
                    text='',
                )
                operator = row.operator(
                    'pies_plus.choose_custom_sculpt_brush',
                    text='Choose',
                )
                operator.slot = slot
                operator = row.operator(
                    'pies_plus.activate_custom_sculpt_brush_slot',
                    text='',
                    icon='CHECKMARK',
                )
                operator.slot = slot
                operator = row.operator(
                    'pies_plus.reset_custom_sculpt_brush_slot',
                    text='',
                    icon='X',
                )
                operator.slot = slot

            footer = box.row(align=True)
            footer.label(text="Activate tests the selected slot in the current Blender context")
            footer.operator(
                'pies_plus.reset_custom_sculpt_brushes',
                text='Reset All',
                icon='FILE_REFRESH',
            )

            col = layout.column(align=True)
            col.separator()
            box = col.box()
            draw_timeline_scrub_preferences(self.timeline_scrub, box)


##################################
# REGISTRATION
##################################


classes = (
    PIESPLUS_timeline_settings,
    PIESPLUS_keymap_profile,
    PIESPLUS_property_group,
    PIESPLUS_OT_add_hotkey,
    PIESPLUS_OT_restore_all_hotkeys,
    PIESPLUS_OT_open_keymap_editor,
    PIESPLUS_OT_save_keymap_profile,
    PIESPLUS_OT_load_keymap_profile,
    PIESPLUS_OT_delete_keymap_profile,
    PIESPLUS_MT_addon_prefs,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    Scene.pies_plus = PointerProperty(type = PIESPLUS_property_group)

    PIESPLUS_addon_keymaps.new_keymap('Separate', 'wm.call_menu', 'PIESPLUS_MT_separate',
                                      'Mesh', 'EMPTY', 'WINDOW',
                                      'P', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Active Tools', 'wm.call_menu_pie', 'PIESPLUS_MT_active_tools',
                                      '3D View', 'VIEW_3D', 'WINDOW',
                                      'W', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Sculpt Tools', 'wm.call_menu_pie', 'PIESPLUS_MT_sculpt',
                                      'Sculpt', 'EMPTY', 'WINDOW',
                                      'W', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Align Pie (Object Mode)', 'wm.call_menu_pie', 'PIESPLUS_MT_align',
                                      'Mesh', 'EMPTY', 'WINDOW',
                                      'X', 'PRESS', False, False, True)

    PIESPLUS_addon_keymaps.new_keymap('Animation Playback', 'wm.call_menu_pie', 'PIESPLUS_MT_animation',
                                      'Object Non-modal', 'EMPTY', 'WINDOW',
                                      'SPACE', 'PRESS', False, True, False)

    PIESPLUS_addon_keymaps.new_keymap('Animation Keyframing', 'wm.call_menu_pie', 'PIESPLUS_MT_keyframing',
                                      'Object Non-modal', 'EMPTY', 'WINDOW',
                                      'SPACE', 'PRESS', False, False, True)

    PIESPLUS_addon_keymaps.new_keymap('Bool Tool Pie (Object Mode)', 'wm.call_menu_pie', 'PIESPLUS_MT_booltool',
                                      'Object Mode', 'EMPTY', 'WINDOW',
                                      'C', 'PRESS', False, False, True)

    PIESPLUS_addon_keymaps.new_keymap('EdgeFlow Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_edgeflow',
                                      'Mesh', 'EMPTY', 'WINDOW',
                                      'F', 'PRESS', False, True, True)

    PIESPLUS_addon_keymaps.new_keymap('Delete Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_delete',
                                      'Mesh', 'EMPTY', 'WINDOW',
                                      'X', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Delete Pie (Curve)', 'wm.call_menu_pie', 'PIESPLUS_MT_delete_curve',
                                      'Curve', 'EMPTY', 'WINDOW',
                                      'X', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('LoopTools Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_looptools',
                                      'Mesh', 'EMPTY', 'WINDOW',
                                      'Q', 'PRESS', False, True, False)

    PIESPLUS_addon_keymaps.new_keymap('Origin / Cursor Change Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_origin_pivot',
                                      '3D View', 'VIEW_3D', 'WINDOW',
                                      'S', 'PRESS', False, True, False)

    PIESPLUS_addon_keymaps.new_keymap('Proportional Editing Pie (Object Mode)', 'wm.call_menu_pie', 'PIESPLUS_MT_proportional_object_mode',
                                      'Object Mode', 'EMPTY', 'WINDOW',
                                      'O', 'PRESS', False, True, False)

    PIESPLUS_addon_keymaps.new_keymap('Proportional Editing Pie (Edit Mode)', 'wm.call_menu_pie', 'PIESPLUS_MT_proportional_edit_mode',
                                      'Mesh', 'EMPTY', 'WINDOW',
                                      'O', 'PRESS', False, True, False)

    PIESPLUS_addon_keymaps.new_keymap('Save Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_save',
                                      '3D View', 'VIEW_3D', 'WINDOW',
                                      'S', 'PRESS', True, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Select Mode Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_modes',
                                      'Object Non-modal', 'EMPTY', 'WINDOW',
                                      'TAB', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Select Mode Pie (UV)', 'wm.call_menu_pie', 'PIESPLUS_MT_UV_modes',
                                      'UV Editor', 'EMPTY', 'WINDOW',
                                      'TAB', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Selection Pie (Object Mode)', 'wm.call_menu_pie', 'PIESPLUS_MT_selection_object_mode',
                                      'Object Mode', 'EMPTY', 'WINDOW',
                                      'A', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Selection Pie (Edit Mode)', 'wm.call_menu_pie', 'PIESPLUS_MT_selection_edit_mode',
                                      'Mesh', 'EMPTY', 'WINDOW',
                                      'A', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Shading Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_shading',
                                      '3D View', 'VIEW_3D', 'WINDOW',
                                      'Z', 'PRESS', False, False, False)

    PIESPLUS_addon_keymaps.new_keymap('Snapping Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_snapping',
                                      '3D View', 'VIEW_3D', 'WINDOW',
                                      'TAB', 'PRESS', False, True, False)

    PIESPLUS_addon_keymaps.new_keymap('Snapping Pie (UV)', 'wm.call_menu_pie', 'PIESPLUS_MT_UV_snapping',
                                      'UV Editor', 'EMPTY', 'WINDOW',
                                      'TAB', 'PRESS', False, True, False)

    PIESPLUS_addon_keymaps.new_keymap('Transforms Pie', 'wm.call_menu_pie', 'PIESPLUS_MT_transforms',
                                      'Object Mode', 'EMPTY', 'WINDOW',
                                      'A', 'PRESS', True, False, False)

    PIESPLUS_addon_keymaps.register_keymaps()  # Keymap Setup


def unregister():
    PIESPLUS_addon_keymaps.unregister_keymaps()  # Keymap Cleanup

    if hasattr(Scene, 'pies_plus'):
        del Scene.pies_plus

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
