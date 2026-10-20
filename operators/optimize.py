"""MeshForge - Opérateur principal d'optimisation."""

from __future__ import annotations
import bpy
from ..core.pipeline import run_meshforge_pipeline


class MESHFORGE_OT_optimize(bpy.types.Operator):
    """Lance la chaîne d'optimisation des maillages selon les options actives"""
    bl_idname = "meshforge.optimize"
    bl_label = "Optimiser le maillage"
    bl_options = {'REGISTER', 'UNDO'}

    confirm_destructive: bpy.props.BoolProperty(
        name="Confirmer l'écrasement destructif",
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

    def invoke(self, context, event):
        props = context.scene.meshforge_settings
        # Si le mode destructif est coché et la duplication décochée, demander confirmation explicite
        if props.destructive_mode and not props.create_new_object:
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if context.mode != 'OBJECT' or (obj and obj.mode != 'OBJECT'):
            self.report({'WARNING'}, "MeshForge : L'optimisation requiert le mode Objet. Veuillez repasser en mode Objet (Touche Tab) pour l'exécuter.")
            return {'CANCELLED'}

        props = context.scene.meshforge_settings

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Veuillez sélectionner un objet maillage valide.")
            return {'CANCELLED'}

        # Exécution du pipeline
        report = run_meshforge_pipeline(obj, props)

        # Mémorisation du rapport complet pour l'export JSON / Texte
        from . import report_export
        report_export.LAST_PIPELINE_REPORT = report

        # Enregistrement des résultats pour affichage UI
        props.last_status = "Succès" if report["success"] else "Échec"
        props.last_duration = report.get("total_duration", 0.0)
        props.last_result_obj_name = report.get("result_name", "")

        s_init = report.get("initial_stats", {})
        s_final = report.get("final_stats", {})
        props.last_verts_before = s_init.get("vertices", 0)
        props.last_verts_after = s_final.get("vertices", 0)
        props.last_edges_before = s_init.get("edges", 0)
        props.last_edges_after = s_final.get("edges", 0)
        props.last_faces_before = s_init.get("faces", 0)
        props.last_faces_after = s_final.get("faces", 0)
        props.last_tris_before = s_init.get("estimated_triangles", 0)
        props.last_tris_after = s_final.get("estimated_triangles", 0)
        props.last_reduction = report.get("reduction_percentage", 0.0)

        # Concaténation des logs résumés
        all_logs = report.get("logs", [])
        props.last_logs = "\n".join(all_logs[-6:]) if all_logs else "Aucune modification nécessaire."

        if not report["success"]:
            err_msg = " ; ".join(report.get("errors", ["Erreur pipeline."]))
            self.report({'ERROR'}, f"MeshForge : {err_msg}")
            return {'CANCELLED'}

        tri_delta = props.last_tris_before - props.last_tris_after
        self.report(
            {'INFO'},
            f"MeshForge terminé en {props.last_duration:.2f}s | Triangles: {props.last_tris_before} -> {props.last_tris_after} (-{props.last_reduction:.1f}%)"
        )
        return {'FINISHED'}
