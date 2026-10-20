"""MeshForge - Opérateurs pour chaque section exécutable individuellement."""

from __future__ import annotations
import bpy

from ..core.repair_pipeline import execute_repair
from ..core.manifold import execute_manifold
from ..core.dissolve import execute_dissolve
from ..core.topology import execute_topology
from ..core.normals import execute_normals
from ..core.object_data import execute_object_data
from ..core.simplification import execute_simplification


def _check_object_mode(operator: bpy.types.Operator, context: bpy.types.Context) -> bool:
    """Vérifie que le contexte actuel est bien le mode Objet et signale un avertissement sinon."""
    obj = context.active_object
    if context.mode != 'OBJECT' or (obj and obj.mode != 'OBJECT'):
        operator.report({'WARNING'}, "MeshForge : Cette opération requiert le mode Objet. Veuillez repasser en mode Objet (Touche Tab) pour l'exécuter.")
        return False
    return True


class MESHFORGE_OT_repair(bpy.types.Operator):
    """Exécute uniquement les réparations (géométries isolées, doublons, faces nulles)"""
    bl_idname = "meshforge.repair"
    bl_label = "Réparer"
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
        if not _check_object_mode(self, context):
            return {'CANCELLED'}
        res = execute_repair(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Réparation terminée."]))
        self.report({'INFO'}, f"MeshForge Repair : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_manifold(bpy.types.Operator):
    """Exécute uniquement les corrections de géométrie Manifold"""
    bl_idname = "meshforge.manifold"
    bl_label = "Corriger Manifold"
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
        if not _check_object_mode(self, context):
            return {'CANCELLED'}
        res = execute_manifold(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Opération Manifold terminée."]))
        self.report({'INFO'}, f"MeshForge Manifold : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_dissolve(bpy.types.Operator):
    """Exécute uniquement la dissolution coplanaire"""
    bl_idname = "meshforge.dissolve"
    bl_label = "Dissoudre"
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
        if not _check_object_mode(self, context):
            return {'CANCELLED'}
        res = execute_dissolve(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Dissolution terminée."]))
        self.report({'INFO'}, f"MeshForge Dissolve : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_topology(bpy.types.Operator):
    """Exécute uniquement la conversion topologique (Triangulation ou Quads)"""
    bl_idname = "meshforge.topology"
    bl_label = "Adapter topologie"
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
        if not _check_object_mode(self, context):
            return {'CANCELLED'}
        res = execute_topology(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Topologie traitée."]))
        self.report({'INFO'}, f"MeshForge Topology : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_simplification(bpy.types.Operator):
    """Exécute uniquement la simplification adaptative contrôlée"""
    bl_idname = "meshforge.simplification"
    bl_label = "Réduire le maillage"
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
        if not _check_object_mode(self, context):
            return {'CANCELLED'}
        res = execute_simplification(context.active_object, context.scene.meshforge_settings)
        if res.get("status") == "ERROR":
            err_msg = " | ".join(res.get("log", ["Erreur lors de la simplification."]))
            self.report({'ERROR'}, f"MeshForge Simplification : {err_msg}")
            return {'CANCELLED'}
        msg = " | ".join(res.get("log", ["Simplification terminée."]))
        self.report({'INFO'}, f"MeshForge Simplification : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_normals(bpy.types.Operator):
    """Exécute uniquement le recalcul et lissage des normales"""
    bl_idname = "meshforge.normals"
    bl_label = "Traiter normales"
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
        if not _check_object_mode(self, context):
            return {'CANCELLED'}
        res = execute_normals(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Normales traitées."]))
        self.report({'INFO'}, f"MeshForge Normals : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_object_data(bpy.types.Operator):
    """Exécute uniquement le nettoyage des matériaux et vertex groups"""
    bl_idname = "meshforge.object_data"
    bl_label = "Nettoyer données d'objet"
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
        if not _check_object_mode(self, context):
            return {'CANCELLED'}
        res = execute_object_data(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Données d'objet nettoyées."]))
        self.report({'INFO'}, f"MeshForge Object Data : {msg}")
        return {'FINISHED'}
