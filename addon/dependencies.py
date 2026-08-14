"""Optional Blender add-on dependency detection.

Dependency availability is determined from the operators that an integration
actually needs.  Installed/enabled module information is supplemental because
Blender extensions and bundled add-ons do not always appear in the same
registry across supported releases.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import bpy

from .compat import get_operator


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DependencySpec:
    key: str
    label: str
    modules: Tuple[str, ...]
    operators: Tuple[str, ...]


@dataclass(frozen=True)
class DependencyStatus:
    spec: DependencySpec
    installed: bool
    enabled: bool
    available: bool
    missing_operators: Tuple[str, ...]
    module_name: Optional[str] = None

    @property
    def state_label(self) -> str:
        if self.available:
            return "Available"
        if self.enabled:
            return "Enabled, but operators unavailable"
        if self.installed:
            return "Installed, not enabled"
        return "Not detected"

    @property
    def message(self) -> str:
        if self.available:
            return f"{self.spec.label} is available."
        if self.installed:
            return f"Enable {self.spec.label} to use this pie menu."
        return f"Install or enable {self.spec.label} to use this pie menu."


DEPENDENCY_SPECS: Tuple[DependencySpec, ...] = (
    DependencySpec(
        key="looptools",
        label="LoopTools",
        modules=("mesh_looptools", "looptools"),
        operators=(
            "mesh.looptools_relax",
            "mesh.looptools_space",
            "mesh.looptools_flatten",
            "mesh.looptools_circle",
            "mesh.looptools_bridge",
            "mesh.looptools_gstretch",
            "mesh.looptools_curve",
        ),
    ),
    DependencySpec(
        key="booltool",
        label="Bool Tool",
        modules=("object_boolean_tools", "booltool", "boolean_tools"),
        operators=(
            "object.boolean_auto_slice",
            "object.boolean_brush_slice",
            "object.boolean_auto_difference",
            "object.boolean_brush_difference",
            "object.boolean_brush_intersect",
            "object.boolean_brush_union",
            "object.boolean_auto_union",
            "object.boolean_auto_intersect",
        ),
    ),
    DependencySpec(
        key="edgeflow",
        label="EdgeFlow",
        modules=("edgeflow", "edge_flow", "mesh_edgeflow"),
        operators=(
            "mesh.set_edge_flow",
            "mesh.set_edge_curve",
            "mesh.set_edge_linear",
            "mesh.align_vertex_curve",
        ),
    ),
)

_SPECS_BY_KEY: Dict[str, DependencySpec] = {
    spec.key: spec for spec in DEPENDENCY_SPECS
}


def _normalise_names(names: Iterable[str]) -> set[str]:
    return {name.rsplit('.', 1)[-1].lower() for name in names}


def _installed_module_names() -> set[str]:
    """Return discoverable addon/extension module names when available."""
    try:
        import addon_utils
        modules = addon_utils.modules()
    except (ImportError, AttributeError, RuntimeError):
        return set()

    return _normalise_names(
        getattr(module, "__name__", "")
        for module in modules
        if getattr(module, "__name__", "")
    )


def _enabled_module_names() -> set[str]:
    """Return enabled addon module names across Blender API variants."""
    names = set()

    try:
        names.update(str(name).lower() for name in bpy.context.preferences.addons.keys())
    except (AttributeError, RuntimeError):
        pass

    try:
        import addon_utils
    except ImportError:
        return names

    for spec in DEPENDENCY_SPECS:
        for module_name in spec.modules:
            try:
                _loaded, enabled = addon_utils.check(module_name)
            except (AttributeError, RuntimeError, TypeError):
                continue
            if enabled:
                names.add(module_name.lower())
    return names


def _operator_status(spec: DependencySpec) -> Tuple[bool, Tuple[str, ...]]:
    missing = tuple(
        idname for idname in spec.operators if get_operator(idname) is None
    )
    return not missing, missing


def _status_for_spec(
    spec: DependencySpec,
    installed_names: set[str],
    enabled_names: set[str],
) -> DependencyStatus:
    module_name = next(
        (name for name in spec.modules if name.lower() in installed_names),
        None,
    )
    enabled_module = any(name.lower() in enabled_names for name in spec.modules)
    available, missing_operators = _operator_status(spec)

    return DependencyStatus(
        spec=spec,
        installed=module_name is not None or enabled_module,
        enabled=enabled_module or available,
        available=available,
        missing_operators=missing_operators,
        module_name=module_name,
    )


def get_dependency_status(key: str) -> DependencyStatus:
    """Return a fresh status snapshot for an optional integration."""
    try:
        spec = _SPECS_BY_KEY[key.lower()]
    except KeyError as exc:
        raise KeyError(f"Unknown optional dependency: {key}") from exc

    return _status_for_spec(
        spec,
        _installed_module_names(),
        _enabled_module_names(),
    )


def dependency_statuses() -> Tuple[DependencyStatus, ...]:
    """Return current status snapshots for all optional integrations."""
    installed_names = _installed_module_names()
    enabled_names = _enabled_module_names()
    return tuple(
        _status_for_spec(spec, installed_names, enabled_names)
        for spec in DEPENDENCY_SPECS
    )


def check_optional_dependencies() -> Tuple[DependencyStatus, ...]:
    """Check optional integrations at addon registration and log diagnostics."""
    statuses = dependency_statuses()
    for status in statuses:
        if status.available:
            log.debug("Optional dependency available: %s", status.spec.label)
        else:
            log.info("Optional dependency unavailable: %s", status.message)
    return statuses


def draw_dependency_notice(layout, key: str) -> bool:
    """Draw a useful fallback message and return whether an integration is ready."""
    status = get_dependency_status(key)
    if status.available:
        return True

    row = layout.row()
    row.alert = True
    row.label(text=status.message, icon='ERROR')
    return False
