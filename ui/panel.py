"""MeshForge - Interface utilisateur dans le 3D Viewport (Sidebar N-Panel).
Organise les contrôles en panneaux pliables ergonomiques et clairs.
"""

from __future__ import annotations
import bpy


class VIEW3D_PT_meshforge_base:
    """Classe de base pour tous les panneaux MeshForge."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MeshForge'


class VIEW3D_PT_meshforge_main(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Panneau principal de contrôle MeshForge."""
    bl_idname = 'VIEW3D_PT_meshforge_main'
    bl_label = 'MeshForge'

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        obj = context.active_object

        # Avertissement si aucun objet maillage sélectionné
        if not obj or obj.type != 'MESH':
            box = layout.box()
            box.label(text="Sélectionnez un maillage (Mesh)", icon='INFO')
            return

        # 1. Bouton principal d'optimisation
        col = layout.column(align=True)
        col.scale_y = 1.4
        btn = col.operator("meshforge.optimize", text="Optimiser le maillage", icon='MOD_DECIM')

        # 2. Boutons d'action secondaire
        row = layout.row(align=True)
        row.operator("meshforge.analyze", text="Analyser seulement", icon='VIEWZOOM')
        row.operator("meshforge.toggle_wireframe", text="Filaire", icon='SHADING_WIRE')

        # 3. Bouton Restaurer si un résultat existe
        if "_MF_Optimized" in obj.name:
            box_res = layout.box()
            box_res.label(text="Objet résultat actif", icon='CHECKMARK')
            box_res.operator("meshforge.restore", text="Restaurer l'original", icon='RECOVER_LAST')

        # 4. Paramètres de Workflow et sécurité
        box_flow = layout.box()
        box_flow.label(text="Sécurité & Préservation :", icon='SHIELD')
        box_flow.prop(props, "create_new_object")
        if props.create_new_object:
            box_flow.prop(props, "hide_original")
        else:
            row_warn = box_flow.row()
            row_warn.alert = True
            row_warn.prop(props, "destructive_mode", text="Mode destructif direct !")


class VIEW3D_PT_meshforge_repair(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.1 - Repair"""
    bl_idname = 'VIEW3D_PT_meshforge_repair'
    bl_label = '1. Réparation (Repair)'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_repair", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_repair

        # Loose Geometry
        col = layout.column(align=True)
        col.prop(props, "repair_loose_geometry")
        if props.repair_loose_geometry:
            row = col.row(align=True)
            row.prop(props, "loose_verts", toggle=True)
            row.prop(props, "loose_edges", toggle=True)
            row.prop(props, "loose_faces", toggle=True)

        layout.separator()

        # Doubles
        col = layout.column(align=True)
        col.prop(props, "repair_doubles")
        if props.repair_doubles:
            col.prop(props, "doubles_relative")
            if props.doubles_relative:
                col.prop(props, "doubles_relative_factor")
            else:
                col.prop(props, "doubles_tolerance")

        layout.separator()

        # Zero Faces
        col = layout.column(align=True)
        col.prop(props, "repair_zero_faces")
        if props.repair_zero_faces:
            col.prop(props, "zero_faces_threshold")

        layout.separator()

        # Dispensables
        col = layout.column(align=True)
        col.prop(props, "repair_dispensables")
        if props.repair_dispensables:
            col.prop(props, "dispensable_angle")

        layout.separator()
        layout.operator("meshforge.repair", text="Exécuter Réparation", icon='TOOL_SETTINGS')


class VIEW3D_PT_meshforge_manifold(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.2 - Manifold"""
    bl_idname = 'VIEW3D_PT_meshforge_manifold'
    bl_label = '2. Cohérence Manifold'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_manifold", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_manifold

        layout.prop(props, "manifold_mode")

        col = layout.column(align=True)
        col.prop(props, "remove_wire_geometry")

        col.prop(props, "fill_holes")
        if props.fill_holes:
            col.prop(props, "fill_holes_max_sides")

        if props.manifold_mode == 'AGGRESSIVE':
            box = layout.box()
            box.alert = True
            box.label(text="Options Agressives (Destruction risquée) :", icon='ERROR')
            box.prop(props, "remove_non_manifold_faces")
            box.prop(props, "remove_non_manifold_verts")

        col_plan = layout.column(align=True)
        col_plan.prop(props, "make_planar")
        if props.make_planar:
            col_plan.prop(props, "make_planar_factor")
            col_plan.prop(props, "make_planar_iterations")

        col_flat = layout.column(align=True)
        col_flat.prop(props, "flatten_faces")
        if props.flatten_faces:
            col_flat.prop(props, "flatten_iterations")

        layout.separator()
        layout.operator("meshforge.manifold", text="Exécuter Manifold", icon='MOD_SOLIDIFY')


class VIEW3D_PT_meshforge_dissolve(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.3 - Dissolve"""
    bl_idname = 'VIEW3D_PT_meshforge_dissolve'
    bl_label = '3. Dissolution Coplanaire'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_dissolve", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_dissolve

        layout.prop(props, "dissolve_mode")
        layout.prop(props, "dissolve_angle")

        box = layout.box()
        box.label(text="Préservations strictes :", icon='LOCKED')
        box.prop(props, "preserve_sharp")
        box.prop(props, "preserve_seams")
        box.prop(props, "preserve_materials")
        box.prop(props, "preserve_uvs")
        box.prop(props, "preserve_boundaries")

        layout.separator()
        layout.operator("meshforge.dissolve", text="Exécuter Dissolution", icon='MOD_DECIM')


class VIEW3D_PT_meshforge_topology(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.4 - Topology"""
    bl_idname = 'VIEW3D_PT_meshforge_topology'
    bl_label = '4. Topologie (Tris / Quads)'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_topology", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_topology

        layout.prop(props, "topology_mode")

        if props.topology_mode == 'TRIS':
            col = layout.column(align=True)
            col.prop(props, "triangulate_quad_method")
            col.prop(props, "triangulate_ngon_method")
        elif props.topology_mode == 'QUADS':
            col = layout.column(align=True)
            col.prop(props, "quads_face_threshold")
            col.prop(props, "quads_shape_threshold")
            col.prop(props, "preserve_topology_attributes")

        layout.separator()
        layout.operator("meshforge.topology", text="Exécuter Topologie", icon='MOD_REMESH')


class VIEW3D_PT_meshforge_normals(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.5 - Normals"""
    bl_idname = 'VIEW3D_PT_meshforge_normals'
    bl_label = '5. Normales & Ombrage'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_normals", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_normals

        col = layout.column(align=True)
        col.prop(props, "recalculate_normals")
        if props.recalculate_normals:
            col.prop(props, "recalculate_direction")

        layout.separator()

        col_smooth = layout.column(align=True)
        col_smooth.prop(props, "apply_auto_smooth")
        if props.apply_auto_smooth:
            col_smooth.prop(props, "auto_smooth_angle")

        layout.separator()

        col_opt = layout.column(align=True)
        col_opt.prop(props, "weighted_normals")
        col_opt.prop(props, "clear_custom_split_normals")
        col_opt.prop(props, "clear_sharp_edges")

        layout.separator()
        layout.operator("meshforge.normals", text="Exécuter Normales", icon='NORMALS_FACE')


class VIEW3D_PT_meshforge_object_data(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.6 - Object Data"""
    bl_idname = 'VIEW3D_PT_meshforge_object_data'
    bl_label = '6. Données d\'Objet'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_object_data", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_object_data

        col = layout.column(align=True)
        col.prop(props, "clean_material_doubles")
        col.prop(props, "clean_unused_material_slots")
        col.prop(props, "clean_empty_vertex_groups")

        layout.separator()
        layout.operator("meshforge.object_data", text="Exécuter Nettoyage Données", icon='OUTLINER_OB_MESH')


class VIEW3D_PT_meshforge_report(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 8 - Rapport et Métriques"""
    bl_idname = 'VIEW3D_PT_meshforge_report'
    bl_label = 'Rapport & Statistiques'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings

        box = layout.box()
        box.label(text=f"Statut : {props.last_status}", icon='PRESET')
        if props.last_duration > 0:
            box.label(text=f"Durée totale : {props.last_duration:.3f} s", icon='TIME')

        # Tableau comparatif Avant / Après
        col = box.column(align=True)
        row = col.row()
        row.label(text="Métrique")
        row.label(text="Avant")
        row.label(text="Après")

        row_tri = col.row()
        row_tri.label(text="Triangles estim.")
        row_tri.label(text=str(props.last_tris_before))
        row_tri.label(text=str(props.last_tris_after))

        row_f = col.row()
        row_f.label(text="Faces")
        row_f.label(text=str(props.last_faces_before))
        row_f.label(text=str(props.last_faces_after))

        row_v = col.row()
        row_v.label(text="Sommets")
        row_v.label(text=str(props.last_verts_before))
        row_v.label(text=str(props.last_verts_after))

        if props.last_reduction > 0:
            box.label(text=f"Réduction globale : {props.last_reduction:.1f} %", icon='SOLO_ON')

        # Boutons d'exportation de rapport (Phase B)
        row_exp = box.row(align=True)
        op_json = row_exp.operator("meshforge.export_report", text="Exporter (JSON)", icon='DOCUMENTS')
        op_json.format_type = 'JSON'
        op_txt = row_exp.operator("meshforge.export_report", text="Exporter (Texte)", icon='TEXT')
        op_txt.format_type = 'TXT'

        if props.last_logs:
            box_log = layout.box()
            box_log.label(text="Détails & Événements :", icon='TEXT')
            for line in props.last_logs.split("\n"):
                if line.strip():
                    box_log.label(text=line)


classes = (
    VIEW3D_PT_meshforge_main,
    VIEW3D_PT_meshforge_repair,
    VIEW3D_PT_meshforge_manifold,
    VIEW3D_PT_meshforge_dissolve,
    VIEW3D_PT_meshforge_topology,
    VIEW3D_PT_meshforge_normals,
    VIEW3D_PT_meshforge_object_data,
    VIEW3D_PT_meshforge_report,
)


def register_ui():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister_ui():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
