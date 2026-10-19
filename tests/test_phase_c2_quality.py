"""MeshForge - Suite de tests de qualité et d'audit technique (Phase C2).
Vérifie la robustesse, les cas d'échec géométriques, l'injection de défauts (mutation testing),
la stabilité multi-résolution de la silhouette, et les benchmarks détaillés avec mesure mémoire.
"""

from __future__ import annotations
import bpy
import bmesh
import math
import time
import sys
import unittest
import tracemalloc
import numpy as np
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.mesh_stats import get_mesh_statistics
from meshforge.core.simplification import execute_simplification
from meshforge.core.validation import (
    evaluate_geometric_deviation,
    sample_mesh_surface,
    compute_silhouette_occupancy_and_contour
)


class TestMeshForgePhaseC2Quality(unittest.TestCase):
    """Tests d'audit, de non-régression et de validation de qualité (Phase C2)."""

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_01_true_silhouette_iou_vs_aabb_defect_injection(self):
        """1. Injection de défaut : Démontre que l'ancien calcul AABB est incapable de détecter
        la perte de silhouette (0% d'écart entre sphère et octaèdre), alors que le nouveau calcul IoU
        détecte une divergence de ~49%.
        """
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24)
        sphere = bpy.context.active_object

        bpy.ops.mesh.primitive_uv_sphere_add(segments=4, ring_count=3)
        octa = bpy.context.active_object

        pts_sphere, _ = sample_mesh_surface(sphere.data, target_samples=10000, seed=42)
        pts_octa, _ = sample_mesh_surface(octa.data, target_samples=10000, seed=42)

        # Calcul erroné (défaut AABB)
        s_min = np.min(pts_sphere[:, [0, 1]], axis=0)
        s_max = np.max(pts_sphere[:, [0, 1]], axis=0)
        o_min = np.min(pts_octa[:, [0, 1]], axis=0)
        o_max = np.max(pts_octa[:, [0, 1]], axis=0)
        area_s_aabb = (s_max[0] - s_min[0]) * (s_max[1] - s_min[1])
        area_o_aabb = (o_max[0] - o_min[0]) * (o_max[1] - o_min[1])
        delta_aabb = abs(area_s_aabb - area_o_aabb) / area_s_aabb * 100.0

        # Nouveau calcul (Validation MeshForge C2)
        val = evaluate_geometric_deviation(sphere, octa, sample_count=10000, seed=42)
        self.assertTrue(val["valid"])
        sil_metrics = val["silhouette_metrics"]["XY"]
        divergence_iou = sil_metrics["divergence_pct"]

        print(f"\n[Test Silhouette] Défaut AABB = {delta_aabb:.2f}% | Vraie divergence IoU = {divergence_iou:.2f}%")
        # L'IoU doit impérativement détecter une divergence majeure (> 35%)
        self.assertGreater(divergence_iou, 35.0)
        self.assertGreater(sil_metrics["contour_distance_mean_m"], 0.05)

    def test_02_local_bounding_box_scale_invariance_defect_injection(self):
        """2. Injection de défaut : Vérifie l'invariance au scale non appliqué.
        Démontre que la diagonale de boîte locale est utilisée au lieu de world dimensions.length.
        """
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object
        cube.scale = (5.0, 5.0, 5.0)  # Scale x5 non appliqué

        simp_cube = cube.copy()
        simp_cube.data = cube.data.copy()
        bpy.context.collection.objects.link(simp_cube)

        val = evaluate_geometric_deviation(cube, simp_cube, sample_count=2000, seed=42)
        # La diagonale du cube de côté 2.0 en coordonnées locales est sqrt(2^2 + 2^2 + 2^2) = ~3.464 m
        # Si le scale non appliqué avait été pris en compte (défaut), la diagonale aurait été 17.32 m
        self.assertAlmostEqual(val["bounding_box_diagonal"], 3.4641, delta=0.01)

    def test_03_standalone_operator_enforces_tolerance(self):
        """3. Vérifie que l'opérateur unitaire meshforge.simplification respecte la tolérance
        en créant un instantané interne fiable, sans contourner la tolérance.
        """
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24)
        sphere = bpy.context.active_object
        initial_tris = len(sphere.data.polygons) * 2

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'BUDGET_TRIANGLES'
        props.simplification_target_triangles = 80  # Demande agressive
        props.enable_simplification_tolerance = True
        props.simplification_max_tolerance = 0.015  # Tolérance serrée (1.5 cm)

        bpy.context.view_layer.objects.active = sphere
        res_op = bpy.ops.meshforge.simplification()
        self.assertEqual(res_op, {'FINISHED'})

        final_tris = sum(max(0, len(p.vertices) - 2) for p in sphere.data.polygons)
        # L'opérateur a dû refuser de descendre à 80 triangles pour préserver la tolérance
        self.assertGreater(final_tris, 250)

    def test_04_watertight_volume_safety_defect_injection(self):
        """4. Vérifie que la variation de volume est refusée (None) si le maillage simplifié
        n'est pas strictement étanche (bilatéral).
        """
        bpy.ops.mesh.primitive_cube_add()
        cube_orig = bpy.context.active_object

        cube_broken = cube_orig.copy()
        cube_broken.data = cube_orig.data.copy()
        bpy.context.collection.objects.link(cube_broken)

        # Créer un trou dans cube_broken
        bm = bmesh.new()
        bm.from_mesh(cube_broken.data)
        bm.faces.ensure_lookup_table()
        bm.faces.remove(bm.faces[0])  # Supprimer une face -> surface ouverte
        bm.to_mesh(cube_broken.data)
        bm.free()

        val = evaluate_geometric_deviation(cube_orig, cube_broken, sample_count=2000, seed=42)
        self.assertTrue(val["valid"])
        self.assertFalse(val["is_watertight"])
        self.assertTrue(val["is_watertight_orig"])
        self.assertFalse(val["is_watertight_simp"])
        # Le calcul de volume DOIT être None pour éviter les valeurs aberrantes
        self.assertIsNone(val["volume_delta_pct"])

    def test_05_chamfer_and_crease_preservation(self):
        """5. Vérifie le comportement sur un asset mécanique avec chanfreins étroits (Bevel)."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object
        mod_b = cube.modifiers.new("Bevel", 'BEVEL')
        mod_b.width = 0.05  # Chanfrein 5 cm
        mod_b.segments = 3
        bpy.ops.object.modifier_apply(modifier=mod_b.name)

        simp = cube.copy()
        simp.data = cube.data.copy()
        bpy.context.collection.objects.link(simp)

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 40.0
        props.enable_simplification_tolerance = True
        props.simplification_max_tolerance = 0.02

        res = execute_simplification(simp, props, orig_reference_obj=cube)
        self.assertEqual(res["status"], "SUCCESS")
        val = res.get("geometric_validation", {})
        self.assertTrue(val.get("valid"))
        self.assertLessEqual(val["distance_p95"], 0.02)

    def test_06_thin_cloth_folds_preservation(self):
        """6. Vérifie le comportement sur un tissu/cloth ouvert avec plis fins sinusoïdaux."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=40, size=2.0)
        cloth = bpy.context.active_object
        # Déformer les sommets en ondes
        for v in cloth.data.vertices:
            v.co.z = 0.1 * math.sin(v.co.x * 6.0) * math.cos(v.co.y * 6.0)

        simp = cloth.copy()
        simp.data = cloth.data.copy()
        bpy.context.collection.objects.link(simp)

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 50.0
        props.preserve_boundaries = True

        res = execute_simplification(simp, props, orig_reference_obj=cloth)
        self.assertEqual(res["status"], "SUCCESS")

        stats_simp = get_mesh_statistics(simp)
        self.assertTrue(stats_simp["is_open_surface"])
        self.assertEqual(stats_simp["boundary_loops_count"], 1)

    def test_07_complex_uv_islands_and_materials(self):
        """7. Vérifie la survie des données UV et des assignations de matériaux."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=3)
        bpy.ops.uv.smart_project()
        bpy.ops.object.mode_set(mode='OBJECT')

        m1 = bpy.data.materials.new("Mat_A")
        m2 = bpy.data.materials.new("Mat_B")
        cube.data.materials.append(m1)
        cube.data.materials.append(m2)
        for i, p in enumerate(cube.data.polygons):
            if i < len(cube.data.polygons) // 2:
                p.material_index = 1

        simp = cube.copy()
        simp.data = cube.data.copy()
        bpy.context.collection.objects.link(simp)

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 50.0
        props.preserve_materials = True
        props.preserve_uvs = True

        res = execute_simplification(simp, props, orig_reference_obj=cube)
        self.assertEqual(res["status"], "SUCCESS")
        val = res.get("geometric_validation", {})
        self.assertEqual(val["materials_before"], 2)
        self.assertEqual(val["materials_after"], 2)
        self.assertGreater(len(simp.data.uv_layers), 0)

    def test_08_non_manifold_input_safety(self):
        """8. Robustesse : Vérifie qu'un maillage non-manifold (arête à 3 faces) ne fait pas planter le moteur."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(plane.data)
        bm.edges.ensure_lookup_table()
        e = bm.edges[0]
        v_new = bm.verts.new((0, 0, 1))
        bm.faces.new([e.verts[0], e.verts[1], v_new])
        bm.to_mesh(plane.data)
        bm.free()

        simp = plane.copy()
        simp.data = plane.data.copy()
        bpy.context.collection.objects.link(simp)

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.simplification_percentage = 30.0

        res = execute_simplification(simp, props, orig_reference_obj=plane)
        # Doit s'exécuter sans crash
        self.assertIn(res["status"], ["SUCCESS", "ERROR"])

    def test_09_silhouette_resolution_stability(self):
        """9. Vérifie la stabilité des métriques de silhouette sur résolutions 64, 128 et 256."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
        orig = bpy.context.active_object

        simp = orig.copy()
        simp.data = orig.data.copy()
        bpy.context.collection.objects.link(simp)

        mod = simp.modifiers.new("Decim", 'DECIMATE')
        mod.ratio = 0.5
        bpy.context.view_layer.objects.active = simp
        bpy.ops.object.modifier_apply(modifier=mod.name)

        ious = []
        for res in [64, 128, 256]:
            val = evaluate_geometric_deviation(orig, simp, sample_count=5000, silhouette_resolution=res, seed=42)
            iou = val["silhouette_metrics"]["XY"]["iou"]
            ious.append(iou)

        print(f"\n[Stabilité Silhouette IoU] Res 64: {ious[0]:.4f} | Res 128: {ious[1]:.4f} | Res 256: {ious[2]:.4f}")
        # La variation d'IoU entre 64, 128 et 256 ne doit pas dépasser 0.05
        self.assertLess(abs(ious[0] - ious[1]), 0.05)
        self.assertLess(abs(ious[1] - ious[2]), 0.05)

    def test_10_benchmark_1_587M_multiratio_and_memory(self):
        """10. Benchmark de référence (1,587M triangles) : Mesure séparée de simplification,
        validation, passes et mémoire maximale.
        """
        tracemalloc.start()
        t_create_0 = time.perf_counter()
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=891, y_subdivisions=891, size=2)
        grid = bpy.context.active_object
        grid.data.calc_loop_triangles()
        tri_init = len(grid.data.loop_triangles)

        print(f"\n=======================================================")
        print(f"BENCHMARK MULTI-RATIO 1,587M TRIANGLES (PHASE C2)")
        print(f"=======================================================")
        print(f"  Modèle source : Grille plane ({tri_init} triangles réels)")

        props = bpy.context.scene.meshforge_settings
        props.simplification_mode = 'PERCENTAGE'
        props.enable_simplification_tolerance = False

        ratios_to_test = [0.75, 0.50, 0.25]
        for r in ratios_to_test:
            pct = round((1.0 - r) * 100.0, 1)
            props.simplification_percentage = pct

            simp = grid.copy()
            simp.data = grid.data.copy()
            bpy.context.collection.objects.link(simp)

            t_decim_0 = time.perf_counter()
            res = execute_simplification(simp, props, orig_reference_obj=None)
            t_decim = time.perf_counter() - t_decim_0

            # Mesure séparée de la validation
            t_val_0 = time.perf_counter()
            val = evaluate_geometric_deviation(grid, simp, sample_count=5000, seed=42)
            t_val = time.perf_counter() - t_val_0

            current_mem, peak_mem = tracemalloc.get_traced_memory()
            peak_mb = peak_mem / (1024 * 1024)

            print(f"  [Ratio {r:.2f} | Cible -{pct}%] :")
            print(f"    - Triangles obtenus : {res['obtained_triangles']} ({res['reduction_percentage']}%)")
            print(f"    - Temps Decimate    : {t_decim:.3f} s")
            print(f"    - Temps Validation  : {t_val:.3f} s (IoU XY: {val['silhouette_metrics']['XY']['iou']:.4f})")
            print(f"    - Distance P99      : {val['distance_p99']:.6f} m")
            print(f"    - Pic mémoire Python: {peak_mb:.1f} MB")

            self.assertEqual(res["status"], "SUCCESS")
            self.assertLess(t_decim, 30.0)

            bpy.data.objects.remove(simp, do_unlink=True)

        tracemalloc.stop()
        print(f"=======================================================\n")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseC2Quality)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
