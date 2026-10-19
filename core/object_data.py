"""MeshForge - Module de nettoyage des données d'objet (Section 3.6 du CdC).
Nettoie les slots de matériaux dupliqués ou orphelins sur l'objet sans jamais
détruire de datablocks globaux du fichier Blender. Supprime les vertex groups vides.
"""

from __future__ import annotations
import bpy
from typing import Dict, Any, List, Set


def execute_object_data(obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Nettoie les slots de matériaux et groupes de sommets de l'objet cible."""
    results: Dict[str, Any] = {
        "status": "SUCCESS",
        "duplicate_slots_merged": 0,
        "unused_slots_removed": 0,
        "empty_vertex_groups_removed": 0,
        "log": []
    }

    if not obj or obj.type != 'MESH':
        results["status"] = "ERROR"
        results["log"].append("Objet invalide pour le nettoyage des données d'objet.")
        return results

    prev_mode = obj.mode
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data

    # 1. Fusion des slots de matériaux dupliqués pointant vers le même matériau
    if getattr(props, "clean_material_doubles", True) and len(obj.material_slots) > 1:
        seen_materials: Dict[bpy.types.Material, int] = {}
        remap: Dict[int, int] = {} # old_slot_index -> target_slot_index
        slots_to_remove: List[int] = []

        for idx, slot in enumerate(obj.material_slots):
            mat = slot.material
            if mat is None:
                continue
            if mat in seen_materials:
                remap[idx] = seen_materials[mat]
                slots_to_remove.append(idx)
            else:
                seen_materials[mat] = idx

        if remap:
            # Réassigner les faces
            for poly in mesh.polygons:
                if poly.material_index in remap:
                    poly.material_index = remap[poly.material_index]

            # Supprimer les slots redondants en partant de la fin
            for idx in sorted(slots_to_remove, reverse=True):
                obj.active_material_index = idx
                bpy.ops.object.material_slot_remove()

            results["duplicate_slots_merged"] = len(slots_to_remove)
            results["log"].append(f"Slots de matériaux dupliqués fusionnés : {len(slots_to_remove)}.")

    # 2. Suppression des slots de matériaux non assignés à la géométrie
    if getattr(props, "clean_unused_material_slots", True) and len(obj.material_slots) > 0:
        used_indices: Set[int] = {poly.material_index for poly in mesh.polygons}
        unused_slots: List[int] = [
            i for i in range(len(obj.material_slots)) if i not in used_indices
        ]

        if unused_slots:
            # Pour supprimer proprement sans décaler les indices des autres faces,
            # on supprime en partant de la fin et on met à jour les indices des polygones
            for slot_idx in sorted(unused_slots, reverse=True):
                # Décrémenter les indices supérieurs dans les polygones
                for poly in mesh.polygons:
                    if poly.material_index > slot_idx:
                        poly.material_index -= 1
                obj.active_material_index = slot_idx
                bpy.ops.object.material_slot_remove()

            results["unused_slots_removed"] = len(unused_slots)
            results["log"].append(f"Slots de matériaux inutilisés retirés : {len(unused_slots)}.")

    # 3. Suppression des groupes de sommets vides
    if getattr(props, "clean_empty_vertex_groups", True) and len(obj.vertex_groups) > 0:
        # Trouver quels groupes de sommets ont au moins un sommet avec un poids > 0
        used_vg_indices: Set[int] = set()
        for v in mesh.vertices:
            for g in v.groups:
                if g.weight > 0.0:
                    used_vg_indices.add(g.group)

        empty_groups = [vg for vg in obj.vertex_groups if vg.index not in used_vg_indices]
        removed_count = len(empty_groups)
        for vg in empty_groups:
            obj.vertex_groups.remove(vg)

        results["empty_vertex_groups_removed"] = removed_count
        if removed_count > 0:
            results["log"].append(f"Groupes de sommets vides supprimés : {removed_count}.")

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
