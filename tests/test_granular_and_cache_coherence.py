"""Tests complets pour la clôture ciblée du diagnostic (P0 Granularité & P0 Cache/Validations).
Couvre formellement :
- Granularité du marquage intentionnel (2 anomalies du même type, une intentionnelle, une accidentelle).
- Refus du marquage global non ciblé.
- Distinction stricte géométrie intentionnelle vs conformité objectif (EXPORT_PREP / strict_manifold).
- Scénario 1 : Modification en Mode Édition (détection péremption).
- Scénario 2 : Changement topologique après validation intentionnelle (purge et pruned_validations).
- Scénario 3 : Suppression puis recréation d'une zone validée (invalidation spatiale, pas de rétention silencieuse).
- Scénario 4 : Changement d'objectif sans modification géométrique (réévaluation instantanée sans recalcul facts).
- Scénario 5 : Annulation d'un marquage intentionnel (restauration immédiate en DEFECT).
"""

import unittest
import bpy
import bmesh
import sys
import json
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.structured_diagnosis import measure_mesh_facts, evaluate_structured_diagnosis
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.operators.topology_inspect import _ACTIVE_DIAGNOSIS_CACHE, check_diagnosis_staleness


class TestGranularAndCacheCoherence(unittest.TestCase):

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

    def _create_mesh_with_two_concave_ngons(self):
        """Crée un maillage avec exactement 2 N-gones concaves distincts et distants."""
        mesh = bpy.data.meshes.new("TwoConcaveMesh")
        bm = bmesh.new()

        # Face 0 (N-gone concave à gauche, X ~ -3)
        v0 = bm.verts.new((-4.0, -1.0, 0.0))
        v1 = bm.verts.new((-2.0, -1.0, 0.0))
        v2 = bm.verts.new((-2.0, 1.0, 0.0))
        v3 = bm.verts.new((-3.0, 0.0, 0.0))  # cran concave
        v4 = bm.verts.new((-4.0, 1.0, 0.0))
        bm.faces.new((v0, v1, v2, v3, v4))

        # Face 1 (N-gone concave à droite, X ~ +3)
        v5 = bm.verts.new((2.0, -1.0, 0.0))
        v6 = bm.verts.new((4.0, -1.0, 0.0))
        v7 = bm.verts.new((4.0, 1.0, 0.0))
        v8 = bm.verts.new((3.0, 0.0, 0.0))  # cran concave
        v9 = bm.verts.new((2.0, 1.0, 0.0))
        bm.faces.new((v5, v6, v7, v8, v9))

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("TwoConcaveObj", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        return obj

    # =========================================================================
    # P0 : GRANULARITÉ DU MARQUAGE INTENTIONNEL
    # =========================================================================

    def test_01_two_anomalies_same_type_first_intentional_second_accidental(self):
        """Vérifie le cas P0 :
        - 2 anomalies du même type (Face 0 intentionnelle, Face 1 accidentelle).
        - Le marquage global sans ciblage est refusé (CANCELLED).
        - Le marquage ciblé de Face 0 laisse Face 1 visible, comptabilisée et zoomable.
        """
        obj = self._create_mesh_with_two_concave_ngons()
        bpy.context.scene.meshforge_settings.asset_target_mode = "GAME_ASSET"

        # 1. Analyse initiale
        diag = diagnose_topology(obj, mode="GAME_ASSET")
        findings_map = {f["id"]: f for f in diag["findings"]}

        self.assertIn("topo_ngons_concave:0", findings_map)
        self.assertIn("topo_ngons_concave:1", findings_map)
        self.assertEqual(findings_map["topo_ngons_concave:0"]["severity"], "DEFECT")
        self.assertEqual(findings_map["topo_ngons_concave:1"]["severity"], "DEFECT")

        # 2. Refus du marquage global non ciblé
        res_global = bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave")
        self.assertEqual(res_global, {'CANCELLED'})

        # 3. Marquage granulaire de Face 0 uniquement
        res_gran = bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave:0")
        self.assertEqual(res_gran, {'FINISHED'})

        # 4. Vérification post-marquage
        diag_after = diagnose_topology(obj, mode="GAME_ASSET")
        findings_after = {f["id"]: f for f in diag_after["findings"]}

        # Face 0 est marquée intentionnelle (sous GAME_ASSET, elle devient RISK car non conforme quads/temps réel)
        f0 = findings_after["topo_ngons_concave:0"]
        self.assertTrue(f0.get("is_intentional"))
        self.assertEqual(f0["severity"], "RISK")
        self.assertIn("[Intentionnel non conforme", f0["name"])

        # Face 1 n'est PAS marquée intentionnelle : elle DOIT rester un DEFECT critique
        f1 = findings_after["topo_ngons_concave:1"]
        self.assertFalse(f1.get("is_intentional", False))
        self.assertEqual(f1["severity"], "DEFECT")
        self.assertEqual(f1["indices"], [1])

        # Face 1 est comptabilisée dans les défauts
        self.assertGreaterEqual(diag_after["structured"]["summary_counts"]["defects"], 1)

        # 5. Inspection / Zoom sur la seconde anomalie accidentelle (Face 1)
        res_focus = bpy.ops.meshforge.focus_defect(finding_id="topo_ngons_concave:1")
        self.assertEqual(res_focus, {'FINISHED'})

    def test_02_intentional_vs_goal_compliance(self):
        """Vérifie qu'une géométrie voulue non conforme à l'objectif ne reçoit pas de faux bilan sain :
        - Frontière ouverte sous EXPORT_PREP reste un RISK [Intentionnel non conforme export].
        - Frontière ouverte sous GENERAL devient une OBSERVATION neutre.
        """
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        bpy.context.view_layer.objects.active = plane

        # Marquer l'ouverture comme intentionnelle
        bpy.ops.meshforge.mark_intentional(finding_id="topo_open_boundary", unmark=False)

        # Sous EXPORT_PREP : RISK car non étanche
        diag_export = diagnose_topology(plane, mode="EXPORT_PREP")
        f_export = {f["id"]: f for f in diag_export["findings"]}["topo_open_boundary"]
        self.assertTrue(f_export.get("is_intentional"))
        self.assertEqual(f_export["severity"], "RISK")
        self.assertIn("non conforme export", f_export["name"])

        # Sous GENERAL : OBSERVATION conforme
        diag_gen = diagnose_topology(plane, mode="GENERAL")
        f_gen = {f["id"]: f for f in diag_gen["findings"]}["topo_open_boundary"]
        self.assertTrue(f_gen.get("is_intentional"))
        self.assertEqual(f_gen["severity"], "OBSERVATION")

    # =========================================================================
    # P0 : COHÉRENCE DU CACHE ET DES VALIDATIONS (5 SCÉNARIOS)
    # =========================================================================

    def test_03_scenario_1_edit_mode_modification_staleness(self):
        """Scénario 1 : Modification en Mode Édition -> diagnostic détecté comme périmé."""
        obj = self._create_mesh_with_two_concave_ngons()
        bpy.ops.meshforge.analyze_topology()

        is_stale_before, _ = check_diagnosis_staleness(obj)
        self.assertFalse(is_stale_before)

        # Passage en mode Édition et modification de coordonnées
        bpy.ops.object.mode_set(mode='EDIT')
        is_stale_edit, reason_edit = check_diagnosis_staleness(obj)
        self.assertTrue(is_stale_edit)
        self.assertIn("Mode Édition", reason_edit)

        # Déplacement d'un sommet en mode Édition
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.verts[0].co.x += 10.0
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode='OBJECT')

        # De retour en mode Objet, la bbox a changé -> péremption détectée
        is_stale_after, reason_after = check_diagnosis_staleness(obj)
        self.assertTrue(is_stale_after)

    def test_04_scenario_2_topology_change_after_validation_pruned(self):
        """Scénario 2 : Changement topologique après validation intentionnelle.
        La validation de l'élément modifié/supprimé est purgée et signalée dans pruned_validations.
        """
        obj = self._create_mesh_with_two_concave_ngons()
        bpy.ops.meshforge.analyze_topology()

        # Valider Face 0 comme intentionnelle
        bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave:0")
        self.assertIn("topo_ngons_concave:0", obj.get("_mf_intentional_findings", []))

        # Trianguler Face 0 (supprime le N-gone concave 0)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.triangulate(bm, faces=[bm.faces[0]])
        bm.to_mesh(obj.data)
        bm.free()

        # Nouvelle mesure des faits
        facts_after = measure_mesh_facts(obj)
        pruned = facts_after.get("pruned_validations", [])

        # La validation pour Face 0 a été purgée automatiquement
        self.assertGreater(len(pruned), 0)
        self.assertTrue(any("topo_ngons_concave:0" in p.get("key", "") for p in pruned))
        self.assertNotIn("topo_ngons_concave:0", obj.get("_mf_intentional_findings", []))

        # evaluate_structured_diagnosis signale la réinitialisation
        eval_res = evaluate_structured_diagnosis(facts_after)
        find_pruned = [f for f in eval_res["findings"] if f["id"] == "audit_pruned_validations"]
        self.assertEqual(len(find_pruned), 1)

    def test_05_scenario_3_deletion_recreation_spatial_invalidation(self):
        """Scénario 3 : Suppression puis recréation d'une zone validée.
        L'élément recréé à un autre endroit avec le même index n'est PAS validé silencieusement.
        """
        obj = self._create_mesh_with_two_concave_ngons()
        bpy.ops.meshforge.analyze_topology()

        # Valider Face 0 à sa position X ~ -3
        bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave:0")

        # Supprimer Face 0 et recréer un N-gone à X = +50.0 (déplacement géométrique complet)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES_ONLY')

        # Recréer une nouvelle face avec index réutilisé mais coordonnées totalement distinctes
        nv0 = bm.verts.new((50.0, -1.0, 0.0))
        nv1 = bm.verts.new((52.0, -1.0, 0.0))
        nv2 = bm.verts.new((52.0, 1.0, 0.0))
        nv3 = bm.verts.new((51.0, 0.0, 0.0))
        nv4 = bm.verts.new((50.0, 1.0, 0.0))
        bm.faces.new((nv0, nv1, nv2, nv3, nv4))

        bm.to_mesh(obj.data)
        bm.free()

        # Remesurer : l'écart spatial > 0.1 m invalide la validation ancienne
        facts_after = measure_mesh_facts(obj)
        self.assertNotIn("topo_ngons_concave:0", facts_after.get("intentional_finding_ids", []))
        self.assertGreater(len(facts_after.get("pruned_validations", [])), 0)

    def test_06_scenario_4_goal_change_without_geometry_change(self):
        """Scénario 4 : Changement d'objectif sans modification géométrique.
        Réévaluation immédiate des recommandations sans recalcul géométrique facts.
        """
        obj = self._create_mesh_with_two_concave_ngons()
        bpy.ops.meshforge.analyze_topology()
        cached = _ACTIVE_DIAGNOSIS_CACHE.get(obj.name)
        initial_facts = cached.get("facts")

        # Changement d'objectif de GAME_ASSET vers MECHANICAL_CAD
        props = bpy.context.scene.meshforge_settings
        props.asset_target_mode = 'MECHANICAL_CAD'

        # Le cache a été réévalué instantanément
        diag_cad = _ACTIVE_DIAGNOSIS_CACHE.get(obj.name)
        self.assertEqual(diag_cad["structured"]["profile_id"], "MECHANICAL_CAD")
        # Les faits initiaux sont restés strictement identiques (zéro recalcul)
        self.assertIs(diag_cad.get("facts"), initial_facts)

    def test_07_scenario_5_unmarking_intentional_restores_defect(self):
        """Scénario 5 : Annulation d'un marquage intentionnel.
        L'élément retourne immédiatement dans sa sévérité d'origine (DEFECT).
        """
        obj = self._create_mesh_with_two_concave_ngons()
        bpy.context.scene.meshforge_settings.asset_target_mode = "GAME_ASSET"
        bpy.ops.meshforge.analyze_topology()

        # 1. Marquer Face 0
        bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave:0", unmark=False)
        self.assertIn("topo_ngons_concave:0", obj.get("_mf_intentional_findings", []))

        # 2. Dé-marquer Face 0
        res_unm = bpy.ops.meshforge.mark_intentional(finding_id="topo_ngons_concave:0", unmark=True)
        self.assertEqual(res_unm, {'FINISHED'})
        self.assertNotIn("topo_ngons_concave:0", obj.get("_mf_intentional_findings", []))

        # 3. Vérification immédiate dans le cache
        cached = _ACTIVE_DIAGNOSIS_CACHE.get(obj.name)
        findings_map = {f["id"]: f for f in cached["findings"]}
        f0 = findings_map["topo_ngons_concave:0"]
        self.assertFalse(f0.get("is_intentional", False))
        self.assertEqual(f0["severity"], "DEFECT")


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestGranularAndCacheCoherence)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    return res.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
