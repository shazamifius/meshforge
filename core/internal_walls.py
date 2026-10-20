"""MeshForge - Module de détection et traitement des parois internes (Phase D2.4).
Distingue formellement et avec prudence :
1. Les parois internes mitoyennes strictes (Strict Internal Walls) :
   Faces entièrement occluses reliant deux cellules fermées dont la suppression
   guérit les arêtes non-manifold sans créer aucune frontière ouverte (aucun trou).
2. Les jonctions de surface et ailerons (T-Junctions / Fins) :
   Surfaces rattachées formant une jonction en T mais possédant des bords libres
   ou dont le retrait ouvrirait un trou dans la surface (aucune suppression automatique).
3. Les intersections complexes (Complex Junctions) :
   Carrefours à 4 faces ou plus nécessitant une décision manuelle.

Fournit une garantie transactionnelle intégrale avec MeshSnapshot et rollback
automatique en cas de violation d'invariant géométrique.
"""

from __future__ import annotations
import bpy
import bmesh
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Set

from .conservative_cleaner import MeshSnapshot
from .topology_diagnosis import diagnose_topology


def classify_non_manifold_faces(bm: bmesh.types.BMMesh) -> Dict[str, Any]:
    """Analyse topologique approfondie de toutes les faces connectées à des arêtes non-manifold.
    Distingue rigoureusement :
    - 'STRICT_INTERNAL_WALL' : Faces de cloison mitoyenne dont la suppression guérit la non-manifoldité sans ouvrir de trou.
    - 'T_JUNCTION_OR_FIN' : Surfaces ouvertes attachées (ailerons, plans) qu'il ne faut PAS supprimer automatiquement.
    - 'COMPLEX_JUNCTION' : Intersections complexes à 4 faces ou plus.
    """
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    nm_edges = {e for e in bm.edges if len(e.link_faces) >= 3}
    if not nm_edges:
        return {
            "has_non_manifold": False,
            "strict_internal_faces": [],
            "t_junction_faces": [],
            "complex_junction_faces": [],
            "strict_clusters_count": 0,
            "total_non_manifold_edges": 0,
            "healed_edges_count": 0,
            "strict_wall_center": (0.0, 0.0, 0.0),
            "area_savings": 0.0
        }

    # Étape 1 : Candidats initiaux
    # Une paroi interne mitoyenne ne peut avoir AUCUNE arête exposée à l'air libre (len == 1)
    candidates: Set[bmesh.types.BMFace] = set()
    for e in nm_edges:
        for f in e.link_faces:
            if not any(len(ed.link_faces) == 1 for ed in f.edges):
                candidates.add(f)

    # Étape 2 : Élagage topologique strict (Pruning)
    # Si une face candidate partage une arête 2-manifold avec une face extérieure (non-candidate),
    # alors sa suppression réduirait cette arête à 1 face, créant un trou dans la coque externe !
    # Une telle face fait partie de la coque externe et doit être retirée des candidats.
    changed = True
    while changed:
        changed = False
        to_remove = set()
        for f in candidates:
            for ed in f.edges:
                if len(ed.link_faces) == 2:
                    other_f = [lf for lf in ed.link_faces if lf != f][0]
                    if other_f not in candidates:
                        to_remove.add(f)
                        break
        if to_remove:
            candidates -= to_remove
            changed = True

    # Étape 3 : Décomposition en clusters et vérification des conditions aux limites
    strict_internal_faces: List[int] = []
    strict_clusters_count = 0
    healed_edges_set: Set[bmesh.types.BMEdge] = set()
    total_area_savings = 0.0
    strict_centers: List[np.ndarray] = []

    unvisited = set(candidates)
    while unvisited:
        start_f = unvisited.pop()
        cluster: Set[bmesh.types.BMFace] = {start_f}
        queue = [start_f]

        while queue:
            curr_f = queue.pop()
            for ed in curr_f.edges:
                for lf in ed.link_faces:
                    if lf in unvisited:
                        unvisited.remove(lf)
                        cluster.add(lf)
                        queue.append(lf)

        # Frontière du cluster
        cluster_boundary: Dict[bmesh.types.BMEdge, List[bmesh.types.BMFace]] = {}
        for f in cluster:
            for ed in f.edges:
                out_faces = [lf for lf in ed.link_faces if lf not in cluster]
                if out_faces:
                    cluster_boundary[ed] = out_faces

        # THÉORÈME DE LA PAROI MITOYENNE FERMÉE :
        # Le cluster est une paroi mitoyenne stricte si et seulement si pour TOUTE arête frontière,
        # le nombre de faces extérieures est EXACTEMENT 2.
        # Ainsi, la suppression du cluster laisse chaque arête frontière avec exactement 2 faces (2-manifold)
        # et ne crée aucun trou (0 arête frontière créée) !
        if cluster_boundary and all(len(out) == 2 for out in cluster_boundary.values()):
            strict_internal_faces.extend([f.index for f in cluster])
            strict_clusters_count += 1
            for ed in cluster_boundary.keys():
                healed_edges_set.add(ed)
            for f in cluster:
                total_area_savings += f.calc_area()
                strict_centers.append(np.array(f.calc_center_bounds()))

    # Étape 4 : Détection des jonctions en T et ailerons
    strict_set = set(strict_internal_faces)
    t_junction_faces: List[int] = []
    complex_junction_faces: List[int] = []

    for e in nm_edges:
        for f in e.link_faces:
            if f.index not in strict_set:
                has_open_edge = any(len(ed.link_faces) == 1 for ed in f.edges)
                if has_open_edge:
                    if f.index not in t_junction_faces:
                        t_junction_faces.append(f.index)
                else:
                    if f.index not in complex_junction_faces:
                        complex_junction_faces.append(f.index)

    if strict_centers:
        mean_center = tuple(np.mean(strict_centers, axis=0))
    else:
        mean_center = (0.0, 0.0, 0.0)

    return {
        "has_non_manifold": True,
        "strict_internal_faces": strict_internal_faces,
        "t_junction_faces": t_junction_faces,
        "complex_junction_faces": complex_junction_faces,
        "strict_clusters_count": strict_clusters_count,
        "total_non_manifold_edges": len(nm_edges),
        "healed_edges_count": len(healed_edges_set),
        "strict_wall_center": mean_center,
        "area_savings": total_area_savings
    }


def detect_internal_walls(obj: bpy.types.Object) -> Dict[str, Any]:
    """Exécute un diagnostic exhaustif et strictement en lecture seule des parois internes.
    Retourne les classifications de faces et les coordonnées monde pour le zoom d'inspection.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {"valid": False, "error": "Objet invalide ou non-maillage."}

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    diag = classify_non_manifold_faces(bm)
    bm.free()

    # Transformation du centre en coordonnées monde
    matrix_world = obj.matrix_world
    local_c = diag["strict_wall_center"]
    world_c = tuple(matrix_world @ bpy.types.mathutils.Vector(local_c)) if hasattr(bpy.types, "mathutils") else local_c

    diag["valid"] = True
    diag["world_center"] = world_c
    return diag


def execute_remove_internal_walls(
    obj: bpy.types.Object,
    remove_strict_only: bool = True,
    selected_only: bool = False
) -> Dict[str, Any]:
    """Exécute la suppression prudente et sécurisée des parois internes mitoyennes.
    Garantit le rollback automatique via MeshSnapshot si un invariant critique
    (ouverture de trou, augmentation de non-manifoldité) est violé.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {"success": False, "error": "Objet invalide ou non-maillage."}

    mesh = obj.data
    if getattr(mesh, "is_editmode", False) or (hasattr(obj, "mode") and obj.mode == 'EDIT'):
        return {
            "success": False,
            "error": "L'objet est en mode Édition. Passez en mode Objet avant d'exécuter la suppression."
        }

    start_time = time.perf_counter()

    # 1. Snapshot transactionnel préventif
    snapshot = MeshSnapshot(mesh)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    initial_face_count = len(bm.faces)
    initial_boundary_edges = sum(1 for e in bm.edges if e.is_boundary)
    initial_nm_edges = sum(1 for e in bm.edges if len(e.link_faces) >= 3)
    initial_area = sum(f.calc_area() for f in bm.faces)

    # 2. Analyse et identification formelle
    classification = classify_non_manifold_faces(bm)
    strict_indices = set(classification["strict_internal_faces"])

    if not strict_indices:
        bm.free()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": True,
            "rolled_back": False,
            "faces_removed": 0,
            "healed_edges": 0,
            "boundaries_created": 0,
            "message": "Aucune paroi interne mitoyenne stricte détectée.",
            "execution_time_ms": elapsed_ms,
            "post_diagnosis": diagnose_topology(obj)
        }

    # 3. Filtrage des faces à supprimer
    faces_to_delete: List[bmesh.types.BMFace] = []
    for f in bm.faces:
        if f.index in strict_indices:
            if selected_only and not f.select:
                continue
            faces_to_delete.append(f)

    if not faces_to_delete:
        bm.free()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "success": True,
            "rolled_back": False,
            "faces_removed": 0,
            "healed_edges": 0,
            "boundaries_created": 0,
            "message": "Aucune paroi interne sélectionnée pour la suppression.",
            "execution_time_ms": elapsed_ms,
            "post_diagnosis": diagnose_topology(obj)
        }

    deleted_area = sum(f.calc_area() for f in faces_to_delete)
    deleted_count = len(faces_to_delete)

    # 4. Suppression prudente des faces
    try:
        bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES_ONLY')

        # Nettoyage des arêtes filaires résiduelles créées par la suppression
        bm.edges.ensure_lookup_table()
        residual_wire_edges = [e for e in bm.edges if not e.link_faces]
        if residual_wire_edges:
            bmesh.ops.delete(bm, geom=residual_wire_edges, context='EDGES')

        # Nettoyage des sommets orphelins résiduels
        bm.verts.ensure_lookup_table()
        residual_loose_verts = [v for v in bm.verts if not v.link_edges]
        if residual_loose_verts:
            bmesh.ops.delete(bm, geom=residual_loose_verts, context='VERTS')

    except Exception as e:
        bm.free()
        snapshot.restore(mesh)
        return {
            "success": False,
            "rolled_back": True,
            "error": f"Erreur lors de la suppression bmesh : {str(e)}. Rollback effectué."
        }

    # 5. VÉRIFICATION RIGOUREUSE DES INVARIANTS GÉOMÉTRIQUES POST-SUPPRESSION
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    final_boundary_edges = sum(1 for e in bm.edges if e.is_boundary)
    final_nm_edges = sum(1 for e in bm.edges if len(e.link_faces) >= 3)
    final_area = sum(f.calc_area() for f in bm.faces)

    # Invariant A : Aucune nouvelle frontière ouverte ne doit avoir été créée !
    if final_boundary_edges > initial_boundary_edges:
        bm.free()
        snapshot.restore(mesh)
        return {
            "success": False,
            "rolled_back": True,
            "error": (
                f"Violation d'invariant critique : {final_boundary_edges - initial_boundary_edges} "
                "arête(s) de frontière ouverte (trou) créée(s). Rollback automatique effectué."
            )
        }

    # Invariant B : La non-manifoldité doit avoir diminué
    if final_nm_edges > initial_nm_edges:
        bm.free()
        snapshot.restore(mesh)
        return {
            "success": False,
            "rolled_back": True,
            "error": "Violation d'invariant : augmentation anormale de la non-manifoldité. Rollback automatique."
        }

    # Invariant C : Stabilité de la surface externe restante
    expected_area = initial_area - deleted_area
    if initial_area > 1e-6:
        area_deviation = abs(final_area - expected_area) / initial_area
        if area_deviation > 0.005:  # Tolérance de 0.5%
            bm.free()
            snapshot.restore(mesh)
            return {
                "success": False,
                "rolled_back": True,
                "error": f"Déviation inattendue de surface externe ({area_deviation*100:.2f}%). Rollback automatique."
            }

    # 6. Écriture définitive dans le maillage Blender
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    post_diag = diagnose_topology(obj)
    healed_edges = initial_nm_edges - final_nm_edges

    return {
        "success": True,
        "rolled_back": False,
        "faces_removed": deleted_count,
        "initial_faces": initial_face_count,
        "final_faces": len(mesh.polygons),
        "healed_edges": healed_edges,
        "boundaries_created": max(0, final_boundary_edges - initial_boundary_edges),
        "area_removed": deleted_area,
        "execution_time_ms": elapsed_ms,
        "post_diagnosis": post_diag,
        "inventory": snapshot.inventory
    }
