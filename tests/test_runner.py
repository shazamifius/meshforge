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
from tests.test_phase_c2_quality import TestMeshForgePhaseC2Quality
from tests.test_phase_d1_diagnosis import TestMeshForgePhaseD1Diagnosis
from tests.test_interactive_gui import TestMeshForgePhaseD1Interactive
from tests.test_phase_d2_conservative import TestMeshForgePhaseD2Conservative
from tests.test_phase_d2_ngon_cut import TestMeshForgePhaseD2_2
from tests.test_real_world_ux import TestRealWorldUX
from tests.test_ux6_fixes import TestUX6Fixes

if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseA))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseB))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseC))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseC2Quality))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD1Diagnosis))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD1Interactive))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD2Conservative))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseD2_2))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRealWorldUX))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestUX6Fixes))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
