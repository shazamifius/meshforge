"""MeshForge - Outil de profilage des performances du diagnostic sur gros maillages.
Mesure précisément le temps passé dans chaque fonction et sous-phase pour différentes tailles de maillages.
"""

from __future__ import annotations
import sys
import time
import os
import gc
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import bpy
import bmesh
import numpy as np

import meshforge
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.core.structured_diagnosis import measure_mesh_facts, evaluate_structured_diagnosis
from meshforge.ui.panel import VIEW3D_PT_meshforge_main


class DummyLayout:
    def __init__(self):
        self.alert = False
        self.active = True
        self.scale_y = 1.0

    def box(self):
        return DummyLayout()

    def row(self, align=False):
        return DummyLayout()

    def column(self, align=False):
        return DummyLayout()

    def grid_flow(self, **kwargs):
        return DummyLayout()

    def label(self, text="", icon='NONE'):
        pass

    def prop(self, data, property, **kwargs):
        pass

    def operator(self, operator, text="", **kwargs):
        class DummyOp:
            def __init__(self):
                self.finding_id = ""
                self.format_type = ""
        return DummyOp()

    def separator(self):
        pass


class MockPanel:
    def __init__(self):
        self.layout = DummyLayout()


def create_test_mesh(name: str, subdiv_level: int):
    """Crée une Icosphère subdivisée pour obtenir un nombre contrôlé de sommets/faces."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not hasattr(bpy.types.Scene, "meshforge_settings"):
        meshforge.register()

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv_level, radius=2.0)
    obj = bpy.context.active_object
    obj.name = name

    # Insérer quelques cas particuliers pour tester la complétude du diagnostic
    # (par ex. un N-gone en supprimant une arête interne)
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    if len(bm.edges) > 10:
        bmesh.ops.dissolve_edges(bm, edges=[bm.edges[0]])
    bm.to_mesh(mesh)
    bm.free()

    mesh.calc_loop_triangles()
    return obj


def profile_mesh(obj: bpy.types.Object, label: str):
    mesh = obj.data
    v_count = len(mesh.vertices)
    e_count = len(mesh.edges)
    f_count = len(mesh.polygons)
    tri_count = len(mesh.loop_triangles)

    print(f"\n{'='*70}")
    print(f"PROFILAGE : {label}")
    print(f"Éléments : {v_count:,} sommets | {e_count:,} arêtes | {f_count:,} faces | {tri_count:,} triangles réels")
    print(f"{'='*70}")

    # Mesure 1 : diagnose_topology global
    gc.collect()
    t0 = time.perf_counter()
    diag = diagnose_topology(obj, mode='GAME_ASSET')
    t_diag_total = time.perf_counter() - t0
    print(f"1. diagnose_topology() TOTAL : {t_diag_total:.4f} s")

    # Mesure 2 : Décomposition interne de diagnose_topology
    # 2.1 Bounding box v_coords
    gc.collect()
    t0 = time.perf_counter()
    v_coords = np.array([v.co for v in mesh.vertices], dtype=np.float64)
    local_min = np.min(v_coords, axis=0)
    local_max = np.max(v_coords, axis=0)
    span = local_max - local_min
    bbox_diag = max(1e-6, float(np.linalg.norm(span)))
    t_vcoords = time.perf_counter() - t0
    print(f"   2.1 v_coords [v.co for v in mesh.vertices] : {t_vcoords:.4f} s")

    # 2.1b Alternative Vectorisée foreach_get
    t0 = time.perf_counter()
    coords_fast = np.empty((v_count, 3), dtype=np.float32)
    mesh.vertices.foreach_get('co', coords_fast.ravel())
    c_min = coords_fast.min(axis=0)
    c_max = coords_fast.max(axis=0)
    bbox_diag_fast = float(np.linalg.norm(c_max - c_min))
    t_vcoords_fast = time.perf_counter() - t0
    print(f"   2.1b (Comparatif) mesh.vertices.foreach_get : {t_vcoords_fast:.4f} s (Gain: x{t_vcoords/max(1e-6, t_vcoords_fast):.1f})")

    # 2.2 BMesh from_mesh
    gc.collect()
    t0 = time.perf_counter()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    t_bm_from = time.perf_counter() - t0
    print(f"   2.2 bmesh.from_mesh() : {t_bm_from:.4f} s")

    # 2.3 Parcours bm.faces
    t0 = time.perf_counter()
    for f in bm.faces:
        _ = len(f.verts)
        _ = f.calc_area()
    t_bm_faces = time.perf_counter() - t0
    print(f"   2.3 Parcours bm.faces + calc_area() : {t_bm_faces:.4f} s")

    # 2.4 Parcours bm.edges
    t0 = time.perf_counter()
    for e in bm.edges:
        _ = e.is_wire
        _ = len(e.link_faces)
        _ = e.calc_length()
    t_bm_edges = time.perf_counter() - t0
    print(f"   2.4 Parcours bm.edges + calc_length() : {t_bm_edges:.4f} s")

    # 2.5 Parcours bm.verts
    t0 = time.perf_counter()
    for v in bm.verts:
        _ = len(v.link_edges)
        _ = v.is_boundary
    t_bm_verts = time.perf_counter() - t0
    print(f"   2.5 Parcours bm.verts : {t_bm_verts:.4f} s")

    # 2.6 BFS Composantes connexes
    t0 = time.perf_counter()
    unvisited = set(bm.faces)
    num_comps = 0
    while unvisited:
        root = unvisited.pop()
        num_comps += 1
        queue = [root]
        while queue:
            curr = queue.pop()
            for e in curr.edges:
                for nf in e.link_faces:
                    if nf in unvisited:
                        unvisited.remove(nf)
                        queue.append(nf)
    t_bfs = time.perf_counter() - t0
    print(f"   2.6 BFS Composantes connexes ({num_comps} trouvées) : {t_bfs:.4f} s")

    bm.free()

    # Mesure 3 : measure_mesh_facts (appelé redondamment dans diagnose_topology !)
    gc.collect()
    t0 = time.perf_counter()
    facts = measure_mesh_facts(obj)
    t_facts = time.perf_counter() - t0
    print(f"3. measure_mesh_facts() TOTAL (RE-CALCUL DUPLIQUÉ) : {t_facts:.4f} s")

    # Mesure 4 : evaluate_structured_diagnosis
    t0 = time.perf_counter()
    struct = evaluate_structured_diagnosis(facts, 'GAME_ASSET')
    t_struct = time.perf_counter() - t0
    print(f"4. evaluate_structured_diagnosis() : {t_struct:.4f} s")

    # Mesure 5 : panel.draw() impact UI
    panel = MockPanel()
    props = bpy.context.scene.meshforge_settings
    props.ui_section_clean_expanded = True
    props.ui_section_decimate_expanded = True  # Tester avec les deux sections ouvertes

    t0 = time.perf_counter()
    for _ in range(5):
        VIEW3D_PT_meshforge_main.draw(panel, bpy.context)
    t_draw = (time.perf_counter() - t0) / 5.0
    print(f"5. UI Panel draw() moyen : {t_draw:.4f} s ({t_draw*1000:.1f} ms)")

    return {
        "label": label,
        "v_count": v_count,
        "f_count": f_count,
        "tri_count": tri_count,
        "t_diag_total": t_diag_total,
        "t_vcoords": t_vcoords,
        "t_vcoords_fast": t_vcoords_fast,
        "t_bm_from": t_bm_from,
        "t_bm_faces": t_bm_faces,
        "t_bm_edges": t_bm_edges,
        "t_bfs": t_bfs,
        "t_facts": t_facts,
        "t_struct": t_struct,
        "t_draw": t_draw
    }


def main():
    print("MeshForge — Début de la campagne de profilage des performances...")
    levels = [
        ("Petit maillage (~10k sommets)", 4),      # subdiv 4 = 2,562 verts, 5,120 faces
        ("Moyen maillage (~40k sommets)", 5),      # subdiv 5 = 10,242 verts, 20,480 faces
        ("Grand maillage (~160k sommets)", 6),     # subdiv 6 = 40,962 verts, 81,920 faces
        ("Très grand maillage (~650k sommets)", 7) # subdiv 7 = 163,842 verts, 327,680 faces
    ]

    results = []
    for label, level in levels:
        obj = create_test_mesh("BenchObj", level)
        res = profile_mesh(obj, label)
        results.append(res)

    # Test extrême 8 si faisable (~655k sommets, 1.3M tris)
    print("\n--- Test Extrême Subdiv 8 (~655k sommets, 1.3M triangles) ---")
    obj_ext = create_test_mesh("BenchObj_Mega", 8)
    res_ext = profile_mesh(obj_ext, "Extrême (~655k sommets / 1.31M faces)")
    results.append(res_ext)

    print("\n" + "="*80)
    print("RÉSUMÉ DU PROFILAGE INITIAL")
    print(f"{'Maillage':<35} | {'Sommets':<10} | {'Faces':<10} | {'Diag Total':<12} | {'Facts (Dup)':<12} | {'BFS Comp':<10} | {'UI Draw':<10}")
    print("-" * 105)
    for r in results:
        print(f"{r['label']:<35} | {r['v_count']:<10,d} | {r['f_count']:<10,d} | {r['t_diag_total']:<10.3f} s | {r['t_facts']:<10.3f} s | {r['t_bfs']:<8.3f} s | {r['t_draw']*1000:<7.1f} ms")
    print("="*80)


if __name__ == "__main__":
    main()
