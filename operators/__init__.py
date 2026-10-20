"""MeshForge - Enregistrement de tous les opérateurs."""

from __future__ import annotations
import bpy

from .optimize import MESHFORGE_OT_optimize
from .analyze import MESHFORGE_OT_analyze
from .section_ops import (
    MESHFORGE_OT_repair,
    MESHFORGE_OT_manifold,
    MESHFORGE_OT_dissolve,
    MESHFORGE_OT_simplification,
    MESHFORGE_OT_topology,
    MESHFORGE_OT_normals,
    MESHFORGE_OT_object_data,
)
from .restore import MESHFORGE_OT_restore, MESHFORGE_OT_toggle_wireframe
from .report_export import MESHFORGE_OT_export_report
from .topology_inspect import (
    MESHFORGE_OT_analyze_topology,
    MESHFORGE_OT_focus_defect,
    MESHFORGE_OT_clear_defect_view,
    MESHFORGE_OT_mark_intentional
)
from .conservative_clean_op import MESHFORGE_OT_conservative_clean
from .ngon_cut_op import MESHFORGE_OT_cut_ngons
from .quadrangulate_op import MESHFORGE_OT_quadrangulate
from .internal_walls_op import (
    MESHFORGE_OT_select_internal_walls,
    MESHFORGE_OT_remove_internal_walls,
)

classes = (
    MESHFORGE_OT_optimize,
    MESHFORGE_OT_analyze,
    MESHFORGE_OT_analyze_topology,
    MESHFORGE_OT_focus_defect,
    MESHFORGE_OT_clear_defect_view,
    MESHFORGE_OT_mark_intentional,
    MESHFORGE_OT_conservative_clean,
    MESHFORGE_OT_cut_ngons,
    MESHFORGE_OT_quadrangulate,
    MESHFORGE_OT_select_internal_walls,
    MESHFORGE_OT_remove_internal_walls,
    MESHFORGE_OT_repair,
    MESHFORGE_OT_manifold,
    MESHFORGE_OT_dissolve,
    MESHFORGE_OT_simplification,
    MESHFORGE_OT_topology,
    MESHFORGE_OT_normals,
    MESHFORGE_OT_object_data,
    MESHFORGE_OT_restore,
    MESHFORGE_OT_toggle_wireframe,
    MESHFORGE_OT_export_report,
)


from ..core.registration_utils import register_classes_safely, unregister_classes_safely


def register_operators():
    register_classes_safely(classes)


def unregister_operators():
    from .restore import _WIREFRAME_ENABLED_BY_MESHFORGE
    from .topology_inspect import _ACTIVE_DIAGNOSIS_CACHE
    _WIREFRAME_ENABLED_BY_MESHFORGE.clear()
    _ACTIVE_DIAGNOSIS_CACHE.clear()
    unregister_classes_safely(classes)
