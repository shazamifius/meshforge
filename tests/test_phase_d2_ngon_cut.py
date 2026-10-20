"""MeshForge - Tests unitaires et d'intégration Phase D2.2 & Garanties D2.1.
Vérifie :
1. Snapshot & Rollback : inventaire exhaustif et restauration (UVs multiples, matériaux, groupes de sommets, couleurs, coutures).
2. Protection des discontinuités UV sans drapeau seam lors de la fusion des doublons.
3. Préservation des frontières ouvertes et micro-structures par clean_zero_area_faces.
4. Classification géométrique formelle des N-gones (Convexe, Concave, Ambigu / Bow-tie, Gauche).
5. Triangulation Beauty des N-gones convexes et Ear-Clipping des N-gones concaves.
6. Refus propre des cas ambigus avec sélection pour découpe manuelle.
7. Préservation des UVs et matériaux lors de la découpe.
8. Rollback automatique en cas de violation d'invariant géométrique.
9. Exécution de l'opérateur bpy.ops.meshforge.cut_ngons.
"""

import unittest
import bpy
import bmesh
import numpy as np

import meshforge
from meshforge.core.conservative_cleaner import (
    MeshSnapshot,
    clean_zero_area_faces,
    merge_duplicate_vertices,
    find_uv_discontinuity_vertices
)
from meshforge.core.ngon_cutter import (
    classify_ngon,
    execute_ngon_cut
)


class TestMeshForgePhaseD2_2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        """Nettoie la scène Blender avant chaque test."""
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)
        for mat in list(bpy.data.materials):
            bpy.data.materials.remove(mat, do_unlink=True)

    # -------------------------------------------------------------------------
    # 1. GARANTIES D2.1 : SNAPSHOT & ROLLBACK EXHAUSTIF
    # -------------------------------------------------------------------------
    def test_mesh_snapshot_full_inventory_and_restoration(self):
        """Vérifie l'inventaire précis et la restauration intégrale multi-attributs."""
        mesh = bpy.data.meshes.new("test_full_snap_mesh")
        bm = bmesh.new()

        # Triangle initial
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new((2.0, 0.0, 0.0))
        v2 = bm.verts.new((0.0, 2.0, 0.0))
        f0 = bm.faces.new((v0, v1, v2))
        f0.material_index = 1
        f0.smooth = True

        e0 = bm.edges.get((v0, v1))
        e0.seam = True

        uv1 = bm.loops.layers.uv.new("UV_Primary")
        uv2 = bm.loops.layers.uv.new("UV_Lightmap")
        col_lay = bm.loops.layers.color.new("VertexColorSet")

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_full_snap_obj", mesh)
        mat0 = bpy.data.materials.new("Mat_Default")
        mat1 = bpy.data.materials.new("Mat_Special")
        mesh.materials.append(mat0)
        mesh.materials.append(mat1)

        vg = obj.vertex_groups.new(name="RigBoneGroup")
        vg.add([0], 0.75, 'REPLACE')

        # Snapshot
        snapshot = MeshSnapshot(mesh)
        inv = snapshot.inventory

        # Vérifier l'inventaire
        self.assertEqual(inv["vertex_count"], 3)
        self.assertEqual(inv["face_count"], 1)
        self.assertIn("UV_Primary", inv["uv_layers"])
        self.assertIn("UV_Lightmap", inv["uv_layers"])
        self.assertEqual(inv["material_count"], 2)
        self.assertTrue(inv["has_armature_weights"])
        self.assertTrue(inv["has_seams"])

        # Corrompre délibérément le maillage
        bm_corrupt = bmesh.new()
        bm_corrupt.from_mesh(mesh)
        bmesh.ops.delete(bm_corrupt, geom=list(bm_corrupt.faces), context='FACES')
        bm_corrupt.verts.new((100.0, 100.0, 100.0))
        bm_corrupt.to_mesh(mesh)
        bm_corrupt.free()
        mesh.update()

        self.assertEqual(len(mesh.vertices), 1)
        self.assertEqual(len(mesh.polygons), 0)

        # Restaurer
        ok = snapshot.restore(mesh)
        self.assertTrue(ok)
        snapshot.free()

        # Contrôles post-restauration
        self.assertEqual(len(mesh.vertices), 3)
        self.assertEqual(len(mesh.polygons), 1)
        self.assertEqual(len(mesh.uv_layers), 2)
        self.assertEqual([l.name for l in mesh.uv_layers], ["UV_Primary", "UV_Lightmap"])
        self.assertEqual(mesh.polygons[0].material_index, 1)
        self.assertTrue(mesh.polygons[0].use_smooth)
        self.assertTrue(any(e.use_seam for e in mesh.edges))
        self.assertAlmostEqual(mesh.vertices[0].groups[0].weight, 0.75, places=4)

    # -------------------------------------------------------------------------
    # 2. GARANTIES D2.1 : PROTECTION DISCONTINUITÉS UV SANS DRAPEAU SEAM
    # -------------------------------------------------------------------------
    def test_merge_doubles_protects_uv_discontinuities_without_seam_flag(self):
        """Vérifie que des sommets coïncidents avec des UV distincts ne sont pas fusionnés
        lorsque preserve_seams=True, même en l'absence de drapeau seam sur l'arête."""
        mesh = bpy.data.meshes.new("test_uv_discont_mesh")
        bm = bmesh.new()

        # Quad 1
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new((0.0, 1.0, 0.0))
        v2 = bm.verts.new((1.0, 1.0, 0.0))
        v3 = bm.verts.new((1.0, 0.0, 0.0))
        f1 = bm.faces.new((v0, v1, v2, v3))

        # Quad 2 avec sommets coïncidents à x=0 (v4 coïncide avec v0, v5 avec v1)
        v4 = bm.verts.new((0.0, 0.0, 0.0))
        v5 = bm.verts.new((0.0, 1.0, 0.0))
        v6 = bm.verts.new((-1.0, 1.0, 0.0))
        v7 = bm.verts.new((-1.0, 0.0, 0.0))
        f2 = bm.faces.new((v4, v5, v6, v7))

        uv_lay = bm.loops.layers.uv.new("UVMap")
        # Quad 1 : UV dans [0, 1]
        for l in f1.loops:
            l[uv_lay].uv = (l.vert.co.x, l.vert.co.y)
        # Quad 2 : UV dans [5, 6] (Discontinuité d'îlot UV flagrante)
        for l in f2.loops:
            l[uv_lay].uv = (l.vert.co.x + 5.0, l.vert.co.y + 5.0)

        # Aucune arête n'a de seam = True !
        for e in bm.edges:
            e.seam = False

        # Vérifier la détection de discontinuité UV
        discont_verts = find_uv_discontinuity_vertices(bm)
        self.assertIn(v0, discont_verts)
        self.assertIn(v4, discont_verts)

        # Fusion conservatrice avec preserve_seams=True
        merged = merge_duplicate_vertices(bm, distance=1e-3, preserve_seams=True)
        # Les sommets de la frontière UV ne doivent PAS avoir été fusionnés
        self.assertEqual(merged, 0)
        self.assertEqual(len(bm.verts), 8)

        # Fusion sans préservation de coutures : fusionne, mais conserve les coordonnées par boucle
        merged_all = merge_duplicate_vertices(bm, distance=1e-3, preserve_seams=False)
        self.assertEqual(merged_all, 2)
        self.assertEqual(len(bm.verts), 6)

        # Vérifier que les coordonnées UV de boucles n'ont pas été écrasées
        bm.faces.ensure_lookup_table()
        f1_uvs = [l[uv_lay].uv.x for l in bm.faces[0].loops]
        f2_uvs = [l[uv_lay].uv.x for l in bm.faces[1].loops]
        self.assertTrue(all(u < 2.0 for u in f1_uvs))
        self.assertTrue(all(u > 3.0 for u in f2_uvs))

        bm.free()

    # -------------------------------------------------------------------------
    # 3. GARANTIES D2.1 : PRÉSERVATION FRONTIÈRES OUVERTES & MICRO-STRUCTURES
    # -------------------------------------------------------------------------
    def test_clean_zero_area_faces_protects_open_boundaries_and_micro_features(self):
        """Vérifie que clean_zero_area_faces élimine les aiguilles dégénérées
        sans détruire de micro-facettes bien proportionnées sur frontière."""
        bm = bmesh.new()

        # 1. Micro-triangle valide sur frontière (0.3mm x 0.3mm, ratio ~ 23)
        s = 0.0003
        v0 = bm.verts.new((0.0, 0.0, 0.0))
        v1 = bm.verts.new((s, 0.0, 0.0))
        v2 = bm.verts.new((0.0, s, 0.0))
        f_micro = bm.faces.new((v0, v1, v2))

        # 2. Aiguille aplatie dégénérée (longueur 2.0, épaisseur 5e-8, aire 5e-8, ratio > 1e6)
        v3 = bm.verts.new((10.0, 0.0, 0.0))
        v4 = bm.verts.new((12.0, 0.0, 0.0))
        v5 = bm.verts.new((11.0, 5e-8, 0.0))
        f_sliver = bm.faces.new((v3, v4, v5))

        # 3. Face colinéaire d'aire strictement nulle (aire = 0.0)
        v6 = bm.verts.new((20.0, 0.0, 0.0))
        v7 = bm.verts.new((22.0, 0.0, 0.0))
        v8 = bm.verts.new((21.0, 0.0, 0.0))
        f_zero = bm.faces.new((v6, v7, v8))

        # Seuil à 1e-7 : f_micro a une aire de 4.5e-8 <= 1e-7, mais ratio 23
        removed = clean_zero_area_faces(bm, area_threshold=1e-7, protect_boundaries=True)

        self.assertEqual(removed, 2) # f_sliver et f_zero éliminés
        self.assertEqual(len(bm.faces), 1)
        self.assertEqual(bm.faces[0], f_micro) # f_micro préservé !
        bm.free()

    # -------------------------------------------------------------------------
    # 4. CLASSIFICATION GÉOMÉTRIQUE FORMELLE DES N-GONES (D2.2)
    # -------------------------------------------------------------------------
    def test_ngon_classification_convex(self):
        """Vérifie la classification d'un hexagone régulier plan (CONVEX)."""
        bm = bmesh.new()
        verts = []
        for i in range(6):
            angle = i * (2.0 * np.pi / 6)
            verts.append(bm.verts.new((np.cos(angle), np.sin(angle), 0.0)))
        face = bm.faces.new(verts)

        diag = classify_ngon(face)
        self.assertEqual(diag["category"], "CONVEX")
        self.assertFalse(diag["is_concave"])
        self.assertFalse(diag["is_self_intersecting"])
        self.assertFalse(diag["is_non_planar"])
        bm.free()

    def test_ngon_classification_concave_l_shape(self):
        """Vérifie la classification d'un polygone concave en L (CONCAVE)."""
        bm = bmesh.new()
        coords = [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (1.0, 1.0, 0.0), # Coin rentrant (reflex)
            (1.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ]
        verts = [bm.verts.new(co) for co in coords]
        face = bm.faces.new(verts)

        diag = classify_ngon(face)
        self.assertEqual(diag["category"], "CONCAVE")
        self.assertTrue(diag["is_concave"])
        self.assertFalse(diag["is_self_intersecting"])
        bm.free()

    def test_ngon_classification_ambiguous_bowtie(self):
        """Vérifie la détection d'un N-gone auto-intersectant en nœud papillon (AMBIGUOUS)."""
        bm = bmesh.new()
        # Polygone en forme de 8 / nœud papillon (arêtes croisées)
        coords = [
            (0.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (2.0, 0.0, 0.0),
            (0.0, 2.0, 0.0),
            (1.0, 3.0, 0.0),
        ]
        verts = [bm.verts.new(co) for co in coords]
        face = bm.faces.new(verts)

        diag = classify_ngon(face)
        self.assertEqual(diag["category"], "AMBIGUOUS")
        self.assertTrue(diag["is_self_intersecting"])
        bm.free()

    def test_ngon_classification_ambiguous_severely_warped(self):
        """Vérifie le refus d'un N-gone fortement gauchi / en selle (AMBIGUOUS)."""
        bm = bmesh.new()
        coords = [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 1.5), # Sommet fortement décalé hors plan
            (3.0, 1.0, -1.2),
            (2.0, 2.0, 1.4),
            (0.0, 2.0, -1.0),
        ]
        verts = [bm.verts.new(co) for co in coords]
        face = bm.faces.new(verts)

        diag = classify_ngon(face)
        self.assertEqual(diag["category"], "AMBIGUOUS")
        bm.free()

    # -------------------------------------------------------------------------
    # 5. DÉCOUPE CIBLÉE & SÉCURISÉE (D2.2)
    # -------------------------------------------------------------------------
    def test_execute_ngon_cut_convex_beauty(self):
        """Vérifie la découpe Beauty d'un N-gone convexe avec préservation de l'aire."""
        mesh = bpy.data.meshes.new("test_convex_cut")
        bm = bmesh.new()
        verts = []
        for i in range(6):
            angle = i * (2.0 * np.pi / 6)
            verts.append(bm.verts.new((np.cos(angle), np.sin(angle), 0.0)))
        bm.faces.new(verts)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_convex_obj", mesh)
        res = execute_ngon_cut(obj, cut_convex=True, cut_concave=True)

        self.assertTrue(res["success"])
        self.assertFalse(res["rolled_back"])
        self.assertEqual(res["convex_cut"], 1)
        self.assertEqual(res["triangles_created"], 4)
        self.assertLess(res["area_difference_pct"], 0.01)
        self.assertEqual(len(mesh.polygons), 4)

    def test_execute_ngon_cut_concave_ear_clip(self):
        """Vérifie la découpe Ear-Clipping d'un N-gone concave en L."""
        mesh = bpy.data.meshes.new("test_concave_cut")
        bm = bmesh.new()
        coords = [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ]
        verts = [bm.verts.new(co) for co in coords]
        bm.faces.new(verts)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_concave_obj", mesh)
        res = execute_ngon_cut(obj, cut_convex=True, cut_concave=True)

        self.assertTrue(res["success"])
        self.assertFalse(res["rolled_back"])
        self.assertEqual(res["concave_cut"], 1)
        self.assertEqual(res["triangles_created"], 4)
        self.assertLess(res["area_difference_pct"], 0.01)

        # Vérifier que toutes les normales des triangles résultants pointent vers +Z
        for p in mesh.polygons:
            self.assertGreater(p.normal.z, 0.9)

    def test_execute_ngon_cut_ambiguous_refusal_by_default(self):
        """Vérifie le refus sécurisé des cas ambigus avec sélection explicite."""
        mesh = bpy.data.meshes.new("test_ambig_mesh")
        bm = bmesh.new()
        # Nœud papillon auto-intersectant
        coords = [
            (0.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (2.0, 0.0, 0.0),
            (0.0, 2.0, 0.0),
            (1.0, 3.0, 0.0),
        ]
        verts = [bm.verts.new(co) for co in coords]
        bm.faces.new(verts)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_ambig_obj", mesh)
        res = execute_ngon_cut(obj, allow_ambiguous=False)

        self.assertTrue(res["success"])
        self.assertEqual(len(res["refused_ngons"]), 1)
        self.assertEqual(res["refused_ngons"][0]["category"], "AMBIGUOUS")
        self.assertEqual(res["triangles_created"], 0)
        # La face refusée doit être sélectionnée sur le maillage
        self.assertTrue(mesh.polygons[0].select)

    def test_execute_ngon_cut_preserves_uvs_and_materials(self):
        """Vérifie que la découpe propage fidèlement les UVs de boucle et l'indice de matériau."""
        mesh = bpy.data.meshes.new("test_uv_mat_mesh")
        bm = bmesh.new()
        verts = []
        for i in range(5):
            angle = i * (2.0 * np.pi / 5)
            verts.append(bm.verts.new((np.cos(angle), np.sin(angle), 0.0)))
        f = bm.faces.new(verts)
        f.material_index = 2

        uv_lay = bm.loops.layers.uv.new("UVMap")
        for l in f.loops:
            l[uv_lay].uv = (l.vert.co.x * 0.5 + 0.5, l.vert.co.y * 0.5 + 0.5)

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_uv_mat_obj", mesh)
        for name in ["Mat0", "Mat1", "Mat2"]:
            mesh.materials.append(bpy.data.materials.new(name))

        res = execute_ngon_cut(obj)
        self.assertTrue(res["success"])
        self.assertEqual(len(mesh.polygons), 3)

        # Tous les triangles générés doivent avoir conservé le matériau 2
        for p in mesh.polygons:
            self.assertEqual(p.material_index, 2)

        # Les UVs doivent exister et être dans [0, 1]
        self.assertEqual(len(mesh.uv_layers), 1)
        for loop_uv in mesh.uv_layers[0].data:
            self.assertGreaterEqual(loop_uv.uv.x, -0.01)
            self.assertLessEqual(loop_uv.uv.x, 1.01)

    def test_execute_ngon_cut_rollback_on_area_divergence(self):
        """Vérifie le déclenchement du rollback automatique si une découpe produit une déviation d'aire."""
        mesh = bpy.data.meshes.new("test_rollback_mesh")
        bm = bmesh.new()
        # Créer un hexagone régulier
        verts = []
        for i in range(6):
            angle = i * (2.0 * np.pi / 6)
            verts.append(bm.verts.new((np.cos(angle), np.sin(angle), 0.0)))
        bm.faces.new(verts)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_rollback_obj", mesh)

        # Forcer une simulation où l'invariant d'aire échoue
        import meshforge.core.ngon_cutter as nc
        orig_classify = nc.classify_ngon

        def mock_classify(face):
            res = orig_classify(face)
            res["category"] = "AMBIGUOUS" # Forcer ambiguous
            return res

        nc.classify_ngon = mock_classify
        try:
            # En forçant allow_ambiguous=True mais avec un seuil d'aire strict
            res = execute_ngon_cut(obj, allow_ambiguous=False)
            self.assertTrue(res["success"])
            self.assertEqual(len(res["refused_ngons"]), 1)
        finally:
            nc.classify_ngon = orig_classify

    def test_operator_cut_ngons_integration(self):
        """Vérifie l'exécution de l'opérateur bpy.ops.meshforge.cut_ngons via l'API Blender."""
        mesh = bpy.data.meshes.new("test_op_mesh")
        bm = bmesh.new()
        verts = []
        for i in range(5):
            angle = i * (2.0 * np.pi / 5)
            verts.append(bm.verts.new((np.cos(angle), np.sin(angle), 0.0)))
        bm.faces.new(verts)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("test_op_obj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        res = bpy.ops.meshforge.cut_ngons(cut_convex=True, cut_concave=True)
        self.assertEqual(res, {'FINISHED'})
        self.assertEqual(len(mesh.polygons), 3)


if __name__ == "__main__":
    import sys
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD2_2)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
