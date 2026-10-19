"""MeshForge - Module de validation géométrique et métrique de surface (Phase C).
Implémente un échantillonnage surfacique bidirectionnel (barycentrique),
l'analyse des percentiles P95/P99/Max, la déviation des normales,
la silhouette multi-directionnelle et la variation volumétrique.
"""

from __future__ import annotations
import bpy
import bmesh
import math
import numpy as np
from mathutils.bvhtree import BVHTree
from typing import Dict, Any, Tuple, Optional


def sample_mesh_surface(mesh: bpy.types.Mesh, target_samples: int = 10000) -> Tuple[np.ndarray, np.ndarray]:
    """Échantillonne uniformément des points sur la surface des triangles d'un maillage.
    Utilise une distribution barycentrique pondérée par l'aire de chaque face.
    Retourne (positions, normales).
    """
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()

    face_count = len(bm.faces)
    if face_count == 0:
        bm.free()
        if len(mesh.vertices) > 0:
            coords = np.array([v.co for v in mesh.vertices], dtype=np.float64)
            norms = np.array([v.normal for v in mesh.vertices], dtype=np.float64)
            return coords, norms
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.float64)

    v0 = np.empty((face_count, 3), dtype=np.float64)
    v1 = np.empty((face_count, 3), dtype=np.float64)
    v2 = np.empty((face_count, 3), dtype=np.float64)
    fn = np.empty((face_count, 3), dtype=np.float64)
    areas = np.empty(face_count, dtype=np.float64)

    for i, f in enumerate(bm.faces):
        v0[i] = f.verts[0].co
        v1[i] = f.verts[1].co
        v2[i] = f.verts[2].co
        fn[i] = f.normal
        areas[i] = f.calc_area()

    bm.free()

    tot_area = np.sum(areas)
    if tot_area <= 1e-12:
        return v0, fn

    probs = areas / tot_area
    n_samples = min(target_samples, max(100, face_count * 2))
    chosen_faces = np.random.choice(face_count, size=n_samples, p=probs)

    # Coordonnées barycentriques uniformes
    u = np.random.uniform(0.0, 1.0, size=n_samples)
    v = np.random.uniform(0.0, 1.0, size=n_samples)
    flip_mask = (u + v) > 1.0
    u[flip_mask] = 1.0 - u[flip_mask]
    v[flip_mask] = 1.0 - v[flip_mask]

    u = u[:, None]
    v = v[:, None]

    pts = v0[chosen_faces] + u * (v1[chosen_faces] - v0[chosen_faces]) + v * (v2[chosen_faces] - v0[chosen_faces])
    normals = fn[chosen_faces]

    return pts, normals


def evaluate_geometric_deviation(
    orig_obj: bpy.types.Object,
    simp_obj: bpy.types.Object,
    sample_count: int = 10000
) -> Dict[str, Any]:
    """Calcule la comparaison géométrique bidirectionnelle complète entre l'original et le résultat simplifié.
    Documente les distances moyenne, P95, P99, Max observée, déviation des normales et silhouette.
    """
    if not orig_obj or not simp_obj or orig_obj.type != 'MESH' or simp_obj.type != 'MESH':
        return {"valid": False, "error": "Objets invalides pour la validation."}

    mesh_orig = orig_obj.data
    mesh_simp = simp_obj.data

    # Boîte englobante et échelle caractéristique
    bbox_diag = max(1e-6, float(orig_obj.dimensions.length))

    # Construction des BVH Trees
    bvh_orig = BVHTree.FromPolygons([v.co for v in mesh_orig.vertices], [p.vertices for p in mesh_orig.polygons])
    bvh_simp = BVHTree.FromPolygons([v.co for v in mesh_simp.vertices], [p.vertices for p in mesh_simp.polygons])

    # 1. Échantillonnage surfacique bidirectionnel
    pts_orig, nms_orig = sample_mesh_surface(mesh_orig, target_samples=sample_count)
    pts_simp, nms_simp = sample_mesh_surface(mesh_simp, target_samples=sample_count)

    actual_samples_orig = len(pts_orig)
    actual_samples_simp = len(pts_simp)

    # Direction 1 : Original -> Simplifié
    dist_orig_to_simp = []
    normal_deviations = []
    for i in range(actual_samples_orig):
        p = pts_orig[i]
        loc, norm, idx, dist = bvh_simp.find_nearest(p)
        if dist is not None:
            dist_orig_to_simp.append(dist)
            if norm is not None:
                # Produit scalaire des normales
                dot = max(-1.0, min(1.0, float(np.dot(nms_orig[i], norm))))
                ang_deg = math.degrees(math.acos(dot))
                normal_deviations.append(ang_deg)

    # Direction 2 : Simplifié -> Original
    dist_simp_to_orig = []
    for i in range(actual_samples_simp):
        q = pts_simp[i]
        loc, norm, idx, dist = bvh_orig.find_nearest(q)
        if dist is not None:
            dist_simp_to_orig.append(dist)

    all_dists = np.array(dist_orig_to_simp + dist_simp_to_orig, dtype=np.float64)
    if len(all_dists) == 0:
        all_dists = np.array([0.0], dtype=np.float64)

    # 2. Statistiques d'erreur de surface
    dist_mean = float(np.mean(all_dists))
    dist_p95 = float(np.percentile(all_dists, 95))
    dist_p99 = float(np.percentile(all_dists, 99))
    dist_max = float(np.max(all_dists))
    dist_max_relative = float(dist_max / bbox_diag)

    # 3. Statistiques de normales
    ang_mean = float(np.mean(normal_deviations)) if normal_deviations else 0.0
    ang_p95 = float(np.percentile(normal_deviations, 95)) if normal_deviations else 0.0
    ang_max = float(np.max(normal_deviations)) if normal_deviations else 0.0

    # 4. Évaluation de la silhouette (Projection orthogonale XY, XZ, YZ)
    silhouette_deviations = {}
    if actual_samples_orig > 0 and actual_samples_simp > 0:
        for name, axes in [('XY', [0, 1]), ('XZ', [0, 2]), ('YZ', [1, 2])]:
            orig_min = np.min(pts_orig[:, axes], axis=0)
            orig_max = np.max(pts_orig[:, axes], axis=0)
            simp_min = np.min(pts_simp[:, axes], axis=0)
            simp_max = np.max(pts_simp[:, axes], axis=0)
            orig_area = max(1e-9, float((orig_max[0] - orig_min[0]) * (orig_max[1] - orig_min[1])))
            simp_area = max(1e-9, float((simp_max[0] - simp_min[0]) * (simp_max[1] - simp_min[1])))
            delta_area_pct = abs(orig_area - simp_area) / orig_area * 100.0
            silhouette_deviations[name] = round(delta_area_pct, 3)

    # 5. Variation de volume pour maillages fermés
    volume_delta_pct: Optional[float] = None
    bm_orig = bmesh.new()
    bm_orig.from_mesh(mesh_orig)
    bm_simp = bmesh.new()
    bm_simp.from_mesh(mesh_simp)

    is_watertight = (all(e.is_manifold for e in bm_orig.edges) and not any(e.is_boundary for e in bm_orig.edges))
    if is_watertight:
        try:
            v_orig = bm_orig.calc_volume()
            v_simp = bm_simp.calc_volume()
            if abs(v_orig) > 1e-9:
                volume_delta_pct = round(abs(v_orig - v_simp) / abs(v_orig) * 100.0, 3)
        except Exception:
            pass

    bm_orig.free()
    bm_simp.free()

    # 6. Intégrité des caractéristiques
    sharp_orig = sum(1 for e in mesh_orig.edges if e.use_edge_sharp)
    sharp_simp = sum(1 for e in mesh_simp.edges if e.use_edge_sharp)
    seams_orig = sum(1 for e in mesh_orig.edges if e.use_seam)
    seams_simp = sum(1 for e in mesh_simp.edges if e.use_seam)
    mats_orig = len(orig_obj.material_slots)
    mats_simp = len(simp_obj.material_slots)

    return {
        "valid": True,
        "sample_method": "Barycentric surface sampling + Bidirectional BVH",
        "sample_count_orig": actual_samples_orig,
        "sample_count_simp": actual_samples_simp,
        "bounding_box_diagonal": bbox_diag,
        "distance_mean": round(dist_mean, 6),
        "distance_p95": round(dist_p95, 6),
        "distance_p99": round(dist_p99, 6),
        "distance_max_observed": round(dist_max, 6),
        "distance_max_relative": round(dist_max_relative, 6),
        "normal_deviation_mean_deg": round(ang_mean, 2),
        "normal_deviation_p95_deg": round(ang_p95, 2),
        "normal_deviation_max_deg": round(ang_max, 2),
        "silhouette_deviation_pct": silhouette_deviations,
        "volume_delta_pct": volume_delta_pct,
        "is_watertight": is_watertight,
        "sharp_edges_before": sharp_orig,
        "sharp_edges_after": sharp_simp,
        "seams_before": seams_orig,
        "seams_after": seams_simp,
        "materials_before": mats_orig,
        "materials_after": mats_simp,
        "approximation_note": (
            "Mesures empiriques d'écartement surfacique par échantillonnage aléatoire pondéré. "
            "Ne constitue pas une borne mathématique formelle (supremum exact)."
        )
    }
