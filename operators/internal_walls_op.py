"""MeshForge - Opérateurs pour les parois internes (Phase D2.4).
Fournit :
1. Sélection et inspection ciblée des parois internes suspectes.
2. Suppression prudente des parois mitoyennes strictes avec dialogue de confirmation explicite
   et rollback automatique en cas de violation d'invariant.
"""

from __future__ import annotations
import bpy
from typing import Dict, Any

from ..core.internal_walls import detect_internal_walls, execute_remove_internal_walls
from ..core.visualizer import apply_color_inspection, clear_inspection_view, zoom_to_defect
from .topology_inspect import _ACTIVE_DIAGNOSIS_CACHE


class MESHFORGE_OT_select_internal_walls(bpy.types.Operator):
    """Sélectionne et cadre précisément les parois internes mitoyennes pour inspection visuelle"""
    bl_idname = "meshforge.select_internal_walls"
    bl_label = "Inspecter les parois internes"
    bl_description = "Sélectionne et cadre la vue 3D sur les faces de parois internes détectées"
    bl_options = {'REGISTER', 'UNDO'}

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
            self.report({'WARNING'}, "MeshForge : Cette opération requiert le mode Objet.")
            return {'CANCELLED'}

        diag = detect_internal_walls(obj)
        strict_faces = diag.get("strict_internal_faces", [])

        if not strict_faces:
            self.report({'INFO'}, "MeshForge : Aucune paroi interne mitoyenne stricte détectée.")
            return {'FINISHED'}

        # Sélectionner les faces dans le maillage
        mesh = obj.data
        for p in mesh.polygons:
            p.select = (p.index in strict_faces)

        # Cadrage visuel via le visualiseur MeshForge (UX7.1)
        defect_data = {
            "id": "internal_walls_inspect",
            "element_type": "FACE",
            "indices": strict_faces,
            "center": diag.get("world_center")
        }
        zoom_to_defect(defect_data, context, obj=obj)

        self.report({'INFO'}, f"MeshForge : {len(strict_faces)} face(s) de parois internes sélectionnée(s) et cadrée(s).")
        return {'FINISHED'}


class MESHFORGE_OT_remove_internal_walls(bpy.types.Operator):
    """Supprime les parois internes mitoyennes pour rétablir un volume fermé manifold"""
    bl_idname = "meshforge.remove_internal_walls"
    bl_label = "Supprimer les parois internes"
    bl_description = (
        "Supprime prudemment les parois internes mitoyennes après confirmation, "
        "en garantissant l'absence de trou et avec rollback automatique"
    )
    bl_options = {'REGISTER', 'UNDO'}

    remove_strict_only: bpy.props.BoolProperty(
        name="Mitoyennes strictes uniquement",
        description="Ne supprime que les faces dont le retrait guérit la non-manifoldité sans créer de frontière ouverte",
        default=True
    )
    selected_only: bpy.props.BoolProperty(
        name="Sélection uniquement",
        description="Ne supprimer que les parois actuellement sélectionnées",
        default=False
    )
    confirm: bpy.props.BoolProperty(
        name="Demander confirmation",
        description="Affiche une boîte de dialogue explicite avant suppression",
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

    def invoke(self, context, event):
        obj = context.active_object
        if context.mode != 'OBJECT' or (obj and obj.mode != 'OBJECT'):
            self.report({'WARNING'}, "MeshForge : Cette opération requiert le mode Objet.")
            return {'CANCELLED'}

        if self.confirm:
            return context.window_manager.invoke_props_dialog(self, width=380)
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Confirmation de suppression :", icon='QUESTION')
        col = layout.column(align=True)
        col.scale_y = 0.85
        col.label(text="• Supprime uniquement les parois mitoyennes occluses.")
        col.label(text="• Guérit les arêtes non-manifold sans ouvrir de trou.")
        col.label(text="• Transaction sécurisée : rollback automatique si anomalie.")
        layout.separator()
        layout.prop(self, "remove_strict_only")
        layout.prop(self, "selected_only")

    def execute(self, context):
        obj = context.active_object
        if context.mode != 'OBJECT' or (obj and obj.mode != 'OBJECT'):
            self.report({'WARNING'}, "MeshForge : Cette opération requiert le mode Objet.")
            return {'CANCELLED'}

        res = execute_remove_internal_walls(
            obj=obj,
            remove_strict_only=self.remove_strict_only,
            selected_only=self.selected_only
        )

        if not res["success"]:
            err = res.get("error", "Erreur inconnue")
            msg = f"Suppression des parois internes annulée : {err}. Le maillage a été restauré sans perte."
            self.report({'ERROR'}, f"MeshForge : {msg}")
            return {'CANCELLED'}

        faces_removed = res.get("faces_removed", 0)
        healed_edges = res.get("healed_edges", 0)
        elapsed = res.get("execution_time_ms", 0.0)

        # Mise à jour du cache de diagnostic avec signature topologique (UX7.2)
        mesh = obj.data
        real_tris = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)
        post_diag = res.get("post_diagnosis", {})
        post_diag["topo_signature"] = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
        post_diag["mesh_name"] = mesh.name
        post_diag["is_stale"] = False
        post_diag["triangle_count"] = real_tris
        _ACTIVE_DIAGNOSIS_CACHE[obj.name] = post_diag

        defects_remaining = len(post_diag.get("defects", []))
        if defects_remaining > 0:
            apply_color_inspection(obj, post_diag.get("defects", []), context=context)
        else:
            clear_inspection_view(obj, context=context)

        detail_msg = (
            f"Suppression des parois internes terminée en {elapsed:.1f}ms : "
            f"{faces_removed} face(s) mitoyenne(s) supprimée(s), "
            f"{healed_edges} arête(s) non-manifold guérie(s), 0 trou créé. "
            f"Anomalies restantes : {defects_remaining}."
        )

        self.report({'INFO'}, f"MeshForge : {detail_msg}")
        return {'FINISHED'}
