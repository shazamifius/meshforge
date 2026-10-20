"""MeshForge - Tests unitaires et d'intégration ciblés pour la Phase D2.4 (Parois internes).
Vérifie :
1. Détection formelle d'une paroi interne mitoyenne stricte (Strict Internal Wall) entre deux cellules fermées.
2. Distinction rigoureuse d'un aileron / jonction en T (T-Junction) non éligible à la suppression automatique.
3. Suppression sécurisée de la paroi mitoyenne avec guérison complète des arêtes non-manifold et zéro trou créé.
4. Traitement d'une cloison mitoyenne multi-faces (subdivisée en triangles).
5. Protection absolue des ailerons et cloisons ouvertes contre toute suppression intempestive.
6. Préservation intégrale des matériaux, UVs et attributs sur la coque externe restante.
7. Garantie transactionnelle de rollback via MeshSnapshot en cas d'anomalie d'étanchéité.
8. Exécution et protection en mode Édition des opérateurs bpy.ops.meshforge.select_internal_walls et remove_internal_walls.
"""

from __future__ import annotations
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import bpy
import bmesh
import numpy as np

import meshforge
from meshforge.core.internal_walls import (
    classify_non_manifold_faces,
    detect_internal_walls,
    execute_remove_internal_walls
)


def _build_abutting_cubes_mesh() -> bpy.types.Mesh:
    """Construit deux cubes adjacents partageant une face mitoyenne à X=1."""
    mesh = bpy.data.meshes.new("test_abutting_cubes")
    bm = bmesh.new()
    v0 = bm.verts.new((0, 0, 0))
    v1 = bm.verts.new((1, 0, 0))
    v2 = bm.verts.new((1, 1, 0))
    v3 = bm.verts.new((0, 1, 0))
    v4 = bm.verts.new((0, 0, 1))
    v5 = bm.verts.new((1, 0, 1))
    v6 = bm.verts.new((1, 1, 1))
    v7 = bm.verts.new((0, 1, 1))

    v8 = bm.verts.new((2, 0, 0))
    v9 = bm.verts.new((2, 1, 0))
    v10 = bm.verts.new((2, 1, 1))
    v11 = bm.verts.new((2, 0, 1))

    # Cube 1 : faces extérieures
    bm.faces.new((v0, v3, v7, v4))  # X=0
    bm.faces.new((v0, v1, v2, v3))  # Z=0
    bm.faces.new((v4, v7, v6, v5))  # Z=1
    bm.faces.new((v0, v4, v5, v1))  # Y=0
    bm.faces.new((v3, v2, v6, v7))  # Y=1

    # Face mitoyenne partagée à X=1 (Paroi interne !)
    bm.faces.new((v1, v5, v6, v2))

    # Cube 2 : faces extérieures
    bm.faces.new((v8, v11, v10, v9))  # X=2
    bm.faces.new((v1, v8, v9, v2))    # Z=0
    bm.faces.new((v5, v6, v10, v11))  # Z=1
    bm.faces.new((v1, v5, v11, v8))   # Y=0
    bm.faces.new((v2, v9, v10, v6))   # Y=1

    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _build_floor_with_fin_mesh() -> bpy.types.Mesh:
    """Construit un sol plan avec un aileron vertical rattaché en jonction en T."""
    mesh = bpy.data.meshes.new("test_floor_with_fin")
    bm = bmesh.new()
    v0 = bm.verts.new((0, 0, 0))
    v1 = bm.verts.new((1, 0, 0))
    v2 = bm.verts.new((1, 1, 0))
    v3 = bm.verts.new((0, 1, 0))
    v4 = bm.verts.new((2, 0, 0))
    v5 = bm.verts.new((2, 1, 0))

    # Sol : 2 faces partageant l'arête (v1, v2)
    bm.faces.new((v0, v1, v2, v3))
    bm.faces.new((v1, v4, v5, v2))

    # Aileron vertical attaché à l'arête (v1, v2)
    v6 = bm.verts.new((1, 0, 1))
    v7 = bm.verts.new((1, 1, 1))
    bm.faces.new((v1, v6, v7, v2))

    bm.to_mesh(mesh)
    bm.free()
    return mesh


class TestMeshForgePhaseD2_4(unittest.TestCase):
    """Suite de tests ciblés pour la détection et la suppression des parois internes D2.4."""

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)

    def test_01_detect_strict_internal_wall_abutting_cubes(self):
        """1. Vérifie la détection exacte de la paroi interne mitoyenne entre deux cubes."""
        mesh = _build_abutting_cubes_mesh()
        obj = bpy.data.objects.new("test_obj_1", mesh)
        bpy.context.collection.objects.link(obj)

        diag = detect_internal_walls(obj)

        self.assertTrue(diag["valid"])
        self.assertTrue(diag["has_non_manifold"])
        # Doit trouver exactement 1 face mitoyenne stricte (la face à X=1)
        self.assertEqual(len(diag["strict_internal_faces"]), 1)
        self.assertEqual(diag["strict_clusters_count"], 1)
        self.assertEqual(diag["total_non_manifold_edges"], 4)
        self.assertEqual(diag["healed_edges_count"], 4)
        self.assertEqual(len(diag["t_junction_faces"]), 0)

    def test_02_detect_t_junction_fin_not_classified_as_internal_wall(self):
        """2. Vérifie qu'un aileron en T n'est JAMAIS classé comme paroi interne supprimable."""
        mesh = _build_floor_with_fin_mesh()
        obj = bpy.data.objects.new("test_obj_2", mesh)
        bpy.context.collection.objects.link(obj)

        diag = detect_internal_walls(obj)

        self.assertTrue(diag["valid"])
        self.assertTrue(diag["has_non_manifold"])
        # Ne doit comporter AUCUNE paroi interne stricte !
        self.assertEqual(len(diag["strict_internal_faces"]), 0)
        self.assertEqual(diag["strict_clusters_count"], 0)
        # L'aileron doit être détecté dans les t_junction_faces
        self.assertGreaterEqual(len(diag["t_junction_faces"]), 1)
        self.assertEqual(diag["total_non_manifold_edges"], 1)

    def test_03_execute_removal_heals_manifold_without_holes(self):
        """3. Vérifie que la suppression de la face mitoyenne guérit les arêtes sans ouvrir de trou."""
        mesh = _build_abutting_cubes_mesh()
        obj = bpy.data.objects.new("test_obj_3", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        self.assertEqual(len(mesh.polygons), 11)

        res = execute_remove_internal_walls(obj, remove_strict_only=True)

        self.assertTrue(res["success"])
        self.assertFalse(res["rolled_back"])
        self.assertEqual(res["faces_removed"], 1)
        self.assertEqual(res["healed_edges"], 4)
        self.assertEqual(res["boundaries_created"], 0)
        self.assertEqual(len(mesh.polygons), 10)

        # Vérifier sur le maillage Blender final : 0 arête non-manifold, 0 trou
        bm = bmesh.new()
        bm.from_mesh(mesh)
        nm_remaining = [e for e in bm.edges if len(e.link_faces) >= 3]
        boundary_remaining = [e for e in bm.edges if e.is_boundary]
        self.assertEqual(len(nm_remaining), 0)
        self.assertEqual(len(boundary_remaining), 0)
        bm.free()

    def test_04_multi_face_internal_partition(self):
        """4. Vérifie le traitement d'une cloison interne mitoyenne subdivisée en deux triangles."""
        mesh = bpy.data.meshes.new("test_subdivided_wall")
        bm = bmesh.new()
        v0 = bm.verts.new((0, 0, 0))
        v1 = bm.verts.new((1, 0, 0))
        v2 = bm.verts.new((1, 1, 0))
        v3 = bm.verts.new((0, 1, 0))
        v4 = bm.verts.new((0, 0, 1))
        v5 = bm.verts.new((1, 0, 1))
        v6 = bm.verts.new((1, 1, 1))
        v7 = bm.verts.new((0, 1, 1))

        v8 = bm.verts.new((2, 0, 0))
        v9 = bm.verts.new((2, 1, 0))
        v10 = bm.verts.new((2, 1, 1))
        v11 = bm.verts.new((2, 0, 1))

        # Cube 1 extérieur
        bm.faces.new((v0, v3, v7, v4))
        bm.faces.new((v0, v1, v2, v3))
        bm.faces.new((v4, v7, v6, v5))
        bm.faces.new((v0, v4, v5, v1))
        bm.faces.new((v3, v2, v6, v7))

        # Cloison à X=1 formée de 2 triangles
        t1 = bm.faces.new((v1, v5, v6))
        t2 = bm.faces.new((v1, v6, v2))

        # Cube 2 extérieur
        bm.faces.new((v8, v11, v10, v9))
        bm.faces.new((v1, v8, v9, v2))
        bm.faces.new((v5, v6, v10, v11))
        bm.faces.new((v1, v5, v11, v8))
        bm.faces.new((v2, v9, v10, v6))

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_subdiv_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        diag = detect_internal_walls(obj)
        self.assertEqual(len(diag["strict_internal_faces"]), 2)

        res = execute_remove_internal_walls(obj, remove_strict_only=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["faces_removed"], 2)
        self.assertEqual(len(mesh.polygons), 10)

        bm2 = bmesh.new()
        bm2.from_mesh(mesh)
        self.assertEqual(sum(1 for e in bm2.edges if len(e.link_faces) >= 3), 0)
        self.assertEqual(sum(1 for e in bm2.edges if e.is_boundary), 0)
        bm2.free()

    def test_05_fin_is_never_deleted_by_remove_internal_walls(self):
        """5. Vérifie qu'un aileron en T n'est JAMAIS supprimé par execute_remove_internal_walls."""
        mesh = _build_floor_with_fin_mesh()
        obj = bpy.data.objects.new("test_obj_5", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        initial_face_count = len(mesh.polygons)
        res = execute_remove_internal_walls(obj, remove_strict_only=True)

        self.assertTrue(res["success"])
        # Zéro face supprimée pour protéger la géométrie
        self.assertEqual(res["faces_removed"], 0)
        self.assertEqual(len(mesh.polygons), initial_face_count)

    def test_06_preserves_materials_and_uvs_on_outer_faces(self):
        """6. Vérifie la préservation intégrale des matériaux et UVs sur la coque restante."""
        mesh = _build_abutting_cubes_mesh()
        mat_ext = bpy.data.materials.new("MatExt")
        mesh.materials.append(mat_ext)

        bm = bmesh.new()
        bm.from_mesh(mesh)
        uv_layer = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            f.material_index = 0
            for l in f.loops:
                l[uv_layer].uv = (0.25, 0.75)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_obj_6", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        res = execute_remove_internal_walls(obj, remove_strict_only=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["faces_removed"], 1)

        # Vérifier que toutes les 10 faces restantes ont toujours leur matériau et UV
        self.assertEqual(len(mesh.uv_layers), 1)
        self.assertEqual(len(mesh.materials), 1)
        for poly in mesh.polygons:
            self.assertEqual(poly.material_index, 0)

    def test_07_operator_execution_and_edit_mode_protection(self):
        """7. Vérifie l'exécution des opérateurs Blender et la protection en mode Édition."""
        mesh = _build_abutting_cubes_mesh()
        obj = bpy.data.objects.new("test_obj_7", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # A. Opérateur de sélection
        res_sel = bpy.ops.meshforge.select_internal_walls()
        self.assertEqual(res_sel, {'FINISHED'})

        # B. Opérateur de suppression directe sans dialogue (confirm=False)
        res_del = bpy.ops.meshforge.remove_internal_walls(confirm=False)
        self.assertEqual(res_del, {'FINISHED'})
        self.assertEqual(len(mesh.polygons), 10)

        # C. Protection mode Édition
        bpy.ops.object.mode_set(mode='EDIT')
        self.assertFalse(bpy.ops.meshforge.remove_internal_walls.poll())
        with self.assertRaises(RuntimeError):
            bpy.ops.meshforge.remove_internal_walls()

        from meshforge.operators.internal_walls_op import MESHFORGE_OT_remove_internal_walls
        class DummyOp:
            def report(self, t, m): pass
        self.assertEqual(MESHFORGE_OT_remove_internal_walls.execute(DummyOp(), bpy.context), {'CANCELLED'})

        bpy.ops.object.mode_set(mode='OBJECT')

    def test_08_transactional_rollback_on_area_deviation(self):
        """8. Vérifie le déclenchement du rollback automatique si une violation d'invariant survient."""
        mesh = _build_abutting_cubes_mesh()
        obj = bpy.data.objects.new("test_obj_8", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        orig_faces = len(mesh.polygons)

        # Simuler une fonction de classification qui inclurait anormalement une face extérieure
        import meshforge.core.internal_walls as iw
        orig_classify = iw.classify_non_manifold_faces

        def rogue_classify(bm):
            # Déclare la face mitoyenne ET une face extérieure pour forcer un trou dans la surface
            res = orig_classify(bm)
            res["strict_internal_faces"].append(0)  # Face 0 est une face extérieure !
            return res

        try:
            iw.classify_non_manifold_faces = rogue_classify
            res = execute_remove_internal_walls(obj, remove_strict_only=True)
            # Doit détecter la violation (trou créé) et annuler
            self.assertFalse(res["success"])
            self.assertTrue(res["rolled_back"])
            self.assertIn("trou", res["error"].lower())
            # Vérifier que le maillage est intact à 100%
            self.assertEqual(len(mesh.polygons), orig_faces)
        finally:
            iw.classify_non_manifold_faces = orig_classify


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD2_4)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
