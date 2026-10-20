"""MeshForge - Tests de validation des correctifs UX6 (BUG-01 et BUG-02).
Vérifie rigoureusement :
1. Comportement des opérateurs en mode Édition (poll() False, execute() CANCELLED sécurisé, aucun crash to_mesh()).
2. Comportement en mode Objet (poll() True, nettoyages opérationnels).
3. Rejet défensif des fonctions core en mode Édition sans altération de données.
4. Cycle complet register() -> unregister() -> register() sans fuite RNA ni résidu Scene.
5. Idempotence et tolérance aux désenregistrements partiels ou successifs.
6. Récupération propre (rollback) après échec partiel de register().
"""

from __future__ import annotations
import bpy
import bmesh
import unittest
import sys
from pathlib import Path

# Assurer l'accès au package meshforge
root_dir = Path(__file__).resolve().parent.parent
parent_dir = root_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import meshforge
from meshforge.core.registration_utils import (
    is_class_registered,
    safe_register_class,
    safe_unregister_class,
    register_classes_safely,
    unregister_classes_safely,
)
from meshforge.core.conservative_cleaner import execute_conservative_cleanup
from meshforge.core.ngon_cutter import execute_ngon_cut
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.core.pipeline import run_meshforge_pipeline
from meshforge.operators.conservative_clean_op import MESHFORGE_OT_conservative_clean
from meshforge.operators.ngon_cut_op import MESHFORGE_OT_cut_ngons
from meshforge.operators.topology_inspect import MESHFORGE_OT_analyze_topology
from meshforge.operators.section_ops import (
    MESHFORGE_OT_repair,
    MESHFORGE_OT_manifold,
    MESHFORGE_OT_dissolve,
    MESHFORGE_OT_simplification,
    MESHFORGE_OT_topology,
    MESHFORGE_OT_normals,
    MESHFORGE_OT_object_data,
)
from meshforge.operators.optimize import MESHFORGE_OT_optimize
from meshforge.operators.restore import MESHFORGE_OT_restore
from meshforge.operators.analyze import MESHFORGE_OT_analyze


class DummyOperator:
    """Mock pour tester la méthode execute() directement."""
    def __init__(self):
        self.reports = []

    def report(self, type_set, message):
        self.reports.append((type_set, message))


class TestUX6Fixes(unittest.TestCase):
    """Suite de tests unitaires et d'intégration pour BUG-01 (Edit Mode) et BUG-02 (Registration)."""

    @classmethod
    def setUpClass(cls):
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

    @classmethod
    def tearDownClass(cls):
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

    def setUp(self):
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

    def tearDown(self):
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

    def _create_test_mesh(self) -> bpy.types.Object:
        """Crée un objet avec un cube, un sommet orphelin et un 6-gon régulier convexe."""
        mesh = bpy.data.meshes.new("TestMesh")
        bm = bmesh.new()
        # Cube de base
        bmesh.ops.create_cube(bm, size=2.0)
        # Ajouter un sommet orphelin
        bm.verts.new((3.0, 3.0, 3.0))
        # Ajouter un 6-gon convexe propre
        import math
        v_ngon_circle = [
            bm.verts.new((5.0 + math.cos(2 * math.pi * i / 6), 5.0 + math.sin(2 * math.pi * i / 6), 0.0))
            for i in range(6)
        ]
        bm.faces.new(v_ngon_circle)

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("TestObj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        return obj

    # =========================================================================
    # BUG-01 : TESTS DU MODE ÉDITION VS MODE OBJET
    # =========================================================================

    def test_01_operators_poll_in_edit_mode(self):
        """BUG-01 Test A1 : Vérifie que le poll() de tous les opérateurs de modification
        retourne rigoureusement False lorsque l'utilisateur est en mode Édition.
        """
        obj = self._create_test_mesh()
        bpy.ops.object.mode_set(mode='EDIT')
        self.assertEqual(bpy.context.mode, 'EDIT_MESH')
        self.assertEqual(obj.mode, 'EDIT')

        modifying_operator_classes = [
            MESHFORGE_OT_conservative_clean,
            MESHFORGE_OT_cut_ngons,
            MESHFORGE_OT_analyze_topology,
            MESHFORGE_OT_repair,
            MESHFORGE_OT_manifold,
            MESHFORGE_OT_dissolve,
            MESHFORGE_OT_simplification,
            MESHFORGE_OT_topology,
            MESHFORGE_OT_normals,
            MESHFORGE_OT_object_data,
            MESHFORGE_OT_optimize,
            MESHFORGE_OT_restore,
            MESHFORGE_OT_analyze,
        ]

        for op_cls in modifying_operator_classes:
            poll_result = op_cls.poll(bpy.context)
            self.assertFalse(
                poll_result,
                f"L'opérateur {op_cls.__name__}.poll() devrait retourner False en mode Édition."
            )

        # Revenir en mode Objet et vérifier que le poll() repasse à True
        bpy.ops.object.mode_set(mode='OBJECT')
        for op_cls in modifying_operator_classes:
            if op_cls == MESHFORGE_OT_restore:
                continue
            self.assertTrue(
                op_cls.poll(bpy.context),
                f"L'opérateur {op_cls.__name__}.poll() devrait retourner True en mode Objet."
            )

    def test_02_operators_execute_in_edit_mode_returns_cancelled(self):
        """BUG-01 Test A2 : Vérifie qu'en mode Édition, l'appel des opérateurs est protégé
        par poll() (RuntimeError context incorrect) et qu'un appel direct execute()
        retourne proprement {'CANCELLED'} avec un message d'avertissement en français,
        sans aucun crash 'to_mesh(): Mesh is in editmode'.
        """
        obj = self._create_test_mesh()
        vert_count_before = len(obj.data.vertices)

        bpy.ops.object.mode_set(mode='EDIT')

        # 1. Protection par poll() via bpy.ops
        with self.assertRaises(RuntimeError):
            bpy.ops.meshforge.conservative_clean()

        with self.assertRaises(RuntimeError):
            bpy.ops.meshforge.cut_ngons()

        with self.assertRaises(RuntimeError):
            bpy.ops.meshforge.analyze_topology()

        # 2. Protection défensive dans execute()
        dummy_clean = DummyOperator()
        res_clean = MESHFORGE_OT_conservative_clean.execute(dummy_clean, bpy.context)
        self.assertEqual(res_clean, {'CANCELLED'})
        self.assertTrue(any("mode Objet" in msg[1] for msg in dummy_clean.reports))

        dummy_cut = DummyOperator()
        res_cut = MESHFORGE_OT_cut_ngons.execute(dummy_cut, bpy.context)
        self.assertEqual(res_cut, {'CANCELLED'})
        self.assertTrue(any("mode Objet" in msg[1] for msg in dummy_cut.reports))

        dummy_diag = DummyOperator()
        res_diag = MESHFORGE_OT_analyze_topology.execute(dummy_diag, bpy.context)
        self.assertEqual(res_diag, {'CANCELLED'})
        self.assertTrue(any("mode Objet" in msg[1] for msg in dummy_diag.reports))

        # Revenir en mode objet et vérifier qu'aucune donnée n'a été corrompue
        bpy.ops.object.mode_set(mode='OBJECT')
        self.assertEqual(len(obj.data.vertices), vert_count_before)

    def test_03_core_functions_reject_edit_mode_safely(self):
        """BUG-01 Test A3 : Vérifie que les fonctions fondamentales du noyau (core)
        rejettent immédiatement et défensivement les objets en mode Édition sans altération.
        """
        obj = self._create_test_mesh()
        bpy.ops.object.mode_set(mode='EDIT')

        # 1. execute_conservative_cleanup
        res_clean = execute_conservative_cleanup(obj)
        self.assertFalse(res_clean["success"])
        self.assertIn("mode Édition", res_clean["error"])

        # 2. execute_ngon_cut
        res_cut = execute_ngon_cut(obj)
        self.assertFalse(res_cut["success"])
        self.assertIn("mode Édition", res_cut["error"])

        # 3. diagnose_topology
        res_diag = diagnose_topology(obj)
        self.assertFalse(res_diag["valid"])
        self.assertIn("mode Édition", res_diag["error"])

        # 4. run_meshforge_pipeline
        props = bpy.context.scene.meshforge_settings
        res_pipe = run_meshforge_pipeline(obj, props)
        self.assertFalse(res_pipe["success"])
        self.assertTrue(any("mode Édition" in err for err in res_pipe["errors"]))

        bpy.ops.object.mode_set(mode='OBJECT')

    def test_04_normal_execution_in_object_mode(self):
        """BUG-01 Test B : Vérifie le bon déroulement des opérations de nettoyage en mode Objet."""
        obj = self._create_test_mesh()
        # En mode Objet, le nettoyage conservateur supprime le sommet orphelin
        res_clean = execute_conservative_cleanup(obj)
        self.assertTrue(res_clean["success"])
        self.assertEqual(res_clean["elements_removed"]["loose_verts"], 1)

        # Découpe des N-gones en mode Objet
        res_cut = execute_ngon_cut(obj)
        self.assertTrue(res_cut["success"])
        self.assertGreaterEqual(res_cut["convex_cut"], 1)

    # =========================================================================
    # BUG-02 : TESTS DU CYCLE D'ENREGISTREMENT ET DE DÉSINCRIPTION (LIFECYCLE)
    # =========================================================================

    def test_05_single_register_unregister_cycle(self):
        """BUG-02 Test C : Cycle complet register() -> unregister() sans fuite RNA ni résidu Scene."""
        # Désenregistrer d'abord pour tester un cycle propre
        meshforge.unregister()
        self.assertFalse(hasattr(bpy.types.Scene, "meshforge_settings"))

        # Enregistrer
        meshforge.register()
        self.assertTrue(hasattr(bpy.types.Scene, "meshforge_settings"))
        self.assertTrue(is_class_registered(MESHFORGE_OT_conservative_clean))

        # Désenregistrer
        meshforge.unregister()
        self.assertFalse(hasattr(bpy.types.Scene, "meshforge_settings"))
        self.assertFalse(is_class_registered(MESHFORGE_OT_conservative_clean))

        # Réenregistrer pour laisser l'environnement prêt
        meshforge.register()
        self.assertTrue(hasattr(bpy.types.Scene, "meshforge_settings"))

    def test_06_double_cycle_and_idempotence(self):
        """BUG-02 Test D1 : Vérifie que plusieurs cycles successifs et des désinscriptions
        consécutives n'engendrent aucune exception 'missing bl_rna attribute'.
        """
        # Double unregister consécutif (doit être 100% silencieux et sans erreur)
        meshforge.unregister()
        try:
            meshforge.unregister()
        except Exception as e:
            self.fail(f"Le deuxième unregister() consécutif a levé une exception : {e}")

        # Double register consécutif
        meshforge.register()
        try:
            meshforge.register()
        except Exception as e:
            self.fail(f"Le deuxième register() consécutif a levé une exception : {e}")

        # Nettoyage final pour laisser l'environnement propre
        meshforge.unregister()
        meshforge.register()
        self.assertTrue(hasattr(bpy.types.Scene, "meshforge_settings"))

    def test_07_safe_unregister_orphan_classes(self):
        """BUG-02 Test D2 : Vérifie que safe_unregister_class tolère des classes non inscrites
        ou des objets arbitraires sans jamais planter.
        """
        class DummyUnregistered:
            pass

        result = safe_unregister_class(DummyUnregistered)
        self.assertFalse(result)

        # Vérifier qu'une classe enregistrée puis désenregistrée deux fois ne lève rien
        safe_register_class(MESHFORGE_OT_conservative_clean)
        res1 = safe_unregister_class(MESHFORGE_OT_conservative_clean)
        self.assertTrue(res1)
        res2 = safe_unregister_class(MESHFORGE_OT_conservative_clean)
        self.assertFalse(res2)

        # Restaurer l'opérateur
        safe_register_class(MESHFORGE_OT_conservative_clean)

    def test_08_transactional_registration_recovery(self):
        """BUG-02 Test E : Vérifie que register_classes_safely nettoie toutes les classes
        précédentes si une classe ultérieure échoue pendant l'enregistrement.
        """
        class GoodClass1(bpy.types.Operator):
            bl_idname = "meshforge.test_good_1"
            bl_label = "Test Good 1"

        class FaultyClass:
            # Pas une sous-classe valide de bpy.types, fera échouer register_class
            pass

        classes_to_test = [GoodClass1, FaultyClass]

        with self.assertRaises(Exception):
            register_classes_safely(classes_to_test)

        # Vérifier que GoodClass1 a été proprement désenregistrée lors du rollback
        self.assertFalse(is_class_registered(GoodClass1))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestUX6Fixes)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
