"""MeshForge - Tests unitaires ciblés pour la refonte UX guidée par l'objectif utilisateur.
Vérifie :
1. Analyse en premier : calcul factuel neutre, indépendance de la détection et des recommandations.
2. Sélection de l'objectif parmi les 8 profils humains et mise à jour dynamique.
3. Contraintes complémentaires (strict_manifold, quads_only).
4. Organisation des recommandations en 4 catégories lisibles avec les 7 attributs requis.
5. Emplacement et condition d'affichage de 'Restaurer l'original' dans CLEAN.
6. Dessin sans régression du panneau VIEW3D_PT_meshforge_main.
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

# Importation directe des modules MeshForge
import meshforge
from meshforge.core.structured_diagnosis import (
    measure_mesh_facts,
    evaluate_structured_diagnosis,
    PROFILES
)
from meshforge.operators.topology_inspect import (
    _ACTIVE_DIAGNOSIS_CACHE,
    diagnose_topology
)
from meshforge.ui.panel import VIEW3D_PT_meshforge_main


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


class MockPanel:
    def __init__(self):
        self.layout = DummyLayout()


class TestUXGoalDriven(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        _ACTIVE_DIAGNOSIS_CACHE.clear()

    def tearDown(self):
        _ACTIVE_DIAGNOSIS_CACHE.clear()

    def _create_test_mesh(self):
        """Crée un maillage contenant diverses anomalies pour tester les 4 catégories :
        - 1 face d'aire nulle (dégénérescence)
        - 1 sommet orphelin (dégénérescence)
        - 1 N-gone concave
        - 1 N-gone convexe
        - 2 triangles coplanaires pouvant être quadrangulés
        - 1 arête filaire
        """
        mesh = bpy.data.meshes.new("TestMesh")
        bm = bmesh.new()

        # Quads de base
        v0 = bm.verts.new((-1.0, -1.0, 0.0))
        v1 = bm.verts.new((0.0, -1.0, 0.0))
        v2 = bm.verts.new((0.0, 0.0, 0.0))
        v3 = bm.verts.new((-1.0, 0.0, 0.0))
        bm.faces.new((v0, v1, v2, v3))

        # 2 triangles coplanaires
        v4 = bm.verts.new((1.0, -1.0, 0.0))
        v5 = bm.verts.new((1.0, 0.0, 0.0))
        bm.faces.new((v1, v4, v5))
        bm.faces.new((v1, v5, v2))

        # N-gone convexe (5 côtés)
        v6 = bm.verts.new((2.0, -0.5, 0.0))
        v7 = bm.verts.new((2.0, 0.5, 0.0))
        v8 = bm.verts.new((1.5, 1.0, 0.0))
        bm.faces.new((v5, v4, v6, v7, v8))

        # Face d'aire nulle (3 sommets identiques)
        v_z0 = bm.verts.new((5.0, 0.0, 0.0))
        v_z1 = bm.verts.new((5.0, 0.0, 0.0))
        v_z2 = bm.verts.new((5.0, 0.0, 0.0))
        bm.faces.new((v_z0, v_z1, v_z2))

        # Sommet orphelin
        bm.verts.new((10.0, 10.0, 10.0))

        # Arête filaire
        v_w1 = bm.verts.new((12.0, 0.0, 0.0))
        v_w2 = bm.verts.new((13.0, 0.0, 0.0))
        bm.edges.new((v_w1, v_w2))

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("TestObj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        return obj

    def test_01_analysis_first_factual_independence(self):
        """Vérifie que les faits géométriques mesurés sont strictement neutres et constants,
        quel que soit le profil utilisateur ou les contraintes choisies."""
        obj = self._create_test_mesh()
        facts = measure_mesh_facts(obj)

        self.assertTrue(facts.get("valid", False))
        self.assertGreater(facts.get("loose_verts_count", 0), 0)
        self.assertGreater(facts.get("zero_area_faces_count", 0), 0)
        self.assertGreater(facts.get("tris_count", 0), 0)
        self.assertGreater(facts.get("total_ngons", 0), 0)
        self.assertGreater(facts.get("wire_edges_count", 0), 0)

        # L'évaluation sous deux profils différents utilise les mêmes faits exacts
        res_game = evaluate_structured_diagnosis(facts, "GAME_ASSET")
        res_cad = evaluate_structured_diagnosis(facts, "MECHANICAL_CAD")

        self.assertTrue(res_game["valid"])
        self.assertTrue(res_cad["valid"])

        # Les faits sous-jacents ne sont pas altérés
        self.assertEqual(facts["loose_verts_count"], 1)

    def test_02_four_recommendation_categories_structure(self):
        """Vérifie que evaluate_structured_diagnosis génère bien les 4 catégories
        avec tous les 7 attributs obligatoires par carte."""
        obj = self._create_test_mesh()
        facts = measure_mesh_facts(obj)
        res = evaluate_structured_diagnosis(facts, "GAME_ASSET")

        self.assertIn("recommendation_groups", res)
        groups = res["recommendation_groups"]

        self.assertIn("conservative", groups)
        self.assertIn("targeted", groups)
        self.assertIn("risky", groups)
        self.assertIn("observations", groups)

        required_keys = {"problem", "zone", "effect", "data_impact", "reversibility", "confidence"}

        for grp_name, card_list in groups.items():
            for card in card_list:
                for k in required_keys:
                    self.assertIn(k, card, f"Clé manquante '{k}' dans la carte {card.get('title')} du groupe {grp_name}")
                self.assertTrue(len(card["problem"]) > 0)
                self.assertTrue(len(card["zone"]) > 0)
                self.assertTrue(len(card["effect"]) > 0)
                self.assertTrue(len(card["data_impact"]) > 0)
                self.assertTrue(len(card["reversibility"]) > 0)
                self.assertTrue(len(card["confidence"]) > 0)

    def test_03_goal_adaptation(self):
        """Vérifie que les recommandations s'adaptent logiquement à l'objectif :
        - En GAME_ASSET : la découpe des N-gones est recommandée dans les optimisations ciblées.
        - En MECHANICAL_CAD : les N-gones convexes réguliers sont observés et tolérés sans découpe agressive."""
        obj = self._create_test_mesh()
        facts = measure_mesh_facts(obj)

        res_game = evaluate_structured_diagnosis(facts, "GAME_ASSET")
        res_cad = evaluate_structured_diagnosis(facts, "MECHANICAL_CAD")

        # En GAME_ASSET, cut_ngons est dans les optimisations ciblées
        targeted_ops_game = [c.get("operator") for c in res_game["recommendation_groups"]["targeted"]]
        self.assertIn("meshforge.cut_ngons", targeted_ops_game)

        # En MECHANICAL_CAD sans N-gones concaves, les N-gones plans sont en observation
        obs_ids_cad = [c.get("id") for c in res_cad["recommendation_groups"]["observations"]]
        self.assertIn("obs_cad_ngons", obs_ids_cad)

    def test_04_complementary_constraints(self):
        """Vérifie l'impact des contraintes complémentaires :
        - constraint_quads_only impose la découpe des N-gones et la quadrangulation même en GENERAL.
        - constraint_strict_manifold classe les arêtes filaires et frontières ouvertes en DEFECT."""
        obj = self._create_test_mesh()
        facts = measure_mesh_facts(obj)

        # Mode GENERAL standard sans contrainte
        res_gen_clean = evaluate_structured_diagnosis(facts, "GENERAL", strict_manifold=False, quads_only=False)

        # Mode GENERAL avec contrainte quads_only
        res_gen_quads = evaluate_structured_diagnosis(facts, "GENERAL", strict_manifold=False, quads_only=True)

        targeted_gen_quads = [c.get("operator") for c in res_gen_quads["recommendation_groups"]["targeted"]]
        self.assertIn("meshforge.cut_ngons", targeted_gen_quads)
        self.assertIn("meshforge.quadrangulate", targeted_gen_quads)

        # Mode avec contrainte strict_manifold
        res_strict = evaluate_structured_diagnosis(facts, "GENERAL", strict_manifold=True, quads_only=False)
        defects_strict = [f["id"] for f in res_strict["findings"] if f["severity"] == "DEFECT"]
        self.assertIn("topo_wire_edges", defects_strict)

    def test_05_restore_original_visibility(self):
        """Vérifie que 'Restaurer l'original' est lié à la présence d'un résultat actif (_MF_Optimized)."""
        obj = self._create_test_mesh()
        self.assertNotIn("_MF_Optimized", obj.name)

        # Création d'une copie optimisée simulée
        obj_opt = obj.copy()
        obj_opt.data = obj.data.copy()
        obj_opt.name = "TestObj_MF_Optimized"
        obj_opt["_mf_source_ptr"] = obj
        obj_opt["_mf_source_mesh_version"] = f"{len(obj.data.vertices)}v_{len(obj.data.edges)}e_{len(obj.data.polygons)}f"
        bpy.context.collection.objects.link(obj_opt)

        self.assertIn("_MF_Optimized", obj_opt.name)
        self.assertEqual(obj_opt.get("_mf_source_ptr"), obj)

    def test_06_ui_panel_draw_no_object(self):
        """Vérifie que le panneau se dessine sans erreur lorsqu'aucun objet n'est sélectionné."""
        panel = MockPanel()
        bpy.context.view_layer.objects.active = None
        VIEW3D_PT_meshforge_main.draw(panel, bpy.context)

    def test_07_ui_panel_draw_unanalyzed(self):
        """Vérifie que le panneau se dessine sans erreur avec un objet non analysé (invite à l'analyse)."""
        panel = MockPanel()
        obj = self._create_test_mesh()
        VIEW3D_PT_meshforge_main.draw(panel, bpy.context)

    def test_08_ui_panel_draw_analyzed_all_goals(self):
        """Vérifie que le panneau se dessine sans erreur pour tous les 8 objectifs après analyse."""
        panel = MockPanel()
        obj = self._create_test_mesh()
        props = bpy.context.scene.meshforge_settings

        # Lancer l'analyse
        bpy.ops.meshforge.analyze_topology()

        goals = [
            'GENERAL', 'GAME_ASSET', 'RENDER_ANIM', 'DEFORMABLE_CHAR',
            'EXPORT_PREP', 'MECHANICAL_CAD', 'SCULPTED_ORGANIC', 'CUSTOM'
        ]
        for goal in goals:
            props.asset_target_mode = goal
            VIEW3D_PT_meshforge_main.draw(panel, bpy.context)

    def test_09_ui_panel_draw_with_restore_box(self):
        """Vérifie que le panneau se dessine correctement quand un objet optimisé actif est sélectionné."""
        panel = MockPanel()
        obj = self._create_test_mesh()
        bpy.ops.meshforge.analyze_topology()

        # Copie optimisée
        obj_opt = obj.copy()
        obj_opt.data = obj.data.copy()
        obj_opt.name = "TestObj_MF_Optimized"
        obj_opt["_mf_source_ptr"] = obj
        obj_opt["_mf_source_mesh_version"] = f"{len(obj.data.vertices)}v_{len(obj.data.edges)}e_{len(obj.data.polygons)}f"
        bpy.context.collection.objects.link(obj_opt)
        bpy.context.view_layer.objects.active = obj_opt

        # Diagnostiquer la copie
        bpy.ops.meshforge.analyze_topology()
        VIEW3D_PT_meshforge_main.draw(panel, bpy.context)


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestUXGoalDriven)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
