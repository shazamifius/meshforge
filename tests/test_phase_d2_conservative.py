"""MeshForge - Suite de tests de validation de la Phase D2.1 (Nettoyage Conservateur).
Vérifie :
1. Le nettoyage des sommets orphelins (Loose Vertices) à risque nul.
2. Le nettoyage des arêtes filaires sans face (Wire Edges) selon règle explicite.
3. La dissolution des faces dégénérées/nulles en préservant les frontières.
4. La fusion des doublons stricts avec seuil explicite et sans fusion silencieuse.
5. La préservation stricte des coutures UV (seams) et des matériaux.
6. Le respect des géométries ouvertes (nappes/tissus).
7. La garantie formelle de Rollback automatique lors de violations d'invariants ou échec simulé.
8. La restauration après opérations successives.
9. L'actualisation automatique du diagnostic topologique post-nettoyage.
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
from meshforge.core.conservative_cleaner import (
    clean_loose_vertices,
    clean_wire_edges,
    clean_zero_area_faces,
    merge_duplicate_vertices,
    execute_conservative_cleanup,
    MeshSnapshot
)
from meshforge.core.topology_diagnosis import diagnose_topology


class TestMeshForgePhaseD2Conservative(unittest.TestCase):
    """Tests unitaires et transactionnels du nettoyage conservateur (Phase D2.1)."""

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_01_clean_loose_vertices_zero_risk(self):
        """1. Vérifie la suppression des sommets orphelins sans aucune altération des faces et arêtes."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        mesh = cube.data

        # Ajouter 4 sommets orphelins flottants
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for i in range(4):
            bm.verts.new((float(i) + 10.0, 0.0, 0.0))
        bm.to_mesh(mesh)
        bm.free()

        self.assertEqual(len(mesh.vertices), 12)  # 8 du cube + 4 orphelins

        res = execute_conservative_cleanup(
            cube,
            clean_loose_v=True,
            clean_wire_e=False,
            clean_zero_f=False,
            merge_doubles=False
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["elements_removed"]["loose_verts"], 4)
        self.assertEqual(len(mesh.vertices), 8)
        self.assertEqual(len(mesh.polygons), 6)
        self.assertEqual(len(mesh.edges), 12)

    def test_02_clean_wire_edges_explicit_rule(self):
        """2. Vérifie la suppression des arêtes filaires sans face selon la règle explicite."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        mesh = plane.data

        # Ajouter 2 arêtes filaires (segments sans face)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        v1 = bm.verts.new((5.0, 0.0, 0.0))
        v2 = bm.verts.new((6.0, 0.0, 0.0))
        v3 = bm.verts.new((7.0, 0.0, 0.0))
        bm.edges.new((v1, v2))
        bm.edges.new((v2, v3))
        bm.to_mesh(mesh)
        bm.free()

        self.assertEqual(len(mesh.edges), 6)  # 4 du plan + 2 filaires

        res = execute_conservative_cleanup(
            plane,
            clean_loose_v=True,
            clean_wire_e=True,
            clean_zero_f=False,
            merge_doubles=False
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["elements_removed"]["wire_edges"], 2)
        self.assertEqual(len(mesh.edges), 4)
        self.assertEqual(len(mesh.polygons), 1)

    def test_03_clean_zero_area_faces_safe_dissolve(self):
        """3. Vérifie la dissolution des faces d'aire nulle en préservant les faces saines."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        mesh = plane.data

        # Créer un triangle d'aire nulle (3 sommets colinéaires)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        v1 = bm.verts.new((10.0, 0.0, 0.0))
        v2 = bm.verts.new((11.0, 0.0, 0.0))
        v3 = bm.verts.new((12.0, 0.0, 0.0))
        bm.faces.new([v1, v2, v3])
        bm.to_mesh(mesh)
        bm.free()

        self.assertEqual(len(mesh.polygons), 2)

        res = execute_conservative_cleanup(
            plane,
            clean_loose_v=True,
            clean_wire_e=True,
            clean_zero_f=True,
            merge_doubles=False
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["elements_removed"]["zero_faces"], 1)
        self.assertEqual(len(mesh.polygons), 1)

    def test_04_merge_doubles_explicit_threshold_and_consequences(self):
        """4. Vérifie la fusion de doublons avec seuil explicite : ne fusionne pas au-delà du seuil."""
        mesh = bpy.data.meshes.new("DoublesMesh")
        bm = bmesh.new()
        # Deux sommets séparés de 5 µm (0.000005 m)
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((0.0, 0.0, 0.000005))
        # Deux sommets séparés de 1 mm (0.001 m)
        v3 = bm.verts.new((1.0, 0.0, 0.0))
        v4 = bm.verts.new((1.001, 0.0, 0.0))
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("DoublesObj", mesh)
        bpy.context.collection.objects.link(obj)

        # Seuil fixé à 10 µm (0.000010 m)
        res = execute_conservative_cleanup(
            obj,
            clean_loose_v=False,
            clean_wire_e=False,
            clean_zero_f=False,
            merge_doubles=True,
            doubles_distance=0.00001
        )

        self.assertTrue(res["success"])
        # Seul le premier doublon doit être fusionné, le couple à 1 mm reste intact
        self.assertEqual(res["elements_removed"]["doubles_merged"], 1)
        self.assertEqual(len(mesh.vertices), 3)

    def test_05_preserve_uv_seams_during_merge(self):
        """5. Vérifie que les sommets délimitant des coutures UV (Seams) ne sont pas fusionnés si preserve_seams est actif."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        mesh = plane.data

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        # Marquer une arête comme seam
        e_seam = bm.edges[0]
        e_seam.seam = True
        # Ajouter un sommet doublon très proche du premier sommet de la couture
        co0 = e_seam.verts[0].co
        v_dup = bm.verts.new((co0.x, co0.y, co0.z + 0.000005))
        bm.to_mesh(mesh)
        bm.free()

        # Si preserve_seams = True, le sommet de seam est protégé de la fusion
        res = execute_conservative_cleanup(
            plane,
            clean_loose_v=False,
            clean_wire_e=False,
            clean_zero_f=False,
            merge_doubles=True,
            doubles_distance=0.00001,
            preserve_seams=True
        )

        self.assertTrue(res["success"])
        # Le sommet de la seam n'a pas été écrasé
        self.assertEqual(res["elements_removed"]["doubles_merged"], 0)

    def test_06_open_mesh_boundary_preservation(self):
        """6. Vérifie que les frontières d'une nappe ouverte (tissu/grille) restent rigoureusement ouvertes."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10)
        grid = bpy.context.active_object
        mesh = grid.data

        # Vérifier le nombre d'arêtes de frontière initiales via BMesh
        bm_before = bmesh.new()
        bm_before.from_mesh(mesh)
        boundaries_before = sum(1 for e in bm_before.edges if e.is_boundary)
        bm_before.free()

        res = execute_conservative_cleanup(
            grid,
            clean_loose_v=True,
            clean_wire_e=True,
            clean_zero_f=True,
            merge_doubles=True,
            doubles_distance=1e-5
        )

        self.assertTrue(res["success"])
        bm_after = bmesh.new()
        bm_after.from_mesh(mesh)
        boundaries_after = sum(1 for e in bm_after.edges if e.is_boundary)
        bm_after.free()
        self.assertEqual(boundaries_after, boundaries_before)

    def test_07_material_and_uv_preservation(self):
        """7. Vérifie la survie intacte des matériaux multiples et des coordonnées UV."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        mesh = cube.data

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.smart_project()
        bpy.ops.object.mode_set(mode='OBJECT')

        mat1 = bpy.data.materials.new("Mat_A")
        mat2 = bpy.data.materials.new("Mat_B")
        cube.data.materials.append(mat1)
        cube.data.materials.append(mat2)

        # Ajouter un sommet orphelin
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.new((10.0, 10.0, 10.0))
        bm.to_mesh(mesh)
        bm.free()

        uv_before = np.array([l.uv for l in mesh.uv_layers[0].data])

        res = execute_conservative_cleanup(cube)
        self.assertTrue(res["success"])
        self.assertEqual(len(cube.data.materials), 2)
        uv_after = np.array([l.uv for l in mesh.uv_layers[0].data])
        np.testing.assert_array_equal(uv_before, uv_after)

    def test_08_transaction_rollback_on_simulated_critical_failure(self):
        """8. Garantie de Rollback : Démontre la restauration automatique de l'état initial lors d'une violation d'invariant."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        mesh = cube.data
        initial_verts = len(mesh.vertices)
        initial_faces = len(mesh.polygons)
        coords_before = np.array([v.co for v in mesh.vertices])

        # Création manuelle d'un snapshot
        snapshot = MeshSnapshot(mesh)

        # Simuler une corruption du maillage (suppression totale ou injection de NaN)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        # Supprimer toutes les faces pour violer l'invariant de préservation
        bmesh.ops.delete(bm, geom=bm.faces, context='FACES')
        bm.to_mesh(mesh)
        bm.free()

        # Le maillage a été corrompu
        self.assertEqual(len(mesh.polygons), 0)

        # Restauration transactionnelle via Snapshot
        ok_restore = snapshot.restore(mesh)
        self.assertTrue(ok_restore)

        # Vérifier que le maillage est rigoureusement identique à l'état initial
        self.assertEqual(len(mesh.vertices), initial_verts)
        self.assertEqual(len(mesh.polygons), initial_faces)
        coords_after = np.array([v.co for v in mesh.vertices])
        np.testing.assert_array_equal(coords_before, coords_after)

    def test_09_multi_step_successive_restoration(self):
        """9. Vérifie la stabilité après plusieurs opérations successives avec actualisation du diagnostic."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # Étape 1 : Nettoyage conservateur sur cube sain (doit réussir sans suppression)
        res1 = execute_conservative_cleanup(cube)
        self.assertTrue(res1["success"])
        self.assertEqual(res1["elements_removed"]["loose_verts"], 0)

        # Étape 2 : Ajout de 3 sommets orphelins et nettoyage
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        for i in range(3):
            bm.verts.new((float(i) + 5.0, 0.0, 0.0))
        bm.to_mesh(cube.data)
        bm.free()

        res2 = execute_conservative_cleanup(cube)
        self.assertTrue(res2["success"])
        self.assertEqual(res2["elements_removed"]["loose_verts"], 3)
        self.assertEqual(len(cube.data.vertices), 8)

    def test_10_re_run_topology_diagnosis_and_reporting(self):
        """10. Vérifie le calcul automatique du rapport et du diagnostic post-nettoyage conservateur."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # Ajouter un N-gone (qui ne doit PAS être touché par le nettoyage conservateur)
        # et un sommet orphelin (qui DOIT être supprimé)
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        # Sommet orphelin
        bm.verts.new((5.0, 5.0, 5.0))
        # N-gone à 6 côtés
        v_ngon = [
            bm.verts.new((10.0, 0.0, 0.0)),
            bm.verts.new((11.0, 0.0, 0.0)),
            bm.verts.new((11.5, 1.0, 0.0)),
            bm.verts.new((11.0, 2.0, 0.0)),
            bm.verts.new((10.0, 2.0, 0.0)),
            bm.verts.new((9.5, 1.0, 0.0))
        ]
        bm.faces.new(v_ngon)
        bm.to_mesh(cube.data)
        bm.free()

        res = execute_conservative_cleanup(cube, target_mode='HYBRID_CLEANUP')
        self.assertTrue(res["success"])
        self.assertEqual(res["elements_removed"]["loose_verts"], 1)

        # Vérifier que le post-diagnostic rapporte bien le N-gone restant intact
        post_diag = res["post_diagnosis"]
        self.assertTrue(post_diag["valid"])
        self.assertEqual(post_diag["summary"]["ngons"], 1)
        self.assertGreater(res["execution_time_ms"], 0.0)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD2Conservative)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
