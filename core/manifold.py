"""MeshForge - Module de gestion Manifold (Section 3.2 du CdC).
Prend en charge l'inspection et la correction des non-manifold, le bouchage
contrôlé de trous, et le nettoyage de géométrie filaire (wire).
"""

from __future__ import annotations
import bpy
import bmesh
from typing import Dict, Any


def execute_manifold(obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Exécute les opérations de la section Manifold."""
    results: Dict[str, Any] = {
        "status": "SUCCESS",
        "mode": getattr(props, "manifold_mode", "CAREFUL"),
        "holes_filled": 0,
        "wire_removed": 0,
        "non_manifold_elements_removed": 0,
        "planar_applied": False,
        "log": []
    }

    if not obj or obj.type != 'MESH':
        results["status"] = "ERROR"
        results["log"].append("Objet invalide pour l'opération manifold.")
        return results

    mode = getattr(props, "manifold_mode", "CAREFUL")

    # Mode DIAGNOSTIC : n'effectue aucune modification, rapporte l'état
    if mode == 'DIAGNOSTIC':
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        nm_edges = sum(1 for e in bm.edges if not e.is_manifold)
        nm_verts = sum(1 for v in bm.verts if not v.is_manifold)
        boundary_edges = sum(1 for e in bm.edges if e.is_boundary)
        wire_edges = sum(1 for e in bm.edges if e.is_wire)
        bm.free()
        results["log"].append(f"[Diagnostic] Arêtes non-manifold: {nm_edges}, Sommets non-manifold: {nm_verts}, Frontières: {boundary_edges}, Filaires: {wire_edges}.")
        return results

    prev_mode = obj.mode
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    # 1. Suppression des géométries filaires sans surface (Wire)
    if getattr(props, "remove_wire_geometry", True):
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        wire_edges = [e for e in bm.edges if e.is_wire]
        if wire_edges:
            count = len(wire_edges)
            bmesh.ops.delete(bm, geom=wire_edges, context='EDGES')
            bmesh.update_edit_mesh(obj.data)
            results["wire_removed"] = count
            results["log"].append(f"Arêtes filaires (wire) supprimées : {count}.")

    # 2. Remplissage contrôlé des trous (Fill Holes)
    if getattr(props, "fill_holes", False):
        max_sides = getattr(props, "fill_holes_max_sides", 4)
        bpy.ops.mesh.select_all(action='SELECT')
        # fill_holes avec limitation du nombre de côtés
        try:
            bpy.ops.mesh.fill_holes(sides=max_sides)
            bmesh.update_edit_mesh(obj.data)
            results["log"].append(f"Remplissage de trous appliqué (max {max_sides} côtés).")
        except Exception as e:
            results["log"].append(f"Avertissement remplissage trous : {e}")

    # 3. Traitement non-manifold (Prudent vs Agressif)
    if mode == 'AGGRESSIVE':
        if getattr(props, "remove_non_manifold_faces", False) or getattr(props, "remove_non_manifold_verts", False):
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_non_manifold(
                extend=False,
                use_wire=True,
                use_boundary=False, # ne pas supprimer les frontières ouvertes par défaut
                use_multi_face=True,
                use_non_contiguous=True,
                use_verts=getattr(props, "remove_non_manifold_verts", False)
            )
            del_type = 'VERT' if getattr(props, "remove_non_manifold_verts", False) else 'FACES'
            bpy.ops.mesh.delete(type=del_type)
            bmesh.update_edit_mesh(obj.data)
            results["log"].append(f"[Agressif] Éléments non-manifold supprimés (type: {del_type}).")

    # 4. Make Planar / Undistort
    if getattr(props, "make_planar", False):
        factor = getattr(props, "make_planar_factor", 1.0)
        iters = getattr(props, "make_planar_iterations", 1)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.face_make_planar(factor=factor, repeat=iters)
        bmesh.update_edit_mesh(obj.data)
        results["planar_applied"] = True
        results["log"].append(f"Aplanissement des faces (facteur: {factor}, itérations: {iters}).")

    # 5. Flatten Faces (Lissage local contrôlé)
    if getattr(props, "flatten_faces", False):
        flatten_iters = getattr(props, "flatten_iterations", 3)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=flatten_iters)
        bmesh.update_edit_mesh(obj.data)
        results["log"].append(f"Lissage des faces appliqué ({flatten_iters} itérations).")

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
