"""MeshForge - Module de gestion de la topologie (Section 3.4 du CdC).
Prend en charge la conservation par défaut, la triangulation ou la quadrangulation
sans forcer un format et en préservant les attributs existants.
"""

from __future__ import annotations
import bpy
import bmesh
from typing import Dict, Any


def execute_topology(obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Exécute les opérations topologiques selon le choix explicite de l'utilisateur."""
    results: Dict[str, Any] = {
        "status": "SUCCESS",
        "mode": getattr(props, "topology_mode", "KEEP"),
        "log": []
    }

    if not obj or obj.type != 'MESH':
        results["status"] = "ERROR"
        results["log"].append("Objet invalide pour l'opération topologique.")
        return results

    mode = getattr(props, "topology_mode", "KEEP")

    # Si le mode est KEEP, aucune altération de topologie (respect du CdC)
    if mode == 'KEEP':
        results["log"].append("Topologie préservée : aucune conversion requise (mode KEEP).")
        return results

    prev_mode = obj.mode
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    bpy.ops.mesh.select_all(action='SELECT')

    if mode == 'TRIS':
        quad_meth = getattr(props, "triangulate_quad_method", "BEAUTY")
        ngon_meth = getattr(props, "triangulate_ngon_method", "BEAUTY")
        bpy.ops.mesh.quads_convert_to_tris(
            quad_method=quad_meth,
            ngon_method=ngon_meth
        )
        results["log"].append(f"Conversion en triangles effectuée (méthodes: {quad_meth}/{ngon_meth}).")

    elif mode == 'QUADS':
        face_thresh = getattr(props, "quads_face_threshold", 0.698)
        shape_thresh = getattr(props, "quads_shape_threshold", 0.698)
        preserve_attr = getattr(props, "preserve_topology_attributes", True)

        bpy.ops.mesh.tris_convert_to_quads(
            face_threshold=face_thresh,
            shape_threshold=shape_thresh,
            uvs=preserve_attr,
            vcols=preserve_attr,
            seam=preserve_attr,
            sharp=preserve_attr,
            materials=preserve_attr
        )
        results["log"].append(f"Conversion en quads effectuée (préservation attributs: {preserve_attr}).")

    bmesh.update_edit_mesh(obj.data)

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
