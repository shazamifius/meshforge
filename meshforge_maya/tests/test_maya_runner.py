"""MeshForge Maya - Automated Test Runner.
Executes the Maya unit test suite headlessly via mayapy.
"""

import sys
import os
import unittest

def run_tests():
    # Ensure current repo root is in python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    maya_root = os.path.dirname(current_dir)
    parent_root = os.path.dirname(maya_root)

    for p in [parent_root, maya_root]:
        if p not in sys.path:
            sys.path.insert(0, p)

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from meshforge_maya.ui.qt_compat import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["-platform", "offscreen"])

    # Initialize Maya standalone
    import maya.standalone
    try:
        maya.standalone.initialize()
        print("Maya standalone environment initialized successfully.")
    except RuntimeError:
        pass

    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.discover(current_dir, pattern="test_maya_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == "__main__":
    run_tests()
