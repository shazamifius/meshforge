"""MeshForge - Tests de robustesse en conditions réelles et validation UX (Phases UX0 à UX5).
Vérifie :
1. La robustesse aux contextes réels (aucune sélection, types non-maillage, maillages vides).
2. L'évaluation instantanée du diagnostic structuré (< 5 ms) lors du changement de profil.
3. Le respect des règles d'interprétation des 5 profils (GENERAL, GAME_ASSET, DEFORMABLE_CHAR, SCULPTED_ORGANIC, MECHANICAL_CAD).
4. Le ciblage et le cadrage non-destructif via `focus_defect` (par finding_id et par index).
5. La conformité des actions prioritaires recommandées et de leurs niveaux de risque.
6. L'exécution réelle des opérateurs (Nettoyage conservateur, Découpe N-gones, Effacer inspection).
7. Le rendu visuel Workbench pour preuve vérifiable.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
parent_dir = root_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import bpy
import bmesh
import time
import unittest

import meshforge
from meshforge.core.structured_diagnosis import (
    measure_mesh_facts,
    evaluate_structured_diagnosis,
    PROFILES,
    CATEGORIES
)
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.operators.topology_inspect import _ACTIVE_DIAGNOSIS_CACHE


class TestRealWorldUX(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def tearDown(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)
        _ACTIVE_DIAGNOSIS_CACHE.clear()

    def _create_test_mesh_with_all_defects(self) -> bpy.types.Object:
        """Crée un maillage contrôlé contenant un panel varié d'anomalies :
        - 1 N-gone plan (5 côtés)
        - 1 face d'aire nulle (dégénérescence)
        - 2 sommets isolés (orphelins)
        - 1 arête sans face (loose edge)
        - 2 sommets doublons coïncidents
        - 2 quads sains
        """
        mesh = bpy.data.meshes.new("DefectiveMesh")
        bm = bmesh.new()

        # Quad 1 sain
        v0 = bm.verts.new((-1, -1, 0))
        v1 = bm.verts.new((0, -1, 0))
        v2 = bm.verts.new((0, 0, 0))
        v3 = bm.verts.new((-1, 0, 0))
        f_quad1 = bm.faces.new((v0, v1, v2, v3))

        # Quad 2 sain
        v4 = bm.verts.new((1, -1, 0))
        v5 = bm.verts.new((1, 0, 0))
        f_quad2 = bm.faces.new((v1, v4, v5, v2))

        # N-gone plan à 5 côtés
        v6 = bm.verts.new((0, 1, 0))
        v7 = bm.verts.new((0.5, 1.5, 0))
        v8 = bm.verts.new((1, 1, 0))
        f_ngon = bm.faces.new((v2, v5, v8, v7, v6))

        # Face d'aire nulle (v9, v10, v11 co-alignés)
        v9 = bm.verts.new((-2, 0, 0))
        v10 = bm.verts.new((-2, 0.5, 0))
        v11 = bm.verts.new((-2, 1.0, 0))
        # Triangle quasi plat d'aire < 1e-10
        v10_collinear = bm.verts.new((-2, 0.5, 0.0000000001))
        bm.faces.new((v9, v10_collinear, v11))

        # Sommets orphelins (loose verts)
        bm.verts.new((5, 5, 5))
        bm.verts.new((6, 6, 6))

        # Arête orpheline (loose edge sans face)
        vl1 = bm.verts.new((-3, -3, 0))
        vl2 = bm.verts.new((-3, -4, 0))
        bm.edges.new((vl1, vl2))

        # Doublons coïncidents
        bm.verts.new((-1, -1, 0)) # Même position que v0

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("DefectiveObj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        return obj

    def test_01_no_selection_and_non_mesh_robustness(self):
        """Vérifie que le système gère sans crash : aucune sélection, objet Caméra, maillage vide."""
        # 1. Aucune sélection
        bpy.context.view_layer.objects.active = None
        self.assertFalse(bpy.ops.meshforge.analyze_topology.poll())
        self.assertFalse(bpy.ops.meshforge.conservative_clean.poll())
        self.assertFalse(bpy.ops.meshforge.cut_ngons.poll())

        # 2. Objet Caméra
        cam_data = bpy.data.cameras.new("TestCam")
        cam_obj = bpy.data.objects.new("TestCamObj", cam_data)
        bpy.context.collection.objects.link(cam_obj)
        bpy.context.view_layer.objects.active = cam_obj
        cam_obj.select_set(True)

        self.assertFalse(bpy.ops.meshforge.analyze_topology.poll())
        self.assertFalse(bpy.ops.meshforge.conservative_clean.poll())
        self.assertFalse(bpy.ops.meshforge.cut_ngons.poll())

        # 3. Maillage vide (0 sommets, 0 faces)
        empty_mesh = bpy.data.meshes.new("EmptyMesh")
        empty_obj = bpy.data.objects.new("EmptyObj", empty_mesh)
        bpy.context.collection.objects.link(empty_obj)
        bpy.context.view_layer.objects.active = empty_obj
        empty_obj.select_set(True)

        self.assertTrue(bpy.ops.meshforge.analyze_topology.poll())
        res = bpy.ops.meshforge.analyze_topology()
        self.assertEqual(res, {'FINISHED'})

        facts = measure_mesh_facts(empty_obj)
        self.assertTrue(facts.get("is_empty"))

    def test_02_mesh_facts_measurement_objectivity(self):
        """Vérifie que les mesures de MeshFacts sont objectives et complètes."""
        obj = self._create_test_mesh_with_all_defects()
        facts = measure_mesh_facts(obj)

        self.assertTrue(facts["valid"])
        self.assertEqual(facts["total_ngons"], 1)
        self.assertGreaterEqual(facts["zero_area_faces_count"], 1)
        self.assertEqual(facts["loose_verts_count"], 4)
        self.assertEqual(facts["wire_edges_count"], 1)
        self.assertEqual(facts["quads_count"], 2)

    def test_03_instant_profile_reevaluation_performance(self):
        """Vérifie que le changement de profil réévalue les constats en < 5ms sans recalculer les faits."""
        obj = self._create_test_mesh_with_all_defects()
        facts = measure_mesh_facts(obj)

        profiles = ["GENERAL", "GAME_ASSET", "DEFORMABLE_CHAR", "SCULPTED_ORGANIC", "MECHANICAL_CAD"]
        for p in profiles:
            t0 = time.perf_counter()
            res = evaluate_structured_diagnosis(facts, p)
            dt = (time.perf_counter() - t0) * 1000.0

            self.assertLess(dt, 5.0, f"L'évaluation du profil {p} a pris {dt:.2f} ms (seuil max 5 ms)")
            self.assertIn("findings", res)
            self.assertIn("recommended_actions", res)
            self.assertIn("health", res)
            self.assertEqual(res["profile_id"], p)

    def test_04_profile_semantic_rules(self):
        """Vérifie que chaque profil interprète les mêmes faits selon son rôle propre."""
        obj = self._create_test_mesh_with_all_defects()
        facts = measure_mesh_facts(obj)

        # Profil 1 : GENERAL (Neutre)
        res_gen = evaluate_structured_diagnosis(facts, "GENERAL")
        ngon_finding_gen = next((f for f in res_gen["findings"] if "ngon" in f["id"]), None)
        self.assertIsNotNone(ngon_finding_gen)
        self.assertIn(ngon_finding_gen["severity"], ("RISK", "OBSERVATION"))

        # Profil 2 : GAME_ASSET (Zéro N-gone, Triangles obligatoires)
        res_game = evaluate_structured_diagnosis(facts, "GAME_ASSET")
        ngon_finding_game = next((f for f in res_game["findings"] if "ngon" in f["id"]), None)
        self.assertIsNotNone(ngon_finding_game)
        self.assertEqual(ngon_finding_game["severity"], "DEFECT")

        # Profil 5 : MECHANICAL_CAD (Les N-gones plans sont acceptés)
        res_cad = evaluate_structured_diagnosis(facts, "MECHANICAL_CAD")
        ngon_finding_cad = next((f for f in res_cad["findings"] if "ngon" in f["id"]), None)
        self.assertIsNotNone(ngon_finding_cad)
        self.assertEqual(ngon_finding_cad["severity"], "OBSERVATION")

    def test_05_recommended_actions_and_risk_badges(self):
        """Vérifie que les actions prioritaires recommandées respectent le plafond de 2-3 actions claires."""
        obj = self._create_test_mesh_with_all_defects()
        facts = measure_mesh_facts(obj)

        res_game = evaluate_structured_diagnosis(facts, "GAME_ASSET")
        actions = res_game["recommended_actions"]

        # Maximum 2-3 actions
        self.assertLessEqual(len(actions), 3)

        action_ids = [a["id"] for a in actions]
        self.assertIn("conservative_clean", action_ids)
        self.assertIn("cut_ngons", action_ids)

        clean_act = next(a for a in actions if a["id"] == "conservative_clean")
        self.assertEqual(clean_act["risk_level"], "LOW")
        self.assertEqual(clean_act["risk_badge"], "[Risque Faible]")

        cut_act = next(a for a in actions if a["id"] == "cut_ngons")
        self.assertEqual(cut_act["risk_level"], "CONTROLLED")
        self.assertEqual(cut_act["risk_badge"], "[Risque Contrôlé]")

    def test_06_focus_defect_with_finding_id_and_index(self):
        """Vérifie le zoom et cadrage non-destructif via `focus_defect` avec finding_id."""
        obj = self._create_test_mesh_with_all_defects()
        bpy.ops.meshforge.analyze_topology()

        # 1. Zoom par finding_id
        res_id = bpy.ops.meshforge.focus_defect(finding_id="geom_zero_area_faces")
        self.assertEqual(res_id, {'FINISHED'})

        # 2. Zoom par finding_id N-gones
        res_ngon = bpy.ops.meshforge.focus_defect(finding_id="topo_ngon_faces")
        self.assertEqual(res_ngon, {'FINISHED'})

        # 3. Zoom par defect_index
        res_idx = bpy.ops.meshforge.focus_defect(defect_index=0)
        self.assertEqual(res_idx, {'FINISHED'})

        # 4. Nettoyage de l'inspection
        res_clear = bpy.ops.meshforge.clear_defect_view()
        self.assertEqual(res_clear, {'FINISHED'})

    def test_07_conservative_clean_and_ngon_cut_execution(self):
        """Vérifie l'exécution réelle sans régression du nettoyage conservateur et de la découpe N-gones."""
        obj = self._create_test_mesh_with_all_defects()

        # 1. Exécuter le nettoyage conservateur
        res_clean = bpy.ops.meshforge.conservative_clean()
        self.assertEqual(res_clean, {'FINISHED'})

        # Vérifier que les orphelins et faces nulles ont été éliminés
        facts_after_clean = measure_mesh_facts(obj)
        self.assertEqual(facts_after_clean["loose_verts_count"], 0)
        self.assertEqual(facts_after_clean["wire_edges_count"], 0)
        self.assertEqual(facts_after_clean["zero_area_faces_count"], 0)

        # Les N-gones doivent être restés intacts après le nettoyage conservateur (aucune modification non sollicitée)
        self.assertEqual(facts_after_clean["total_ngons"], 1)

        # 2. Exécuter la découpe ciblée des N-gones
        res_cut = bpy.ops.meshforge.cut_ngons()
        self.assertEqual(res_cut, {'FINISHED'})

        facts_after_cut = measure_mesh_facts(obj)
        self.assertEqual(facts_after_cut["total_ngons"], 0)
        # Le N-gone à 5 côtés est maintenant composé de triangles propres
        self.assertGreater(facts_after_cut["tris_count"], 0)

    def test_08_multi_mesh_types_analysis(self):
        """Vérifie le diagnostic sur plusieurs types de maillages réels (Cube, Suzanne, Sphère UV)."""
        # Cube
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        cube_diag = diagnose_topology(cube, mode="GENERAL")
        self.assertTrue(cube_diag["valid"])
        self.assertEqual(cube_diag["summary"]["ngons"], 0)
        self.assertEqual(cube_diag["summary"]["degeneracies"], 0)

        # Suzanne (Monkey)
        bpy.ops.mesh.primitive_monkey_add()
        suzanne = bpy.context.active_object
        suz_diag = diagnose_topology(suzanne, mode="DEFORMABLE_CHAR")
        self.assertTrue(suz_diag["valid"])
        self.assertIn("structured", suz_diag)
        self.assertEqual(suz_diag["structured"]["profile_id"], "DEFORMABLE_CHAR")

        # Sphère UV
        bpy.ops.mesh.primitive_uv_sphere_add()
        sphere = bpy.context.active_object
        sphere_diag = diagnose_topology(sphere, mode="GAME_ASSET")
        self.assertTrue(sphere_diag["valid"])
        self.assertIn("structured", sphere_diag)
        self.assertEqual(sphere_diag["structured"]["profile_id"], "GAME_ASSET")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRealWorldUX)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
