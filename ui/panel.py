"""MeshForge - Interface utilisateur dans le 3D Viewport (Sidebar N-Panel).
Organise les contrôles selon le parcours guidé utilisateur (Phases UX1 à UX5) :
1. Objet sélectionné & statistiques directes
2. Choix de l'objectif parmi les 5 profils prédéfinis
3. Diagnostic topologique & santé globale
4. Actions prioritaires recommandées avec badges de risque
5. Tableau détaillé des constats avec filtres et cadrage (Zoomer)
6. Réduction de polygones optionnelle clairement délimitée
7. Mode Expert repliable déverrouillant les réglages techniques
"""

from __future__ import annotations
import bpy

from ..operators.topology_inspect import get_active_diagnosis
from ..core.structured_diagnosis import PROFILES, PROFILE_ALIAS, CATEGORIES


class VIEW3D_PT_meshforge_base:
    """Classe de base pour tous les panneaux MeshForge."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MeshForge'


class VIEW3D_PT_meshforge_main(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Panneau principal de l'assistant MeshForge (Phases UX1 - UX5)."""
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

        # Comptage immédiat exact sans bmesh lourd
        mesh.calc_loop_triangles()
        real_tris = len(mesh.loop_triangles) if hasattr(mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

        grid = box_obj.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        grid.label(text=f"Sommets : {len(mesh.vertices):,}")
        grid.label(text=f"Arêtes : {len(mesh.edges):,}")
        grid.label(text=f"Faces : {len(mesh.polygons):,}")
        grid.label(text=f"Triangles réels : {real_tris:,}")

        # Bouton Restaurer si objet optimisé actif
        if "_MF_Optimized" in obj.name:
            box_res = layout.box()
            box_res.label(text="Objet résultat actif :", icon='INFO')
            box_res.operator("meshforge.restore", text="Restaurer l'original", icon='RECOVER_LAST')

        # ---------------------------------------------------------
        # 2. ÉTAPE 1 : CHOISIR VOTRE OBJECTIF (LES 5 PROFILS)
        # ---------------------------------------------------------
        box_mode = layout.box()
        box_mode.label(text="1. Choisir votre objectif :", icon='TRACKING')
        col_m = box_mode.column(align=True)
        col_m.prop(props, "asset_target_mode", text="")

        # Explication concise du profil actif
        mode = props.asset_target_mode
        resolved_profile = PROFILE_ALIAS.get(mode, mode)
        p_info = PROFILES.get(resolved_profile, PROFILES.get("GENERAL", {}))

        box_exp = box_mode.box()
        col_exp = box_exp.column(align=True)
        col_exp.scale_y = 0.85
        col_exp.label(text=f"{p_info.get('name', 'Profil')} :", icon=p_info.get('icon', 'HELP'))
        col_exp.label(text=p_info.get('summary', ''))

        # ---------------------------------------------------------
        # 3. ÉTAPE 2 : ANALYSER LE MAILLAGE (ACTION CENTRALE)
        # ---------------------------------------------------------
        box_step2 = layout.box()
        box_step2.label(text="2. Diagnostic du maillage :", icon='VIEWZOOM')

        col_diag_btn = box_step2.column(align=True)
        col_diag_btn.scale_y = 1.3
        col_diag_btn.operator("meshforge.analyze_topology", text="Analyser le maillage", icon='VIEWZOOM')

        row_tools = box_step2.row(align=True)
        row_tools.operator("meshforge.toggle_wireframe", text="Afficher le filaire", icon='SHADING_WIRE')
        row_tools.operator("meshforge.clear_defect_view", text="Effacer l'inspection", icon='PANEL_CLOSE')

        # ---------------------------------------------------------
        # 4. ÉTAPE 3 : RÉSULTATS & SANTÉ GLOBALE
        # ---------------------------------------------------------
        diag = get_active_diagnosis(obj.name)
        if diag and diag.get("valid"):
            structured = diag.get("structured", {})
            findings = diag.get("findings", [])
            health = structured.get("health", {})
            total_defects = health.get("defects_count", 0)
            total_risks = health.get("risks_count", 0)
            total_obs = health.get("observations_count", 0)

            box_health = layout.box()
            row_hh = box_health.row()
            if health.get("status") == "HEALTHY":
                row_hh.label(text="Santé : Maillage sain pour cet objectif", icon='CHECKMARK')
            elif health.get("status") == "CRITICAL":
                row_hh.alert = True
                row_hh.label(text=f"Santé : {total_defects} anomalie(s) critique(s)", icon='ERROR')
            else:
                row_hh.label(text=f"Santé : {total_risks} point(s) de vigilance", icon='INFO')

            # Pastilles de comptage
            row_counts = box_health.row(align=True)
            r_def = row_counts.row(align=True)
            if total_defects > 0:
                r_def.alert = True
            r_def.label(text=f"Défauts : {total_defects}", icon='CANCEL')
            row_counts.label(text=f"Risques : {total_risks}", icon='HELP')
            row_counts.label(text=f"Observations : {total_obs}", icon='INFO')

            # ---------------------------------------------------------
            # 5. ÉTAPE 4 : ACTIONS PRIORITAIRES RECOMMANDÉES (MAX 2-3)
            # ---------------------------------------------------------
            facts = diag.get("facts", {})

            has_degeneracies = (
                facts.get("zero_area_faces_count", 0) > 0 or
                facts.get("degenerate_edges_count", 0) > 0 or
                facts.get("isolated_verts_count", 0) > 0 or
                facts.get("loose_edges_count", 0) > 0
            )
            has_ngons = (facts.get("ngons_count", 0) > 0)

            box_acts = layout.box()
            box_acts.label(text="3. Actions recommandées :", icon='TOOL_SETTINGS')

            shown_actions = 0

            # Action 1: Nettoyage conservateur sûr
            if has_degeneracies:
                shown_actions += 1
                b_act1 = box_acts.box()
                r1 = b_act1.row()
                r1.label(text="Nettoyage conservateur sûr", icon='BRUSH_DATA')
                r1.label(text="[Risque Faible]", icon='CHECKMARK')

                col_b1 = b_act1.column(align=True)
                col_b1.scale_y = 1.2
                col_b1.operator("meshforge.conservative_clean", text="Nettoyer les dégénérescences (sans décimer)", icon='BRUSH_DATA')

                c_info1 = b_act1.column(align=True)
                c_info1.scale_y = 0.75
                c_info1.label(text="• Supprime faces nulles, arêtes sans face et éléments orphelins.")
                c_info1.label(text="• Fusionne les doublons en protégeant les coutures UV.")
                c_info1.label(text="• 100% sans décimation : géométrie utile préservée.")

            # Action 2: Découpe des N-gones (selon profil)
            if has_ngons and resolved_profile in ("GAME_ASSET", "DEFORMABLE_CHAR", "GENERAL"):
                shown_actions += 1
                b_act2 = box_acts.box()
                r2 = b_act2.row()
                r2.label(text="Découper les N-gones", icon='MOD_TRIANGULATE')
                r2.label(text="[Risque Contrôlé]", icon='INFO')

                col_b2 = b_act2.column(align=True)
                col_b2.scale_y = 1.2
                col_b2.operator("meshforge.cut_ngons", text=f"Découper les {facts.get('ngons_count', 0)} N-gones", icon='MOD_TRIANGULATE')

                c_info2 = b_act2.column(align=True)
                c_info2.scale_y = 0.75
                c_info2.label(text="• Ear-clipping et Beauty triangulation avec préservation des UVs.")
                c_info2.label(text="• Rollback automatique en cas d'altération.")

            if shown_actions == 0:
                b_ok = box_acts.box()
                b_ok.label(text="Aucune action corrective urgente requise.", icon='CHECKMARK')
                b_ok.label(text="La géométrie respecte les critères du profil actif.")

            # ---------------------------------------------------------
            # 6. ÉTAPE 5 : TABLEAU DÉTAILLÉ DES CONSTATS (REPLIABLE)
            # ---------------------------------------------------------
            box_table = layout.box()
            r_t_head = box_table.row(align=True)
            r_t_head.prop(
                props,
                "show_findings_table",
                text=f"Tableau détaillé ({len(findings)} constats)",
                icon='TRIA_DOWN' if props.show_findings_table else 'TRIA_RIGHT'
            )

            if props.show_findings_table and findings:
                # Filtres
                col_filters = box_table.column(align=True)
                col_filters.prop(props, "active_category_filter", text="Catégorie")
                col_filters.prop(props, "active_severity_filter", text="Sévérité")

                cat_f = props.active_category_filter
                sev_f = props.active_severity_filter

                filtered_findings = []
                for f in findings:
                    f_cat = getattr(f, "category", None) or (f.get("category") if isinstance(f, dict) else "")
                    f_sev = getattr(f, "severity", None) or (f.get("severity") if isinstance(f, dict) else "")
                    if cat_f != 'ALL' and f_cat != cat_f:
                        continue
                    if sev_f != 'ALL' and f_sev != sev_f:
                        continue
                    filtered_findings.append(f)

                box_table.label(text=f"{len(filtered_findings)} constat(s) affiché(s) :", icon='FILTER')

                # Affichage des constats filtrés (limité à 8 pour clarté)
                for f in filtered_findings[:8]:
                    f_id = getattr(f, "id", None) or (f.get("id") if isinstance(f, dict) else "")
                    f_name = getattr(f, "name", None) or (f.get("name") if isinstance(f, dict) else "Constat")
                    f_sev = getattr(f, "severity", None) or (f.get("severity") if isinstance(f, dict) else "OBSERVATION")
                    f_exp = getattr(f, "explanation", None) or (f.get("explanation") if isinstance(f, dict) else "")
                    f_conseq = getattr(f, "consequence", None) or (f.get("consequence") if isinstance(f, dict) else "")
                    f_rec = getattr(f, "recommendation", None) or (f.get("recommendation") if isinstance(f, dict) else "")
                    f_indices = getattr(f, "indices", None) or (f.get("indices") if isinstance(f, dict) else [])

                    b_find = box_table.box()
                    r_f_top = b_find.row(align=True)

                    if f_sev == 'DEFECT':
                        r_f_top.alert = True
                        r_f_top.label(text="[DÉFAUT]", icon='CANCEL')
                    elif f_sev == 'RISK':
                        r_f_top.label(text="[RISQUE]", icon='HELP')
                    else:
                        r_f_top.label(text="[INFO]", icon='INFO')

                    r_f_top.label(text=f_name)

                    if f_indices:
                        op_z = r_f_top.operator("meshforge.focus_defect", text="Zoomer", icon='ZOOM_SELECTED')
                        op_z.finding_id = f_id

                    c_f_det = b_find.column(align=True)
                    c_f_det.scale_y = 0.75
                    if f_exp:
                        c_f_det.label(text=f_exp)
                    if f_conseq:
                        c_f_det.label(text=f"Impact : {f_conseq}")
                    if f_rec:
                        c_f_det.label(text=f"Conseil : {f_rec}")

                if len(filtered_findings) > 8:
                    box_table.label(text=f"... et {len(filtered_findings) - 8} autre(s) constat(s).")

        # ---------------------------------------------------------
        # 7. ÉTAPE 6 : RÉDUCTION DE POLYGONES / DÉCIMATION (OPTIONNEL)
        # ---------------------------------------------------------
        box_sim = layout.box()
        box_sim.label(text="4. Réduction de polygones (Optionnel) :", icon='MOD_DECIM')

        col_s = box_sim.column(align=True)
        col_s.prop(props, "simplification_percentage", text="Pourcentage cible (%)", slider=True)

        col_s_btn = box_sim.column(align=True)
        col_s_btn.scale_y = 1.2
        col_s_btn.operator("meshforge.simplification", text="Réduire les triangles (Décimateur natif)", icon='MOD_DECIM')

        col_s_warn = box_sim.column(align=True)
        col_s_warn.scale_y = 0.75
        col_s_warn.label(text="⚠️ Moteur natif Decimate : adapté aux décors rigides.", icon='ERROR')
        col_s_warn.label(text="Sur surfaces sculptées/courbées, risque d'artefacts d'ombrage noirs.")

        # ---------------------------------------------------------
        # 8. ÉTAPE 7 : MODE EXPERT REPLIABLE
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
            box_flow.label(text="Sécurité & Préservation :", icon='LOCKED')
            box_flow.prop(props, "create_new_object")
            if props.create_new_object:
                box_flow.prop(props, "hide_original")
            else:
                row_warn = box_flow.row()
                row_warn.alert = True
                row_warn.prop(props, "destructive_mode", text="Mode destructif direct !")

            box_flow.separator()
            box_flow.label(text="Pipeline combiné complet :", icon='MODIFIER')
            box_flow.operator("meshforge.optimize", text="Exécuter tout le pipeline (Réparation + Décimation)", icon='PLAY')


class VIEW3D_PT_meshforge_repair(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.1 - Repair (Mode Expert)"""
    bl_idname = 'VIEW3D_PT_meshforge_repair'
    bl_label = '1. Réparation (Repair)'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        return props is not None and props.show_expert_mode

    def draw_header(self, context):
        props = context.scene.meshforge_settings
        self.layout.prop(props, "enable_repair", text="")

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings
        layout.active = props.enable_repair

        col = layout.column(align=True)
        col.prop(props, "repair_loose_geometry")
        if props.repair_loose_geometry:
            row = col.row(align=True)
            row.prop(props, "loose_verts", toggle=True)
            row.prop(props, "loose_edges", toggle=True)
            row.prop(props, "loose_faces", toggle=True)

        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "repair_doubles")
        if props.repair_doubles:
            col.prop(props, "doubles_relative")
            if props.doubles_relative:
                col.prop(props, "doubles_relative_factor")
            else:
                col.prop(props, "doubles_tolerance")

        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "repair_zero_faces")
        if props.repair_zero_faces:
            col.prop(props, "zero_faces_threshold")

        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "repair_dispensables")
        if props.repair_dispensables:
            col.prop(props, "dispensable_angle")

        layout.separator()
        layout.operator("meshforge.repair", text="Exécuter Réparation", icon='TOOL_SETTINGS')


class VIEW3D_PT_meshforge_manifold(VIEW3D_PT_meshforge_base, bpy.types.Panel):
    """Section 3.2 - Manifold (Mode Expert)"""
    bl_idname = 'VIEW3D_PT_meshforge_manifold'
    bl_label = '2. Cohérence Manifold'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        return props is not None and props.show_expert_mode

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
    """Section 3.3 - Dissolve (Mode Expert)"""
    bl_idname = 'VIEW3D_PT_meshforge_dissolve'
    bl_label = '3. Dissolution Coplanaire'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        return props is not None and props.show_expert_mode

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
    """Section 4 - Simplification Intelligente (Mode Expert)"""
    bl_idname = 'VIEW3D_PT_meshforge_simplification'
    bl_label = '4. Simplification Détaillée'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        return props is not None and props.show_expert_mode

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
    """Section 3.4 - Topology (Mode Expert)"""
    bl_idname = 'VIEW3D_PT_meshforge_topology'
    bl_label = '5. Topologie (Tris / Quads)'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        return props is not None and props.show_expert_mode

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
    """Section 3.5 - Normals (Mode Expert)"""
    bl_idname = 'VIEW3D_PT_meshforge_normals'
    bl_label = '6. Normales & Ombrage'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        return props is not None and props.show_expert_mode

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
    """Section 3.6 - Object Data (Mode Expert)"""
    bl_idname = 'VIEW3D_PT_meshforge_object_data'
    bl_label = '7. Données d\'Objet'
    bl_parent_id = 'VIEW3D_PT_meshforge_main'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        return props is not None and props.show_expert_mode

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

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "meshforge_settings", None)
        if not props:
            return False
        return props.show_expert_mode or (props.last_duration > 0 or props.last_status != 'Prêt')

    def draw(self, context):
        layout = self.layout
        props = context.scene.meshforge_settings

        box = layout.box()
        box.label(text=f"Statut : {props.last_status}", icon='PRESET')
        if props.last_duration > 0:
            box.label(text=f"Durée totale : {props.last_duration:.3f} s", icon='TIME')

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
