"""MeshForge - Core module."""

from .mesh_stats import get_mesh_statistics
from .repair_pipeline import execute_repair
from .manifold import execute_manifold
from .dissolve import execute_dissolve
from .topology import execute_topology
from .normals import execute_normals
from .object_data import execute_object_data
from .simplification import execute_simplification
from .validation import evaluate_geometric_deviation, sample_mesh_surface
from .pipeline import run_meshforge_pipeline, duplicate_object_non_destructive
from .report import format_report_as_text, export_report_to_file
from .topology_diagnosis import diagnose_topology
from .visualizer import select_defect, zoom_to_defect, apply_color_inspection, clear_inspection_view
from .quadrangulator import (
    quad_orthogonality_score,
    check_triangle_pair_compatibility,
    execute_targeted_quadrangulation,
)
from .registration_utils import (
    is_class_registered,
    safe_register_class,
    safe_unregister_class,
    register_classes_safely,
    unregister_classes_safely,
)

__all__ = [
    "get_mesh_statistics",
    "execute_repair",
    "execute_manifold",
    "execute_dissolve",
    "execute_topology",
    "execute_normals",
    "execute_object_data",
    "execute_simplification",
    "evaluate_geometric_deviation",
    "sample_mesh_surface",
    "run_meshforge_pipeline",
    "duplicate_object_non_destructive",
    "format_report_as_text",
    "export_report_to_file",
    "diagnose_topology",
    "select_defect",
    "zoom_to_defect",
    "apply_color_inspection",
    "clear_inspection_view",
    "quad_orthogonality_score",
    "check_triangle_pair_compatibility",
    "execute_targeted_quadrangulation",
    "is_class_registered",
    "safe_register_class",
    "safe_unregister_class",
    "register_classes_safely",
    "unregister_classes_safely",
]
