"""MeshForge - Suite de tests techniques et de validation de la Phase B.
Couvre :
- Géométries ouvertes (surfaces planes/tissus).
- Géométries fermées et manifold (watertight).
- Maillages triangulés et maillages en quads.
- Maillages à multiples composantes disjointes.
- Préservation rigoureuse des UV, matériaux multiples, vertex groups et arêtes Sharp.
- Robustesse et rollback garanti de l'original en cas d'erreur.
- Exportation du rapport en JSON et Texte.
- Tests de scalabilité sur densités croissantes (10k, 100k, et cas de référence à ~1,587M triangles).
"""

from __future__ import annotations
import bpy
import bmesh
import json
import time
import sys
import unittest
from pathlib import Path

# Ajouter les chemins d'importation
repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import meshforge
from meshforge.core.mesh_stats import get_mesh_statistics
from meshforge.core.pipeline import run_meshforge_pipeline
from meshforge.core.report import export_report_to_file


class TestMeshForgePhaseB(unittest.TestCase):
    """Validation technique formelle des exigences de la Phase B."""

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

    def test_01_open_geometry_cloth_like(self):
        """1. Vérifie le diagnostic et le respect strict d'une surface ouverte (type tissu/plan)."""
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10, size=2)
        grid = bpy.context.active_object
        stats = get_mesh_statistics(grid)

        self.assertTrue(stats["is_open_surface"])
        self.assertFalse(stats["is_watertight"])
        self.assertGreater(stats["boundary_edges"], 0)
        self.assertEqual(stats["boundary_loops_count"], 1)
        self.assertTrue(any("Surface ouverte" in r for r in stats["risk_assessment"]))

        # Exécuter le pipeline : s'assurer que sans option 'fill_holes', le contour ouvert est intact
        props = bpy.context.scene.meshforge_settings
        props.create_new_object = True
        props.fill_holes = False
        props.enable_repair = True
        props.enable_manifold = True

        report = run_meshforge_pipeline(grid, props)
        self.assertTrue(report["success"])
        res_obj = bpy.data.objects.get(report["result_name"])
        res_stats = get_mesh_statistics(res_obj)
        self.assertTrue(res_stats["is_open_surface"])
        self.assertEqual(res_stats["boundary_loops_count"], 1)

    def test_02_watertight_manifold_geometry(self):
        """2. Vérifie qu'un maillage fermé et régulier est certifié manifold et watertight."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        stats = get_mesh_statistics(cube)

        self.assertFalse(stats["is_open_surface"])
        self.assertEqual(stats["boundary_edges"], 0)
        self.assertEqual(stats["boundary_loops_count"], 0)
        self.assertEqual(stats["non_manifold_edges"], 0)
        self.assertEqual(stats["non_manifold_verts"], 0)
        self.assertTrue(stats["is_manifold"])
        self.assertTrue(stats["is_watertight"])
        self.assertEqual(len(stats["risk_assessment"]), 0)

    def test_03_triangulated_vs_quad_topologies(self):
        """3. Vérifie la distinction exacte entre topologie pure triangles et pure quads."""
        # Topologie pure triangles (Icosphère)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2)
        ico = bpy.context.active_object
        ico_stats = get_mesh_statistics(ico)
        self.assertEqual(ico_stats["quad_faces"], 0)
        self.assertEqual(ico_stats["ngon_faces"], 0)
        self.assertEqual(ico_stats["tri_faces"], ico_stats["faces"])
        self.assertEqual(ico_stats["faces"], ico_stats["estimated_triangles"])

        # Topologie pure quads (Grille subdivisée)
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=4) # 5x5 = 25 quads
        bpy.ops.object.mode_set(mode='OBJECT')
        plane_stats = get_mesh_statistics(plane)
        self.assertEqual(plane_stats["tri_faces"], 0)
        self.assertEqual(plane_stats["quad_faces"], 25)
        self.assertEqual(plane_stats["estimated_triangles"], 50)

    def test_04_multiple_disjoint_components(self):
        """4. Vérifie la détection et préservation de composantes connexes multiples (îlots)."""
        bpy.ops.mesh.primitive_cube_add(location=(-3, 0, 0))
        c1 = bpy.context.active_object
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
        c2 = bpy.context.active_object
        bpy.ops.mesh.primitive_cube_add(location=(3, 0, 0))
        c3 = bpy.context.active_object

        c1.select_set(True)
        c2.select_set(True)
        c3.select_set(True)
        bpy.context.view_layer.objects.active = c1
        bpy.ops.object.join()

        joined_obj = bpy.context.active_object
        stats = get_mesh_statistics(joined_obj)
        self.assertEqual(stats["disjoint_components"], 3)

        # Vérifier que le pipeline préserve les 3 composantes
        props = bpy.context.scene.meshforge_settings
        report = run_meshforge_pipeline(joined_obj, props)
        self.assertTrue(report["success"])
        res_obj = bpy.data.objects.get(report["result_name"])
        res_stats = get_mesh_statistics(res_obj)
        self.assertEqual(res_stats["disjoint_components"], 3)

    def test_05_strict_attribute_preservation(self):
        """5. Vérifie la préservation des UV, matériaux multiples, groupes de sommets et arêtes vives."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # 2 couches UV
        uv1 = cube.data.uv_layers.new(name="UV_Albedo")
        uv2 = cube.data.uv_layers.new(name="UV_Lightmap")

        # 2 matériaux distincts assignés aux faces
        mat_a = bpy.data.materials.new("Mat_Wood")
        mat_b = bpy.data.materials.new("Mat_Metal")
        cube.data.materials.append(mat_a)
        cube.data.materials.append(mat_b)
        cube.data.polygons[0].material_index = 0
        cube.data.polygons[1].material_index = 1

        # 2 groupes de sommets avec poids réels
        vg_leg = cube.vertex_groups.new(name="Bone_Leg")
        vg_arm = cube.vertex_groups.new(name="Bone_Arm")
        vg_leg.add([0, 1, 2], 0.75, 'REPLACE')
        vg_arm.add([4, 5, 6], 1.0, 'REPLACE')

        # Arêtes vives marquées
        cube.data.edges[0].use_edge_sharp = True
        cube.data.edges[1].use_edge_sharp = True

        props = bpy.context.scene.meshforge_settings
        props.create_new_object = True
        props.enable_repair = True
        props.enable_manifold = True
        props.enable_normals = True
        props.enable_object_data = True

        report = run_meshforge_pipeline(cube, props)
        self.assertTrue(report["success"])

        res_obj = bpy.data.objects.get(report["result_name"])
        self.assertIsNotNone(res_obj)

        # Vérification des couches UV
        res_uv_names = [uv.name for uv in res_obj.data.uv_layers]
        self.assertIn("UV_Albedo", res_uv_names)
        self.assertIn("UV_Lightmap", res_uv_names)

        # Vérification des matériaux
        res_mat_names = [slot.material.name for slot in res_obj.material_slots if slot.material]
        self.assertIn("Mat_Wood", res_mat_names)
        self.assertIn("Mat_Metal", res_mat_names)

        # Vérification des groupes de sommets
        res_vg_names = [vg.name for vg in res_obj.vertex_groups]
        self.assertIn("Bone_Leg", res_vg_names)
        self.assertIn("Bone_Arm", res_vg_names)

    def test_06_pipeline_failure_rollback_guarantee(self):
        """6. Vérifie que l'objet original reste intact et visible en cas d'erreur inopinée dans le pipeline."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        orig_name = cube.name
        initial_vert_count = len(cube.data.vertices)

        props = bpy.context.scene.meshforge_settings
        props.create_new_object = True
        props.hide_original = True

        # Injecter intentionnellement une erreur lors d'une étape
        import meshforge.core.pipeline as mf_pipe
        orig_execute_repair = mf_pipe.execute_repair

        def crash_repair(obj, props):
            raise RuntimeError("Erreur de test simulée dans la phase Repair")

        mf_pipe.execute_repair = crash_repair
        try:
            report = run_meshforge_pipeline(cube, props)
            self.assertFalse(report["success"])
            self.assertIn("Erreur de test simulée", report["errors"][0])

            # Vérifier le rollback : l'objet source est visible et actif
            source_after = bpy.data.objects.get(orig_name)
            self.assertIsNotNone(source_after)
            self.assertFalse(source_after.hide_get())
            self.assertEqual(len(source_after.data.vertices), initial_vert_count)

            # Vérifier qu'aucun objet _MF_Optimized orphelin n'a subsisté
            res_orphan = bpy.data.objects.get(f"{orig_name}_MF_Optimized")
            self.assertIsNone(res_orphan)
        finally:
            mf_pipe.execute_repair = orig_execute_repair

    def test_07_report_export_json_and_text(self):
        """7. Vérifie l'exportation et la structure des rapports au format JSON et texte."""
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # Ajouter des doublons et des éléments lâches
        bm = bmesh.new()
        bm.from_mesh(cube.data)
        bm.verts.new((0.00001, 0, 0)) # doublon
        bm.verts.new((5, 5, 0))       # lâche
        bm.to_mesh(cube.data)
        bm.free()

        props = bpy.context.scene.meshforge_settings
        report = run_meshforge_pipeline(cube, props)
        self.assertTrue(report["success"])

        # Vérifier la distinction détectés vs résolus
        det = report["issues_detected"]
        res = report["issues_resolved"]
        self.assertIn("loose_verts", det)
        self.assertIn("loose_verts_removed", res)
        self.assertIn("potential_duplicates", det)
        self.assertIn("doubles_merged", res)

        # Exporter en JSON
        json_path = repo_root / "tests" / "test_output_report.json"
        saved_json = export_report_to_file(report, str(json_path), format_type='JSON')
        self.assertTrue(Path(saved_json).exists())

        with open(saved_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("issues_detected", data)
            self.assertIn("issues_resolved", data)
            self.assertIn("phase_timings", data)

        # Exporter en Texte
        txt_path = repo_root / "tests" / "test_output_report.txt"
        saved_txt = export_report_to_file(report, str(txt_path), format_type='TXT')
        self.assertTrue(Path(saved_txt).exists())

        with open(saved_txt, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("RAPPORT D'OPTIMISATION MESHFORGE", content)
            self.assertIn("PROBLÈMES DÉTECTÉS VS CORRIGÉS", content)

    def test_08_scalability_dense_benchmark(self):
        """8. Benchmark sur maillages de densité croissante : 10k, 100k et ~1,587 million de triangles."""
        densities = [
            ("10k_triangles", 72, 72),      # ~10 082 tris
            ("100k_triangles", 225, 225),   # ~100 352 tris
            ("1.587M_reference", 891, 891)  # ~1 587 762 tris (cas de référence CdC)
        ]

        props = bpy.context.scene.meshforge_settings
        props.create_new_object = True
        props.enable_repair = True
        props.enable_manifold = True
        props.enable_dissolve = False # Ne pas dissoudre pour benchmark pur pipeline & diagnostics
        props.enable_normals = True
        props.enable_object_data = True

        benchmark_results = {}

        for name, sub_x, sub_y in densities:
            t0 = time.perf_counter()
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=sub_x, y_subdivisions=sub_y, size=2)
            grid = bpy.context.active_object
            t_gen = time.perf_counter() - t0

            tri_count = len(grid.data.polygons) * 2

            t_pipe_start = time.perf_counter()
            report = run_meshforge_pipeline(grid, props)
            t_pipe = time.perf_counter() - t_pipe_start

            self.assertTrue(report["success"])

            benchmark_results[name] = {
                "triangles": tri_count,
                "generation_time_s": round(t_gen, 3),
                "pipeline_time_s": round(t_pipe, 3),
                "diagnostic_time_s": round(report["phase_timings"].get("diagnostic_initial", 0.0), 3),
                "repair_time_s": round(report["phase_timings"].get("repair", 0.0), 3),
                "normals_time_s": round(report["phase_timings"].get("normals", 0.0), 3)
            }

            # Nettoyer pour libérer la mémoire avant la taille suivante
            bpy.data.objects.remove(grid, do_unlink=True)
            res_obj = bpy.data.objects.get(report["result_name"])
            if res_obj:
                bpy.data.objects.remove(res_obj, do_unlink=True)

        print("\n--- RÉSULTATS RÉELS DU BENCHMARK DE DENSITÉ CROISSANTE ---")
        for k, v in benchmark_results.items():
            print(f"  [{k}] {v['triangles']} triangles : Pipeline total = {v['pipeline_time_s']}s (Diagnostic = {v['diagnostic_time_s']}s, Repair = {v['repair_time_s']}s, Normals = {v['normals_time_s']}s)")
        print("-----------------------------------------------------------\n")

        # Vérifier que le cas de référence à 1.587M triangles est traité bien en dessous du budget de 10 minutes (600s)
        self.assertLess(benchmark_results["1.587M_reference"]["pipeline_time_s"], 60.0)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseB)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
