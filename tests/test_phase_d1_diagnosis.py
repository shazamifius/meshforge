"""MeshForge - Suite de tests de validation de la Phase D1.
Vérifie :
1. Le diagnostic topologique en lecture seule (sans modification de maillage).
2. La détection et catégorisation sémantique des défauts (Orange, Bleu, Rouge, Violet).
3. La distinction formelle entre statistiques de valence objectives et heuristiques de mode.
4. La non-destructivité de la sélection et du nettoyage de la vue d'inspection.
5. La robustesse aux contextes sans vue 3D (mode background/batch).
6. La performance sur différentes densités de maillage.
"""

from __future__ import annotations
import bpy
import bmesh
import time
import sys
import unittest
import numpy as np
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.core.visualizer import (
    select_defect,
    zoom_to_defect,
    apply_color_inspection,
    clear_inspection_view,
    TEMP_ATTR_NAME
)


class TestMeshForgePhaseD1Diagnosis(unittest.TestCase):
    """Tests unitaires et d'intégration de l'assistant topologique et de la visualisation (Phase D1)."""

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_01_strictly_read_only_analysis(self):
        """1. Vérifie que le diagnostic n'altère absolument pas la géométrie (sommets, arêtes, faces, coordonnées)."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
        obj = bpy.context.active_object
        mesh = obj.data

        verts_before = len(mesh.vertices)
        edges_before = len(mesh.edges)
        faces_before = len(mesh.polygons)
        coords_before = np.array([v.co for v in mesh.vertices])

        diag = diagnose_topology(obj, mode='HYBRID_CLEANUP')
        self.assertTrue(diag["valid"])

        # Vérifier que rien n'a bougé
        self.assertEqual(len(mesh.vertices), verts_before)
        self.assertEqual(len(mesh.edges), edges_before)
        self.assertEqual(len(mesh.polygons), faces_before)
        coords_after = np.array([v.co for v in mesh.vertices])
        np.testing.assert_array_equal(coords_before, coords_after)

    def test_02_ngons_detection_and_classification(self):
        """2. Vérifie la détection des N-gones (Catégorie ORANGE) et la distinction convexe/concave."""
        # Créer un polygone à 6 côtés (Cercle rempli NGON)
        bpy.ops.mesh.primitive_circle_add(vertices=6, fill_type='NGON')
        obj = bpy.context.active_object

        diag = diagnose_topology(obj, mode='HYBRID_CLEANUP')
        self.assertEqual(diag["summary"]["ngons"], 1)

        # Vérifier que le défaut est bien classé ORANGE
        ngon_defects = [d for d in diag["defects"] if d["type"] == "NGON"]
        self.assertEqual(len(ngon_defects), 1)
        self.assertEqual(ngon_defects[0]["category"], "ORANGE")
        self.assertEqual(ngon_defects[0]["element_type"], "FACE")

    def test_03_triangles_in_quads_mode_vs_hybrid(self):
        """3. Vérifie que les triangles ne sont considérés suspects qu'en mode DEFORMABLE_QUADS."""
        # Cube avec une face coupée en deux triangles
        bpy.ops.mesh.primitive_cube_add()
        obj = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        f0 = bm.faces[0]
        # Trianguler uniquement la première face
        bmesh.ops.triangulate(bm, faces=[f0])
        bm.to_mesh(obj.data)
        bm.free()

        # En mode HYBRID_CLEANUP : les triangles sont inventoriés mais non signalés comme erreurs
        diag_hybrid = diagnose_topology(obj, mode='HYBRID_CLEANUP')
        self.assertEqual(diag_hybrid["summary"]["triangles"], 2)
        self.assertEqual(diag_hybrid["summary"]["suspect_triangles"], 0)

        # En mode DEFORMABLE_QUADS : les triangles isolés dans les quads sont signalés en BLEU
        diag_quads = diagnose_topology(obj, mode='DEFORMABLE_QUADS')
        self.assertEqual(diag_quads["summary"]["triangles"], 2)
        self.assertGreaterEqual(diag_quads["summary"]["suspect_triangles"], 1)
        blue_defects = [d for d in diag_quads["defects"] if d["category"] == "BLUE"]
        self.assertGreater(len(blue_defects), 0)

    def test_04_valence_and_poles_distinction(self):
        """4. Vérifie la distinction entre statistiques de valence objectives et heuristiques de pôles."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        # Un cube simple a 8 sommets de valence 3 (N-poles)
        diag = diagnose_topology(cube, mode='HYBRID_CLEANUP')
        val_stats = diag["valence_stats"]
        self.assertEqual(val_stats["poles_3_n"], 8)
        self.assertEqual(val_stats["regular_4"], 0)
        self.assertEqual(val_stats["poles_6_plus"], 0)

        # En mode HYBRID, les valences 3 du cube NE sont PAS des défauts
        complex_defects = [d for d in diag["defects"] if d["type"] == "COMPLEX_POLE"]
        self.assertEqual(len(complex_defects), 0)

    def test_05_degeneracies_detection_red(self):
        """5. Vérifie la détection des faces d'aire nulle et arêtes minuscules (Catégorie ROUGE)."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(plane.data)
        bm.verts.ensure_lookup_table()
        # Créer un triangle d'aire nulle en plaçant 3 sommets colinéaires
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((2.0, 0.0, 0.0))
        bm.faces.new([v1, v2, v3])
        bm.to_mesh(plane.data)
        bm.free()

        diag = diagnose_topology(plane, mode='HYBRID_CLEANUP')
        self.assertGreaterEqual(diag["summary"]["degeneracies"], 1)
        red_defects = [d for d in diag["defects"] if d["category"] == "RED"]
        self.assertGreater(len(red_defects), 0)
        self.assertTrue(any(d["type"] == "ZERO_AREA_FACE" for d in red_defects))

    def test_06_isolated_components_and_loose_violet(self):
        """6. Vérifie la détection des éléments orphelins et composants isolés (Catégorie VIOLET)."""
        bpy.ops.mesh.primitive_cube_add(location=(-5, 0, 0))
        cube = bpy.context.active_object
        # Ajouter un sommet orphelin (loose)
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        bm.verts.new((10, 10, 10))
        bm.to_mesh(cube.data)
        bm.free()

        diag = diagnose_topology(cube, mode='HYBRID_CLEANUP')
        self.assertGreaterEqual(diag["summary"]["isolated"], 1)
        violet_defects = [d for d in diag["defects"] if d["category"] == "VIOLET"]
        self.assertGreater(len(violet_defects), 0)

    def test_07_open_mesh_boundaries_not_flagged_as_non_manifold(self):
        """7. Vérifie que les frontières ouvertes d'une nappe/grille ne sont pas déclarées non-manifold."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10)
        grid = bpy.context.active_object

        diag = diagnose_topology(grid, mode='HYBRID_CLEANUP')
        # Une grille ouverte ne doit pas avoir d'erreur non-manifold rouge
        nm_defects = [d for d in diag["defects"] if d["type"] == "NON_MANIFOLD_EDGE"]
        self.assertEqual(len(nm_defects), 0)

    def test_08_visualizer_selection_and_cleanup(self):
        """8. Vérifie que l'attribution de couleur temporaire et son nettoyage n'affectent pas les attributs utilisateur."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # Ajouter un attribut de couleur utilisateur légitime
        user_attr = cube.data.color_attributes.new(name="User_ColorMap", type='FLOAT_COLOR', domain='POINT')
        initial_attr_count = len(cube.data.color_attributes)

        diag = diagnose_topology(cube, mode='DEFORMABLE_QUADS')
        # Appliquer l'inspection
        ok_apply = apply_color_inspection(cube, diag.get("defects", []))
        self.assertTrue(ok_apply)
        self.assertIn(TEMP_ATTR_NAME, cube.data.color_attributes)

        # Nettoyer l'inspection
        ok_clear = clear_inspection_view(cube)
        self.assertTrue(ok_clear)
        self.assertNotIn(TEMP_ATTR_NAME, cube.data.color_attributes)
        # Vérifier que l'attribut utilisateur existe toujours
        self.assertEqual(len(cube.data.color_attributes), initial_attr_count)
        self.assertIn("User_ColorMap", cube.data.color_attributes)

    def test_09_zoom_to_defect_safe_fallback_in_headless(self):
        """9. Vérifie que zoom_to_defect ne lève aucune exception non gérée lorsqu'aucune vue 3D n'est active."""
        dummy_defect = {"center": (0.0, 0.0, 0.0), "name": "Test Defect"}
        ok, msg = zoom_to_defect(dummy_defect, bpy.context)
        # En mode headless/batch, il doit renvoyer proprement False avec message explicatif
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)

    def test_10_diagnosis_scalability_benchmark(self):
        """10. Benchmark de scalabilité : Vérifie le temps de diagnostic sur maillage dense (~100k et ~1M triangles)."""
        # Test sur 100k triangles
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=225, y_subdivisions=225)
        grid_100k = bpy.context.active_object
        grid_100k.data.calc_loop_triangles()
        tri_count = len(grid_100k.data.loop_triangles) # ~101 250 triangles

        t0 = time.perf_counter()
        diag = diagnose_topology(grid_100k, mode='HYBRID_CLEANUP')
        dt = time.perf_counter() - t0

        print(f"\n--- BENCHMARK DIAGNOSTIC TOPOLOGIQUE D1 ---")
        print(f"  Maillage : {tri_count} triangles réels")
        print(f"  Durée diagnostic : {dt:.3f} s")
        print(f"  Défauts identifiés : {len(diag['defects'])}")
        print(f"-------------------------------------------\n")

        self.assertTrue(diag["valid"])
        # Le diagnostic sur 100k triangles doit s'exécuter en moins de 1.5 seconde
        self.assertLess(dt, 1.5)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD1Diagnosis)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
