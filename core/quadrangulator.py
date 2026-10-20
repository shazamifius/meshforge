"""MeshForge - Module de quadrangulation ciblée et sécurisée (Phase D2.3).
Exécute la fusion de paires de triangles coplanaires en quads en respectant strictement :
1. La compatibilité géométrique et la planéité (angle dièdre contrôlé).
2. La convexité stricte du quad résultant (refus des quads concaves ou repliés).
3. Les coutures UV (seams) et les discontinuités UV d'îlots même non marquées.
4. Les arêtes vives (sharp edges, crease, bevel weights).
5. Les délimitations de matériaux (material index) et d'ombrage (smooth).
6. La sélection gloutonne optimale par score d'orthogonalité et de planéité.
7. La garantie transactionnelle de rollback intégral via MeshSnapshot en cas de déviation d'invariants.
"""

from __future__ import annotations
import bpy
import bmesh
import math
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Set

from .conservative_cleaner import MeshSnapshot
from .topology_diagnosis import diagnose_topology


def quad_orthogonality_score(pts: List[Any]) -> float:
    """Calcule le score d'orthogonalité d'un quad à partir de ses 4 sommets ordonnés.
    Plus les angles intérieurs sont proches de 90° (pi/2 radians), plus le score est proche de 1.0.
    Permet de privilégier les quads rectangulaires/carrés équilibrés plutôt que des trapèzes étirés.
    """
    if len(pts) != 4:
        return 0.0

    angles = []
    for i in range(4):
        p_prev = np.array(pts[(i - 1) % 4])
        p_curr = np.array(pts[i])
        p_next = np.array(pts[(i + 1) % 4])

        v1 = p_prev - p_curr
        v2 = p_next - p_curr
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 < 1e-7 or n2 < 1e-7:
            return 0.0

        cos_a = max(-1.0, min(1.0, float(np.dot(v1, v2) / (n1 * n2))))
        angles.append(math.acos(cos_a))

    # Écart absolu par rapport à 90° (pi/2)
    dev = sum(abs(a - math.pi / 2.0) for a in angles)
    # Écart maximal théorique normalisé (2*pi)
    score = max(0.0, 1.0 - (dev / (2.0 * math.pi)))
    return score


def check_triangle_pair_compatibility(
    f1: bmesh.types.BMFace,
    f2: bmesh.types.BMFace,
    shared_edge: bmesh.types.BMEdge,
    max_angle_deg: float = 15.0,
    compare_uvs: bool = True,
    compare_seams: bool = True,
    compare_sharp: bool = True,
    compare_materials: bool = True,
    compare_colors: bool = True,
    bm: Optional[bmesh.types.BMesh] = None
) -> Tuple[bool, str, float, List[bmesh.types.BMVert]]:
    """Évalue de façon exhaustive si deux triangles partageant une arête peuvent être fusionnés en quad.
    Retourne :
        (is_compatible, refusal_reason, quality_score, ordered_vertices)
    """
    # 1. Vérification que les deux faces sont bien des triangles
    if len(f1.verts) != 3 or len(f2.verts) != 3:
        return False, "NOT_TRIANGLES", 0.0, []

    # 2. Vérification des matériaux
    if compare_materials and (f1.material_index != f2.material_index):
        return False, "MATERIAL_MISMATCH", 0.0, []

    # 3. Vérification de l'ombrage (smooth / flat)
    if f1.smooth != f2.smooth:
        return False, "SMOOTH_MISMATCH", 0.0, []

    # 4. Respect des coutures UV marquées (seams)
    if compare_seams and getattr(shared_edge, "seam", False):
        return False, "SEAM", 0.0, []

    # 5. Respect des arêtes vives (sharp / non-smooth)
    if compare_sharp and not getattr(shared_edge, "smooth", True):
        return False, "SHARP", 0.0, []

    # 6. Respect des plis de subdivision et biseaux
    if bm is not None and len(bm.edges.layers.float) > 0:
        for fl_layer in bm.edges.layers.float:
            if shared_edge[fl_layer] > 0.001:
                return False, "CREASE_OR_BEVEL", 0.0, []

    va = shared_edge.verts[0]
    vb = shared_edge.verts[1]

    # 7. Respect des discontinuités UV (coutures d'îlots même sans drapeau seam)
    if compare_uvs and bm is not None and len(bm.loops.layers.uv) > 0:
        for uv_layer in bm.loops.layers.uv:
            # Récupérer les loops sur va et vb pour f1 et f2
            l1_va = None
            l1_vb = None
            for loop in f1.loops:
                if loop.vert == va:
                    l1_va = loop
                elif loop.vert == vb:
                    l1_vb = loop

            l2_va = None
            l2_vb = None
            for loop in f2.loops:
                if loop.vert == va:
                    l2_va = loop
                elif loop.vert == vb:
                    l2_vb = loop

            if l1_va and l2_va:
                uv1 = l1_va[uv_layer].uv
                uv2 = l2_va[uv_layer].uv
                if (uv1.x - uv2.x) ** 2 + (uv1.y - uv2.y) ** 2 > 1e-8:
                    return False, "UV_DISCONTINUITY", 0.0, []

            if l1_vb and l2_vb:
                uv1 = l1_vb[uv_layer].uv
                uv2 = l2_vb[uv_layer].uv
                if (uv1.x - uv2.x) ** 2 + (uv1.y - uv2.y) ** 2 > 1e-8:
                    return False, "UV_DISCONTINUITY", 0.0, []

    # 8. Respect des discontinuités de couleur (Color Attributes)
    if compare_colors and bm is not None and len(bm.loops.layers.color) > 0:
        for col_layer in bm.loops.layers.color:
            l1_va = next((l for l in f1.loops if l.vert == va), None)
            l2_va = next((l for l in f2.loops if l.vert == va), None)
            if l1_va and l2_va:
                c1 = l1_va[col_layer]
                c2 = l2_va[col_layer]
                dist_sq = sum((c1[i] - c2[i]) ** 2 for i in range(len(c1)))
                if dist_sq > 0.001:
                    return False, "COLOR_DISCONTINUITY", 0.0, []

            l1_vb = next((l for l in f1.loops if l.vert == vb), None)
            l2_vb = next((l for l in f2.loops if l.vert == vb), None)
            if l1_vb and l2_vb:
                c1 = l1_vb[col_layer]
                c2 = l2_vb[col_layer]
                dist_sq = sum((c1[i] - c2[i]) ** 2 for i in range(len(c1)))
                if dist_sq > 0.001:
                    return False, "COLOR_DISCONTINUITY", 0.0, []

    # 9. Planéité et angle dièdre
    n1 = f1.normal
    n2 = f2.normal
    len_n1 = n1.length
    len_n2 = n2.length
    if len_n1 < 1e-7 or len_n2 < 1e-7:
        return False, "DEGENERATE_NORMAL", 0.0, []

    cos_dihedral = max(-1.0, min(1.0, float(n1.dot(n2) / (len_n1 * len_n2))))
    dihedral_deg = math.degrees(math.acos(cos_dihedral))
    if dihedral_deg > max_angle_deg:
        return False, "NON_COPLANAR", 0.0, []

    # 10. Identification des sommets opposés et ordonnancement cyclique du quad
    vc_candidates = [v for v in f1.verts if v not in (va, vb)]
    vd_candidates = [v for v in f2.verts if v not in (va, vb)]
    if not vc_candidates or not vd_candidates:
        return False, "TOPOLOGY_ERROR", 0.0, []

    vc = vc_candidates[0]
    vd = vd_candidates[0]
    if vc == vd:
        return False, "DEGENERATE_DOUBLE", 0.0, []

    # Détermination de l'orientation de l'arête partagée dans f1
    # Dans f1, on trouve le loop à va : s'il pointe vers vb, le sens est va -> vb
    is_va_to_vb_in_f1 = False
    for l in f1.loops:
        if l.vert == va and l.link_loop_next.vert == vb:
            is_va_to_vb_in_f1 = True
            break

    if is_va_to_vb_in_f1:
        # Parcours CCW : vc -> va -> vd -> vb
        ordered_verts = [vc, va, vd, vb]
    else:
        # Parcours CCW : vc -> vb -> vd -> va
        ordered_verts = [vc, vb, vd, va]

    # 11. Vérification de convexité stricte du quad résultant
    # Le quad ne doit avoir aucun angle rentrant (> 180°) ni sommets alignés
    n_avg = (n1 + n2) * 0.5
    if n_avg.length < 1e-7:
        return False, "OPPOSING_NORMALS", 0.0, []
    n_avg.normalize()

    area1 = f1.calc_area()
    area2 = f2.calc_area()
    total_tri_area = area1 + area2
    if total_tri_area < 1e-9:
        return False, "ZERO_AREA", 0.0, []

    epsilon = 1e-7 * total_tri_area
    for i in range(4):
        p0 = ordered_verts[i].co
        p1 = ordered_verts[(i + 1) % 4].co
        p2 = ordered_verts[(i + 2) % 4].co

        v0 = p1 - p0
        v1 = p2 - p1
        cross = v0.cross(v1)
        dot = cross.dot(n_avg)
        if dot <= epsilon:
            # L'angle est concave, plat ou replié
            return False, "CONCAVE_OR_FOLDED", 0.0, []

    # 12. Vérification de stabilité de surface
    # Calcul de l'aire alternative selon l'autre diagonale (vc - vd)
    v_diag = ordered_verts[2].co - ordered_verts[0].co
    v_side1 = ordered_verts[1].co - ordered_verts[0].co
    v_side2 = ordered_verts[3].co - ordered_verts[0].co
    area_alt1 = 0.5 * v_diag.cross(v_side1).length
    area_alt2 = 0.5 * v_diag.cross(v_side2).length
    total_alt_area = area_alt1 + area_alt2

    if abs(total_tri_area - total_alt_area) > 0.02 * total_tri_area:
        return False, "AREA_DIVERGENCE", 0.0, []

    # 13. Calcul du score de qualité combiné (Planéité + Orthogonalité)
    ortho_score = quad_orthogonality_score([v.co for v in ordered_verts])
    planarity_score = math.cos(math.radians(dihedral_deg))
    combined_score = 0.4 * planarity_score + 0.6 * ortho_score

    return True, "COMPATIBLE", combined_score, ordered_verts


def execute_targeted_quadrangulation(
    obj: bpy.types.Object,
    max_angle_deg: float = 15.0,
    compare_uvs: bool = True,
    compare_seams: bool = True,
    compare_sharp: bool = True,
    compare_materials: bool = True,
    compare_colors: bool = True
) -> Dict[str, Any]:
    """Exécute la quadrangulation ciblée et réversible d'un maillage.
    Fusionne de façon optimale et non-destructive les paires de triangles coplanaires.
    Garantit le rollback automatique en cas de déviation géométrique anormale.
    """
    if obj is None or obj.type != 'MESH' or not obj.data:
        return {
            "success": False,
            "error": "Aucun maillage actif valide sélectionné."
        }

    mesh = obj.data
    if getattr(mesh, "is_editmode", False) or (hasattr(obj, "mode") and obj.mode == 'EDIT'):
        return {
            "success": False,
            "error": "L'objet est en mode Édition. Passez en mode Objet avant d'exécuter la quadrangulation."
        }

    start_time = time.perf_counter()

    # 1. Snapshot transactionnel pour garantie de rollback intégrale
    snapshot = MeshSnapshot(mesh)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    initial_face_count = len(bm.faces)
    initial_triangle_count = sum(1 for f in bm.faces if len(f.verts) == 3)
    initial_quad_count = sum(1 for f in bm.faces if len(f.verts) == 4)

    refusals: Dict[str, int] = {
        "NON_COPLANAR": 0,
        "CONCAVE_OR_FOLDED": 0,
        "UV_DISCONTINUITY": 0,
        "SEAM": 0,
        "SHARP": 0,
        "MATERIAL_MISMATCH": 0,
        "SMOOTH_MISMATCH": 0,
        "CREASE_OR_BEVEL": 0,
        "AREA_DIVERGENCE": 0,
        "NOT_TRIANGLES": 0,
        "BOUNDARY": 0,
        "NON_MANIFOLD": 0,
        "ADJACENCY_CONFLICT": 0
    }

    # 2. Examen de toutes les arêtes candidates
    candidates: List[Tuple[float, bmesh.types.BMEdge, bmesh.types.BMFace, bmesh.types.BMFace, List[bmesh.types.BMVert]]] = []

    for edge in bm.edges:
        link_count = len(edge.link_faces)
        if link_count == 1:
            refusals["BOUNDARY"] += 1
            continue
        if link_count > 2:
            refusals["NON_MANIFOLD"] += 1
            continue

        f1, f2 = edge.link_faces[0], edge.link_faces[1]
        is_compat, reason, score, ordered_verts = check_triangle_pair_compatibility(
            f1=f1,
            f2=f2,
            shared_edge=edge,
            max_angle_deg=max_angle_deg,
            compare_uvs=compare_uvs,
            compare_seams=compare_seams,
            compare_sharp=compare_sharp,
            compare_materials=compare_materials,
            compare_colors=compare_colors,
            bm=bm
        )

        if is_compat:
            candidates.append((score, edge, f1, f2, ordered_verts))
        else:
            if reason in refusals:
                refusals[reason] += 1
            else:
                refusals[reason] = 1

    # 3. Sélection gloutonne disjointe (aucun triangle ne peut fusionner deux fois)
    candidates.sort(key=lambda item: item[0], reverse=True)

    used_faces: Set[bmesh.types.BMFace] = set()
    edges_to_dissolve: List[bmesh.types.BMEdge] = []

    for score, edge, f1, f2, ordered_verts in candidates:
        if f1 in used_faces or f2 in used_faces:
            refusals["ADJACENCY_CONFLICT"] += 1
            continue

        used_faces.add(f1)
        used_faces.add(f2)
        edges_to_dissolve.append(edge)

    # 4. Si aucune arête ne peut être fusionnée
    if not edges_to_dissolve:
        bm.free()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": True,
            "quads_created": 0,
            "triangles_merged": 0,
            "refusals": refusals,
            "initial_faces": initial_face_count,
            "final_faces": initial_face_count,
            "initial_quads": initial_quad_count,
            "final_quads": initial_quad_count,
            "execution_time_ms": elapsed_ms,
            "message": "Aucune paire de triangles compatible pour la quadrangulation.",
            "post_diagnosis": diagnose_topology(obj)
        }

    # 5. Dissolution sécurisée des arêtes sélectionnées
    try:
        bmesh.ops.dissolve_edges(bm, edges=edges_to_dissolve, use_verts=False, use_face_split=False)
    except Exception as e:
        bm.free()
        snapshot.restore(mesh)
        return {
            "success": False,
            "rolled_back": True,
            "error": f"Erreur lors de la dissolution bmesh : {str(e)}. Rollback effectué."
        }

    # 6. Vérification transactionnelle des invariants géométriques
    final_area = sum(f.calc_area() for f in bm.faces)
    initial_area = sum(p.area for p in snapshot.backup_mesh.polygons)

    if initial_area > 1e-6:
        area_diff_ratio = abs(final_area - initial_area) / initial_area
        if area_diff_ratio > 0.005:  # Plus de 0.5% de déviation
            bm.free()
            snapshot.restore(mesh)
            return {
                "success": False,
                "rolled_back": True,
                "error": f"Déviation anormale de la surface totale ({area_diff_ratio*100:.2f}%). Rollback automatique déclenché."
            }

    # 7. Écriture dans le maillage Blender
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    post_diag = diagnose_topology(obj)

    final_quad_count = sum(1 for p in mesh.polygons if len(p.vertices) == 4)
    final_triangle_count = sum(1 for p in mesh.polygons if len(p.vertices) == 3)

    return {
        "success": True,
        "rolled_back": False,
        "quads_created": len(edges_to_dissolve),
        "triangles_merged": len(edges_to_dissolve) * 2,
        "initial_triangles": initial_triangle_count,
        "final_triangles": final_triangle_count,
        "initial_quads": initial_quad_count,
        "final_quads": final_quad_count,
        "refusals": refusals,
        "execution_time_ms": elapsed_ms,
        "inventory": snapshot.inventory,
        "post_diagnosis": post_diag
    }
