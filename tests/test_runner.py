"""MeshForge - Script exécutable pour lancer les tests en ligne de commande via Blender."""

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

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgePhaseA)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
