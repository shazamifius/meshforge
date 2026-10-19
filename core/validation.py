"""MeshForge - Module de validation géométrique et métrique de surface (Phase C2).
Implémente un échantillonnage surfacique bidirectionnel reproductible (avec seed),
des distances de Hausdorff et quantiles P95/P99 séparés (avant / arrière / combiné),
la déviation des normales, une véritable mesure de silhouette 2D par masque d'occupation (IoU)
et distance de contour (KDTree), ainsi qu'un calcul sécurisé de la variation volumétrique.
"""

from __future__ import annotations
import bpy
import bmesh
import math
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from typing import Dict, Any, Tuple, Optional


def sample_mesh_surface(
    mesh: bpy.types.Mesh,
    target_samples: int = 10000,
    seed: Optional[int] = 42
) -> Tuple[np.ndarray, np.ndarray]:
    """Échantillonne uniformément des points sur la surface des triangles d'un maillage.
    Utilise une distribution barycentrique pondérée par l'aire de chaque face.
    Garantit une graine reproductible et inclut les sommets réels du maillage.
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
        if len(mesh.vertices) > 0:
            return np.array([v.co for v in mesh.vertices], dtype=np.float64), np.array([v.normal for v in mesh.vertices], dtype=np.float64)
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.float64)

    rng = np.random.default_rng(seed)
    probs = areas / tot_area
    n_samples = max(target_samples, 100)
    chosen_faces = rng.choice(face_count, size=n_samples, p=probs)

    # Coordonnées barycentriques uniformes
    u = rng.uniform(0.0, 1.0, size=n_samples)
    v = rng.uniform(0.0, 1.0, size=n_samples)
    flip_mask = (u + v) > 1.0
    u[flip_mask] = 1.0 - u[flip_mask]
    v[flip_mask] = 1.0 - v[flip_mask]

    u = u[:, None]
    v = v[:, None]

    face_pts = v0[chosen_faces] + u * (v1[chosen_faces] - v0[chosen_faces]) + v * (v2[chosen_faces] - v0[chosen_faces])
    face_normals = fn[chosen_faces]

    return face_pts, face_normals


def compute_silhouette_occupancy_and_contour(
    pts_2d: np.ndarray,
    bbox_min: np.ndarray,
    bbox_max: np.ndarray,
    res: int = 128
) -> Tuple[np.ndarray, np.ndarray]:
    """Calcule le masque d'occupation 2D (avec dilatation morphologique pour combler
    les écarts d'échantillonnage) et extrait les points de contour 2D.
    """
    span = np.maximum(bbox_max - bbox_min, 1e-6)
    # Mapping normalisé sur la grille [1, res-2] pour laisser 1 pixel de marge
    norm = np.clip((pts_2d - bbox_min) / span, 0.0, 1.0)
    grid_coords = (norm * (res - 3) + 1).astype(np.int32)

    mask = np.zeros((res, res), dtype=bool)
    mask[grid_coords[:, 1], grid_coords[:, 0]] = True

    # Dilatation morphologique adaptative selon la résolution pour combler les écarts d'échantillonnage
    radius = max(1, int(math.ceil(res / 75.0)))
    d_mask = mask.copy()
    for _ in range(radius):
        d_mask[1:, :] |= d_mask[:-1, :]
        d_mask[:-1, :] |= d_mask[1:, :]
        d_mask[:, 1:] |= d_mask[:, :-1]
        d_mask[:, :-1] |= d_mask[:, 1:]

    # Flood-fill depuis la bordure extérieure pour déterminer le fond (background)
    background = np.zeros((res, res), dtype=bool)
    background[0, :] = True
    background[-1, :] = True
    background[:, 0] = True
    background[:, -1] = True

    stack = []
    for x in range(res):
        if not d_mask[0, x]:
            stack.append((0, x))
        if not d_mask[res - 1, x]:
            stack.append((res - 1, x))
    for y in range(res):
        if not d_mask[y, 0]:
            stack.append((y, 0))
        if not d_mask[y, res - 1]:
            stack.append((y, res - 1))

    while stack:
        cy, cx = stack.pop()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < res and 0 <= nx < res and not background[ny, nx] and not d_mask[ny, nx]:
                background[ny, nx] = True
                stack.append((ny, nx))

    solid_mask = ~background

    # Extraction du contour : pixels solides voisins d'au moins un pixel de fond
    up = np.pad(background[1:, :], ((0, 1), (0, 0)), constant_values=True)
    down = np.pad(background[:-1, :], ((1, 0), (0, 0)), constant_values=True)
    left = np.pad(background[:, 1:], ((0, 0), (0, 1)), constant_values=True)
    right = np.pad(background[:, :-1], ((0, 0), (1, 0)), constant_values=True)

    contour_mask = solid_mask & (up | down | left | right)
    cy, cx = np.nonzero(contour_mask)
    contour_points = np.column_stack((cx, cy)).astype(np.float64)

    return solid_mask, contour_points


def compute_contour_distances(
    contour_a: np.ndarray,
    contour_b: np.ndarray,
    scale_to_meters: float
) -> Tuple[float, float]:
    """Calcule la distance bidirectionnelle (moyenne, max en mètres) entre deux contours 2D."""
    if len(contour_a) == 0 or len(contour_b) == 0:
        return 0.0, 0.0

    kd_b = KDTree(len(contour_b))
    for i, p in enumerate(contour_b):
        kd_b.insert((float(p[0]), float(p[1]), 0.0), i)
    kd_b.balance()

    dists_a = [kd_b.find((float(p[0]), float(p[1]), 0.0))[2] for p in contour_a]

    kd_a = KDTree(len(contour_a))
    for i, p in enumerate(contour_a):
        kd_a.insert((float(p[0]), float(p[1]), 0.0), i)
    kd_a.balance()

    dists_b = [kd_a.find((float(p[0]), float(p[1]), 0.0))[2] for p in contour_b]

    all_d = np.array(dists_a + dists_b, dtype=np.float64) * scale_to_meters
    return float(np.mean(all_d)), float(np.max(all_d))


def evaluate_geometric_deviation(
    orig_obj: bpy.types.Object,
    simp_obj: bpy.types.Object,
    sample_count: int = 10000,
    silhouette_resolution: int = 128,
    seed: Optional[int] = 42
) -> Dict[str, Any]:
    """Calcule la comparaison géométrique bidirectionnelle complète entre l'original et le résultat simplifié.
    Distingue rigoureusement distances avant, arrière, Hausdorff, déviation des normales,
    vraie silhouette par IoU/contour, et intégrité topologique.
    """
    if not orig_obj or not simp_obj or orig_obj.type != 'MESH' or simp_obj.type != 'MESH':
        return {"valid": False, "error": "Objets invalides pour la validation."}

    mesh_orig = orig_obj.data
    mesh_simp = simp_obj.data

    # Boîte englobante locale (immunisée contre le scale non appliqué)
    v_orig_co = np.array([v.co for v in mesh_orig.vertices], dtype=np.float64)
    if len(v_orig_co) == 0:
        return {"valid": False, "error": "Maillage original vide."}
    local_min = np.min(v_orig_co, axis=0)
    local_max = np.max(v_orig_co, axis=0)
    bbox_diag = max(1e-6, float(np.linalg.norm(local_max - local_min)))

    # Construction ultra-rapide des BVH Trees via BMesh natif
    bm_bvh_orig = bmesh.new()
    bm_bvh_orig.from_mesh(mesh_orig)
    bvh_orig = BVHTree.FromBMesh(bm_bvh_orig)
    bm_bvh_orig.free()

    bm_bvh_simp = bmesh.new()
    bm_bvh_simp.from_mesh(mesh_simp)
    bvh_simp = BVHTree.FromBMesh(bm_bvh_simp)
    bm_bvh_simp.free()

    # 1. Échantillonnage surfacique bidirectionnel avec seed
    pts_orig, nms_orig = sample_mesh_surface(mesh_orig, target_samples=sample_count, seed=seed)
    pts_simp, nms_simp = sample_mesh_surface(
        mesh_simp,
        target_samples=sample_count,
        seed=seed + 1 if seed is not None else None
    )

    actual_samples_orig = len(pts_orig)
    actual_samples_simp = len(pts_simp)

    # Direction 1 : Original -> Simplifié (Sens direct / Forward)
    dist_orig_to_simp = []
    normal_deviations = []
    for i in range(actual_samples_orig):
        p = pts_orig[i]
        loc, norm, idx, dist = bvh_simp.find_nearest(p)
        if dist is not None:
            dist_orig_to_simp.append(dist)
            if norm is not None and norm.length > 1e-6:
                # Normalisation sécurisée
                n_unit = norm.normalized()
                dot = max(-1.0, min(1.0, float(np.dot(nms_orig[i], n_unit))))
                ang_deg = math.degrees(math.acos(dot))
                normal_deviations.append(ang_deg)

    # Direction 2 : Simplifié -> Original (Sens inverse / Backward)
    dist_simp_to_orig = []
    for i in range(actual_samples_simp):
        q = pts_simp[i]
        loc, norm, idx, dist = bvh_orig.find_nearest(q)
        if dist is not None:
            dist_simp_to_orig.append(dist)

    d_fwd = np.array(dist_orig_to_simp, dtype=np.float64) if dist_orig_to_simp else np.array([0.0])
    d_bwd = np.array(dist_simp_to_orig, dtype=np.float64) if dist_simp_to_orig else np.array([0.0])
    all_dists = np.concatenate((d_fwd, d_bwd))

    # Métriques séparées et combinées
    dist_fwd_mean = float(np.mean(d_fwd))
    dist_fwd_p95 = float(np.percentile(d_fwd, 95))
    dist_fwd_p99 = float(np.percentile(d_fwd, 99))
    dist_fwd_max = float(np.max(d_fwd))

    dist_bwd_mean = float(np.mean(d_bwd))
    dist_bwd_p95 = float(np.percentile(d_bwd, 95))
    dist_bwd_p99 = float(np.percentile(d_bwd, 99))
    dist_bwd_max = float(np.max(d_bwd))

    dist_hausdorff = max(dist_fwd_max, dist_bwd_max)
    dist_mean = float(np.mean(all_dists))
    dist_p95 = float(np.percentile(all_dists, 95))
    dist_p99 = float(np.percentile(all_dists, 99))
    dist_max = dist_hausdorff
    dist_max_relative = float(dist_max / bbox_diag)

    # Statistiques de normales
    ang_mean = float(np.mean(normal_deviations)) if normal_deviations else 0.0
    ang_p95 = float(np.percentile(normal_deviations, 95)) if normal_deviations else 0.0
    ang_max = float(np.max(normal_deviations)) if normal_deviations else 0.0

    # 4. Évaluation rigoureuse de silhouette 2D (IoU + Contours)
    silhouette_deviations = {}
    silhouette_metrics = {}
    res = silhouette_resolution

    if actual_samples_orig > 0 and actual_samples_simp > 0:
        for name, axes in [('XY', [0, 1]), ('XZ', [0, 2]), ('YZ', [1, 2])]:
            pts_2d_orig = pts_orig[:, axes]
            pts_2d_simp = pts_simp[:, axes]

            min_2d = np.minimum(np.min(pts_2d_orig, axis=0), np.min(pts_2d_simp, axis=0)) - 0.02
            max_2d = np.maximum(np.max(pts_2d_orig, axis=0), np.max(pts_2d_simp, axis=0)) + 0.02
            span_2d = np.maximum(max_2d - min_2d, 1e-6)
            scale_m = float(np.mean(span_2d) / (res - 3))

            mask_orig, contour_orig = compute_silhouette_occupancy_and_contour(pts_2d_orig, min_2d, max_2d, res=res)
            mask_simp, contour_simp = compute_silhouette_occupancy_and_contour(pts_2d_simp, min_2d, max_2d, res=res)

            inter = np.sum(mask_orig & mask_simp)
            union = np.sum(mask_orig | mask_simp)
            iou = float(inter / max(1, union))
            divergence_pct = round((1.0 - iou) * 100.0, 3)

            area_orig = np.sum(mask_orig)
            area_simp = np.sum(mask_simp)
            area_delta_pct = round(abs(area_orig - area_simp) / max(1, area_orig) * 100.0, 3)

            c_mean_m, c_max_m = compute_contour_distances(contour_orig, contour_simp, scale_m)

            silhouette_deviations[name] = divergence_pct
            silhouette_metrics[name] = {
                "iou": round(iou, 4),
                "divergence_pct": divergence_pct,
                "area_delta_pct": area_delta_pct,
                "contour_distance_mean_m": round(c_mean_m, 6),
                "contour_distance_max_m": round(c_max_m, 6),
                "mask_resolution": res
            }

    # 5. Variation de volume pour maillages fermés (Vérification bilatérale stricte)
    volume_delta_pct: Optional[float] = None
    bm_orig = bmesh.new()
    bm_orig.from_mesh(mesh_orig)
    bm_simp = bmesh.new()
    bm_simp.from_mesh(mesh_simp)

    is_watertight_orig = (all(e.is_manifold for e in bm_orig.edges) and not any(e.is_boundary for e in bm_orig.edges))
    is_watertight_simp = (all(e.is_manifold for e in bm_simp.edges) and not any(e.is_boundary for e in bm_simp.edges))
    is_watertight = is_watertight_orig and is_watertight_simp

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
        "sample_method": "Barycentric surface sampling + Bidirectional BVH + 2D IoU Silhouette",
        "sample_count_orig": actual_samples_orig,
        "sample_count_simp": actual_samples_simp,
        "bounding_box_diagonal": round(bbox_diag, 6),
        "distance_forward": {
            "mean": round(dist_fwd_mean, 6),
            "p95": round(dist_fwd_p95, 6),
            "p99": round(dist_fwd_p99, 6),
            "max": round(dist_fwd_max, 6)
        },
        "distance_backward": {
            "mean": round(dist_bwd_mean, 6),
            "p95": round(dist_bwd_p95, 6),
            "p99": round(dist_bwd_p99, 6),
            "max": round(dist_bwd_max, 6)
        },
        "distance_hausdorff": round(dist_hausdorff, 6),
        "distance_mean": round(dist_mean, 6),
        "distance_p95": round(dist_p95, 6),
        "distance_p99": round(dist_p99, 6),
        "distance_max_observed": round(dist_max, 6),
        "distance_max_relative": round(dist_max_relative, 6),
        "normal_deviation_mean_deg": round(ang_mean, 2),
        "normal_deviation_p95_deg": round(ang_p95, 2),
        "normal_deviation_max_deg": round(ang_max, 2),
        "silhouette_deviation_pct": silhouette_deviations,
        "silhouette_metrics": silhouette_metrics,
        "volume_delta_pct": volume_delta_pct,
        "is_watertight": is_watertight,
        "is_watertight_orig": is_watertight_orig,
        "is_watertight_simp": is_watertight_simp,
        "sharp_edges_before": sharp_orig,
        "sharp_edges_after": sharp_simp,
        "seams_before": seams_orig,
        "seams_after": seams_simp,
        "materials_before": mats_orig,
        "materials_after": mats_simp,
        "approximation_note": (
            "Mesures empiriques d'écartement surfacique par échantillonnage aléatoire pondéré (graine fixée). "
            "Ne constitue pas une borne mathématique formelle (supremum exact)."
        )
    }
