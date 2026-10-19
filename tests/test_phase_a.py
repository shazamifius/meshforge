"""MeshForge - Suite de tests unitaires et d'intégration pour la Phase A.
Exécutable sous Blender 5.2.2 LTS en mode background.
"""

from __future__ import annotations
import bpy
import bmesh
import math
import sys
import unittest
from pathlib import Path

# Ajouter le répertoire parent de meshforge au path pour permettre "import meshforge"
repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.mesh_stats import get_mesh_statistics
from meshforge.core.repair_pipeline import execute_repair
from meshforge.core.manifold import execute_manifold
from meshforge.core.dissolve import execute_dissolve
from meshforge.core.topology import execute_topology
from meshforge.core.normals import execute_normals
from meshforge.core.object_data import execute_object_data
from meshforge.core.pipeline import run_meshforge_pipeline


class TestMeshForgePhaseA(unittest.TestCase):
    """Vérifie l'ensemble des critères d'acceptation de la Phase A."""

    @classmethod
    def setUpClass(cls):
        # Enregistrement propre de l'add-on
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        # Nettoyage de la scène entre chaque test
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_01_addon_registration(self):
        """1. Vérifie que l'add-on s'installe et s'active sans erreur dans Blender."""
        self.assertTrue(hasattr(bpy.types.Scene, "meshforge_settings"))
        # Vérifier que les opérateurs sont enregistrés
        self.assertTrue(hasattr(bpy.ops.meshforge, "optimize"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "analyze"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "repair"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "manifold"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "dissolve"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "topology"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "normals"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "object_data"))
        self.assertTrue(hasattr(bpy.ops.meshforge, "restore"))

    def test_02_mesh_statistics_accuracy(self):
        """2. Vérifie le calcul exact des faces polygonales et triangles estimés."""
        # Cube = 6 faces quad = 12 triangles estimés
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        stats = get_mesh_statistics(cube)

        self.assertTrue(stats["valid"])
        self.assertEqual(stats["vertices"], 8)
        self.assertEqual(stats["edges"], 12)
        self.assertEqual(stats["faces"], 6)
        self.assertEqual(stats["estimated_triangles"], 12)
        self.assertEqual(stats["quad_faces"], 6)
        self.assertEqual(stats["tri_faces"], 0)
        self.assertEqual(stats["ngon_faces"], 0)

    def test_03_repair_operations(self):
        """3. Vérifie le nettoyage des doublons, éléments isolés et faces nulles."""
        # Création d'un maillage altéré
        mesh = bpy.data.meshes.new("DirtyMesh")
        obj = bpy.data.objects.new("DirtyObject", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        bm = bmesh.new()
        # 1 face normale (4 sommets)
        v0 = bm.verts.new((-1, -1, 0))
        v1 = bm.verts.new((1, -1, 0))
        v2 = bm.verts.new((1, 1, 0))
        v3 = bm.verts.new((-1, 1, 0))
        bm.faces.new((v0, v1, v2, v3))

        # 2 sommets superposés (doublons à fusionner)
        bm.verts.new((0.00001, 0.0, 0))
        bm.verts.new((0.00002, 0.0, 0))

        # 2 sommets lâches (loose verts)
        bm.verts.new((5, 5, 0))
        bm.verts.new((6, 6, 0))

        # 1 arête lâche (loose edge)
        v_l1 = bm.verts.new((10, 10, 0))
        v_l2 = bm.verts.new((11, 11, 0))
        bm.edges.new((v_l1, v_l2))

        # 1 face dégénérée d'aire quasi-nulle
        v_d1 = bm.verts.new((0, 0, 0))
        v_d2 = bm.verts.new((0.0000001, 0, 0))
        v_d3 = bm.verts.new((0, 0.0000001, 0))
        bm.faces.new((v_d1, v_d2, v_d3))

        bm.to_mesh(mesh)
        bm.free()

        # Exécuter repair
        props = bpy.context.scene.meshforge_settings
        props.repair_loose_geometry = True
        props.loose_verts = True
        props.loose_edges = True
        props.repair_doubles = True
        props.doubles_tolerance = 0.001
        props.repair_zero_faces = True

        res = execute_repair(obj, props)
        self.assertEqual(res["status"], "SUCCESS")

        stats = get_mesh_statistics(obj)
        # Les sommets isolés et l'arête isolée doivent avoir disparu
        self.assertEqual(stats["loose_verts"], 0)
        self.assertEqual(stats["loose_edges"], 0)
        # La face dégénérée doit avoir disparu
        self.assertEqual(stats["zero_area_faces"], 0)

    def test_04_manifold_wire_cleanup(self):
        """4. Vérifie la suppression des géométries filaires (wire)."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        # Ajouter une arête filaire
        bm = bmesh.new()
        bm.from_mesh(plane.data)
        v_w1 = bm.verts.new((2, 0, 0))
        v_w2 = bm.verts.new((3, 0, 0))
        bm.edges.new((v_w1, v_w2))
        bm.to_mesh(plane.data)
        bm.free()

        props = bpy.context.scene.meshforge_settings
        props.manifold_mode = 'CAREFUL'
        props.remove_wire_geometry = True
        props.fill_holes = False

        res = execute_manifold(plane, props)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreaterEqual(res["wire_removed"], 1)

    def test_05_dissolve_planar_regions(self):
        """5. Vérifie la simplification par dissolution coplanaire."""
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        # Subdiviser le plan en grille 4x4 (16 faces coplanaires)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=3)
        bpy.ops.object.mode_set(mode='OBJECT')

        self.assertEqual(len(plane.data.polygons), 16)

        props = bpy.context.scene.meshforge_settings
        props.dissolve_angle = 5.0
        props.preserve_boundaries = True

        res = execute_dissolve(plane, props)
        self.assertEqual(res["status"], "SUCCESS")
        # Les faces intérieures coplanaires ont été dissoutes
        self.assertEqual(len(plane.data.polygons), 1)

    def test_06_topology_modes(self):
        """6. Vérifie les options de topologie (KEEP, TRIS, QUADS)."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        props = bpy.context.scene.meshforge_settings

        # Mode KEEP : aucun changement
        props.topology_mode = 'KEEP'
        execute_topology(cube, props)
        self.assertEqual(len(cube.data.polygons), 6)

        # Mode TRIS : conversion en 12 triangles
        props.topology_mode = 'TRIS'
        execute_topology(cube, props)
        self.assertEqual(len(cube.data.polygons), 12)

        # Mode QUADS : reconversion en 6 quads
        props.topology_mode = 'QUADS'
        execute_topology(cube, props)
        self.assertEqual(len(cube.data.polygons), 6)

    def test_07_normals_management(self):
        """7. Vérifie le recalcul des normales et l'ombrage par angle sous Blender 5.x."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        props = bpy.context.scene.meshforge_settings
        props.recalculate_normals = True
        props.apply_auto_smooth = True
        props.auto_smooth_angle = 30.0

        res = execute_normals(cube, props)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["recalculated"])
        self.assertTrue(res["auto_smooth_applied"])

    def test_08_object_data_cleaning(self):
        """8. Vérifie la fusion des slots matériaux dupliqués et suppression des vertex groups vides."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # Ajouter deux slots pointant vers le même matériau
        mat = bpy.data.materials.new(name="SharedMat")
        cube.data.materials.append(mat)
        cube.data.materials.append(mat)
        self.assertEqual(len(cube.material_slots), 2)

        # Ajouter un vertex group vide (aucun sommet assigné)
        vg = cube.vertex_groups.new(name="EmptyGroup")
        self.assertEqual(len(cube.vertex_groups), 1)

        props = bpy.context.scene.meshforge_settings
        props.clean_material_doubles = True
        props.clean_empty_vertex_groups = True

        res = execute_object_data(cube, props)
        self.assertEqual(res["status"], "SUCCESS")
        # Le slot en doublon a été fusionné (il n'en reste qu'1)
        self.assertEqual(len(cube.material_slots), 1)
        # Le vertex group vide a été supprimé
        self.assertEqual(len(cube.vertex_groups), 0)

    def test_09_full_pipeline_non_destructive(self):
        """9. Vérifie le pipeline complet en mode non-destructif."""
        bpy.ops.mesh.primitive_cube_add()
        source_obj = bpy.context.active_object
        source_name = source_obj.name

        # Subdiviser pour avoir de la géométrie coplanaire
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=2)
        bpy.ops.object.mode_set(mode='OBJECT')

        props = bpy.context.scene.meshforge_settings
        props.create_new_object = True
        props.hide_original = True
        props.enable_repair = True
        props.enable_manifold = True
        props.enable_dissolve = True
        props.enable_topology = False
        props.enable_normals = True
        props.enable_object_data = True

        report = run_meshforge_pipeline(source_obj, props)
        self.assertTrue(report["success"])

        # Vérifier que l'objet source existe toujours intact et est masqué
        orig = bpy.data.objects.get(source_name)
        self.assertIsNotNone(orig)
        self.assertTrue(orig.hide_get())

        # Vérifier que le résultat existe avec le suffixe
        result_name = f"{source_name}_MF_Optimized"
        res_obj = bpy.data.objects.get(result_name)
        self.assertIsNotNone(res_obj)

        # Vérifier la réduction
        self.assertGreater(report["reduction_percentage"], 0.0)
        self.assertGreater(report["total_duration"], 0.0)

    def test_10_safe_error_handling(self):
        """10. Vérifie que des entrées invalides ne font pas crasher Blender."""
        props = bpy.context.scene.meshforge_settings
        # Passer None
        report = run_meshforge_pipeline(None, props)
        self.assertFalse(report["success"])
        self.assertGreater(len(report["errors"]), 0)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseA)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
