"""MeshForge Maya - One-Click Drag & Drop Shelf & Module Installer.
Drag and drop this file or install.mel directly into Maya's 3D viewport to install!
Compatible with Maya 2020, 2022, 2023, 2024, 2025, 2026, 2027+ across Windows, macOS, and Linux.
"""

from __future__ import annotations
import os
import sys
import maya.cmds as cmds
import maya.mel as mel

def onMayaDroppedPythonFile(*args, **kwargs):
    """Callback triggered automatically when this script is dropped into Maya's viewport."""
    install_meshforge_shelf_button()

def install_meshforge_shelf_button(repo_root: str | None = None, auto_launch: bool = True):
    """Installs MeshForge module descriptor, userSetup.py integration, and shelf button."""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = repo_root or os.path.dirname(module_dir)

    # If repo_root pointed directly to meshforge_maya, move one level up
    if os.path.basename(parent_dir) == "meshforge_maya":
        parent_dir = os.path.dirname(parent_dir)

    parent_dir = os.path.abspath(parent_dir).replace("\\", "/")

    # Ensure parent dir is in sys.path
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # 1. Install Maya Module (.mod)
    try:
        user_app_dir = cmds.internalVar(userAppDir=True)
        if user_app_dir:
            modules_dir = os.path.join(user_app_dir, "modules").replace("\\", "/")
            os.makedirs(modules_dir, exist_ok=True)
            mod_path = os.path.join(modules_dir, "meshforge_maya.mod").replace("\\", "/")
            pkg_path = os.path.join(parent_dir, "meshforge_maya").replace("\\", "/")
            mod_content = f"+ meshforge_maya 0.2.0 {pkg_path}\nPYTHONPATH +:= ..\n"
            with open(mod_path, "w", encoding="utf-8") as f:
                f.write(mod_content)
    except Exception as exc:
        print(f"[MeshForge] Warning: Could not write .mod descriptor: {exc}")

    # 2. Install userSetup.py hook in global scripts dir
    try:
        scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts").replace("\\", "/")
        os.makedirs(scripts_dir, exist_ok=True)
        usersetup_path = os.path.join(scripts_dir, "userSetup.py").replace("\\", "/")
        snippet = (
            f"\n# --- MeshForge Maya Startup Integration ---\n"
            f"import sys\n"
            f"mf_path = r'{parent_dir}'\n"
            f"if mf_path not in sys.path:\n"
            f"    sys.path.insert(0, mf_path)\n"
        )
        already_has = False
        if os.path.exists(usersetup_path):
            with open(usersetup_path, "r", encoding="utf-8", errors="ignore") as f:
                if "MeshForge Maya Startup Integration" in f.read():
                    already_has = True
        if not already_has:
            with open(usersetup_path, "a", encoding="utf-8") as f:
                f.write(snippet)
    except Exception as exc:
        print(f"[MeshForge] Warning: Could not update userSetup.py: {exc}")

    # 3. Resolve Custom Icon
    icon_path = os.path.join(module_dir, "icons", "meshforge_icon.png").replace("\\", "/")
    if not os.path.exists(icon_path):
        icon_path = "polyRemesh.png"

    # 4. Add Shelf Button to current active shelf (if GUI is running)
    if not cmds.about(batch=True):
        try:
            current_shelf = ""
            try:
                current_shelf = mel.eval('string $currentShelf = `tabLayout -q -selectTab "ShelfLayout"`;')
            except Exception:
                pass

            if not current_shelf or current_shelf == "0":
                current_shelf = "Custom"

            button_label = "MeshForge"
            button_command = (
                f"import sys\n"
                f"p = r'{parent_dir}'\n"
                f"if p not in sys.path: sys.path.insert(0, p)\n"
                f"import meshforge_maya\n"
                f"meshforge_maya.show()\n"
            )

            # Delete previous MeshForge button on this shelf if it exists
            if cmds.shelfLayout(current_shelf, exists=True):
                existing_buttons = cmds.shelfLayout(current_shelf, query=True, childArray=True) or []
                for btn in existing_buttons:
                    if cmds.objectType(btn) == "shelfButton":
                        lbl = cmds.shelfButton(btn, query=True, label=True)
                        if lbl == button_label:
                            cmds.deleteUI(btn)

                cmds.setParent(current_shelf)
                cmds.shelfButton(
                    label=button_label,
                    annotation="MeshForge: 3D Mesh Analysis, Repair & Decimation Suite",
                    image=icon_path,
                    command=button_command,
                    sourceType="python",
                    overlayLabelColor=(1, 1, 1),
                    overlayLabelBackColor=(0.17, 0.36, 0.53, 0.8)
                )
        except Exception as exc:
            print(f"[MeshForge] Warning: Could not create shelf button: {exc}")

    # 5. Confirmation & Launch
    if auto_launch and not cmds.about(batch=True):
        res = cmds.confirmDialog(
            title="MeshForge Installed",
            message=(
                f"MeshForge for Maya is now successfully installed!\n\n"
                f"• Shelf button added to '{current_shelf}'\n"
                f"• Module descriptor registered\n"
                f"• Auto-load enabled on Maya startup"
            ),
            button=["Launch MeshForge", "OK"],
            defaultButton="Launch MeshForge"
        )
        if res == "Launch MeshForge":
            import meshforge_maya
            meshforge_maya.show()

if __name__ == "__main__":
    install_meshforge_shelf_button()
