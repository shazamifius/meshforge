"""MeshForge Maya - Automated Tests for Pipeline Orchestration and Restoration."""

import unittest
import maya.cmds as cmds
import maya.standalone

class TestMeshForgeMayaPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            maya.standalone.initialize()
        except RuntimeError:
            pass

    def setUp(self):
        cmds.file(new=True, force=True)

    def test_01_non_destructive_duplication(self):
        """Verifies duplicate creation with _MF_Optimized naming and original hiding."""
        from meshforge_maya.core.pipeline import duplicate_object_non_destructive, restore_original_object

        cube = cmds.polyCube(name="char_body")[0]
        self.assertTrue(cmds.getAttr(f"{cube}.visibility"))

        # Duplicate non-destructive
        opt = duplicate_object_non_destructive(cube)
        self.assertEqual(opt, "char_body_MF_Optimized")
        self.assertFalse(cmds.getAttr(f"{cube}.visibility"))
        self.assertTrue(cmds.objExists(opt))

        # Restore original
        restored = restore_original_object(opt)
        self.assertEqual(restored, cube)
        self.assertFalse(cmds.objExists(opt))
        self.assertTrue(cmds.getAttr(f"{cube}.visibility"))

    def test_02_full_pipeline_execution(self):
        """Verifies the complete sequential optimization pipeline."""
        from meshforge_maya.core.pipeline import run_meshforge_pipeline

        torus = cmds.polyTorus(name="hero_prop", subdivisionsAxis=20, subdivisionsHeight=20)[0]
        settings = {
            "create_new_object": True,
            "enable_repair": True,
            "enable_internal_walls": False,
            "enable_dissolve": False,
            "enable_simplification": True,
            "simplification_percentage": 40.0,
            "enable_topology": False,
            "enable_normals": True,
            "enable_object_data": True
        }

        report = run_meshforge_pipeline(torus, settings)
        self.assertTrue(report["success"])
        self.assertTrue(cmds.objExists("hero_prop_MF_Optimized"))
        self.assertGreater(report["reduction_percentage"], 0.0)

if __name__ == "__main__":
    unittest.main()
