"""MeshForge - Verification interactive en conditions réelles (GUI) pour la Phase UX7.
Vérifie graphiquement dans la véritable interface Blender :
1. UX7.1 : Cadrage (zoom) précis et distinct sur deux anomalies éloignées dans la vue 3D.
2. UX7.3 : Interrupteur de mode filaire (ON / OFF) avec mise à jour du texte et de l'icône du bouton.
3. UX7.4 : Affichage de la légende des couleurs sémantiques.
4. UX7.2 : Détection de géométrie modifiée et affichage de l'alerte "Diagnostic à actualiser".
5. UX7.2 : Effacement de l'inspection et retour à l'affichage normal.
"""

import sys
import time
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

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
cam_locations = {}

def log(msg):
    print(f"[UX7_GUI_TEST] {msg}", flush=True)
    audit_log.append(msg)

def sequence():
    global step
    step += 1

    if step == 1:
        log("Initialisation de la scène avec deux anomalies espacées...")
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for m in list(bpy.data.meshes):
            bpy.data.meshes.remove(m, do_unlink=True)

        mesh = bpy.data.meshes.new("UX7_Interactive_Mesh")
        obj = bpy.data.objects.new("UX7_Interactive_Object", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        obj.location = (1.0, 2.0, 0.0)

        bm = bmesh.new()
        # Anomalie 1 : N-gone à 5 côtés à (+8, +8, 0)
        v0 = bm.verts.new((7.0, 7.0, 0.0))
        v1 = bm.verts.new((9.0, 7.0, 0.0))
        v2 = bm.verts.new((9.5, 8.0, 0.0))
        v3 = bm.verts.new((9.0, 9.0, 0.0))
        v4 = bm.verts.new((7.0, 9.0, 0.0))
        bm.faces.new([v0, v1, v2, v3, v4])

        # Anomalie 2 : Face d'aire nulle à (-8, -8, 0)
        vd0 = bm.verts.new((-8.0, -8.0, 0.0))
        vd1 = bm.verts.new((-8.0, -8.0, 0.0))
        vd2 = bm.verts.new((-7.0, -8.0, 0.0))
        bm.faces.new([vd0, vd1, vd2])

        # Sommet orphelin
        bm.verts.new((0.0, 0.0, 4.0))

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        bpy.context.view_layer.update()

        # Déployer le panneau latéral N
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.show_region_ui = True

        # Analyser
        bpy.context.scene.meshforge_settings.asset_target_mode = 'GENERAL'
        bpy.ops.meshforge.analyze_topology()
        bpy.context.scene.meshforge_settings.show_color_legend = True
        diag = meshforge.operators.topology_inspect.get_active_diagnosis(obj.name) or {}
        for i, d in enumerate(diag.get("defects", [])):
            log(f"Defect {i}: id={d.get('id')}, name={d.get('name')}, type={d.get('type')}, indices={d.get('indices')}, center={d.get('center')}")
        log("Analyse topologique terminée.")
        return 1.0

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
                            except Exception:
                                pass
        return 0.8

    elif step == 3:
        # UX7.1 : Focus sur l'anomalie 1 (N-gone)
        log("Cadrage sur Anomalie 1 (N-gone)...")
        res_ngon = bpy.ops.meshforge.focus_defect(defect_index=0)
        log(f"Résultat focus N-gone: {res_ngon}")

        # Enregistrer la position de cadrage
        cursor_loc = bpy.context.scene.cursor.location.copy()
        cam_locations["ngon"] = cursor_loc
        log(f"Position focus N-gone : X={cursor_loc.x:.2f}, Y={cursor_loc.y:.2f}, Z={cursor_loc.z:.2f}")

        shot_ngon = out_dir / "gui_ux7_zoom_defect_1_ngon.png"
        bpy.ops.screen.screenshot(filepath=str(shot_ngon))
        log(f"Capture enregistrée : {shot_ngon.name}")
        return 1.0

    elif step == 4:
        # UX7.1 : Focus sur l'anomalie 2 (Face nulle)
        log("Cadrage sur Anomalie 2 (Face nulle)...")
        res_zero = bpy.ops.meshforge.focus_defect(defect_index=1)
        log(f"Résultat focus Face nulle: {res_zero}")

        cursor_loc = bpy.context.scene.cursor.location.copy()
        cam_locations["zero_face"] = cursor_loc
        log(f"Position focus Face nulle : X={cursor_loc.x:.2f}, Y={cursor_loc.y:.2f}, Z={cursor_loc.z:.2f}")

        # Vérification mathématique du déplacement effectif
        dist = (cam_locations["ngon"] - cam_locations["zero_face"]).length
        log(f"Distance entre les deux points focaux : {dist:.2f} m")
        assert dist > 15.0, f"Les deux cadrages doivent être nettement distincts (> 15m), obtenu {dist:.2f}m"

        shot_zero = out_dir / "gui_ux7_zoom_defect_2_zeroface.png"
        bpy.ops.screen.screenshot(filepath=str(shot_zero))
        log(f"Capture enregistrée : {shot_zero.name}")
        return 1.0

    elif step == 5:
        # UX7.3 : Activer le filaire
        log("Activation du mode filaire...")
        bpy.ops.meshforge.toggle_wireframe()
        obj = bpy.context.active_object
        assert obj.show_wire is True, "L'objet doit avoir show_wire=True"

        # Redessin
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        shot_wire_on = out_dir / "gui_ux7_wireframe_on.png"
        bpy.ops.screen.screenshot(filepath=str(shot_wire_on))
        log(f"Capture filaire activé : {shot_wire_on.name}")
        return 0.8

    elif step == 6:
        # UX7.3 : Désactiver le filaire
        log("Désactivation du mode filaire...")
        bpy.ops.meshforge.toggle_wireframe()
        obj = bpy.context.active_object
        assert obj.show_wire is False, "L'objet doit avoir show_wire=False"

        # Redessin
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        shot_wire_off = out_dir / "gui_ux7_wireframe_off.png"
        bpy.ops.screen.screenshot(filepath=str(shot_wire_off))
        log(f"Capture filaire désactivé : {shot_wire_off.name}")
        return 0.8

    elif step == 7:
        # UX7.2 : Modification de géométrie pour provoquer l'état périmé (stale)
        log("Modification de géométrie pour test de péremption...")
        obj = bpy.context.active_object
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.new((50.0, 50.0, 50.0)) # Ajout d'un sommet
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        # Forcer le redessin du panneau pour afficher l'alerte
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        shot_stale = out_dir / "gui_ux7_stale_notification.png"
        bpy.ops.screen.screenshot(filepath=str(shot_stale))
        log(f"Capture alerte péremption : {shot_stale.name}")
        return 0.8

    elif step == 8:
        # UX7.2 : Nettoyage et restauration
        log("Effacement de l'inspection et réinitialisation...")
        bpy.ops.meshforge.clear_defect_view()
        obj = bpy.context.active_object
        assert "_MF_Inspection_Temp" not in obj.data.color_attributes, "L'attribut temporaire doit être supprimé"
        assert obj.show_wire is False, "Le filaire doit être désactivé"

        log_file = out_dir / "ux7_gui_verification.txt"
        log_file.write_text("\n".join(audit_log), encoding="utf-8")
        log("Toutes les vérifications GUI UX7 ont réussi à 100%.")
        return 0.5

    elif step == 9:
        bpy.ops.wm.quit_blender()
        return None

bpy.app.timers.register(sequence, first_interval=0.5)
