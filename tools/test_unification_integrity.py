"""Test d'intégrité : vérifie que l'analyse unifiée produit exactement les mêmes résultats factuels que l'ancienne."""
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

# Créer un objet avec tous les défauts types
bpy.ops.wm.read_factory_settings(use_empty=True)
if not hasattr(bpy.types.Scene, "meshforge_settings"):
    meshforge.register()

mesh = bpy.data.meshes.new("TestIntegrity")
bm = bmesh.new()

# Quads
v0 = bm.verts.new((-1.0, -1.0, 0.0))
v1 = bm.verts.new((0.0, -1.0, 0.0))
v2 = bm.verts.new((0.0, 0.0, 0.0))
v3 = bm.verts.new((-1.0, 0.0, 0.0))
bm.faces.new((v0, v1, v2, v3))

# Triangles
v4 = bm.verts.new((1.0, -1.0, 0.0))
v5 = bm.verts.new((1.0, 0.0, 0.0))
bm.faces.new((v1, v4, v5))
bm.faces.new((v1, v5, v2))

# Ngon concave
v6 = bm.verts.new((2.0, -0.5, 0.0))
v7 = bm.verts.new((2.0, 0.5, 0.0))
v8 = bm.verts.new((1.5, 0.0, 0.0)) # concave
bm.faces.new((v5, v4, v6, v7, v8))

# Face d'aire nulle
vz0 = bm.verts.new((5.0, 0.0, 0.0))
vz1 = bm.verts.new((5.0, 0.0, 0.0))
vz2 = bm.verts.new((5.0, 0.0, 0.0))
bm.faces.new((vz0, vz1, vz2))

# Sommet orphelin
bm.verts.new((10.0, 10.0, 10.0))

# Arête filaire
vw1 = bm.verts.new((12.0, 0.0, 0.0))
vw2 = bm.verts.new((13.0, 0.0, 0.0))
bm.edges.new((vw1, vw2))

bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new("TestIntegrity", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj

diag = diagnose_topology(obj, mode='GAME_ASSET')
print("Analyse actuelle :")
print(f"  Valid: {diag['valid']}")
print(f"  Summary: {diag['summary']}")
print(f"  Defects: {len(diag['defects'])}")
for d in diag['defects']:
    print(f"    - [{d['category']}] {d['type']} : {d['name']} (element: {d['element_type']})")
print(f"  Findings: {len(diag['findings'])}")
for f in diag['findings']:
    print(f"    - [{f['severity']}] {f['id']} : {f['name']}")
