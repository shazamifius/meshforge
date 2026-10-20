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

# Seuil de densité reproductible pour l'actualisation automatique immédiate
# Mesure de performance : 25 000 triangles correspond à ~45 ms de calcul (invisible à l'utilisateur)
AUTO_REFRESH_TRIANGLE_THRESHOLD = 25_000


def get_active_diagnosis(obj_name: str) -> Optional[Dict[str, Any]]:
    return _ACTIVE_DIAGNOSIS_CACHE.get(obj_name)


def check_diagnosis_staleness(obj: bpy.types.Object) -> Tuple[bool, Optional[str]]:
    """Vérifie si le diagnostic en cache pour l'objet est périmé.
    Retourne (is_stale, raison).
    """
    if not obj or obj.name not in _ACTIVE_DIAGNOSIS_CACHE:
        return False, None
    diag = _ACTIVE_DIAGNOSIS_CACHE[obj.name]
    if not isinstance(diag, dict):
        return False, None
    if diag.get("is_stale", False):
        return True, "Marqué obsolète suite à une modification géométrique."

    mesh = getattr(obj, "data", None)
    if not mesh or not hasattr(mesh, "vertices"):
        return False, None

    # Comparaison de la signature topologique (V, E, F)
    cached_sig = diag.get("topo_signature")
    if cached_sig:
        curr_sig = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
        if curr_sig != cached_sig:
            diag["is_stale"] = True
            return True, f"Topologie modifiée (Sommets: {cached_sig[0]} -> {curr_sig[0]}, Faces: {cached_sig[2]} -> {curr_sig[2]})."

    # Comparaison du maillage interne
    cached_mesh_name = diag.get("mesh_name")
    if cached_mesh_name and cached_mesh_name != mesh.name:
        diag["is_stale"] = True
        return True, "Bloc de données maillage réassigné."

    return False, None


def mark_diagnosis_stale(obj_name: str, reason: str = "") -> None:
    """Marque explicitement le diagnostic d'un objet comme périmé."""
    if obj_name in _ACTIVE_DIAGNOSIS_CACHE and isinstance(_ACTIVE_DIAGNOSIS_CACHE[obj_name], dict):
        _ACTIVE_DIAGNOSIS_CACHE[obj_name]["is_stale"] = True


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

        mesh = obj.data
        diag = diagnose_topology(obj, mode=mode)

        # Enregistrement de la signature topologique pour détection de péremption (UX7.2)
        real_tris = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)
        diag["topo_signature"] = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
        diag["mesh_name"] = mesh.name
        diag["is_stale"] = False
        diag["triangle_count"] = real_tris

        _ACTIVE_DIAGNOSIS_CACHE[obj.name] = diag

        sum_d = diag.get("summary", {})
        total_anomalies = len(diag.get("defects", []))

        # Appliquer la coloration temporaire si des défauts existent
        if total_anomalies > 0:
            apply_color_inspection(obj, diag.get("defects", []), context=context)
        else:
            clear_inspection_view(obj, context=context)

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
    bl_description = "Sélectionne les éléments du défaut et cadre la vue 3D dessus avec précision"
    bl_options = {'REGISTER', 'UNDO'}

    defect_index: bpy.props.IntProperty(name="Index du défaut", default=-1)
    finding_id: bpy.props.StringProperty(name="ID de l'anomalie", default="")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        diag = _ACTIVE_DIAGNOSIS_CACHE.get(obj.name)

        # Vérification de péremption du diagnostic (UX7.2)
        is_stale, reason = check_diagnosis_staleness(obj)
        mesh = obj.data
        real_tris = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

        if not diag or is_stale:
            # Pour les petits maillages (< seuil), réanalyser automatiquement en mode Objet
            if context.mode == 'OBJECT' and obj.mode == 'OBJECT' and real_tris <= AUTO_REFRESH_TRIANGLE_THRESHOLD:
                props = context.scene.meshforge_settings
                diag = diagnose_topology(obj, mode=props.asset_target_mode)
                diag["topo_signature"] = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
                diag["mesh_name"] = mesh.name
                diag["is_stale"] = False
                diag["triangle_count"] = real_tris
                _ACTIVE_DIAGNOSIS_CACHE[obj.name] = diag
                if len(diag.get("defects", [])) > 0:
                    apply_color_inspection(obj, diag.get("defects", []), context=context)
            elif is_stale:
                self.report({'WARNING'}, f"MeshForge : Géométrie modifiée ({reason}). Veuillez actualiser le diagnostic.")
                return {'CANCELLED'}
            else:
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

        # 3. Sélection non-destructive des éléments
        if target_defect.get("indices"):
            select_defect(obj, target_defect)

        # 4. Cadrage précis (zoom avec point focal et distance)
        ok_zoom, zoom_msg = zoom_to_defect(target_defect, context, obj=obj)

        self.report({'INFO'}, f"MeshForge : {target_name} sélectionné. {zoom_msg}")
        return {'FINISHED'}


class MESHFORGE_OT_clear_defect_view(bpy.types.Operator):
    """Nettoie la visualisation d'inspection et réinitialise la vue 3D"""
    bl_idname = "meshforge.clear_defect_view"
    bl_label = "Effacer l'inspection"
    bl_description = "Supprime les couleurs temporaires d'inspection, restaure l'affichage initial et désélectionne les éléments"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        clear_inspection_view(obj, context=context)
        _ACTIVE_DIAGNOSIS_CACHE.pop(obj.name, None)
        self.report({'INFO'}, "MeshForge : Inspection visuelle effacée et affichage normal restauré.")
        return {'FINISHED'}
