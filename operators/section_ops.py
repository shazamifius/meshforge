"""MeshForge - Opérateurs pour chaque section exécutable individuellement."""

from __future__ import annotations
import bpy
import time

from ..core.repair_pipeline import execute_repair
from ..core.manifold import execute_manifold
from ..core.dissolve import execute_dissolve
from ..core.topology import execute_topology
from ..core.normals import execute_normals
from ..core.object_data import execute_object_data
from ..core.simplification import execute_simplification
from ..core.pipeline import duplicate_object_non_destructive


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
        t0 = time.perf_counter()
        props = context.scene.meshforge_settings
        source_obj = context.active_object

        target_obj = source_obj
        if getattr(props, "create_new_object", True) and not source_obj.name.endswith("_MF_Optimized"):
            target_obj = duplicate_object_non_destructive(source_obj)
            if getattr(props, "hide_original", True):
                source_obj.hide_set(True)
            bpy.context.view_layer.objects.active = target_obj
            target_obj.select_set(True)

        m_in = target_obj.data
        v_before = len(m_in.vertices)
        e_before = len(m_in.edges)
        f_before = len(m_in.polygons)
        try:
            m_in.calc_loop_triangles()
            t_before = len(m_in.loop_triangles) if hasattr(m_in, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in m_in.polygons)
        except Exception:
            t_before = sum(max(0, len(p.vertices) - 2) for p in m_in.polygons)

        res = execute_dissolve(target_obj, props)
        dt = time.perf_counter() - t0

        if res.get("status") == "ERROR":
            err_msg = " | ".join(res.get("log", ["Erreur lors de la dissolution."]))
            self.report({'ERROR'}, f"MeshForge Dissolve : {err_msg}")
            return {'CANCELLED'}

        m_out = target_obj.data
        v_after = len(m_out.vertices)
        e_after = len(m_out.edges)
        f_after = len(m_out.polygons)
        try:
            m_out.calc_loop_triangles()
            t_after = len(m_out.loop_triangles) if hasattr(m_out, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in m_out.polygons)
        except Exception:
            t_after = sum(max(0, len(p.vertices) - 2) for p in m_out.polygons)

        props.last_status = "Succès"
        props.last_duration = dt
        props.last_result_obj_name = target_obj.name
        props.last_verts_before = v_before
        props.last_verts_after = v_after
        props.last_edges_before = e_before
        props.last_edges_after = e_after
        props.last_faces_before = f_before
        props.last_faces_after = f_after
        props.last_tris_before = t_before
        props.last_tris_after = t_after
        if t_before > 0:
            props.last_reduction = round(((t_before - t_after) / t_before) * 100.0, 2)
        elif f_before > 0:
            props.last_reduction = round(((f_before - f_after) / f_before) * 100.0, 2)
        else:
            props.last_reduction = 0.0

        props.last_deviation_measured = False
        props.last_max_hausdorff = 0.0
        props.last_mean_deviation = 0.0
        props.last_max_normal_angle = 0.0

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
        t0 = time.perf_counter()
        props = context.scene.meshforge_settings
        source_obj = context.active_object

        target_obj = source_obj
        if getattr(props, "create_new_object", True) and not source_obj.name.endswith("_MF_Optimized"):
            target_obj = duplicate_object_non_destructive(source_obj)
            if getattr(props, "hide_original", True):
                source_obj.hide_set(True)
            bpy.context.view_layer.objects.active = target_obj
            target_obj.select_set(True)

        m_in = target_obj.data
        v_before = len(m_in.vertices)
        e_before = len(m_in.edges)
        f_before = len(m_in.polygons)
        try:
            m_in.calc_loop_triangles()
            t_before = len(m_in.loop_triangles) if hasattr(m_in, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in m_in.polygons)
        except Exception:
            t_before = sum(max(0, len(p.vertices) - 2) for p in m_in.polygons)

        ref_obj = source_obj if target_obj != source_obj else None
        res = execute_simplification(target_obj, props, orig_reference_obj=ref_obj)
        dt = time.perf_counter() - t0

        if res.get("status") == "ERROR":
            err_msg = " | ".join(res.get("log", ["Erreur lors de la simplification."]))
            self.report({'ERROR'}, f"MeshForge Simplification : {err_msg}")
            return {'CANCELLED'}

        m_out = target_obj.data
        v_after = len(m_out.vertices)
        e_after = len(m_out.edges)
        f_after = len(m_out.polygons)
        try:
            m_out.calc_loop_triangles()
            t_after = len(m_out.loop_triangles) if hasattr(m_out, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in m_out.polygons)
        except Exception:
            t_after = sum(max(0, len(p.vertices) - 2) for p in m_out.polygons)

        props.last_status = "Succès"
        props.last_duration = dt
        props.last_result_obj_name = target_obj.name
        props.last_verts_before = v_before
        props.last_verts_after = v_after
        props.last_edges_before = e_before
        props.last_edges_after = e_after
        props.last_faces_before = f_before
        props.last_faces_after = f_after
        props.last_tris_before = t_before
        props.last_tris_after = t_after
        if t_before > 0:
            props.last_reduction = round(((t_before - t_after) / t_before) * 100.0, 2)
        elif f_before > 0:
            props.last_reduction = round(((f_before - f_after) / f_before) * 100.0, 2)
        else:
            props.last_reduction = 0.0

        geom_val = res.get("geometric_validation", {})
        if geom_val and geom_val.get("valid"):
            props.last_deviation_measured = True
            props.last_max_hausdorff = geom_val.get("hausdorff_distance", 0.0)
            props.last_mean_deviation = geom_val.get("mean_distance", 0.0)
            props.last_max_normal_angle = geom_val.get("max_normal_deviation_deg", 0.0)
        else:
            props.last_deviation_measured = False
            props.last_max_hausdorff = 0.0
            props.last_mean_deviation = 0.0
            props.last_max_normal_angle = 0.0

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
