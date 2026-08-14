# SPDX-FileCopyrightText: 2021-2023 Blender Foundation
#
# SPDX-License-Identifier: GPL-3.0-or-later

'''Based on viewport_timeline_scrub standalone addon - Samuel Bernou'''

from ..utils import get_addon_preferences

import math

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader

from bpy.props import (BoolProperty,
                       StringProperty,
                       IntProperty,
                       FloatVectorProperty,
                       EnumProperty)


def get_timeline_preferences():
    return get_addon_preferences().timeline_scrub


def nearest(values, value) -> int:
    """Return the closest frame value without requiring an external package."""
    return int(min(values, key=lambda candidate: abs(candidate - value)))


def _is_grease_pencil_object(obj) -> bool:
    return getattr(obj, 'type', None) in {'GREASEPENCIL', 'GPENCIL'}


def _action_fcurves(anim_data):
    action = getattr(anim_data, 'action', None)
    if action is None:
        return ()

    if bpy.app.version < (5, 0, 0):
        return getattr(action, 'fcurves', ())

    slot = getattr(anim_data, 'action_slot', None)
    if slot is not None:
        action_data = getattr(slot, 'id_data', action)
        layers = getattr(action_data, 'layers', ())
        if layers:
            strips = getattr(layers[0], 'strips', ())
            if strips:
                try:
                    channelbag = strips[0].channelbag(slot)
                except (AttributeError, RuntimeError, TypeError):
                    channelbag = None
                if channelbag is not None:
                    return getattr(channelbag, 'fcurves', ())

    return getattr(action, 'fcurves', ())


def _object_keyframes(obj):
    anim_data = getattr(obj, 'animation_data', None)
    if anim_data is None:
        return ()
    return (
        keyframe.co.x
        for fcurve in _action_fcurves(anim_data)
        for keyframe in getattr(fcurve, 'keyframe_points', ())
    )


def _append_frame_values(target, values):
    """Append finite frame values without introducing duplicates."""
    known = set(target)
    for value in values:
        try:
            frame = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(frame) and frame not in known:
            target.append(frame)
            known.add(frame)


def _grease_pencil_keyframes(obj, layer_target):
    """Return Grease Pencil drawing frames using the current layer context."""
    data = getattr(obj, 'data', None)
    layers = getattr(data, 'layers', None)
    if layers is None:
        return ()

    if layer_target == 'ALL':
        return (
            frame.frame_number
            for layer in layers
            for frame in getattr(layer, 'frames', ())
        )

    frames = []
    layer_groups = getattr(data, 'layer_groups', None)
    active_group = getattr(layer_groups, 'active', None)
    if active_group:
        frames.extend(
            frame.frame_number
            for layer in layers
            for frame in getattr(layer, 'frames', ())
            if getattr(layer, 'parent_group', None) == active_group
        )

    active_layer = getattr(layers, 'active', None)
    if active_layer:
        frames.extend(
            frame.frame_number
            for frame in getattr(active_layer, 'frames', ())
        )
    return frames


def _smart_objects(context, scope):
    """Return animation sources for Smart Scrub's selected scope."""
    if not context.space_data or context.space_data.type not in {'VIEW_3D', 'NODE_EDITOR'}:
        return ()

    active = getattr(context, 'active_object', None) or getattr(context, 'object', None)
    if scope == 'ACTIVE':
        return (active,) if active else ()

    if scope == 'SELECTED':
        objects = list(getattr(context, 'selected_objects', ()))
    else:
        objects = []
        for obj in getattr(getattr(context, 'view_layer', None), 'objects', ()):
            try:
                visible = obj.visible_get()
            except (AttributeError, RuntimeError):
                visible = not getattr(obj, 'hide_viewport', False)
            if visible:
                objects.append(obj)

    if active and active not in objects:
        objects.insert(0, active)
    return tuple(objects)


def _sequence_strip_bounds(scene):
    """Return strip boundaries across Blender's sequence collection names."""
    sequence_editor = getattr(scene, 'sequence_editor', None)
    if sequence_editor is None:
        return ()

    strips = getattr(sequence_editor, 'strips_all', None)
    if strips is None:
        strips = getattr(sequence_editor, 'sequences_all', ())

    bounds = []
    for strip in strips:
        start = getattr(strip, 'frame_final_start', None)
        end = getattr(strip, 'frame_final_end', None)
        if start is not None:
            bounds.append(start)
        if end is not None:
            bounds.append(end)
    return bounds


def _smart_target_frames(context, prefs):
    """Build one unified set of meaningful frames for Smart Scrub."""
    frames = []
    labels = []

    for obj in _smart_objects(context, prefs.smart_target_scope):
        if not _is_grease_pencil_object(obj) or prefs.evaluate_gp_obj_key:
            object_frames = list(_object_keyframes(obj))
            _append_frame_values(frames, object_frames)
            if object_frames:
                labels.append('Object Keys')

        if _is_grease_pencil_object(obj):
            gp_frames = _grease_pencil_keyframes(obj, prefs.gp_layer_target)
            before = len(frames)
            _append_frame_values(frames, gp_frames)
            if len(frames) != before:
                labels.append('Grease Pencil')

    if prefs.smart_include_markers:
        marker_frames = [marker.frame for marker in getattr(context.scene, 'timeline_markers', ())]
        before = len(frames)
        _append_frame_values(frames, marker_frames)
        if len(frames) != before:
            labels.append('Markers')

    if prefs.smart_include_strip_bounds and context.space_data:
        if context.space_data.type == 'SEQUENCE_EDITOR':
            strip_frames = _sequence_strip_bounds(context.scene)
            before = len(frames)
            _append_frame_values(frames, strip_frames)
            if len(frames) != before:
                labels.append('Strip Bounds')

    if not labels:
        labels.append('Frame Range')
    return sorted(frames), ' + '.join(dict.fromkeys(labels))


def _smart_snap_frame(raw_frame, targets, previous, radius):
    """Snap near a semantic target while keeping the cursor stable in its halo."""
    if not targets:
        return raw_frame, None

    candidate = nearest(targets, raw_frame)
    if previous is not None and abs(raw_frame - previous) <= radius + 1:
        return previous, previous
    if abs(raw_frame - candidate) <= radius:
        return candidate, candidate
    return raw_frame, None


def draw_callback_px(self, context):
    '''Draw callback use by modal to draw in viewport'''
    if context.area != self.current_area:
        return

    # text
    font_id = 0

    shader = gpu.shader.from_builtin('UNIFORM_COLOR') # initiate shader
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(1.0)

    # Draw HUD
    if self.use_hud_time_line:
        shader.bind()
        shader.uniform_float("color", self.color_timeline)
        self.batch_timeline.draw(shader)

    # Display keyframes
    if self.use_hud_keyframes and self.batch_keyframes:
        width = 3.0 if self.keyframe_aspect == 'LINE' else 1.0
        gpu.state.line_width_set(width)
        shader.bind()
        shader.uniform_float("color", self.color_timeline)
        self.batch_keyframes.draw(shader)

    # Show current frame line
    gpu.state.line_width_set(1.0)
    if self.use_hud_playhead:
        playhead = [(self.cursor_x, self.my + self.playhead_size/2),
                    (self.cursor_x, self.my - self.playhead_size/2)]
        batch = batch_for_shader(shader, 'LINES', {"pos": playhead})
        shader.bind()
        shader.uniform_float("color", self.color_playhead)
        batch.draw(shader)

    # restore opengl defaults
    gpu.state.blend_set('NONE')

    # Display current frame text
    blf.color(font_id, *self.color_text)
    if self.use_hud_frame_current:
        blf.position(font_id, self.mouse[0]+10, self.mouse[1]+10, 0)
        blf.size(font_id, 30 * (self.dpi / 72.0))
        blf.draw(font_id, f'{self.new_frame:.0f}')

    # Display frame offset text
    if self.use_hud_frame_offset:
        blf.position(font_id, self.mouse[0]+10,
                     self.mouse[1]+(40*self.ui_scale), 0)
        blf.size(font_id, 16 * (self.dpi / 72.0))
        sign = '+' if self.offset > 0 else ''
        blf.draw(font_id, f'{sign}{self.offset:.0f}')

    if self.smart_scrub and self.smart_show_status:
        blf.position(font_id, self.mouse[0]+10,
                     self.mouse[1]-(30*self.ui_scale), 0)
        blf.size(font_id, 13 * (self.dpi / 72.0))
        blf.draw(font_id, f'Smart: {self.smart_target_label}')


class PIESPLUS_OT_time_scrub(bpy.types.Operator):
    bl_idname = "pies_plus.timeline_scrub"
    bl_label = "Time scrub"
    bl_description = "Quick time scrubbing with a shortcut"
    bl_options = {"REGISTER", "INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not context.space_data:
            return False
        if context.space_data.type == 'NODE_EDITOR':
            # Triggered by the global "Grease Pencil" keymap
            return get_timeline_preferences().use_in_node_editor
        return context.space_data.type in ('VIEW_3D', 'SEQUENCE_EDITOR', 'CLIP_EDITOR')

    def invoke(self, context, event):
        prefs = get_timeline_preferences()

        self.current_area = context.area
        # Get the key that triggered the modal (Fallback to keycode if not called through a Press)
        self.key = event.type if event.value == 'PRESS' else prefs.keycode
        self.evaluate_gp_obj_key = prefs.evaluate_gp_obj_key
        self.always_snap = prefs.always_snap
        self.rolling_mode = prefs.rolling_mode
        self.hide_overlays = prefs.hide_overlays
        self.smart_scrub = prefs.smart_scrub
        self.smart_auto_snap = prefs.smart_auto_snap
        self.smart_snap_radius = prefs.smart_snap_radius
        self.smart_show_status = prefs.smart_show_status
        self.smart_snap_frame = None
        self.smart_target_label = ''

        self.dpi = context.preferences.system.dpi
        self.ui_scale = context.preferences.system.ui_scale
        # hud prefs
        self.color_timeline = prefs.color_timeline
        self.color_playhead = prefs.color_playhead
        self.color_text = prefs.color_playhead
        self.use_hud_time_line = prefs.use_hud_time_line
        self.use_hud_keyframes = prefs.use_hud_keyframes
        self.keyframe_aspect = prefs.keyframe_aspect
        self.use_hud_playhead = prefs.use_hud_playhead
        self.use_hud_frame_current = prefs.use_hud_frame_current
        self.use_hud_frame_offset = prefs.use_hud_frame_offset

        self.playhead_size = prefs.playhead_size
        self.lines_size = prefs.lines_size

        self.px_step = float(prefs.pixel_step)
        self.snap_on = False
        self.mouse = (event.mouse_region_x, event.mouse_region_y)
        self.init_mouse_x = self.cursor_x = event.mouse_region_x

        # self.init_mouse_y = event.mouse_region_y # only to display init frame text
        self.cancel_frame = self.init_frame = self.new_frame = context.scene.frame_current
        self.lock_range = context.scene.lock_frame_selection_to_range
        if context.scene.use_preview_range:
            self.f_start = context.scene.frame_preview_start
            self.f_end = context.scene.frame_preview_end
        else:
            self.f_start = context.scene.frame_start
            self.f_end = context.scene.frame_end

        if self.smart_scrub and prefs.smart_adaptive_sensitivity:
            frame_span = max(self.f_end - self.f_start, 1)
            area_width = max(getattr(context.area, 'width', 1), 1)
            self.px_step = min(self.px_step, max(1.0, area_width / frame_span))

        self.offset = 0
        self.pos = []

        # Snap control
        self.snap_ctrl = not prefs.use_ctrl
        self.snap_shift = not prefs.use_shift
        self.snap_alt = not prefs.use_alt
        self.snap_mouse_key = 'LEFTMOUSE' if self.key == 'RIGHTMOUSE' else 'RIGHTMOUSE'

        ob = context.object

        if context.space_data.type not in ('VIEW_3D', 'NODE_EDITOR'):
            ob = None  # do not consider any key

        if self.smart_scrub:
            self.pos, self.smart_target_label = _smart_target_frames(context, prefs)
            self.smart_positions = list(self.pos)
        elif ob:  # condition to allow empty scrubing
            if not _is_grease_pencil_object(ob) or self.evaluate_gp_obj_key:
                # Get object keyframe position
                self.pos += list(set(_object_keyframes(ob)))
                            ## (currently only on active object, using 'action.layers' would be fine).
                    
                    ## Expanded equivalent
                    # for fcu in fcurves:
                    #     for kf in fcu.keyframe_points:
                    #         if kf.co.x not in self.pos:
                    #             self.pos.append(kf.co.x)

            if _is_grease_pencil_object(ob):
                # Get GP frame position
                gpl = ob.data.layers
                if prefs.gp_layer_target == 'ALL':
                    all_frames = set(f.frame_number for l in gpl for f in l.frames)
                    self.pos += [n for n in sorted(all_frames) if n not in self.pos]

                else:
                    # 'ACTIVE': active layer keys, or keys of active group layers
                    layer_groups = getattr(ob.data, 'layer_groups', None)
                    group = getattr(layer_groups, 'active', None)
                    if group:
                        ## group is active (no active layer) -> consider keys of all layer in groups
                        group_frames = [
                            f.frame_number for l in gpl for f in l.frames
                            if getattr(l, 'parent_group', None) == group
                        ]
                        if group_frames:
                            self.pos += sorted(set(group_frames))
                        ## Consider all frame if layer is empty ?

                    layer = gpl.active
                    if layer:
                        for frame in layer.frames:
                            if frame.frame_number not in self.pos:
                                self.pos.append(frame.frame_number)

        if (not ob and not self.smart_scrub) or not self.pos:
            # Disable inverted behavior if no frame to snap
            self.always_snap = False
            if self.rolling_mode:
                self.report({'WARNING'}, 'No Keys to flip on')
                return {'CANCELLED'}

        if self.rolling_mode:
            if self.lock_range:
                # Trim before any index computation (out of range keys are not reachable)
                self.pos = [i for i in self.pos if self.f_start <= i <= self.f_end]
                if not self.pos:
                    self.report({'WARNING'}, 'No keys to flip on within frame range')
                    return {'CANCELLED'}
            # Sorted and cast to int list since it's going to work with indices
            self.pos = sorted([int(f) for f in self.pos])
            # Find and make current frame the "starting" frame (force snap)
            active_pos = [i for i, num in enumerate(self.pos) if num <= self.init_frame]
            if active_pos:
                self.init_index = active_pos[-1]
                self.init_frame = self.new_frame = self.pos[self.init_index]
            else:
                self.init_index = 0
                self.init_frame = self.new_frame = self.pos[0]

            # del active_pos
            self.index_limit = len(self.pos) - 1

        # Also snap on play bounds (sliced off for keyframe display)
        self.pos += [self.f_start, self.f_end]
        if self.smart_scrub:
            self.smart_positions = sorted(set(self.pos))

        # Disable Onion skin and other overlays
        self.active_space_data = context.space_data
        self.onion_skin = None
        self.show_overlays = None
        self.show_gizmo = None
        self.multi_frame = None
        if context.space_data.type == 'VIEW_3D':
            self.onion_skin = self.active_space_data.overlay.use_gpencil_onion_skin
            self.active_space_data.overlay.use_gpencil_onion_skin = False

            if self.hide_overlays:
                # Store overlays state and disable
                self.show_overlays = self.active_space_data.overlay.show_overlays
                self.show_gizmo = self.active_space_data.show_gizmo
                self.active_space_data.overlay.show_overlays = False
                self.active_space_data.show_gizmo = False


        if ob and _is_grease_pencil_object(ob):
            multi_frame = getattr(
                context.scene.tool_settings,
                'use_grease_pencil_multi_frame_editing',
                False,
            )
            if multi_frame:
                self.multi_frame = multi_frame
                context.scene.tool_settings.use_grease_pencil_multi_frame_editing = False

        self.hud = prefs.use_hud
        if not self.hud:
            ## Same as end settings when HUD is On
            if self.lock_range:
                self.pos = [i for i in self.pos if self.f_start <= i <= self.f_end]
            if self.rolling_mode:
                context.scene.frame_current = self.new_frame
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        # - HUD params
        width = context.area.width
        right = int((width - self.init_mouse_x) / self.px_step)
        left = int(self.init_mouse_x / self.px_step)

        hud_pos_x = []
        for i in range(1, left):
            hud_pos_x.append(self.init_mouse_x - i*self.px_step)
        for i in range(1, right):
            hud_pos_x.append(self.init_mouse_x + i*self.px_step)

        # - list of double coords

        init_height = 60
        frame_height = self.lines_size
        key_height = 14
        bound_h = key_height + 19
        bound_bracket_l = self.px_step/2

        self.my = my = event.mouse_region_y

        self.hud_lines = []

        if not self.rolling_mode:
            # frame marks
            for x in hud_pos_x:
                self.hud_lines.append((x, my - (frame_height/2)))
                self.hud_lines.append((x, my + (frame_height/2)))

        # init frame mark
        self.hud_lines += [(self.init_mouse_x, my - (init_height/2)),
                           (self.init_mouse_x, my + (init_height/2))]

        if not self.rolling_mode:
            # Add start/end boundary bracket to HUD
            start_x = self.init_mouse_x + \
                (self.f_start - self.init_frame) * self.px_step
            end_x = self.init_mouse_x + \
                (self.f_end - self.init_frame) * self.px_step

            # start
            up = (start_x, my - (bound_h/2))
            dn = (start_x, my + (bound_h/2))
            self.hud_lines.append(up)
            self.hud_lines.append(dn)

            self.hud_lines.append(up)
            self.hud_lines.append((up[0] + bound_bracket_l, up[1]))
            self.hud_lines.append(dn)
            self.hud_lines.append((dn[0] + bound_bracket_l, dn[1]))

            # end
            up = (end_x, my - (bound_h/2))
            dn = (end_x, my + (bound_h/2))
            self.hud_lines.append(up)
            self.hud_lines.append(dn)

            self.hud_lines.append(up)
            self.hud_lines.append((up[0] - bound_bracket_l, up[1]))
            self.hud_lines.append(dn)
            self.hud_lines.append((dn[0] - bound_bracket_l, dn[1]))

        # Horizontal line
        self.hud_lines += [(0, my), (width, my)]

        # Prepare batchs to draw static parts
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')  # initiate shader
        self.batch_timeline = batch_for_shader(
            shader, 'LINES', {"pos": self.hud_lines})

        if self.rolling_mode:
            current_id = self.pos.index(self.new_frame)
            # Add init_frame to "cancel" it in later UI code
            ui_key_pos = [i - current_id + self.init_frame for i, _f in enumerate(self.pos[:-2])]
        else:
            ui_key_pos = self.pos[:-2]

        self.batch_keyframes = None # init if there are no keyframe to draw
        if ui_key_pos:
            if self.keyframe_aspect == 'LINE':
                key_lines = []
                # Slice off position of start/end frame added last (in list for snapping)
                for i in ui_key_pos:
                    key_lines.append(
                        (self.init_mouse_x + ((i-self.init_frame) * self.px_step), my - (key_height/2)))
                    key_lines.append(
                        (self.init_mouse_x + ((i-self.init_frame) * self.px_step), my + (key_height/2)))

                self.batch_keyframes = batch_for_shader(
                    shader, 'LINES', {"pos": key_lines})

            else:
                # diamond and square
                # keysize5 for square, 4 or 6 for diamond
                keysize = 6 if self.keyframe_aspect == 'DIAMOND' else 5
                upper = 0

                shaped_key = []
                indices = []
                idx_offset = 0
                for i in ui_key_pos:
                    center = self.init_mouse_x + ((i-self.init_frame)*self.px_step)
                    if self.keyframe_aspect == 'DIAMOND':
                        # +1 on x is to correct pixel alignment
                        shaped_key += [(center-keysize, my+upper),
                                    (center+1, my+keysize+upper),
                                    (center+keysize, my+upper),
                                    (center+1, my-keysize+upper)]

                    elif self.keyframe_aspect == 'SQUARE':
                        shaped_key += [(center-keysize+1, my-keysize+upper),
                                    (center-keysize+1, my+keysize+upper),
                                    (center+keysize, my+keysize+upper),
                                    (center+keysize, my-keysize+upper)]

                    indices += [(0+idx_offset, 1+idx_offset, 2+idx_offset),
                                (0+idx_offset, 2+idx_offset, 3+idx_offset)]
                    idx_offset += 4

                self.batch_keyframes = batch_for_shader(
                    shader, 'TRIS', {"pos": shaped_key}, indices=indices)

        # Trim snapping list of frame outside of frame range if range lock activated
        # (after drawing batch so those are still showed)
        if self.lock_range:
            self.pos = [i for i in self.pos if self.f_start <= i <= self.f_end]
            if self.smart_scrub:
                self.smart_positions = [
                    i for i in self.smart_positions
                    if self.f_start <= i <= self.f_end
                ]

        if self.rolling_mode:
            context.scene.frame_current = self.new_frame

        args = (self, context)
        self.viewtype = None
        self.spacetype = 'WINDOW'  # is PREVIEW for VSE, needed for handler remove

        if context.space_data.type == 'VIEW_3D':
            self.viewtype = bpy.types.SpaceView3D
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_px, args, 'WINDOW', 'POST_PIXEL')

        elif context.space_data.type == 'SEQUENCE_EDITOR':
            self.viewtype = bpy.types.SpaceSequenceEditor
            self.spacetype = 'PREVIEW'
            self._handle = bpy.types.SpaceSequenceEditor.draw_handler_add(
                draw_callback_px, args, 'PREVIEW', 'POST_PIXEL')

        elif context.space_data.type == 'CLIP_EDITOR':
            self.viewtype = bpy.types.SpaceClipEditor
            self._handle = bpy.types.SpaceClipEditor.draw_handler_add(
                draw_callback_px, args, 'WINDOW', 'POST_PIXEL')

        elif context.space_data.type == 'NODE_EDITOR':
            self.viewtype = bpy.types.SpaceNodeEditor
            self._handle = bpy.types.SpaceNodeEditor.draw_handler_add(
                draw_callback_px, args, 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _exit_modal(self, context):
        if self.onion_skin is not None:
            self.active_space_data.overlay.use_gpencil_onion_skin = self.onion_skin
        if self.show_overlays is not None:
            self.active_space_data.overlay.show_overlays = self.show_overlays
        if self.show_gizmo is not None:
            self.active_space_data.show_gizmo = self.show_gizmo
        if self.multi_frame is not None:
            context.scene.tool_settings.use_grease_pencil_multi_frame_editing = self.multi_frame
        if self.hud and self.viewtype:
            self.viewtype.draw_handler_remove(self._handle, self.spacetype)
            context.area.tag_redraw()

    def modal(self, context, event):

        if event.type == 'MOUSEMOVE':
            # - calculate frame offset from pixel offset
            # - get mouse.x and add it to initial frame num
            self.mouse = (event.mouse_region_x, event.mouse_region_y)

            px_offset = (event.mouse_region_x - self.init_mouse_x)
            self.offset = int(px_offset / self.px_step)
            raw_frame = self.init_frame + self.offset
            self.new_frame = raw_frame

            if self.rolling_mode:
                # Frame Flipping mode (equidistant scrub snap)
                self.index = self.init_index + self.offset
                # clamp to possible index range
                self.index = min(max(self.index, 0), self.index_limit)
                self.new_frame = self.pos[self.index]
                context.scene.frame_current = self.new_frame
                self.cursor_x = self.init_mouse_x + (self.offset * self.px_step)

            else:
                mod_snap = False
                if self.snap_ctrl and event.ctrl:
                    mod_snap = True
                if self.snap_shift and event.shift:
                    mod_snap = True
                if self.snap_alt and event.alt:
                    mod_snap = True

                ## Snapping
                if self.always_snap:
                    # inverted snapping behavior
                    if not self.snap_on and not mod_snap:
                        self.new_frame = nearest(self.pos, self.new_frame)
                else:
                    if self.snap_on or mod_snap:
                        self.new_frame = nearest(self.pos, self.new_frame)

                if self.smart_scrub and self.smart_auto_snap:
                    smart_snap_allowed = (
                        not self.snap_on
                        and (not self.always_snap or mod_snap)
                    )
                    if smart_snap_allowed:
                        self.new_frame, self.smart_snap_frame = _smart_snap_frame(
                            raw_frame,
                            self.smart_positions,
                            self.smart_snap_frame,
                            self.smart_snap_radius,
                        )
                    else:
                        self.smart_snap_frame = None

                # frame range restriction
                if self.lock_range:
                    if self.new_frame < self.f_start:
                        self.new_frame = self.f_start
                    elif self.new_frame > self.f_end:
                        self.new_frame = self.f_end

                # context.scene.frame_set(self.new_frame)
                context.scene.frame_current = self.new_frame

                # - recalculate offset to snap cursor to frame
                self.offset = self.new_frame - self.init_frame

                # - calculate cursor pixel position from frame offset
                self.cursor_x = self.init_mouse_x + (self.offset * self.px_step)

        if event.type == 'ESC':
            # frame_set(self.init_frame) ?
            context.scene.frame_current = self.cancel_frame
            self._exit_modal(context)
            return {'CANCELLED'}

        # Snap if pressing NOT used mouse key (right or mid)
        if event.type == self.snap_mouse_key:
            if event.value == "PRESS":
                self.snap_on = True
            else:
                self.snap_on = False

        if event.type == self.key and event.value == 'RELEASE':
            self._exit_modal(context)
            return {'FINISHED'}

        return {"RUNNING_MODAL"}


# --- addon prefs

def auto_rebind(self, context):
    unregister_keymaps()
    register_keymaps()


class PIESPLUS_OT_set_scrub_keymap(bpy.types.Operator):
    bl_idname = "pies_plus.set_timeline_scrub_keymap"
    bl_label = "Change keymap"
    bl_description = "Quick time scrubbing with a shortcut"
    bl_options = {"REGISTER", "INTERNAL"}

    def invoke(self, context, event):
        self.prefs = get_timeline_preferences()
        self.ctrl = False
        self.shift = False
        self.alt = False

        self.init_value = self.prefs.keycode
        self.prefs.keycode = ''
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        exclude_keys = {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE',
                        'TIMER_REPORT', 'ESC', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
        exclude_in = ('SHIFT', 'CTRL', 'ALT')
        if event.type == 'ESC':
            self.prefs.keycode = self.init_value
            return {'CANCELLED'}

        self.ctrl = event.ctrl
        self.shift = event.shift
        self.alt = event.alt

        if event.type not in exclude_keys and not any(x in event.type for x in exclude_in):
            # print('key:', event.type, 'value:', event.value)
            if event.value == 'PRESS':
                self.report({'INFO'}, event.type)
                # set the chosen key
                self.prefs.keycode = event.type
                # Following condition to avoid unnecessary rebind update
                if self.prefs.use_shift != event.shift:
                    self.prefs.use_shift = event.shift

                if self.prefs.use_alt != event.alt:
                    self.prefs.use_alt = event.alt

                # -# Trigger rebind update with last
                self.prefs.use_ctrl = event.ctrl

                return {'FINISHED'}

        return {"RUNNING_MODAL"}


class PIESPLUS_timeline_settings(bpy.types.PropertyGroup):

    keycode: StringProperty(
        name="Shortcut",
        description="Shortcut to trigger the scrub in viewport during press",
        default="MIDDLEMOUSE")

    always_snap: BoolProperty(
        name="Always Snap",
        description="Always snap to keys if any, modifier is used deactivate the snapping\nDisabled if no keyframe found",
        default=False)

    rolling_mode: BoolProperty(
        name="Rolling Mode",
        description="Alternative Gap-less timeline. No time information to quickly roll/flip over keys\nOverride normal and 'always snap' mode",
        default=False)

    use: BoolProperty(
        name="Enable",
        description="Enable/Disable timeline scrub",
        default=True,
        update=auto_rebind)

    smart_scrub: BoolProperty(
        name="Smart Scrub",
        description=(
            "Opt into context-aware targets, proximity snapping, and adaptive "
            "scrub sensitivity; disabled by default to preserve classic behavior"
        ),
        default=False)

    smart_target_scope: EnumProperty(
        name="Animation Scope",
        description="Animation sources used by Smart Scrub",
        default='ACTIVE',
        items=(
            ('ACTIVE', 'Active Object',
             'Use keys from the active object and its active Grease Pencil layer', 0),
            ('SELECTED', 'Selected Objects',
             'Use keys from the active and selected objects', 1),
            ('VISIBLE', 'Visible Objects',
             'Use keys from all visible objects in the current view layer', 2),
        ))

    smart_include_markers: BoolProperty(
        name="Include Markers",
        description="Use scene timeline markers as Smart Scrub targets",
        default=True)

    smart_include_strip_bounds: BoolProperty(
        name="Include Strip Bounds",
        description="Use video and sound strip boundaries as Sequencer targets",
        default=True)

    smart_auto_snap: BoolProperty(
        name="Proximity Snap",
        description="Magnetically snap when the cursor moves close to a Smart Scrub target",
        default=True)

    smart_snap_radius: IntProperty(
        name="Snap Radius",
        description="Maximum frame distance for proximity snapping",
        default=2,
        min=0,
        max=20,
        soft_max=8)

    smart_adaptive_sensitivity: BoolProperty(
        name="Adaptive Sensitivity",
        description="Reduce the pixel step for long frame ranges so more of the scene is reachable",
        default=True)

    smart_show_status: BoolProperty(
        name="Smart HUD Status",
        description="Show the active Smart Scrub target sources in the temporary HUD",
        default=True)

    use_in_timeline_editor: BoolProperty(
        name="Shortcut in timeline editors",
        description="Add the same shortcut to scrub in timeline editor windows",
        default=True,
        update=auto_rebind)
    
    use_in_node_editor: BoolProperty(
        name="Use in Node editor",
        description="Allow using the scrub shortcut in node editor the same way it's used in viewport",
        default=True)

    use_shift: BoolProperty(
        name="Combine With Shift",
        description="Add shift",
        default=False,
        update=auto_rebind)

    use_alt: BoolProperty(
        name="Combine With Alt",
        description="Add alt",
        default=True,
        update=auto_rebind)

    use_ctrl: BoolProperty(
        name="Combine With Ctrl",
        description="Add ctrl",
        default=False,
        update=auto_rebind)

    evaluate_gp_obj_key: BoolProperty(
        name='Use Gpencil Object Keyframes',
        description="Also snap on greasepencil object keyframe (else only active layer frames)",
        default=True)

    gp_layer_target: EnumProperty(
        name="Layer Target",
        description="Grease pencil layers keys to consider when scrubbing",
        default='ACTIVE',
        items=(
            ('ACTIVE', 'Active Layer Keys',
             'Consider only keys of the active layer\n(if group item is active, consider keys of all layers in group)', 0),
            ('ALL', 'All Layers Keys',
             'Consider keys of all layers', 1),
        ))

    pixel_step: IntProperty(
        name="Frame Interval On Screen",
        description="Pixel steps on screen that represent a frame intervals",
        default=10,
        min=1,
        max=500,
        soft_min=2,
        soft_max=100,
        step=1,
        subtype='PIXEL')

    use_hud: BoolProperty(
        name='Display Timeline Overlay',
        description="Display overlays with timeline information when scrubbing time in viewport",
        default=True)

    use_hud_time_line: BoolProperty(
        name='Timeline',
        description="Display a static marks overlay to represent timeline when scrubbing",
        default=True)

    use_hud_keyframes: BoolProperty(
        name='Keyframes',
        description="Display shapes overlay to show keyframe position when scrubbing",
        default=True)

    use_hud_playhead: BoolProperty(
        name='Playhead',
        description="Display the playhead as a vertical line to show position in time",
        default=True)

    use_hud_frame_current: BoolProperty(
        name='Text Frame Current',
        description="Display the current frame as text above mouse cursor",
        default=True)

    use_hud_frame_offset: BoolProperty(
        name='Text Frame Offset',
        description="Display frame offset from initial position as text above mouse cursor",
        default=True)

    color_timeline: FloatVectorProperty(
        name="Timeline Color",
        subtype='COLOR_GAMMA',
        size=4,
        default=(0.5, 0.5, 0.5, 0.6),
        min=0.0, max=1.0,
        description="Color of the temporary timeline")

    color_playhead: FloatVectorProperty(
        name="Cursor Color",
        subtype='COLOR_GAMMA',
        size=4,
        default=(0.01, 0.64, 1.0, 0.8),
        min=0.0, max=1.0,
        description="Color of the temporary line cursor and text")

    # sizes
    playhead_size: IntProperty(
        name="Playhead Size",
        description="Playhead height in pixels",
        default=100,
        min=2,
        max=10000,
        soft_min=10,
        soft_max=5000,
        step=1,
        subtype='PIXEL')

    lines_size: IntProperty(
        name="Frame Lines Size",
        description="Frame lines height in pixels",
        default=10,
        min=1,
        max=10000,
        soft_min=5,
        soft_max=40,
        step=1,
        subtype='PIXEL')

    keyframe_aspect: EnumProperty(
        name="Keyframe Display",
        description="Customize aspect of the keyframes",
        default='LINE',
        items=(
            ('LINE', 'Line',
             'Keyframe displayed as thick lines', 'SNAP_INCREMENT', 0),
            ('SQUARE', 'Square',
             'Keyframe displayed as squares', 'HANDLETYPE_VECTOR_VEC', 1),
            ('DIAMOND', 'Diamond',
             'Keyframe displayed as diamonds', 'HANDLETYPE_FREE_VEC', 2),
        ))

    hide_overlays: BoolProperty(
        name="Hide Overlays",
        description="Hide overlays and gizmos while scrubbing is active",
        default=False
    )

def draw_timeline_scrub_preferences(prefs, layout):
    # - General settings
    layout.label(text='Timeline Scrub:')
    layout.prop(prefs, 'use')
    if not prefs.use:
        return

    layout.prop(prefs, 'evaluate_gp_obj_key')
    layout.prop(prefs, 'gp_layer_target')
    layout.prop(prefs, 'pixel_step')

    smart_box = layout.box()
    smart_box.label(text='Smart Scrub (optional):')
    smart_box.prop(prefs, 'smart_scrub')
    if prefs.smart_scrub:
        smart_box.label(
            text='Adds context-aware targets while classic scrub settings stay independent.',
            icon='INFO')
        smart_box.prop(prefs, 'smart_target_scope')
        row = smart_box.row(align=True)
        row.prop(prefs, 'smart_include_markers')
        row.prop(prefs, 'smart_include_strip_bounds')
        row = smart_box.row(align=True)
        row.prop(prefs, 'smart_auto_snap')
        row.prop(prefs, 'smart_snap_radius')
        row = smart_box.row(align=True)
        row.prop(prefs, 'smart_adaptive_sensitivity')
        row.prop(prefs, 'smart_show_status')

    # -/ Keymap -
    box = layout.box()
    box.label(text='Keymap:')
    box.operator('pies_plus.set_timeline_scrub_keymap',
                 text='Click here to change shortcut')

    if prefs.keycode:
        row = box.row(align=True)
        row.prop(prefs, 'use_ctrl', text='Ctrl')
        row.prop(prefs, 'use_alt', text='Alt')
        row.prop(prefs, 'use_shift', text='Shift')
        # -/Cosmetic-
        icon = None
        if prefs.keycode == 'LEFTMOUSE':
            icon = 'MOUSE_LMB'
        elif prefs.keycode == 'MIDDLEMOUSE':
            icon = 'MOUSE_MMB'
        elif prefs.keycode == 'RIGHTMOUSE':
            icon = 'MOUSE_RMB'
        if icon:
            row.label(text=f'{prefs.keycode}', icon=icon)
        # -Cosmetic-/
        else:
            row.label(text=f'Key: {prefs.keycode}')

    else:
        box.label(text='[ NOW TYPE KEY OR CLICK TO USE, WITH MODIFIER ]')

    if prefs.always_snap:
        snap_text = 'Disable keyframes snap: '
    else:
        snap_text = 'Keyframes snap: '

    snap_text += 'Left Mouse' if prefs.keycode == 'RIGHTMOUSE' else 'Right Mouse'
    if not prefs.use_ctrl:
        snap_text += ' or Ctrl'
    if not prefs.use_shift:
        snap_text += ' or Shift'
    if not prefs.use_alt:
        snap_text += ' or Alt'

    if prefs.rolling_mode:
        snap_text = 'Gap-less mode (always snap)'

    box.label(text=snap_text, icon='SNAP_ON')
    if prefs.keycode in ('LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE') and not prefs.use_ctrl and not prefs.use_alt and not prefs.use_shift:
        box.label(
            text="Recommended to choose at least one modifier to combine with clicks (default: Ctrl+Alt)", icon="ERROR")

    col = box.column(align=False)
    row = col.row()
    row.prop(prefs, 'always_snap')
    row.prop(prefs, 'rolling_mode')
    row = col.row()
    row.prop(prefs, 'use_in_timeline_editor', text='Add shortcut to scrub in timeline editors')
    row.prop(prefs, 'hide_overlays')
    row = col.row()
    row.prop(prefs, 'use_in_node_editor', text='Use scrub in node editor')

    # - HUD/OSD
    box = layout.box()
    box.prop(prefs, 'use_hud')

    col = box.column()
    row = col.row()
    row.prop(prefs, 'color_timeline')
    row.prop(prefs, 'color_playhead', text='Cursor And Text Color')
    col.label(text='Show:')
    row = col.row()
    row.prop(prefs, 'use_hud_time_line')
    row.prop(prefs, 'lines_size')
    row = col.row()
    row.prop(prefs, 'use_hud_playhead')
    row.prop(prefs, 'playhead_size')
    row = col.row()
    row.prop(prefs, 'use_hud_keyframes')
    row.prop(prefs, 'keyframe_aspect', text='')
    row = col.row()
    row.prop(prefs, 'use_hud_frame_current')
    row.prop(prefs, 'use_hud_frame_offset')
    col.enabled = prefs.use_hud


# --- Keymap

addon_keymaps = []


def register_keymaps():
    try:
        prefs = get_timeline_preferences()
    except (AttributeError, KeyError):
        # A factory-startup import has no enabled-addon preference entry yet.
        # Blender will register these keymaps when the installed addon is enabled.
        return
    if not prefs.use:
        return

    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return

    km = kc.keymaps.new(name="Grease Pencil", space_type="EMPTY", region_type='WINDOW')

    if not prefs.keycode:
        print(r'/!\ Timeline scrub: no keycode entered for keymap')
        return
    kmi = km.keymap_items.new(
        'pies_plus.timeline_scrub',
        type=prefs.keycode, value='PRESS',
        alt=prefs.use_alt, ctrl=prefs.use_ctrl, shift=prefs.use_shift, any=False)
    kmi.repeat = False
    addon_keymaps.append((km, kmi))

    # - Add keymap in timeline editors
    if prefs.use_in_timeline_editor:

        editor_l = [
            ('Dopesheet', 'DOPESHEET_EDITOR', 'anim.change_frame'),
            ('Graph Editor', 'GRAPH_EDITOR', 'graph.cursor_set'),
            ("NLA Editor", "NLA_EDITOR", 'anim.change_frame'),
            ("Sequencer", "SEQUENCE_EDITOR", 'anim.change_frame')
            # ("Clip Graph Editor", "CLIP_EDITOR", 'clip.change_frame'),
        ]

        for editor, space, operator in editor_l:
            km = kc.keymaps.new(name=editor, space_type=space)
            kmi = km.keymap_items.new(
                operator, type=prefs.keycode, value='PRESS',
                alt=prefs.use_alt, ctrl=prefs.use_ctrl, shift=prefs.use_shift)
            addon_keymaps.append((km, kmi))


def unregister_keymaps():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

# --- REGISTER ---

classes = (
    PIESPLUS_OT_time_scrub,
    PIESPLUS_OT_set_scrub_keymap,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_keymaps()

def unregister():
    unregister_keymaps()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
