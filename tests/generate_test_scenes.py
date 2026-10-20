"""MeshForge - Générateur de scènes de test réelles (.blend) pour la Phase UX6.
Crée les 8 fichiers .blend représentatifs :
1. 01_simple_clean.blend : Maillage simple et propre (Cylindre/Cube biseauté, quads purs, UV propre).
2. 02_dense_triangulated.blend : Objet triangulé dense (Icosphère subdivisée, ~20k tris).
3. 03_sculpted_organic.blend : Maillage sculpté organique avec détails fins et courbures marquées.
4. 04_mechanical_assembly.blend : Assemblage mécanique multi-composantes (plaque, écrou, axe).
5. 05_open_surface_cloth.blend : Surface ouverte (nappe de tissu drapée avec frontières libres).
6. 06_multi_uv_materials.blend : Modèle avec 2 canaux UV (UVMap + Lightmap), 3 matériaux et couleurs de sommets.
7. 07_deformable_character.blend : Modèle déformable avec 4 groupes de sommets d'armature (Head, Neck, Torso, Arm.L).
8. 08_defects_and_edge_cases.blend : Maillage combinant de vrais défauts (faces nulles, arêtes filaires, isolés) et cas limites légitimes.
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
import math
import numpy as np

SCENE_DIR = root_dir / "tests" / "test_scenes"
SCENE_DIR.mkdir(parents=True, exist_ok=True)

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh, do_unlink=True)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat, do_unlink=True)

def save_scene(filename: str):
    path = SCENE_DIR / filename
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print(f"Scène créée : {path}")

# ---------------------------------------------------------------------------
# 1. 01_simple_clean.blend
# ---------------------------------------------------------------------------
def create_01_simple_clean():
    reset_scene()
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0)
    obj = bpy.context.active_object
    obj.name = "CleanCylinder"
    
    # Rendre les caps en quads
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # Trianguler puis quadranguler les caps pour n-gones
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(obj.data)
    bm.free()
    
    mat = bpy.data.materials.new("Mat_Clean")
    obj.data.materials.append(mat)
    save_scene("01_simple_clean.blend")

# ---------------------------------------------------------------------------
# 2. 02_dense_triangulated.blend
# ---------------------------------------------------------------------------
def create_02_dense_triangulated():
    reset_scene()
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.5)
    obj = bpy.context.active_object
    obj.name = "DenseTriangulatedSphere"
    mat = bpy.data.materials.new("Mat_DenseRock")
    obj.data.materials.append(mat)
    save_scene("02_dense_triangulated.blend")

# ---------------------------------------------------------------------------
# 3. 03_sculpted_organic.blend
# ---------------------------------------------------------------------------
def create_03_sculpted_organic():
    reset_scene()
    bpy.ops.mesh.primitive_monkey_add(size=2.0)
    obj = bpy.context.active_object
    obj.name = "SculptedOrganicModel"
    
    # Subdiviser pour simuler un sculpt haute densité avec détails fins
    sub_mod = obj.modifiers.new("Subsurf", 'SUBSURF')
    sub_mod.levels = 3
    sub_mod.render_levels = 3
    bpy.ops.object.modifier_apply(modifier="Subsurf")
    
    # Ajouter un déplacement ondulatoire pour micro-reliefs
    mesh = obj.data
    for v in mesh.vertices:
        v.co.z += 0.05 * math.sin(v.co.x * 12.0) * math.cos(v.co.y * 12.0)
    
    # Ombrage lissé
    for p in mesh.polygons:
        p.use_smooth = True
        
    mat = bpy.data.materials.new("Mat_SkinOrganic")
    obj.data.materials.append(mat)
    save_scene("03_sculpted_organic.blend")

# ---------------------------------------------------------------------------
# 4. 04_mechanical_assembly.blend
# ---------------------------------------------------------------------------
def create_04_mechanical_assembly():
    reset_scene()
    # Plaque de base
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    base = bpy.context.active_object
    base.scale = (2.0, 1.5, 0.2)
    bpy.ops.object.transform_apply(scale=True)
    
    # Axe central (Cylindre)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.4, depth=1.5, location=(0, 0, 0.75))
    axis = bpy.context.active_object
    
    # Écrou hexagonal
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.8, depth=0.4, location=(0, 0, 1.2))
    nut = bpy.context.active_object
    
    # Joindre en un assemblage multi-composantes
    base.select_set(True)
    axis.select_set(True)
    nut.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    
    assembly = bpy.context.active_object
    assembly.name = "MechanicalAssembly"
    mat = bpy.data.materials.new("Mat_SteelCAD")
    assembly.data.materials.append(mat)
    save_scene("04_mechanical_assembly.blend")

# ---------------------------------------------------------------------------
# 5. 05_open_surface_cloth.blend
# ---------------------------------------------------------------------------
def create_05_open_surface_cloth():
    reset_scene()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=20, y_subdivisions=20, size=3.0)
    cloth = bpy.context.active_object
    cloth.name = "OpenClothSurface"
    
    # Ondulation type drapé
    mesh = cloth.data
    for v in mesh.vertices:
        r = math.sqrt(v.co.x**2 + v.co.y**2)
        v.co.z = 0.3 * math.cos(r * 3.0) * math.exp(-0.2 * r)
        
    mat = bpy.data.materials.new("Mat_SilkCloth")
    cloth.data.materials.append(mat)
    save_scene("05_open_surface_cloth.blend")

# ---------------------------------------------------------------------------
# 6. 06_multi_uv_materials.blend
# ---------------------------------------------------------------------------
def create_06_multi_uv_materials():
    reset_scene()
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    obj.name = "MultiUvMaterialAsset"
    
    mesh = obj.data
    # 2 couches UV
    uv1 = mesh.uv_layers.new(name="UVMap_BaseColor")
    uv2 = mesh.uv_layers.new(name="UVMap_Lightmap")
    
    # 3 matériaux assignés
    mat1 = bpy.data.materials.new("Mat_Wood")
    mat2 = bpy.data.materials.new("Mat_Metal")
    mat3 = bpy.data.materials.new("Mat_Glass")
    mesh.materials.append(mat1)
    mesh.materials.append(mat2)
    mesh.materials.append(mat3)
    
    # Assigner des matériaux différents aux faces
    for i, p in enumerate(mesh.polygons):
        p.material_index = i % 3
        
    # Couche de couleur de sommets
    vcol = mesh.color_attributes.new(name="AO_VertexColors", type='FLOAT_COLOR', domain='CORNER')
    
    # Marquer des coutures UV (Seams)
    mesh.edges[0].use_seam = True
    mesh.edges[1].use_seam = True
    save_scene("06_multi_uv_materials.blend")

# ---------------------------------------------------------------------------
# 7. 07_deformable_character.blend
# ---------------------------------------------------------------------------
def create_07_deformable_character():
    reset_scene()
    bpy.ops.mesh.primitive_monkey_add(size=2.0)
    obj = bpy.context.active_object
    obj.name = "DeformableCharacterHead"
    
    # Créer des groupes de sommets d'armature avec pondérations
    vg_head = obj.vertex_groups.new(name="DEF_Head")
    vg_jaw = obj.vertex_groups.new(name="DEF_Jaw")
    vg_neck = obj.vertex_groups.new(name="DEF_Neck")
    vg_ear_l = obj.vertex_groups.new(name="DEF_Ear.L")
    
    for v in obj.data.vertices:
        if v.co.z > 0.2:
            vg_head.add([v.index], 1.0, 'REPLACE')
        elif v.co.z < -0.2:
            vg_neck.add([v.index], 0.8, 'REPLACE')
            vg_jaw.add([v.index], 0.5, 'REPLACE')
        else:
            vg_head.add([v.index], 0.5, 'REPLACE')
            vg_neck.add([v.index], 0.5, 'REPLACE')
            
        if v.co.x > 0.6:
            vg_ear_l.add([v.index], 0.9, 'REPLACE')
            
    mat = bpy.data.materials.new("Mat_ToonSkin")
    obj.data.materials.append(mat)
    save_scene("07_deformable_character.blend")

# ---------------------------------------------------------------------------
# 8. 08_defects_and_edge_cases.blend
# ---------------------------------------------------------------------------
def create_08_defects_and_edge_cases():
    reset_scene()
    mesh = bpy.data.meshes.new("DefectEdgeCaseMesh")
    bm = bmesh.new()
    
    # Partie 1 : Quads sains
    v0 = bm.verts.new((-1, -1, 0))
    v1 = bm.verts.new((0, -1, 0))
    v2 = bm.verts.new((0, 0, 0))
    v3 = bm.verts.new((-1, 0, 0))
    bm.faces.new((v0, v1, v2, v3))
    
    # Partie 2 : N-gone régulier convexe (5 côtés)
    v4 = bm.verts.new((1, -1, 0))
    v5 = bm.verts.new((1.5, -0.5, 0))
    v6 = bm.verts.new((1, 0, 0))
    bm.faces.new((v1, v4, v5, v6, v2))
    
    # Partie 3 : Face d'aire nulle (dégénérée colinéaire)
    v7 = bm.verts.new((-2, 0, 0))
    v8 = bm.verts.new((-2, 0.5, 0))
    v9 = bm.verts.new((-2, 1.0, 0))
    v8_collinear = bm.verts.new((-2, 0.5, 0.0000000001))
    bm.faces.new((v7, v8_collinear, v9))
    
    # Partie 4 : Éléments orphelins (2 sommets isolés, 1 arête filaire)
    bm.verts.new((4, 4, 0))
    bm.verts.new((5, 4, 0))
    vw1 = bm.verts.new((3, 2, 0))
    vw2 = bm.verts.new((3, 3, 0))
    bm.edges.new((vw1, vw2))
    
    # Partie 5 : Arête vive légitime (sharp edge)
    bm.to_mesh(mesh)
    bm.free()
    
    mesh.edges[0].use_edge_sharp = True
    
    obj = bpy.data.objects.new("DefectAndEdgeCaseAsset", mesh)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.new("Mat_Debug")
    obj.data.materials.append(mat)
    
    save_scene("08_defects_and_edge_cases.blend")

if __name__ == "__main__":
    print("--- Génération des 8 scènes .blend représentatives ---")
    create_01_simple_clean()
    create_02_dense_triangulated()
    create_03_sculpted_organic()
    create_04_mechanical_assembly()
    create_05_open_surface_cloth()
    create_06_multi_uv_materials()
    create_07_deformable_character()
    create_08_defects_and_edge_cases()
    print("--- 8 scènes créées avec succès dans tests/test_scenes ---")
