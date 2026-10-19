"""MeshForge - Module de génération et d'export de rapports (Section 8 du CdC & Phase B).
Génère des rapports structurés au format JSON et Texte, distinguant formellement
les problèmes détectés des problèmes effectivement corrigés.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any


def format_report_as_text(report: Dict[str, Any]) -> str:
    """Produit une version textuelle claire et détaillée du rapport d'exécution."""
    lines = []
    lines.append("=" * 60)
    lines.append("RAPPORT D'OPTIMISATION MESHFORGE")
    lines.append("=" * 60)

    lines.append(f"Objet source     : {report.get('original_name', 'N/A')}")
    lines.append(f"Objet résultat   : {report.get('result_name', 'N/A')}")
    lines.append(f"Statut           : {'SUCCÈS' if report.get('success') else 'ÉCHEC'}")
    lines.append(f"Durée totale     : {report.get('total_duration', 0.0):.4f} s")
    lines.append(f"Réduction estim. : {report.get('reduction_percentage', 0.0):.2f} %")
    lines.append("")

    lines.append("-" * 60)
    lines.append("1. MÉTRIQUES GÉOMÉTRIQUES (AVANT / APRÈS)")
    lines.append("-" * 60)
    s_init = report.get("initial_stats", {})
    s_final = report.get("final_stats", {})

    lines.append(f"  Sommets            : {s_init.get('vertices', 0)} -> {s_final.get('vertices', 0)}")
    lines.append(f"  Arêtes             : {s_init.get('edges', 0)} -> {s_final.get('edges', 0)}")
    lines.append(f"  Faces (Polygones)  : {s_init.get('faces', 0)} -> {s_final.get('faces', 0)}")
    lines.append(f"  Triangles estimés  : {s_init.get('estimated_triangles', 0)} -> {s_final.get('estimated_triangles', 0)}")
    lines.append(f"  Triangles réels    : {s_init.get('tri_faces', 0)} -> {s_final.get('tri_faces', 0)}")
    lines.append(f"  Quads              : {s_init.get('quad_faces', 0)} -> {s_final.get('quad_faces', 0)}")
    lines.append(f"  N-gons             : {s_init.get('ngon_faces', 0)} -> {s_final.get('ngon_faces', 0)}")
    lines.append(f"  Composantes isolées: {s_init.get('disjoint_components', 0)} -> {s_final.get('disjoint_components', 0)}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("2. PROBLÈMES DÉTECTÉS VS CORRIGÉS (PHASE B)")
    lines.append("-" * 60)
    det = report.get("issues_detected", {})
    res = report.get("issues_resolved", {})

    lines.append(f"  Sommets isolés (Loose V)  : Détectés = {det.get('loose_verts', 0):<5} | Corrigés = {res.get('loose_verts_removed', 0)}")
    lines.append(f"  Arêtes isolées (Loose E)  : Détectées = {det.get('loose_edges', 0):<5} | Corrigées = {res.get('loose_edges_removed', 0)}")
    lines.append(f"  Doublons potentiels       : Détectés = {det.get('potential_duplicates', 0):<5} | Fusionnés = {res.get('doubles_merged', 0)}")
    lines.append(f"  Faces dégénérées / nulles : Détectées = {det.get('zero_area_faces', 0):<5} | Dissoutes = {res.get('zero_faces_dissolved', 0)}")
    lines.append(f"  Arêtes filaires (Wire)    : Détectées = {det.get('wire_edges', 0):<5} | Supprimées = {res.get('wire_edges_removed', 0)}")
    lines.append(f"  Slots matériaux inutilisés: Détectés = {det.get('unused_material_slots', 0):<5} | Retirés   = {res.get('unused_slots_removed', 0)}")
    lines.append(f"  Groupes sommets vides     : Détectés = {det.get('empty_vertex_groups', 0):<5} | Retirés   = {res.get('empty_vg_removed', 0)}")
    lines.append(f"  Arêtes non-manifold       : Détectées = {det.get('non_manifold_edges', 0):<5} | (Action prudente: conservées/nettoyées)")
    lines.append(f"  Ouvertures / Trous        : Détectées = {det.get('boundary_loops_count', 0):<5} | (Surface ouverte: {'Oui' if det.get('is_open_surface') else 'Non'})")
    lines.append("")

    lines.append("-" * 60)
    lines.append("3. INVENTAIRE DES ATTRIBUTS CONSERVÉS")
    lines.append("-" * 60)
    lines.append(f"  Couches UV ({s_final.get('uv_layer_count', 0)})        : {s_final.get('uv_layer_names', [])}")
    lines.append(f"  Groupes de sommets ({s_final.get('vertex_group_count', 0)}): {s_final.get('vertex_group_names', [])}")
    lines.append(f"  Matériaux ({s_final.get('material_slot_count', 0)})         : {s_final.get('material_names', [])}")
    lines.append(f"  Arêtes vives (Sharp)     : {s_final.get('sharp_edge_count', 0)}")
    lines.append(f"  Coutures UV (Seams)      : {s_final.get('seam_edge_count', 0)}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("4. DURÉE PAR PHASE D'EXÉCUTION")
    lines.append("-" * 60)
    for phase, duration in report.get("phase_timings", {}).items():
        lines.append(f"  {phase:<24} : {duration:.4f} s")
    lines.append("")

    # Section Validation Géométrique (Phases C & C2)
    val = report.get("geometric_validation")
    if val and val.get("valid"):
        lines.append("-" * 60)
        lines.append("5. VALIDATION GÉOMÉTRIQUE & TOPOLOGIQUE (PHASE C2)")
        lines.append("-" * 60)
        lines.append(f"  Méthode              : {val.get('sample_method')}")
        lines.append(f"  Échantillons (Orig)  : {val.get('sample_count_orig')}")
        lines.append(f"  Échantillons (Simp)  : {val.get('sample_count_simp')}")
        lines.append(f"  Diagonale bbox locale: {val.get('bounding_box_diagonal', 0.0):.6f} m")

        # Distances séparées
        fwd = val.get("distance_forward", {})
        bwd = val.get("distance_backward", {})
        if fwd and bwd:
            lines.append(f"  Distance Directe (Orig->Simp)  : Moy={fwd.get('mean', 0.0):.6f} m | P95={fwd.get('p95', 0.0):.6f} m | Max={fwd.get('max', 0.0):.6f} m")
            lines.append(f"  Distance Inverse (Simp->Orig)  : Moy={bwd.get('mean', 0.0):.6f} m | P95={bwd.get('p95', 0.0):.6f} m | Max={bwd.get('max', 0.0):.6f} m")
            lines.append(f"  Distance Hausdorff bidirect.   : {val.get('distance_hausdorff', 0.0):.6f} m")
        else:
            lines.append(f"  Distance moyenne     : {val.get('distance_mean'):.6f} m")
            lines.append(f"  Distance P95         : {val.get('distance_p95'):.6f} m")
            lines.append(f"  Distance P99         : {val.get('distance_p99'):.6f} m")

        lines.append(f"  Distance max observée: {val.get('distance_max_observed'):.6f} m ({val.get('distance_max_relative', 0.0)*100:.3f}% de la bbox)")
        lines.append(f"  Déviation normale moy: {val.get('normal_deviation_mean_deg'):.2f}° (P95: {val.get('normal_deviation_p95_deg'):.2f}°, Max: {val.get('normal_deviation_max_deg'):.2f}°)")

        # Silhouette 2D détaillée
        sm = val.get("silhouette_metrics", {})
        if sm:
            for plane in ['XY', 'XZ', 'YZ']:
                p_data = sm.get(plane, {})
                lines.append(
                    f"  Silhouette {plane:<2} (IoU / Delta / Contour) : "
                    f"IoU={p_data.get('iou', 0.0):.4f} (Div {p_data.get('divergence_pct', 0.0):.1f}%) | "
                    f"Aire \u0394={p_data.get('area_delta_pct', 0.0):.2f}% | "
                    f"Contour Dist Moy={p_data.get('contour_distance_mean_m', 0.0):.5f}m (Max {p_data.get('contour_distance_max_m', 0.0):.5f}m)"
                )
        else:
            lines.append(f"  Écart silhouette (%) : {val.get('silhouette_deviation_pct')}")

        if val.get('volume_delta_pct') is not None:
            lines.append(f"  Variation de volume  : {val.get('volume_delta_pct'):.3f} % (Maillage fermé vérifié bilatéralement)")
        else:
            lines.append("  Variation de volume  : N/A (Surface ouverte ou non-manifold)")

        lines.append(f"  Arêtes Sharp (Av/Ap) : {val.get('sharp_edges_before')} -> {val.get('sharp_edges_after')} (Note: fusion d'arêtes Decimate)")
        lines.append(f"  Coutures UV (Av/Ap)  : {val.get('seams_before')} -> {val.get('seams_after')}")
        lines.append(f"  Matériaux (Av/Ap)    : {val.get('materials_before')} -> {val.get('materials_after')}")
        lines.append(f"  Note d'approximation : {val.get('approximation_note')}")
        lines.append("")

    if report.get("warnings"):
        lines.append("-" * 60)
        lines.append("AVERTISSEMENTS :")
        lines.append("-" * 60)
        for w in report["warnings"]:
            lines.append(f"  [!] {w}")
        lines.append("")

    if report.get("errors"):
        lines.append("-" * 60)
        lines.append("ERREURS :")
        lines.append("-" * 60)
        for err in report["errors"]:
            lines.append(f"  [X] {err}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def export_report_to_file(report: Dict[str, Any], filepath: str, format_type: str = 'JSON') -> str:
    """Exporte le rapport sur disque au format JSON ou Texte."""
    path = Path(filepath).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if format_type.upper() == 'JSON':
        # Assurer la sérialisation des structures
        serializable_data = {
            "original_name": report.get("original_name"),
            "result_name": report.get("result_name"),
            "success": report.get("success"),
            "total_duration_sec": report.get("total_duration"),
            "reduction_percentage": report.get("reduction_percentage"),
            "initial_stats": report.get("initial_stats"),
            "final_stats": report.get("final_stats"),
            "issues_detected": report.get("issues_detected"),
            "issues_resolved": report.get("issues_resolved"),
            "phase_timings": report.get("phase_timings"),
            "applied_parameters": report.get("applied_parameters"),
            "simplification_details": report.get("simplification_details"),
            "geometric_validation": report.get("geometric_validation"),
            "warnings": report.get("warnings"),
            "errors": report.get("errors"),
            "logs": report.get("logs")
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
    else:
        text_content = format_report_as_text(report)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text_content)

    return str(path)
