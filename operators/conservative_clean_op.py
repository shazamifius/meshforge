"""MeshForge - Opérateur de nettoyage conservateur transactionnel (Phase D2.1).
Exécute la suppression sécurisée des éléments orphelins, arêtes filaires, faces nulles
et la fusion des sommets doublons avec vérification d'invariants et rollback automatique.
"""

from __future__ import annotations
import bpy
from typing import Dict, Any

from ..core.conservative_cleaner import execute_conservative_cleanup
from ..core.visualizer import apply_color_inspection
from .topology_inspect import _ACTIVE_DIAGNOSIS_CACHE


class MESHFORGE_OT_conservative_clean(bpy.types.Operator):
    """Exécute un nettoyage conservateur ciblé avec garantie de rollback automatique"""
    bl_idname = "meshforge.conservative_clean"
    bl_label = "Nettoyage conservateur (Sûr)"
    bl_description = (
        "Supprime les sommets orphelins, arêtes filaires et faces nulles, "
        "et fusionne les doublons stricts avec rollback automatique si une anomalie survient"
    )
    bl_options = {'REGISTER', 'UNDO'}

    clean_loose_verts: bpy.props.BoolProperty(
        name="Supprimer sommets orphelins",
        description="Retire les sommets flottants sans arête ni face (Risque Nul)",
        default=True
    )
    clean_wire_edges: bpy.props.BoolProperty(
        name="Supprimer arêtes filaires sans face",
        description="Retire les segments ne délimitant aucune face polygonale (Risque Faible)",
        default=True
    )
    clean_zero_faces: bpy.props.BoolProperty(
        name="Dissoudre faces d'aire nulle",
        description="Dissout les faces plates repliées ou colinéaires <= 1e-7 m² (Risque Modéré)",
        default=True
    )
    merge_doubles: bpy.props.BoolProperty(
        name="Fusionner les sommets doublons",
        description="Fusionne les sommets coïncidents selon une tolérance explicite",
        default=True
    )
    doubles_distance: bpy.props.FloatProperty(
        name="Tolérance de fusion",
        description="Distance maximale pour considérer deux sommets comme doublons",
        default=0.00001,
        min=0.000001,
        max=0.01,
        precision=6,
        unit='LENGTH'
    )
    preserve_seams: bpy.props.BoolProperty(
        name="Protéger les coutures UV (Seams)",
        description="Ne fusionne pas les sommets situés sur les coutures de texture pour éviter de déchirer les UVs",
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

        props = context.scene.meshforge_settings
        mode = props.asset_target_mode

        # Exécuter la transaction sécurisée
        res = execute_conservative_cleanup(
            obj=obj,
            clean_loose_v=self.clean_loose_verts,
            clean_wire_e=self.clean_wire_edges,
            clean_zero_f=self.clean_zero_faces,
            merge_doubles=self.merge_doubles,
            doubles_distance=self.doubles_distance,
            preserve_seams=self.preserve_seams,
            target_mode=mode
        )

        if not res["success"]:
            err = res.get("error", "Erreur inconnue")
            msg = f"Nettoyage refusé et annulé : {err}. Le maillage a été restauré sans aucune perte."
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

        # Réappliquer la visualisation sur les défauts restants ou effacer si 0 anomalie
        defects_remaining = len(post_diag.get("defects", []))
        if defects_remaining > 0:
            apply_color_inspection(obj, post_diag.get("defects", []), context=context)
        else:
            clear_inspection_view(obj, context=context)

        # Rapport de synthèse
        elem = res.get("elements_removed", {})
        detail_msg = (
            f"Nettoyage conservateur réussi en {res['execution_time_ms']:.1f}ms : "
            f"{elem.get('loose_verts', 0)} sommet(s) orphelin(s), "
            f"{elem.get('wire_edges', 0)} arête(s) filaire(s), "
            f"{elem.get('zero_faces', 0)} face(s) nulle(s) supprimé(s), "
            f"{elem.get('doubles_merged', 0)} doublon(s) fusionné(s). "
            f"Anomalies restantes : {defects_remaining}."
        )
        self.report({'INFO'}, f"MeshForge : {detail_msg}")
        return {'FINISHED'}
