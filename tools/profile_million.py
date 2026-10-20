"""Test de profilage sur maillages de 1 Million et 2.25 Millions de sommets."""
import bpy
import bmesh
import time
import numpy as np
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.core.structured_diagnosis import measure_mesh_facts

bpy.ops.wm.read_factory_settings(use_empty=True)
if not hasattr(bpy.types.Scene, "meshforge_settings"):
    meshforge.register()

print("\n--- Test Grille 1,000 x 1,000 (1,000,000 sommets / 998,001 faces) ---")
bpy.ops.mesh.primitive_grid_add(x_subdivisions=1000, y_subdivisions=1000, size=10.0)
obj_1m = bpy.context.active_object
mesh_1m = obj_1m.data

print(f"Objet 1M : {len(mesh_1m.vertices):,} sommets, {len(mesh_1m.edges):,} arêtes, {len(mesh_1m.polygons):,} faces")

t0 = time.perf_counter()
diag_1m = diagnose_topology(obj_1m, mode='GAME_ASSET')
t_total_1m = time.perf_counter() - t0
print(f"diagnose_topology 1M TOTAL : {t_total_1m:.3f} s")

print("\n--- Test Grille 1,500 x 1,500 (2,250,000 sommets / 2,247,001 faces) ---")
bpy.ops.wm.read_factory_settings(use_empty=True)
if not hasattr(bpy.types.Scene, "meshforge_settings"):
    meshforge.register()
bpy.ops.mesh.primitive_grid_add(x_subdivisions=1500, y_subdivisions=1500, size=15.0)
obj_2m = bpy.context.active_object
mesh_2m = obj_2m.data

print(f"Objet 2.25M : {len(mesh_2m.vertices):,} sommets, {len(mesh_2m.edges):,} arêtes, {len(mesh_2m.polygons):,} faces")

t0 = time.perf_counter()
diag_2m = diagnose_topology(obj_2m, mode='GAME_ASSET')
t_total_2m = time.perf_counter() - t0
print(f"diagnose_topology 2.25M TOTAL : {t_total_2m:.3f} s")
