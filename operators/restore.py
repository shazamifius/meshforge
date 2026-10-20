"""MeshForge - Opérateur de restauration et de bascule de prévisualisation."""

from __future__ import annotations
import bpy


class MESHFORGE_OT_restore(bpy.types.Operator):
    """Supprime l'objet optimisé et réactive l'objet maillage d'origine"""
    bl_idname = "meshforge.restore"
    bl_label = "Restaurer / Supprimer le résultat"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None and
            "_MF_Optimized" in obj.name and
            context.mode == 'OBJECT' and
            obj.mode == 'OBJECT'
        )

    def execute(self, context):
        current_obj = context.active_object
        if context.mode != 'OBJECT' or (current_obj and current_obj.mode != 'OBJECT'):
            self.report({'WARNING'}, "MeshForge : La restauration requiert le mode Objet. Veuillez repasser en mode Objet (Touche Tab).")
            return {'CANCELLED'}

        orig_name = current_obj.name.replace("_MF_Optimized", "")

        # Retrouver l'objet original
        orig_obj = bpy.data.objects.get(orig_name)
        if orig_obj:
            orig_obj.hide_set(False)
            context.view_layer.objects.active = orig_obj
            orig_obj.select_set(True)

        # Supprimer le résultat courant
        mesh_to_delete = current_obj.data
        bpy.data.objects.remove(current_obj, do_unlink=True)
        if mesh_to_delete and mesh_to_delete.users == 0:
            bpy.data.meshes.remove(mesh_to_delete)

        self.report({'INFO'}, f"Résultat supprimé, objet original '{orig_name}' restauré.")
        return {'FINISHED'}


class MESHFORGE_OT_toggle_wireframe(bpy.types.Operator):
    """Bascule l'affichage filaire (Wireframe) pour inspecter la topologie"""
    bl_idname = "meshforge.toggle_wireframe"
    bl_label = "Affichage Filaire (Wireframe)"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        obj.show_wire = not obj.show_wire
        obj.show_all_edges = obj.show_wire
        status = "activé" if obj.show_wire else "désactivé"
        self.report({'INFO'}, f"Affichage filaire {status}.")
        return {'FINISHED'}
