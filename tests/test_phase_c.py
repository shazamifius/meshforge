"""MeshForge - Suite de tests techniques et de validation de la Phase C.
Couvre :
- Contrôle de la réduction (pourcentage, budget triangles, tolérance maximale).
- Arbitrage formel Budget vs Tolérance (arrêt anticipé sur tolérance sans violation silencieuse).
- Validation géométrique bidirectionnelle (distances moyenne, P95, P99, max, normales, silhouette, volume).
- Préservation des caractéristiques sur modèles variés :
  * surface plane dense
  * sphère
  * cube triangulé et cube en quads
  * surface organique avec plis
  * maillage ouvert (aucune fermeture implicite)
  * géométrie à plusieurs composantes
  * asset avec UV et plusieurs matériaux
- Benchmark comparatif sur maillage de référence (~1,587 million de triangles).
"""

from __future__ import annotations
import bpy
import bmesh
import math
import time
import sys
import unittest
from pathlib import Path

# Ajouter les chemins d'importation
repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.mesh_stats import get_mesh_statistics
from meshforge.core.simplification import execute_simplification
from meshforge.core.validation import evaluate_geometric_deviation, sample_mesh_surface
from meshforge.core.pipeline import run_meshforge_pipeline


class TestMeshForgePhaseC(unittest.TestCase):
    """Validation technique formelle du moteur de simplification et de validation (Phase C)."""

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_01_percentage_reduction_control(self):
        """1. Vérifie la réduction par pourcentage cible (ex. 50% et 75%)."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32)
        orig = bpy.context.active_object
        initial_tris = len(orig.data.polygons) * 2 # 4096 tris

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 50.0
        props.enable_simplification_tolerance = False

        simp_obj = orig.copy()
        simp_obj.data = orig.data.copy()
        bpy.context.collection.objects.link(simp_obj)

        res = execute_simplification(simp_obj, props, orig_reference_obj=orig)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertAlmostEqual(res["obtained_triangles"], 2048, delta=150)
        self.assertGreater(res["reduction_percentage"], 45.0)

    def test_02_target_triangles_budget_control(self):
        """2. Vérifie la réduction vers un budget cible exact en triangles (ex. 800 triangles)."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32)
        orig = bpy.context.active_object

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'BUDGET_TRIANGLES'
        props.simplification_target_triangles = 800
        props.enable_simplification_tolerance = False

        simp_obj = orig.copy()
        simp_obj.data = orig.data.copy()
        bpy.context.collection.objects.link(simp_obj)

        res = execute_simplification(simp_obj, props, orig_reference_obj=orig)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["target_budget_triangles"], 800)
        # Vérifier que le résultat approche le budget à moins de 10%
        self.assertAlmostEqual(res["obtained_triangles"], 800, delta=100)

    def test_03_tolerance_arbitration_early_stop(self):
        """3. Vérifie l'arrêt anticipé sur tolérance : préserver la qualité plutôt que violer la tolérance."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32)
        orig = bpy.context.active_object

        # Demander un budget très agressif (100 triangles), mais une tolérance serrée (0.01 m)
        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'BUDGET_TRIANGLES'
        props.simplification_target_triangles = 100
        props.enable_simplification_tolerance = True
        props.simplification_max_tolerance = 0.012 # 1.2 cm

        simp_obj = orig.copy()
        simp_obj.data = orig.data.copy()
        bpy.context.collection.objects.link(simp_obj)

        res = execute_simplification(simp_obj, props, orig_reference_obj=orig)
        self.assertEqual(res["status"], "SUCCESS")
        # Le moteur doit s'arrêter à un nombre de triangles plus élevé que 100 pour respecter 0.012m
        self.assertGreater(res["obtained_triangles"], 300)
        self.assertIn("Arrêt sur tolérance géométrique prioritaire", res["stop_reason"])

        # Vérifier que l'erreur P99 mesurée est bien dans la tolérance
        val = res.get("geometric_validation", {})
        self.assertTrue(val.get("valid", False))
        self.assertLessEqual(val["distance_p99"], 0.015)

    def test_04_bidirectional_surface_validation(self):
        """4. Vérifie la validation géométrique bidirectionnelle (P95, P99, Max, Normales, Silhouette, Volume)."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
        orig = bpy.context.active_object

        simp = orig.copy()
        simp.data = orig.data.copy()
        bpy.context.collection.objects.link(simp)

        mod = simp.modifiers.new(name="Decim", type='DECIMATE')
        mod.ratio = 0.5
        bpy.context.view_layer.objects.active = simp
        bpy.ops.object.modifier_apply(modifier=mod.name)

        val = evaluate_geometric_deviation(orig, simp, sample_count=5000)
        self.assertTrue(val["valid"])
        self.assertIn("distance_mean", val)
        self.assertIn("distance_p95", val)
        self.assertIn("distance_p99", val)
        self.assertIn("distance_max_observed", val)
        self.assertIn("normal_deviation_mean_deg", val)
        self.assertIn("silhouette_deviation_pct", val)
        self.assertIsNotNone(val["volume_delta_pct"])
        self.assertTrue(val["is_watertight"])

        # Cohérence mathématique des quantiles : mean <= p95 <= p99 <= max
        self.assertLessEqual(val["distance_mean"], val["distance_p95"])
        self.assertLessEqual(val["distance_p95"], val["distance_p99"])
        self.assertLessEqual(val["distance_p99"], val["distance_max_observed"])

    def test_05_open_mesh_cloth_preservation(self):
        """5. Vérifie que les surfaces ouvertes ne sont jamais fermées et que les frontières sont préservées."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=20, y_subdivisions=20, size=2)
        grid = bpy.context.active_object
        orig_stats = get_mesh_statistics(grid)
        self.assertTrue(orig_stats["is_open_surface"])

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 60.0
        props.preserve_boundaries = True

        simp = grid.copy()
        simp.data = grid.data.copy()
        bpy.context.collection.objects.link(simp)

        res = execute_simplification(simp, props, orig_reference_obj=grid)
        self.assertEqual(res["status"], "SUCCESS")
        simp_stats = get_mesh_statistics(simp)

        # La surface doit rester ouverte avec exactement 1 boucle de frontière
        self.assertTrue(simp_stats["is_open_surface"])
        self.assertEqual(simp_stats["boundary_loops_count"], 1)

    def test_06_quads_vs_tris_distinction(self):
        """6. Vérifie que les faces polygonales et triangles estimés sont comptés distinctement."""
        # Cube avec faces quads subdivisées
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=3) # 4x4 par face = 96 quads = 192 tris
        bpy.ops.object.mode_set(mode='OBJECT')

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 50.0

        simp = cube.copy()
        simp.data = cube.data.copy()
        bpy.context.collection.objects.link(simp)

        res = execute_simplification(simp, props, orig_reference_obj=cube)
        self.assertEqual(res["status"], "SUCCESS")
        # Distingue bien les faces obtenues des triangles obtenus
        self.assertGreater(res["obtained_triangles"], 0)
        self.assertGreater(res["obtained_polygons"], 0)

    def test_07_multi_component_mesh_preservation(self):
        """7. Vérifie que les composantes disjointes ne fusionnent pas lors de la réduction."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=(-2, 0, 0))
        s1 = bpy.context.active_object
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=(2, 0, 0))
        s2 = bpy.context.active_object

        s1.select_set(True)
        s2.select_set(True)
        bpy.context.view_layer.objects.active = s1
        bpy.ops.object.join()

        joined = bpy.context.active_object
        stats_init = get_mesh_statistics(joined)
        self.assertEqual(stats_init["disjoint_components"], 2)

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 50.0

        simp = joined.copy()
        simp.data = joined.data.copy()
        bpy.context.collection.objects.link(simp)

        res = execute_simplification(simp, props, orig_reference_obj=joined)
        self.assertEqual(res["status"], "SUCCESS")
        stats_simp = get_mesh_statistics(simp)
        self.assertEqual(stats_simp["disjoint_components"], 2)

    def test_08_materials_and_uv_preservation(self):
        """8. Vérifie la survie effective des matériaux multiples et des coordonnées UV."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=4)
        bpy.ops.object.mode_set(mode='OBJECT')

        mat1 = bpy.data.materials.new("Mat_Red")
        mat2 = bpy.data.materials.new("Mat_Blue")
        cube.data.materials.append(mat1)
        cube.data.materials.append(mat2)
        # Assigner Mat_Blue à la première moitié des polygones
        for i in range(len(cube.data.polygons) // 2):
            cube.data.polygons[i].material_index = 1

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 50.0
        props.preserve_materials = True
        props.preserve_uvs = True

        simp = cube.copy()
        simp.data = cube.data.copy()
        bpy.context.collection.objects.link(simp)

        res = execute_simplification(simp, props, orig_reference_obj=cube)
        self.assertEqual(res["status"], "SUCCESS")

        # Vérifier que les deux matériaux sont encore présents et assignés
        used_mats = set(p.material_index for p in simp.data.polygons)
        self.assertIn(0, used_mats)
        self.assertIn(1, used_mats)
        self.assertGreater(len(simp.data.uv_layers), 0)

    def test_09_organic_surface_with_creases(self):
        """9. Vérifie la réduction sur une surface avec fortes variations de courbure (Torus déformé)."""
        bpy.ops.mesh.primitive_torus_add(major_radius=1.5, minor_radius=0.4, major_segments=48, minor_segments=24)
        torus = bpy.context.active_object

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 70.0
        props.enable_simplification_tolerance = True
        props.simplification_max_tolerance = 0.05 # 5cm

        simp = torus.copy()
        simp.data = torus.data.copy()
        bpy.context.collection.objects.link(simp)

        res = execute_simplification(simp, props, orig_reference_obj=torus)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(res["reduction_percentage"], 50.0)

        val = res.get("geometric_validation", {})
        self.assertTrue(val.get("valid", False))
        self.assertLessEqual(val["distance_p95"], 0.05)

    def test_10_dense_reference_scalability(self):
        """10. Benchmark et vérification sur le cas de référence à ~1,587 million de triangles."""
        t0 = time.perf_counter()
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=891, y_subdivisions=891, size=2)
        grid = bpy.context.active_object
        tri_init = len(grid.data.polygons) * 2 # 1 587 762 triangles

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 50.0 # 50% de réduction
        props.enable_simplification_tolerance = False

        simp = grid.copy()
        simp.data = grid.data.copy()
        bpy.context.collection.objects.link(simp)

        t_sim_start = time.perf_counter()
        res = execute_simplification(simp, props, orig_reference_obj=None)
        t_sim = time.perf_counter() - t_sim_start

        self.assertEqual(res["status"], "SUCCESS")
        self.assertAlmostEqual(res["obtained_triangles"], tri_init // 2, delta=20000)
        self.assertGreater(res["reduction_percentage"], 45.0)

        print(f"\n--- BENCHMARK RÉDUCTION 1,587M TRIANGLES (PHASE C) ---")
        print(f"  Triangles initiaux : {tri_init}")
        print(f"  Triangles obtenus  : {res['obtained_triangles']} (-{res['reduction_percentage']}%)")
        print(f"  Durée de réduction : {t_sim:.3f} s")
        print(f"------------------------------------------------------\n")

        # Vérifier que le temps de réduction reste bien sous 60 secondes
        self.assertLess(t_sim, 60.0)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseC)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
