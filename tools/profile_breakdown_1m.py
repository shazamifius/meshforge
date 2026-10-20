"""Profilage détaillé des sous-phases sur le maillage de 1 Million de sommets."""
import bpy
import bmesh
import time
import numpy as np
import sys
import gc
from pathlib import Path
from mathutils import Vector

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.structured_diagnosis import measure_mesh_facts

bpy.ops.wm.read_factory_settings(use_empty=True)
if not hasattr(bpy.types.Scene, "meshforge_settings"):
    meshforge.register()

bpy.ops.mesh.primitive_grid_add(x_subdivisions=1000, y_subdivisions=1000, size=10.0)
obj = bpy.context.active_object
mesh = obj.data

print(f"Objet : {len(mesh.vertices):,} sommets, {len(mesh.edges):,} arêtes, {len(mesh.polygons):,} faces")

# 1. v_coords via list comprehension
t0 = time.perf_counter()
v_coords = np.array([v.co for v in mesh.vertices], dtype=np.float64)
span = np.max(v_coords, axis=0) - np.min(v_coords, axis=0)
diag_vcoords = float(np.linalg.norm(span))
t_vcoords = time.perf_counter() - t0
print(f"Phase A - v_coords Python list comprehension : {t_vcoords:.3f} s")

# 1b. v_coords via foreach_get ou obj.bound_box
t0 = time.perf_counter()
bb = obj.bound_box
bbox_fast = float(np.linalg.norm(Vector(bb[6]) - Vector(bb[0])))
t_bbox_fast = time.perf_counter() - t0
print(f"Phase A-bis - obj.bound_box direct : {t_bbox_fast*1000:.4f} ms")

# 2. BMesh conversion
t0 = time.perf_counter()
bm = bmesh.new()
bm.from_mesh(mesh)
t_bm_from = time.perf_counter() - t0
print(f"Phase B - bmesh.from_mesh() : {t_bm_from:.3f} s")

# 3. Parcours faces
t0 = time.perf_counter()
zero_f = 0
tris = 0
quads = 0
ngons = 0
for f in bm.faces:
    nv = len(f.verts)
    if nv == 4:
        quads += 1
    elif nv == 3:
        tris += 1
    else:
        ngons += 1
    if f.calc_area() <= 1e-7:
        zero_f += 1
t_faces = time.perf_counter() - t0
print(f"Phase C - Parcours bm.faces + f.calc_area() : {t_faces:.3f} s")

# 4. Parcours edges
t0 = time.perf_counter()
wire_e = 0
boundary_e = 0
non_manifold_e = 0
micro_e = 0
threshold = 0.001
for e in bm.edges:
    if not e.link_faces:
        wire_e += 1
    elif e.is_boundary:
        boundary_e += 1
    elif not e.is_manifold:
        non_manifold_e += 1
    if e.calc_length() <= threshold:
        micro_e += 1
t_edges = time.perf_counter() - t0
print(f"Phase D - Parcours bm.edges + e.calc_length() : {t_edges:.3f} s")

# 5. Parcours verts
t0 = time.perf_counter()
loose_v = 0
poles_3 = 0
poles_5 = 0
poles_6 = 0
for v in bm.verts:
    val = len(v.link_edges)
    if val == 0:
        loose_v += 1
    elif not v.is_boundary:
        if val == 3:
            poles_3 += 1
        elif val == 5:
            poles_5 += 1
        elif val >= 6:
            poles_6 += 1
t_verts = time.perf_counter() - t0
print(f"Phase E - Parcours bm.verts + valences : {t_verts:.3f} s")

# 6. Connected components BFS
t0 = time.perf_counter()
unvisited = set(bm.faces)
comp_count = 0
while unvisited:
    root = unvisited.pop()
    comp_count += 1
    queue = [root]
    while queue:
        curr = queue.pop()
        for e in curr.edges:
            for nf in e.link_faces:
                if nf in unvisited:
                    unvisited.remove(nf)
                    queue.append(nf)
t_bfs = time.perf_counter() - t0
print(f"Phase F - BFS Composantes connexes Python set/queue : {t_bfs:.3f} s")

bm.free()

# 7. measure_mesh_facts execution
t0 = time.perf_counter()
facts = measure_mesh_facts(obj)
t_facts = time.perf_counter() - t0
print(f"Phase G - measure_mesh_facts() (2ème BMesh + 2ème parcours) : {t_facts:.3f} s")
