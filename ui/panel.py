"""MeshForge - Interface utilisateur dans le 3D Viewport (Sidebar N-Panel).
Organise les contrôles autour de deux sections majeures et un mode expert :
1. Objet sélectionné & statistiques directes
2. Choix de l'objectif parmi les 5 profils prédéfinis
3. SECTION 1 : CLEAN — Nettoyer et réparer (ouverte par défaut : diagnostic, santé, actions sûres, topologie)
4. SECTION 2 : DECIMATE — Réduire le maillage (repliée par défaut : contraction d'arêtes vs dissolution, estimation, métrologie)
5. MODE EXPERT : Réglages techniques avancés et pipeline combiné
"""

from __future__ import annotations
import bpy

from ..operators.topology_inspect import get_active_diagnosis, check_diagnosis_staleness
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
        is_edit = (context.mode == 'EDIT_MESH' or (obj and obj.mode == 'EDIT'))
        if not is_edit:
            try:
                mesh.calc_loop_triangles()
                real_tris = len(mesh.loop_triangles) if hasattr(mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)
            except Exception:
                real_tris = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)
        else:
            real_tris = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

        mode = props.asset_target_mode
        resolved_profile = PROFILE_ALIAS.get(mode, mode)

        grid = box_obj.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        grid.label(text=f"Sommets : {len(mesh.vertices):,}")
        grid.label(text=f"Arêtes : {len(mesh.edges):,}")
        grid.label(text=f"Faces : {len(mesh.polygons):,}")
        grid.label(text=f"Triangles réels : {real_tris:,}")

        # Alerte explicite si le mode Édition est actif
        if is_edit:
            box_edit = layout.box()
            box_edit.alert = True
            row_we = box_edit.row(align=True)
            row_we.label(text="Mode Édition actif : actions désactivées", icon='EDITMODE_HLT')
            col_we = box_edit.column(align=True)
            col_we.scale_y = 0.85
            col_we.label(text="Repassez en mode Objet (Touche Tab) pour lancer")
            col_we.label(text="l'analyse et les réparations géométriques sûres.")

        # ---------------------------------------------------------
        # 2. SECTION 1 : CLEAN — NETTOYER ET RÉPARER (OUVERTE PAR DÉFAUT)
        # ---------------------------------------------------------
        box_clean = layout.box()
        row_cl = box_clean.row(align=True)
        icon_cl = 'TRIA_DOWN' if props.ui_section_clean_expanded else 'TRIA_RIGHT'
        row_cl.prop(props, "ui_section_clean_expanded", text="CLEAN — Nettoyer et réparer", icon=icon_cl, emboss=False)

        if props.ui_section_clean_expanded:
            # 2.1 Étape 1 : Analyse initiale & Inspection 3D
            box_step1 = box_clean.box()
            box_step1.label(text="1. Analyser le maillage :", icon='VIEWZOOM')
            col_diag_btn = box_step1.column(align=True)
            col_diag_btn.scale_y = 1.3
            col_diag_btn.operator("meshforge.analyze_topology", text="Analyser le maillage", icon='VIEWZOOM')

            is_wire = getattr(obj, "show_wire", False)
            row_tools = box_step1.row(align=True)
            row_tools.operator(
                "meshforge.toggle_wireframe",
                text="Masquer le filaire" if is_wire else "Afficher le filaire",
                icon='CHECKBOX_HLT' if is_wire else 'SHADING_WIRE',
                depress=is_wire
            )
            row_tools.operator("meshforge.clear_defect_view", text="Effacer l'inspection", icon='PANEL_CLOSE')

            diag = get_active_diagnosis(obj.name)
            is_stale, stale_reason = check_diagnosis_staleness(obj)

            if not diag or not diag.get("valid"):
                b_inv = box_clean.box()
                b_inv.label(text="Analyse requise pour commencer", icon='INFO')
                c_inv = b_inv.column(align=True)
                c_inv.scale_y = 0.85
                c_inv.label(text="Cliquez sur 'Analyser le maillage' ci-dessus pour révéler")
                c_inv.label(text="la santé géométrique et obtenir des recommandations ciblées.")
            else:
                # Alerte de péremption si la géométrie a changé
                if is_stale:
                    box_stale = box_clean.box()
                    box_stale.alert = True
                    row_st = box_stale.row(align=True)
                    row_st.label(text="Diagnostic à actualiser", icon='ERROR')
                    col_st = box_stale.column(align=True)
                    col_st.scale_y = 0.85
                    col_st.label(text="La géométrie a été modifiée depuis la dernière analyse.")
                    if stale_reason:
                        col_st.label(text=f"Motif : {stale_reason}")
                    col_act_st = box_stale.column(align=True)
                    col_act_st.scale_y = 1.2
                    col_act_st.operator("meshforge.analyze_topology", text="Actualiser le diagnostic maintenant", icon='FILE_REFRESH')

                structured = diag.get("structured", {})
                findings = diag.get("findings", [])
                health = structured.get("health", {})
                total_defects = health.get("defects_count", 0)
                total_risks = health.get("risks_count", 0)
                total_obs = health.get("observations_count", 0)
                rec_groups = structured.get("recommendation_groups", {})

                # 2.2 Étape 2 : Constats factuels de géométrie (indépendants de l'objectif)
                box_step2 = box_clean.box()
                box_step2.label(text="2. Constats factuels de géométrie :", icon='SOLO_ON')

                row_hh = box_step2.row()
                if health.get("status") == "HEALTHY":
                    row_hh.label(text="Santé : Maillage géométriquement sain", icon='CHECKMARK')
                elif health.get("status") == "CRITICAL":
                    row_hh.alert = True
                    row_hh.label(text=f"Santé : {total_defects} anomalie(s) critique(s)", icon='ERROR')
                else:
                    row_hh.label(text=f"Santé : {total_risks} point(s) de vigilance", icon='INFO')

                row_counts = box_step2.row(align=True)
                r_def = row_counts.row(align=True)
                if total_defects > 0:
                    r_def.alert = True
                r_def.label(text=f"Défauts : {total_defects}", icon='CANCEL')
                row_counts.label(text=f"Risques : {total_risks}", icon='HELP')
                row_counts.label(text=f"Observations : {total_obs}", icon='INFO')

                # Tableau détaillé repliable des constats
                box_table = box_step2.box()
                r_t_head = box_table.row(align=True)
                r_t_head.prop(
                    props,
                    "show_findings_table",
                    text=f"Tableau détaillé ({len(findings)} constats)",
                    icon='TRIA_DOWN' if props.show_findings_table else 'TRIA_RIGHT',
                    emboss=False
                )

                if props.show_findings_table and findings:
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

                # 2.3 Étape 3 : Définir l'objectif pour cet asset
                box_step3 = box_clean.box()
                box_step3.label(text="3. Objectif pour cet asset :", icon='TRACKING')
                col_m = box_step3.column(align=True)
                col_m.prop(props, "asset_target_mode", text="")

                mode = props.asset_target_mode
                resolved_profile = PROFILE_ALIAS.get(mode, mode)
                p_info = PROFILES.get(resolved_profile, PROFILES.get("GENERAL", {}))

                box_exp = box_step3.box()
                col_exp = box_exp.column(align=True)
                col_exp.scale_y = 0.85
                col_exp.label(text=f"{p_info.get('name', 'Profil')} :", icon=p_info.get('icon', 'HELP'))
                col_exp.label(text=p_info.get('summary', ''))

                # Contraintes complémentaires
                box_constraints = box_step3.box()
                box_constraints.label(text="Contraintes complémentaires :", icon='CHECKBOX_HLT')
                col_c = box_constraints.column(align=True)
                col_c.prop(props, "constraint_strict_manifold", text="Étanchéité manifold stricte")
                col_c.prop(props, "constraint_quads_only", text="Exiger 100% quads (sans triangles ni N-gones)")

                # 2.4 Étape 4 : Recommandations claires (Les 4 Catégories)
                box_step4 = box_clean.box()
                box_step4.label(text="4. Recommandations pour votre objectif :", icon='TOOL_SETTINGS')

                # Catégorie 1 : Corrections conservatrices recommandées
                b_c1 = box_step4.box()
                r_c1_hdr = b_c1.row()
                r_c1_hdr.label(text="1. Corrections conservatrices recommandées", icon='CHECKMARK')
                c_list1 = rec_groups.get("conservative", [])
                if c_list1:
                    for card in c_list1:
                        b_cd = b_c1.box()
                        r_top = b_cd.row()
                        r_top.label(text=card["title"], icon=card.get("operator_icon", 'BRUSH_DATA'))
                        r_top.label(text=f"[{card['confidence']}]")

                        c_inf = b_cd.column(align=True)
                        c_inf.scale_y = 0.75
                        c_inf.label(text=f"• Problème : {card['problem']}")
                        c_inf.label(text=f"• Zone : {card['zone']}")
                        c_inf.label(text=f"• Effet : {card['effect']}")
                        c_inf.label(text=f"• Données : {card['data_impact']}")
                        c_inf.label(text=f"• Réversibilité : {card['reversibility']}")

                        col_btn = b_cd.column(align=True)
                        col_btn.scale_y = 1.15
                        r_btns = col_btn.row(align=True)
                        if card.get("focus_id"):
                            op_z = r_btns.operator("meshforge.focus_defect", text="Inspecter (Zoom)", icon='VIEWZOOM')
                            op_z.finding_id = card["focus_id"]
                        if card.get("operator"):
                            r_btns.operator(card["operator"], text=card["operator_text"], icon=card.get("operator_icon", 'PLAY'))
                else:
                    b_c1.label(text="Aucune dégénérescence ni anomalie conservatrice à corriger.", icon='CHECKMARK')

                # Catégorie 2 : Optimisations ciblées pour l'objectif
                b_c2 = box_step4.box()
                r_c2_hdr = b_c2.row()
                r_c2_hdr.label(text="2. Optimisations ciblées pour l'objectif", icon='MOD_TRIANGULATE')
                c_list2 = rec_groups.get("targeted", [])
                if c_list2:
                    for card in c_list2:
                        b_cd = b_c2.box()
                        r_top = b_cd.row()
                        r_top.label(text=card["title"], icon=card.get("operator_icon", 'MOD_TRIANGULATE'))
                        r_top.label(text=f"[{card['confidence']}]")

                        c_inf = b_cd.column(align=True)
                        c_inf.scale_y = 0.75
                        c_inf.label(text=f"• Problème : {card['problem']}")
                        c_inf.label(text=f"• Zone : {card['zone']}")
                        c_inf.label(text=f"• Effet : {card['effect']}")
                        c_inf.label(text=f"• Données : {card['data_impact']}")
                        c_inf.label(text=f"• Réversibilité : {card['reversibility']}")

                        col_btn = b_cd.column(align=True)
                        col_btn.scale_y = 1.15
                        r_btns = col_btn.row(align=True)
                        if card.get("focus_id"):
                            op_z = r_btns.operator("meshforge.focus_defect", text="Inspecter (Zoom)", icon='VIEWZOOM')
                            op_z.finding_id = card["focus_id"]
                        if card.get("operator"):
                            r_btns.operator(card["operator"], text=card["operator_text"], icon=card.get("operator_icon", 'PLAY'))
                else:
                    b_c2.label(text="Topologie polygonale adaptée aux exigences de l'objectif.", icon='CHECKMARK')

                # Catégorie 3 : Actions à risque à examiner individuellement
                b_c3 = box_step4.box()
                r_c3_hdr = b_c3.row()
                r_c3_hdr.label(text="3. Actions à risque à examiner individuellement", icon='HELP')
                c_list3 = rec_groups.get("risky", [])
                if c_list3:
                    for card in c_list3:
                        b_cd = b_c3.box()
                        b_cd.alert = True
                        r_top = b_cd.row()
                        r_top.label(text=card["title"], icon='ERROR')
                        r_top.label(text=f"[{card['confidence']}]")

                        c_inf = b_cd.column(align=True)
                        c_inf.scale_y = 0.75
                        c_inf.label(text=f"• Problème : {card['problem']}")
                        c_inf.label(text=f"• Zone : {card['zone']}")
                        c_inf.label(text=f"• Effet : {card['effect']}")
                        c_inf.label(text=f"• Précision : {card['data_impact']}")
                        c_inf.label(text=f"• Statut : {card['reversibility']}")

                        col_btn = b_cd.column(align=True)
                        col_btn.scale_y = 1.15
                        if card.get("focus_id"):
                            op_z = col_btn.operator("meshforge.focus_defect", text="Inspecter / Cadrer l'anomalie", icon='VIEWZOOM')
                            op_z.finding_id = card["focus_id"]
                else:
                    b_c3.label(text="Aucune configuration géométrique risquée ou ambiguë détectée.", icon='CHECKMARK')

                # Catégorie 4 : Observations sans action requise
                b_c4 = box_step4.box()
                r_c4_hdr = b_c4.row()
                r_c4_hdr.label(text="4. Observations sans action requise", icon='INFO')
                c_list4 = rec_groups.get("observations", [])
                if c_list4:
                    col_obs = b_c4.column(align=True)
                    col_obs.scale_y = 0.85
                    for card in c_list4:
                        col_obs.label(text=f"• {card['title']} : {card['problem']} ({card['confidence']})")
                else:
                    b_c4.label(text="Aucune observation supplémentaire.", icon='INFO')

                # Utilitaires directs de retouche topologique
                box_topo = box_clean.box()
                box_topo.label(text="Outils directs de topologie :", icon='SNAP_FACE')
                col_topo_btns = box_topo.column(align=True)
                col_topo_btns.operator("meshforge.cut_ngons", text="Découper les N-gones (Convexes / Concaves)", icon='MOD_TRIANGULATE')
                col_topo_btns.operator("meshforge.quadrangulate", text="Quadranguler les triangles (Tris -> Quads)", icon='SNAP_FACE')

                # 2.5 Étape 5 : Historique & Restauration de l'original
                if "_MF_Optimized" in obj.name or obj.get("_mf_source_ptr"):
                    box_res = box_clean.box()
                    box_res.label(text="5. Historique & Restauration de l'original :", icon='RECOVER_LAST')

                    root_source = obj.get("_mf_source_ptr", None)
                    if root_source and root_source.name in bpy.data.objects and root_source.data:
                        orig_sig = f"{len(root_source.data.vertices)}v_{len(root_source.data.edges)}e_{len(root_source.data.polygons)}f"
                        saved_sig = obj.get("_mf_source_mesh_version", "")
                        if saved_sig and orig_sig != saved_sig:
                            b_stale = box_res.box()
                            b_stale.alert = True
                            b_stale.label(text="Attention : L'original a été modifié !", icon='ERROR')
                            c_st = b_stale.column(align=True)
                            c_st.scale_y = 0.8
                            c_st.label(text=f"L'original '{root_source.name}' a évolué depuis cette copie.")
                            c_st.label(text="Restaurez ou ré-optimisez depuis l'original pour actualiser.")

                    box_res.operator("meshforge.restore", text="Restaurer l'original", icon='RECOVER_LAST')

        # ---------------------------------------------------------
        # 4. SECTION 2 : DECIMATE — RÉDUIRE LE MAILLAGE (REPLIÉE PAR DÉFAUT)
        # ---------------------------------------------------------
        box_dec = layout.box()
        row_dec = box_dec.row(align=True)
        icon_dec = 'TRIA_DOWN' if props.ui_section_decimate_expanded else 'TRIA_RIGHT'
        row_dec.prop(props, "ui_section_decimate_expanded", text="DECIMATE — Réduire le maillage", icon=icon_dec, emboss=False)

        if props.ui_section_decimate_expanded:
            # 4.1 Choix de la méthode
            box_meth = box_dec.box()
            box_meth.label(text="1. Méthode de réduction :", icon='MOD_DECIM')
            box_meth.prop(props, "decimate_method", text="")

            box_guidance = box_meth.box()
            col_guidance = box_guidance.column(align=True)
            col_guidance.scale_y = 0.85

            if props.decimate_method == 'COLLAPSE':
                if resolved_profile in ("MECHANICAL_CAD", "HARD_SURFACE"):
                    col_guidance.label(text="Conseil : pour les pièces mécaniques avec de larges faces planes,", icon='INFO')
                    col_guidance.label(text="la 'Dissolution coplanaire' élimine les arêtes sans distorsion de silhouette.")
                else:
                    col_guidance.label(text="Recommandé pour surfaces courbées et organiques :", icon='INFO')
                    col_guidance.label(text="Contraction progressive d'arêtes préservant la silhouette globale.")
            else:
                if resolved_profile in ("SCULPTED_ORGANIC", "DEFORMABLE_CHAR"):
                    col_guidance.label(text="Conseil : pour les modèles organiques ou sculptés, la 'Contraction", icon='INFO')
                    col_guidance.label(text="d'arêtes' est préférable (la dissolution n'agit que sur les plans stricts).")
                else:
                    col_guidance.label(text="Spécialisé pièces hard-surface & CAD :", icon='INFO')
                    col_guidance.label(text="Dissout les arêtes entre faces coplanaires sans altérer les courbures.")

            # 4.2 Objectif de réduction & Estimation claire
            box_obj_dec = box_dec.box()
            box_obj_dec.label(text="2. Objectif :", icon='DRIVER')

            if props.decimate_method == 'COLLAPSE':
                box_obj_dec.prop(props, "simplification_mode", text="Objectif")

                if props.simplification_mode == 'PERCENTAGE':
                    box_obj_dec.prop(props, "simplification_percentage", text="Pourcentage (%)", slider=True)
                    pct = props.simplification_percentage
                    est_tris = max(4, int(real_tris * (1.0 - (pct / 100.0))))

                    box_est = box_obj_dec.box()
                    col_est = box_est.column(align=True)
                    col_est.scale_y = 0.85
                    col_est.label(text=f"Estimation : ~{est_tris:,} triangles (-{pct:.1f}%)", icon='DRIVER')
                    col_est.label(text="Note : estimation théorique basée sur le maillage actuel.")
                    col_est.label(text="Le résultat réel dépend de la topologie et des contraintes.")

                elif props.simplification_mode == 'BUDGET_TRIANGLES':
                    box_obj_dec.prop(props, "simplification_target_triangles", text="Triangles cibles")
                    tgt = props.simplification_target_triangles
                    est_tris = min(real_tris, max(4, tgt))
                    est_pct = ((real_tris - est_tris) / real_tris * 100.0) if real_tris > 0 else 0.0

                    box_est = box_obj_dec.box()
                    col_est = box_est.column(align=True)
                    col_est.scale_y = 0.85
                    col_est.label(text=f"Estimation : ~{est_tris:,} triangles (cible demandée)", icon='DRIVER')
                    col_est.label(text=f"Réduction théorique estimée : -{est_pct:.1f}%.")
                    col_est.label(text="Le décimateur s'arrête au plus près du budget spécifié.")

                else:  # TOLERANCE_ONLY
                    box_obj_dec.label(text="Réduction maximale jusqu'au seuil de tolérance géométrique.")

            else:  # DISSOLVE
                box_obj_dec.prop(props, "dissolve_angle", text="Angle de planéité limite")
                box_obj_dec.prop(props, "dissolve_mode", text="Niveau de rigueur")
                box_est = box_obj_dec.box()
                col_est = box_est.column(align=True)
                col_est.scale_y = 0.85
                col_est.label(text=f"Dissolution des arêtes coplanaires sous {props.dissolve_angle:.1f}°.", icon='INFO')
                col_est.label(text="La réduction exacte dépend des surfaces parfaitement planes du modèle.")

            # 4.3 Options de préservation
            box_pres = box_dec.box()
            box_pres.label(text="3. Préservation des détails :", icon='LOCKED')

            if props.decimate_method == 'COLLAPSE':
                col_p = box_pres.column(align=True)
                col_p.prop(props, "collapse_triangulate", text="Trianguler avant réduction")
                col_p.prop(props, "preserve_normals_angle", text="Préserver angles de normales")

                box_tol = box_pres.box()
                box_tol.prop(props, "enable_simplification_tolerance", text="Plafonner par tolérance géométrique")
                if props.enable_simplification_tolerance:
                    col_tol = box_tol.column(align=True)
                    col_tol.prop(props, "simplification_max_tolerance", text="Tolérance max (m)")
                    col_tol.prop(props, "tolerance_relative", text="Tolérance relative (bbox)")
            else:
                col_p = box_pres.column(align=True)
                col_p.prop(props, "preserve_sharp", text="Arêtes vives (Sharp Edges)")
                col_p.prop(props, "preserve_seams", text="Coutures UV (Seams)")
                col_p.prop(props, "preserve_materials", text="Frontières de matériaux")
                col_p.prop(props, "preserve_uvs", text="Coordonnées UV")
                col_p.prop(props, "preserve_boundaries", text="Frontières ouvertes")

            # 4.4 Sécurité & Workflow non-destructif
            box_sec = box_dec.box()
            box_sec.label(text="4. Sécurité du workflow :", icon='FILE_TICK')
            col_sec = box_sec.column(align=True)
            col_sec.prop(props, "create_new_object", text="Créer un nouvel objet (non-destructif)")
            if props.create_new_object:
                col_sec.prop(props, "hide_original", text="Masquer l'original")
            else:
                box_w = box_sec.box()
                box_w.alert = True
                box_w.prop(props, "destructive_mode", text="Mode destructif direct !")
                col_w = box_w.column(align=True)
                col_w.scale_y = 0.85
                col_w.label(text="Avertissement : les modifications écraseront l'objet actif.")

            # Protection Shape Keys (Point 1 de Sécurisation UX8)
            has_sk = (mesh.shape_keys is not None and len(mesh.shape_keys.key_blocks) > 0)
            if has_sk:
                box_sk = box_sec.box()
                box_sk.alert = True
                box_sk.label(text="Attention : Shape Keys détectées !", icon='ERROR')
                col_sk = box_sk.column(align=True)
                col_sk.scale_y = 0.85
                col_sk.label(text="Blender interdit de modifier la topologie d'un maillage avec clés de forme.")
                col_sk.label(text="Pour réduire, une copie statique sans Shape Keys est requise.")
                col_sk.label(text="L'objet original conservera 100% de ses clés d'animation intactes.")
                box_sk.prop(props, "allow_shape_keys_removal_on_copy", text="Créer copie statique sans Shape Keys")

            # Protection Dissolution Agressive (Point 2 de Sécurisation UX8)
            if props.decimate_method == 'DISSOLVE':
                mesh_has_seams = any(e.use_seam for e in mesh.edges)
                mesh_has_sharp = any(e.use_edge_sharp for e in mesh.edges)
                mesh_has_multiple_mats = len(obj.material_slots) > 1
                mesh_has_curvature = False
                if len(mesh.polygons) > 1:
                    poly_sample = mesh.polygons[:min(30, len(mesh.polygons))]
                    n0 = poly_sample[0].normal
                    mesh_has_curvature = any(p.normal.dot(n0) < 0.99 for p in poly_sample[1:])

                dissolve_risks = []
                if mesh_has_seams and not props.preserve_seams:
                    dissolve_risks.append("Coutures UV non préservées (risque de distorsion)")
                if mesh_has_sharp and not props.preserve_sharp:
                    dissolve_risks.append("Arêtes vives non préservées (risque d'altération d'ombrage)")
                if mesh_has_multiple_mats and not props.preserve_materials:
                    dissolve_risks.append("Frontières de matériaux non préservées (risque de fusion)")
                if props.dissolve_mode == 'AGGRESSIVE' and resolved_profile in ('GAME_ASSET', 'DEFORMABLE_CHAR'):
                    dissolve_risks.append(f"Dissolution agressive sur profil sensible ({resolved_profile})")
                if mesh_has_curvature and props.dissolve_angle >= 15.0:
                    dissolve_risks.append(f"Angle élevé ({props.dissolve_angle:.1f}°) sur surface courbée")

                if dissolve_risks:
                    box_rk = box_sec.box()
                    box_rk.alert = True
                    box_rk.label(text="Risque de dissolution identifié :", icon='ERROR')
                    col_rk = box_rk.column(align=True)
                    col_rk.scale_y = 0.85
                    for r_item in dissolve_risks:
                        col_rk.label(text=f"• {r_item}")
                    box_rk.prop(props, "confirm_aggressive_dissolve", text="Confirmer la dissolution à risque")

            # 4.5 Bouton d'action
            col_exec = box_dec.column(align=True)
            col_exec.scale_y = 1.3
            if props.decimate_method == 'COLLAPSE':
                col_exec.operator("meshforge.simplification", text="Réduire le maillage (Contraction d'arêtes)", icon='MOD_DECIM')
            else:
                col_exec.operator("meshforge.dissolve", text="Simplifier les faces (Dissolution coplanaire)", icon='SNAP_FACE')

            # 4.6 Comparaison Avant / Après (Post-exécution)
            if props.last_faces_before > 0 or props.last_tris_before > 0:
                box_res_post = box_dec.box()
                row_res_hdr = box_res_post.row()
                row_res_hdr.label(text="Résultat réel de la dernière opération :", icon='PRESET')

                row_st = box_res_post.row(align=True)
                is_ok = (props.last_status == "Succès")
                row_st.label(text=f"Statut : {props.last_status}", icon='CHECKMARK' if is_ok else 'ERROR')
                if props.last_duration > 0:
                    row_st.label(text=f"Durée : {props.last_duration:.2f} s", icon='TIME')

                # Grille comparative claire
                grid_comp = box_res_post.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)
                grid_comp.label(text=f"Triangles réels :")
                grid_comp.label(text=f"{props.last_tris_before:,} -> {props.last_tris_after:,}")
                grid_comp.label(text=f"(-{props.last_reduction:.1f}%)" if props.last_reduction > 0 else "(0%)")

                grid_comp.label(text=f"Faces :")
                grid_comp.label(text=f"{props.last_faces_before:,} -> {props.last_faces_after:,}")
                delta_f = props.last_faces_before - props.last_faces_after
                grid_comp.label(text=f"(-{delta_f:,})" if delta_f > 0 else "")

                grid_comp.label(text=f"Sommets :")
                grid_comp.label(text=f"{props.last_verts_before:,} -> {props.last_verts_after:,}")
                delta_v = props.last_verts_before - props.last_verts_after
                grid_comp.label(text=f"(-{delta_v:,})" if delta_v > 0 else "")

                # Métrologie / Déviation géométrique strictement honnête (Règle 2)
                box_met = box_res_post.box()
                col_met = box_met.column(align=True)
                col_met.scale_y = 0.85
                if props.last_deviation_measured:
                    col_met.label(text="Métrologie géométrique mesurée :", icon='CHECKMARK')
                    col_met.label(text=f"• Écart Hausdorff max : {props.last_max_hausdorff:.5f} m")
                    col_met.label(text=f"• Écart moyen de surface : {props.last_mean_deviation:.5f} m")
                    col_met.label(text=f"• Déviation angulaire des normales : {props.last_max_normal_angle:.1f}°")
                else:
                    col_met.label(text="Déviation géométrique : Non mesurée (validation approfondie non exécutée)", icon='INFO')

                if "_MF_Optimized" in obj.name or props.last_result_obj_name:
                    box_res_post.operator("meshforge.restore", text="Restaurer l'original", icon='RECOVER_LAST')

        # ---------------------------------------------------------
        # 5. MODE EXPERT / RÉGLAGES TECHNIQUES (REPLIÉ PAR DÉFAUT)
        # ---------------------------------------------------------
        box_exp_toggle = layout.box()
        row_exp_h = box_exp_toggle.row(align=True)
        icon_exp = 'TRIA_DOWN' if props.show_expert_mode else 'TRIA_RIGHT'
        row_exp_h.prop(
            props,
            "show_expert_mode",
            text="Mode Expert / Réglages techniques",
            icon=icon_exp,
            emboss=False
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

        box_safe_iw = layout.box()
        box_safe_iw.label(text="Parois internes mitoyennes (Sûr) :", icon='CHECKMARK')
        row_iw = box_safe_iw.row(align=True)
        row_iw.operator("meshforge.select_internal_walls", text="Inspecter (Zoom)", icon='VIEWZOOM')
        row_iw.operator("meshforge.remove_internal_walls", text="Supprimer", icon='X')

        layout.separator()
        layout.operator("meshforge.manifold", text="Exécuter Manifold complet", icon='MOD_SOLIDIFY')


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
        layout.operator("meshforge.quadrangulate", text="Quadrangulation ciblée sécurisée", icon='SNAP_FACE')
        layout.separator()
        layout.operator("meshforge.topology", text="Exécuter Topologie complète", icon='MOD_REMESH')


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


from ..core.registration_utils import register_classes_safely, unregister_classes_safely


def register_ui():
    register_classes_safely(classes)


def unregister_ui():
    unregister_classes_safely(classes)
