"""MeshForge - Module de nettoyage des données d'objet (Section 3.6 du CdC).
Nettoie les slots de matériaux dupliqués ou orphelins sur l'objet sans jamais
détruire de datablocks globaux du fichier Blender. Supprime les vertex groups vides.
Optimisé pour les maillages denses (utilise les opérateurs C natifs de Blender).
"""

from __future__ import annotations
import bpy
from typing import Dict, Any, List, Set


def execute_object_data(obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Nettoie les slots de matériaux et groupes de sommets de l'objet cible de manière performante et sûre."""
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
    initial_slot_count = len(obj.material_slots)

    # 1. Fusion des slots de matériaux dupliqués pointant vers le même matériau
    if getattr(props, "clean_material_doubles", True) and initial_slot_count > 1:
        seen_materials: Dict[bpy.types.Material, int] = {}
        remap: Dict[int, int] = {}  # duplicate_slot_idx -> canonical_slot_idx

        for idx, slot in enumerate(obj.material_slots):
            mat = slot.material
            if mat is None:
                continue
            if mat in seen_materials:
                remap[idx] = seen_materials[mat]
            else:
                seen_materials[mat] = idx

        if remap:
            # Réassigner les faces pointant vers un slot dupliqué vers le slot canonique
            for poly in mesh.polygons:
                if poly.material_index in remap:
                    poly.material_index = remap[poly.material_index]

            # Supprimer les slots désormais libérés
            duplicate_indices = sorted(list(remap.keys()), reverse=True)
            for dup_idx in duplicate_indices:
                if dup_idx < len(obj.material_slots):
                    obj.active_material_index = dup_idx
                    bpy.ops.object.material_slot_remove()

            results["duplicate_slots_merged"] = len(remap)
            results["log"].append(f"Slots de matériaux dupliqués fusionnés : {len(remap)}.")

    # 2. Suppression des slots de matériaux non assignés à la géométrie (rapide en C)
    if getattr(props, "clean_unused_material_slots", True) and len(obj.material_slots) > 0:
        before_clean_slots = len(obj.material_slots)
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.material_slot_remove_unused()
            removed = before_clean_slots - len(obj.material_slots)
            results["unused_slots_removed"] = max(0, removed)
            if removed > 0:
                results["log"].append(f"Slots de matériaux inutilisés retirés : {removed}.")
        except Exception as e:
            results["log"].append(f"Avertissement retrait slots inutilisés : {e}")

    # 3. Suppression des groupes de sommets vides (aucun poids > 0)
    if getattr(props, "clean_empty_vertex_groups", True) and len(obj.vertex_groups) > 0:
        used_vg_indices: Set[int] = set()
        for v in mesh.vertices:
            for g in v.groups:
                if g.weight > 0.0:
                    used_vg_indices.add(g.group)

        empty_groups = [vg for vg in obj.vertex_groups if vg.index not in used_vg_indices]
        removed_vg = len(empty_groups)
        for vg in empty_groups:
            obj.vertex_groups.remove(vg)

        results["empty_vertex_groups_removed"] = removed_vg
        if removed_vg > 0:
            results["log"].append(f"Groupes de sommets vides supprimés : {removed_vg}.")

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
