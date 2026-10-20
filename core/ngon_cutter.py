"""MeshForge - Module de découpe ciblée et sécurisée des N-gones (Phase D2.2).
Traite distinctement les polygones selon leur morphologie géométrique réelle :
1. N-gones Convexes (Triangulation équilibrée Beauty évitant les aiguilles)
2. N-gones Concaves (Ear-clipping orienté respectant strictement les angles rentrants)
3. N-gones Ambigus / Auto-intersectants / Gauches (Refus propre et sélection explicite)

Garantit la préservation des coordonnées UV par boucle, des matériaux multiples,
et contrôle les déviations d'aire ou triangles dégénérés avec rollback automatique.
"""

from __future__ import annotations
import bpy
import bmesh
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from .conservative_cleaner import MeshSnapshot
from .topology_diagnosis import diagnose_topology


def _segments_intersect_2d(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float]
) -> bool:
    """Détermine si deux segments 2D [p1, p2] et [p3, p4] se croisent strictement en 2D."""
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    intersect = (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))
    return intersect


def classify_ngon(face: bmesh.types.BMFace) -> Dict[str, Any]:
    """Analyse géométrique approfondie d'un N-gone (>= 5 sommets).
    Distingue formellement :
    - 'CONVEX' : N-gone convexe quasi-plan (triangulation équilibrée Beauty sûre)
    - 'CONCAVE' : N-gone concave à angles rentrants (ear-clipping orienté)
    - 'AMBIGUOUS' : N-gone auto-intersectant (bow-tie) ou gauche non-plan (refus propre requis)
    """
    v_count = len(face.verts)
    if v_count < 5:
        return {
            "valid": False,
            "category": "NOT_NGON",
            "vertex_count": v_count,
            "reason": "La face possède 4 sommets ou moins."
        }

    try:
        face.normal_update()
    except Exception:
        pass

    area = face.calc_area()
    center = face.calc_center_bounds()
    norm = face.normal

    pts_3d = [v.co for v in face.verts]

    # 1. Test de planéité
    dists = [abs((p - center).dot(norm)) for p in pts_3d]
    max_dist = max(dists) if dists else 0.0

    coords_np = np.array([list(p) for p in pts_3d], dtype=np.float64)
    bbox_span = np.max(coords_np, axis=0) - np.min(coords_np, axis=0)
    diameter = max(1e-6, float(np.linalg.norm(bbox_span)))
    planarity_ratio = max_dist / diameter
    is_non_planar = (planarity_ratio > 0.04)
    is_severely_warped = (planarity_ratio > 0.15)

    # 2. Construction d'une base orthonormée 2D locale pour projection
    axis = np.array([0.0, 0.0, 1.0]) if abs(norm.z) < 0.9 else np.array([1.0, 0.0, 0.0])
    u_vec = np.cross(axis, norm)
    u_len = np.linalg.norm(u_vec)
    if u_len < 1e-6:
        u_vec = np.array([1.0, 0.0, 0.0])
    else:
        u_vec = u_vec / u_len
    v_vec = np.cross(norm, u_vec)
    v_vec = v_vec / max(1e-6, np.linalg.norm(v_vec))

    pts_2d = [
        (float(np.dot(p - center, u_vec)), float(np.dot(p - center, v_vec)))
        for p in pts_3d
    ]

    # 3. Test d'auto-intersection 2D (Bow-tie / boucle croisée en 8)
    is_self_intersecting = False
    for i in range(v_count):
        p1 = pts_2d[i]
        p2 = pts_2d[(i + 1) % v_count]
        for j in range(i + 2, v_count):
            if i == 0 and j == v_count - 1:
                continue
            p3 = pts_2d[j]
            p4 = pts_2d[(j + 1) % v_count]
            if _segments_intersect_2d(p1, p2, p3, p4):
                is_self_intersecting = True
                break
        if is_self_intersecting:
            break

    # 4. Test d'angles rentrants (Concavité)
    signed_area_2x = sum(
        pts_2d[i][0] * pts_2d[(i + 1) % v_count][1] - pts_2d[(i + 1) % v_count][0] * pts_2d[i][1]
        for i in range(v_count)
    )
    ccw_orientation = (signed_area_2x >= 0.0)

    reflex_corners = 0
    for i in range(v_count):
        p0 = pts_2d[i - 1]
        p1 = pts_2d[i]
        p2 = pts_2d[(i + 1) % v_count]
        cross = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
        if ccw_orientation and cross < -1e-6:
            reflex_corners += 1
        elif not ccw_orientation and cross > 1e-6:
            reflex_corners += 1

    is_concave = (reflex_corners > 0)

    # 5. Rapport d'aspect des arêtes
    edge_lens = [e.calc_length() for e in face.edges]
    max_e = max(edge_lens) if edge_lens else 1.0
    min_e = min(edge_lens) if edge_lens else 1.0
    aspect_ratio = max_e / max(1e-7, min_e)
    is_needle = (aspect_ratio > 8.0)

    # 6. Catégorisation et arbitrage
    if is_self_intersecting:
        category = 'AMBIGUOUS'
        reason = "N-gone auto-intersectant (bords croisés en 8 / nœud papillon). Découpe automatique refusée."
    elif is_non_planar and is_concave:
        category = 'AMBIGUOUS'
        reason = f"N-gone gauche non-plan (écart {max_dist*1000:.2f} mm) et concave. Découpe automatique refusée pour éviter la création de faces retournées."
    elif is_severely_warped:
        category = 'AMBIGUOUS'
        reason = f"N-gone fortement gauchi en selle (torsion {planarity_ratio*100:.1f}%). Découpe automatique refusée."
    elif is_concave:
        category = 'CONCAVE'
        reason = f"N-gone concave ({reflex_corners} angle(s) rentrant(s)). Triangulation par Ear-Clipping orienté requise."
    else:
        category = 'CONVEX'
        reason = f"N-gone convexe régulier ({v_count} sommets). Triangulation équilibrée Beauty recommandée."

    return {
        "valid": True,
        "face_index": face.index,
        "vertex_count": v_count,
        "category": category,
        "reason": reason,
        "area": area,
        "center": tuple(center),
        "is_concave": is_concave,
        "is_self_intersecting": is_self_intersecting,
        "is_non_planar": is_non_planar,
        "is_severely_warped": is_severely_warped,
        "is_needle": is_needle,
        "aspect_ratio": round(aspect_ratio, 2),
        "planarity_ratio": round(planarity_ratio, 4)
    }


def execute_ngon_cut(
    obj: bpy.types.Object,
    cut_convex: bool = True,
    cut_concave: bool = True,
    allow_ambiguous: bool = False,
    selected_only: bool = False,
    target_mode: str = 'HYBRID_CLEANUP'
) -> Dict[str, Any]:
    """Exécute la découpe ciblée des N-gones selon leur catégorie morphologique réelle.
    - Convexes : Triangulation Beauty équilibrée (Delaunay-like)
    - Concaves : Triangulation Ear-Clipping orienté
    - Ambigus : Refus propre et sélection pour découpe manuelle au couteau
    Garantit la préservation des UVs et matériaux, et applique un rollback automatique
    en cas d'invariant violé ou d'erreur.
    """
    t0 = time.perf_counter()

    result: Dict[str, Any] = {
        "success": False,
        "rolled_back": False,
        "object_name": obj.name if obj else "Inconnu",
        "total_ngons_found": 0,
        "convex_cut": 0,
        "concave_cut": 0,
        "ambiguous_cut": 0,
        "refused_ngons": [],
        "triangles_created": 0,
        "area_before": 0.0,
        "area_after": 0.0,
        "area_difference_pct": 0.0,
        "post_diagnosis": {},
        "execution_time_ms": 0.0,
        "logs": [],
        "warnings": [],
        "error": None
    }

    if not obj or obj.type != 'MESH' or not obj.data:
        result["error"] = "Objet sélectionné invalide ou sans maillage."
        return result

    if obj.mode != 'OBJECT' or getattr(obj.data, "is_editmode", False):
        result["error"] = "L'objet est en mode Édition. Veuillez repasser en mode Objet (Touche Tab) pour exécuter la découpe sans risquer de corrompre les données non validées."
        return result

    mesh = obj.data

    # 1. Snapshot mémoire intégral
    snapshot = MeshSnapshot(mesh)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    try:
        # 2. Inventaire et classification géométrique des N-gones
        ngon_faces = [f for f in bm.faces if len(f.verts) >= 5]
        if selected_only:
            ngon_faces = [f for f in ngon_faces if f.select]

        result["total_ngons_found"] = len(ngon_faces)
        if len(ngon_faces) == 0:
            result["success"] = True
            result["logs"].append("Aucun N-gone détecté sur cet objet.")
            bm.free()
            snapshot.free()
            return result

        initial_total_area = sum(f.calc_area() for f in bm.faces)
        result["area_before"] = initial_total_area

        # Classifier chaque N-gone
        convex_faces: List[bmesh.types.BMFace] = []
        concave_faces: List[bmesh.types.BMFace] = []
        ambiguous_faces: List[bmesh.types.BMFace] = []

        for f in ngon_faces:
            diag_f = classify_ngon(f)
            cat = diag_f["category"]

            if cat == 'AMBIGUOUS':
                if not allow_ambiguous:
                    result["refused_ngons"].append({
                        "face_index": f.index,
                        "center": diag_f["center"],
                        "reason": diag_f["reason"],
                        "category": "AMBIGUOUS"
                    })
                    result["warnings"].append(
                        f"N-gone #{f.index} refusé : {diag_f['reason']}"
                    )
                else:
                    ambiguous_faces.append(f)
            elif cat == 'CONCAVE':
                if cut_concave:
                    concave_faces.append(f)
                else:
                    result["refused_ngons"].append({
                        "face_index": f.index,
                        "center": diag_f["center"],
                        "reason": "Découpe des N-gones concaves désactivée par l'utilisateur.",
                        "category": "CONCAVE"
                    })
            elif cat == 'CONVEX':
                if cut_convex:
                    convex_faces.append(f)
                else:
                    result["refused_ngons"].append({
                        "face_index": f.index,
                        "center": diag_f["center"],
                        "reason": "Découpe des N-gones convexes désactivée par l'utilisateur.",
                        "category": "CONVEX"
                    })

        total_to_cut = len(convex_faces) + len(concave_faces) + len(ambiguous_faces)

        # Si aucune face n'est éligible à la découpe
        if total_to_cut == 0:
            result["success"] = True
            result["logs"].append(
                f"{len(result['refused_ngons'])} N-gone(s) examiné(s), aucun n'a été découpé (refus ou options désactivées)."
            )
            # Sélectionner les faces refusées sur le maillage d'origine pour guidage manuel
            refused_indices = {r["face_index"] for r in result["refused_ngons"]}
            for p in mesh.polygons:
                p.select = (p.index in refused_indices)
            bm.free()
            snapshot.free()
            return result

        # 3. Exécution de la triangulation ciblée différenciée
        new_faces: List[bmesh.types.BMFace] = []

        # A. N-gones convexes : BEAUTY (Delaunay-like équilibré)
        if convex_faces:
            res_convex = bmesh.ops.triangulate(
                bm,
                faces=convex_faces,
                quad_method='BEAUTY',
                ngon_method='BEAUTY'
            )
            new_faces.extend(res_convex.get("faces", []))
            result["convex_cut"] = len(convex_faces)

        # B. N-gones concaves : EAR_CLIP (respect strict des angles rentrants)
        if concave_faces:
            res_concave = bmesh.ops.triangulate(
                bm,
                faces=concave_faces,
                quad_method='BEAUTY',
                ngon_method='EAR_CLIP'
            )
            new_faces.extend(res_concave.get("faces", []))
            result["concave_cut"] = len(concave_faces)

        # C. N-gones ambigus forcés (si expressément autorisé)
        if ambiguous_faces and allow_ambiguous:
            res_ambig = bmesh.ops.triangulate(
                bm,
                faces=ambiguous_faces,
                quad_method='BEAUTY',
                ngon_method='EAR_CLIP'
            )
            new_faces.extend(res_ambig.get("faces", []))
            result["ambiguous_cut"] = len(ambiguous_faces)

        result["triangles_created"] = len(new_faces)

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # 4. Contrôle des invariants de sécurité post-découpe
        final_total_area = sum(f.calc_area() for f in bm.faces)
        result["area_after"] = final_total_area
        area_diff = abs(final_total_area - initial_total_area)
        area_pct = (area_diff / max(1e-6, initial_total_area)) * 100.0
        result["area_difference_pct"] = round(area_pct, 4)

        # Invariant 1 : L'aire totale ne doit pas diverger de plus de 0.5%
        if area_pct > 0.5 and not allow_ambiguous:
            raise ValueError(
                f"Violation d'invariant : variation d'aire excessive ({area_pct:.2f}%). "
                "La triangulation a provoqué un chevauchement ou un effondrement de surface."
            )

        # Invariant 2 : Aucune face dégénérée d'aire nulle ne doit être générée
        for nf in new_faces:
            if nf.calc_area() <= 1e-8:
                raise ValueError("Violation d'invariant : création d'une face dégénérée d'aire nulle.")

        # Invariant 3 : Aucune coordonnée corrompue
        for v in bm.verts:
            if not np.all(np.isfinite(v.co)):
                raise ValueError("Violation d'invariant : coordonnées corrompues (NaN).")

        # 5. Appliquer les modifications au maillage
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        snapshot.free()

        # 6. Si des cas ambigus ont été refusés, les sélectionner pour couteau manuel
        if result["refused_ngons"]:
            refused_indices = {r["face_index"] for r in result["refused_ngons"]}
            for p in mesh.polygons:
                p.select = (p.index in refused_indices)

        # 7. Relancer le diagnostic topologique
        post_diag = diagnose_topology(obj, mode=target_mode)
        result["post_diagnosis"] = post_diag
        result["success"] = True
        result["execution_time_ms"] = (time.perf_counter() - t0) * 1000.0

        result["logs"].append(
            f"Découpe terminée : {result['convex_cut']} N-gones convexes, "
            f"{result['concave_cut']} N-gones concaves découpés en {result['triangles_created']} triangles. "
            f"{len(result['refused_ngons'])} N-gones ambigus refusés."
        )

    except Exception as e:
        # Rollback automatique en cas d'erreur ou d'invariant violé
        bm.free()
        ok_restore = snapshot.restore(mesh)
        snapshot.free()
        result["success"] = False
        result["rolled_back"] = ok_restore
        result["error"] = str(e)
        result["logs"].append(f"ÉCHEC ET ROLLBACK DÉCLENCHÉ : {e}. Le maillage a été restauré dans son état initial.")
        result["execution_time_ms"] = (time.perf_counter() - t0) * 1000.0

    return result
