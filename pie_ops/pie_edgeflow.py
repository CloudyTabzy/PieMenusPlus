import bpy
from bpy.types import Menu


########################################
# EDGEFLOW - SHIFT + ALT + F
########################################


class PIESPLUS_MT_edgeflow(Menu):
    bl_idname = "PIESPLUS_MT_edgeflow"
    bl_label = "EdgeFlow"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        # Check if EdgeFlow operators exist
        if not hasattr(bpy.ops.mesh, 'set_edge_flow'):
            pie.label(text="          WARNING: You must have EdgeFlow addon enabled")
            return

        # Get mesh select mode to determine which operators to show
        mesh_select_mode = context.scene.tool_settings.mesh_select_mode[:3]

        if mesh_select_mode == (True, False, False):
            # Vertex mode - only show Set Vertex Curve
            # 4 - LEFT
            pie.operator("mesh.set_vertex_curve", text="Set Vertex Curve")
            # Others show disabled or label
            pie.label(text="EdgeFlow - Vertex Mode")
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
        elif mesh_select_mode == (False, True, False):
            # Edge mode - show Set Flow, Set Curve, Set Linear
            # 4 - LEFT
            pie.operator("mesh.set_edge_flow", text="Set Flow")
            # 6 - RIGHT
            pie.operator("mesh.set_edge_curve", text="Set Curve")
            # 2 - BOTTOM
            pie.operator("mesh.set_edge_linear", text="Set Linear")
            # Others show disabled or separator
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()
        else:
            # Face mode or mixed - show all available operators
            pie.operator("mesh.set_edge_flow", text="Set Flow")
            pie.operator("mesh.set_edge_curve", text="Set Curve")
            pie.operator("mesh.set_edge_linear", text="Set Linear")
            pie.operator("mesh.set_vertex_curve", text="Set Vertex Curve")
            pie.separator()
            pie.separator()
            pie.separator()
            pie.separator()


##############################
#   REGISTRATION
##############################


def register():
    bpy.utils.register_class(PIESPLUS_MT_edgeflow)


def unregister():
    bpy.utils.unregister_class(PIESPLUS_MT_edgeflow)


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
