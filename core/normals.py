"""MeshForge - Module de gestion des normales (Section 3.5 du CdC).
Prend en charge le recalcul cohérent des normales, le lissage par angle
conforme à l'API Blender 5.x, les normales pondérées et le nettoyage des données personnalisées.
"""

from __future__ import annotations
import bpy
import math
from typing import Dict, Any


def execute_normals(obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Exécute les opérations sur les normales de l'objet."""
    results: Dict[str, Any] = {
        "status": "SUCCESS",
        "recalculated": False,
        "auto_smooth_applied": False,
        "weighted_applied": False,
        "cleared_split_normals": False,
        "cleared_sharp": False,
        "log": []
    }

    if not obj or obj.type != 'MESH':
        results["status"] = "ERROR"
        results["log"].append("Objet invalide pour la gestion des normales.")
        return results

    prev_mode = obj.mode
    bpy.context.view_layer.objects.active = obj

    # 1. Nettoyage des normales personnalisées fractionnées (Clear Custom Split Normals)
    if getattr(props, "clear_custom_split_normals", False):
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        try:
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
            results["cleared_split_normals"] = True
            results["log"].append("Normales personnalisées fractionnées nettoyées.")
        except Exception as e:
            results["log"].append(f"Avertissement clear split normals: {e}")

    # 2. Nettoyage des arêtes vives marquées (Clear Sharp Edges)
    if getattr(props, "clear_sharp_edges", False):
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.mark_sharp(clear=True)
        results["cleared_sharp"] = True
        results["log"].append("Marquages d'arêtes vives effacés.")

    # 3. Recalcul des normales (Recalculate Outside / Inside)
    if getattr(props, "recalculate_normals", True):
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        inside = (getattr(props, "recalculate_direction", "OUTSIDE") == "INSIDE")
        bpy.ops.mesh.normals_make_consistent(inside=inside)
        results["recalculated"] = True
        results["log"].append(f"Normales recalculées vers {'l\'intérieur' if inside else 'l\'extérieur'}.")

    # Retour en mode Objet pour les opérations d'ombrage et de modificateurs
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # 4. Lissage automatique par angle (Auto Smooth conforme à Blender 5.x)
    if getattr(props, "apply_auto_smooth", True):
        angle_deg = getattr(props, "auto_smooth_angle", 30.0)
        angle_rad = math.radians(angle_deg)
        try:
            bpy.ops.object.shade_smooth_by_angle(angle=angle_rad, keep_sharp_edges=True)
            results["auto_smooth_applied"] = True
            results["log"].append(f"Lissage automatique appliqué (angle: {angle_deg:.1f}°).")
        except Exception as e:
            results["log"].append(f"Avertissement shade_smooth_by_angle: {e}")

    # 5. Normales pondérées (Weighted Normals)
    if getattr(props, "weighted_normals", False):
        try:
            mod = obj.modifiers.new(name="MeshForge_WeightedNormal", type='WEIGHTED_NORMAL')
            mod.keep_sharp = True
            bpy.ops.object.modifier_apply(modifier=mod.name)
            results["weighted_applied"] = True
            results["log"].append("Modificateur Weighted Normal appliqué.")
        except Exception as e:
            results["log"].append(f"Avertissement weighted normals: {e}")

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
