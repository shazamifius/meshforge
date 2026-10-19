"""MeshForge - Module de statistiques et de métriques de maillage.
Fournit une analyse précise et non destructive de l'état géométrique et topologique.
"""

from __future__ import annotations
import bpy
import bmesh
from typing import Dict, Any


def get_mesh_statistics(obj: bpy.types.Object) -> Dict[str, Any]:
    """Calcule les statistiques complètes d'un objet maillage.
    Distingue clairement les faces polygonales réelles et les triangles estimés.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {
            "valid": False,
            "error": "L'objet sélectionné n'est pas un maillage valide."
        }

    mesh = obj.data

    # Comptage direct Blender
    vert_count = len(mesh.vertices)
    edge_count = len(mesh.edges)
    face_count = len(mesh.polygons)

    # Calcul précis des triangles estimés (n-gons décomposés en triangles)
    estimated_triangles = sum(max(0, len(poly.vertices) - 2) for poly in mesh.polygons)

    # Répartition quad / tri / n-gon
    tri_faces = 0
    quad_faces = 0
    ngon_faces = 0
    for poly in mesh.polygons:
        v_count = len(poly.vertices)
        if v_count == 3:
            tri_faces += 1
        elif v_count == 4:
            quad_faces += 1
        elif v_count > 4:
            ngon_faces += 1

    # Attributs et métadonnées
    uv_layer_count = len(mesh.uv_layers)
    uv_layer_names = [uv.name for uv in mesh.uv_layers]
    color_attribute_count = len(mesh.color_attributes)
    vertex_group_count = len(obj.vertex_groups)
    material_slot_count = len(obj.material_slots)
    assigned_materials = [slot.material.name for slot in obj.material_slots if slot.material]

    # Analyse topologique via BMesh en lecture seule
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
    loose_edges = sum(1 for e in bm.edges if not e.link_faces)
    boundary_edges = sum(1 for e in bm.edges if e.is_boundary)
    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
    non_manifold_verts = sum(1 for v in bm.verts if not v.is_manifold)
    zero_area_faces = sum(1 for f in bm.faces if f.calc_area() <= 1e-7)

    is_manifold = (non_manifold_edges == 0 and non_manifold_verts == 0 and boundary_edges == 0)
    is_watertight = is_manifold and (loose_verts == 0) and (loose_edges == 0)

    bm.free()

    return {
        "valid": True,
        "object_name": obj.name,
        "vertices": vert_count,
        "edges": edge_count,
        "faces": face_count,
        "estimated_triangles": estimated_triangles,
        "tri_faces": tri_faces,
        "quad_faces": quad_faces,
        "ngon_faces": ngon_faces,
        "uv_layer_count": uv_layer_count,
        "uv_layer_names": uv_layer_names,
        "color_attribute_count": color_attribute_count,
        "vertex_group_count": vertex_group_count,
        "material_slot_count": material_slot_count,
        "assigned_materials": assigned_materials,
        "loose_verts": loose_verts,
        "loose_edges": loose_edges,
        "boundary_edges": boundary_edges,
        "non_manifold_edges": non_manifold_edges,
        "non_manifold_verts": non_manifold_verts,
        "zero_area_faces": zero_area_faces,
        "is_manifold": is_manifold,
        "is_watertight": is_watertight,
    }
