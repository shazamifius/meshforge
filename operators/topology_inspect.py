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
        obj = context.active_object
        return (
            obj is not None and
            obj.type == 'MESH' and
            context.mode == 'OBJECT' and
            obj.mode == 'OBJECT'
        )

    def execute(self, context):
        obj = context.active_object
        if context.mode != 'OBJECT' or (obj and obj.mode != 'OBJECT'):
            self.report({'WARNING'}, "MeshForge : L'analyse topologique requiert le mode Objet. Veuillez repasser en mode Objet (Touche Tab) pour l'exécuter.")
            return {'CANCELLED'}

        props = context.scene.meshforge_settings
        mode = props.asset_target_mode

        diag = diagnose_topology(obj, mode=mode)
        _ACTIVE_DIAGNOSIS_CACHE[obj.name] = diag

        sum_d = diag.get("summary", {})
        total_anomalies = len(diag.get("defects", []))

        # Appliquer la coloration temporaire si des défauts existent
        if total_anomalies > 0:
            apply_color_inspection(obj, diag.get("defects", []), context=context)

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

    defect_index: bpy.props.IntProperty(name="Index du défaut", default=-1)
    finding_id: bpy.props.StringProperty(name="ID de l'anomalie", default="")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        diag = _ACTIVE_DIAGNOSIS_CACHE.get(obj.name)

        if not diag:
            # Si aucun diagnostic en cache, exécuter le diagnostic d'abord (en mode Objet uniquement)
            if context.mode != 'OBJECT' or (obj and obj.mode != 'OBJECT'):
                self.report({'WARNING'}, "MeshForge : Aucune analyse en cache. Veuillez repasser en mode Objet (Touche Tab) pour lancer l'analyse préalable.")
                return {'CANCELLED'}
            props = context.scene.meshforge_settings
            diag = diagnose_topology(obj, mode=props.asset_target_mode)
            _ACTIVE_DIAGNOSIS_CACHE[obj.name] = diag

        target_defect = None
        target_name = "Anomalie"

        # 1. Recherche prioritaire par finding_id
        if self.finding_id:
            findings = diag.get("findings", [])
            for f in findings:
                f_id = getattr(f, "id", None) or (f.get("id") if isinstance(f, dict) else None)
                if f_id == self.finding_id:
                    if hasattr(f, "to_dict"):
                        target_defect = f.to_dict()
                    else:
                        target_defect = dict(f)
                    target_name = target_defect.get("name", self.finding_id)
                    break

        # 2. Repli sur defect_index dans la liste des défauts visuels
        defects = diag.get("defects", [])
        if target_defect is None and defects:
            idx = 0 if self.defect_index < 0 else max(0, min(len(defects) - 1, self.defect_index))
            target_defect = defects[idx]
            target_name = target_defect.get("name", f"Défaut #{idx+1}")
            context.scene.meshforge_settings.active_defect_index = idx

        if not target_defect:
            self.report({'INFO'}, "MeshForge : Aucune anomalie ciblée ou maillage sain.")
            return {'FINISHED'}

        # 3. Sélection non-destructive
        if target_defect.get("indices"):
            select_defect(obj, target_defect)

        # 4. Cadrage sécurisé (zoom)
        ok_zoom, zoom_msg = zoom_to_defect(target_defect, context)

        self.report({'INFO'}, f"MeshForge : {target_name} sélectionné. {zoom_msg}")
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
        clear_inspection_view(obj, context=context)
        self.report({'INFO'}, "MeshForge : Inspection visuelle effacée.")
        return {'FINISHED'}
