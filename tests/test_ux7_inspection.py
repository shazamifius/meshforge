"""MeshForge - Tests unitaires ciblés pour la Phase UX7.
Vérifie :
1. UX7.1 : Focus précis sur les anomalies (coordonnées monde, distance proportionnelle, 3D cursor, différents types d'éléments, gestion défensive des indices).
2. UX7.2 : Détection de péremption du diagnostic (staleness), seuil d'actualisation et nettoyage strict des attributs.
3. UX7.3 : Interrupteur de mode filaire, mémorisation d'état et restauration.
4. UX7.4 : Système de couleurs sémantiques, hiérarchie de priorité et intégrité.
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
import time
from mathutils import Vector

import meshforge
from meshforge.core.visualizer import (
    CATEGORY_COLORS,
    TEMP_ATTR_NAME,
    zoom_to_defect,
    select_defect,
    apply_color_inspection,
    clear_inspection_view,
    _find_active_3d_spaces
)
from meshforge.operators.topology_inspect import (
    _ACTIVE_DIAGNOSIS_CACHE,
    check_diagnosis_staleness,
    mark_diagnosis_stale,
    AUTO_REFRESH_TRIANGLE_THRESHOLD
)
from meshforge.operators.restore import (
    _WIREFRAME_ENABLED_BY_MESHFORGE,
    restore_wireframe_if_meshforge_enabled
)
from meshforge.core.topology_diagnosis import diagnose_topology


class TestMeshForgePhaseUX7(unittest.TestCase):
    """Suite de tests ciblés pour l'ergonomie d'inspection et la fiabilité du workflow (UX7)."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        # Nettoyage systématique de la scène
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            bpy.data.meshes.remove(mesh, do_unlink=True)
        _ACTIVE_DIAGNOSIS_CACHE.clear()
        _WIREFRAME_ENABLED_BY_MESHFORGE.clear()

    def _create_test_mesh_with_spaced_defects(self) -> bpy.types.Object:
        """Crée un maillage contenant deux défauts géométriques très espacés :
        - Défaut 1 (N-gone à 5 côtés) centré autour de (+10, +10, 0)
        - Défaut 2 (Face nulle) située à (-10, -10, 0)
        L'objet a une transformation monde non nulle (location=(2, 3, 0), scale=(1.5, 1.5, 1.5)).
        """
        mesh = bpy.data.meshes.new("UX7_Spaced_Mesh")
        obj = bpy.data.objects.new("UX7_Spaced_Object", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        obj.location = (2.0, 3.0, 0.0)
        obj.scale = (1.5, 1.5, 1.5)
        bpy.context.view_layer.update()

        bm = bmesh.new()
        # N-gone à 5 côtés centré vers (+10, +10, 0) en local
        v0 = bm.verts.new((9.0, 9.0, 0.0))
        v1 = bm.verts.new((11.0, 9.0, 0.0))
        v2 = bm.verts.new((11.5, 10.0, 0.0))
        v3 = bm.verts.new((11.0, 11.0, 0.0))
        v4 = bm.verts.new((9.0, 11.0, 0.0))
        bm.faces.new([v0, v1, v2, v3, v4])

        # Face nulle à (-10, -10, 0) en local
        vd0 = bm.verts.new((-10.0, -10.0, 0.0))
        vd1 = bm.verts.new((-10.0, -10.0, 0.0))
        vd2 = bm.verts.new((-9.0, -10.0, 0.0))
        bm.faces.new([vd0, vd1, vd2])

        # Sommet orphelin à (0, 0, 5) en local
        bm.verts.new((0.0, 0.0, 5.0))

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        return obj

    # =========================================================================
    # UX7.1 — FOCUS PRÉCIS SUR LES ANOMALIES
    # =========================================================================

    def test_01_focus_defect_world_coordinates_and_distance(self):
        """1. Vérifie que zoom_to_defect calcule les coordonnées monde exactes et oriente la caméra."""
        obj = self._create_test_mesh_with_spaced_defects()
        diag = diagnose_topology(obj, mode='GENERAL')
        defects = diag["defects"]
        self.assertGreaterEqual(len(defects), 2)

        ngon_def = next(d for d in defects if d["type"] == "NGON")
        zero_def = next(d for d in defects if d["type"] == "ZERO_AREA_FACE")

        # 1. Test du cadrage sur le N-gone
        ok_ngon, msg_ngon = zoom_to_defect(ngon_def, bpy.context, obj=obj)
        # En mode headless/background sans vue 3D, retourne False proprement avec message explicite
        spaces_3d = _find_active_3d_spaces(bpy.context)
        if spaces_3d:
            self.assertTrue(ok_ngon)
            cursor_loc = bpy.context.scene.cursor.location.copy()
            # Le centre local du n-gone est ~ (10.3, 10.0, 0.0)
            # En monde avec location=(2, 3, 0) et scale=(1.5, 1.5, 1.5) : X = 2 + 10.3*1.5 = ~17.45
            self.assertGreater(cursor_loc.x, 15.0)
            self.assertGreater(cursor_loc.y, 15.0)

            # 2. Test du cadrage sur la face nulle
            ok_zero, msg_zero = zoom_to_defect(zero_def, bpy.context, obj=obj)
            self.assertTrue(ok_zero)
            cursor_zero = bpy.context.scene.cursor.location.copy()
            # Le centre local est ~ (-9.66, -10.0, 0.0) -> en monde : X = 2 - 9.66*1.5 = ~ -12.5
            self.assertLess(cursor_zero.x, -5.0)
            self.assertLess(cursor_zero.y, -5.0)

            # Vérifie que les deux cadrages ont conduit à des positions mondes distinctes
            dist = (cursor_loc - cursor_zero).length
            self.assertGreater(dist, 20.0, "Les deux défauts doivent avoir des points focaux nettement distincts !")
        else:
            self.assertFalse(ok_ngon)
            self.assertIn("Aucune vue 3D active", msg_ngon)

    def test_02_focus_defect_element_types_and_selection(self):
        """2. Vérifie la sélection et le cadrage pour les 3 types géométriques : FACE, EDGE, VERT."""
        obj = self._create_test_mesh_with_spaced_defects()
        mesh = obj.data

        # Test FACE
        face_defect = {"element_type": "FACE", "indices": [0], "center": (10, 10, 0)}
        self.assertTrue(select_defect(obj, face_defect))
        self.assertTrue(mesh.polygons[0].select)
        self.assertFalse(mesh.polygons[1].select)

        # Test VERT (Sommet orphelin)
        vert_defect = {"element_type": "VERT", "indices": [8], "center": (0, 0, 5)}
        self.assertTrue(select_defect(obj, vert_defect))
        self.assertFalse(mesh.polygons[0].select)
        self.assertTrue(mesh.vertices[8].select)

        # Test EDGE
        edge_defect = {"element_type": "EDGE", "indices": [1], "center": (10, 10, 0)}
        self.assertTrue(select_defect(obj, edge_defect))
        self.assertTrue(mesh.edges[1].select)
        self.assertFalse(mesh.vertices[8].select)

    def test_03_focus_defect_defensive_invalid_indices_and_fallbacks(self):
        """3. Robustesse : indices hors bornes (maillage modifié) ou objet invalide."""
        obj = self._create_test_mesh_with_spaced_defects()

        # Defect avec index de face complètement invalide (ex: face 9999)
        bad_defect = {
            "element_type": "FACE",
            "indices": [9999],
            "center": (10.0, 10.0, 0.0)
        }
        # Ne doit pas lever d'IndexError, doit utiliser le centre de repli
        ok, msg = zoom_to_defect(bad_defect, bpy.context, obj=obj)
        spaces_3d = _find_active_3d_spaces(bpy.context)
        if spaces_3d:
            self.assertTrue(ok)
        else:
            self.assertFalse(ok)

        # Defect sans aucun centre ni coordonnée
        empty_defect = {"element_type": "FACE", "indices": [9999]}
        ok_empty, msg_empty = zoom_to_defect(empty_defect, bpy.context, obj=obj)
        self.assertFalse(ok_empty)
        self.assertIn("introuvables", msg_empty)

    # =========================================================================
    # UX7.2 — ACTUALISATION DU DIAGNOSTIC ET PÉREMPTION
    # =========================================================================

    def test_04_diagnosis_staleness_detection(self):
        """4. Vérifie que la modification de la topologie rend immédiatement le diagnostic périmé."""
        obj = self._create_test_mesh_with_spaced_defects()
        bpy.ops.meshforge.analyze_topology()

        # Immédiatement après analyse : diagnostic frais et valide
        is_stale, reason = check_diagnosis_staleness(obj)
        self.assertFalse(is_stale)
        self.assertIsNone(reason)

        # Modification de la topologie : ajout d'un sommet
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.new((99.0, 99.0, 99.0))
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        # Vérifie que la détection de péremption réagit instantanément
        is_stale_after, reason_after = check_diagnosis_staleness(obj)
        self.assertTrue(is_stale_after)
        self.assertIn("Topologie modifiée", reason_after)

    def test_05_clear_inspection_view_preserves_user_attributes(self):
        """5. Vérifie que clear_inspection_view restaure l'attribut utilisateur et ne détruit rien."""
        obj = self._create_test_mesh_with_spaced_defects()
        mesh = obj.data

        # Créer un attribut utilisateur préexistant
        user_col = mesh.color_attributes.new(name="MonCalqueArtiste", type='FLOAT_COLOR', domain='CORNER')
        mesh.color_attributes.active_color = user_col
        self.assertEqual(mesh.color_attributes.active_color.name, "MonCalqueArtiste")

        # Lancer l'analyse (injecte _MF_Inspection_Temp)
        bpy.ops.meshforge.analyze_topology()
        self.assertIn(TEMP_ATTR_NAME, mesh.color_attributes)
        self.assertEqual(mesh.color_attributes.active_color.name, TEMP_ATTR_NAME)

        # Effacer l'inspection
        bpy.ops.meshforge.clear_defect_view()
        self.assertNotIn(TEMP_ATTR_NAME, mesh.color_attributes)
        self.assertIn("MonCalqueArtiste", mesh.color_attributes)
        self.assertEqual(mesh.color_attributes.active_color.name, "MonCalqueArtiste")
        self.assertNotIn(obj.name, _ACTIVE_DIAGNOSIS_CACHE)

    # =========================================================================
    # UX7.3 — INTERRUPTEUR DE MODE FILAIRE
    # =========================================================================

    def test_06_toggle_wireframe_lifecycle_and_restoration(self):
        """6. Vérifie le cycle complet de l'interrupteur filaire et sa restauration à la fermeture."""
        obj = self._create_test_mesh_with_spaced_defects()
        self.assertFalse(obj.show_wire)

        # 1. Activation
        bpy.ops.meshforge.toggle_wireframe()
        self.assertTrue(obj.show_wire)
        self.assertTrue(obj.show_all_edges)
        self.assertIn(obj.name, _WIREFRAME_ENABLED_BY_MESHFORGE)

        # 2. Désactivation manuelle
        bpy.ops.meshforge.toggle_wireframe()
        self.assertFalse(obj.show_wire)
        self.assertNotIn(obj.name, _WIREFRAME_ENABLED_BY_MESHFORGE)

        # 3. Activation puis fermeture d'inspection
        bpy.ops.meshforge.toggle_wireframe()
        self.assertTrue(obj.show_wire)
        bpy.ops.meshforge.clear_defect_view()
        self.assertFalse(obj.show_wire, "clear_defect_view doit restaurer l'affichage normal sans filaire !")

    # =========================================================================
    # UX7.4 — SYSTÈME DE COULEURS SÉMANTIQUES
    # =========================================================================

    def test_07_semantic_color_palette_and_priority(self):
        """7. Vérifie la palette sémantique complète (ORANGE, BLUE, RED, VIOLET, YELLOW, NEUTRAL)."""
        self.assertIn('ORANGE', CATEGORY_COLORS)
        self.assertIn('BLUE', CATEGORY_COLORS)
        self.assertIn('RED', CATEGORY_COLORS)
        self.assertIn('VIOLET', CATEGORY_COLORS)
        self.assertIn('YELLOW', CATEGORY_COLORS)
        self.assertIn('NEUTRAL', CATEGORY_COLORS)

        obj = self._create_test_mesh_with_spaced_defects()
        mesh = obj.data

        # Face 0 a un N-gone (ORANGE) ET une face nulle sur Face 1 (RED)
        defects = [
            {"element_type": "FACE", "indices": [0], "category": "ORANGE"},
            {"element_type": "FACE", "indices": [0], "category": "RED"} # Même face avec défaut critique
        ]
        apply_color_inspection(obj, defects)
        temp_attr = mesh.color_attributes.get(TEMP_ATTR_NAME)
        self.assertIsNotNone(temp_attr)

        # Vérifie que la couleur appliquée sur Face 0 est bien ROUGE (priorité max)
        poly0 = mesh.polygons[0]
        loop0_col = temp_attr.data[poly0.loop_indices[0]].color
        red_col = CATEGORY_COLORS['RED']
        self.assertAlmostEqual(loop0_col[0], red_col[0], places=2)
        self.assertAlmostEqual(loop0_col[1], red_col[1], places=2)
        self.assertAlmostEqual(loop0_col[2], red_col[2], places=2)

    def test_08_properties_and_legend_switches(self):
        """8. Vérifie la présence de show_color_legend et des options de filtre complètes."""
        props = bpy.context.scene.meshforge_settings
        self.assertTrue(hasattr(props, "show_color_legend"))
        props.show_color_legend = True
        self.assertTrue(props.show_color_legend)

        # Vérifie la présence de YELLOW dans active_defect_filter
        filter_items = [item.identifier for item in props.bl_rna.properties["active_defect_filter"].enum_items]
        self.assertIn('YELLOW', filter_items)
        self.assertIn('ORANGE', filter_items)
        self.assertIn('RED', filter_items)
        self.assertIn('BLUE', filter_items)
        self.assertIn('VIOLET', filter_items)


if __name__ == "__main__":
    import sys
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseUX7)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
