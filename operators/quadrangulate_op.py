"""MeshForge - Opérateur de quadrangulation ciblée (Phase D2.3).
Fusionne les paires de triangles coplanaires en quads réguliers avec respect
strict des coutures UV, arêtes vives, matériaux et rollback automatique garanti.
"""

from __future__ import annotations
import bpy
from typing import Dict, Any

from ..core.quadrangulator import execute_targeted_quadrangulation
from ..core.visualizer import apply_color_inspection, clear_inspection_view
from .topology_inspect import _ACTIVE_DIAGNOSIS_CACHE


class MESHFORGE_OT_quadrangulate(bpy.types.Operator):
    """Fusionne de façon ciblée les paires de triangles coplanaires en quads réguliers"""
    bl_idname = "meshforge.quadrangulate"
    bl_label = "Quadrangulation ciblée"
    bl_description = (
        "Fusionne les paires de triangles coplanaires en quads en respectant strictement "
        "les coutures UV, arêtes vives, frontières et matériaux"
    )
    bl_options = {'REGISTER', 'UNDO'}

    max_angle: bpy.props.FloatProperty(
        name="Angle dièdre max (°)",
        description="Angle dièdre maximal toléré entre deux triangles coplanaires (15° par défaut)",
        default=15.0,
        min=0.1,
        max=45.0
    )
    compare_uvs: bpy.props.BoolProperty(
        name="Respecter les UVs",
        description="Ne fusionne pas les triangles à travers une discontinuité ou frontière UV",
        default=True
    )
    compare_seams: bpy.props.BoolProperty(
        name="Respecter les coutures (Seams)",
        description="Préserve les arêtes marquées comme coutures de dépliage",
        default=True
    )
    compare_sharp: bpy.props.BoolProperty(
        name="Respecter les arêtes vives (Sharp)",
        description="Préserve les arêtes vives et les démarcations d'ombrage",
        default=True
    )
    compare_materials: bpy.props.BoolProperty(
        name="Respecter les matériaux",
        description="Ne fusionne pas deux triangles ayant des matériaux différents",
        default=True
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

        res = execute_targeted_quadrangulation(
            obj=obj,
            max_angle_deg=self.max_angle,
            compare_uvs=self.compare_uvs,
            compare_seams=self.compare_seams,
            compare_sharp=self.compare_sharp,
            compare_materials=self.compare_materials
        )

        if not res["success"]:
            err = res.get("error", "Erreur inconnue")
            msg = f"Quadrangulation annulée : {err}. Le maillage a été restauré sans perte."
            self.report({'ERROR'}, f"MeshForge : {msg}")
            return {'CANCELLED'}

        # Mise à jour du cache de diagnostic avec signature topologique (UX7.2)
        mesh = obj.data
        real_tris = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)
        post_diag = res.get("post_diagnosis", {})
        post_diag["topo_signature"] = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
        post_diag["mesh_name"] = mesh.name
        post_diag["is_stale"] = False
        post_diag["triangle_count"] = real_tris
        _ACTIVE_DIAGNOSIS_CACHE[obj.name] = post_diag

        # Réappliquer la visualisation s'il reste des défauts ou effacer si 0 anomalie
        defects_remaining = len(post_diag.get("defects", []))
        if defects_remaining > 0:
            apply_color_inspection(obj, post_diag.get("defects", []), context=context)
        else:
            clear_inspection_view(obj, context=context)

        # Rapport synthétique
        quads_created = res.get("quads_created", 0)
        tris_merged = res.get("triangles_merged", 0)
        refusals = res.get("refusals", {})
        total_refusals = sum(refusals.values())
        elapsed = res.get("execution_time_ms", 0.0)

        detail_msg = (
            f"Quadrangulation terminée en {elapsed:.1f}ms : "
            f"{quads_created} quad(s) créé(s) ({tris_merged} triangles fusionnés). "
            f"Triangles restants : {res.get('final_triangles', 0)}. "
            f"{total_refusals} arête(s) refusée(s) pour préserver la forme et les UVs. "
            f"Anomalies restantes : {defects_remaining}."
        )

        self.report({'INFO'}, f"MeshForge : {detail_msg}")
        return {'FINISHED'}
