"""MeshForge - Opérateur d'analyse et diagnostic initial (lecture seule)."""

from __future__ import annotations
import bpy
from ..core.mesh_stats import get_mesh_statistics


class MESHFORGE_OT_analyze(bpy.types.Operator):
    """Analyse l'état topologique et géométrique du maillage actif sans le modifier"""
    bl_idname = "meshforge.analyze"
    bl_label = "Analyser seulement"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        props = context.scene.meshforge_settings

        stats = get_mesh_statistics(obj)
        if not stats.get("valid", False):
            self.report({'ERROR'}, stats.get("error", "Erreur lors de l'analyse."))
            return {'CANCELLED'}

        # Mise à jour des propriétés d'affichage
        props.last_status = "Analysé"
        props.last_duration = 0.0
        props.last_result_obj_name = obj.name
        props.last_verts_before = stats["vertices"]
        props.last_verts_after = stats["vertices"]
        props.last_edges_before = stats["edges"]
        props.last_edges_after = stats["edges"]
        props.last_faces_before = stats["faces"]
        props.last_faces_after = stats["faces"]
        props.last_tris_before = stats["estimated_triangles"]
        props.last_tris_after = stats["estimated_triangles"]
        props.last_reduction = 0.0

        summary = (
            f"Triangles: {stats['estimated_triangles']} | Faces: {stats['faces']} "
            f"(Tris: {stats['tri_faces']}, Quads: {stats['quad_faces']}, N-gons: {stats['ngon_faces']})\n"
            f"Non-Manifold Edges: {stats['non_manifold_edges']}, Verts: {stats['non_manifold_verts']}\n"
            f"Frontières: {stats['boundary_edges']}, Éléments lâches: {stats['loose_verts']}V/{stats['loose_edges']}E\n"
            f"Faces d'aire nulle: {stats['zero_area_faces']}, UVs: {stats['uv_layer_count']}, Matériaux: {stats['material_slot_count']}"
        )
        props.last_logs = summary

        self.report({'INFO'}, f"Analyse MeshForge : {stats['faces']} faces, {stats['estimated_triangles']} triangles.")
        return {'FINISHED'}
