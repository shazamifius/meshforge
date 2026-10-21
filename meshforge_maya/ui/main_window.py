"""MeshForge Maya - Main User Interface Window.
Comprehensive PySide GUI providing complete 1:1 feature parity with MeshForge for Blender:
- Section 1: CLEAN (Analysis, Findings Table with 3D Zoom & Auto-Fix, 8 Profiles, 4 Categories, Topology Tools, Restore)
- Section 2: DECIMATE (Edge Collapse vs Dissolve, Live Estimation, Percentage & Budget, Detail Preservation, Blendshape Safety, Metrology)
- Section 3: EXPERT MODE (Combined Pipeline & 7 Collapsible Specialist Subpanels with Export Reports)
"""

from __future__ import annotations
import sys
import json
import time
from typing import Dict, Any, List, Optional

import maya.cmds as cmds
import maya.mel as mel

from .qt_compat import QtWidgets, QtCore, QtGui
from .styles import MAYA_DARK_STYLE

from ..core.mesh_stats import get_selected_mesh, get_mesh_statistics
from ..core.structured_diagnosis import evaluate_mesh_diagnosis, PROFILES, CATEGORIES
from ..core.conservative_cleaner import execute_conservative_cleanup
from ..core.ngon_cutter import execute_ngon_cut
from ..core.quadrangulator import execute_targeted_quadrangulation
from ..core.internal_walls import detect_internal_walls, execute_remove_internal_walls
from ..core.dissolve import execute_dissolve
from ..core.simplification import execute_simplification
from ..core.normals import execute_normals
from ..core.object_data import execute_object_data
from ..core.pipeline import duplicate_object_non_destructive, restore_original_object, run_meshforge_pipeline
from ..core.validation import validate_mesh_surface
from ..core.visualizer import focus_on_components, toggle_wireframe_display, clear_inspection_view


class CollapsibleSection(QtWidgets.QWidget):
    """Collapsible section container with animated header arrow."""

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self.layout_main = QtWidgets.QVBoxLayout(self)
        self.layout_main.setContentsMargins(0, 2, 0, 2)
        self.layout_main.setSpacing(0)

        # Header Toggle Button
        self.toggle_btn = QtWidgets.QPushButton(self)
        self.toggle_btn.setStyleSheet(
            "text-align: left; font-weight: bold; padding: 6px 8px; "
            "background-color: #333333; border: 1px solid #444444; border-radius: 3px;"
        )
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(expanded)
        self.toggle_btn.clicked.connect(self._on_toggle)

        self.title_text = title
        self._update_title()
        self.layout_main.addWidget(self.toggle_btn)

        # Content widget
        self.content_widget = QtWidgets.QWidget(self)
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 6, 4, 6)
        self.content_layout.setSpacing(6)
        self.content_widget.setVisible(expanded)
        self.layout_main.addWidget(self.content_widget)

    def _update_title(self):
        arrow = "▼ " if self.toggle_btn.isChecked() else "▶ "
        self.toggle_btn.setText(f"{arrow}{self.title_text}")

    def _on_toggle(self):
        is_expanded = self.toggle_btn.isChecked()
        self.content_widget.setVisible(is_expanded)
        self._update_title()

    def set_expanded(self, expanded: bool):
        self.toggle_btn.setChecked(expanded)
        self.content_widget.setVisible(expanded)
        self._update_title()

    def is_expanded(self) -> bool:
        return self.toggle_btn.isChecked()


class MeshForgeMayaWindow(QtWidgets.QMainWindow):
    """MeshForge for Maya - Main Control Center Window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MeshForge — 3D Assistant (Maya)")
        self.resize(480, 850)
        self.setStyleSheet(MAYA_DARK_STYLE)

        self.active_mesh: Optional[str] = None
        self.active_stats: Dict[str, Any] = {}
        self.active_diagnosis: Dict[str, Any] = {}
        self.intentional_finding_ids: List[str] = []

        self._build_ui()
        self.on_profile_changed()
        self.refresh_selection()

    def _build_ui(self):
        central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(central_widget)
        main_vbox = QtWidgets.QVBoxLayout(central_widget)
        main_vbox.setContentsMargins(6, 6, 6, 6)
        main_vbox.setSpacing(6)

        # Scroll Area for dense control sets
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll_layout.setSpacing(8)
        scroll.setWidget(scroll_content)
        main_vbox.addWidget(scroll)

        # -------------------------------------------------------------
        # 1. ACTIVE OBJECT TELEMETRY BOX
        # -------------------------------------------------------------
        self.box_telemetry = QtWidgets.QFrame(self)
        self.box_telemetry.setObjectName("CardBox")
        box_tel_layout = QtWidgets.QVBoxLayout(self.box_telemetry)
        box_tel_layout.setContentsMargins(8, 8, 8, 8)
        box_tel_layout.setSpacing(4)

        row_obj = QtWidgets.QHBoxLayout()
        self.lbl_object_name = QtWidgets.QLabel("Objet : Aucun sélectionné", self)
        self.lbl_object_name.setObjectName("HeaderTitle")
        row_obj.addWidget(self.lbl_object_name)

        self.btn_refresh_sel = QtWidgets.QPushButton("Actualiser", self)
        self.btn_refresh_sel.setMaximumWidth(90)
        self.btn_refresh_sel.clicked.connect(self.refresh_selection)
        row_obj.addWidget(self.btn_refresh_sel)
        box_tel_layout.addLayout(row_obj)

        grid_stats = QtWidgets.QGridLayout()
        self.lbl_verts = QtWidgets.QLabel("Sommets : 0", self)
        self.lbl_edges = QtWidgets.QLabel("Arêtes : 0", self)
        self.lbl_faces = QtWidgets.QLabel("Faces : 0", self)
        self.lbl_tris = QtWidgets.QLabel("Triangles réels : 0", self)

        grid_stats.addWidget(self.lbl_verts, 0, 0)
        grid_stats.addWidget(self.lbl_edges, 0, 1)
        grid_stats.addWidget(self.lbl_faces, 1, 0)
        grid_stats.addWidget(self.lbl_tris, 1, 1)
        box_tel_layout.addLayout(grid_stats)

        self.scroll_layout.addWidget(self.box_telemetry)

        # -------------------------------------------------------------
        # 2. SECTION 1: CLEAN — NETTOYER ET RÉPARER (Ouverte par défaut)
        # -------------------------------------------------------------
        self.sec_clean = CollapsibleSection("SECTION 1 : CLEAN — Nettoyer et réparer", expanded=True, parent=self)
        l_clean = self.sec_clean.content_layout

        # Étape 1 : Analyse initiale & Inspection 3D
        grp_step1 = QtWidgets.QGroupBox("1. Analyser le maillage :", self)
        l_s1 = QtWidgets.QVBoxLayout(grp_step1)

        self.btn_analyze = QtWidgets.QPushButton("Analyser le maillage", self)
        self.btn_analyze.setObjectName("PrimaryButton")
        self.btn_analyze.clicked.connect(self.on_analyze_topology)
        l_s1.addWidget(self.btn_analyze)

        row_view_tools = QtWidgets.QHBoxLayout()
        self.btn_wire = QtWidgets.QPushButton("Afficher / Masquer filaire", self)
        self.btn_wire.clicked.connect(self.on_toggle_wireframe)
        row_view_tools.addWidget(self.btn_wire)

        self.btn_clear_view = QtWidgets.QPushButton("Effacer l'inspection", self)
        self.btn_clear_view.clicked.connect(self.on_clear_inspection)
        row_view_tools.addWidget(self.btn_clear_view)
        l_s1.addLayout(row_view_tools)
        l_clean.addWidget(grp_step1)

        # Étape 2 : Constats factuels de géométrie
        grp_step2 = QtWidgets.QGroupBox("2. Constats factuels de géométrie :", self)
        l_s2 = QtWidgets.QVBoxLayout(grp_step2)

        self.lbl_health_status = QtWidgets.QLabel("Santé : Analyse non effectuée", self)
        self.lbl_health_status.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        l_s2.addWidget(self.lbl_health_status)

        self.lbl_counters = QtWidgets.QLabel("Défauts : 0  |  Risques : 0  |  Observations : 0", self)
        l_s2.addWidget(self.lbl_counters)

        # Tableau détaillé repliable des constats avec filtres
        self.sec_findings_table = CollapsibleSection("Tableau détaillé des constats (0)", expanded=True, parent=self)
        l_tbl = self.sec_findings_table.content_layout

        row_filters = QtWidgets.QHBoxLayout()
        row_filters.addWidget(QtWidgets.QLabel("Catégorie :", self))
        self.combo_filter_cat = QtWidgets.QComboBox(self)
        self.combo_filter_cat.addItem("Toutes les catégories", "ALL")
        for cat_id, cat_info in CATEGORIES.items():
            self.combo_filter_cat.addItem(cat_info["name"], cat_id)
        self.combo_filter_cat.currentIndexChanged.connect(self._render_findings_table)
        row_filters.addWidget(self.combo_filter_cat)

        row_filters.addWidget(QtWidgets.QLabel("Sévérité :", self))
        self.combo_filter_sev = QtWidgets.QComboBox(self)
        self.combo_filter_sev.addItem("Toutes les sévérités", "ALL")
        self.combo_filter_sev.addItem("Défauts critiques", "DEFECT")
        self.combo_filter_sev.addItem("Points de risque", "RISK")
        self.combo_filter_sev.addItem("Observations", "OBSERVATION")
        self.combo_filter_sev.currentIndexChanged.connect(self._render_findings_table)
        row_filters.addWidget(self.combo_filter_sev)
        l_tbl.addLayout(row_filters)

        self.l_findings_cards = QtWidgets.QVBoxLayout()
        l_tbl.addLayout(self.l_findings_cards)
        l_s2.addWidget(self.sec_findings_table)
        l_clean.addWidget(grp_step2)

        # Étape 3 : Objectif pour cet asset (8 Profils)
        grp_step3 = QtWidgets.QGroupBox("3. Objectif pour cet asset :", self)
        l_s3 = QtWidgets.QVBoxLayout(grp_step3)

        self.combo_profile = QtWidgets.QComboBox(self)
        for p_key, p_val in PROFILES.items():
            self.combo_profile.addItem(p_val["name"], p_key)
        self.combo_profile.currentIndexChanged.connect(self.on_profile_changed)
        l_s3.addWidget(self.combo_profile)

        self.lbl_profile_summary = QtWidgets.QLabel(self)
        self.lbl_profile_summary.setWordWrap(True)
        self.lbl_profile_summary.setStyleSheet("color: #aaaaaa; font-style: italic;")
        l_s3.addWidget(self.lbl_profile_summary)

        # Contraintes complémentaires
        self.chk_strict_manifold = QtWidgets.QCheckBox("Étanchéité manifold stricte", self)
        self.chk_strict_manifold.stateChanged.connect(self.on_profile_changed)
        l_s3.addWidget(self.chk_strict_manifold)

        self.chk_quads_only = QtWidgets.QCheckBox("Exiger 100% quads (sans triangles ni N-gones)", self)
        self.chk_quads_only.stateChanged.connect(self.on_profile_changed)
        l_s3.addWidget(self.chk_quads_only)
        l_clean.addWidget(grp_step3)

        # Étape 4 : Recommandations pour votre objectif (Les 4 Catégories)
        self.grp_step4 = QtWidgets.QGroupBox("4. Recommandations pour votre objectif :", self)
        self.l_recs = QtWidgets.QVBoxLayout(self.grp_step4)
        l_clean.addWidget(self.grp_step4)

        # Outils directs de topologie
        grp_topo_tools = QtWidgets.QGroupBox("Outils directs de topologie :", self)
        l_tt = QtWidgets.QHBoxLayout(grp_topo_tools)
        btn_cut_ngons = QtWidgets.QPushButton("Découper les N-Gones", self)
        btn_cut_ngons.clicked.connect(self.on_cut_ngons)
        l_tt.addWidget(btn_cut_ngons)

        btn_quad = QtWidgets.QPushButton("Quadranguler les triangles", self)
        btn_quad.clicked.connect(self.on_quadrangulate)
        l_tt.addWidget(btn_quad)
        l_clean.addWidget(grp_topo_tools)

        # Étape 5 : Historique & Restauration
        self.box_restore = QtWidgets.QFrame(self)
        self.box_restore.setObjectName("CardBox")
        l_res = QtWidgets.QHBoxLayout(self.box_restore)
        self.btn_restore = QtWidgets.QPushButton("Restaurer l'original", self)
        self.btn_restore.setObjectName("DangerButton")
        self.btn_restore.clicked.connect(self.on_restore_original)
        l_res.addWidget(self.btn_restore)
        l_clean.addWidget(self.box_restore)

        self.scroll_layout.addWidget(self.sec_clean)

        # -------------------------------------------------------------
        # 3. SECTION 2: DECIMATE — RÉDUIRE LE MAILLAGE (Repliée par défaut)
        # -------------------------------------------------------------
        self.sec_decimate = CollapsibleSection("SECTION 2 : DECIMATE — Réduire le maillage", expanded=False, parent=self)
        l_dec = self.sec_decimate.content_layout

        # 1. Méthode de réduction
        grp_method = QtWidgets.QGroupBox("1. Méthode de réduction :", self)
        l_m = QtWidgets.QVBoxLayout(grp_method)
        self.combo_method = QtWidgets.QComboBox(self)
        self.combo_method.addItem("Contraction d'arêtes QEM (Surfaces courbes / Organique)", "COLLAPSE")
        self.combo_method.addItem("Dissolution coplanaire (Surfaces planes / CAD)", "DISSOLVE")
        self.combo_method.currentIndexChanged.connect(self.on_method_changed)
        l_m.addWidget(self.combo_method)

        self.lbl_method_guidance = QtWidgets.QLabel("Recommandé pour surfaces courbes : contraction d'arêtes préservant la silhouette.", self)
        self.lbl_method_guidance.setWordWrap(True)
        self.lbl_method_guidance.setStyleSheet("color: #aaaaaa; font-style: italic;")
        l_m.addWidget(self.lbl_method_guidance)
        l_dec.addWidget(grp_method)

        # 2. Objectif & Estimation dynamique
        grp_goal = QtWidgets.QGroupBox("2. Objectif & Estimation dynamique :", self)
        l_g = QtWidgets.QVBoxLayout(grp_goal)

        # Inputs pour Contraction d'arêtes (COLLAPSE)
        self.w_collapse_goal = QtWidgets.QWidget(self)
        l_cg = QtWidgets.QVBoxLayout(self.w_collapse_goal)
        l_cg.setContentsMargins(0, 0, 0, 0)

        row_cmode = QtWidgets.QHBoxLayout()
        row_cmode.addWidget(QtWidgets.QLabel("Mode objectif :", self))
        self.combo_collapse_mode = QtWidgets.QComboBox(self)
        self.combo_collapse_mode.addItem("Pourcentage (%)", "PERCENTAGE")
        self.combo_collapse_mode.addItem("Triangles cibles (Budget)", "BUDGET_TRIANGLES")
        self.combo_collapse_mode.currentIndexChanged.connect(self._on_collapse_mode_changed)
        row_cmode.addWidget(self.combo_collapse_mode)
        l_cg.addLayout(row_cmode)

        self.row_pct = QtWidgets.QHBoxLayout()
        self.row_pct.addWidget(QtWidgets.QLabel("Pourcentage (%) :", self))
        self.slider_pct = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.slider_pct.setRange(0, 99)
        self.slider_pct.setValue(50)
        self.slider_pct.valueChanged.connect(self.on_pct_slider_changed)
        self.row_pct.addWidget(self.slider_pct)
        self.lbl_pct_val = QtWidgets.QLabel("50%", self)
        self.row_pct.addWidget(self.lbl_pct_val)
        l_cg.addLayout(self.row_pct)

        self.row_budget = QtWidgets.QHBoxLayout()
        self.row_budget.addWidget(QtWidgets.QLabel("Triangles cibles :", self))
        self.spin_budget = QtWidgets.QSpinBox(self)
        self.spin_budget.setRange(4, 10000000)
        self.spin_budget.setValue(1000)
        self.spin_budget.valueChanged.connect(lambda _: self._update_estimation_label())
        self.row_budget.addWidget(self.spin_budget)
        l_cg.addLayout(self.row_budget)
        self.spin_budget.setEnabled(False)

        self.lbl_estimation = QtWidgets.QLabel("Estimation : ~0 triangles (-50.0%)", self)
        self.lbl_estimation.setStyleSheet("font-weight: bold; color: #4a90e2;")
        l_cg.addWidget(self.lbl_estimation)
        l_g.addWidget(self.w_collapse_goal)

        # Inputs pour Dissolution Coplanaire (DISSOLVE)
        self.w_dissolve_goal = QtWidgets.QWidget(self)
        l_dg = QtWidgets.QVBoxLayout(self.w_dissolve_goal)
        l_dg.setContentsMargins(0, 0, 0, 0)
        row_ang = QtWidgets.QHBoxLayout()
        row_ang.addWidget(QtWidgets.QLabel("Angle de planéité limite (°) :", self))
        self.spin_dissolve_angle = QtWidgets.QDoubleSpinBox(self)
        self.spin_dissolve_angle.setRange(0.1, 90.0)
        self.spin_dissolve_angle.setValue(5.0)
        row_ang.addWidget(self.spin_dissolve_angle)
        l_dg.addLayout(row_ang)
        l_g.addWidget(self.w_dissolve_goal)
        self.w_dissolve_goal.setVisible(False)

        l_dec.addWidget(grp_goal)

        # 3. Préservation des détails
        grp_pres = QtWidgets.QGroupBox("3. Préservation des détails :", self)
        l_p = QtWidgets.QVBoxLayout(grp_pres)
        self.chk_triangulate_first = QtWidgets.QCheckBox("Trianguler avant réduction", self)
        l_p.addWidget(self.chk_triangulate_first)

        self.chk_pres_boundaries = QtWidgets.QCheckBox("Préserver les frontières ouvertes (Open Boundaries)", self)
        self.chk_pres_boundaries.setChecked(True)
        l_p.addWidget(self.chk_pres_boundaries)

        self.chk_pres_sharp = QtWidgets.QCheckBox("Préserver les arêtes vives (Hard Edges)", self)
        self.chk_pres_sharp.setChecked(True)
        l_p.addWidget(self.chk_pres_sharp)

        self.chk_pres_seams = QtWidgets.QCheckBox("Préserver les coutures UV (Texture Seams)", self)
        self.chk_pres_seams.setChecked(True)
        l_p.addWidget(self.chk_pres_seams)
        l_dec.addWidget(grp_pres)

        # 4. Sécurité & Workflow non-destructif
        grp_sec = QtWidgets.QGroupBox("4. Sécurité du workflow & Garde-fous :", self)
        l_sec = QtWidgets.QVBoxLayout(grp_sec)
        self.chk_create_copy = QtWidgets.QCheckBox("Créer un nouvel objet (non-destructif)", self)
        self.chk_create_copy.setChecked(True)
        l_sec.addWidget(self.chk_create_copy)

        self.box_blendshape_alert = QtWidgets.QFrame(self)
        self.box_blendshape_alert.setObjectName("AlertBox")
        l_ba = QtWidgets.QVBoxLayout(self.box_blendshape_alert)
        l_ba.addWidget(QtWidgets.QLabel("⚠️ Déformateurs BlendShapes détectés sur le maillage !", self))
        self.chk_allow_blendshape_copy = QtWidgets.QCheckBox("Créer une copie statique sans BlendShapes", self)
        l_ba.addWidget(self.chk_allow_blendshape_copy)
        l_sec.addWidget(self.box_blendshape_alert)
        self.box_blendshape_alert.setVisible(False)
        l_dec.addWidget(grp_sec)

        # 5. Bouton d'action
        self.btn_execute_decimate = QtWidgets.QPushButton("Réduire le maillage (Contraction d'arêtes)", self)
        self.btn_execute_decimate.setObjectName("PrimaryButton")
        self.btn_execute_decimate.clicked.connect(self.on_execute_decimate)
        l_dec.addWidget(self.btn_execute_decimate)

        # 6. Comparaison Avant / Après (Post-exécution)
        self.box_post_results = QtWidgets.QFrame(self)
        self.box_post_results.setObjectName("CardBox")
        l_pr = QtWidgets.QVBoxLayout(self.box_post_results)
        l_pr.addWidget(QtWidgets.QLabel("Résultat réel de la dernière opération :", self))

        grid_res = QtWidgets.QGridLayout()
        self.lbl_res_tris = QtWidgets.QLabel("Triangles : 0 -> 0 (0%)", self)
        self.lbl_res_faces = QtWidgets.QLabel("Faces : 0 -> 0", self)
        self.lbl_res_verts = QtWidgets.QLabel("Sommets : 0 -> 0", self)
        grid_res.addWidget(self.lbl_res_tris, 0, 0)
        grid_res.addWidget(self.lbl_res_faces, 0, 1)
        grid_res.addWidget(self.lbl_res_verts, 1, 0)
        l_pr.addLayout(grid_res)

        self.lbl_metrology = QtWidgets.QLabel("Déviation géométrique : Non mesurée", self)
        self.lbl_metrology.setStyleSheet("color: #aaaaaa; font-style: italic;")
        l_pr.addWidget(self.lbl_metrology)
        l_dec.addWidget(self.box_post_results)
        self.box_post_results.setVisible(False)

        self.scroll_layout.addWidget(self.sec_decimate)

        # -------------------------------------------------------------
        # 4. SECTION 3: MODE EXPERT / RÉGLAGES TECHNIQUES (Replié par défaut)
        # -------------------------------------------------------------
        self.sec_expert = CollapsibleSection("SECTION 3 : MODE EXPERT / RÉGLAGES TECHNIQUES", expanded=False, parent=self)
        l_exp = self.sec_expert.content_layout

        btn_run_full_pipeline = QtWidgets.QPushButton("Exécuter tout le pipeline combiné (Réparation + Décimation + Normales)", self)
        btn_run_full_pipeline.setObjectName("SuccessButton")
        btn_run_full_pipeline.clicked.connect(self.on_run_full_pipeline)
        l_exp.addWidget(btn_run_full_pipeline)

        # LES 7 SOUS-PANNEAUX SPÉCIALISÉS (ACCORDÉONS DÉROULANTS)
        # 3.1 Réparation (Repair)
        self.sub_repair = CollapsibleSection("1. Réparation (Repair)", expanded=False, parent=self)
        l_sub_rep = self.sub_repair.content_layout
        self.chk_rep_loose = QtWidgets.QCheckBox("Supprimer sommets et arêtes orphelines", self)
        self.chk_rep_loose.setChecked(True)
        l_sub_rep.addWidget(self.chk_rep_loose)

        self.chk_rep_doubles = QtWidgets.QCheckBox("Fusionner les sommets doublons", self)
        self.chk_rep_doubles.setChecked(True)
        l_sub_rep.addWidget(self.chk_rep_doubles)

        row_tol = QtWidgets.QHBoxLayout()
        row_tol.addWidget(QtWidgets.QLabel("Tolérance doublons (m) :", self))
        self.spin_doubles_tol = QtWidgets.QDoubleSpinBox(self)
        self.spin_doubles_tol.setRange(0.00001, 1.0)
        self.spin_doubles_tol.setValue(0.0001)
        self.spin_doubles_tol.setDecimals(5)
        row_tol.addWidget(self.spin_doubles_tol)
        l_sub_rep.addLayout(row_tol)

        self.chk_rep_zero_faces = QtWidgets.QCheckBox("Supprimer faces à surface nulle", self)
        self.chk_rep_zero_faces.setChecked(True)
        l_sub_rep.addWidget(self.chk_rep_zero_faces)

        btn_do_repair = QtWidgets.QPushButton("Exécuter Réparation", self)
        btn_do_repair.clicked.connect(self.on_run_conservative_cleanup)
        l_sub_rep.addWidget(btn_do_repair)
        l_exp.addWidget(self.sub_repair)

        # 3.2 Cohérence Manifold
        self.sub_manifold = CollapsibleSection("2. Cohérence Manifold", expanded=False, parent=self)
        l_sub_man = self.sub_manifold.content_layout
        row_man_mode = QtWidgets.QHBoxLayout()
        row_man_mode.addWidget(QtWidgets.QLabel("Mode Manifold :", self))
        self.combo_man_mode = QtWidgets.QComboBox(self)
        self.combo_man_mode.addItem("Standard (Sûr)", "STANDARD")
        self.combo_man_mode.addItem("Agressif (Destructif)", "AGGRESSIVE")
        row_man_mode.addWidget(self.combo_man_mode)
        l_sub_man.addLayout(row_man_mode)

        self.chk_man_wire = QtWidgets.QCheckBox("Supprimer arêtes filaires (Wire edges)", self)
        self.chk_man_wire.setChecked(True)
        l_sub_man.addWidget(self.chk_man_wire)

        self.chk_man_fill = QtWidgets.QCheckBox("Reboucher les trous (Fill holes)", self)
        l_sub_man.addWidget(self.chk_man_fill)

        box_man_iw = QtWidgets.QFrame(self)
        box_man_iw.setObjectName("CardBox")
        l_bmi = QtWidgets.QVBoxLayout(box_man_iw)
        l_bmi.addWidget(QtWidgets.QLabel("Parois internes mitoyennes (Sûr) :", self))
        row_iw_btns = QtWidgets.QHBoxLayout()
        btn_iw_zoom = QtWidgets.QPushButton("Inspecter (Zoom)", self)
        btn_iw_zoom.clicked.connect(self.on_zoom_internal_walls)
        row_iw_btns.addWidget(btn_iw_zoom)
        btn_iw_del = QtWidgets.QPushButton("Supprimer", self)
        btn_iw_del.clicked.connect(self.on_remove_internal_walls)
        row_iw_btns.addWidget(btn_iw_del)
        l_bmi.addLayout(row_iw_btns)
        l_sub_man.addWidget(box_man_iw)

        btn_do_manifold = QtWidgets.QPushButton("Exécuter Manifold complet", self)
        btn_do_manifold.clicked.connect(self.on_remove_internal_walls)
        l_sub_man.addWidget(btn_do_manifold)
        l_exp.addWidget(self.sub_manifold)

        # 3.3 Dissolution Coplanaire
        self.sub_dissolve = CollapsibleSection("3. Dissolution Coplanaire", expanded=False, parent=self)
        l_sub_dis = self.sub_dissolve.content_layout
        row_dis_ang = QtWidgets.QHBoxLayout()
        row_dis_ang.addWidget(QtWidgets.QLabel("Angle de planéité limite (°) :", self))
        self.spin_exp_dissolve_angle = QtWidgets.QDoubleSpinBox(self)
        self.spin_exp_dissolve_angle.setRange(0.1, 90.0)
        self.spin_exp_dissolve_angle.setValue(5.0)
        row_dis_ang.addWidget(self.spin_exp_dissolve_angle)
        l_sub_dis.addLayout(row_dis_ang)

        self.chk_exp_pres_sharp = QtWidgets.QCheckBox("Préserver les arêtes vives", self)
        self.chk_exp_pres_sharp.setChecked(True)
        l_sub_dis.addWidget(self.chk_exp_pres_sharp)

        self.chk_exp_pres_seams = QtWidgets.QCheckBox("Préserver les coutures UV", self)
        self.chk_exp_pres_seams.setChecked(True)
        l_sub_dis.addWidget(self.chk_exp_pres_seams)

        btn_do_dissolve = QtWidgets.QPushButton("Exécuter Dissolution", self)
        btn_do_dissolve.clicked.connect(lambda: execute_dissolve(self.active_mesh, dissolve_angle=self.spin_exp_dissolve_angle.value()))
        l_sub_dis.addWidget(btn_do_dissolve)
        l_exp.addWidget(self.sub_dissolve)

        # 3.4 Simplification Détaillée
        self.sub_simplification = CollapsibleSection("4. Simplification Détaillée", expanded=False, parent=self)
        l_sub_sim = self.sub_simplification.content_layout
        row_sim_mode = QtWidgets.QHBoxLayout()
        row_sim_mode.addWidget(QtWidgets.QLabel("Mode simplification :", self))
        self.combo_exp_sim_mode = QtWidgets.QComboBox(self)
        self.combo_exp_sim_mode.addItem("Pourcentage", "PERCENTAGE")
        self.combo_exp_sim_mode.addItem("Budget Triangles", "BUDGET_TRIANGLES")
        row_sim_mode.addWidget(self.combo_exp_sim_mode)
        l_sub_sim.addLayout(row_sim_mode)

        btn_do_simp = QtWidgets.QPushButton("Exécuter Simplification", self)
        btn_do_simp.clicked.connect(self.on_execute_decimate)
        l_sub_sim.addWidget(btn_do_simp)
        l_exp.addWidget(self.sub_simplification)

        # 3.5 Topologie (Tris / Quads)
        self.sub_topology = CollapsibleSection("5. Topologie (Tris / Quads)", expanded=False, parent=self)
        l_sub_top = self.sub_topology.content_layout
        row_tri_m = QtWidgets.QHBoxLayout()
        row_tri_m.addWidget(QtWidgets.QLabel("Méthode triangulation :", self))
        self.combo_tri_method = QtWidgets.QComboBox(self)
        self.combo_tri_method.addItem("Beauty (Delaunay)", "BEAUTY")
        self.combo_tri_method.addItem("Ear-Clipping", "EAR_CLIP")
        row_tri_m.addWidget(self.combo_tri_method)
        l_sub_top.addLayout(row_tri_m)

        btn_quad_target = QtWidgets.QPushButton("Quadrangulation ciblée sécurisée", self)
        btn_quad_target.clicked.connect(self.on_quadrangulate)
        l_sub_top.addWidget(btn_quad_target)

        btn_cut_target = QtWidgets.QPushButton("Découpage N-Gones morphologique", self)
        btn_cut_target.clicked.connect(self.on_cut_ngons)
        l_sub_top.addWidget(btn_cut_target)
        l_exp.addWidget(self.sub_topology)

        # 3.6 Normales & Ombrage
        self.sub_normals = CollapsibleSection("6. Normales & Ombrage", expanded=False, parent=self)
        l_sub_norm = self.sub_normals.content_layout
        self.chk_norm_conform = QtWidgets.QCheckBox("Recalculer et orienter les normales", self)
        self.chk_norm_conform.setChecked(True)
        l_sub_norm.addWidget(self.chk_norm_conform)

        row_soft = QtWidgets.QHBoxLayout()
        row_soft.addWidget(QtWidgets.QLabel("Angle adoucissement (°) :", self))
        self.spin_soft_angle = QtWidgets.QDoubleSpinBox(self)
        self.spin_soft_angle.setRange(0.0, 180.0)
        self.spin_soft_angle.setValue(30.0)
        row_soft.addWidget(self.spin_soft_angle)
        l_sub_norm.addLayout(row_soft)

        btn_do_normals = QtWidgets.QPushButton("Exécuter Normales", self)
        btn_do_normals.clicked.connect(lambda: execute_normals(self.active_mesh, soft_edge_angle=self.spin_soft_angle.value()))
        l_sub_norm.addWidget(btn_do_normals)
        l_exp.addWidget(self.sub_normals)

        # 3.7 Données d'Objet
        self.sub_obj_data = CollapsibleSection("7. Données d'Objet", expanded=False, parent=self)
        l_sub_od = self.sub_obj_data.content_layout
        self.chk_clean_mats = QtWidgets.QCheckBox("Nettoyer slots de matériaux inutilisés", self)
        self.chk_clean_mats.setChecked(True)
        l_sub_od.addWidget(self.chk_clean_mats)

        self.chk_clean_sets = QtWidgets.QCheckBox("Nettoyer sets et vertex groups vides", self)
        self.chk_clean_sets.setChecked(True)
        l_sub_od.addWidget(self.chk_clean_sets)

        btn_do_od = QtWidgets.QPushButton("Exécuter Nettoyage Données", self)
        btn_do_od.clicked.connect(lambda: execute_object_data(self.active_mesh))
        l_sub_od.addWidget(btn_do_od)
        l_exp.addWidget(self.sub_obj_data)

        # 3.8 Rapport & Métriques
        self.sub_reports = CollapsibleSection("Rapport & Statistiques", expanded=False, parent=self)
        l_sub_rep_out = self.sub_reports.content_layout
        row_rep = QtWidgets.QHBoxLayout()
        btn_exp_json = QtWidgets.QPushButton("Exporter Rapport (JSON)", self)
        btn_exp_json.clicked.connect(lambda: self.export_report("JSON"))
        row_rep.addWidget(btn_exp_json)

        btn_exp_txt = QtWidgets.QPushButton("Exporter Rapport (Texte)", self)
        btn_exp_txt.clicked.connect(lambda: self.export_report("TXT"))
        row_rep.addWidget(btn_exp_txt)
        l_sub_rep_out.addLayout(row_rep)
        l_exp.addWidget(self.sub_reports)

        self.scroll_layout.addWidget(self.sec_expert)
        self.scroll_layout.addStretch()

    # -------------------------------------------------------------
    # SLOTS & LOGIC HANDLERS
    # -------------------------------------------------------------
    def refresh_selection(self):
        """Refreshes active mesh selection and updates live telemetry."""
        obj = get_selected_mesh()
        self.active_mesh = obj

        if not obj:
            self.lbl_object_name.setText("Objet : Aucun sélectionné")
            self.lbl_verts.setText("Sommets : 0")
            self.lbl_edges.setText("Arêtes : 0")
            self.lbl_faces.setText("Faces : 0")
            self.lbl_tris.setText("Triangles réels : 0")
            self.box_restore.setVisible(False)
            self.box_blendshape_alert.setVisible(False)
            self.active_stats = {}
            self.active_diagnosis = {}
            self._render_findings_table()
            self._clear_recommendations()
            return

        display_name = obj.split("|")[-1]
        self.lbl_object_name.setText(f"Objet : {display_name}")

        stats = get_mesh_statistics(obj)
        self.active_stats = stats

        if stats.get("valid"):
            self.lbl_verts.setText(f"Sommets : {stats['vertices']:,}")
            self.lbl_edges.setText(f"Arêtes : {stats['edges']:,}")
            self.lbl_faces.setText(f"Faces : {stats['faces']:,}")
            self.lbl_tris.setText(f"Triangles réels : {stats['triangles']:,}")
            self._update_estimation_label()

            # BlendShape alert
            has_bs = stats.get("has_blendshapes", False)
            self.box_blendshape_alert.setVisible(has_bs)

        is_optimized_copy = ("_MF_Optimized" in obj or cmds.attributeQuery("_mf_source_ptr", node=obj, exists=True))
        self.box_restore.setVisible(is_optimized_copy)

    def _on_collapse_mode_changed(self):
        mode = self.combo_collapse_mode.currentData()
        is_pct = (mode == "PERCENTAGE")
        self.slider_pct.setEnabled(is_pct)
        self.spin_budget.setEnabled(not is_pct)
        self._update_estimation_label()

    def on_pct_slider_changed(self, val):
        self.lbl_pct_val.setText(f"{val}%")
        self._update_estimation_label()

    def _update_estimation_label(self):
        if not self.active_stats or not self.active_stats.get("valid"):
            self.lbl_estimation.setText("Estimation : ~0 triangles")
            return

        real_tris = self.active_stats.get("triangles", 0)
        mode = self.combo_collapse_mode.currentData() if hasattr(self, "combo_collapse_mode") else "PERCENTAGE"

        if mode == "PERCENTAGE":
            pct = self.slider_pct.value()
            est = max(4, int(real_tris * (1.0 - (pct / 100.0))))
            self.lbl_estimation.setText(f"Estimation : ~{est:,} triangles (-{pct:.1f}%)")
        else:
            budget = self.spin_budget.value()
            est = min(real_tris, max(4, budget))
            pct = ((real_tris - est) / float(real_tris) * 100.0) if real_tris > 0 else 0.0
            self.lbl_estimation.setText(f"Estimation : ~{est:,} triangles (cible demandée, -{pct:.1f}%)")

    def on_method_changed(self):
        method = self.combo_method.currentData()
        is_collapse = (method == "COLLAPSE")
        self.w_collapse_goal.setVisible(is_collapse)
        self.w_dissolve_goal.setVisible(not is_collapse)
        self.btn_execute_decimate.setText(
            "Réduire le maillage (Contraction d'arêtes)" if is_collapse else "Simplifier les faces (Dissolution coplanaire)"
        )
        if is_collapse:
            self.lbl_method_guidance.setText("Recommandé pour surfaces courbes : contraction d'arêtes préservant la silhouette.")
        else:
            self.lbl_method_guidance.setText("Spécialisé pièces hard-surface & CAD : dissout les arêtes coplanaires sans distorsion.")

    def on_profile_changed(self):
        p_key = self.combo_profile.currentData()
        p_info = PROFILES.get(p_key, PROFILES["GENERAL"])
        self.lbl_profile_summary.setText(f"{p_info['name']} : {p_info['summary']}")
        if self.active_stats.get("valid"):
            self._re_evaluate_diagnosis()

    def on_analyze_topology(self):
        self.refresh_selection()
        if not self.active_mesh:
            return
        self._re_evaluate_diagnosis()

    def _re_evaluate_diagnosis(self):
        if not self.active_mesh or not self.active_stats.get("valid"):
            return

        p_key = self.combo_profile.currentData()
        strict_m = self.chk_strict_manifold.isChecked()
        quads_only = self.chk_quads_only.isChecked()

        diag = evaluate_mesh_diagnosis(
            self.active_mesh,
            self.active_stats,
            profile_id=p_key,
            strict_manifold=strict_m,
            quads_only=quads_only,
            intentional_ids=self.intentional_finding_ids
        )
        self.active_diagnosis = diag

        # Health status
        h = diag["health"]
        status = h["status"]
        if status == "HEALTHY":
            self.lbl_health_status.setText("Santé : Maillage géométriquement sain")
            self.lbl_health_status.setStyleSheet("font-weight: bold; color: #2ecc71;")
        elif status == "CRITICAL":
            self.lbl_health_status.setText(f"Santé : {h['defects_count']} anomalie(s) critique(s)")
            self.lbl_health_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        else:
            self.lbl_health_status.setText(f"Santé : {h['risks_count']} point(s) de vigilance")
            self.lbl_health_status.setStyleSheet("font-weight: bold; color: #f39c12;")

        self.lbl_counters.setText(f"Défauts : {h['defects_count']}  |  Risques : {h['risks_count']}  |  Observations : {h['observations_count']}")

        # Render Detailed Findings Table
        self._render_findings_table()

        # Render 4 Recommendation Groups
        self._render_recommendations()

    def _render_findings_table(self):
        """Renders the detailed findings cards with Zoom and Auto-Fix buttons."""
        while self.l_findings_cards.count() > 0:
            item = self.l_findings_cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.active_diagnosis or not self.active_diagnosis.get("valid"):
            self.sec_findings_table.toggle_btn.setText("▶ Tableau détaillé des constats (0)")
            lbl_empty = QtWidgets.QLabel("Cliquez sur 'Analyser le maillage' pour afficher les constats.", self)
            lbl_empty.setStyleSheet("color: #888888; font-style: italic;")
            self.l_findings_cards.addWidget(lbl_empty)
            return

        findings = self.active_diagnosis.get("findings", [])
        self.sec_findings_table.title_text = f"Tableau détaillé ({len(findings)} constats)"
        self.sec_findings_table._update_title()

        cat_filter = self.combo_filter_cat.currentData()
        sev_filter = self.combo_filter_sev.currentData()

        matched = 0
        for f in findings:
            if cat_filter != "ALL" and f.get("category") != cat_filter:
                continue
            if sev_filter != "ALL" and f.get("severity") != sev_filter:
                continue

            matched += 1
            f_id = f.get("id")
            f_name = f.get("name")
            f_sev = f.get("severity")
            f_is_int = f.get("is_intentional", False)
            f_comps = f.get("components", [])

            card = QtWidgets.QFrame(self)
            card.setObjectName("AlertBox" if f_sev == "DEFECT" and not f_is_int else "CardBox")
            l_cd = QtWidgets.QVBoxLayout(card)
            l_cd.setContentsMargins(6, 6, 6, 6)
            l_cd.setSpacing(4)

            # Top Header Row
            row_top = QtWidgets.QHBoxLayout()
            if f_is_int:
                lbl_badge = QtWidgets.QLabel("[INTENTIONNEL]", self)
                lbl_badge.setStyleSheet("color: #2ecc71; font-weight: bold;")
            elif f_sev == "DEFECT":
                lbl_badge = QtWidgets.QLabel("[DÉFAUT]", self)
                lbl_badge.setStyleSheet("color: #e74c3c; font-weight: bold;")
            elif f_sev == "RISK":
                lbl_badge = QtWidgets.QLabel("[RISQUE]", self)
                lbl_badge.setStyleSheet("color: #f39c12; font-weight: bold;")
            else:
                lbl_badge = QtWidgets.QLabel("[INFO]", self)
                lbl_badge.setStyleSheet("color: #4a90e2; font-weight: bold;")
            row_top.addWidget(lbl_badge)

            lbl_title = QtWidgets.QLabel(f_name, self)
            lbl_title.setStyleSheet("font-weight: bold;")
            row_top.addWidget(lbl_title)
            row_top.addStretch()

            # Zoom Button
            if f_comps:
                btn_zoom = QtWidgets.QPushButton(f"Zoomer ({len(f_comps)})", self)
                btn_zoom.setStyleSheet("background-color: #1e3a5f; color: #ffffff; font-weight: bold; padding: 2px 8px;")
                btn_zoom.clicked.connect(lambda _, c=f_comps: focus_on_components(c))
                row_top.addWidget(btn_zoom)

            # Mark Intentional Toggle
            btn_int = QtWidgets.QPushButton("Rétablir" if f_is_int else "Intentionnel", self)
            btn_int.setMaximumWidth(80)
            btn_int.clicked.connect(lambda _, fid=f_id: self._toggle_intentional(fid))
            row_top.addWidget(btn_int)
            l_cd.addLayout(row_top)

            # Details
            if f.get("explanation"):
                l_cd.addWidget(QtWidgets.QLabel(f.get("explanation"), self))
            if f.get("consequence"):
                lbl_conseq = QtWidgets.QLabel(f"Impact : {f.get('consequence')}", self)
                lbl_conseq.setStyleSheet("color: #aaaaaa;")
                l_cd.addWidget(lbl_conseq)
            if f.get("recommendation"):
                lbl_rec = QtWidgets.QLabel(f"Conseil : {f.get('recommendation')}", self)
                lbl_rec.setStyleSheet("color: #4a90e2;")
                l_cd.addWidget(lbl_rec)

            # Auto-Fix Button if operator available
            op = f.get("operator")
            op_text = f.get("operator_text")
            if op:
                btn_fix = QtWidgets.QPushButton(f"Réparer : {op_text}", self)
                btn_fix.setObjectName("SuccessButton")
                if op == "cut_ngons":
                    btn_fix.clicked.connect(self.on_cut_ngons)
                elif op == "conservative_clean":
                    btn_fix.clicked.connect(self.on_run_conservative_cleanup)
                elif op == "quadrangulate":
                    btn_fix.clicked.connect(self.on_quadrangulate)
                elif op == "remove_internal_walls":
                    btn_fix.clicked.connect(self.on_remove_internal_walls)
                l_cd.addWidget(btn_fix)

            self.l_findings_cards.addWidget(card)

        if matched == 0:
            lbl_none = QtWidgets.QLabel("Aucun constat ne correspond aux filtres sélectionnés.", self)
            lbl_none.setStyleSheet("color: #888888; font-style: italic;")
            self.l_findings_cards.addWidget(lbl_none)

    def _toggle_intentional(self, finding_id: str):
        if finding_id in self.intentional_finding_ids:
            self.intentional_finding_ids.remove(finding_id)
        else:
            self.intentional_finding_ids.append(finding_id)
        self._re_evaluate_diagnosis()

    def _clear_recommendations(self):
        while self.l_recs.count() > 0:
            item = self.l_recs.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_recommendations(self):
        self._clear_recommendations()
        diag = self.active_diagnosis
        rec_groups = diag.get("recommendation_groups", {})

        # Catégorie 1 : Corrections conservatrices recommandées (Sûr)
        c1_list = rec_groups.get("conservative", [])
        box_c1 = QtWidgets.QFrame(self)
        box_c1.setObjectName("CardBox")
        l_b1 = QtWidgets.QVBoxLayout(box_c1)
        l_b1.addWidget(QtWidgets.QLabel("1. Corrections conservatrices recommandées (Sûr) :", self))
        if c1_list:
            for item in c1_list:
                card = QtWidgets.QFrame(self)
                card.setObjectName("CardBox")
                lc = QtWidgets.QVBoxLayout(card)
                lc.addWidget(QtWidgets.QLabel(f"• {item['title']} [{item.get('confidence', 'Sûr')}]", self))
                lc.addWidget(QtWidgets.QLabel(f"  Problème : {item['problem']}", self))
                lc.addWidget(QtWidgets.QLabel(f"  Effet : {item['effect']}", self))
                row_act = QtWidgets.QHBoxLayout()
                comps = item.get("components", [])
                if comps:
                    btn_z = QtWidgets.QPushButton(f"Zoom ({len(comps)})", self)
                    btn_z.clicked.connect(lambda _, c=comps: focus_on_components(c))
                    row_act.addWidget(btn_z)
                btn_run = QtWidgets.QPushButton(item.get("operator_text", "Exécuter"), self)
                btn_run.setObjectName("SuccessButton")
                btn_run.clicked.connect(self.on_run_conservative_cleanup)
                row_act.addWidget(btn_run)
                lc.addLayout(row_act)
                l_b1.addWidget(card)
        else:
            lbl_ok = QtWidgets.QLabel("✓ Aucune dégénérescence ni anomalie conservatrice à corriger.", self)
            lbl_ok.setStyleSheet("color: #2ecc71;")
            l_b1.addWidget(lbl_ok)
        self.l_recs.addWidget(box_c1)

        # Catégorie 2 : Optimisations ciblées pour l'objectif
        c2_list = rec_groups.get("targeted", [])
        box_c2 = QtWidgets.QFrame(self)
        box_c2.setObjectName("CardBox")
        l_b2 = QtWidgets.QVBoxLayout(box_c2)
        l_b2.addWidget(QtWidgets.QLabel("2. Optimisations ciblées pour l'objectif :", self))
        if c2_list:
            for item in c2_list:
                card = QtWidgets.QFrame(self)
                card.setObjectName("CardBox")
                lc = QtWidgets.QVBoxLayout(card)
                lc.addWidget(QtWidgets.QLabel(f"• {item['title']} [{item.get('confidence', 'Recommandé')}]", self))
                lc.addWidget(QtWidgets.QLabel(f"  Problème : {item['problem']}", self))
                lc.addWidget(QtWidgets.QLabel(f"  Effet : {item['effect']}", self))
                row_act = QtWidgets.QHBoxLayout()
                comps = item.get("components", [])
                if comps:
                    btn_z = QtWidgets.QPushButton(f"Zoom ({len(comps)})", self)
                    btn_z.clicked.connect(lambda _, c=comps: focus_on_components(c))
                    row_act.addWidget(btn_z)
                btn_op = QtWidgets.QPushButton(item.get("operator_text", "Exécuter"), self)
                btn_op.setObjectName("PrimaryButton")
                if item.get("operator") == "cut_ngons":
                    btn_op.clicked.connect(self.on_cut_ngons)
                elif item.get("operator") == "quadrangulate":
                    btn_op.clicked.connect(self.on_quadrangulate)
                row_act.addWidget(btn_op)
                lc.addLayout(row_act)
                l_b2.addWidget(card)
        else:
            lbl_ok2 = QtWidgets.QLabel("✓ Topologie polygonale adaptée aux exigences de l'objectif.", self)
            lbl_ok2.setStyleSheet("color: #2ecc71;")
            l_b2.addWidget(lbl_ok2)
        self.l_recs.addWidget(box_c2)

        # Catégorie 3 : Actions à risque à examiner individuellement
        c3_list = rec_groups.get("risky", [])
        box_c3 = QtWidgets.QFrame(self)
        box_c3.setObjectName("AlertBox")
        l_b3 = QtWidgets.QVBoxLayout(box_c3)
        l_b3.addWidget(QtWidgets.QLabel("3. Actions à risque à examiner individuellement :", self))
        if c3_list:
            for item in c3_list:
                card = QtWidgets.QFrame(self)
                card.setObjectName("CardBox")
                lc = QtWidgets.QVBoxLayout(card)
                lc.addWidget(QtWidgets.QLabel(f"⚠️ {item['title']} [{item.get('confidence', 'Risqué')}]", self))
                lc.addWidget(QtWidgets.QLabel(f"  Problème : {item['problem']}", self))
                row_act = QtWidgets.QHBoxLayout()
                comps = item.get("components", [])
                if comps:
                    btn_z = QtWidgets.QPushButton(f"Zoom ({len(comps)})", self)
                    btn_z.clicked.connect(lambda _, c=comps: focus_on_components(c))
                    row_act.addWidget(btn_z)
                btn_iw = QtWidgets.QPushButton(item.get("operator_text", "Supprimer parois internes"), self)
                btn_iw.clicked.connect(self.on_remove_internal_walls)
                row_act.addWidget(btn_iw)
                lc.addLayout(row_act)
                l_b3.addWidget(card)
        else:
            lbl_ok3 = QtWidgets.QLabel("✓ Aucune configuration géométrique risquée ou ambiguë détectée.", self)
            lbl_ok3.setStyleSheet("color: #2ecc71;")
            l_b3.addWidget(lbl_ok3)
        self.l_recs.addWidget(box_c3)

        # Catégorie 4 : Observations sans action requise
        c4_list = rec_groups.get("observations", [])
        box_c4 = QtWidgets.QFrame(self)
        box_c4.setObjectName("CardBox")
        l_b4 = QtWidgets.QVBoxLayout(box_c4)
        l_b4.addWidget(QtWidgets.QLabel("4. Observations sans action requise :", self))
        if c4_list:
            for item in c4_list:
                l_b4.addWidget(QtWidgets.QLabel(f"• {item['title']}: {item['problem']}", self))
        else:
            lbl_ok4 = QtWidgets.QLabel("✓ Aucune observation supplémentaire.", self)
            lbl_ok4.setStyleSheet("color: #888888; font-style: italic;")
            l_b4.addWidget(lbl_ok4)
        self.l_recs.addWidget(box_c4)

    def on_toggle_wireframe(self):
        toggle_wireframe_display()

    def on_clear_inspection(self):
        clear_inspection_view()

    def on_zoom_internal_walls(self):
        if not self.active_mesh:
            return
        iw = detect_internal_walls(self.active_mesh)
        if iw:
            focus_on_components(iw)

    def on_run_conservative_cleanup(self):
        if not self.active_mesh:
            return
        execute_conservative_cleanup(self.active_mesh)
        self.refresh_selection()
        self._re_evaluate_diagnosis()

    def on_cut_ngons(self):
        if not self.active_mesh:
            return
        execute_ngon_cut(self.active_mesh)
        self.refresh_selection()
        self._re_evaluate_diagnosis()

    def on_quadrangulate(self):
        if not self.active_mesh:
            return
        execute_targeted_quadrangulation(self.active_mesh)
        self.refresh_selection()
        self._re_evaluate_diagnosis()

    def on_remove_internal_walls(self):
        if not self.active_mesh:
            return
        execute_remove_internal_walls(self.active_mesh)
        self.refresh_selection()
        self._re_evaluate_diagnosis()

    def on_restore_original(self):
        if not self.active_mesh:
            return
        restore_original_object(self.active_mesh)
        self.refresh_selection()

    def on_execute_decimate(self):
        if not self.active_mesh:
            return

        method = self.combo_method.currentData()
        create_copy = self.chk_create_copy.isChecked()

        source_obj = self.active_mesh
        target_obj = source_obj

        if create_copy:
            target_obj = duplicate_object_non_destructive(source_obj)
            # Check blendshapes removal on copy if needed
            if self.active_stats.get("has_blendshapes") and self.chk_allow_blendshape_copy.isChecked():
                history = cmds.listHistory(target_obj) or []
                bs_nodes = cmds.ls(history, type='blendShape') or []
                if bs_nodes:
                    cmds.delete(bs_nodes)

        t_before = cmds.polyEvaluate(target_obj, triangle=True)
        f_before = cmds.polyEvaluate(target_obj, face=True)
        v_before = cmds.polyEvaluate(target_obj, vertex=True)
        t0 = time.perf_counter()

        if method == "COLLAPSE":
            col_mode = self.combo_collapse_mode.currentData() if hasattr(self, "combo_collapse_mode") else "PERCENTAGE"
            pct = float(self.slider_pct.value())
            budget = self.spin_budget.value()

            res = execute_simplification(
                target_obj,
                mode=col_mode,
                percentage=pct,
                target_triangles=budget,
                preserve_boundaries=self.chk_pres_boundaries.isChecked(),
                preserve_sharp=self.chk_pres_sharp.isChecked(),
                preserve_seams=self.chk_pres_seams.isChecked(),
                triangulate_first=self.chk_triangulate_first.isChecked()
            )
        else:
            ang = self.spin_dissolve_angle.value()
            res = execute_dissolve(
                target_obj,
                dissolve_angle=ang,
                preserve_sharp=self.chk_pres_sharp.isChecked(),
                preserve_seams=self.chk_pres_seams.isChecked()
            )

        dur = time.perf_counter() - t0
        t_after = cmds.polyEvaluate(target_obj, triangle=True)
        f_after = cmds.polyEvaluate(target_obj, face=True)
        v_after = cmds.polyEvaluate(target_obj, vertex=True)

        # Show post results grid
        pct_red = round(((t_before - t_after) / float(t_before) * 100.0), 1) if t_before > 0 else 0.0
        delta_f = f_before - f_after
        delta_v = v_before - v_after

        self.lbl_res_tris.setText(f"Triangles réels : {t_before:,} -> {t_after:,} (-{pct_red}%)")
        self.lbl_res_faces.setText(f"Faces : {f_before:,} -> {f_after:,} (-{delta_f:,})")
        self.lbl_res_verts.setText(f"Sommets : {v_before:,} -> {v_after:,} (-{delta_v:,})")

        # Metrology
        val = validate_mesh_surface(source_obj, target_obj)
        if val.get("measured"):
            self.lbl_metrology.setText(f"Écart Hausdorff max : {val['max_hausdorff_m']} m  |  Déviation moyenne : {val['mean_deviation_m']} m")
        else:
            self.lbl_metrology.setText("Déviation géométrique : Non mesurée")

        self.box_post_results.setVisible(True)
        cmds.select(target_obj)
        self.refresh_selection()

    def on_run_full_pipeline(self):
        if not self.active_mesh:
            return
        settings = {
            "create_new_object": self.chk_create_copy.isChecked(),
            "enable_repair": True,
            "enable_internal_walls": True,
            "enable_dissolve": False,
            "enable_simplification": True,
            "simplification_percentage": float(self.slider_pct.value()),
            "enable_topology": False,
            "enable_normals": True,
            "enable_object_data": True
        }
        rep = run_meshforge_pipeline(self.active_mesh, settings)
        if rep.get("success") and rep.get("result_name") and cmds.objExists(rep["result_name"]):
            cmds.select(rep["result_name"])
        self.refresh_selection()

    def export_report(self, format_type: str = "JSON"):
        if not self.active_diagnosis:
            return
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save MeshForge Report",
            f"MeshForge_{self.active_mesh}_Report.{format_type.lower()}",
            "JSON (*.json)" if format_type == "JSON" else "Text (*.txt)"
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                if format_type == "JSON":
                    json.dump(self.active_diagnosis, f, indent=2, default=str)
                else:
                    f.write(f"MeshForge Maya Report for {self.active_mesh}\n")
                    f.write(str(self.active_diagnosis))


# Global window reference to prevent garbage collection
_MESHFORGE_MAYA_WINDOW = None

def show_meshforge_window():
    """Entry point to launch or bring MeshForge Maya to the front."""
    global _MESHFORGE_MAYA_WINDOW

    # Get Maya parent window if possible
    parent_win = None
    try:
        from shiboken6 import wrapInstance
        import maya.OpenMayaUI as omui
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            parent_win = wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        try:
            from shiboken2 import wrapInstance
            import maya.OpenMayaUI as omui
            ptr = omui.MQtUtil.mainWindow()
            if ptr:
                parent_win = wrapInstance(int(ptr), QtWidgets.QWidget)
        except Exception:
            pass

    if _MESHFORGE_MAYA_WINDOW is None:
        _MESHFORGE_MAYA_WINDOW = MeshForgeMayaWindow(parent=parent_win)

    _MESHFORGE_MAYA_WINDOW.show()
    _MESHFORGE_MAYA_WINDOW.raise_()
    _MESHFORGE_MAYA_WINDOW.activateWindow()
    return _MESHFORGE_MAYA_WINDOW
