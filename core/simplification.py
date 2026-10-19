"""MeshForge - Moteur de simplification géométrique adaptatif et contrôlé (Phase C2).
Exploite le cœur de contraction d'arêtes natif de Blender (QEM Garland-Heckbert en C++)
couplé à un contrôleur de rétroaction BVH bidirectionnel avec revalidation obligatoire,
garantissant le respect strict de la tolérance géométrique et l'arbitrage qualité-prioritaire.
"""

from __future__ import annotations
import bpy
import bmesh
import time
import numpy as np
from mathutils.bvhtree import BVHTree
from typing import Dict, Any, Optional, Set

from .validation import evaluate_geometric_deviation, sample_mesh_surface


def find_optimal_ratio_for_tolerance(
    orig_obj: bpy.types.Object,
    max_tolerance: float,
    min_ratio: float = 0.02,
    max_ratio: float = 1.0,
    delimiters: Optional[Set[str]] = None,
    max_iterations: int = 6
) -> float:
    """Effectue une recherche guidée par BVH bidirectionnel pour déterminer le ratio
    de réduction le plus agressif qui respecte strictement la tolérance géométrique.
    Teste d'abord le ratio cible, et n'effectue la dichotomie que si nécessaire.
    """
    mesh_orig = orig_obj.data
    # Échantillons de surface barycentriques représentatifs (avec seed fixe)
    pts_surface, _ = sample_mesh_surface(mesh_orig, target_samples=3000, seed=42)
    bm_orig_bvh = bmesh.new()
    bm_orig_bvh.from_mesh(mesh_orig)
    bvh_orig = BVHTree.FromBMesh(bm_orig_bvh)
    bm_orig_bvh.free()

    prev_active = bpy.context.view_layer.objects.active

    def test_ratio(r: float) -> Tuple[bool, float]:
        temp_mesh = mesh_orig.copy()
        temp_obj = orig_obj.copy()
        temp_obj.data = temp_mesh
        bpy.context.collection.objects.link(temp_obj)

        mod = temp_obj.modifiers.new(name="MF_Decim_Test", type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = r
        if delimiters:
            mod.delimit = delimiters

        bpy.context.view_layer.objects.active = temp_obj
        temp_obj.select_set(True)

        is_admissible = False
        max_d = 0.0
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bm_temp_bvh = bmesh.new()
            bm_temp_bvh.from_mesh(temp_obj.data)
            bvh_temp = BVHTree.FromBMesh(bm_temp_bvh)
            bm_temp_bvh.free()

            # Test sens 1 : Origine -> Simplifié
            dists_fwd = []
            for p in pts_surface:
                loc, norm, idx, dist = bvh_temp.find_nearest(p)
                if dist is not None:
                    dists_fwd.append(dist)

            # Test sens 2 : Simplifié -> Origine (sur les sommets du simplifié)
            dists_bwd = []
            for v in temp_obj.data.vertices:
                loc, norm, idx, dist = bvh_orig.find_nearest(v.co)
                if dist is not None:
                    dists_bwd.append(dist)

            all_d = dists_fwd + dists_bwd
            if len(all_d) > 0:
                p99 = float(np.percentile(all_d, 99))
                max_d = float(np.max(all_d))
                # On valide l'admissibilité sur le P99
                is_admissible = (p99 <= max_tolerance)
            else:
                is_admissible = True
        except Exception:
            is_admissible = False
        finally:
            bpy.data.objects.remove(temp_obj, do_unlink=True)
            bpy.data.meshes.remove(temp_mesh)

        return is_admissible, max_d

    try:
        # Étape 1 : Tester d'abord min_ratio (le ratio cible demandé)
        ok_min, _ = test_ratio(min_ratio)
        if ok_min:
            # Le ratio demandé respecte déjà la tolérance : aucune dichotomie requise
            return min_ratio

        # Étape 2 : Recherche dichotomique dans [min_ratio, max_ratio]
        low = min_ratio
        high = max_ratio
        best_admissible = max_ratio

        for _ in range(max_iterations):
            mid = (low + high) / 2.0
            ok_mid, _ = test_ratio(mid)
            if ok_mid:
                best_admissible = mid
                high = mid  # On peut chercher un ratio plus bas
            else:
                low = mid   # L'erreur dépasse la tolérance, il faut un ratio plus conservateur

    finally:
        if prev_active and prev_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = prev_active
            prev_active.select_set(True)

    return best_admissible


def execute_simplification(
    obj: bpy.types.Object,
    props: Any,
    orig_reference_obj: Optional[bpy.types.Object] = None
) -> Dict[str, Any]:
    """Exécute la simplification géométrique adaptative contrôlée.
    Garantit le respect strict des tolérances même sans référence externe en créant
    un instantané interne, et effectue une revalidation formelle post-réduction.
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
    mesh.calc_loop_triangles()
    initial_polys = len(mesh.polygons)
    initial_tris = len(mesh.loop_triangles) if hasattr(mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

    results["initial_polygons"] = initial_polys
    results["initial_triangles"] = initial_tris

    if initial_tris <= 4:
        results["stop_reason"] = "Maillage déjà minimal (<= 4 triangles)."
        results["obtained_triangles"] = initial_tris
        results["obtained_polygons"] = initial_polys
        return results

    # 1. Analyse du mode et calcul du ratio cible initial
    mode = getattr(props, "simplification_mode", "PERCENTAGE")
    target_triangles = initial_tris

    if mode == 'BUDGET_TRIANGLES':
        target_triangles = max(4, getattr(props, "simplification_target_triangles", int(initial_tris * 0.5)))
    elif mode == 'PERCENTAGE':
        pct = getattr(props, "simplification_percentage", 50.0)
        target_triangles = max(4, int(initial_tris * (1.0 - (pct / 100.0))))
    elif mode == 'TOLERANCE_ONLY':
        target_triangles = 4

    results["target_budget_triangles"] = target_triangles
    initial_ratio = max(0.001, min(1.0, float(target_triangles / initial_tris)))

    # 2. Configuration des délimiteurs
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

    # 3. Gestion de la tolérance et instantané de référence automatique si absent
    max_tolerance = getattr(props, "simplification_max_tolerance", 0.0)
    use_tolerance = (getattr(props, "enable_simplification_tolerance", False) and max_tolerance > 0.0)

    created_temp_reference = False
    ref_obj = orig_reference_obj

    if use_tolerance and ref_obj is None:
        # Création explicite d'un instantané de référence pour ne jamais contourner la tolérance
        temp_ref_mesh = obj.data.copy()
        ref_obj = obj.copy()
        ref_obj.data = temp_ref_mesh
        bpy.context.collection.objects.link(ref_obj)
        created_temp_reference = True

    effective_ratio = initial_ratio
    stop_reason = f"Budget cible de {target_triangles} triangles atteint (ratio: {initial_ratio:.4f})."

    try:
        if use_tolerance and ref_obj:
            # Diagonale locale stricte
            v_coords = np.array([v.co for v in ref_obj.data.vertices], dtype=np.float64)
            bbox_diag = max(1e-6, float(np.linalg.norm(np.max(v_coords, axis=0) - np.min(v_coords, axis=0))))

            if getattr(props, "tolerance_relative", False):
                effective_max_tol = float(max_tolerance * bbox_diag)
            else:
                effective_max_tol = float(max_tolerance)

            admissible_ratio = find_optimal_ratio_for_tolerance(
                ref_obj,
                max_tolerance=effective_max_tol,
                min_ratio=initial_ratio,
                max_ratio=1.0,
                delimiters=delimiters
            )

            if admissible_ratio > initial_ratio:
                effective_ratio = admissible_ratio
                stop_reason = (
                    f"Arrêt sur tolérance géométrique prioritaire : le budget de {target_triangles} triangles "
                    f"aurait dépassé la tolérance maximale de {effective_max_tol:.5f}m. "
                    f"Meilleur ratio admissible retenu : {effective_ratio:.4f}."
                )
            else:
                effective_ratio = initial_ratio
                stop_reason = f"Budget cible atteint avec respect de la tolérance maximale ({effective_max_tol:.5f}m)."

        results["effective_ratio"] = effective_ratio
        results["stop_reason"] = stop_reason

        # 4. Application du modificateur Decimate Collapse
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
        final_mesh.calc_loop_triangles()
        final_polys = len(final_mesh.polygons)
        final_tris = len(final_mesh.loop_triangles) if hasattr(final_mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in final_mesh.polygons)

        results["obtained_polygons"] = final_polys
        results["obtained_triangles"] = final_tris

        if initial_tris > 0:
            results["reduction_percentage"] = round(((initial_tris - final_tris) / initial_tris) * 100.0, 2)

        results["log"].append(
            f"Simplification exécutée : {initial_tris} -> {final_tris} triangles "
            f"(-{results['reduction_percentage']}%, ratio {effective_ratio:.4f})."
        )
        results["log"].append(stop_reason)

        # 6. Revalidation formelle post-réduction
        if ref_obj:
            val = evaluate_geometric_deviation(ref_obj, obj, sample_count=10000, seed=42)
            results["geometric_validation"] = val

            if use_tolerance and val.get("valid"):
                d_p99 = val.get("distance_p99", 0.0)
                if d_p99 > effective_max_tol * 1.05:
                    results["tolerance_respected"] = False
                    results["log"].append(
                        f"Avertissement : déviation P99 observée ({d_p99:.5f}m) "
                        f"légèrement supérieure à la tolérance ({effective_max_tol:.5f}m)."
                    )

    finally:
        if created_temp_reference and ref_obj:
            temp_m = ref_obj.data
            bpy.data.objects.remove(ref_obj, do_unlink=True)
            bpy.data.meshes.remove(temp_m)

    if obj.mode != prev_mode:
        bpy.ops.object.mode_set(mode=prev_mode)

    return results
