"""MeshForge - Opérateurs pour chaque section exécutable individuellement."""

from __future__ import annotations
import bpy

from ..core.repair_pipeline import execute_repair
from ..core.manifold import execute_manifold
from ..core.dissolve import execute_dissolve
from ..core.topology import execute_topology
from ..core.normals import execute_normals
from ..core.object_data import execute_object_data


class MESHFORGE_OT_repair(bpy.types.Operator):
    """Exécute uniquement les réparations (géométries isolées, doublons, faces nulles)"""
    bl_idname = "meshforge.repair"
    bl_label = "Réparer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
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
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
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
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
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
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        res = execute_topology(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Topologie traitée."]))
        self.report({'INFO'}, f"MeshForge Topology : {msg}")
        return {'FINISHED'}


class MESHFORGE_OT_normals(bpy.types.Operator):
    """Exécute uniquement le recalcul et lissage des normales"""
    bl_idname = "meshforge.normals"
    bl_label = "Traiter normales"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
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
        return context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        res = execute_object_data(context.active_object, context.scene.meshforge_settings)
        msg = " | ".join(res.get("log", ["Données d'objet nettoyées."]))
        self.report({'INFO'}, f"MeshForge Object Data : {msg}")
        return {'FINISHED'}
