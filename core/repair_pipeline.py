"""MeshForge - Module de réparation de maillage (Section 3.1 du CdC).
Prend en charge la suppression des géométries lâches, des doublons (absolu/relatif)
et des faces dégénérées/nulles.
"""

from __future__ import annotations
import bpy
import bmesh
from typing import Dict, Any


def execute_repair(obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Exécute les opérations de la section Repair sur l'objet actif.
    L'objet doit être en mode Objet ou Edition; la fonction s'assure d'un état propre.
    """
    results: Dict[str, Any] = {
        "status": "SUCCESS",
        "loose_removed": False,
        "doubles_removed": 0,
        "degenerate_dissolved": False,
        "dispensables_cleaned": False,
        "log": []
    }

    if not obj or obj.type != 'MESH':
        results["status"] = "ERROR"
        results["log"].append("Objet invalide pour la réparation.")
        return results

    # Passage temporaire en mode Édition pour appliquer les opérateurs de maillage
    prev_mode = obj.mode
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    bm = bmesh.from_edit_mesh(obj.data)

    # 1. Fusion des sommets doublons (Doubles)
    if getattr(props, "repair_doubles", True):
        threshold = getattr(props, "doubles_tolerance", 0.0001)
        if getattr(props, "doubles_relative", False):
            bbox_dim = max(obj.dimensions) if hasattr(obj, "dimensions") else 1.0
            factor = getattr(props, "doubles_relative_factor", 0.0001)
            threshold = max(1e-7, float(bbox_dim * factor))

        initial_verts = len(bm.verts)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(
            threshold=threshold,
            use_unselected=False
        )
        bmesh.update_edit_mesh(obj.data)
        bm = bmesh.from_edit_mesh(obj.data)
        merged = initial_verts - len(bm.verts)
        results["doubles_removed"] = merged
        results["log"].append(f"Doublons fusionnés : {merged} sommets (seuil: {threshold:.6f}m).")

    # 2. Suppression des faces dégénérées / d'aire nulle (Zero Faces)
    if getattr(props, "repair_zero_faces", True):
        threshold = getattr(props, "zero_faces_threshold", 0.000001)
        initial_faces = len(bm.faces)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.dissolve_degenerate(threshold=threshold)
        bmesh.update_edit_mesh(obj.data)
        bm = bmesh.from_edit_mesh(obj.data)
        delta_f = initial_faces - len(bm.faces)
        results["degenerate_dissolved"] = True
        results["log"].append(f"Faces dégénérées dissoutes : {delta_f} (seuil aire: {threshold:.8f}).")

    # 3. Suppression des géométries isolées (Loose Geometry)
    if getattr(props, "repair_loose_geometry", True):
        initial_verts = len(bm.verts)
        initial_edges = len(bm.edges)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete_loose(
            use_verts=getattr(props, "loose_verts", True),
            use_edges=getattr(props, "loose_edges", True),
            use_faces=getattr(props, "loose_faces", False)
        )
        bmesh.update_edit_mesh(obj.data)
        bm = bmesh.from_edit_mesh(obj.data)
        delta_v = initial_verts - len(bm.verts)
        delta_e = initial_edges - len(bm.edges)
        results["loose_removed"] = True
        results["log"].append(f"Éléments isolés supprimés : {delta_v} sommets, {delta_e} arêtes.")

    # 4. Simplification prudente des redondances (Dispensables)
    if getattr(props, "repair_dispensables", False):
        angle = getattr(props, "dispensable_angle", 0.001745)  # ~0.1 deg
        initial_faces = len(bm.faces)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.dissolve_limited(angle_limit=angle, use_dissolve_boundaries=False)
        bmesh.update_edit_mesh(obj.data)
        bm = bmesh.from_edit_mesh(obj.data)
        delta_disp = initial_faces - len(bm.faces)
        results["dispensables_cleaned"] = True
        results["log"].append(f"Arêtes/faces redondantes nettoyées : {delta_disp}.")

    bmesh.update_edit_mesh(obj.data)

    # Restauration du mode d'origine
    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
