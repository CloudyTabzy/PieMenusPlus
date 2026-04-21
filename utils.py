import bpy
import inspect
import logging
import bmesh
from timeit import default_timer
from typing import Any, Optional
import bpy.types as types

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class OpInfo:
    """Mix-in class for operators with default options."""
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = ""


class CodeTimer:
    """A basic context manager for timing code blocks."""
    def __init__(self, repeat: int = 100) -> None:
        self.timing = 1000  # milliseconds
        self.timer = default_timer
        self.repeat = repeat

    def __enter__(self) -> int:
        self.start = self.timer()
        return self.repeat

    def __exit__(self, _exc_type: Any, _exc_val: Any, _traceback: Any) -> None:
        end = self.timer()
        self.elapsed = (end - self.start) * self.timing

        print(f"{inspect.stack()[1][3]}'s time: {round(self.elapsed, 6)}ms")


class BMeshFromEditMode:
    """Generate a temporary BMesh. Accepts Objects or Meshes as inputs temp change."""
    def __init__(self, input_data: types.Object | types.Mesh, update_mesh: bool = True) -> None:
        if isinstance(input_data, types.Mesh):
            self.input_data = input_data
        else:
            self.input_data = input_data.data

        self.update_mesh = update_mesh

    def __enter__(self) -> bmesh.types.BMesh:
        self.bm = bmesh.from_edit_mesh(self.input_data)
        return self.bm

    def __exit__(self, _exc_type: Any, _exc_value: Any, _exc_traceback: Any) -> None:
        # NOTE do not use self.bm.free() for BMeshes made in Edit Mode, uses same data regardless

        if self.update_mesh:
            bmesh.update_edit_mesh(self.input_data)


def get_addon_preferences() -> Any:
    """Get the addon preferences object."""
    return bpy.context.preferences.addons[__package__].preferences
