"""MeshForge - Core module."""

from .mesh_stats import get_mesh_statistics
from .repair_pipeline import execute_repair
from .manifold import execute_manifold
from .dissolve import execute_dissolve
from .topology import execute_topology
from .normals import execute_normals
from .object_data import execute_object_data
from .pipeline import run_meshforge_pipeline, duplicate_object_non_destructive

__all__ = [
    "get_mesh_statistics",
    "execute_repair",
    "execute_manifold",
    "execute_dissolve",
    "execute_topology",
    "execute_normals",
    "execute_object_data",
    "run_meshforge_pipeline",
    "duplicate_object_non_destructive",
]
