"""Tests de validation du système de mise à jour automatique MeshForge."""

import unittest
import os
import sys
import tempfile
import zipfile
import shutil
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import bpy
import meshforge
try:
    meshforge.register()
except Exception:
    pass

from meshforge.core.updater import (
    parse_version_tuple,
    is_newer_version,
    get_current_version_str,
    get_update_state,
    check_for_updates_sync,
    install_update_sync,
    _set_update_state,
    GITHUB_REPO,
)


class TestMeshForgeUpdater(unittest.TestCase):

    def test_01_version_parsing_and_comparison(self):
        """Vérifie la robustesse du comparateur de versions sémantiques."""
        self.assertEqual(parse_version_tuple("0.1.0"), (0, 1, 0))
        self.assertEqual(parse_version_tuple("v0.2.1"), (0, 2, 1))
        self.assertEqual(parse_version_tuple("V1.0"), (1, 0, 0))
        self.assertEqual(parse_version_tuple("2.1.3-beta"), (2, 1, 3))

        self.assertTrue(is_newer_version("0.2.0", "0.1.0"))
        self.assertTrue(is_newer_version("v1.0.0", "0.9.9"))
        self.assertTrue(is_newer_version("0.1.1", "0.1.0"))

        self.assertFalse(is_newer_version("0.1.0", "0.1.0"))
        self.assertFalse(is_newer_version("0.0.9", "0.1.0"))
        self.assertFalse(is_newer_version("v0.1.0", "0.1.0"))

    def test_02_operators_registered(self):
        """Vérifie que les opérateurs du système de mise à jour sont bien enregistrés dans Blender."""
        self.assertTrue(hasattr(bpy.ops.meshforge, "check_update"), "meshforge.check_update manquant")
        self.assertTrue(hasattr(bpy.ops.meshforge, "install_update"), "meshforge.install_update manquant")
        self.assertTrue(hasattr(bpy.ops.meshforge, "open_github"), "meshforge.open_github manquant")

    def test_03_preferences_and_state(self):
        """Vérifie l'état initial du module et la présence des préférences de mise à jour."""
        state = get_update_state()
        self.assertIn("status", state)
        self.assertIn("current_version", state)
        self.assertEqual(state["current_version"], get_current_version_str())

    def test_04_simulated_archive_extraction(self):
        """Vérifie que le déballage et la mise à jour sélective fonctionnent correctement."""
        # Créer un faux répertoire d'add-on
        test_addon_dir = tempfile.mkdtemp(prefix="test_addon_")
        test_update_dir = tempfile.mkdtemp(prefix="test_update_")
        zip_path = os.path.join(test_update_dir, "fake_release.zip")

        try:
            # 1. Écrire une fausse structure initiale
            os.makedirs(os.path.join(test_addon_dir, "core"), exist_ok=True)
            with open(os.path.join(test_addon_dir, "__init__.py"), "w", encoding="utf-8") as f:
                f.write('bl_info = {"version": (0, 1, 0)}\n')
            with open(os.path.join(test_addon_dir, "core", "test.py"), "w", encoding="utf-8") as f:
                f.write('# initial code\n')

            # 2. Préparer une fausse archive de mise à jour (structure avec sous-dossier type GitHub)
            nested_dir = os.path.join(test_update_dir, "meshforge-0.2.0")
            os.makedirs(os.path.join(nested_dir, "core"), exist_ok=True)
            with open(os.path.join(nested_dir, "__init__.py"), "w", encoding="utf-8") as f:
                f.write('bl_info = {"version": (0, 2, 0)}\n')
            with open(os.path.join(nested_dir, "core", "test.py"), "w", encoding="utf-8") as f:
                f.write('# updated code v0.2.0\n')

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(os.path.join(nested_dir, "__init__.py"), "meshforge-0.2.0/__init__.py")
                zf.write(os.path.join(nested_dir, "core", "test.py"), "meshforge-0.2.0/core/test.py")

            # 3. Tester l'extraction en pointant le get_addon_root vers test_addon_dir
            import meshforge.core.updater as upd
            orig_get_root = upd.get_addon_root
            upd.get_addon_root = lambda: test_addon_dir

            try:
                # Exécuter l'installation depuis le fichier local via file:// URL
                file_url = f"file:///{zip_path.replace(os.sep, '/')}"
                success, msg = install_update_sync(download_url=file_url)
                self.assertTrue(success, f"Échec installation : {msg}")

                # Vérifier que le fichier test.py a bien été mis à jour
                with open(os.path.join(test_addon_dir, "core", "test.py"), "r", encoding="utf-8") as f:
                    updated_content = f.read()
                self.assertIn("v0.2.0", updated_content)

            finally:
                upd.get_addon_root = orig_get_root

        finally:
            shutil.rmtree(test_addon_dir, ignore_errors=True)
            shutil.rmtree(test_update_dir, ignore_errors=True)

    def test_05_live_github_api_query(self):
        """Vérifie la communication réseau avec l'API publique GitHub du dépôt shazamifius/meshforge."""
        res = check_for_updates_sync(timeout=8.0)
        # La requête doit aboutir sans lever d'exception non gérée
        self.assertIn(res["status"], ("UP_TO_DATE", "UPDATE_AVAILABLE", "ERROR"))
        if res["status"] != "ERROR":
            self.assertEqual(res["current_version"], "0.1.0")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshForgeUpdater)
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
