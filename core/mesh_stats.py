"""MeshForge - Module de statistiques, métriques et diagnostic renforcé de maillage (Phase B).
Fournit une analyse exhaustive et non-destructive de l'état géométrique et topologique,
avec détection des composantes isolées, trous, doublons en lecture seule et inventaire d'attributs.
"""

from __future__ import annotations
import bpy
import bmesh
from mathutils.kdtree import KDTree
from typing import Dict, Any, List, Set


def get_mesh_statistics(obj: bpy.types.Object, duplicate_tolerance: float = 0.0001, max_kdtree_verts: int = 300000) -> Dict[str, Any]:
    """Calcule les statistiques et diagnostics complets d'un objet maillage.
    Distingue clairement les faces réelles, triangles estimés, éléments problématiques
    et inventorie rigoureusement tous les attributs (UV, matériaux, groupes, arêtes vives).
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {
            "valid": False,
            "error": "L'objet sélectionné n'est pas un maillage valide."
        }

    mesh = obj.data

    # 1. Métriques de base Blender
    vert_count = len(mesh.vertices)
    edge_count = len(mesh.edges)
    face_count = len(mesh.polygons)

    # Triangles estimés
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

    # 2. Inventaire des attributs et métadonnées
    uv_layer_names = [uv.name for uv in mesh.uv_layers]
    color_attribute_names = [ca.name for ca in mesh.color_attributes]
    vertex_group_names = [vg.name for vg in obj.vertex_groups]
    material_names = [slot.material.name for slot in obj.material_slots if slot.material]
    
    # Présence d'arêtes marquées vives (Sharp) ou coutures (Seams)
    sharp_edge_count = sum(1 for e in mesh.edges if e.use_edge_sharp)
    seam_edge_count = sum(1 for e in mesh.edges if e.use_seam)

    # 3. Analyse topologique approfondie via BMesh en lecture seule
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
    loose_edges = sum(1 for e in bm.edges if not e.link_faces)
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    boundary_edge_count = len(boundary_edges)
    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
    non_manifold_verts = sum(1 for v in bm.verts if not v.is_manifold)
    zero_area_faces = sum(1 for f in bm.faces if f.calc_area() <= 1e-7)

    # Détection des ouvertures/trous (boundary loops)
    boundary_loops_count = 0
    visited_b_edges: Set[bmesh.types.BMEdge] = set()
    for b_edge in boundary_edges:
        if b_edge in visited_b_edges:
            continue
        boundary_loops_count += 1
        queue = [b_edge]
        while queue:
            curr = queue.pop()
            visited_b_edges.add(curr)
            for v in curr.verts:
                for cand in v.link_edges:
                    if cand.is_boundary and cand not in visited_b_edges:
                        queue.append(cand)

    # Détection des composantes connexes disjointes (islands)
    disjoint_components = 0
    unvisited_faces = set(bm.faces)
    while unvisited_faces:
        disjoint_components += 1
        root = unvisited_faces.pop()
        queue = [root]
        while queue:
            f = queue.pop()
            for e in f.edges:
                for neighbor in e.link_faces:
                    if neighbor in unvisited_faces:
                        unvisited_faces.remove(neighbor)
                        queue.append(neighbor)

    # Si aucune face mais des sommets existent, compter les composantes par sommets
    if face_count == 0 and vert_count > 0:
        disjoint_components = loose_verts

    is_open_surface = (boundary_edge_count > 0)
    is_manifold = (non_manifold_edges == 0 and non_manifold_verts == 0 and not is_open_surface)
    is_watertight = is_manifold and (loose_verts == 0) and (loose_edges == 0)

    bm.free()

    # 4. Détection non-destructive des doublons potentiels (KDTree)
    potential_duplicate_verts = 0
    if 0 < vert_count <= max_kdtree_verts:
        kd = KDTree(vert_count)
        for i, v in enumerate(mesh.vertices):
            kd.insert(v.co, i)
        kd.balance()

        seen_dup_indices: Set[int] = set()
        for i, v in enumerate(mesh.vertices):
            if i in seen_dup_indices:
                continue
            neighbors = kd.find_range(v.co, duplicate_tolerance)
            if len(neighbors) > 1:
                for _, n_idx, _ in neighbors:
                    seen_dup_indices.add(n_idx)
                potential_duplicate_verts += (len(neighbors) - 1)

    # 5. Évaluation des risques techniques (Phase B - Section 2.2 / 11)
    risk_assessment: List[str] = []
    if is_open_surface:
        risk_assessment.append(
            f"Surface ouverte détectée ({boundary_edge_count} arêtes de frontière, {boundary_loops_count} ouvertures). "
            "Ne pas activer 'Fill Holes' ou le recalcul extérieur aveugle sur une surface volontairement ouverte."
        )
    if non_manifold_edges > 0 or non_manifold_verts > 0:
        risk_assessment.append(
            f"Défauts non-manifold détectés ({non_manifold_edges} arêtes, {non_manifold_verts} sommets). "
            "Une suppression agressive risque de trouer le maillage."
        )
    if zero_area_faces > 0:
        risk_assessment.append(
            f"{zero_area_faces} faces d'aire nulle/dégénérées détectées. Dissolution recommandée."
        )
    if loose_verts > 0 or loose_edges > 0:
        risk_assessment.append(
            f"Éléments isolés orphelins détectés ({loose_verts} sommets, {loose_edges} arêtes). Nettoyage recommandé."
        )
    if potential_duplicate_verts > 0:
        risk_assessment.append(
            f"{potential_duplicate_verts} sommets superposés potentiels détectés (seuil {duplicate_tolerance}m)."
        )

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
        "uv_layer_count": len(uv_layer_names),
        "uv_layer_names": uv_layer_names,
        "color_attribute_count": len(color_attribute_names),
        "color_attribute_names": color_attribute_names,
        "vertex_group_count": len(vertex_group_names),
        "vertex_group_names": vertex_group_names,
        "material_slot_count": len(obj.material_slots),
        "material_names": material_names,
        "sharp_edge_count": sharp_edge_count,
        "seam_edge_count": seam_edge_count,
        "loose_verts": loose_verts,
        "loose_edges": loose_edges,
        "boundary_edges": boundary_edge_count,
        "boundary_loops_count": boundary_loops_count,
        "non_manifold_edges": non_manifold_edges,
        "non_manifold_verts": non_manifold_verts,
        "zero_area_faces": zero_area_faces,
        "disjoint_components": disjoint_components,
        "potential_duplicate_verts": potential_duplicate_verts,
        "is_open_surface": is_open_surface,
        "is_manifold": is_manifold,
        "is_watertight": is_watertight,
        "risk_assessment": risk_assessment,
    }
