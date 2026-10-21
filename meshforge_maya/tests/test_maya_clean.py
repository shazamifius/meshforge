"""MeshForge Maya - Automated Tests for Telemetry, Repair and Clean Operations."""

import unittest
import maya.cmds as cmds
import maya.standalone

class TestMeshForgeMayaClean(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            maya.standalone.initialize()
        except RuntimeError:
            pass # Already initialized

    def setUp(self):
        cmds.file(new=True, force=True)

    def test_01_telemetry_accuracy(self):
        """Verifies accurate vertex, edge, face and triangle counts on a standard cube and cylinder."""
        from meshforge_maya.core.mesh_stats import get_mesh_statistics

        cube = cmds.polyCube(name="test_cube", width=1, height=1, depth=1)[0]
        stats = get_mesh_statistics(cube)

        self.assertTrue(stats["valid"])
        self.assertEqual(stats["vertices"], 8)
        self.assertEqual(stats["edges"], 12)
        self.assertEqual(stats["faces"], 6)
        self.assertEqual(stats["triangles"], 12)
        self.assertEqual(stats["ngons_count"], 0)
        self.assertEqual(stats["quads_count"], 6)
        self.assertTrue(stats["is_watertight"])

    def test_02_ngon_detection_and_cut(self):
        """Verifies detection and cutting of N-gons into triangles."""
        from meshforge_maya.core.mesh_stats import get_mesh_statistics
        from meshforge_maya.core.ngon_cutter import execute_ngon_cut

        # Create a cylinder with an N-gon top cap (8 subdivisions on cap)
        cyl = cmds.polyCylinder(name="test_cyl", subdivisionsAxis=8, subdivisionsCaps=0)[0]
        stats_init = get_mesh_statistics(cyl)
        self.assertGreater(stats_init["ngons_count"], 0)

        # Cut N-gons
        res = execute_ngon_cut(cyl, cut_convex=True, cut_concave=True)
        self.assertTrue(res["success"])
        self.assertGreater(res["convex_cut"], 0)

        stats_after = get_mesh_statistics(cyl)
        self.assertEqual(stats_after["ngons_count"], 0)

    def test_03_conservative_cleanup(self):
        """Verifies safe cleanup of zero-area faces and duplicate vertices."""
        from meshforge_maya.core.mesh_stats import get_mesh_statistics
        from meshforge_maya.core.conservative_cleaner import execute_conservative_cleanup

        plane = cmds.polyPlane(name="test_plane", subdivisionsX=2, subdivisionsY=2)[0]
        # Merge vertices with tiny tolerance
        res = execute_conservative_cleanup(plane, merge_doubles=True, doubles_distance=0.0001)
        self.assertTrue(res["success"])

        stats = get_mesh_statistics(plane)
        self.assertTrue(stats["valid"])

    def test_04_quadrangulation(self):
        """Verifies converting triangulated planar faces into quads."""
        from meshforge_maya.core.mesh_stats import get_mesh_statistics
        from meshforge_maya.core.quadrangulator import execute_targeted_quadrangulation

        plane = cmds.polyPlane(name="test_plane_tri", subdivisionsX=2, subdivisionsY=2)[0]
        cmds.polyTriangulate(plane)
        stats_tri = get_mesh_statistics(plane)
        self.assertEqual(stats_tri["quads_count"], 0)
        self.assertGreater(stats_tri["tris_count"], 0)

        # Quadrangulate
        res = execute_targeted_quadrangulation(plane, max_angle_deg=15.0)
        self.assertTrue(res["success"])
        self.assertGreater(res["quads_created"], 0)

        stats_quad = get_mesh_statistics(plane)
        self.assertGreater(stats_quad["quads_count"], 0)

if __name__ == "__main__":
    unittest.main()
