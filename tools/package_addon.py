"""MeshForge - Script d'empaquetage et de synchronisation d'extension Blender.
Génère le zip prêt à installer sur le Bureau et synchronise le dossier d'extension actif.
Garantit qu'un seul exemplaire actif existe dans Blender (extensions/user_default).
"""

import os
import shutil
import zipfile
from pathlib import Path

SOURCE_DIR = Path(r"C:\Users\Administrator\Documents\meshforge")
DESKTOP_ZIP = Path(r"C:\Users\Administrator\Desktop\meshforge.zip")
INSTALLED_EXT_DIR = Path(r"C:\Users\Administrator\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\meshforge")
LEGACY_ADDON_DIR = Path(r"C:\Users\Administrator\AppData\Roaming\Blender Foundation\Blender\5.2\scripts\addons\meshforge")

EXCLUDE_DIRS = {".git", ".pytest_cache", "__pycache__", "tests", "docs", "tools"}
EXCLUDE_EXTS = {".pyc", ".pyo", ".blend1", ".blend2"}


def package():
    print(f"Empaquetage depuis {SOURCE_DIR} vers {DESKTOP_ZIP}...")

    if DESKTOP_ZIP.exists():
        DESKTOP_ZIP.unlink()

    with zipfile.ZipFile(DESKTOP_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

            rel_root = Path(root).relative_to(SOURCE_DIR)
            for file in files:
                if any(file.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                file_path = Path(root) / file
                arc_name = Path("meshforge") / rel_root / file
                zf.write(file_path, arc_name)

    print(f"Zip créé avec succès : {DESKTOP_ZIP} ({DESKTOP_ZIP.stat().st_size / 1024:.1f} KB)")

    # 1. Nettoyage du répertoire legacy (scripts/addons) pour éviter les collisions RNA et doublons
    if LEGACY_ADDON_DIR.exists():
        print(f"Suppression du dossier legacy {LEGACY_ADDON_DIR} pour garantir une installation unique...")
        shutil.rmtree(LEGACY_ADDON_DIR)

    # 2. Synchronisation vers l'extension active moderne (extensions/user_default)
    if INSTALLED_EXT_DIR.parent.exists():
        print(f"Synchronisation vers l'extension active : {INSTALLED_EXT_DIR}...")
        if INSTALLED_EXT_DIR.exists():
            shutil.rmtree(INSTALLED_EXT_DIR)
        INSTALLED_EXT_DIR.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(SOURCE_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            rel_root = Path(root).relative_to(SOURCE_DIR)
            dest_dir = INSTALLED_EXT_DIR / rel_root
            dest_dir.mkdir(parents=True, exist_ok=True)
            for file in files:
                if any(file.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue
                src_file = Path(root) / file
                dest_file = dest_dir / file
                shutil.copy2(src_file, dest_file)

        print("Synchronisation de l'extension terminée avec succès (exemplaire unique garanti).")


if __name__ == "__main__":
    package()
