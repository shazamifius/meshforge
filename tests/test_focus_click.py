import time
import ctypes
from pathlib import Path
import bpy
import meshforge

meshforge.register()

def find_blender_hwnd():
    user32 = ctypes.windll.user32
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    GetWindowText = user32.GetWindowTextW
    GetWindowTextLength = user32.GetWindowTextLengthW
    IsWindowVisible = user32.IsWindowVisible

    titles = []
    def foreach_window(hwnd, lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLength(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            GetWindowText(hwnd, buff, length + 1)
            if "Blender" in buff.value:
                titles.append((hwnd, buff.value))
        return True

    EnumWindows(EnumWindowsProc(foreach_window), 0)
    return titles[0][0] if titles else None

step = 0
def sequence():
    global step
    step += 1
    if step == 1:
        hwnd = find_blender_hwnd()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 3) # SW_MAXIMIZE
            ctypes.windll.user32.SetForegroundWindow(hwnd)

        if not bpy.context.active_object and bpy.data.objects:
            bpy.context.view_layer.objects.active = bpy.data.objects[0]
            bpy.data.objects[0].select_set(True)

        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.show_region_ui = True

        # Analyser pour que les résultats s'affichent
        try:
            bpy.context.scene.meshforge_settings.asset_target_mode = 'GAME_ASSET'
            bpy.ops.meshforge.analyze_topology()
        except:
            pass

        return 0.6

    elif step == 2:
        # Clic exact sur l'onglet MeshForge (x=2075, y=1105)
        print("Clic sur onglet MeshForge à (2075, 1105)...")
        ctypes.windll.user32.SetCursorPos(2075, 1105)
        time.sleep(0.08)
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
        time.sleep(0.08)
        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
        return 0.8

    elif step == 3:
        out_path = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\fa5a54fd-39fd-441a-9208-6087175eaefe\gui_meshforge_panel_opened.png")
        bpy.ops.screen.screenshot(filepath=str(out_path))
        print(f"Screenshot enregistré: {out_path}")
        return 0.5

    elif step == 4:
        bpy.ops.wm.quit_blender()
        return None

if __name__ == "__main__":
    bpy.app.timers.register(sequence, first_interval=0.6)
