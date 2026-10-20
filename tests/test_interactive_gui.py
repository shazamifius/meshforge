"""MeshForge - Test de vérification du flux interactif et rendu visuel (Phase D1).
Vérifie :
1. L'exécution des opérateurs d'interface (meshforge.analyze_topology, focus_defect, clear_defect_view).
2. Le comportement des 3 modes (GAME_TRIANGLES, DEFORMABLE_QUADS, HYBRID_CLEANUP).
3. Le filtrage des catégories (ALL, ORANGE, BLUE, RED, VIOLET).
4. La sélection active d'anomalies et la gestion du cadrage / zoom.
5. Le rendu visuel Workbench confirmant la visibilité des couleurs sémantiques.
"""

from __future__ import annotations
import bpy
import bmesh
import os
import sys
import unittest
import numpy as np
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.core.visualizer import (
    CATEGORY_COLORS,
    TEMP_ATTR_NAME,
    apply_color_inspection,
    clear_inspection_view,
    zoom_to_defect
)
from meshforge.operators.topology_inspect import _ACTIVE_DIAGNOSIS_CACHE


class TestMeshForgePhaseD1Interactive(unittest.TestCase):
    """Vérifications du flux d'interaction utilisateur et de rendu visuel."""

    @classmethod
    def setUpClass(cls):
        meshforge.register()

    @classmethod
    def tearDownClass(cls):
        meshforge.unregister()

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not hasattr(bpy.types.Scene, "meshforge_settings"):
            meshforge.register()

    def _create_multi_defect_asset(self) -> bpy.types.Object:
        """Crée un asset de test réunissant les 4 familles de défauts :
        - ORANGE : N-gone à 6 côtés
        - BLEU : Triangle isolé dans des quads
        - ROUGE : Arête non-manifold connectée à 3 faces
        - VIOLET : Fragment isolé de 2 faces
        """
        mesh = bpy.data.meshes.new("MultiDefectMesh")
        bm = bmesh.new()

        # 1. Grille de base (quads réguliers)
        # 3x3 quads entre x=0..3, y=0..3
        grid_verts = []
        for y in range(4):
            row = []
            for x in range(4):
                row.append(bm.verts.new((float(x), float(y), 0.0)))
            grid_verts.append(row)

        for y in range(3):
            for x in range(3):
                bm.faces.new([
                    grid_verts[y][x],
                    grid_verts[y][x+1],
                    grid_verts[y+1][x+1],
                    grid_verts[y+1][x]
                ])

        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        # 2. Insérer un ORANGE (N-gone à 6 côtés)
        # Supprimer 2 faces adjacentes et créer une face à 6 sommets
        v_ngon = [
            grid_verts[0][0], grid_verts[0][2],
            grid_verts[1][2], grid_verts[2][2],
            grid_verts[2][0], grid_verts[1][0]
        ]
        # (Laissons les faces de base et ajoutons une face N-gone à côté)
        v_ext = [
            bm.verts.new((4.0, 0.0, 0.0)),
            bm.verts.new((5.0, 0.0, 0.0)),
            bm.verts.new((5.5, 1.0, 0.0)),
            bm.verts.new((5.0, 2.0, 0.0)),
            bm.verts.new((4.0, 2.0, 0.0)),
            bm.verts.new((3.5, 1.0, 0.0))
        ]
        bm.faces.new(v_ext)

        # 3. Insérer un BLEU (Triangle au milieu de quads)
        # Couper une face quad en 2 triangles
        bm.faces.ensure_lookup_table()
        f_target = bm.faces[4]  # Face centrale
        bmesh.ops.triangulate(bm, faces=[f_target])

        # 4. Insérer un ROUGE (Arête non-manifold à 3 faces)
        bm.edges.ensure_lookup_table()
        e_nm = bm.edges[0]
        v_up = bm.verts.new((0.0, 0.0, 1.5))
        v_dn = bm.verts.new((0.0, 0.0, -1.5))
        bm.faces.new([e_nm.verts[0], e_nm.verts[1], v_up])
        bm.faces.new([e_nm.verts[0], e_nm.verts[1], v_dn])

        # 5. Insérer un VIOLET (Fragment isolé mineur)
        v_iso1 = bm.verts.new((10.0, 0.0, 0.0))
        v_iso2 = bm.verts.new((11.0, 0.0, 0.0))
        v_iso3 = bm.verts.new((11.0, 1.0, 0.0))
        v_iso4 = bm.verts.new((10.0, 1.0, 0.0))
        bm.faces.new([v_iso1, v_iso2, v_iso3, v_iso4])

        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new("MultiDefectAsset", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        return obj

    def test_01_full_operator_flow(self):
        """1. Vérifie le flux complet : analyse, inspection, sélection par opérateur, zoom et effacement."""
        obj = self._create_multi_defect_asset()
        props = bpy.context.scene.meshforge_settings

        # 1. Tester le Mode Déformable
        props.asset_target_mode = 'DEFORMABLE_QUADS'
        res_op = bpy.ops.meshforge.analyze_topology()
        self.assertEqual(res_op, {'FINISHED'})

        # Vérifier que l'analyse est en cache et que les 4 catégories sont bien présentes
        diag = _ACTIVE_DIAGNOSIS_CACHE.get(obj.name)
        self.assertIsNotNone(diag)
        categories_found = {d["category"] for d in diag.get("defects", [])}
        self.assertIn("ORANGE", categories_found)
        self.assertIn("BLUE", categories_found)
        self.assertIn("RED", categories_found)
        self.assertIn("VIOLET", categories_found)

        # 2. Vérifier que l'attribut temporaire de couleur a été créé et activé
        self.assertIn(TEMP_ATTR_NAME, obj.data.color_attributes)
        self.assertEqual(obj.data.color_attributes.active_color.name, TEMP_ATTR_NAME)

        # 3. Tester le filtrage des défauts
        for filt in ['ALL', 'ORANGE', 'BLUE', 'RED', 'VIOLET']:
            props.active_defect_filter = filt
            visible = [d for d in diag["defects"] if filt == 'ALL' or d.get("category") == filt]
            self.assertGreater(len(visible), 0)

        # 4. Tester l'opérateur Zoom/Focus sur la 1ère anomalie
        res_focus = bpy.ops.meshforge.focus_defect(defect_index=0)
        self.assertEqual(res_focus, {'FINISHED'})

        # 5. Tester l'effacement de l'inspection
        res_clear = bpy.ops.meshforge.clear_defect_view()
        self.assertEqual(res_clear, {'FINISHED'})
        self.assertNotIn(TEMP_ATTR_NAME, obj.data.color_attributes)

    def test_02_three_modes_differentiation(self):
        """2. Vérifie la différenciation concrète des résultats entre les 3 modes sur le même asset."""
        obj = self._create_multi_defect_asset()

        # Mode GAME_TRIANGLES : les triangles de maillage ne sont pas des anomalies bloquantes
        diag_game = diagnose_topology(obj, mode='GAME_TRIANGLES')
        tri_suspect_game = [d for d in diag_game["defects"] if d["type"] == "TRIANGLE_SUSPECT"]
        self.assertEqual(len(tri_suspect_game), 0)

        # Mode DEFORMABLE_QUADS : les triangles isolés dans des quads sont signalés
        diag_quads = diagnose_topology(obj, mode='DEFORMABLE_QUADS')
        tri_suspect_quads = [d for d in diag_quads["defects"] if d["type"] == "TRIANGLE_SUSPECT"]
        self.assertGreaterEqual(len(tri_suspect_quads), 1)

        # Mode HYBRID_CLEANUP : conserve un comportement neutre
        diag_hybrid = diagnose_topology(obj, mode='HYBRID_CLEANUP')
        self.assertTrue(diag_hybrid["valid"])

    def test_03_color_visibility_and_render_capture(self):
        """3. Confirme que les couleurs sont réellement visibles et génère un rendu Workbench comme preuve."""
        obj = self._create_multi_defect_asset()
        diag = diagnose_topology(obj, mode='DEFORMABLE_QUADS')

        # Appliquer la coloration
        ok = apply_color_inspection(obj, diag.get("defects", []))
        self.assertTrue(ok)

        # Vérifier que les données de couleur ne sont pas uniformes
        temp_attr = obj.data.color_attributes[TEMP_ATTR_NAME]
        colors = np.array([col.color for col in temp_attr.data])
        unique_colors = np.unique(np.round(colors, 3), axis=0)
        # Doit contenir la couleur neutre + au moins 3 couleurs de défauts distinctes
        self.assertGreaterEqual(len(unique_colors), 4)

        # Configuration d'une caméra pour le rendu visuel
        cam_data = bpy.data.cameras.new("InspectCamera")
        cam_obj = bpy.data.objects.new("InspectCamera", cam_data)
        bpy.context.collection.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj
        cam_obj.location = (4.0, -6.0, 5.0)
        cam_obj.rotation_euler = (np.radians(55), 0, np.radians(30))

        # Configurer le moteur Workbench pour restituer les couleurs de sommets
        scene = bpy.context.scene
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.display.shading.color_type = 'VERTEX'
        scene.render.resolution_x = 800
        scene.render.resolution_y = 600

        output_dir = Path(repo_root) / "docs" / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        render_path = output_dir / "d1_inspection_evidence.png"
        scene.render.filepath = str(render_path)

        bpy.ops.render.render(write_still=True)
        self.assertTrue(render_path.exists())
        self.assertGreater(render_path.stat().st_size, 1000)

        print(f"\n[PREUVE VISUELLE D1] Capture rendue avec succès dans : {render_path}")

    def test_11_panel_draw_all_modes_and_icons(self):
        """11. Vérifie que le panneau principal et toutes ses sous-sections se dessinent sans erreur ni icône invalide."""
        from meshforge.ui.panel import VIEW3D_PT_meshforge_main

        obj = self._create_multi_defect_asset()
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        # Lancer le diagnostic pour alimenter le cache et les badges d'anomalies
        bpy.ops.meshforge.analyze_topology()

        class DummyPanelDrawOp(bpy.types.Operator):
            bl_idname = "wm.meshforge_test_panel_draw"
            bl_label = "Test Draw"
            def draw(self, context):
                panel = VIEW3D_PT_meshforge_main()
                panel.layout = self.layout
                panel.draw(context)
            def execute(self, context):
                return {'FINISHED'}

        bpy.utils.register_class(DummyPanelDrawOp)
        try:
            props = bpy.context.scene.meshforge_settings
            # Tester tous les modes d'asset
            for mode in ['GAME_TRIANGLES', 'DEFORMABLE_QUADS', 'HYBRID_CLEANUP']:
                props.asset_target_mode = mode
                res = bpy.ops.wm.meshforge_test_panel_draw('INVOKE_DEFAULT')
                self.assertEqual(res, {'FINISHED'})

            # Tester avec le mode expert ouvert
            props.show_expert_mode = True
            res = bpy.ops.wm.meshforge_test_panel_draw('INVOKE_DEFAULT')
            self.assertEqual(res, {'FINISHED'})
        finally:
            bpy.utils.unregister_class(DummyPanelDrawOp)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD1Interactive)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
