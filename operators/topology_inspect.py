"""MeshForge - Opérateurs d'inspection et de navigation dans les anomalies topologiques (Phase D1).
Permet de sélectionner, cadrer (zoomer) et inspecter visuellement chaque défaut
de manière 100% non-destructive.
"""

from __future__ import annotations
import bpy
from typing import Dict, Any, List

from ..core.topology_diagnosis import diagnose_topology
from ..core.visualizer import select_defect, zoom_to_defect, apply_color_inspection, clear_inspection_view

# Cache éphémère en mémoire pour l'interface utilisateur
_ACTIVE_DIAGNOSIS_CACHE: Dict[str, Any] = {}


def get_active_diagnosis(obj_name: str) -> Optional[Dict[str, Any]]:
    return _ACTIVE_DIAGNOSIS_CACHE.get(obj_name)


class MESHFORGE_OT_analyze_topology(bpy.types.Operator):
    """Exécute le diagnostic topologique non-destructif en lecture seule"""
    bl_idname = "meshforge.analyze_topology"
    bl_label = "Analyser la topologie"
    bl_description = "Exécute une analyse topologique non-destructive et répertorie les anomalies par couleur"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        props = context.scene.meshforge_settings
        mode = props.asset_target_mode

        diag = diagnose_topology(obj, mode=mode)
        _ACTIVE_DIAGNOSIS_CACHE[obj.name] = diag

        sum_d = diag.get("summary", {})
        total_anomalies = len(diag.get("defects", []))

        # Appliquer la coloration temporaire si des défauts existent
        if total_anomalies > 0:
            apply_color_inspection(obj, diag.get("defects", []))

        msg = (
            f"Analyse topologique terminée : {total_anomalies} anomalie(s) "
            f"(N-gones: {sum_d.get('ngons', 0)}, Triangles: {sum_d.get('suspect_triangles', 0)}, "
            f"Dégénérescences: {sum_d.get('degeneracies', 0)}, Isolés: {sum_d.get('isolated', 0)})"
        )
        self.report({'INFO'}, f"MeshForge : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_focus_defect(bpy.types.Operator):
    """Sélectionne le défaut et zoome automatiquement dessus dans la vue 3D"""
    bl_idname = "meshforge.focus_defect"
    bl_label = "Zoomer sur l'anomalie"
    bl_description = "Sélectionne les éléments du défaut et cadre la vue 3D dessus"
    bl_options = {'REGISTER', 'UNDO'}

    defect_index: bpy.props.IntProperty(name="Index du défaut", default=0)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        diag = _ACTIVE_DIAGNOSIS_CACHE.get(obj.name)

        if not diag or "defects" not in diag or not diag["defects"]:
            # Si aucun diagnostic en cache, exécuter le diagnostic d'abord
            props = context.scene.meshforge_settings
            diag = diagnose_topology(obj, mode=props.asset_target_mode)
            _ACTIVE_DIAGNOSIS_CACHE[obj.name] = diag

        defects = diag.get("defects", [])
        if not defects:
            self.report({'INFO'}, "MeshForge : Aucune anomalie détectée sur ce maillage.")
            return {'FINISHED'}

        idx = max(0, min(len(defects) - 1, self.defect_index))
        defect = defects[idx]

        # 1. Sélection non-destructive
        select_defect(obj, defect)

        # 2. Cadrage sécurisé (zoom)
        ok_zoom, zoom_msg = zoom_to_defect(defect, context)

        context.scene.meshforge_settings.active_defect_index = idx
        self.report({'INFO'}, f"MeshForge : {defect.get('name')} sélectionné. {zoom_msg}")
        return {'FINISHED'}


class MESHFORGE_OT_clear_defect_view(bpy.types.Operator):
    """Nettoie la visualisation d'inspection et réinitialise la vue 3D"""
    bl_idname = "meshforge.clear_defect_view"
    bl_label = "Effacer l'inspection"
    bl_description = "Supprime les couleurs temporaires d'inspection et désélectionne les éléments"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        clear_inspection_view(obj)
        self.report({'INFO'}, "MeshForge : Inspection visuelle effacée.")
        return {'FINISHED'}
