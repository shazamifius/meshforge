"""Test de reproduction du cas P0 : deux anomalies distinctes du même type."""
import bpy
import bmesh
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.structured_diagnosis import measure_mesh_facts, evaluate_structured_diagnosis
from meshforge.core.topology_diagnosis import diagnose_topology

bpy.ops.wm.read_factory_settings(use_empty=True)
if not hasattr(bpy.types.Scene, "meshforge_settings"):
    meshforge.register()

# Créer un maillage avec 2 N-gones concaves distincts (Face A et Face B)
mesh = bpy.data.meshes.new("TwoConcaveNgons")
bm = bmesh.new()

# N-gone concave 1 (intentionnel) centré autour de X = -3
v1_0 = bm.verts.new((-4.0, -1.0, 0.0))
v1_1 = bm.verts.new((-2.0, -1.0, 0.0))
v1_2 = bm.verts.new((-2.0, 1.0, 0.0))
v1_3 = bm.verts.new((-3.0, 0.0, 0.0)) # cran concave
v1_4 = bm.verts.new((-4.0, 1.0, 0.0))
f1 = bm.faces.new((v1_0, v1_1, v1_2, v1_3, v1_4))

# N-gone concave 2 (accidentel) centré autour de X = +3
v2_0 = bm.verts.new((2.0, -1.0, 0.0))
v2_1 = bm.verts.new((4.0, -1.0, 0.0))
v2_2 = bm.verts.new((4.0, 1.0, 0.0))
v2_3 = bm.verts.new((3.0, 0.0, 0.0)) # cran concave
v2_4 = bm.verts.new((2.0, 1.0, 0.0))
f2 = bm.faces.new((v2_0, v2_1, v2_2, v2_3, v2_4))

bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new("TwoConcaveNgons", mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj

diag = diagnose_topology(obj, mode="GAME_ASSET")
print("\n--- Diagnostic initial ---")
print("Findings:")
for f in diag["findings"]:
    print(f"  - [{f['severity']}] ID='{f['id']}' Name='{f['name']}' Count={f['count']} Indices={f['indices']}")
print(f"Defects count: {diag['structured']['summary_counts']['defects']}")

# 1. Tentative avec l'ID global sans précision d'index (doit être refusée pour sécurité)
print("\n--- 1. Tentative de marquage global sans spécifier l'occurrence ---")
res_global = bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave")
print(f"Résultat marquage global (doit être CANCELLED): {res_global}")

# 2. Marquage granulaire de la première anomalie (Face 0) uniquement
print("\n--- 2. Marquage granulaire de l'occurrence 0 (Face 0) ---")
res_granular = bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave:0")
print(f"Résultat marquage granulaire: {res_granular}")

diag_after = diagnose_topology(obj, mode="GAME_ASSET")
print("\n--- Diagnostic après marquage granulaire de Face 0 ---")
for f in diag_after["findings"]:
    print(f"  - [{f['severity']}] ID='{f['id']}' Name='{f['name']}' Count={f['count']} Indices={f['indices']} Intentional={f.get('is_intentional')}")
print(f"Defects count: {diag_after['structured']['summary_counts']['defects']}")
print(f"Risks count: {diag_after['structured']['summary_counts']['risks']}")

# 3. Test de zoom sur la seconde anomalie (Face 1), qui doit rester inspectable
print("\n--- 3. Zoom sur la seconde anomalie accidentelle (Face 1) ---")
res_focus = bpy.ops.meshforge.focus_defect(finding_id="topo_ngons_concave:1")
print(f"Résultat focus Face 1: {res_focus}")

# Vérifications
findings_dict = {f["id"]: f for f in diag_after["findings"]}
assert "topo_ngons_concave:0" in findings_dict, "Face 0 doit être présente"
assert "topo_ngons_concave:1" in findings_dict, "Face 1 doit être présente"
assert findings_dict["topo_ngons_concave:0"]["is_intentional"] == True, "Face 0 doit être marquée intentionnelle"
assert findings_dict["topo_ngons_concave:1"]["is_intentional"] == False, "Face 1 ne doit PAS être marquée intentionnelle"
assert findings_dict["topo_ngons_concave:1"]["severity"] == "DEFECT", "Face 1 doit rester un DÉFAUT"
print("\n[SUCCESS] Le test de granularité P0 est validé à 100% !")
