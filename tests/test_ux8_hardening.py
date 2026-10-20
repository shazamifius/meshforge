"""MeshForge - Tests unitaires ciblés pour la sécurisation post-UX8.

Vérifie :
1. Blocage par défaut de DECIMATE (Collapse et Dissolve) sur objet avec Shape Keys.
2. Protection stricte de l'original : non-suppression et non-altération des Shape Keys sources.
3. Option explicite de copie statique sans Shape Keys (crée une copie sans shape keys, original intact).
4. Refus de modification directe des Shape Keys en mode destructif.
5. Détection des risques identifiables de dissolution agressive (seams non protégées, sharp non protégées, profil sensible).
6. Déblocage conditionnel via confirmation explicite (confirm_aggressive_dissolve).
7. Gestion propre des noms lors des décimations successives (non-prolifération des suffixes .001).
8. Absence d'échantillonnage BVH / tolérance lorsque la tolérance n'est pas activée.
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
from mathutils import Vector
import meshforge
from meshforge.ui.panel import VIEW3D_PT_meshforge_main


class DummyLayout:
    """Mock minimal de Layout Blender pour tester draw()."""
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
        return DummyOp()


class TestUX8Hardening(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            meshforge.register()
        except ValueError:
            pass

    @classmethod
    def tearDownClass(cls):
        try:
            meshforge.unregister()
        except Exception:
            pass

    def setUp(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        self.scene = bpy.context.scene
        self.props = self.scene.meshforge_settings

        # Réinitialisation des réglages
        self.props.create_new_object = True
        self.props.hide_original = True
        self.props.allow_shape_keys_removal_on_copy = False
        self.props.confirm_aggressive_dissolve = False
        self.props.enable_simplification_tolerance = False
        self.props.decimate_method = 'COLLAPSE'
        self.props.simplification_mode = 'PERCENTAGE'
        self.props.simplification_percentage = 50.0

    def _create_cube_with_shape_keys(self, name="SK_Cube") -> bpy.types.Object:
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        obj = bpy.context.active_object
        obj.name = name

        # Ajouter base et clé de forme
        obj.shape_key_add(name="Basis")
        sk1 = obj.shape_key_add(name="Key_1")
        sk1.data[0].co += Vector((0.2, 0.2, 0.2))
        return obj

    def _create_subdivided_plane(self, name="SubPlane") -> bpy.types.Object:
        bpy.ops.mesh.primitive_plane_add(size=2.0)
        obj = bpy.context.active_object
        obj.name = name
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=4)
        bpy.ops.object.mode_set(mode='OBJECT')
        return obj

    # -------------------------------------------------------------
    # 1. Tests Shape Keys (Sécurisation 1)
    # -------------------------------------------------------------
    def test_shape_keys_refusal_by_default_collapse(self):
        """Vérifie que la contraction d'arêtes refuse d'agir sur un objet avec Shape Keys par défaut."""
        obj = self._create_cube_with_shape_keys()
        self.props.allow_shape_keys_removal_on_copy = False

        with self.assertRaises(RuntimeError) as ctx:
            bpy.ops.meshforge.simplification()
        self.assertIn("Shape Keys", str(ctx.exception))

        # L'objet source doit TOUJOURS avoir ses clés intactes
        self.assertIsNotNone(obj.data.shape_keys)
        self.assertEqual(len(obj.data.shape_keys.key_blocks), 2)

    def test_shape_keys_refusal_by_default_dissolve(self):
        """Vérifie que la dissolution refuse d'agir sur un objet avec Shape Keys par défaut."""
        obj = self._create_cube_with_shape_keys()
        self.props.decimate_method = 'DISSOLVE'
        self.props.allow_shape_keys_removal_on_copy = False

        with self.assertRaises(RuntimeError) as ctx:
            bpy.ops.meshforge.dissolve()
        self.assertIn("Shape Keys", str(ctx.exception))

        # L'objet source doit TOUJOURS avoir ses clés intactes
        self.assertIsNotNone(obj.data.shape_keys)
        self.assertEqual(len(obj.data.shape_keys.key_blocks), 2)

    def test_shape_keys_refusal_in_destructive_mode(self):
        """En mode destructif, MeshForge refuse absolument de supprimer les Shape Keys de l'original."""
        obj = self._create_cube_with_shape_keys()
        self.props.create_new_object = False
        self.props.allow_shape_keys_removal_on_copy = True

        with self.assertRaises(RuntimeError) as ctx:
            bpy.ops.meshforge.simplification()
        self.assertIn("Shape Keys", str(ctx.exception))

        # L'original n'a pas été touché
        self.assertIsNotNone(obj.data.shape_keys)
        self.assertEqual(len(obj.data.shape_keys.key_blocks), 2)

    def test_shape_keys_allowed_creates_static_copy_original_untouched(self):
        """Avec allow_shape_keys_removal_on_copy=True, crée une copie statique et préserve 100% l'original."""
        obj = self._create_cube_with_shape_keys()
        self.props.allow_shape_keys_removal_on_copy = True
        self.props.simplification_percentage = 50.0

        res = bpy.ops.meshforge.simplification()
        self.assertIn('FINISHED', res)

        # 1. Vérifier l'original : 100% intact avec ses shape keys
        self.assertIn(obj.name, bpy.data.objects)
        self.assertIsNotNone(obj.data.shape_keys)
        self.assertEqual(len(obj.data.shape_keys.key_blocks), 2)

        # 2. Vérifier la copie optimisée : créée sans shape keys
        active = bpy.context.active_object
        self.assertNotEqual(active, obj)
        self.assertTrue(active.name.endswith("_MF_Optimized"))
        self.assertTrue(active.data.shape_keys is None or len(active.data.shape_keys.key_blocks) == 0)

    # -------------------------------------------------------------
    # 2. Tests Dissolution Agressive (Sécurisation 2)
    # -------------------------------------------------------------
    def test_aggressive_dissolve_risk_uv_seams(self):
        """Vérifie le blocage de sécurité si le maillage a des coutures UV et preserve_seams=False."""
        obj = self._create_subdivided_plane()
        # Marquer une couture UV
        obj.data.edges[0].use_seam = True

        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = False
        self.props.confirm_aggressive_dissolve = False

        res = bpy.ops.meshforge.dissolve()
        self.assertIn('CANCELLED', res)

        # Avec confirmation explicite, l'exécution est autorisée
        self.props.confirm_aggressive_dissolve = True
        res2 = bpy.ops.meshforge.dissolve()
        self.assertIn('FINISHED', res2)

    def test_aggressive_dissolve_risk_sharp_edges(self):
        """Vérifie le blocage si le maillage a des arêtes vives et preserve_sharp=False."""
        obj = self._create_subdivided_plane()
        # Marquer une arête vive
        obj.data.edges[0].use_edge_sharp = True

        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_sharp = False
        self.props.confirm_aggressive_dissolve = False

        res = bpy.ops.meshforge.dissolve()
        self.assertIn('CANCELLED', res)

        # Avec confirmation explicite, l'exécution est autorisée
        self.props.confirm_aggressive_dissolve = True
        res2 = bpy.ops.meshforge.dissolve()
        self.assertIn('FINISHED', res2)

    def test_aggressive_dissolve_risk_game_asset_profile(self):
        """Vérifie le blocage si dissolve_mode=AGGRESSIVE sur profil GAME_ASSET."""
        obj = self._create_subdivided_plane()
        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = True
        self.props.preserve_sharp = True
        self.props.asset_target_mode = 'GAME_ASSET'
        self.props.dissolve_mode = 'AGGRESSIVE'
        self.props.confirm_aggressive_dissolve = False

        res = bpy.ops.meshforge.dissolve()
        self.assertIn('CANCELLED', res)

        # Avec confirmation, autorisé
        self.props.confirm_aggressive_dissolve = True
        res2 = bpy.ops.meshforge.dissolve()
        self.assertIn('FINISHED', res2)

    # -------------------------------------------------------------
    # 3. Tests Workflow & Métrologie Honnête
    # -------------------------------------------------------------
    def test_chained_decimate_preserves_naming(self):
        """Vérifie que des réductions successives réutilisent l'objet optimisé sans générer .001.002."""
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=16)
        source = bpy.context.active_object
        source.name = "TestSphere"

        # Première décimation
        self.props.simplification_percentage = 25.0
        res1 = bpy.ops.meshforge.simplification()
        self.assertIn('FINISHED', res1)
        opt1 = bpy.context.active_object
        self.assertEqual(opt1.name, "TestSphere_MF_Optimized")

        # Deuxième décimation depuis l'objet optimisé actif
        self.props.simplification_percentage = 50.0
        res2 = bpy.ops.meshforge.simplification()
        self.assertIn('FINISHED', res2)
        opt2 = bpy.context.active_object
        self.assertEqual(opt2.name, "TestSphere_MF_Optimized")

    def test_no_tolerance_no_bvh_measurement(self):
        """Vérifie que sans tolérance demandée, aucune déviation géométrique inventée n'est enregistrée."""
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2)
        self.props.enable_simplification_tolerance = False
        self.props.simplification_percentage = 40.0

        res = bpy.ops.meshforge.simplification()
        self.assertIn('FINISHED', res)

        self.assertFalse(self.props.last_deviation_measured)
        self.assertEqual(self.props.last_max_hausdorff, 0.0)
        self.assertEqual(self.props.last_mean_deviation, 0.0)

    # -------------------------------------------------------------
    # 4. Dessin UI avec alertes Shape Keys et Risque Dissolution
    # -------------------------------------------------------------
    def test_ui_panel_draw_with_shape_keys_and_dissolve_risks(self):
        """Vérifie que VIEW3D_PT_meshforge_main se dessine sans erreur avec Shape Keys et alertes actives."""
        obj = self._create_cube_with_shape_keys()
        self.props.ui_section_decimate_expanded = True
        self.props.decimate_method = 'DISSOLVE'
        self.props.preserve_seams = False

        class MockPanelObj:
            def __init__(self):
                self.layout = DummyLayout()

        mock_panel = MockPanelObj()
        class DummyContext:
            def __init__(self, scene, active_obj):
                self.scene = scene
                self.active_object = active_obj
                self.mode = 'OBJECT'

        # Le dessin ne doit lever aucune exception
        VIEW3D_PT_meshforge_main.draw(mock_panel, DummyContext(self.scene, obj))


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestUX8Hardening)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
