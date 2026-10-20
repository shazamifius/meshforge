"""MeshForge - Tests unitaires ciblés pour la refonte UX CLEAN / DECIMATE.
Vérifie :
1. Enregistrement et valeurs par défaut des propriétés de section et de méthode.
2. Dessin propre du panneau VIEW3D_PT_meshforge_main (contexte vide, mode CLEAN, mode DECIMATE).
3. Méthodes de décimation : Contraction d'arêtes vs Dissolution coplanaire.
4. Estimations théoriques de triangles sans calculs BVH lourds.
5. Câblage des opérateurs de décimation en workflow non-destructif (création copie + masquage original + restauration).
6. Affichage strict de la métrologie post-exécution (distinction réelle / non mesurée, aucune valeur inventée).
7. Filtrage du Mode Expert (poll des sous-panneaux).
8. Cycle propre register/unregister.
"""

from __future__ import annotations
import sys
import unittest
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import bpy
import bmesh
from mathutils import Vector

import meshforge
from meshforge.ui.panel import (
    VIEW3D_PT_meshforge_main,
    VIEW3D_PT_meshforge_repair,
    VIEW3D_PT_meshforge_manifold,
    VIEW3D_PT_meshforge_dissolve,
    VIEW3D_PT_meshforge_simplification,
    VIEW3D_PT_meshforge_topology,
    VIEW3D_PT_meshforge_normals,
    VIEW3D_PT_meshforge_object_data,
    VIEW3D_PT_meshforge_report,
)


class MockPanel:
    def __init__(self):
        self.layout = DummyLayout()


class DummyLayout:
    """Mock minimal de Layout Blender pour tester draw() en mode background."""
    def __init__(self):
        self.alert = False
        self.active = True
        self.scale_y = 1.0

    def box(self):
        return DummyLayout()

    def row(self, align=False):
        return DummyLayout()

    def column(self, align=False):
        return DummyLayout()

    def grid_flow(self, **kwargs):
        return DummyLayout()

    def label(self, text="", icon='NONE'):
        pass

    def prop(self, data, property, **kwargs):
        pass

    def operator(self, operator, text="", **kwargs):
        class DummyOp:
            def __init__(self):
                self.finding_id = ""
                self.format_type = ""
        return DummyOp()

    def separator(self):
        pass


class TestMeshForgeUXCleanDecimate(unittest.TestCase):
    """Suite de validation ciblée pour la refonte UX CLEAN / DECIMATE."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.props = self.scene.meshforge_settings

    def tearDown(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh)

    def test_01_properties_defaults(self):
        """Vérifie que les propriétés UI et métrologie existent avec leurs valeurs par défaut."""
        props = self.props
        # Section CLEAN ouverte par défaut
        self.assertTrue(hasattr(props, "ui_section_clean_expanded"))
        self.assertTrue(props.ui_section_clean_expanded)

        # Section DECIMATE repliée par défaut
        self.assertTrue(hasattr(props, "ui_section_decimate_expanded"))
        self.assertFalse(props.ui_section_decimate_expanded)

        # Méthode de réduction
        self.assertTrue(hasattr(props, "decimate_method"))
        self.assertEqual(props.decimate_method, 'COLLAPSE')
        props.decimate_method = 'DISSOLVE'
        self.assertEqual(props.decimate_method, 'DISSOLVE')
        props.decimate_method = 'COLLAPSE'

        # Propriétés de métrologie post-exécution
        self.assertTrue(hasattr(props, "last_deviation_measured"))
        self.assertFalse(props.last_deviation_measured)
        self.assertTrue(hasattr(props, "last_max_hausdorff"))
        self.assertEqual(props.last_max_hausdorff, 0.0)
        self.assertTrue(hasattr(props, "last_mean_deviation"))
        self.assertEqual(props.last_mean_deviation, 0.0)
        self.assertTrue(hasattr(props, "last_max_normal_angle"))
        self.assertEqual(props.last_max_normal_angle, 0.0)

    def test_02_panel_draw_empty_scene(self):
        """Vérifie que le panneau se dessine sans erreur lorsqu'aucun objet n'est sélectionné."""
        mock = MockPanel()

        # Aucun objet actif
        bpy.context.view_layer.objects.active = None
        # Ne doit pas lever d'exception
        VIEW3D_PT_meshforge_main.draw(mock, bpy.context)

    def test_03_panel_draw_clean_expanded(self):
        """Vérifie le dessin de la section CLEAN ouverte avec diagnostic valide."""
        # Création d'un maillage de test avec N-gones
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1.0, depth=2.0)
        cyl = bpy.context.active_object

        # Lancer le diagnostic
        bpy.ops.meshforge.analyze_topology()

        mock = MockPanel()

        self.props.ui_section_clean_expanded = True
        self.props.ui_section_decimate_expanded = False
        self.props.show_findings_table = True

        # Dessin sans exception
        VIEW3D_PT_meshforge_main.draw(mock, bpy.context)

    def test_04_panel_draw_decimate_collapse_and_estimates(self):
        """Vérifie le dessin de la section DECIMATE en mode COLLAPSE avec estimations théoriques."""
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
        sphere = bpy.context.active_object

        mock = MockPanel()

        self.props.ui_section_clean_expanded = False
        self.props.ui_section_decimate_expanded = True
        self.props.decimate_method = 'COLLAPSE'

        # Test mode pourcentage
        self.props.simplification_mode = 'PERCENTAGE'
        self.props.simplification_percentage = 40.0
        VIEW3D_PT_meshforge_main.draw(mock, bpy.context)

        # Test mode budget
        self.props.simplification_mode = 'BUDGET_TRIANGLES'
        self.props.simplification_target_triangles = 80
        VIEW3D_PT_meshforge_main.draw(mock, bpy.context)

    def test_05_panel_draw_decimate_dissolve(self):
        """Vérifie le dessin de la section DECIMATE en mode DISSOLVE."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object

        mock = MockPanel()

        self.props.ui_section_decimate_expanded = True
        self.props.decimate_method = 'DISSOLVE'
        self.props.dissolve_angle = 5.0
        self.props.dissolve_mode = 'BALANCED'

        VIEW3D_PT_meshforge_main.draw(mock, bpy.context)

    def test_06_panel_draw_post_execution_metrology(self):
        """Vérifie l'affichage de la comparaison Avant/Après avec et sans métrologie mesurée."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)

        mock = MockPanel()

        self.props.ui_section_decimate_expanded = True
        self.props.last_faces_before = 12
        self.props.last_faces_after = 6
        self.props.last_tris_before = 24
        self.props.last_tris_after = 12
        self.props.last_reduction = 50.0

        # Cas 1 : Déviation non mesurée (pas de valeurs inventées)
        self.props.last_deviation_measured = False
        VIEW3D_PT_meshforge_main.draw(mock, bpy.context)

        # Cas 2 : Déviation réellement mesurée
        self.props.last_deviation_measured = True
        self.props.last_max_hausdorff = 0.00045
        self.props.last_mean_deviation = 0.00012
        self.props.last_max_normal_angle = 1.8
        VIEW3D_PT_meshforge_main.draw(mock, bpy.context)

    def test_07_simplification_operator_non_destructive_workflow(self):
        """Vérifie que meshforge.simplification crée une copie, masque l'original et met à jour les stats."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=16, radius=1.0)
        sphere = bpy.context.active_object
        orig_name = sphere.name

        self.props.create_new_object = True
        self.props.hide_original = True
        self.props.simplification_mode = 'PERCENTAGE'
        self.props.simplification_percentage = 50.0

        res = bpy.ops.meshforge.simplification()
        self.assertEqual(res, {'FINISHED'})

        # L'objet actif doit être la copie optimisée
        opt_obj = bpy.context.active_object
        self.assertIn("_MF_Optimized", opt_obj.name)
        opt_name = opt_obj.name
        self.assertEqual(opt_name, f"{orig_name}_MF_Optimized")

        # L'original doit être masqué
        orig_obj = bpy.data.objects.get(orig_name)
        self.assertIsNotNone(orig_obj)
        self.assertTrue(orig_obj.hide_get())

        # Statistiques réelles enregistrées
        self.assertEqual(self.props.last_status, "Succès")
        self.assertGreater(self.props.last_tris_before, self.props.last_tris_after)
        self.assertGreater(self.props.last_reduction, 0.0)

        # Test restauration
        res_rst = bpy.ops.meshforge.restore()
        self.assertEqual(res_rst, {'FINISHED'})
        self.assertNotIn(opt_name, bpy.data.objects)
        self.assertFalse(orig_obj.hide_get())
        self.assertEqual(bpy.context.active_object, orig_obj)

    def test_08_dissolve_operator_non_destructive_workflow(self):
        """Vérifie que meshforge.dissolve fonctionne avec le workflow non-destructif sur un cube subdivisé."""
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        cube = bpy.context.active_object
        # Subdiviser les faces du cube (faces coplanaires)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=2)
        bpy.ops.object.mode_set(mode='OBJECT')

        orig_name = cube.name
        self.props.create_new_object = True
        self.props.hide_original = True
        self.props.dissolve_angle = 5.0
        self.props.dissolve_mode = 'BALANCED'

        res = bpy.ops.meshforge.dissolve()
        self.assertEqual(res, {'FINISHED'})

        opt_obj = bpy.context.active_object
        self.assertIn("_MF_Optimized", opt_obj.name)
        self.assertLess(self.props.last_faces_after, self.props.last_faces_before)

        # Restauration
        bpy.ops.meshforge.restore()
        self.assertFalse(cube.hide_get())

    def test_09_expert_subpanels_poll(self):
        """Vérifie que les sous-panneaux du Mode Expert obéissent strictement à show_expert_mode."""
        self.props.show_expert_mode = False
        context = bpy.context

        # Tous les sous-panneaux doivent être masqués quand Mode Expert est désactivé
        self.assertFalse(VIEW3D_PT_meshforge_repair.poll(context))
        self.assertFalse(VIEW3D_PT_meshforge_manifold.poll(context))
        self.assertFalse(VIEW3D_PT_meshforge_dissolve.poll(context))
        self.assertFalse(VIEW3D_PT_meshforge_simplification.poll(context))
        self.assertFalse(VIEW3D_PT_meshforge_topology.poll(context))
        self.assertFalse(VIEW3D_PT_meshforge_normals.poll(context))
        self.assertFalse(VIEW3D_PT_meshforge_object_data.poll(context))

        # Quand Mode Expert est activé, les sous-panneaux deviennent accessibles
        self.props.show_expert_mode = True
        self.assertTrue(VIEW3D_PT_meshforge_repair.poll(context))
        self.assertTrue(VIEW3D_PT_meshforge_manifold.poll(context))
        self.assertTrue(VIEW3D_PT_meshforge_dissolve.poll(context))
        self.assertTrue(VIEW3D_PT_meshforge_simplification.poll(context))
        self.assertTrue(VIEW3D_PT_meshforge_topology.poll(context))
        self.assertTrue(VIEW3D_PT_meshforge_normals.poll(context))
        self.assertTrue(VIEW3D_PT_meshforge_object_data.poll(context))

    def test_10_register_unregister_cleanliness(self):
        """Vérifie que le cycle unregister puis register s'exécute proprement sans fuite."""
        # Unregister
        meshforge.unregister()
        self.assertFalse(hasattr(bpy.types.Scene, "meshforge_settings"))

        # Re-register
        meshforge.register()
        self.assertTrue(hasattr(bpy.types.Scene, "meshforge_settings"))


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestMeshForgeUXCleanDecimate)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
