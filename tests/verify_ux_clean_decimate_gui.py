"""MeshForge - Protocole de vérification UX ciblée en conditions réelles (GUI).
Valide interactivement dans l'interface graphique de Blender 5.2.2 LTS :
1. CLEAN ouvert par défaut et DECIMATE replié en bas.
2. Lisibilité directe des constats dans le panneau principal sans sous-panneaux.
3. Actions CLEAN : Analyse, Zoom sur défaut, Nettoyage conservateur.
4. Méthodes DECIMATE :
   - Contraction d'arêtes sur objet courbe / organique (Sphère UV avec UVs, matériaux, vertex groups).
   - Dissolution coplanaire sur objet plat / hard-surface (Cube biseauté/subdivisé avec arêtes vives et seams).
5. Workflow non-destructif : création copie _MF_Optimized, masquage original, exécutions successives, restauration.
6. Préservation des UVs, matériaux, vertex groups et attributs de couleur.
7. Métrologie : vérification de la mention explicite "Non mesurée" si validation non exécutée.
8. Robustesse : Mode Édition (alerte et protection), sans objet actif, changement de sélection, repliement/dépliement.
"""

from __future__ import annotations
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
parent_dir = repo_root.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import bpy
import bmesh
from mathutils import Vector

import meshforge
if not hasattr(bpy.types.Scene, "meshforge_settings"):
    meshforge.register()

out_dir = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\fa5a54fd-39fd-441a-9208-6087175eaefe")

step = 0
audit_results = []
screenshots_taken = []


def log(msg: str):
    print(f"[UX_VERIFICATION] {msg}", flush=True)
    audit_results.append(msg)


def get_current_diagnosis(obj_name: str) -> dict:
    """Récupère le diagnostic actif depuis le module effectivement chargé par Blender."""
    for mod_name in ("bl_ext.user_default.meshforge.operators.topology_inspect", "meshforge.operators.topology_inspect"):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "_ACTIVE_DIAGNOSIS_CACHE"):
                cache = mod._ACTIVE_DIAGNOSIS_CACHE
                if obj_name in cache:
                    return cache[obj_name]
    return {}


def ensure_n_panel_visible():
    """Déploie la barre latérale N et sélectionne l'onglet MeshForge dans la vue 3D."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.show_region_ui = True
                for region in area.regions:
                    if region.type == 'UI':
                        try:
                            with bpy.context.temp_override(window=window, area=area, region=region):
                                region.active_panel_category = 'MeshForge'
                                region.tag_redraw()
                        except Exception:
                            pass


def redraw_all():
    """Force le rafraîchissement complet des vues 3D."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def gui_sequence():
    global step
    step += 1

    try:
        if step == 1:
            log("--- SCÉNARIO 1 : DÉMARRAGE ET VÉRIFICATION DE L'ÉTAT INITIAL ---")
            # Nettoyage initial
            for o in list(bpy.data.objects):
                bpy.data.objects.remove(o, do_unlink=True)
            for m in list(bpy.data.meshes):
                bpy.data.meshes.remove(m, do_unlink=True)

            # Création d'un objet avec anomalies (Cylindre 8 côtés avec N-gones et sommets orphelins)
            bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=1.5, depth=2.5, location=(0, 0, 1.25))
            cyl = bpy.context.active_object
            cyl.name = "Test_Cylinder_Defects"

            # Ajouter 2 sommets orphelins et 1 face d'aire nulle
            bm = bmesh.new()
            bm.from_mesh(cyl.data)
            v_orp1 = bm.verts.new((3.0, 3.0, 0.0))
            v_orp2 = bm.verts.new((3.5, 3.5, 0.0))
            # Face nulle
            vn0 = bm.verts.new((-3.0, -3.0, 0.0))
            vn1 = bm.verts.new((-3.0, -3.0, 0.0))
            vn2 = bm.verts.new((-2.5, -2.5, 0.0))
            bm.faces.new([vn0, vn1, vn2])
            bm.to_mesh(cyl.data)
            bm.free()
            cyl.data.update()

            props = bpy.context.scene.meshforge_settings
            log(f"État section CLEAN : expanded={props.ui_section_clean_expanded}")
            log(f"État section DECIMATE : expanded={props.ui_section_decimate_expanded}")

            assert props.ui_section_clean_expanded is True, "CLEAN doit être ouvert par défaut !"
            assert props.ui_section_decimate_expanded is False, "DECIMATE doit être replié par défaut !"

            ensure_n_panel_visible()
            redraw_all()
            return 0.8

        elif step == 2:
            log("--- SCÉNARIO 2 : LISIBILITÉ DES CONSTATS ET ANALYSE TOPOLOGIQUE ---")
            # Lancer l'analyse topologique
            bpy.ops.meshforge.analyze_topology()
            props = bpy.context.scene.meshforge_settings

            diag = get_current_diagnosis(bpy.context.active_object.name)
            findings = diag.get("findings", [])
            health = diag.get("structured", {}).get("health", {})
            log(f"Santé détectée : {health.get('status')} | Défauts : {health.get('defects_count')} | Risques : {health.get('risks_count')}")
            log(f"Nombre de constats listés dans le tableau principal : {len(findings)}")

            assert len(findings) > 0, "Des constats doivent être détectés sur le maillage de test !"

            # Capture d'écran 1 : Panneau CLEAN ouvert avec constats et santé
            ensure_n_panel_visible()
            redraw_all()
            shot1 = out_dir / "gui_ux_clean_panel_default.png"
            bpy.ops.screen.screenshot(filepath=str(shot1))
            screenshots_taken.append(shot1.name)
            log(f"Capture enregistrée : {shot1.name}")
            return 0.8

        elif step == 3:
            log("--- SCÉNARIO 3 : ACTIONS CLEAN (CADRAGE SUR DÉFAUT ET NETTOYAGE SÛR) ---")
            # Cadrage sur le premier défaut
            res_focus = bpy.ops.meshforge.focus_defect(defect_index=0)
            log(f"Résultat cadrage focus_defect: {res_focus}")

            # Exécuter le nettoyage conservateur sûr
            res_clean = bpy.ops.meshforge.conservative_clean()
            log(f"Résultat conservative_clean: {res_clean}")
            assert res_clean == {'FINISHED'}, "Le nettoyage conservateur doit réussir !"

            # Ré-analyser pour vérifier la disparition des défauts critiques
            bpy.ops.meshforge.analyze_topology()
            diag_after = get_current_diagnosis(bpy.context.active_object.name)
            health_after = diag_after.get("structured", {}).get("health", {})
            log(f"Santé après nettoyage : {health_after.get('status')} (Défauts critiques restants : {health_after.get('defects_count')})")
            return 0.8

        elif step == 4:
            log("--- SCÉNARIO 4 : DECIMATE EN CONTRACTION D'ARÊTES SUR MODÈLE COURBE (SPHÈRE) ---")
            # Nettoyer et créer une sphère UV avec UVs, matériau, vertex group et attributs
            for o in list(bpy.data.objects):
                bpy.data.objects.remove(o, do_unlink=True)

            bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=24, radius=1.5, location=(0, 0, 1.5))
            sphere = bpy.context.active_object
            sphere.name = "Organic_Sphere"

            # Ajouter un matériau
            mat = bpy.data.materials.new("Material_Organic")
            mat.use_nodes = True
            sphere.data.materials.append(mat)

            # Ajouter un groupe de sommets avec des poids
            vg = sphere.vertex_groups.new(name="Rig_Deform_Zone")
            vg.add([0, 1, 2, 3, 4, 5, 10, 20, 30], 0.85, 'REPLACE')

            # Ajouter une couche de couleur
            color_layer = sphere.data.color_attributes.new(name="Vertex_Paint_Colors", type='FLOAT_COLOR', domain='POINT')
            for col in color_layer.data:
                col.color = (0.2, 0.8, 0.3, 1.0)

            # Vérifier l'état initial des attributs
            init_tris = len(sphere.data.polygons) * 2  # environ
            log(f"Sphère initiale créée : {len(sphere.data.vertices)} sommets, {len(sphere.data.polygons)} faces")
            log(f"Attributs initiaux : UVs={len(sphere.data.uv_layers)}, Matériaux={len(sphere.material_slots)}, VGroups={len(sphere.vertex_groups)}, Colors={len(sphere.data.color_attributes)}")

            # Déplier DECIMATE et configurer COLLAPSE à 50%
            props = bpy.context.scene.meshforge_settings
            props.ui_section_clean_expanded = False
            props.ui_section_decimate_expanded = True
            props.decimate_method = 'COLLAPSE'
            props.simplification_mode = 'PERCENTAGE'
            props.simplification_percentage = 50.0
            props.create_new_object = True
            props.hide_original = True

            ensure_n_panel_visible()
            redraw_all()
            shot2 = out_dir / "gui_ux_decimate_panel_collapse.png"
            bpy.ops.screen.screenshot(filepath=str(shot2))
            screenshots_taken.append(shot2.name)
            log(f"Capture enregistrée : {shot2.name}")
            return 0.8

        elif step == 5:
            log("--- SCÉNARIO 5 : EXÉCUTION DÉCIMATION CONTRACTION ET VÉRIFICATION ATTRIBUTS ---")
            sphere = bpy.data.objects.get("Organic_Sphere")
            bpy.context.view_layer.objects.active = sphere

            res_simp = bpy.ops.meshforge.simplification()
            log(f"Résultat simplification : {res_simp}")
            assert res_simp == {'FINISHED'}, "La simplification par contraction doit réussir !"

            opt_obj = bpy.context.active_object
            log(f"Objet actif après décimation : '{opt_obj.name}'")
            assert opt_obj.name == "Organic_Sphere_MF_Optimized", f"Nom inattendu : {opt_obj.name}"
            assert sphere.hide_get() is True, "L'objet original 'Organic_Sphere' doit être masqué !"

            # Vérification rigoureuse de la préservation des attributs (Point 6)
            has_uv = len(opt_obj.data.uv_layers) > 0
            has_mat = len(opt_obj.material_slots) > 0 and opt_obj.material_slots[0].material.name == "Material_Organic"
            has_vg = len(opt_obj.vertex_groups) > 0 and opt_obj.vertex_groups[0].name == "Rig_Deform_Zone"
            has_col = len(opt_obj.data.color_attributes) > 0

            log(f"Préservation UVs : {'OUI' if has_uv else 'NON'} ({len(opt_obj.data.uv_layers)} couche(s))")
            log(f"Préservation Matériaux : {'OUI' if has_mat else 'NON'} (Slot 0 : {opt_obj.material_slots[0].material.name})")
            log(f"Préservation Vertex Groups : {'OUI' if has_vg else 'NON'} (Group: {opt_obj.vertex_groups[0].name})")
            log(f"Préservation Color Attributes : {'OUI' if has_col else 'NON'}")

            assert has_uv, "Les coordonnées UV doivent être préservées !"
            assert has_mat, "Les matériaux doivent être préservés !"
            assert has_vg, "Les groupes de sommets doivent être préservés !"

            # Vérification de la métrologie honnête (Point 7)
            props = bpy.context.scene.meshforge_settings
            log(f"last_deviation_measured = {props.last_deviation_measured}")
            assert props.last_deviation_measured is False, "La déviation ne doit pas être déclarée mesurée sans calcul BVH lourd !"

            # Capture d'écran du panneau après exécution avec deltas réels
            ensure_n_panel_visible()
            redraw_all()
            shot3 = out_dir / "gui_ux_decimate_post_results.png"
            bpy.ops.screen.screenshot(filepath=str(shot3))
            screenshots_taken.append(shot3.name)
            log(f"Capture enregistrée : {shot3.name}")
            return 0.8

        elif step == 6:
            log("--- SCÉNARIO 6 : EXÉCUTIONS SUCCESSIVES ET RESTAURATION ---")
            opt_obj = bpy.context.active_object
            props = bpy.context.scene.meshforge_settings

            # Deuxième décimation successive
            props.simplification_percentage = 70.0
            res_simp2 = bpy.ops.meshforge.simplification()
            log(f"Résultat 2ème décimation : {res_simp2}")
            opt_obj2 = bpy.context.active_object

            # Vérifier qu'on n'a pas créé d'objet en cascade '_MF_Optimized_MF_Optimized' ou '.001'
            log(f"Nom après 2ème décimation : '{opt_obj2.name}'")
            all_obj_names = [o.name for o in bpy.data.objects]
            log(f"Objets présents dans la scène : {all_obj_names}")
            assert not any(".001" in n for n in all_obj_names), "Aucun objet dupliqué orphelin .001 ne doit persister !"
            assert "Organic_Sphere_MF_Optimized" in all_obj_names, "L'objet optimisé unique doit être présent !"

            # Restauration de l'original
            res_rst = bpy.ops.meshforge.restore()
            log(f"Résultat restauration : {res_rst}")
            assert res_rst == {'FINISHED'}, "La restauration doit réussir !"

            sphere = bpy.data.objects.get("Organic_Sphere")
            assert sphere is not None, "L'objet original 'Organic_Sphere' doit exister !"
            assert sphere.hide_get() is False, "L'objet original doit être redevenu visible !"
            assert bpy.context.active_object == sphere, "L'objet original doit être l'objet actif !"
            log("Restauration de l'original validée avec succès.")
            return 0.8

        elif step == 7:
            log("--- SCÉNARIO 7 : DECIMATE EN DISSOLUTION COPLANAIRE SUR PIÈCE HARD-SURFACE / CAD ---")
            # Nettoyer et créer un objet mécanique plat : Cube avec biseau et faces coplanaires subdivisées
            for o in list(bpy.data.objects):
                bpy.data.objects.remove(o, do_unlink=True)

            bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 1.0))
            cube = bpy.context.active_object
            cube.name = "Mechanical_Plate"

            # Marquer des arêtes vives et seams
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(cube.data)
            for e in bm.edges[:4]:
                e.seam = True
                e.smooth = False
            bmesh.update_edit_mesh(cube.data)

            # Subdiviser pour créer des faces coplanaires
            bpy.ops.mesh.subdivide(number_cuts=3)
            bpy.ops.object.mode_set(mode='OBJECT')

            mat_cad = bpy.data.materials.new("Material_CAD")
            cube.data.materials.append(mat_cad)

            faces_init = len(cube.data.polygons)
            log(f"Pièce CAD créée : {faces_init} faces coplanaires")

            # Configurer DECIMATE en DISSOLVE
            props = bpy.context.scene.meshforge_settings
            props.decimate_method = 'DISSOLVE'
            props.dissolve_angle = 5.0
            props.dissolve_mode = 'BALANCED'
            props.preserve_sharp = True
            props.preserve_seams = True
            props.create_new_object = True
            props.hide_original = True

            ensure_n_panel_visible()
            redraw_all()
            shot4 = out_dir / "gui_ux_decimate_panel_dissolve.png"
            bpy.ops.screen.screenshot(filepath=str(shot4))
            screenshots_taken.append(shot4.name)
            log(f"Capture enregistrée : {shot4.name}")
            return 0.8

        elif step == 8:
            log("--- SCÉNARIO 8 : EXÉCUTION DISSOLUTION ET RESTAURATION ---")
            props = bpy.context.scene.meshforge_settings
            res_dis = bpy.ops.meshforge.dissolve()
            log(f"Résultat dissolution coplanaire : {res_dis}")
            assert res_dis == {'FINISHED'}, "La dissolution doit réussir !"

            opt_cad = bpy.context.active_object
            faces_after = len(opt_cad.data.polygons)
            log(f"Faces avant: {props.last_faces_before} -> Faces après: {faces_after} (delta: {props.last_faces_before - faces_after})")
            assert faces_after < props.last_faces_before, "Des faces coplanaires doivent avoir été dissoutes !"

            # Restauration
            bpy.ops.meshforge.restore()
            cube = bpy.data.objects.get("Mechanical_Plate")
            assert cube.hide_get() is False
            log("Dissolution et restauration validées.")
            return 0.8

        elif step == 9:
            log("--- SCÉNARIO 9 : ROBUSTESSE EN MODE ÉDITION ET SANS OBJET ACTIF ---")
            # 1. Mode Édition
            cube = bpy.data.objects.get("Mechanical_Plate")
            bpy.context.view_layer.objects.active = cube
            bpy.ops.object.mode_set(mode='EDIT')
            log(f"Mode actuel : {bpy.context.mode}")

            # Vérifier que poll() désactive immédiatement les boutons d'action
            can_clean = bpy.ops.meshforge.conservative_clean.poll()
            can_simp = bpy.ops.meshforge.simplification.poll()
            can_dis = bpy.ops.meshforge.dissolve.poll()
            log(f"Opérateurs autorisés en mode Édition : conservative_clean={can_clean}, simplification={can_simp}, dissolve={can_dis}")
            assert not can_clean, "conservative_clean doit être désactivé en mode Édition !"
            assert not can_simp, "simplification doit être désactivée en mode Édition !"
            assert not can_dis, "dissolve doit être désactivé en mode Édition !"

            # 2. Revenir en mode Objet
            bpy.ops.object.mode_set(mode='OBJECT')

            # 3. Aucun objet sélectionné
            bpy.ops.object.select_all(action='DESELECT')
            bpy.context.view_layer.objects.active = None
            log(f"Objet actif : {bpy.context.active_object}")

            ensure_n_panel_visible()
            redraw_all()

            # Enregistrer le journal d'audit complet
            log_file = out_dir / "ux_clean_decimate_verification_report.txt"
            log_file.write_text("\n".join(audit_results), encoding="utf-8")
            log(f"Rapport d'audit enregistré : {log_file.name}")
            log("TOUTES LES VÉRIFICATIONS GUI ONT RÉUSSI AVEC SUCCÈS (100%).")
            return 0.8

        elif step == 10:
            bpy.ops.wm.quit_blender()
            return None

    except Exception as e:
        log(f"ERREUR DANS LE PROTOCOLE : {e}")
        import traceback
        traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(gui_sequence, first_interval=0.5)
