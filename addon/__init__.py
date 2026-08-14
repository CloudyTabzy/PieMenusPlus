bl_info = {
    "name": "Pie Menus Plus",
    "description": "Improved Pie Menu ecosystem for Blender 4.2+",
    "author": "Tabzy",
    "version": (2, 7, 0),
    "blender": (4, 2, 0),
    "category": "3D View",
}


import importlib

from .dependencies import check_optional_dependencies


module_names = (
    "ui",
    "prefs",

    "ops.op_separate",

    "pie_ops.pie_modes",
    "pie_ops.pie_snapping",
    "pie_ops.pie_origin_cursor",
    "pie_ops.pie_transforms",
    "pie_ops.pie_selection",
    "pie_ops.pie_shading",
    "pie_ops.pie_proportional",
    "pie_ops.pie_keyframing",
    "pie_ops.pie_save",
    "pie_ops.pie_align",
    "pie_ops.pie_timeline_scrub"
)
modules = []
for mod in module_names:
    if mod in locals():
        modules.append(importlib.reload(locals()[mod]))
    else:
        modules.append(importlib.import_module(f".{mod}", package=__package__))


def register():
    for mod in modules:
        mod.register()
    check_optional_dependencies()

def unregister():
    for mod in modules:
        mod.unregister()


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
