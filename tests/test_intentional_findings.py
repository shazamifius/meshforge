"""Tests unitaires pour la Partie C : Anomalies sans correction, étapes manuelles et marquage intentionnel."""
import unittest
import bpy
import bmesh
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.structured_diagnosis import measure_mesh_facts, evaluate_structured_diagnosis
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.ui.panel import VIEW3D_PT_meshforge_main


class MockLayout:
    def __init__(self):
        self.alert = False
        self.active = True
        self.scale_y = 1.0

    def box(self):
        return MockLayout()

    def row(self, align=False):
        return MockLayout()

    def column(self, align=False):
        return MockLayout()

    def grid_flow(self, **kwargs):
        return MockLayout()

    def label(self, text="", icon='NONE'):
        pass

    def prop(self, data, prop_name, text="", icon='NONE', expand=False, emboss=True):
        pass

    def operator(self, op_name, text="", icon='NONE', **kwargs):
        class MockOp:
            def __setattr__(self, k, v): pass
        return MockOp()

    def separator(self):
        pass


class MockPanel:
    def __init__(self):
        self.layout = MockLayout()


class TestIntentionalFindingsAndManualSteps(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_01_manual_correction_steps_available(self):
        """Vérifie que les anomalies non automatisables fournissent des étapes manuelles claires."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        
        facts = measure_mesh_facts(plane)
        eval_res = evaluate_structured_diagnosis(facts, profile_id="EXPORT_PREP")
        
        findings = {f["id"]: f for f in eval_res["findings"]}
        self.assertIn("topo_open_boundary", findings)
        open_f = findings["topo_open_boundary"]
        
        manual_steps = open_f.get("manual_correction_steps", [])
        self.assertGreater(len(manual_steps), 0)
        self.assertTrue(any("Édition" in s or "Tab" in s for s in manual_steps))
        self.assertTrue(any("F" in s or "Grid Fill" in s for s in manual_steps))

    def test_02_mark_intentional_operator_and_severity_downgrade(self):
        """Vérifie le marquage comme intentionnel, la diminution des défauts et le statut de santé."""
        bpy.ops.mesh.primitive_plane_add()
        obj = bpy.context.active_object
        bpy.context.view_layer.objects.active = obj
        bpy.context.scene.meshforge_settings.asset_target_mode = "EXPORT_PREP"

        # 1. Analyse initiale
        diag = diagnose_topology(obj, mode="EXPORT_PREP")
        findings_before = {f["id"]: f for f in diag["findings"]}
        self.assertIn("topo_open_boundary", findings_before)
        self.assertEqual(findings_before["topo_open_boundary"]["severity"], "DEFECT")
        self.assertEqual(diag["structured"]["health"]["status"], "CRITICAL")
        self.assertGreaterEqual(diag["structured"]["summary_counts"]["defects"], 1)

        # 2. Marquer topo_open_boundary comme intentionnel
        res = bpy.ops.meshforge.mark_intentional(finding_id="topo_open_boundary", unmark=False)
        self.assertEqual(res, {'FINISHED'})
        self.assertIn("topo_open_boundary", list(obj.get("_mf_intentional_findings", [])))

        # 3. Ré-analyse
        diag_after = diagnose_topology(obj, mode="EXPORT_PREP")
        findings_after = {f["id"]: f for f in diag_after["findings"]}
        
        f_open = findings_after["topo_open_boundary"]
        self.assertTrue(f_open.get("is_intentional"))
        self.assertEqual(f_open["severity"], "OBSERVATION")
        self.assertIn("[Intentionnel]", f_open["name"])
        
        # Le nombre de défauts a diminué car l'ouverture est maintenant intentionnelle
        self.assertEqual(diag_after["structured"]["summary_counts"]["defects"], 0)
        self.assertNotEqual(diag_after["structured"]["health"]["status"], "CRITICAL")

        # 4. Annuler le marquage intentionnel
        res_unm = bpy.ops.meshforge.mark_intentional(finding_id="topo_open_boundary", unmark=True)
        self.assertEqual(res_unm, {'FINISHED'})
        self.assertNotIn("topo_open_boundary", list(obj.get("_mf_intentional_findings", [])))

        # Vérifier retour au statut initial
        diag_revert = diagnose_topology(obj, mode="EXPORT_PREP")
        findings_revert = {f["id"]: f for f in diag_revert["findings"]}
        self.assertFalse(findings_revert["topo_open_boundary"].get("is_intentional", False))
        self.assertEqual(findings_revert["topo_open_boundary"]["severity"], "DEFECT")

    def test_03_intentional_moves_from_risky_to_observations(self):
        """Vérifie qu'une anomalie risquée (ex: T-junction) passe en Catégorie 4 quand validée intentionnelle."""
        # Créer une véritable jonction en T (arête partagée par 3 faces)
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(plane.data)
        bm.edges.ensure_lookup_table()
        e = bm.edges[0]
        v_top = bm.verts.new((0.0, 0.0, 1.0))
        v_bot = bm.verts.new((0.0, 0.0, -1.0))
        bm.faces.new([e.verts[0], e.verts[1], v_top])
        bm.faces.new([e.verts[0], e.verts[1], v_bot])
        bm.to_mesh(plane.data)
        bm.free()

        bpy.context.view_layer.objects.active = plane
        bpy.context.scene.meshforge_settings.asset_target_mode = "MECHANICAL_CAD"

        # Diagnostic initial
        diag = diagnose_topology(plane, mode="MECHANICAL_CAD")
        rec_g = diag["structured"]["recommendation_groups"]
        risky_ids = [c["id"] for c in rec_g["risky"]]
        self.assertIn("rec_risky_t_junctions", risky_ids)

        # Marquer topo_t_junctions comme intentionnel
        bpy.ops.meshforge.mark_intentional(finding_id="topo_t_junctions", unmark=False)

        diag_after = diagnose_topology(plane, mode="MECHANICAL_CAD")
        rec_g_after = diag_after["structured"]["recommendation_groups"]
        risky_ids_after = [c["id"] for c in rec_g_after["risky"]]
        obs_ids_after = [c["id"] for c in rec_g_after["observations"]]

        # Exclu de Catégorie 3 (risky) et présent dans Catégorie 4 (observations)
        self.assertNotIn("rec_risky_t_junctions", risky_ids_after)
        self.assertTrue(any("t_junctions" in o_id for o_id in obs_ids_after))

    def test_04_ui_draw_with_intentional_and_manual_steps(self):
        """Vérifie le rendu UI sans erreur du panneau avec éléments intentionnels et étapes manuelles."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        bpy.context.view_layer.objects.active = cube
        
        # Marquer un constat intentionnel
        cube["_mf_intentional_findings"] = ["topo_open_boundary", "topo_ngons_ambiguous"]
        bpy.ops.meshforge.analyze_topology()

        panel = MockPanel()
        # Ne doit lever aucune exception
        VIEW3D_PT_meshforge_main.draw(panel, bpy.context)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIntentionalFindingsAndManualSteps)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
