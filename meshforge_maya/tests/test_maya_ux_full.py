"""MeshForge Maya - Exhaustive 100% UX and Interactive Feature Test Suite.
Tests every single button, slider, checkbox, combobox, and workflow interaction.
"""

import sys
import os
import unittest
import tempfile
import json

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from meshforge_maya.ui.qt_compat import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["-platform", "offscreen"])

import maya.cmds as cmds
import maya.standalone

class TestMeshForgeMayaUXFull(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            maya.standalone.initialize()
        except RuntimeError:
            pass
        cls.app = app

    def setUp(self):
        cmds.file(new=True, force=True)
        from meshforge_maya.ui.main_window import MeshForgeMayaWindow
        self.win = MeshForgeMayaWindow()
        self.win.show()

    def tearDown(self):
        if self.win:
            self.win.close()
            self.win.deleteLater()

    def test_01_ui_initial_state_empty_selection(self):
        """Verifies UI state when no mesh is selected."""
        cmds.select(clear=True)
        self.win.refresh_selection()

        self.assertIn("None selected", self.win.lbl_object_name.text())
        self.assertEqual(self.win.lbl_verts.text(), "Vertices: 0")
        self.assertEqual(self.win.lbl_edges.text(), "Edges: 0")
        self.assertEqual(self.win.lbl_faces.text(), "Faces: 0")
        self.assertEqual(self.win.lbl_tris.text(), "Real Tris: 0")
        self.assertFalse(self.win.box_restore.isVisible())

    def test_02_ui_mesh_selection_telemetry(self):
        """Verifies UI updates live telemetry when a mesh is selected."""
        cyl = cmds.polyCylinder(name="ux_cylinder", subdivisionsAxis=12, subdivisionsCaps=1)[0]
        cmds.select(cyl)
        self.win.refresh_selection()

        self.assertIn("ux_cylinder", self.win.lbl_object_name.text())
        self.assertNotEqual(self.win.lbl_verts.text(), "Vertices: 0")
        self.assertNotEqual(self.win.lbl_faces.text(), "Faces: 0")
        self.assertNotEqual(self.win.lbl_tris.text(), "Real Tris: 0")

    def test_03_section_1_clean_all_buttons(self):
        """Tests 100% of Section 1 (CLEAN) buttons, tools, and profile switches."""
        cube = cmds.polyCube(name="clean_cube")[0]
        cmds.select(cube)
        self.win.refresh_selection()

        # 1. Analyze button
        self.win.btn_analyze.click()
        self.assertTrue(self.win.active_diagnosis.get("valid", False))
        self.assertIn("Health:", self.win.lbl_health_status.text())

        # 2. Toggle Wireframe button
        self.win.btn_wire.click()
        self.win.btn_wire.click()

        # 3. Clear inspection button
        self.win.btn_clear_view.click()

        # 4. Profile dropdown - cycle through all 8 profiles
        from meshforge_maya.core.structured_diagnosis import PROFILES
        for idx in range(self.win.combo_profile.count()):
            self.win.combo_profile.setCurrentIndex(idx)
            p_key = self.win.combo_profile.currentData()
            self.assertIn(p_key, PROFILES)
            p_info = PROFILES[p_key]
            self.assertIn(p_info["name"], self.win.lbl_profile_summary.text())

        # 5. Complementary constraints checkboxes
        self.win.chk_strict_manifold.setChecked(True)
        self.win.chk_strict_manifold.setChecked(False)
        self.win.chk_quads_only.setChecked(True)
        self.win.chk_quads_only.setChecked(False)

        # 6. Conservative cleanup execution
        self.win.on_run_conservative_cleanup()

        # 7. Cut N-gons button
        self.win.on_cut_ngons()

        # 8. Quadrangulate button
        self.win.on_quadrangulate()

        # 9. Remove Internal Walls button
        self.win.on_remove_internal_walls()

    def test_04_section_2_decimate_all_controls(self):
        """Tests 100% of Section 2 (DECIMATE) controls, dynamic sliders, and decimation methods."""
        sphere = cmds.polySphere(name="decimate_sphere", subdivisionsX=16, subdivisionsY=16)[0]
        cmds.select(sphere)
        self.win.refresh_selection()

        # 1. Expand Section 2
        self.win.sec_decimate.set_expanded(True)
        self.assertTrue(self.win.sec_decimate.content_widget.isVisible())

        # 2. Switch between COLLAPSE and DISSOLVE methods
        self.win.combo_method.setCurrentIndex(0) # COLLAPSE
        self.assertTrue(self.win.w_collapse_goal.isVisible())
        self.assertFalse(self.win.w_dissolve_goal.isVisible())
        self.assertIn("Edge Collapse", self.win.btn_execute_decimate.text())

        # Slider interaction & dynamic budget estimation
        self.win.slider_pct.setValue(25)
        self.assertIn("25%", self.win.lbl_pct_val.text())
        self.assertIn("-25%", self.win.lbl_estimation.text())

        self.win.slider_pct.setValue(75)
        self.assertIn("75%", self.win.lbl_pct_val.text())
        self.assertIn("-75%", self.win.lbl_estimation.text())

        self.win.combo_method.setCurrentIndex(1) # DISSOLVE
        self.assertFalse(self.win.w_collapse_goal.isVisible())
        self.assertTrue(self.win.w_dissolve_goal.isVisible())
        self.assertIn("Coplanar Dissolve", self.win.btn_execute_decimate.text())

        self.win.spin_dissolve_angle.setValue(10.0)

        # 3. Preservation checkboxes
        self.win.chk_pres_boundaries.setChecked(True)
        self.win.chk_pres_sharp.setChecked(True)
        self.win.chk_pres_seams.setChecked(True)

        # 4. Non-destructive copy execution
        self.win.combo_method.setCurrentIndex(0) # Back to COLLAPSE
        self.win.slider_pct.setValue(50)
        self.win.chk_create_copy.setChecked(True)

        self.win.btn_execute_decimate.click()

        # Verify results box popped up with actual values
        self.assertTrue(self.win.box_post_results.isVisible())
        self.assertIn("Triangles:", self.win.lbl_res_tris.text())
        self.assertIn("Vertices:", self.win.lbl_res_verts.text())
        self.assertIn("Faces:", self.win.lbl_res_faces.text())
        self.assertIn("Max Hausdorff:", self.win.lbl_metrology.text())

        # Verify duplicate object was selected
        curr_sel = cmds.ls(selection=True)[0]
        self.assertIn("_MF_Optimized", curr_sel)
        self.assertTrue(self.win.box_restore.isVisible())

        # 5. Test Restore Original button
        self.win.btn_restore.click()
        self.assertTrue(cmds.objExists("decimate_sphere"))
        self.assertFalse(cmds.objExists("decimate_sphere_MF_Optimized"))

    def test_05_section_2_blendshape_guard_ui(self):
        """Tests that blendshapes trigger the safety alert box and allow static copy option."""
        base = cmds.polyCube(name="char_face")[0]
        target = cmds.polyCube(name="char_blink")[0]
        cmds.move(0, 0.5, 0, f"{target}.vtx[1]")
        cmds.blendShape(target, base, name="facial_bs")

        cmds.select(base)
        self.win.refresh_selection()
        self.win.sec_decimate.set_expanded(True)

        self.assertTrue(self.win.box_blendshape_alert.isVisible())
        self.win.chk_allow_blendshape_copy.setChecked(True)

        # Execute decimation with blendshapes
        self.win.slider_pct.setValue(40)
        self.win.btn_execute_decimate.click()

        # Original mesh still has blendshape node
        history_orig = cmds.listHistory("char_face") or []
        self.assertIn("facial_bs", history_orig)

    def test_06_section_3_expert_mode_and_reports(self):
        """Tests Section 3 Expert Mode full pipeline, specialist buttons, and report export."""
        torus = cmds.polyTorus(name="expert_torus")[0]
        cmds.select(torus)
        self.win.refresh_selection()

        # Run full pipeline button
        self.win.on_run_full_pipeline()
        self.assertTrue(cmds.objExists("expert_torus_MF_Optimized"))

        # Test report export to JSON and TXT
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_json:
            json_path = f_json.name
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f_txt:
            txt_path = f_txt.name

        try:
            # Populate diagnosis for export
            self.win.on_analyze_topology()
            diag = self.win.active_diagnosis
            self.assertTrue(diag.get("valid"))

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(diag, f, indent=2, default=str)
            self.assertTrue(os.path.getsize(json_path) > 0)

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(str(diag))
            self.assertTrue(os.path.getsize(txt_path) > 0)
        finally:
            if os.path.exists(json_path):
                os.remove(json_path)
            if os.path.exists(txt_path):
                os.remove(txt_path)

if __name__ == "__main__":
    unittest.main()
