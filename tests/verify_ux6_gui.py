"""MeshForge - Verification interactive en conditions réelles (GUI) des correctifs UX6 (BUG-01 et BUG-02).
Exécute :
1. Test en mode Objet (analyse, affichage des boutons).
2. Test en mode Édition (apparition du bandeau d'alerte français, désactivation des opérateurs).
3. Test d'exécution forcée en mode Édition (annulation propre, pas d'exception to_mesh()).
4. Test du cycle register / unregister en session interactive.
5. Capture des preuves visuelles réelles.
"""

import sys
import time
import ctypes
from pathlib import Path
import bpy
import bmesh

root_dir = Path(__file__).resolve().parent.parent
parent_dir = root_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import meshforge
if not hasattr(bpy.types.Scene, "meshforge_settings"):
    meshforge.register()

out_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\fa5a54fd-39fd-441a-9208-6087175eaefe")

step = 0
audit_log = []

def log(msg):
    print(f"[UX6_GUI_TEST] {msg}")
    audit_log.append(msg)

def sequence():
    global step
    step += 1

    if step == 1:
        log("Initialisation de la scène avec anomalies...")
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for m in list(bpy.data.meshes):
            bpy.data.meshes.remove(m, do_unlink=True)

        # Création d'un maillage avec n-gone, face nulle et sommet orphelin
        mesh = bpy.data.meshes.new("UX6_Test_Mesh")
        obj = bpy.data.objects.new("UX6_Test_Object", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        bm = bmesh.new()
        v0 = bm.verts.new((-1, -1, 0))
        v1 = bm.verts.new((1, -1, 0))
        v2 = bm.verts.new((1.5, 0, 0))
        v3 = bm.verts.new((1, 1, 0))
        v4 = bm.verts.new((-1, 1, 0))
        bm.faces.new([v0, v1, v2, v3, v4]) # N-gone à 5 côtés
        
        # Face nulle
        v_d0 = bm.verts.new((3, 0, 0))
        v_d1 = bm.verts.new((3, 0, 0))
        v_d2 = bm.verts.new((4, 0, 0))
        bm.faces.new([v_d0, v_d1, v_d2])
        
        # Sommet orphelin
        bm.verts.new((5, 5, 0))
        
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        # Déployer le volet N
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.show_region_ui = True

        # Analyser
        bpy.context.scene.meshforge_settings.asset_target_mode = 'GENERAL'
        bpy.ops.meshforge.analyze_topology()
        log("Analyse topologique terminée en mode Objet.")
        return 1.0  # Laisser le temps à Blender d'initialiser la région UI

    elif step == 2:
        # Activer l'onglet MeshForge dans la barre latérale N
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'UI':
                            try:
                                with bpy.context.temp_override(window=window, area=area, region=region):
                                    region.active_panel_category = 'MeshForge'
                                    region.tag_redraw()
                                    log("Onglet 'MeshForge' activé avec succès.")
                            except Exception as e:
                                log(f"Tentative active_panel_category: {e}")
        return 0.8

    elif step == 3:
        # Prendre capture en mode Objet
        shot_obj = out_dir / "gui_ux6_object_mode.png"
        bpy.ops.screen.screenshot(filepath=str(shot_obj))
        log(f"Capture mode Objet enregistrée : {shot_obj.name}")

        # Passer en mode Édition
        bpy.ops.object.mode_set(mode='EDIT')
        log(f"Passage en mode Édition. bpy.context.mode = {bpy.context.mode}")

        # Forcer le redessin de l'interface
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'UI':
                            region.tag_redraw()
        return 1.0

    elif step == 4:
        # Prendre capture en mode Édition
        shot_edit = out_dir / "gui_ux6_edit_mode.png"
        bpy.ops.screen.screenshot(filepath=str(shot_edit))
        log(f"Capture mode Édition enregistrée : {shot_edit.name}")

        # Vérifier le poll en mode Édition
        poll_clean = bpy.ops.meshforge.conservative_clean.poll()
        poll_ngon = bpy.ops.meshforge.cut_ngons.poll()
        poll_inspect = bpy.ops.meshforge.analyze_topology.poll()
        log(f"Poll en mode Édition: clean={poll_clean}, cut_ngons={poll_ngon}, inspect={poll_inspect}")
        assert not poll_clean, "Le poll de conservative_clean devrait être False en mode Édition"
        assert not poll_ngon, "Le poll de cut_ngons devrait être False en mode Édition"
        assert not poll_inspect, "Le poll de analyze_topology devrait être False en mode Édition"

        # Tenter d'exécuter via bpy.ops -> doit lever RuntimeError car poll() est False
        try:
            bpy.ops.meshforge.conservative_clean('EXEC_DEFAULT')
            executed = True
        except RuntimeError as e:
            executed = False
            log(f"Blender a bloque l'operateur via poll(): {e}")
        assert not executed, "L'operateur ne doit pas pouvoir s'executer via bpy.ops en mode Edition"

        # Tenter l'appel direct du noyau core -> verifie le rejet propre sans plantage to_mesh()
        from meshforge.core.conservative_cleaner import execute_conservative_cleanup
        core_res = execute_conservative_cleanup(bpy.context.active_object, bpy.context.scene.meshforge_settings)
        log(f"Rejet defensif du noyau core en mode Edition: success={core_res['success']} - error={core_res['error']}")
        assert core_res['success'] is False, f"Attendu success=False, obtenu {core_res['success']}"
        assert "mode Édition" in core_res['error'], "Le message d'erreur doit mentionner le mode Édition"

        # Revenir en mode Objet
        bpy.ops.object.mode_set(mode='OBJECT')
        log("Retour en mode Objet.")
        assert bpy.ops.meshforge.conservative_clean.poll() is True, "Le poll devrait être True en mode Objet"

        # Tester le cycle complet register/unregister en session interactive
        log("Test du cycle unregister() / register()...")
        meshforge.unregister()
        assert not hasattr(bpy.types.Scene, "meshforge_settings"), "meshforge_settings doit être nettoyé"
        meshforge.register()
        assert hasattr(bpy.types.Scene, "meshforge_settings"), "meshforge_settings doit être réenregistré"
        log("Cycle unregister() / register() réussi avec succès en session interactive.")

        # Écrire le journal de test
        log_file = out_dir / "ux6_gui_verification.txt"
        log_file.write_text("\n".join(audit_log), encoding="utf-8")
        log("Toutes les vérifications GUI UX6 ont réussi à 100%.")

        return 0.5

    elif step == 5:
        bpy.ops.wm.quit_blender()
        return None

bpy.app.timers.register(sequence, first_interval=0.5)
