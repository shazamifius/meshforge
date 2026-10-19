"""MeshForge - Pipeline d'orchestration non-destructif (Section 2 du CdC).
Coordonne l'ordre des opérations (Diagnostic, Repair, Manifold, Dissolve,
Topology, Normals, Object Data), mesure les temps d'exécution et préserve l'original.
"""

from __future__ import annotations
import bpy
import time
from typing import Dict, Any, List

from .mesh_stats import get_mesh_statistics
from .repair_pipeline import execute_repair
from .manifold import execute_manifold
from .dissolve import execute_dissolve
from .topology import execute_topology
from .normals import execute_normals
from .object_data import execute_object_data


def duplicate_object_non_destructive(source_obj: bpy.types.Object, suffix: str = "_MF_Optimized") -> bpy.types.Object:
    """Duplique l'objet et ses données de maillage de manière strictement indépendante."""
    new_mesh = source_obj.data.copy()
    new_obj = source_obj.copy()
    new_obj.data = new_mesh
    new_obj.name = f"{source_obj.name}{suffix}"

    # Associer aux collections de l'objet source
    for coll in source_obj.users_collection:
        coll.objects.link(new_obj)

    return new_obj


def run_meshforge_pipeline(source_obj: bpy.types.Object, props: Any) -> Dict[str, Any]:
    """Exécute la chaîne complète des opérations sélectionnées en respectant l'ordre."""
    t_start_total = time.perf_counter()

    report: Dict[str, Any] = {
        "success": False,
        "original_name": source_obj.name if source_obj else "Inconnu",
        "result_name": "",
        "initial_stats": {},
        "final_stats": {},
        "phase_timings": {},
        "logs": [],
        "errors": [],
        "warnings": [],
        "reduction_percentage": 0.0,
    }

    if not source_obj or source_obj.type != 'MESH':
        report["errors"].append("Sélectionnez un objet de type maillage (MESH).")
        return report

    # 1. Diagnostic initial (stats avant traitement)
    t0 = time.perf_counter()
    stats_before = get_mesh_statistics(source_obj)
    report["initial_stats"] = stats_before
    report["phase_timings"]["diagnostic_initial"] = time.perf_counter() - t0

    # Détermination de l'objet cible (Non-destructif par défaut)
    create_new = getattr(props, "create_new_object", True)
    if create_new:
        target_obj = duplicate_object_non_destructive(source_obj)
        if getattr(props, "hide_original", True):
            source_obj.hide_set(True)
        report["logs"].append(f"Objet dupliqué créé : '{target_obj.name}' (original préservé).")
    else:
        # Mode destructif explicite (doit être confirmé par confirmation préalable)
        target_obj = source_obj
        report["warnings"].append("Traitement direct (mode destructif) sélectionné par l'utilisateur.")

    report["result_name"] = target_obj.name

    # Définir l'objet cible comme actif et sélectionné
    bpy.context.view_layer.objects.active = target_obj
    target_obj.select_set(True)

    try:
        # 2. Réparation prudente (Repair)
        if getattr(props, "enable_repair", True):
            t0 = time.perf_counter()
            res = execute_repair(target_obj, props)
            report["phase_timings"]["repair"] = time.perf_counter() - t0
            report["logs"].extend(res.get("log", []))
            if res.get("status") == "ERROR":
                report["warnings"].append("La phase Repair a rencontré des avertissements.")

        # 3. Manifold (Nettoyage & trous)
        if getattr(props, "enable_manifold", True):
            t0 = time.perf_counter()
            res = execute_manifold(target_obj, props)
            report["phase_timings"]["manifold"] = time.perf_counter() - t0
            report["logs"].extend(res.get("log", []))
            if res.get("status") == "ERROR":
                report["warnings"].append("La phase Manifold a rencontré des avertissements.")

        # 4. Dissolve / simplification coplanaire
        if getattr(props, "enable_dissolve", False):
            t0 = time.perf_counter()
            res = execute_dissolve(target_obj, props)
            report["phase_timings"]["dissolve"] = time.perf_counter() - t0
            report["logs"].extend(res.get("log", []))
            if res.get("status") == "ERROR":
                report["warnings"].append("La phase Dissolve a rencontré des avertissements.")

        # 5. Topology (Reconstruction topologique)
        if getattr(props, "enable_topology", False):
            t0 = time.perf_counter()
            res = execute_topology(target_obj, props)
            report["phase_timings"]["topology"] = time.perf_counter() - t0
            report["logs"].extend(res.get("log", []))

        # 6. Normals (Recalcul et lissage)
        if getattr(props, "enable_normals", True):
            t0 = time.perf_counter()
            res = execute_normals(target_obj, props)
            report["phase_timings"]["normals"] = time.perf_counter() - t0
            report["logs"].extend(res.get("log", []))

        # 7. Object Data (Nettoyage matériaux & vertex groups)
        if getattr(props, "enable_object_data", True):
            t0 = time.perf_counter()
            res = execute_object_data(target_obj, props)
            report["phase_timings"]["object_data"] = time.perf_counter() - t0
            report["logs"].extend(res.get("log", []))

        # 8. Validation finale et rapport
        t0 = time.perf_counter()
        stats_after = get_mesh_statistics(target_obj)
        report["final_stats"] = stats_after
        report["phase_timings"]["validation_finale"] = time.perf_counter() - t0

        # Calcul du pourcentage de réduction (sur les triangles estimés)
        tri_before = stats_before.get("estimated_triangles", 0)
        tri_after = stats_after.get("estimated_triangles", 0)
        if tri_before > 0:
            reduction = ((tri_before - tri_after) / tri_before) * 100.0
            report["reduction_percentage"] = max(0.0, reduction)

        report["success"] = True

    except Exception as exc:
        report["errors"].append(f"Erreur inattendue dans le pipeline : {exc}")
        report["success"] = False

    total_duration = time.perf_counter() - t_start_total
    report["total_duration"] = total_duration
    report["phase_timings"]["total"] = total_duration

    return report
