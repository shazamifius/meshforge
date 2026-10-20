"""Prototype d'unification pour tester le gain immédiat sur 1M et 2.25M sommets."""
import bpy
import bmesh
import time
import numpy as np
import sys
from pathlib import Path
from mathutils import Vector

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

def fast_measure_mesh(obj: bpy.types.Object):
    t0 = time.perf_counter()
    mesh = obj.data

    # Bbox instantanée via obj.bound_box
    bb = obj.bound_box
    span = Vector(bb[6]) - Vector(bb[0])
    bbox_diameter = max(1e-6, float(span.length))
    micro_edge_threshold = max(1e-6, bbox_diameter * 1e-4)

    # Statistiques directes
    v_count = len(mesh.vertices)
    e_count = len(mesh.edges)
    f_count = len(mesh.polygons)

    # Calcul loop_triangles
    mesh.calc_loop_triangles()
    real_triangles = len(mesh.loop_triangles)

    # UN SEUL BMesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Parcours unique des faces
    tris = []
    quads = []
    ngons_convex = []
    ngons_concave = []
    ngons_ambiguous = []
    zero_area_faces = []
    needle_triangles = []

    for f in bm.faces:
        area = f.calc_area()
        if area <= 1e-7:
            zero_area_faces.append(f.index)
            continue
        nv = len(f.verts)
        if nv == 4:
            quads.append(f.index)
        elif nv == 3:
            tris.append(f.index)
            edge_lens = [e.calc_length() for e in f.edges]
            max_l = max(edge_lens) if edge_lens else 1.0
            min_l = min(edge_lens) if edge_lens else 1.0
            aspect = max_l / max(1e-7, min_l)
            if aspect > 8.0:
                needle_triangles.append((f.index, aspect))
        else:
            # Ngon
            try:
                from meshforge.core.ngon_cutter import classify_ngon
                diag_ng = classify_ngon(f)
                cat = diag_ng.get("category", "CONVEX")
            except Exception:
                cat = "CONVEX"
            if cat == 'AMBIGUOUS':
                ngons_ambiguous.append(f.index)
            elif cat == 'CONCAVE':
                ngons_concave.append(f.index)
            else:
                ngons_convex.append(f.index)

    # Parcours unique des arêtes
    wire_edges = []
    boundary_edges = []
    non_manifold_edges = []
    micro_edges = []
    for e in bm.edges:
        lf_len = len(e.link_faces)
        if lf_len == 0:
            wire_edges.append(e.index)
        elif lf_len == 1:
            boundary_edges.append(e.index)
        elif lf_len > 2:
            non_manifold_edges.append(e.index)
        if e.calc_length() <= micro_edge_threshold and lf_len > 1:
            micro_edges.append(e.index)

    # Analyse des parois internes si non-manifold présent
    strict_internal_faces = []
    t_junction_faces = []
    if non_manifold_edges:
        try:
            from meshforge.core.internal_walls import classify_non_manifold_faces
            wall_diag = classify_non_manifold_faces(bm)
            strict_internal_faces = wall_diag.get("strict_internal_faces", [])
            t_junction_faces = wall_diag.get("t_junction_faces", [])
        except Exception:
            pass

    # Parcours unique des sommets
    loose_verts = []
    poles_valence_3 = 0
    poles_valence_4 = 0
    poles_valence_5 = 0
    poles_valence_6_plus = []

    for v in bm.verts:
        val = len(v.link_edges)
        if val == 0:
            loose_verts.append(v.index)
        elif not v.is_boundary:
            if val == 3:
                poles_valence_3 += 1
            elif val == 4:
                poles_valence_4 += 1
            elif val == 5:
                poles_valence_5 += 1
            elif val >= 6:
                poles_valence_6_plus.append(v.index)

    # Composantes connexes (BFS unique)
    # Optimisation : si aucun bord libre ni arête orpheline et f_count > 100k,
    # tester si 1 seule composante rapidement
    components = []
    unvisited = set(bm.faces)
    while unvisited:
        start = unvisited.pop()
        comp = [start.index]
        queue = [start]
        while queue:
            curr = queue.pop()
            for e in curr.edges:
                for nf in e.link_faces:
                    if nf in unvisited:
                        unvisited.remove(nf)
                        comp.append(nf.index)
                        queue.append(nf)
        components.append(comp)

    bm.free()

    duration = time.perf_counter() - t0
    return {
        "v_count": v_count,
        "f_count": f_count,
        "duration": duration,
        "components_count": len(components),
        "zero_area_count": len(zero_area_faces),
        "wire_edges_count": len(wire_edges),
        "loose_verts_count": len(loose_verts)
    }

# Test sur 1M
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=1000, y_subdivisions=1000, size=10.0)
obj1m = bpy.context.active_object
res1m = fast_measure_mesh(obj1m)
print(f"FAST 1M Sommets ({res1m['v_count']:,} v, {res1m['f_count']:,} f) : {res1m['duration']:.3f} s (vs 10.707 s avant)")

# Test sur 2.25M
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=1500, y_subdivisions=1500, size=15.0)
obj2m = bpy.context.active_object
res2m = fast_measure_mesh(obj2m)
print(f"FAST 2.25M Sommets ({res2m['v_count']:,} v, {res2m['f_count']:,} f) : {res2m['duration']:.3f} s (vs 22.844 s avant)")
