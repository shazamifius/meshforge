"""MeshForge - Module de diagnostic topologique non-destructif en lecture seule (Phase D1).
Analyse rigoureusement les maillages selon les trois modes d'usage (Triangles, Quads, Hybride).
Distingue formellement les propriétés topologiques objectives (valences, connectivité)
des heuristiques de qualité selon l'usage visé (déformation vs rigide).
Aucune modification géométrique n'est effectuée sur l'objet analysé.
"""

from __future__ import annotations
import bpy
import bmesh
import math
import numpy as np
from typing import Dict, Any, List, Set, Tuple, Optional


# ---------------------------------------------------------------------------
# Spécifications documentées des seuils diagnostiques
# ---------------------------------------------------------------------------
THRESHOLD_SPECS = {
    "micro_edge": {
        "factor": 1e-4,  # 0.01% de la diagonale de la boîte englobante locale
        "floor_meters": 1e-6,  # 1 micromètre minimum absolu
        "unit": "ratio relatif / mètres",
        "justification": (
            "Sur un modèle de taille humaine (2 m), 1e-4 correspond à 0.2 mm. "
            "Les arêtes inférieures à cette longueur résultent quasi-systématiquement "
            "d'extrusions involontaires, de doubles sommets non fusionnés ou d'imprécisions booléennes."
        )
    },
    "zero_area_face": {
        "threshold_sq_meters": 1e-7,  # 0.1 mm²
        "unit": "mètres carrés",
        "justification": (
            "Seuil numérique en deçà duquel l'aire polygonale est considérée dégénérée, "
            "provoquant des divisions par zéro lors du calcul des normales et du rendu."
        )
    },
    "needle_aspect_ratio": {
        "threshold": 8.0,  # ratio arête_max / arête_min
        "unit": "ratio sans dimension",
        "justification": (
            "Un triangle effilé avec un rapport supérieur à 8:1 génère de sévères "
            "artefacts de dégradé d'ombrage spéculaire et dégrade le conditionnement de simulation."
        )
    },
    "minor_component_ratio": {
        "threshold": 0.05,  # moins de 5% du nombre de faces du composant dominant
        "min_faces": 10,
        "unit": "pourcentage relatif",
        "justification": (
            "Distingue un composant mécanique intentionnel (ex: 4 roues représentant chacune 20% des faces) "
            "d'un résidu flottant ou débris oublié suite à une découpe booléenne."
        )
    },
    "complex_pole_valence": {
        "threshold": 6,  # 6 arêtes ou plus connectées à un sommet non-frontière
        "unit": "degré de connectivité (nombre d'arêtes)",
        "justification": (
            "Les pôles de valence >= 6 en géométrie quad interrompent les boucles d'arêtes "
            "et créent des plis en étoile non maîtrisables lors des déformations d'armature (rigging)."
        )
    }
}


def diagnose_topology(
    obj: bpy.types.Object,
    mode: str = 'HYBRID_CLEANUP',
    micro_edge_threshold: float = 0.0001,
    strict_manifold: bool = False,
    quads_only: bool = False
) -> Dict[str, Any]:
    """Exécute un diagnostic topologique complet en lecture seule.
    Retourne les statistiques objectives et une liste de défauts catégorisés
    avec code couleur sémantique (Orange, Bleu, Rouge, Violet).
    Optimisé pour les maillages multi-millions de sommets (un seul BMesh, zéro redondance).
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {"valid": False, "error": "Objet sélectionné invalide."}

    if obj.mode != 'OBJECT' or getattr(obj.data, "is_editmode", False):
        return {"valid": False, "error": "L'objet est en mode Édition. Veuillez repasser en mode Objet (Touche Tab) pour exécuter l'analyse."}

    from .structured_diagnosis import measure_mesh_facts, evaluate_structured_diagnosis

    facts = measure_mesh_facts(obj, custom_micro_edge=micro_edge_threshold)
    if not facts.get("valid", False):
        return {"valid": False, "error": facts.get("error", "Erreur lors de la mesure du maillage.")}

    if facts.get("is_empty", False):
        return {
            "valid": True,
            "object_name": obj.name,
            "real_triangles": 0,
            "defects": [],
            "summary": {"ngons": 0, "concave_ngons": 0, "triangles": 0, "suspect_triangles": 0, "degeneracies": 0, "complex_poles": 0, "isolated": 0, "disjoint_components_total": 0},
            "valence_stats": {"poles_3_n": 0, "regular_4": 0, "poles_5_e": 0, "poles_6_plus": 0},
            "bounding_box_diagonal": 0.0,
            "total_faces": 0,
            "total_vertices": 0,
            "facts": facts,
            "structured": evaluate_structured_diagnosis(facts, mode, strict_manifold, quads_only),
            "findings": [],
            "recommended_actions": []
        }

    # Résumé D1 pour compatibilité complète
    suspect_tris = facts["tris_count"] if mode == 'DEFORMABLE_QUADS' else facts["needle_triangles_count"]
    complex_poles = facts["poles_valence_6_plus_count"] if mode == 'DEFORMABLE_QUADS' else 0
    degeneracies = (
        facts["zero_area_faces_count"] +
        facts["micro_edges_count"] +
        facts["non_manifold_edges_count"] +
        complex_poles
    )
    isolated = facts["loose_verts_count"] + facts["wire_edges_count"] + facts["minor_components_count"]

    summary = {
        "ngons": facts["total_ngons"],
        "concave_ngons": facts["ngons_concave_count"],
        "triangles": facts["tris_count"],
        "suspect_triangles": suspect_tris,
        "degeneracies": degeneracies,
        "complex_poles": complex_poles,
        "isolated": isolated,
        "disjoint_components_total": facts["components_count"]
    }

    # Liste des défauts D1
    defects = list(facts.get("legacy_defects", []))
    # Si mode == DEFORMABLE_QUADS, ajouter les pôles complexes aux défauts si présents
    if mode == 'DEFORMABLE_QUADS' and facts["poles_valence_6_plus_count"] > 0:
        c_p6 = facts.get("poles_6_plus_center", (0.0, 0.0, 0.0))
        for v_idx in facts.get("poles_6_plus_indices", [])[:30]:
            defects.append({
                "id": f"pole_{v_idx}",
                "type": "COMPLEX_POLE",
                "category": "RED",
                "name": "Pôle complexe (Valence >= 6)",
                "severity": "WARNING",
                "element_type": "VERT",
                "indices": [v_idx],
                "center": c_p6,
                "explanation": "Sommet connectant 6 arêtes ou plus en maillage quad déformable.",
                "recommendation": "Rediriger les arêtes pour scinder ce pôle."
            })
    # Si mode == DEFORMABLE_QUADS et triangles présents, ajouter les triangles suspects en BLEU
    if mode == 'DEFORMABLE_QUADS' and facts["tris_count"] > 0:
        for f_idx in facts.get("tris_indices", [])[:30]:
            defects.append({
                "id": f"tri_{f_idx}",
                "type": "TRIANGLE_SUSPECT",
                "category": "BLUE",
                "name": "Triangle en zone déformable",
                "severity": "WARNING",
                "element_type": "FACE",
                "indices": [f_idx],
                "center": (0.0, 0.0, 0.0),
                "explanation": "Ce triangle interrompt le flux régulier des boucles d'arêtes.",
                "recommendation": "Fusionner avec un triangle adjacent (Alt+J)."
            })

    structured = evaluate_structured_diagnosis(facts, mode, strict_manifold=strict_manifold, quads_only=quads_only)

    return {
        "valid": True,
        "object_name": obj.name,
        "target_mode": mode,
        "bounding_box_diagonal": round(facts["bbox_diameter"], 5),
        "real_triangles": facts["real_triangles"],
        "total_faces": facts["polygon_count"],
        "total_vertices": facts["vertex_count"],
        "valence_stats": facts["valence_stats"],
        "summary": summary,
        "defects": defects,
        "facts": facts,
        "structured": structured,
        "findings": structured.get("findings", []),
        "recommended_actions": structured.get("recommended_actions", [])
    }
