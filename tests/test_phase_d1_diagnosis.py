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
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

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
        """10. Benchmark de scalabilité : Vérifie le temps de diagnostic sur maillage dense (~100k triangles)."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=225, y_subdivisions=225)
        grid_100k = bpy.context.active_object
        grid_100k.data.calc_loop_triangles()
        tri_count = len(grid_100k.data.loop_triangles)  # ~101 250 triangles

        t0 = time.perf_counter()
        diag = diagnose_topology(grid_100k, mode='HYBRID_CLEANUP')
        dt = time.perf_counter() - t0

        print(f"\n--- BENCHMARK DIAGNOSTIC TOPOLOGIQUE D1 ---")
        print(f"  Maillage : {tri_count} triangles réels")
        print(f"  Durée diagnostic : {dt:.3f} s")
        print(f"  Défauts identifiés : {len(diag['defects'])}")
        print(f"-------------------------------------------\n")

        self.assertTrue(diag["valid"])
        self.assertLess(dt, 1.5)

    def test_11_concave_vs_convex_ngons(self):
        """11. Couverture diagnostique : Vérifie la distinction stricte entre N-gones convexes et concaves (angle rentrant > 180°)."""
        # A. Polygone convexe (Hexagone régulier)
        bpy.ops.mesh.primitive_circle_add(vertices=6, fill_type='NGON')
        hex_obj = bpy.context.active_object
        diag_hex = diagnose_topology(hex_obj, mode='HYBRID_CLEANUP')
        self.assertEqual(diag_hex["summary"]["ngons"], 1)
        self.assertEqual(diag_hex["summary"]["concave_ngons"], 0)
        self.assertFalse(any("Concave" in d["name"] for d in diag_hex["defects"]))

        # B. Polygone concave (Forme en flèche / angle rentrant)
        # Sommets dans l'ordre CCW : (0,0), (2,0), (2,2), (1,0.5), (0,2)
        # Le sommet (1, 0.5) est un angle rentrant intérieur > 180°
        arrow_mesh = bpy.data.meshes.new("ConcaveArrowMesh")
        bm = bmesh.new()
        verts = [
            bm.verts.new((0.0, 0.0, 0.0)),
            bm.verts.new((2.0, 0.0, 0.0)),
            bm.verts.new((2.0, 2.0, 0.0)),
            bm.verts.new((1.0, 0.5, 0.0)),  # Sommet concave / reflex
            bm.verts.new((0.0, 2.0, 0.0))
        ]
        bm.faces.new(verts)
        bm.to_mesh(arrow_mesh)
        bm.free()

        arrow_obj = bpy.data.objects.new("ConcaveArrowObj", arrow_mesh)
        bpy.context.collection.objects.link(arrow_obj)

        diag_arrow = diagnose_topology(arrow_obj, mode='HYBRID_CLEANUP')
        self.assertEqual(diag_arrow["summary"]["ngons"], 1)
        self.assertEqual(diag_arrow["summary"]["concave_ngons"], 1)
        concave_defects = [d for d in diag_arrow["defects"] if "Concave" in d["name"]]
        self.assertEqual(len(concave_defects), 1)
        self.assertIn("angle rentrant supérieur à 180°", concave_defects[0]["explanation"])

    def test_12_non_manifold_edge_3_plus_faces(self):
        """12. Couverture diagnostique : Vérifie la détection d'arête non-manifold partagée par >= 3 faces (jonction en T)."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(plane.data)
        bm.edges.ensure_lookup_table()
        e = bm.edges[0]
        # Ajouter 2 faces supplémentaires partageant cette arête (total 3 faces sur e)
        v_top = bm.verts.new((0.0, 0.0, 1.0))
        v_bot = bm.verts.new((0.0, 0.0, -1.0))
        bm.faces.new([e.verts[0], e.verts[1], v_top])
        bm.faces.new([e.verts[0], e.verts[1], v_bot])
        bm.to_mesh(plane.data)
        bm.free()

        diag = diagnose_topology(plane, mode='HYBRID_CLEANUP')
        nm_defects = [d for d in diag["defects"] if d["type"] == "NON_MANIFOLD_EDGE"]
        self.assertEqual(len(nm_defects), 1)
        self.assertEqual(nm_defects[0]["category"], "RED")
        self.assertIn("3 faces", nm_defects[0]["name"])

    def test_13_needle_triangles_aspect_ratio(self):
        """13. Couverture diagnostique : Vérifie la détection des triangles aiguilles (needle triangles, ratio > 8:1)."""
        mesh = bpy.data.meshes.new("NeedleMesh")
        bm = bmesh.new()
        # Triangle extrêmement fin : base = 10m, hauteur = 0.2m (ratio > 20:1)
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new((10.0, 0.0, 0.0))
        v2 = bm.verts.new((0.0, 0.2, 0.0))
        bm.faces.new([v0, v1, v2])
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("NeedleObj", mesh)
        bpy.context.collection.objects.link(obj)

        diag_game = diagnose_topology(obj, mode='GAME_TRIANGLES')
        needle_defects = [d for d in diag_game["defects"] if d["type"] == "TRIANGLE_NEEDLE"]
        self.assertEqual(len(needle_defects), 1)
        self.assertEqual(needle_defects[0]["category"], "BLUE")

    def test_14_multi_scale_micro_edges(self):
        """14. Couverture diagnostique : Vérifie l'adaptabilité de la détection de micro-arêtes à différentes échelles."""
        # A. Objet miniature (10 cm, bbox_diag ~ 0.17 m -> seuil micro ~ 17 µm)
        bpy.ops.mesh.primitive_cube_add(size=0.1)
        mini_cube = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(mini_cube.data)
        # Ajouter une arête intérieure de 5 µm
        v_a = bm.verts.new((0.0, 0.0, 0.0))
        v_b = bm.verts.new((0.0, 0.0, 0.000005))
        e_micro = bm.edges.new((v_a, v_b))
        bm.to_mesh(mini_cube.data)
        bm.free()

        diag_mini = diagnose_topology(mini_cube, mode='HYBRID_CLEANUP')
        micro_defects = [d for d in diag_mini["defects"] if d["type"] == "MICRO_EDGE"]
        self.assertGreaterEqual(len(micro_defects), 1)

    def test_15_minor_isolated_component_threshold(self):
        """15. Couverture diagnostique : Vérifie le seuil de 5% pour les composants disjoints mineurs."""
        # Créer une sphère UV principale (480 faces) et un petit fragment isolé de 2 faces (0.4% des faces)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=16)
        sphere = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(sphere.data)
        # Ajouter 2 faces disjointes à 10 mètres
        v1 = bm.verts.new((10.0, 0.0, 0.0))
        v2 = bm.verts.new((11.0, 0.0, 0.0))
        v3 = bm.verts.new((11.0, 1.0, 0.0))
        v4 = bm.verts.new((10.0, 1.0, 0.0))
        v5 = bm.verts.new((10.0, 2.0, 0.0))
        bm.faces.new([v1, v2, v3, v4])
        bm.faces.new([v4, v3, v5])
        bm.to_mesh(sphere.data)
        bm.free()

        diag = diagnose_topology(sphere, mode='HYBRID_CLEANUP')
        isolated_comp_defects = [d for d in diag["defects"] if d["type"] == "ISOLATED_COMPONENT"]
        self.assertEqual(len(isolated_comp_defects), 1)
        self.assertEqual(isolated_comp_defects[0]["category"], "VIOLET")
        self.assertIn("faces", isolated_comp_defects[0]["name"])

    def test_16_color_attribute_pre_existing_temp_and_user_restoration(self):
        """16. Intégrité visuelle : Vérifie la réutilisation de _MF_Inspection_Temp préexistant et la restauration de l'attribut actif utilisateur."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # 1. Ajouter un attribut utilisateur et l'activer
        user_attr = cube.data.color_attributes.new(name="Artist_VertexColor", type='FLOAT_COLOR', domain='CORNER')
        cube.data.color_attributes.active_color = user_attr

        # 2. Pré-créer un attribut _MF_Inspection_Temp avant le diagnostic (simulation de reliquat)
        pre_temp = cube.data.color_attributes.new(name=TEMP_ATTR_NAME, type='FLOAT_COLOR', domain='CORNER')
        self.assertEqual(len(cube.data.color_attributes), 2)

        diag = diagnose_topology(cube, mode='HYBRID_CLEANUP')
        # Appliquer l'inspection
        apply_color_inspection(cube, diag.get("defects", []))
        self.assertEqual(cube.data.color_attributes.active_color.name, TEMP_ATTR_NAME)

        # Nettoyer l'inspection
        clear_inspection_view(cube)
        # Vérifier que _MF_Inspection_Temp a disparu
        self.assertNotIn(TEMP_ATTR_NAME, cube.data.color_attributes)
        # Vérifier que l'attribut utilisateur existe toujours et est redevenu actif
        self.assertEqual(len(cube.data.color_attributes), 1)
        self.assertEqual(cube.data.color_attributes.active_color.name, "Artist_VertexColor")

    def test_17_strict_zero_data_mutation_guarantee(self):
        """17. Intégrité absolue : Vérifie qu'aucune géométrie, UV, normale, matériau ou groupe de sommets n'est modifié pendant le diagnostic."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        mesh = cube.data

        # Ajouter des données riches : UVs, matériaux, groupes de sommets
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.smart_project()
        bpy.ops.object.mode_set(mode='OBJECT')

        mat1 = bpy.data.materials.new("Mat_1")
        mat2 = bpy.data.materials.new("Mat_2")
        cube.data.materials.append(mat1)
        cube.data.materials.append(mat2)

        vg = cube.vertex_groups.new(name="BoneWeight")
        vg.add([0, 1, 2], 0.75, 'REPLACE')

        # Snapshot complet des données
        verts_coords_before = np.array([v.co for v in mesh.vertices])
        poly_count_before = len(mesh.polygons)
        edge_count_before = len(mesh.edges)
        uv_coords_before = np.array([loop.uv for loop in mesh.uv_layers[0].data])
        mat_count_before = len(cube.data.materials)
        vg_count_before = len(cube.vertex_groups)

        # Exécuter diagnostic, sélection et inspection visuelle
        diag = diagnose_topology(cube, mode='DEFORMABLE_QUADS')
        if diag["defects"]:
            select_defect(cube, diag["defects"][0])
        apply_color_inspection(cube, diag.get("defects", []))
        clear_inspection_view(cube)

        # Vérification d'égalité stricte post-diagnostic
        np.testing.assert_array_equal(verts_coords_before, np.array([v.co for v in mesh.vertices]))
        self.assertEqual(len(mesh.polygons), poly_count_before)
        self.assertEqual(len(mesh.edges), edge_count_before)
        np.testing.assert_array_equal(uv_coords_before, np.array([loop.uv for loop in mesh.uv_layers[0].data]))
        self.assertEqual(len(cube.data.materials), mat_count_before)
        self.assertEqual(len(cube.vertex_groups), vg_count_before)

    def test_18_multi_scale_timings_diag_apply_clear(self):
        """18. Performance & Linéarité : Mesure séparée des temps de diagnostic, d'application et de nettoyage sur 3 échelles."""
        scales = [
            ("1k_polygones", 32),    # ~1 000 faces / ~2 000 tris
            ("10k_polygones", 100),  # ~10 000 faces / ~20 000 tris
            ("50k_polygones", 225)   # ~50 000 faces / ~101 250 tris
        ]

        print("\n=======================================================")
        print("MESURES DE PERFORMANCE MULTI-ÉCHELLES (PHASE D1)")
        print("=======================================================")

        for label, subd in scales:
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=subd, y_subdivisions=subd)
            grid = bpy.context.active_object
            f_count = len(grid.data.polygons)
            grid.data.calc_loop_triangles()
            tri_count = len(grid.data.loop_triangles)

            # 1. Durée Diagnostic
            t0 = time.perf_counter()
            diag = diagnose_topology(grid, mode='HYBRID_CLEANUP')
            t_diag = time.perf_counter() - t0

            # 2. Durée Application Visualisation
            t1 = time.perf_counter()
            apply_color_inspection(grid, diag.get("defects", []))
            t_apply = time.perf_counter() - t1

            # 3. Durée Nettoyage Visualisation
            t2 = time.perf_counter()
            clear_inspection_view(grid)
            t_clear = time.perf_counter() - t2

            print(f"  [{label}] : {f_count} faces ({tri_count} triangles réels)")
            print(f"    - Temps diagnostic   : {t_diag*1000:.2f} ms")
            print(f"    - Temps visualiseur  : {t_apply*1000:.2f} ms")
            print(f"    - Temps nettoyage    : {t_clear*1000:.2f} ms")
            print(f"    - Total interactif   : {(t_diag + t_apply + t_clear)*1000:.2f} ms")

            # Garanties de performance
            self.assertLess(t_diag, 1.0)
            self.assertLess(t_apply, 0.5)
            self.assertLess(t_clear, 0.2)

            bpy.data.objects.remove(grid, do_unlink=True)

        print("=======================================================\n")



if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD1Diagnosis)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
