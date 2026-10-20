"""MeshForge - Opérateur de découpe ciblée des N-gones (Phase D2.2).
Traite les polygones selon leur morphologie (Convexes, Concaves) et refuse proprement
les cas ambigus ou auto-intersectants, avec rollback automatique garanti.
"""

from __future__ import annotations
import bpy
from typing import Dict, Any

from ..core.ngon_cutter import execute_ngon_cut
from ..core.visualizer import apply_color_inspection
from .topology_inspect import _ACTIVE_DIAGNOSIS_CACHE


class MESHFORGE_OT_cut_ngons(bpy.types.Operator):
    """Découpe de façon adaptée et sécurisée les N-gones en triangles réguliers"""
    bl_idname = "meshforge.cut_ngons"
    bl_label = "Découper les N-gones"
    bl_description = (
        "Triangule les N-gones convexes (Beauty équilibré) et concaves (Ear-Clipping) "
        "en préservant les UVs et matériaux, et refuse les cas ambigus pour découpe manuelle"
    )
    bl_options = {'REGISTER', 'UNDO'}

    cut_convex: bpy.props.BoolProperty(
        name="N-gones convexes",
        description="Découper les N-gones convexes réguliers en triangles équilibrés",
        default=True
    )
    cut_concave: bpy.props.BoolProperty(
        name="N-gones concaves",
        description="Découper les N-gones concaves par ear-clipping orienté respectant les angles rentrants",
        default=True
    )
    allow_ambiguous: bpy.props.BoolProperty(
        name="Forcer cas ambigus (Risque Élevé)",
        description="Tenter de découper même si le N-gone est auto-intersectant ou fortement gauche",
        default=False
    )
    selected_only: bpy.props.BoolProperty(
        name="Sélection uniquement",
        description="Ne traiter que les N-gones actuellement sélectionnés",
        default=False
    )

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
            self.report({'WARNING'}, "MeshForge : Cette opération requiert le mode Objet. Veuillez repasser en mode Objet (Touche Tab) pour l'exécuter.")
            return {'CANCELLED'}

        props = context.scene.meshforge_settings
        mode = props.asset_target_mode

        res = execute_ngon_cut(
            obj=obj,
            cut_convex=self.cut_convex,
            cut_concave=self.cut_concave,
            allow_ambiguous=self.allow_ambiguous,
            selected_only=self.selected_only,
            target_mode=mode
        )

        if not res["success"]:
            err = res.get("error", "Erreur inconnue")
            msg = f"Découpe des N-gones annulée : {err}. Le maillage a été restauré sans perte."
            self.report({'ERROR'}, f"MeshForge : {msg}")
            return {'CANCELLED'}

        # Mise à jour du cache de diagnostic
        post_diag = res.get("post_diagnosis", {})
        _ACTIVE_DIAGNOSIS_CACHE[obj.name] = post_diag

        # Réappliquer la visualisation s'il reste des défauts
        defects_remaining = len(post_diag.get("defects", []))
        if defects_remaining > 0:
            apply_color_inspection(obj, post_diag.get("defects", []), context=context)

        # Rapport synthétique
        n_refused = len(res.get("refused_ngons", []))
        detail_msg = (
            f"Découpe N-gones terminée en {res['execution_time_ms']:.1f}ms : "
            f"{res.get('convex_cut', 0)} convexe(s), {res.get('concave_cut', 0)} concave(s) découpé(s) "
            f"en {res.get('triangles_created', 0)} triangles. "
            f"{n_refused} cas ambigu(s) refusé(s) (sélectionnés pour couteau manuel). "
            f"Anomalies restantes : {defects_remaining}."
        )

        if n_refused > 0:
            self.report({'WARNING'}, f"MeshForge : {detail_msg}")
        else:
            self.report({'INFO'}, f"MeshForge : {detail_msg}")

        return {'FINISHED'}
