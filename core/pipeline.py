"""MeshForge - Pipeline d'orchestration robuste et sécurisé (Phase B).
Garantit l'intégrité de l'original en cas d'erreur à n'importe quelle étape,
distingue les problèmes détectés des problèmes corrigés et consigne tous les paramètres.
"""

from __future__ import annotations
import bpy
import time
from typing import Dict, Any

from .mesh_stats import get_mesh_statistics
from .repair_pipeline import execute_repair
from .manifold import execute_manifold
from .dissolve import execute_dissolve
from .topology import execute_topology
from .normals import execute_normals
from .object_data import execute_object_data
from .simplification import execute_simplification


def duplicate_object_non_destructive(source_obj: bpy.types.Object, suffix: str = "_MF_Optimized") -> bpy.types.Object:
    """Duplique l'objet et ses données de maillage de manière strictement indépendante."""
    new_mesh = source_obj.data.copy()
    new_obj = source_obj.copy()
    new_obj.data = new_mesh
    new_obj.name = f"{source_obj.name}{suffix}"

    for coll in source_obj.users_collection:
        coll.objects.link(new_obj)

    return new_obj


def extract_applied_parameters(props: Any) -> Dict[str, Any]:
    """Extrait un dictionnaire des paramètres appliqués lors de la session."""
    params = {}
    param_names = [
        "create_new_object", "hide_original", "destructive_mode",
        "enable_repair", "repair_loose_geometry", "repair_doubles", "doubles_tolerance",
        "doubles_relative", "doubles_relative_factor", "repair_zero_faces", "zero_faces_threshold",
        "repair_dispensables", "dispensable_angle",
        "enable_manifold", "manifold_mode", "fill_holes", "fill_holes_max_sides", "remove_wire_geometry",
        "remove_non_manifold_faces", "remove_non_manifold_verts", "make_planar", "flatten_faces",
        "enable_dissolve", "dissolve_mode", "dissolve_angle", "preserve_sharp", "preserve_seams",
        "preserve_materials", "preserve_uvs", "preserve_boundaries",
        "enable_simplification", "simplification_mode", "simplification_percentage", "simplification_target_triangles",
        "enable_simplification_tolerance", "simplification_max_tolerance", "tolerance_relative", "collapse_triangulate",
        "enable_topology", "topology_mode", "triangulate_quad_method", "triangulate_ngon_method",
        "quads_face_threshold", "quads_shape_threshold",
        "enable_normals", "recalculate_normals", "recalculate_direction", "apply_auto_smooth",
        "auto_smooth_angle", "weighted_normals", "clear_custom_split_normals", "clear_sharp_edges",
        "enable_object_data", "clean_material_doubles", "clean_unused_material_slots", "clean_empty_vertex_groups"
    ]
    for name in param_names:
        if hasattr(props, name):
            params[name] = getattr(props, name)
    return params


def run_meshforge_pipeline(source_obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Exécute la chaîne d'optimisation avec garantie formelle de rollback en cas d'erreur."""
    t_start_total = time.perf_counter()

    report: Dict[str, Any] = {
        "success": False,
        "original_name": source_obj.name if source_obj else "Inconnu",
        "result_name": "",
        "initial_stats": {},
        "final_stats": {},
        "issues_detected": {},
        "issues_resolved": {
            "doubles_merged": 0,
            "loose_verts_removed": 0,
            "loose_edges_removed": 0,
            "zero_faces_dissolved": 0,
            "wire_edges_removed": 0,
            "unused_slots_removed": 0,
            "empty_vg_removed": 0,
        },
        "phase_timings": {},
        "applied_parameters": extract_applied_parameters(props),
        "logs": [],
        "errors": [],
        "warnings": [],
        "reduction_percentage": 0.0,
    }

    if not source_obj or source_obj.type != 'MESH':
        report["errors"].append("Sélectionnez un objet de type maillage (MESH).")
        return report

    if source_obj.mode != 'OBJECT' or getattr(source_obj.data, "is_editmode", False):
        report["errors"].append("L'objet est en mode Édition. Veuillez repasser en mode Objet (Touche Tab) pour exécuter l'optimisation.")
        return report

    # 1. Diagnostic initial (stats avant traitement)
    t0 = time.perf_counter()
    stats_before = get_mesh_statistics(source_obj)
    report["initial_stats"] = stats_before
    report["phase_timings"]["diagnostic_initial"] = time.perf_counter() - t0

    # Consigner les problèmes détectés (Phase B)
    report["issues_detected"] = {
        "loose_verts": stats_before.get("loose_verts", 0),
        "loose_edges": stats_before.get("loose_edges", 0),
        "potential_duplicates": stats_before.get("potential_duplicate_verts", 0),
        "zero_area_faces": stats_before.get("zero_area_faces", 0),
        "non_manifold_edges": stats_before.get("non_manifold_edges", 0),
        "non_manifold_verts": stats_before.get("non_manifold_verts", 0),
        "boundary_loops_count": stats_before.get("boundary_loops_count", 0),
        "is_open_surface": stats_before.get("is_open_surface", False),
        "disjoint_components": stats_before.get("disjoint_components", 1),
    }

    # Transférer les avertissements de risque
    report["warnings"].extend(stats_before.get("risk_assessment", []))

    # Gestion de la duplication et de la sécurité (Rollback garanti)
    create_new = getattr(props, "create_new_object", True)
    target_obj = None
    destructive_backup_mesh = None

    if create_new:
        target_obj = duplicate_object_non_destructive(source_obj)
        if getattr(props, "hide_original", True):
            source_obj.hide_set(True)
        report["logs"].append(f"Objet dupliqué créé : '{target_obj.name}' (original intact et masqué).")
    else:
        # Mode destructif : sauvegarder une copie de secours temporaire en mémoire
        destructive_backup_mesh = source_obj.data.copy()
        target_obj = source_obj
        report["warnings"].append("Attention : mode destructif direct sélectionné. Sauvegarde mémoire active.")

    report["result_name"] = target_obj.name

    # Rendre l'objet cible actif
    bpy.context.view_layer.objects.active = target_obj
    target_obj.select_set(True)

    try:
        # 2. Réparation prudente (Repair)
        if getattr(props, "enable_repair", True):
            t0 = time.perf_counter()
            res_rep = execute_repair(target_obj, props)
            report["phase_timings"]["repair"] = time.perf_counter() - t0
            report["logs"].extend(res_rep.get("log", []))
            report["issues_resolved"]["doubles_merged"] = res_rep.get("doubles_removed", 0)

        # 3. Manifold (Nettoyage & trous)
        if getattr(props, "enable_manifold", True):
            t0 = time.perf_counter()
            res_man = execute_manifold(target_obj, props)
            report["phase_timings"]["manifold"] = time.perf_counter() - t0
            report["logs"].extend(res_man.get("log", []))
            report["issues_resolved"]["wire_edges_removed"] = res_man.get("wire_removed", 0)

        # 4. Dissolve / simplification coplanaire
        if getattr(props, "enable_dissolve", False):
            t0 = time.perf_counter()
            res_dis = execute_dissolve(target_obj, props)
            report["phase_timings"]["dissolve"] = time.perf_counter() - t0
            report["logs"].extend(res_dis.get("log", []))

        # 5. Réduction adaptative (Simplification géométrique - Phase C)
        if getattr(props, "enable_simplification", False):
            t0 = time.perf_counter()
            res_simp = execute_simplification(target_obj, props, orig_reference_obj=source_obj)
            report["phase_timings"]["simplification"] = time.perf_counter() - t0
            report["logs"].extend(res_simp.get("log", []))
            report["simplification_details"] = res_simp
            if res_simp.get("geometric_validation"):
                report["geometric_validation"] = res_simp.get("geometric_validation")

        # 6. Topology (Reconstruction topologique)
        if getattr(props, "enable_topology", False):
            t0 = time.perf_counter()
            res_top = execute_topology(target_obj, props)
            report["phase_timings"]["topology"] = time.perf_counter() - t0
            report["logs"].extend(res_top.get("log", []))

        # 6. Normals (Recalcul et lissage)
        if getattr(props, "enable_normals", True):
            t0 = time.perf_counter()
            res_norm = execute_normals(target_obj, props)
            report["phase_timings"]["normals"] = time.perf_counter() - t0
            report["logs"].extend(res_norm.get("log", []))

        # 7. Object Data (Nettoyage matériaux & vertex groups)
        if getattr(props, "enable_object_data", True):
            t0 = time.perf_counter()
            res_od = execute_object_data(target_obj, props)
            report["phase_timings"]["object_data"] = time.perf_counter() - t0
            report["logs"].extend(res_od.get("log", []))
            report["issues_resolved"]["unused_slots_removed"] = res_od.get("unused_slots_removed", 0)
            report["issues_resolved"]["empty_vg_removed"] = res_od.get("empty_vertex_groups_removed", 0)

        # 8. Validation finale et calcul des deltas réels
        t0 = time.perf_counter()
        stats_after = get_mesh_statistics(target_obj)
        report["final_stats"] = stats_after
        report["phase_timings"]["validation_finale"] = time.perf_counter() - t0

        # Calcul des corrections effectives
        report["issues_resolved"]["loose_verts_removed"] = max(0, stats_before.get("loose_verts", 0) - stats_after.get("loose_verts", 0))
        report["issues_resolved"]["loose_edges_removed"] = max(0, stats_before.get("loose_edges", 0) - stats_after.get("loose_edges", 0))
        report["issues_resolved"]["zero_faces_dissolved"] = max(0, stats_before.get("zero_area_faces", 0) - stats_after.get("zero_area_faces", 0))

        # Taux de réduction
        tri_before = stats_before.get("estimated_triangles", 0)
        tri_after = stats_after.get("estimated_triangles", 0)
        if tri_before > 0:
            reduction = ((tri_before - tri_after) / tri_before) * 100.0
            report["reduction_percentage"] = max(0.0, reduction)

        report["success"] = True

        # Si le mode destructif s'est terminé avec succès, libérer le mesh de secours
        if destructive_backup_mesh:
            bpy.data.meshes.remove(destructive_backup_mesh)

    except Exception as exc:
        report["errors"].append(f"Échec dans le pipeline : {exc}")
        report["success"] = False

        # ROLLBACK STRICT (L'original reste intact en cas d'échec)
        if create_new and target_obj and target_obj != source_obj:
            target_mesh = target_obj.data
            bpy.data.objects.remove(target_obj, do_unlink=True)
            if target_mesh:
                bpy.data.meshes.remove(target_mesh)
            source_obj.hide_set(False)
            bpy.context.view_layer.objects.active = source_obj
            source_obj.select_set(True)
            report["logs"].append("Rollback effectué : objet temporaire supprimé, original réactivé.")
        elif not create_new and destructive_backup_mesh:
            # Restaurer le mesh d'origine en mode destructif
            failed_mesh = source_obj.data
            source_obj.data = destructive_backup_mesh
            bpy.data.meshes.remove(failed_mesh)
            report["logs"].append("Rollback destructif effectué : maillage d'origine restauré depuis la sauvegarde.")

    total_duration = time.perf_counter() - t_start_total
    report["total_duration"] = total_duration
    report["phase_timings"]["total"] = total_duration

    return report
