"""MeshForge - Module de dissolution et simplification coplanaire (Section 3.3 du CdC).
Réduit les régions planes sous un seuil angulaire contrôlé avec préservation
stricte des arêtes vives, coutures UV, matériaux et frontières.
"""

from __future__ import annotations
import bpy
import bmesh
import math
from typing import Dict, Any, Set


def execute_dissolve(obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Exécute la simplification par dissolution limitée sur l'objet sélectionné."""
    results: Dict[str, Any] = {
        "status": "SUCCESS",
        "faces_before": 0,
        "faces_after": 0,
        "delta_faces": 0,
        "log": []
    }

    if not obj or obj.type != 'MESH':
        results["status"] = "ERROR"
        results["log"].append("Objet invalide pour la dissolution.")
        return results

    prev_mode = obj.mode
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    bm = bmesh.from_edit_mesh(obj.data)
    initial_faces = len(bm.faces)
    results["faces_before"] = initial_faces

    # Récupération des paramètres
    angle_deg = getattr(props, "dissolve_angle", 5.0)
    angle_rad = math.radians(angle_deg)
    use_boundaries = not getattr(props, "preserve_boundaries", True)

    # Délimiteurs pour la protection des attributs
    delimiters: Set[str] = set()
    if getattr(props, "preserve_sharp", True):
        delimiters.add('SHARP')
    if getattr(props, "preserve_seams", True):
        delimiters.add('SEAM')
    if getattr(props, "preserve_materials", True):
        delimiters.add('MATERIAL')
    if getattr(props, "preserve_uvs", True):
        delimiters.add('UV')

    mode = getattr(props, "dissolve_mode", "BALANCED")
    if mode == 'CAREFUL':
        # En mode prudent, on restreint l'angle à max 2 degrés
        angle_rad = min(angle_rad, math.radians(2.0))
        delimiters.update({'SHARP', 'SEAM', 'MATERIAL', 'UV'})
    elif mode == 'AGGRESSIVE':
        # En mode agressif, l'angle configuré est utilisé sans forcer tous les délimiteurs
        pass

    try:
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.dissolve_limited(
            angle_limit=angle_rad,
            use_dissolve_boundaries=use_boundaries,
            delimit=delimiters
        )
        bmesh.update_edit_mesh(obj.data)
        bm = bmesh.from_edit_mesh(obj.data)
        final_faces = len(bm.faces)
        results["faces_after"] = final_faces
        results["delta_faces"] = initial_faces - final_faces

        # Inspection qualitative des faces créées (détection des grands N-gones)
        max_verts = max((len(f.verts) for f in bm.faces), default=0)
        giant_ngons = sum(1 for f in bm.faces if len(f.verts) >= 16)
        results["max_face_vertices"] = max_verts
        results["giant_ngons_count"] = giant_ngons

        log_msg = (
            f"Dissolution coplanaire terminée : {results['delta_faces']} faces dissoutes "
            f"(angle: {math.degrees(angle_rad):.1f}°, délimiters: {sorted(list(delimiters))})."
        )
        if giant_ngons > 0:
            log_msg += f" Note : {giant_ngons} grand(s) N-gone(s) formé(s) (jusqu'à {max_verts} côtés)."
        results["log"].append(log_msg)
    except Exception as e:
        results["status"] = "ERROR"
        results["log"].append(f"Erreur lors de la dissolution : {e}")

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
