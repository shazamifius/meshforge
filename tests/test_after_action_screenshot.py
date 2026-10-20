import time
from pathlib import Path
import bpy
import meshforge

meshforge.register()

step = 0
def sequence():
    global step
    step += 1
    
    if step == 1:
        if not bpy.context.active_object and bpy.data.objects:
            bpy.context.view_layer.objects.active = bpy.data.objects[0]
            bpy.data.objects[0].select_set(True)

        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.show_region_ui = True

        # Analyser
        bpy.context.scene.meshforge_settings.asset_target_mode = 'GAME_ASSET'
        bpy.ops.meshforge.analyze_topology()
        return 0.6

    elif step == 2:
        # Basculer vers l'onglet MeshForge
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'UI':
                            with bpy.context.temp_override(window=window, area=area, region=region):
                                region.active_panel_category = 'MeshForge'
                                region.tag_redraw()

        # Exécuter l'action de nettoyage conservateur
        bpy.ops.meshforge.conservative_clean()
        
        # Réanalyser pour mettre à jour les résultats et le tableau de bord
        bpy.ops.meshforge.analyze_topology()
        return 0.8

    elif step == 3:
        out_path = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\fa5a54fd-39fd-441a-9208-6087175eaefe\gui_meshforge_after_action.png")
        bpy.ops.screen.screenshot(filepath=str(out_path))
        print(f"Screenshot post-action enregistré: {out_path}")
        return 0.5

    elif step == 4:
        bpy.ops.wm.quit_blender()
        return None

if __name__ == "__main__":
    bpy.app.timers.register(sequence, first_interval=0.8)
