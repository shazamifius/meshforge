"""MeshForge - Capture de la véritable interface Blender avec l'onglet MeshForge actif.
"""

import sys
import time
import ctypes
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
parent_dir = root_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import bpy
import meshforge

screenshot_dir = root_dir / "docs" / "images"
screenshot_dir.mkdir(parents=True, exist_ok=True)
shot_path = screenshot_dir / "gui_meshforge_active_panel.png"

step = 0

def capture_sequence():
    global step
    step += 1
    
    if step == 1:
        # Enregistrer et s'assurer que l'objet est sélectionné
        meshforge.register()
        if not bpy.context.active_object and bpy.data.objects:
            bpy.context.view_layer.objects.active = bpy.data.objects[0]
            bpy.data.objects[0].select_set(True)
            
        # Déployer le panneau latéral N dans la vue 3D
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.show_region_ui = True
                            
        # Lancer le diagnostic topologique
        try:
            bpy.ops.meshforge.analyze_topology()
        except Exception as e:
            print("Erreur diagnostic:", e)
            
        return 0.5

    elif step == 2:
        # Cliquer sur l'onglet 'MeshForge' dans la barre latérale N (x=2090, y=960)
        try:
            ctypes.windll.user32.SetCursorPos(2090, 960)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0) # LEFTDOWN
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0) # LEFTUP
            print("Clic sur l'onglet MeshForge effectué.")
        except Exception as e:
            print("Erreur clic souris:", e)
        return 0.8

    elif step == 3:
        # Prendre la capture de la véritable interface Blender avec le panneau MeshForge ouvert
        try:
            bpy.ops.screen.screenshot(filepath=str(shot_path))
            print(f"SCREENSHOT_SUCCESS: {shot_path}")
        except Exception as e:
            print("Erreur capture screenshot:", e)
        return 0.5

    elif step == 4:
        bpy.ops.wm.quit_blender()
        return None

if __name__ == "__main__":
    bpy.app.timers.register(capture_sequence, first_interval=0.5)
