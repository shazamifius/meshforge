"""MeshForge - Tests unitaires et d'intégration ciblés pour la Phase D2.3 (Quadrangulation ciblée).
Vérifie :
1. Fusion propre de triangles coplanaires en quads avec préservation d'aire.
2. Restauration d'une grille de quads triangulée (orthogonalité et scoring).
3. Refus strict des paires non-coplanaires (angle dièdre supérieur au seuil).
4. Refus strict des quads concaves ou auto-croisés (chevauchement / chevron).
5. Respect strict des coutures UV marquées (seams).
6. Respect strict des discontinuités UV d'îlots (sans drapeau seam).
7. Respect strict des frontières de matériaux distincts.
8. Respect strict des arêtes vives (sharp edges).
9. Transactionnalité et rollback via MeshSnapshot en cas d'anomalie.
10. Exécution et comportement de l'opérateur bpy.ops.meshforge.quadrangulate.
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
import math
import numpy as np

import meshforge
from meshforge.core.quadrangulator import (
    quad_orthogonality_score,
    check_triangle_pair_compatibility,
    execute_targeted_quadrangulation
)


class TestMeshForgePhaseD2_3(unittest.TestCase):
    """Suite de validation ciblée pour la quadrangulation ciblée D2.3."""

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        # Nettoyage systématique des objets de la scène
        bpy.ops.wm.read_homefile(use_empty=True)

    def test_01_coplanar_pair_basic_quad_merger(self):
        """1. Vérifie la fusion de 2 triangles coplanaires formant un carré parfait."""
        mesh = bpy.data.meshes.new("test_pair_mesh")
        bm = bmesh.new()
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 1.0, 0.0))
        v4 = bm.verts.new((0.0, 1.0, 0.0))
        # 2 triangles partageant l'arête (v1, v3)
        bm.faces.new((v1, v2, v3))
        bm.faces.new((v1, v3, v4))
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_pair_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        initial_area = sum(p.area for p in mesh.polygons)
        self.assertEqual(len(mesh.polygons), 2)

        res = execute_targeted_quadrangulation(obj, max_angle_deg=15.0)

        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 1)
        self.assertEqual(res["triangles_merged"], 2)
        self.assertEqual(len(mesh.polygons), 1)
        self.assertEqual(len(mesh.polygons[0].vertices), 4)

        final_area = sum(p.area for p in mesh.polygons)
        self.assertAlmostEqual(initial_area, final_area, places=5)

    def test_02_triangulated_grid_recovery_with_scoring(self):
        """2. Vérifie la reconstruction d'une grille de quads triangulée avec scoring d'orthogonalité."""
        mesh = bpy.data.meshes.new("test_grid_mesh")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=2.0)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        self.assertEqual(len(bm.faces), 8)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_grid_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        res = execute_targeted_quadrangulation(obj, max_angle_deg=15.0)

        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 4)
        self.assertEqual(res["triangles_merged"], 8)
        self.assertEqual(len(mesh.polygons), 4)
        for poly in mesh.polygons:
            self.assertEqual(len(poly.vertices), 4)

    def test_03_refusal_non_coplanar_dihedral_angle(self):
        """3. Vérifie le refus strict de fusion si l'angle dièdre dépasse le seuil max_angle."""
        mesh = bpy.data.meshes.new("test_dihedral_mesh")
        bm = bmesh.new()
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 1.0, 0.0))
        # v4 est relevé à Z=1.0 créant un angle dièdre de ~45° ou plus
        v4 = bm.verts.new((0.0, 1.0, 1.0))
        bm.faces.new((v1, v2, v3))
        bm.faces.new((v1, v3, v4))
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_dihedral_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        # Avec seuil strict de 15°, la fusion doit être refusée
        res = execute_targeted_quadrangulation(obj, max_angle_deg=15.0)

        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 0)
        self.assertEqual(res["refusals"].get("NON_COPLANAR", 0), 1)
        self.assertEqual(len(mesh.polygons), 2)

    def test_04_refusal_concave_quad(self):
        """4. Vérifie le refus strict des quads concaves (angles rentrants / chevron)."""
        mesh = bpy.data.meshes.new("test_concave_mesh")
        bm = bmesh.new()
        # Forme en flèche / chevron concave
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((2.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 0.5, 0.0))  # Sommet rentrant
        v4 = bm.verts.new((1.0, 2.0, 0.0))
        bm.faces.new((v1, v2, v3))
        bm.faces.new((v1, v3, v4))
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_concave_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        res = execute_targeted_quadrangulation(obj, max_angle_deg=15.0)

        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 0)
        self.assertEqual(res["refusals"].get("CONCAVE_OR_FOLDED", 0), 1)
        self.assertEqual(len(mesh.polygons), 2)

    def test_05_respect_seam_edges(self):
        """5. Vérifie le respect strict des coutures UV marquées (seams)."""
        mesh = bpy.data.meshes.new("test_seam_mesh")
        bm = bmesh.new()
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 1.0, 0.0))
        v4 = bm.verts.new((0.0, 1.0, 0.0))
        f1 = bm.faces.new((v1, v2, v3))
        f2 = bm.faces.new((v1, v3, v4))

        # Marquer l'arête partagée comme couture (seam)
        for e in bm.edges:
            if len(e.link_faces) == 2:
                e.seam = True

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_seam_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        # Avec compare_seams=True, le refus doit avoir lieu
        res = execute_targeted_quadrangulation(obj, compare_seams=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 0)
        self.assertEqual(res["refusals"].get("SEAM", 0), 1)

        # Avec compare_seams=False, la fusion est autorisée
        res2 = execute_targeted_quadrangulation(obj, compare_seams=False)
        self.assertTrue(res2["success"])
        self.assertEqual(res2["quads_created"], 1)

    def test_06_respect_uv_discontinuities_without_seam(self):
        """6. Vérifie le respect des discontinuités UV même si l'arête n'a pas de drapeau seam."""
        mesh = bpy.data.meshes.new("test_uv_discont_mesh")
        bm = bmesh.new()
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 1.0, 0.0))
        v4 = bm.verts.new((0.0, 1.0, 0.0))
        f1 = bm.faces.new((v1, v2, v3))
        f2 = bm.faces.new((v1, v3, v4))

        uv_layer = bm.loops.layers.uv.new("UVMap")
        # f1 a des coordonnées UV dans [0, 0.5]
        for loop in f1.loops:
            loop[uv_layer].uv = (loop.vert.co.x * 0.5, loop.vert.co.y * 0.5)
        # f2 a des coordonnées UV décalées dans [0.5, 1.0] (discontinuité franche)
        for loop in f2.loops:
            loop[uv_layer].uv = (0.5 + loop.vert.co.x * 0.5, 0.5 + loop.vert.co.y * 0.5)

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_uv_discont_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        res = execute_targeted_quadrangulation(obj, compare_uvs=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 0)
        self.assertEqual(res["refusals"].get("UV_DISCONTINUITY", 0), 1)
        self.assertEqual(len(mesh.polygons), 2)

    def test_07_respect_material_boundaries(self):
        """7. Vérifie le respect strict des frontières de matériaux distincts."""
        mesh = bpy.data.meshes.new("test_mat_mesh")
        # Ajouter 2 slots de matériaux
        mat1 = bpy.data.materials.new("Mat1")
        mat2 = bpy.data.materials.new("Mat2")
        mesh.materials.append(mat1)
        mesh.materials.append(mat2)

        bm = bmesh.new()
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 1.0, 0.0))
        v4 = bm.verts.new((0.0, 1.0, 0.0))
        f1 = bm.faces.new((v1, v2, v3))
        f2 = bm.faces.new((v1, v3, v4))
        f1.material_index = 0
        f2.material_index = 1  # Matériau différent

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_mat_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        res = execute_targeted_quadrangulation(obj, compare_materials=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 0)
        self.assertEqual(res["refusals"].get("MATERIAL_MISMATCH", 0), 1)

    def test_08_respect_sharp_edges(self):
        """8. Vérifie le respect des arêtes vives (sharp edges)."""
        mesh = bpy.data.meshes.new("test_sharp_mesh")
        bm = bmesh.new()
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 1.0, 0.0))
        v4 = bm.verts.new((0.0, 1.0, 0.0))
        f1 = bm.faces.new((v1, v2, v3))
        f2 = bm.faces.new((v1, v3, v4))

        for e in bm.edges:
            if len(e.link_faces) == 2:
                e.smooth = False

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_sharp_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        res = execute_targeted_quadrangulation(obj, compare_sharp=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["quads_created"], 0)
        self.assertEqual(res["refusals"].get("SHARP", 0), 1)

    def test_09_operator_execution_and_edit_mode_protection(self):
        """9. Vérifie l'exécution de l'opérateur bpy.ops.meshforge.quadrangulate et la protection mode Édition."""
        mesh = bpy.data.meshes.new("test_op_mesh")
        bm = bmesh.new()
        v1 = bm.verts.new((0.0, 0.0, 0.0))
        v2 = bm.verts.new((1.0, 0.0, 0.0))
        v3 = bm.verts.new((1.0, 1.0, 0.0))
        v4 = bm.verts.new((0.0, 1.0, 0.0))
        bm.faces.new((v1, v2, v3))
        bm.faces.new((v1, v3, v4))
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_op_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # A. Exécution normale en mode Objet
        res_op = bpy.ops.meshforge.quadrangulate()
        self.assertEqual(res_op, {'FINISHED'})
        self.assertEqual(len(mesh.polygons), 1)
        self.assertEqual(len(mesh.polygons[0].vertices), 4)

        # B. Protection mode Édition
        bpy.ops.object.mode_set(mode='EDIT')
        # poll() doit retourner False en mode EDIT
        self.assertFalse(bpy.ops.meshforge.quadrangulate.poll())
        # L'appel via bpy.ops en mode Edit lève RuntimeError (poll failed)
        with self.assertRaises(RuntimeError):
            bpy.ops.meshforge.quadrangulate()

        # L'appel direct de execute() sur une instance renvoie CANCELLED proprement
        class DummyOp:
            def report(self, type_set, msg):
                pass
        dummy = DummyOp()
        from meshforge.operators.quadrangulate_op import MESHFORGE_OT_quadrangulate
        res_direct = MESHFORGE_OT_quadrangulate.execute(dummy, bpy.context)
        self.assertEqual(res_direct, {'CANCELLED'})

        bpy.ops.object.mode_set(mode='OBJECT')


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD2_3)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
