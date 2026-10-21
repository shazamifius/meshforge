"""MeshForge Maya - Automated Installer Tests.
Tests install.mel and install_meshforge_shelf_button.
"""

import os
import unittest
import maya.cmds as cmds
import maya.mel as mel

class TestMeshForgeMayaInstall(unittest.TestCase):
    def test_installer_mel_source(self):
        """Verifies that sourcing install.mel executes smoothly without error."""
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        install_mel = os.path.join(repo_root, "install.mel").replace("\\", "/")
        self.assertTrue(os.path.exists(install_mel))

        # Sourcing install.mel
        mel.eval(f'source "{install_mel}";')

        # Verify module import and show function availability
        import meshforge_maya
        self.assertTrue(hasattr(meshforge_maya, "show"))
        self.assertEqual(meshforge_maya.__version__, "0.2.0")

if __name__ == "__main__":
    unittest.main()
