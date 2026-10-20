"""MeshForge - Script de génération de preuve visuelle (Rendu Viewport).
Configure une scène avec la mascotte Suzanne et un maillage à anomalies,
applique l'inspection sémantique par couleur, et génère des rendus de vérification.
"""

import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
parent_dir = root_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import bpy
import bmesh
import meshforge
from meshforge.core.topology_diagnosis import diagnose_topology
from meshforge.core.visualizer import apply_color_inspection

def run_visual_verification():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    meshforge.register()

    # 1. Création de Suzanne avec Smooth Shading
    bpy.ops.mesh.primitive_monkey_add(size=2.0, location=(0, 0, 0))
    suzanne = bpy.context.active_object
    suzanne.name = "Suzanne_MeshForge"

    # Ajouter quelques N-gones et triangles caractéristiques
    bm = bmesh.new()
    bm.from_mesh(suzanne.data)
    # Dissoudre une arête pour créer un N-gone
    bm.edges.ensure_lookup_table()
    if len(bm.edges) > 10:
        bmesh.ops.dissolve_edges(bm, edges=[bm.edges[10]], use_verts=False)
    bm.to_mesh(suzanne.data)
    bm.free()

    # 2. Exécution du diagnostic avec le profil GAME_ASSET
    bpy.context.scene.meshforge_settings.asset_target_mode = 'GAME_ASSET'
    diag = diagnose_topology(suzanne, mode='GAME_ASSET')

    # 3. Application de l'inspection visuelle (couleurs sémantiques)
    apply_color_inspection(suzanne, diag.get("defects", []))

    # 4. Configuration d'une caméra et éclairage
    bpy.ops.object.camera_add(location=(3.5, -4.0, 2.5), rotation=(1.1, 0.0, 0.78))
    cam = bpy.context.active_object
    bpy.context.scene.camera = cam

    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
    sun = bpy.context.active_object
    sun.data.energy = 3.0

    # 5. Configuration du rendu Workbench avec Vertex Colors
    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    bpy.context.scene.display.shading.light = 'STUDIO'
    bpy.context.scene.display.shading.color_type = 'VERTEX'
    bpy.context.scene.render.resolution_x = 1280
    bpy.context.scene.render.resolution_y = 720

    out_path = Path(r"C:\Users\Administrator\.gemini\antigravity\brain\fa5a54fd-39fd-441a-9208-6087175eaefe\meshforge_ui_viewport_verification.png")
    bpy.context.scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)
    print(f"VERIFICATION_RENDER_OK: {out_path}")

if __name__ == "__main__":
    run_visual_verification()
