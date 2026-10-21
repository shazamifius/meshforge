"""MeshForge Maya - Automated Tests for Decimation and Surface Validation."""

import unittest
import maya.cmds as cmds
import maya.standalone

class TestMeshForgeMayaDecimate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            maya.standalone.initialize()
        except RuntimeError:
            pass

    def setUp(self):
        cmds.file(new=True, force=True)

    def test_01_percentage_edge_collapse(self):
        """Verifies edge collapse QEM reduction by percentage."""
        from meshforge_maya.core.simplification import execute_simplification
        from meshforge_maya.core.mesh_stats import get_mesh_statistics

        sphere = cmds.polySphere(name="test_sphere", subdivisionsX=20, subdivisionsY=20)[0]
        stats_init = get_mesh_statistics(sphere)
        init_tris = stats_init["triangles"]

        # Reduce by 50%
        res = execute_simplification(sphere, mode="PERCENTAGE", percentage=50.0)
        self.assertTrue(res["success"])

        stats_after = get_mesh_statistics(sphere)
        after_tris = stats_after["triangles"]

        self.assertLess(after_tris, init_tris)
        self.assertGreater(res["reduction_percentage"], 30.0)

    def test_02_target_triangles_budget(self):
        """Verifies edge collapse decimation stopping near a target triangle budget."""
        from meshforge_maya.core.simplification import execute_simplification
        from meshforge_maya.core.mesh_stats import get_mesh_statistics

        sphere = cmds.polySphere(name="test_sphere_budget", subdivisionsX=30, subdivisionsY=30)[0]
        target_budget = 400

        res = execute_simplification(sphere, mode="BUDGET_TRIANGLES", target_triangles=target_budget)
        self.assertTrue(res["success"])

        stats_after = get_mesh_statistics(sphere)
        self.assertLessEqual(stats_after["triangles"], target_budget + 100)

    def test_03_blendshape_guard(self):
        """Verifies detection of blendshapes to protect rigged characters."""
        from meshforge_maya.core.mesh_stats import get_mesh_statistics

        base = cmds.polyCube(name="base_head")[0]
        target = cmds.polyCube(name="target_smile")[0]
        cmds.move(0, 1, 0, f"{target}.vtx[0]") # deform vertex

        # Create blendshape
        bs_node = cmds.blendShape(target, base, name="head_blendShape")[0]

        stats = get_mesh_statistics(base)
        self.assertTrue(stats["has_blendshapes"])
        self.assertIn(bs_node, stats["blendshape_nodes"])

    def test_04_surface_validation(self):
        """Verifies Hausdorff and mean distance measurement."""
        from meshforge_maya.core.validation import validate_mesh_surface
        from meshforge_maya.core.pipeline import duplicate_object_non_destructive
        from meshforge_maya.core.simplification import execute_simplification

        sphere = cmds.polySphere(name="val_sphere", subdivisionsX=16, subdivisionsY=16)[0]
        opt = duplicate_object_non_destructive(sphere)
        execute_simplification(opt, percentage=30.0)

        val = validate_mesh_surface(sphere, opt, sample_count=200)
        self.assertTrue(val["measured"])
        self.assertGreaterEqual(val["max_hausdorff_m"], 0.0)
        self.assertGreaterEqual(val["mean_deviation_m"], 0.0)

if __name__ == "__main__":
    unittest.main()
