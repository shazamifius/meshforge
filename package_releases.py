"""MeshForge - Release Packager.
Builds standalone, clean zip distribution archives for Blender and Maya.
"""

import os
import zipfile

def build_packages():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    releases_dir = os.path.join(repo_root, "releases")
    os.makedirs(releases_dir, exist_ok=True)

    # 1. Blender Package
    blender_zip_path = os.path.join(releases_dir, "meshforge_blender.zip")
    if os.path.exists(blender_zip_path):
        os.remove(blender_zip_path)

    with zipfile.ZipFile(blender_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Root metadata and source files for Blender
        for root_file in [
            "__init__.py",
            "preferences.py",
            "properties.py",
            "blender_manifest.toml",
            "MANUAL.md",
            "README.md",
            "CHANGELOG.md",
            "LICENSES.md"
        ]:
            src_path = os.path.join(repo_root, root_file)
            if os.path.exists(src_path):
                zf.write(src_path, arcname=f"meshforge/{root_file}")

        for folder in ["core", "operators", "ui"]:
            folder_path = os.path.join(repo_root, folder)
            for root, dirs, files in os.walk(folder_path):
                if "__pycache__" in root:
                    continue
                for f in files:
                    if f.endswith(".py"):
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, repo_root).replace("\\", "/")
                        zf.write(full_p, arcname=f"meshforge/{rel_p}")

    print(f"[OK] Blender Zip: {blender_zip_path} ({os.path.getsize(blender_zip_path):,} bytes)")

    # 2. Maya Package
    maya_zip_path = os.path.join(releases_dir, "meshforge_maya.zip")
    if os.path.exists(maya_zip_path):
        os.remove(maya_zip_path)

    with zipfile.ZipFile(maya_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(repo_root, "install.mel"), arcname="install.mel")
        zf.write(os.path.join(repo_root, "install_maya.bat"), arcname="install_maya.bat")
        zf.write(os.path.join(repo_root, "install_maya.sh"), arcname="install_maya.sh")
        zf.write(os.path.join(repo_root, "MANUAL.md"), arcname="MANUAL.md")

        pkg_dir = os.path.join(repo_root, "meshforge_maya")
        for root, dirs, files in os.walk(pkg_dir):
            if "__pycache__" in root:
                continue
            for f in files:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, repo_root).replace("\\", "/")
                zf.write(full_p, arcname=rel_p)

    print(f"[OK] Maya Zip: {maya_zip_path} ({os.path.getsize(maya_zip_path):,} bytes)")

if __name__ == "__main__":
    build_packages()
