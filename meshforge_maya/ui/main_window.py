"""MeshForge Maya - Main User Interface Window.
Dockable PySide GUI providing complete 1:1 feature parity with MeshForge for Blender:
- Section 1: CLEAN (Analysis, Findings Table, Filter, 8 Profiles, 4 Categories, Topology Tools)
- Section 2: DECIMATE (Collapse vs Dissolve, Live Estimation, Detail Preservation, Blendshape Safety)
- Section 3: EXPERT MODE (Combined Pipeline & 7 Specialized Subpanels)
"""

from __future__ import annotations
import sys
import json
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
        self.toggle_btn.setStyleSheet("text-align: left; font-weight: bold; padding: 6px; background-color: #333333; border: 1px solid #444444;")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(expanded)
        self.toggle_btn.clicked.connect(self._on_toggle)

        self.title_text = title
        self._update_title()
        self.layout_main.addWidget(self.toggle_btn)

        # Content widget
        self.content_widget = QtWidgets.QWidget(self)
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(6, 6, 6, 6)
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


class MeshForgeMayaWindow(QtWidgets.QMainWindow):
    """MeshForge for Maya - Main Control Center Window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MeshForge — 3D Assistant (Maya)")
        self.resize(450, 780)
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
        main_vbox.setContentsMargins(8, 8, 8, 8)
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
        self.lbl_object_name = QtWidgets.QLabel("Object: None selected", self)
        self.lbl_object_name.setObjectName("HeaderTitle")
        row_obj.addWidget(self.lbl_object_name)

        self.btn_refresh_sel = QtWidgets.QPushButton("Refresh", self)
        self.btn_refresh_sel.setMaximumWidth(70)
        self.btn_refresh_sel.clicked.connect(self.refresh_selection)
        row_obj.addWidget(self.btn_refresh_sel)
        box_tel_layout.addLayout(row_obj)

        # Telemetry counts grid
        grid_tel = QtWidgets.QGridLayout()
        self.lbl_verts = QtWidgets.QLabel("Vertices: 0", self)
        self.lbl_edges = QtWidgets.QLabel("Edges: 0", self)
        self.lbl_faces = QtWidgets.QLabel("Faces: 0", self)
        self.lbl_tris = QtWidgets.QLabel("Real Tris: 0", self)
        grid_tel.addWidget(self.lbl_verts, 0, 0)
        grid_tel.addWidget(self.lbl_edges, 0, 1)
        grid_tel.addWidget(self.lbl_faces, 1, 0)
        grid_tel.addWidget(self.lbl_tris, 1, 1)
        box_tel_layout.addLayout(grid_tel)

        self.scroll_layout.addWidget(self.box_telemetry)

        # -------------------------------------------------------------
        # 2. SECTION 1: CLEAN — NETTOYER ET RÉPARER (Open by default)
        # -------------------------------------------------------------
        self.sec_clean = CollapsibleSection("SECTION 1: CLEAN — Clean & Repair", expanded=True, parent=self)
        l_clean = self.sec_clean.content_layout

        # Step 1: Analyze & Viewport
        grp_step1 = QtWidgets.QGroupBox("1. Analyze Mesh & 3D Viewport", self)
        l_s1 = QtWidgets.QVBoxLayout(grp_step1)

        self.btn_analyze = QtWidgets.QPushButton("Analyze Topology", self)
        self.btn_analyze.setObjectName("PrimaryButton")
        self.btn_analyze.clicked.connect(self.on_analyze_topology)
        l_s1.addWidget(self.btn_analyze)

        row_tools = QtWidgets.QHBoxLayout()
        self.btn_wire = QtWidgets.QPushButton("Toggle Wireframe", self)
        self.btn_wire.clicked.connect(self.on_toggle_wireframe)
        row_tools.addWidget(self.btn_wire)

        self.btn_clear_view = QtWidgets.QPushButton("Clear Selection", self)
        self.btn_clear_view.clicked.connect(self.on_clear_inspection)
        row_tools.addWidget(self.btn_clear_view)
        l_s1.addLayout(row_tools)
        l_clean.addWidget(grp_step1)

        # Step 2: Factual Findings
        grp_step2 = QtWidgets.QGroupBox("2. Factual Geometric Findings", self)
        l_s2 = QtWidgets.QVBoxLayout(grp_step2)

        self.lbl_health_status = QtWidgets.QLabel("Health: Run analysis to inspect", self)
        self.lbl_health_status.setStyleSheet("font-weight: bold; color: #4a90e2;")
        l_s2.addWidget(self.lbl_health_status)

        self.lbl_counters = QtWidgets.QLabel("Defects: 0  |  Risks: 0  |  Observations: 0", self)
        l_s2.addWidget(self.lbl_counters)

        # Detailed Findings Table container
        self.findings_container = QtWidgets.QVBoxLayout()
        l_s2.addLayout(self.findings_container)
        l_clean.addWidget(grp_step2)

        # Step 3: Target Profile Selection
        grp_step3 = QtWidgets.QGroupBox("3. Target Profile for Asset", self)
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

        # Complementary Constraints
        self.chk_strict_manifold = QtWidgets.QCheckBox("Enforce Strict Manifold Watertightness", self)
        self.chk_strict_manifold.stateChanged.connect(self.on_profile_changed)
        l_s3.addWidget(self.chk_strict_manifold)

        self.chk_quads_only = QtWidgets.QCheckBox("Enforce 100% Quads Only (Flag Tris/N-gons)", self)
        self.chk_quads_only.stateChanged.connect(self.on_profile_changed)
        l_s3.addWidget(self.chk_quads_only)

        l_clean.addWidget(grp_step3)

        # Step 4: Recommendations
        grp_step4 = QtWidgets.QGroupBox("4. Contextual Recommendations", self)
        self.l_recs = QtWidgets.QVBoxLayout(grp_step4)
        l_clean.addWidget(grp_step4)

        # Direct Topology Tools
        grp_topo_tools = QtWidgets.QGroupBox("Direct Topology Tools", self)
        l_tt = QtWidgets.QHBoxLayout(grp_topo_tools)
        btn_cut_ngons = QtWidgets.QPushButton("Cut N-Gons", self)
        btn_cut_ngons.clicked.connect(self.on_cut_ngons)
        l_tt.addWidget(btn_cut_ngons)

        btn_quad = QtWidgets.QPushButton("Quadrangulate (Tris -> Quads)", self)
        btn_quad.clicked.connect(self.on_quadrangulate)
        l_tt.addWidget(btn_quad)
        l_clean.addWidget(grp_topo_tools)

        # Step 5: History & Restore
        self.box_restore = QtWidgets.QFrame(self)
        self.box_restore.setObjectName("CardBox")
        l_res = QtWidgets.QHBoxLayout(self.box_restore)
        self.btn_restore = QtWidgets.QPushButton("Restore Original Mesh", self)
        self.btn_restore.setObjectName("DangerButton")
        self.btn_restore.clicked.connect(self.on_restore_original)
        l_res.addWidget(self.btn_restore)
        l_clean.addWidget(self.box_restore)

        self.scroll_layout.addWidget(self.sec_clean)

        # -------------------------------------------------------------
        # 3. SECTION 2: DECIMATE — RÉDUIRE LE MAILLAGE (Collapsed by default)
        # -------------------------------------------------------------
        self.sec_decimate = CollapsibleSection("SECTION 2: DECIMATE — Mesh Reduction", expanded=False, parent=self)
        l_dec = self.sec_decimate.content_layout

        # Step 1: Reduction Method
        grp_method = QtWidgets.QGroupBox("1. Reduction Method", self)
        l_m = QtWidgets.QVBoxLayout(grp_method)
        self.combo_method = QtWidgets.QComboBox(self)
        self.combo_method.addItem("Edge Collapse QEM (Curved / Organic)", "COLLAPSE")
        self.combo_method.addItem("Coplanar Dissolve (Planar / CAD)", "DISSOLVE")
        self.combo_method.currentIndexChanged.connect(self.on_method_changed)
        l_m.addWidget(self.combo_method)

        self.lbl_method_guidance = QtWidgets.QLabel("Recommended for curved and organic shapes: contracts edges while preserving volume.", self)
        self.lbl_method_guidance.setWordWrap(True)
        self.lbl_method_guidance.setStyleSheet("color: #aaaaaa; font-style: italic;")
        l_m.addWidget(self.lbl_method_guidance)
        l_dec.addWidget(grp_method)

        # Step 2: Goal & Dynamic Budget Estimation
        grp_goal = QtWidgets.QGroupBox("2. Target Objective & Dynamic Estimation", self)
        l_g = QtWidgets.QVBoxLayout(grp_goal)

        # Collapse inputs
        self.w_collapse_goal = QtWidgets.QWidget(self)
        l_cg = QtWidgets.QVBoxLayout(self.w_collapse_goal)
        l_cg.setContentsMargins(0, 0, 0, 0)

        row_pct = QtWidgets.QHBoxLayout()
        row_pct.addWidget(QtWidgets.QLabel("Reduction (%):", self))
        self.slider_pct = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.slider_pct.setRange(0, 99)
        self.slider_pct.setValue(50)
        self.slider_pct.valueChanged.connect(self.on_pct_slider_changed)
        row_pct.addWidget(self.slider_pct)
        self.lbl_pct_val = QtWidgets.QLabel("50%", self)
        row_pct.addWidget(self.lbl_pct_val)
        l_cg.addLayout(row_pct)

        self.lbl_estimation = QtWidgets.QLabel("Estimation: ~0 triangles (-50.0%)", self)
        self.lbl_estimation.setStyleSheet("font-weight: bold; color: #4a90e2;")
        l_cg.addWidget(self.lbl_estimation)
        l_g.addWidget(self.w_collapse_goal)

        # Dissolve inputs
        self.w_dissolve_goal = QtWidgets.QWidget(self)
        l_dg = QtWidgets.QVBoxLayout(self.w_dissolve_goal)
        l_dg.setContentsMargins(0, 0, 0, 0)
        row_ang = QtWidgets.QHBoxLayout()
        row_ang.addWidget(QtWidgets.QLabel("Dissolve Angle (°):", self))
        self.spin_dissolve_angle = QtWidgets.QDoubleSpinBox(self)
        self.spin_dissolve_angle.setRange(0.1, 90.0)
        self.spin_dissolve_angle.setValue(5.0)
        row_ang.addWidget(self.spin_dissolve_angle)
        l_dg.addLayout(row_ang)
        l_g.addWidget(self.w_dissolve_goal)
        self.w_dissolve_goal.setVisible(False)

        l_dec.addWidget(grp_goal)

        # Step 3: Feature Preservations
        grp_pres = QtWidgets.QGroupBox("3. Feature & Detail Preservation", self)
        l_p = QtWidgets.QVBoxLayout(grp_pres)
        self.chk_pres_boundaries = QtWidgets.QCheckBox("Preserve Open Boundaries", self)
        self.chk_pres_boundaries.setChecked(True)
        l_p.addWidget(self.chk_pres_boundaries)

        self.chk_pres_sharp = QtWidgets.QCheckBox("Preserve Hard / Sharp Edges", self)
        self.chk_pres_sharp.setChecked(True)
        l_p.addWidget(self.chk_pres_sharp)

        self.chk_pres_seams = QtWidgets.QCheckBox("Preserve UV Texture Seams", self)
        self.chk_pres_seams.setChecked(True)
        l_p.addWidget(self.chk_pres_seams)
        l_dec.addWidget(grp_pres)

        # Step 4: Safety & Workflow
        grp_sec = QtWidgets.QGroupBox("4. Workflow Safety & Guards", self)
        l_sec = QtWidgets.QVBoxLayout(grp_sec)
        self.chk_create_copy = QtWidgets.QCheckBox("Create New Object (Non-Destructive)", self)
        self.chk_create_copy.setChecked(True)
        l_sec.addWidget(self.chk_create_copy)

        self.box_blendshape_alert = QtWidgets.QFrame(self)
        self.box_blendshape_alert.setObjectName("AlertBox")
        l_ba = QtWidgets.QVBoxLayout(self.box_blendshape_alert)
        l_ba.addWidget(QtWidgets.QLabel("⚠️ BlendShape deformers detected on mesh!", self))
        self.chk_allow_blendshape_copy = QtWidgets.QCheckBox("Create static copy without BlendShapes", self)
        l_ba.addWidget(self.chk_allow_blendshape_copy)
        l_sec.addWidget(self.box_blendshape_alert)
        self.box_blendshape_alert.setVisible(False)

        l_dec.addWidget(grp_sec)

        # Step 5: Execution Button
        self.btn_execute_decimate = QtWidgets.QPushButton("Reduce Mesh (Edge Collapse)", self)
        self.btn_execute_decimate.setObjectName("PrimaryButton")
        self.btn_execute_decimate.clicked.connect(self.on_execute_decimate)
        l_dec.addWidget(self.btn_execute_decimate)

        # Step 6: Post-Execution Telemetry Grid
        self.box_post_results = QtWidgets.QFrame(self)
        self.box_post_results.setObjectName("CardBox")
        l_pr = QtWidgets.QVBoxLayout(self.box_post_results)
        l_pr.addWidget(QtWidgets.QLabel("Real Result of Last Operation:", self))

        grid_res = QtWidgets.QGridLayout()
        self.lbl_res_tris = QtWidgets.QLabel("Triangles: 0 -> 0 (0%)", self)
        self.lbl_res_faces = QtWidgets.QLabel("Faces: 0 -> 0", self)
        self.lbl_res_verts = QtWidgets.QLabel("Vertices: 0 -> 0", self)
        grid_res.addWidget(self.lbl_res_tris, 0, 0)
        grid_res.addWidget(self.lbl_res_faces, 0, 1)
        grid_res.addWidget(self.lbl_res_verts, 1, 0)
        l_pr.addLayout(grid_res)

        self.lbl_metrology = QtWidgets.QLabel("Geometric Deviation: Not measured", self)
        self.lbl_metrology.setStyleSheet("color: #aaaaaa; font-style: italic;")
        l_pr.addWidget(self.lbl_metrology)
        l_dec.addWidget(self.box_post_results)
        self.box_post_results.setVisible(False)

        self.scroll_layout.addWidget(self.sec_decimate)

        # -------------------------------------------------------------
        # 4. SECTION 3: EXPERT MODE (Collapsed by default)
        # -------------------------------------------------------------
        self.sec_expert = CollapsibleSection("SECTION 3: EXPERT MODE — Advanced Controls", expanded=False, parent=self)
        l_exp = self.sec_expert.content_layout

        btn_run_full_pipeline = QtWidgets.QPushButton("Run Full Combined Pipeline", self)
        btn_run_full_pipeline.setObjectName("SuccessButton")
        btn_run_full_pipeline.clicked.connect(self.on_run_full_pipeline)
        l_exp.addWidget(btn_run_full_pipeline)

        # Individual specialist operators
        grp_spec = QtWidgets.QGroupBox("Specialist Subpanel Operators", self)
        l_sp = QtWidgets.QVBoxLayout(grp_spec)

        btn_exp_rep = QtWidgets.QPushButton("1. Execute Repair", self)
        btn_exp_rep.clicked.connect(lambda: self.on_run_conservative_cleanup())
        l_sp.addWidget(btn_exp_rep)

        btn_exp_iw = QtWidgets.QPushButton("2. Remove Internal Walls", self)
        btn_exp_iw.clicked.connect(self.on_remove_internal_walls)
        l_sp.addWidget(btn_exp_iw)

        btn_exp_dis = QtWidgets.QPushButton("3. Execute Dissolve", self)
        btn_exp_dis.clicked.connect(lambda: execute_dissolve(self.active_mesh))
        l_sp.addWidget(btn_exp_dis)

        btn_exp_norm = QtWidgets.QPushButton("4. Execute Normals / Soft Edge", self)
        btn_exp_norm.clicked.connect(lambda: execute_normals(self.active_mesh))
        l_sp.addWidget(btn_exp_norm)

        btn_exp_od = QtWidgets.QPushButton("5. Clean Object Shading Data", self)
        btn_exp_od.clicked.connect(lambda: execute_object_data(self.active_mesh))
        l_sp.addWidget(btn_exp_od)

        l_exp.addWidget(grp_spec)

        # Report Export
        row_rep = QtWidgets.QHBoxLayout()
        btn_exp_json = QtWidgets.QPushButton("Export Report (JSON)", self)
        btn_exp_json.clicked.connect(lambda: self.export_report("JSON"))
        row_rep.addWidget(btn_exp_json)

        btn_exp_txt = QtWidgets.QPushButton("Export Report (TXT)", self)
        btn_exp_txt.clicked.connect(lambda: self.export_report("TXT"))
        row_rep.addWidget(btn_exp_txt)
        l_exp.addLayout(row_rep)

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
            self.lbl_object_name.setText("Object: None selected")
            self.lbl_verts.setText("Vertices: 0")
            self.lbl_edges.setText("Edges: 0")
            self.lbl_faces.setText("Faces: 0")
            self.lbl_tris.setText("Real Tris: 0")
            self.box_restore.setVisible(False)
            return

        self.lbl_object_name.setText(f"Object: {obj}")
        stats = get_mesh_statistics(obj)
        self.active_stats = stats

        if stats.get("valid"):
            self.lbl_verts.setText(f"Vertices: {stats['vertices']:,}")
            self.lbl_edges.setText(f"Edges: {stats['edges']:,}")
            self.lbl_faces.setText(f"Faces: {stats['faces']:,}")
            self.lbl_tris.setText(f"Real Tris: {stats['triangles']:,}")
            self._update_estimation_label()

            # BlendShape alert
            has_bs = stats.get("has_blendshapes", False)
            self.box_blendshape_alert.setVisible(has_bs)

        is_optimized_copy = ("_MF_Optimized" in obj or cmds.attributeQuery("_mf_source_ptr", node=obj, exists=True))
        self.box_restore.setVisible(is_optimized_copy)

    def on_pct_slider_changed(self, val):
        self.lbl_pct_val.setText(f"{val}%")
        self._update_estimation_label()

    def _update_estimation_label(self):
        real_tris = self.active_stats.get("triangles", 0)
        pct = self.slider_pct.value()
        est = max(4, int(real_tris * (1.0 - (pct / 100.0))))
        self.lbl_estimation.setText(f"Estimation: ~{est:,} triangles (-{pct}%)")

    def on_method_changed(self, idx):
        is_collapse = (self.combo_method.currentData() == "COLLAPSE")
        self.w_collapse_goal.setVisible(is_collapse)
        self.w_dissolve_goal.setVisible(not is_collapse)
        self.btn_execute_decimate.setText(
            "Reduce Mesh (Edge Collapse)" if is_collapse else "Simplify Faces (Coplanar Dissolve)"
        )
        profile_key = self.combo_profile.currentData()
        if is_collapse:
            self.lbl_method_guidance.setText("Recommended for curved and organic shapes: contracts edges while preserving volume.")
        else:
            self.lbl_method_guidance.setText("Specialized for CAD and hard-surface: dissolves coplanar edges without altering silhouettes.")

    def on_profile_changed(self):
        p_key = self.combo_profile.currentData()
        p_info = PROFILES.get(p_key, PROFILES["GENERAL"])
        self.lbl_profile_summary.setText(f"{p_info['name']}: {p_info['summary']}")
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
        quads_o = self.chk_quads_only.isChecked()

        diag = evaluate_mesh_diagnosis(
            self.active_mesh,
            self.active_stats,
            profile_id=p_key,
            strict_manifold=strict_m,
            quads_only=quads_o,
            intentional_ids=self.intentional_finding_ids
        )
        self.active_diagnosis = diag

        # Health status
        h = diag["health"]
        status = h["status"]
        if status == "HEALTHY":
            self.lbl_health_status.setText("Health: Geometrically Healthy Mesh")
            self.lbl_health_status.setStyleSheet("font-weight: bold; color: #2ecc71;")
        elif status == "CRITICAL":
            self.lbl_health_status.setText(f"Health: {h['defects_count']} Critical Defect(s)")
            self.lbl_health_status.setStyleSheet("font-weight: bold; color: #e74c3c;")
        else:
            self.lbl_health_status.setText(f"Health: {h['risks_count']} Vigilance Item(s)")
            self.lbl_health_status.setStyleSheet("font-weight: bold; color: #f39c12;")

        self.lbl_counters.setText(f"Defects: {h['defects_count']}  |  Risks: {h['risks_count']}  |  Observations: {h['observations_count']}")

        # Clear old recommendations UI
        while self.l_recs.count() > 0:
            item = self.l_recs.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Populate Category 1: Conservative
        rec_groups = diag.get("recommendation_groups", {})
        c1_list = rec_groups.get("conservative", [])
        if c1_list:
            box_c1 = QtWidgets.QFrame(self)
            box_c1.setObjectName("CardBox")
            l_b1 = QtWidgets.QVBoxLayout(box_c1)
            l_b1.addWidget(QtWidgets.QLabel("1. Recommended Conservative Repairs (Safe):", self))
            for item in c1_list:
                l_b1.addWidget(QtWidgets.QLabel(f"• {item['title']}: {item['problem']}", self))
                btn_run = QtWidgets.QPushButton(item["operator_text"], self)
                btn_run.setObjectName("SuccessButton")
                btn_run.clicked.connect(self.on_run_conservative_cleanup)
                l_b1.addWidget(btn_run)
            self.l_recs.addWidget(box_c1)

        # Populate Category 2: Targeted
        c2_list = rec_groups.get("targeted", [])
        if c2_list:
            box_c2 = QtWidgets.QFrame(self)
            box_c2.setObjectName("CardBox")
            l_b2 = QtWidgets.QVBoxLayout(box_c2)
            l_b2.addWidget(QtWidgets.QLabel("2. Targeted Profile Optimizations:", self))
            for item in c2_list:
                l_b2.addWidget(QtWidgets.QLabel(f"• {item['title']}: {item['problem']}", self))
                btn_op = QtWidgets.QPushButton(item["operator_text"], self)
                if item.get("operator") == "cut_ngons":
                    btn_op.clicked.connect(self.on_cut_ngons)
                elif item.get("operator") == "quadrangulate":
                    btn_op.clicked.connect(self.on_quadrangulate)
                l_b2.addWidget(btn_op)
            self.l_recs.addWidget(box_c2)

        # Populate Category 3: Risky
        c3_list = rec_groups.get("risky", [])
        if c3_list:
            box_c3 = QtWidgets.QFrame(self)
            box_c3.setObjectName("AlertBox")
            l_b3 = QtWidgets.QVBoxLayout(box_c3)
            l_b3.addWidget(QtWidgets.QLabel("3. Risky Actions (Manual Review Required):", self))
            for item in c3_list:
                l_b3.addWidget(QtWidgets.QLabel(f"⚠️ {item['title']}: {item['problem']}", self))
                btn_iw = QtWidgets.QPushButton("Remove Internal Walls", self)
                btn_iw.clicked.connect(self.on_remove_internal_walls)
                l_b3.addWidget(btn_iw)
            self.l_recs.addWidget(box_c3)

    def on_toggle_wireframe(self):
        toggle_wireframe_display()

    def on_clear_inspection(self):
        clear_inspection_view()

    def on_run_conservative_cleanup(self):
        if not self.active_mesh:
            return
        res = execute_conservative_cleanup(self.active_mesh)
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

        if method == "COLLAPSE":
            pct = float(self.slider_pct.value())
            res = execute_simplification(
                target_obj,
                mode="PERCENTAGE",
                percentage=pct,
                preserve_boundaries=self.chk_pres_boundaries.isChecked(),
                preserve_sharp=self.chk_pres_sharp.isChecked(),
                preserve_seams=self.chk_pres_seams.isChecked()
            )
        else:
            ang = self.spin_dissolve_angle.value()
            res = execute_dissolve(
                target_obj,
                dissolve_angle=ang,
                preserve_sharp=self.chk_pres_sharp.isChecked(),
                preserve_seams=self.chk_pres_seams.isChecked()
            )

        t_after = cmds.polyEvaluate(target_obj, triangle=True)
        f_after = cmds.polyEvaluate(target_obj, face=True)
        v_after = cmds.polyEvaluate(target_obj, vertex=True)

        # Show post results grid
        pct_red = round(((t_before - t_after) / float(t_before) * 100.0), 1) if t_before > 0 else 0.0
        self.lbl_res_tris.setText(f"Triangles: {t_before:,} -> {t_after:,} (-{pct_red}%)")
        self.lbl_res_faces.setText(f"Faces: {f_before:,} -> {f_after:,}")
        self.lbl_res_verts.setText(f"Vertices: {v_before:,} -> {v_after:,}")

        # Metrology
        val = validate_mesh_surface(source_obj, target_obj)
        if val.get("measured"):
            self.lbl_metrology.setText(f"Max Hausdorff: {val['max_hausdorff_m']}m  |  Mean Dist: {val['mean_deviation_m']}m")
        else:
            self.lbl_metrology.setText("Geometric Deviation: Not measured")

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
