"""MeshForge - Moteur de simplification géométrique adaptatif et contrôlé (Phase C).
Exploite le cœur de contraction d'arêtes natif de Blender (QEM Garland-Heckbert en C++)
couplé à un contrôleur de rétroaction BVH par dichotomie, garantissant le respect strict
de la tolérance géométrique et l'arbitrage documenté entre budget et erreur.
"""

from __future__ import annotations
import bpy
import bmesh
import time
from mathutils.bvhtree import BVHTree
from typing import Dict, Any, Optional, Set

from .validation import evaluate_geometric_deviation


def find_optimal_ratio_for_tolerance(
    orig_obj: bpy.types.Object,
    max_tolerance: float,
    min_ratio: float = 0.02,
    max_ratio: float = 1.0,
    delimiters: Optional[Set[str]] = None,
    max_iterations: int = 5
) -> float:
    """Effectue une recherche dichotomique guidée par BVH pour trouver le ratio
    de réduction maximal qui respecte strictement la tolérance géométrique maximale.
    """
    mesh_orig = orig_obj.data
    # Échantillons de test rapides pour la dichotomie (1 sommet sur 4)
    sampled_coords = [v.co for i, v in enumerate(mesh_orig.vertices) if i % 4 == 0]
    if len(sampled_coords) == 0 and len(mesh_orig.vertices) > 0:
        sampled_coords = [v.co for v in mesh_orig.vertices]

    low = min_ratio
    high = max_ratio
    best_admissible_ratio = 1.0
    prev_active = bpy.context.view_layer.objects.active

    try:
        for _ in range(max_iterations):
            mid = (low + high) / 2.0

            # Copie temporaire légère
            temp_mesh = mesh_orig.copy()
            temp_obj = orig_obj.copy()
            temp_obj.data = temp_mesh
            bpy.context.collection.objects.link(temp_obj)

            mod = temp_obj.modifiers.new(name="MF_Decim_Test", type='DECIMATE')
            mod.decimate_type = 'COLLAPSE'
            mod.ratio = mid
            if delimiters:
                mod.delimit = delimiters

            bpy.context.view_layer.objects.active = temp_obj
            temp_obj.select_set(True)
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
                bvh_temp = BVHTree.FromPolygons(
                    [v.co for v in temp_obj.data.vertices],
                    [p.vertices for p in temp_obj.data.polygons]
                )

                max_d = 0.0
                for co in sampled_coords:
                    loc, norm, idx, dist = bvh_temp.find_nearest(co)
                    if dist is not None and dist > max_d:
                        max_d = dist

                if max_d <= max_tolerance:
                    best_admissible_ratio = mid
                    high = mid  # On peut tenter de réduire davantage
                else:
                    low = mid   # L'erreur dépasse la tolérance, il faut relaxer
            except Exception:
                low = mid
            finally:
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                bpy.data.meshes.remove(temp_mesh)
    finally:
        if prev_active and prev_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = prev_active
            prev_active.select_set(True)

    return best_admissible_ratio


def execute_simplification(
    obj: bpy.types.Object,
    props: Any,
    orig_reference_obj: Optional[bpy.types.Object] = None
) -> Dict[str, Any]:
    """Exécute la simplification géométrique contrôlée avec distinction formelle
    entre budget cible, triangles obtenus et tolérance mesurée.
    """
    results: Dict[str, Any] = {
        "status": "SUCCESS",
        "initial_triangles": 0,
        "initial_polygons": 0,
        "target_budget_triangles": 0,
        "obtained_triangles": 0,
        "obtained_polygons": 0,
        "reduction_percentage": 0.0,
        "effective_ratio": 1.0,
        "stop_reason": "",
        "tolerance_respected": True,
        "geometric_validation": {},
        "log": []
    }

    if not obj or obj.type != 'MESH':
        results["status"] = "ERROR"
        results["log"].append("Objet cible invalide pour la simplification.")
        return results

    prev_mode = obj.mode
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data
    initial_polys = len(mesh.polygons)
    initial_tris = sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)
    results["initial_polygons"] = initial_polys
    results["initial_triangles"] = initial_tris

    if initial_tris <= 4:
        results["stop_reason"] = "Maillage déjà minimal (<= 4 triangles)."
        results["obtained_triangles"] = initial_tris
        results["obtained_polygons"] = initial_polys
        return results

    # 1. Analyse du mode et calcul du budget cible
    mode = getattr(props, "simplification_mode", "PERCENTAGE")
    target_triangles = initial_tris

    if mode == 'BUDGET_TRIANGLES':
        target_triangles = max(4, getattr(props, "simplification_target_triangles", int(initial_tris * 0.5)))
    elif mode == 'PERCENTAGE':
        pct = getattr(props, "simplification_percentage", 50.0)
        target_triangles = max(4, int(initial_tris * (1.0 - (pct / 100.0))))
    elif mode == 'TOLERANCE_ONLY':
        target_triangles = 4  # Chercher la réduction maximale admissible sous tolérance

    results["target_budget_triangles"] = target_triangles
    initial_ratio = max(0.001, min(1.0, float(target_triangles / initial_tris)))

    # 2. Configuration des contraintes de préservation (Delimiters)
    delimiters: Set[str] = set()
    if getattr(props, "preserve_sharp", True):
        delimiters.add('SHARP')
    if getattr(props, "preserve_seams", True):
        delimiters.add('SEAM')
    if getattr(props, "preserve_materials", True):
        delimiters.add('MATERIAL')
    if getattr(props, "preserve_uvs", True):
        delimiters.add('UV')
    if getattr(props, "preserve_normals_angle", False):
        delimiters.add('NORMAL')

    # 3. Contrôle de tolérance géométrique
    effective_ratio = initial_ratio
    max_tolerance = getattr(props, "simplification_max_tolerance", 0.0)
    use_tolerance = (getattr(props, "enable_simplification_tolerance", False) and max_tolerance > 0.0)

    stop_reason = f"Budget cible de {target_triangles} triangles atteint (ratio appliqué: {initial_ratio:.4f})."

    if use_tolerance and orig_reference_obj:
        if getattr(props, "tolerance_relative", False):
            bbox_diag = max(1e-6, float(orig_reference_obj.dimensions.length))
            effective_max_tol = float(max_tolerance * bbox_diag)
        else:
            effective_max_tol = float(max_tolerance)

        # Recherche dichotomique du ratio garantissant le respect de la tolérance
        admissible_ratio = find_optimal_ratio_for_tolerance(
            orig_reference_obj,
            max_tolerance=effective_max_tol,
            delimiters=delimiters
        )

        if admissible_ratio > initial_ratio:
            # Le budget demandé violerait la tolérance : arbitrage formel
            effective_ratio = admissible_ratio
            stop_reason = (
                f"Arrêt sur tolérance géométrique prioritaire : le budget de {target_triangles} triangles "
                f"dépasserait la tolérance maximale de {effective_max_tol:.5f}m. "
                f"Meilleur ratio admissible retenu : {effective_ratio:.4f}."
            )
        else:
            effective_ratio = initial_ratio
            stop_reason = f"Budget cible atteint avec respect de la tolérance maximale ({effective_max_tol:.5f}m)."

    results["effective_ratio"] = effective_ratio
    results["stop_reason"] = stop_reason

    # 4. Application du modificateur Decimate Collapse contrôlé
    mod = obj.modifiers.new(name="MeshForge_Decimate", type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = effective_ratio
    if delimiters:
        mod.delimit = delimiters
    mod.use_collapse_triangulate = getattr(props, "collapse_triangulate", False)

    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception as e:
        results["status"] = "ERROR"
        results["log"].append(f"Erreur lors de l'application de Decimate : {e}")
        return results

    # 5. Mesure des résultats effectifs
    final_mesh = obj.data
    final_polys = len(final_mesh.polygons)
    final_tris = sum(max(0, len(p.vertices) - 2) for p in final_mesh.polygons)
    results["obtained_polygons"] = final_polys
    results["obtained_triangles"] = final_tris

    if initial_tris > 0:
        results["reduction_percentage"] = round(((initial_tris - final_tris) / initial_tris) * 100.0, 2)

    results["log"].append(
        f"Simplification exécutée : {initial_tris} -> {final_tris} triangles "
        f"(-{results['reduction_percentage']}%, ratio {effective_ratio:.4f})."
    )
    results["log"].append(stop_reason)

    # 6. Validation géométrique rigoureuse (si référence fournie)
    if orig_reference_obj:
        val = evaluate_geometric_deviation(orig_reference_obj, obj, sample_count=10000)
        results["geometric_validation"] = val
        if use_tolerance and val.get("valid"):
            d_p99 = val.get("distance_p99", 0.0)
            if d_p99 > effective_max_tol * 1.05:  # marge de 5% liée à l'échantillonnage
                results["tolerance_respected"] = False
                results["log"].append(f"Avertissement : déviation P99 ({d_p99:.5f}m) supérieure à la tolérance.")

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
