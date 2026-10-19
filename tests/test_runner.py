"""MeshForge - Script d'exécution globale de la suite de tests (Phases A, B & C)."""

import sys
import unittest
from pathlib import Path

# Ajouter la racine et le parent du projet
root_dir = Path(__file__).resolve().parent.parent
parent_dir = root_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from tests.test_phase_a import TestMeshForgePhaseA
from tests.test_phase_b import TestMeshForgePhaseB
from tests.test_phase_c import TestMeshForgePhaseC

if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseA))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseB))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseC))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
