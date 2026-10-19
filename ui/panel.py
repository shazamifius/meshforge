"""MeshForge - Interface utilisateur dans le 3D Viewport (Sidebar N-Panel).
Organise les contrôles en panneaux pliables ergonomiques et clairs.
"""

from __future__ import annotations
import bpy

from ..operators.topology_inspect import get_active_diagnosis


class VIEW3D_PT_meshforge_base:
    """Classe de base pour tous les panneaux MeshForge."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MeshForge'


class VIEW3D_PT_meshforge_main(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Panneau principal de l'assistant MeshForge (Phase D1)."""
    bl_idname = 'VIEW3D_PT_meshforge_main'
    bl_label = 'MeshForge — Assistant 3D'

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        obj = context.active_object

        # ---------------------------------------------------------
        # 1. OBJET SÉLECTIONNÉ & STATISTIQUES IMMÉDIATES
        # ---------------------------------------------------------
        box_obj = layout.box()
        if not obj or obj.type != 'MESH':
            box_obj.label(text="Aucun maillage sélectionné", icon='INFO')
            box_obj.label(text="Sélectionnez un objet 3D pour commencer.", icon='FORWARD')
            return

        mesh = obj.data
        row_title = box_obj.row(align=True)
        row_title.label(text=f"Objet : {obj.name}", icon='MESH_DATA')
        if "_MF_Optimized" in obj.name:
            row_title.label(text="[Optimisé]", icon='CHECKMARK')

        # Comptage immédiat exact
        mesh.calc_loop_triangles()
        real_tris = len(mesh.loop_triangles) if hasattr(mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

        grid = box_obj.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        grid.label(text=f"Sommets : {len(mesh.vertices):,}")
        grid.label(text=f"Arêtes : {len(mesh.edges):,}")
        grid.label(text=f"Faces : {len(mesh.polygons):,}")
        grid.label(text=f"Triangles réels : {real_tris:,}")

        # ---------------------------------------------------------
        # 2. CHOISIR SON OBJECTIF (LES 3 MODES D'ASSET)
        # ---------------------------------------------------------
        box_mode = layout.box()
        box_mode.label(text="1. Choisir votre objectif :", icon='TARGET')
        col_m = box_mode.column(align=True)
        col_m.prop(props, "asset_target_mode", text="")

        # Explication en français simple selon le mode choisi
        mode = props.asset_target_mode
        box_exp = box_mode.box()
        if mode == 'GAME_TRIANGLES':
            box_exp.label(text="Mode Jeu (Triangles) :", icon='SOLO_ON')
            box_exp.label(text="• Priorité : Réduire le poids géométrique (LODs, décors, rochers).")
            box_exp.label(text="• Préserve la silhouette, les UVs et les matériaux.")
            box_exp.label(text="• Les triangles sont conservés et optimisés.")
        elif mode == 'DEFORMABLE_QUADS':
            box_exp.label(text="Mode Déformable (Quads) :", icon='OUTLINER_OB_ARMATURE')
            box_exp.label(text="• Priorité : Fluidité de déformation pour l'animation et le rigging.")
            box_exp.label(text="• Détecte les N-gones et triangles coupant les boucles d'arêtes.")
            box_exp.label(text="• Vise une topologie propre pour personnages et vêtements.")
        elif mode == 'HYBRID_CLEANUP':
            box_exp.label(text="Mode Hybride (Diagnostic) :", icon='PREFERENCES')
            box_exp.label(text="• Priorité : Objets mécaniques, assemblages et maillages mixtes.")
            box_exp.label(text="• Nettoyage conservateur sans forcer quads ou triangulation.")
            box_exp.label(text="• Idéal pour préparer un asset sans objectif tranché.")

        # ---------------------------------------------------------
        # 3. ACTIONS PRINCIPALES
        # ---------------------------------------------------------
        layout.label(text="2. Actions recommandées :", icon='PLAY')

        # Bouton principal Nettoyage / Optimisation
        col_act = layout.column(align=True)
        col_act.scale_y = 1.3
        col_act.operator("meshforge.optimize", text="Nettoyer rapidement le modèle", icon='CHECKMARK')

        row_diag = layout.row(align=True)
        row_diag.scale_y = 1.1
        row_diag.operator("meshforge.analyze_topology", text="Analyser la topologie", icon='VIEWZOOM')
        row_diag.operator("meshforge.simplification", text="Réduire les triangles", icon='MOD_DECIM')

        row_tools = layout.row(align=True)
        row_tools.operator("meshforge.analyze", text="Rapport global", icon='TEXT')
        row_tools.operator("meshforge.toggle_wireframe", text="Filaire", icon='SHADING_WIRE')

        # Bouton Restaurer si objet optimisé
        if "_MF_Optimized" in obj.name:
            box_res = layout.box()
            box_res.label(text="Objet résultat actif :", icon='INFO')
            box_res.operator("meshforge.restore", text="Restaurer l'original", icon='RECOVER_LAST')

        # ---------------------------------------------------------
        # 4. DIAGNOSTIC INTERACTIF & CODE COULEUR DES ANOMALIES
        # ---------------------------------------------------------
        diag = get_active_diagnosis(obj.name)
        if diag and diag.get("valid"):
            defects = diag.get("defects", [])
            summary = diag.get("summary", {})

            box_diag = layout.box()
            row_dh = box_diag.row()
            row_dh.label(text="Diagnostic topologique :", icon='COLOR')
            row_dh.operator("meshforge.clear_defect_view", text="", icon='PANEL_CLOSE')

            # Pastilles sémantiques colorées
            col_badges = box_diag.column(align=True)
            r1 = col_badges.row(align=True)
            r1.label(text=f"● N-gones : {summary.get('ngons', 0)}", icon='RADIOBUT_ON') # Orange
            r1.label(text=f"● Triangles : {summary.get('suspect_triangles', 0)}", icon='RADIOBUT_OFF') # Bleu
            r2 = col_badges.row(align=True)
            r2.label(text=f"● Dégénérescences : {summary.get('degeneracies', 0)}", icon='ERROR') # Rouge
            r2.label(text=f"● Éléments isolés : {summary.get('isolated', 0)}", icon='DOT') # Violet

            if defects:
                box_diag.separator()
                box_diag.prop(props, "active_defect_filter", text="Filtre")

                # Filtrer les anomalies selon le filtre actif
                f_filter = props.active_defect_filter
                visible_defects = [
                    (i, d) for i, d in enumerate(defects)
                    if f_filter == 'ALL' or d.get("category") == f_filter
                ]

                box_diag.label(text=f"{len(visible_defects)} anomalie(s) répertoriée(s) :")

                # Affichage des 5 premières anomalies visibles avec zoom
                for idx_orig, defect in visible_defects[:5]:
                    b_item = box_diag.box()
                    r_item = b_item.row(align=True)
                    r_item.label(text=defect.get("name", "Anomalie"), icon='RIGHTARROW')
                    op_zoom = r_item.operator("meshforge.focus_defect", text="Zoomer", icon='ZOOM_SELECTED')
                    op_zoom.defect_index = idx_orig

                    col_exp = b_item.column(align=True)
                    col_exp.scale_y = 0.8
                    col_exp.label(text=defect.get("explanation", ""))
                    col_exp.label(text=f"Action conseillée : {defect.get('recommendation', '')}")

                if len(visible_defects) > 5:
                    box_diag.label(text=f"... et {len(visible_defects) - 5} autre(s) anomalie(s).")
            else:
                box_diag.label(text="Aucune anomalie topologique critique détectée !", icon='CHECKMARK')

        # ---------------------------------------------------------
        # 5. MODE EXPERT / RÉGLAGES AVANCÉS REPLIABLE
        # ---------------------------------------------------------
        box_exp_toggle = layout.box()
        box_exp_toggle.prop(
            props,
            "show_expert_mode",
            text="Mode Expert / Réglages avancés",
            icon='TRIA_DOWN' if props.show_expert_mode else 'TRIA_RIGHT'
        )

        if props.show_expert_mode:
            box_flow = box_exp_toggle.box()
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


class VIEW3D_PT_meshforge_simplification(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 4 - Simplification intelligente (Phase C)"""
    bl_idname = 'VIEW3D_PT_meshforge_simplification'
    bl_label = '4. Simplification Intelligente'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_simplification", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_simplification

        col = layout.column(align=True)
        col.prop(props, "simplification_mode")

        if props.simplification_mode == 'PERCENTAGE':
            col.prop(props, "simplification_percentage")
        elif props.simplification_mode == 'BUDGET_TRIANGLES':
            col.prop(props, "simplification_target_triangles")

        layout.separator()

        box_tol = layout.box()
        box_tol.prop(props, "enable_simplification_tolerance")
        if props.enable_simplification_tolerance:
            box_tol.prop(props, "simplification_max_tolerance")
            box_tol.prop(props, "tolerance_relative")

        col_opt = layout.column(align=True)
        col_opt.prop(props, "collapse_triangulate")
        col_opt.prop(props, "preserve_normals_angle")

        layout.separator()
        layout.operator("meshforge.simplification", text="Exécuter Simplification", icon='MOD_DECIM')


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
    VIEW3D_PT_meshforge_simplification,
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
