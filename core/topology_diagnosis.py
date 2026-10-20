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
    micro_edge_threshold: float = 0.0001
) -> Dict[str, Any]:
    """Exécute un diagnostic topologique complet en lecture seule.
    Retourne les statistiques objectives et une liste de défauts catégorisés
    avec code couleur sémantique (Orange, Bleu, Rouge, Violet).
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {"valid": False, "error": "Objet sélectionné invalide."}

    mesh = obj.data
    mesh.calc_loop_triangles()
    real_triangles = len(mesh.loop_triangles) if hasattr(mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

    # Calcul de la boîte englobante locale
    v_coords = np.array([v.co for v in mesh.vertices], dtype=np.float64)
    if len(v_coords) == 0:
        return {
            "valid": True,
            "object_name": obj.name,
            "real_triangles": 0,
            "defects": [],
            "summary": {"ngons": 0, "triangles": 0, "degeneracies": 0, "isolated": 0}
        }

    local_min = np.min(v_coords, axis=0)
    local_max = np.max(v_coords, axis=0)
    span = local_max - local_min
    bbox_diag = max(1e-6, float(np.linalg.norm(span)))
    effective_micro_edge = max(1e-6, bbox_diag * micro_edge_threshold)

    # Analyse en lecture seule sur BMesh temporaire
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    defects: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # 1. Catégorie ORANGE : N-gones (Faces à plus de 4 sommets)
    # -------------------------------------------------------------
    ngon_count = 0
    concave_ngon_count = 0
    for f in bm.faces:
        v_count = len(f.verts)
        if v_count > 4:
            ngon_count += 1
            # Vérifier si le n-gone est concave (angle rentrant supérieur à 180°)
            f_norm = f.normal
            is_concave = False
            if v_count >= 5:
                # Test d'angle rentrant (> 180°) invariant à l'échelle via produit vectoriel normalisé
                for i in range(v_count):
                    p0 = f.verts[i - 1].co
                    p1 = f.verts[i].co
                    p2 = f.verts[(i + 1) % v_count].co
                    v_in = p1 - p0
                    v_out = p2 - p1
                    len_in = v_in.length
                    len_out = v_out.length
                    if len_in > 1e-7 and len_out > 1e-7:
                        cross = v_in.cross(v_out)
                        sin_theta = cross.dot(f_norm) / (len_in * len_out)
                        if sin_theta < -1e-4:
                            is_concave = True
                            concave_ngon_count += 1
                            break

            risk_desc = (
                "N-gone concave (angle rentrant supérieur à 180°) : la triangulation automatique par simple éventail risque de produire des triangles se chevauchant ou mal orientés."
                if is_concave else
                f"Face à {v_count} sommets convexes. Risque d'artefacts d'ombrage ou de tension lors de la déformation ou de la subdivision Catmull-Clark."
            )
            defects.append({
                "id": f"ngon_{f.index}",
                "type": "NGON",
                "category": "ORANGE",
                "name": f"N-gone ({v_count} côtés{' - Concave' if is_concave else ''})",
                "severity": "WARNING" if is_concave or mode == 'DEFORMABLE_QUADS' else "INFO",
                "element_type": "FACE",
                "indices": [f.index],
                "center": tuple(f.calc_center_bounds()),
                "explanation": (
                    "Une face possède plus de 4 côtés. " + risk_desc
                ),
                "recommendation": "Découper la face pour former des quads réguliers (K ou Ctrl+T puis J)."
            })

    # -------------------------------------------------------------
    # 2. Catégorie BLEU : Triangles à examiner
    # -------------------------------------------------------------
    tri_count = 0
    suspect_triangles = 0
    for f in bm.faces:
        if len(f.verts) == 3:
            tri_count += 1
            # En mode DEFORMABLE_QUADS, un triangle au milieu de quads interrompt les edge-loops
            # On vérifie si les faces adjacentes sont majoritairement des quads
            neighbor_quads = sum(1 for e in f.edges for nf in e.link_faces if nf != f and len(nf.verts) == 4)
            is_isolated_tri_in_quads = (neighbor_quads >= 2)

            if mode == 'DEFORMABLE_QUADS':
                if is_isolated_tri_in_quads:
                    suspect_triangles += 1
                    defects.append({
                        "id": f"tri_{f.index}",
                        "type": "TRIANGLE_SUSPECT",
                        "category": "BLUE",
                        "name": "Triangle en zone déformable",
                        "severity": "WARNING",
                        "element_type": "FACE",
                        "indices": [f.index],
                        "center": tuple(f.calc_center_bounds()),
                        "explanation": (
                            "Ce triangle est entouré de quadrilatères. Il interrompt le flux régulier "
                            "des boucles d'arêtes (Edge Loops), risquant de créer des plis rigides à l'animation."
                        ),
                        "recommendation": "Fusionner avec un triangle adjacent (Alt+J) ou rediriger les arêtes."
                    })
            elif mode in ('HYBRID_CLEANUP', 'GAME_TRIANGLES'):
                # En hybride ou jeu, on signale les triangles très étirés (forme aiguille / needle)
                edge_lens = [e.calc_length() for e in f.edges]
                max_l = max(edge_lens) if edge_lens else 1.0
                min_l = min(edge_lens) if edge_lens else 1.0
                aspect = max_l / max(1e-7, min_l)
                if aspect > THRESHOLD_SPECS["needle_aspect_ratio"]["threshold"]:
                    suspect_triangles += 1
                    defects.append({
                        "id": f"tri_{f.index}",
                        "type": "TRIANGLE_NEEDLE",
                        "category": "BLUE",
                        "name": f"Triangle très étiré (Ratio {aspect:.1f}:1)",
                        "severity": "INFO",
                        "element_type": "FACE",
                        "indices": [f.index],
                        "center": tuple(f.calc_center_bounds()),
                        "explanation": (
                            f"Triangle extrêmement fin et allongé (rapport de côtés {aspect:.1f}:1 supérieur au seuil de 8:1). "
                            "Susceptible de générer des artefacts de dégradé d'ombrage et des instabilités de rastérisation."
                        ),
                        "recommendation": "Réorganiser les arêtes pour équilibrer la géométrie."
                    })

    # -------------------------------------------------------------
    # 3. Catégorie ROUGE : Géométrie dégénérée & Non-Manifold
    # -------------------------------------------------------------
    degenerate_count = 0

    # 3.1 Faces d'aire nulle
    for f in bm.faces:
        area = f.calc_area()
        if area <= 1e-7:
            degenerate_count += 1
            defects.append({
                "id": f"zero_face_{f.index}",
                "type": "ZERO_AREA_FACE",
                "category": "RED",
                "name": "Face d'aire nulle (Dégénérée)",
                "severity": "ERROR",
                "element_type": "FACE",
                "indices": [f.index],
                "center": tuple(f.calc_center_bounds()),
                "explanation": "Face plate ou repliée sans surface mesurable. Provoque des divisions par zéro et des erreurs de rendu.",
                "recommendation": "Supprimer ou dissoudre cette face."
            })

    # 3.2 Arêtes minuscules
    for e in bm.edges:
        length = e.calc_length()
        if length <= effective_micro_edge and not e.is_boundary:
            degenerate_count += 1
            midpoint = (e.verts[0].co + e.verts[1].co) * 0.5
            defects.append({
                "id": f"micro_edge_{e.index}",
                "type": "MICRO_EDGE",
                "category": "RED",
                "name": f"Arête minuscule ({length*1000:.3f} mm)",
                "severity": "WARNING",
                "element_type": "EDGE",
                "indices": [e.index],
                "face_indices": [f.index for f in e.link_faces],
                "center": tuple(midpoint),
                "explanation": (
                    f"Arête exceptionnellement courte par rapport à l'échelle de l'objet (seuil {effective_micro_edge*1000:.3f} mm). "
                    "Souvent issue d'une extrusion involontaire ou d'un booléen imprécis."
                ),
                "recommendation": "Fusionner les deux sommets si cela ne détruit pas un chanfrein intentionnel."
            })

    # 3.3 Arêtes et sommets non-manifold (hors frontières ouvertes légitimes)
    for e in bm.edges:
        if not e.is_manifold and not e.is_boundary:
            degenerate_count += 1
            midpoint = (e.verts[0].co + e.verts[1].co) * 0.5
            link_count = len(e.link_faces)
            defects.append({
                "id": f"non_manifold_e_{e.index}",
                "type": "NON_MANIFOLD_EDGE",
                "category": "RED",
                "name": f"Arête non-manifold ({link_count} faces connectées)",
                "severity": "ERROR",
                "element_type": "EDGE",
                "indices": [e.index],
                "face_indices": [f.index for f in e.link_faces],
                "center": tuple(midpoint),
                "explanation": (
                    f"Cette arête est partagée par {link_count} faces (au lieu de 2 maximum pour une surface solide). "
                    "Elle forme une paroi intérieure ou une jonction en T interdite sur un asset 3D propre."
                ),
                "recommendation": "Supprimer la face intérieure surnuméraire ou scinder les surfaces."
            })

    # 3.4 Pôles problématiques (Valence >= 6 sur maillage déformable)
    complex_pole_count = 0
    for v in bm.verts:
        val = len(v.link_edges)
        if mode == 'DEFORMABLE_QUADS' and val >= 6 and not v.is_boundary:
            complex_pole_count += 1
            degenerate_count += 1
            defects.append({
                "id": f"pole_{v.index}",
                "type": "COMPLEX_POLE",
                "category": "RED",
                "name": f"Pôle complexe (Valence {val})",
                "severity": "WARNING",
                "element_type": "VERT",
                "indices": [v.index],
                "face_indices": [f.index for f in v.link_faces],
                "center": tuple(v.co),
                "explanation": (
                    f"Ce sommet relie {val} arêtes. Les pôles à haute valence créent des tensions visibles, "
                    "des artefacts d'ombrage en étoile et des déformations chaotiques au rigging."
                ),
                "recommendation": "Rediriger les arêtes pour dissocier ce pôle en pôles de valence 4 ou 5."
            })

    # -------------------------------------------------------------
    # 4. Catégorie VIOLET : Éléments isolés & Morceaux flottants
    # -------------------------------------------------------------
    isolated_count = 0

    # 4.1 Sommets et arêtes isolés (Loose)
    loose_verts = [v.index for v in bm.verts if not v.link_edges]
    if loose_verts:
        isolated_count += len(loose_verts)
        center_loose = tuple(bm.verts[loose_verts[0]].co)
        defects.append({
            "id": "loose_verts_group",
            "type": "LOOSE_VERTS",
            "category": "VIOLET",
            "name": f"{len(loose_verts)} Sommet(s) orphelin(s) non connecté(s)",
            "severity": "WARNING",
            "element_type": "VERT",
            "indices": loose_verts[:50],
            "center": center_loose,
            "explanation": "Sommets flottant dans l'espace sans arête ni face associée.",
            "recommendation": "Supprimer les sommets orphelins (Delete Loose)."
        })

    loose_edges = [e.index for e in bm.edges if not e.link_faces]
    if loose_edges:
        isolated_count += len(loose_edges)
        e0 = bm.edges[loose_edges[0]]
        mid_e = tuple((e0.verts[0].co + e0.verts[1].co) * 0.5)
        defects.append({
            "id": "loose_edges_group",
            "type": "LOOSE_EDGES",
            "category": "VIOLET",
            "name": f"{len(loose_edges)} Arête(s) filaire(s) sans face",
            "severity": "WARNING",
            "element_type": "EDGE",
            "indices": loose_edges[:50],
            "center": mid_e,
            "explanation": "Arêtes filaires isolées ne délimitant aucune face polygonale.",
            "recommendation": "Supprimer les arêtes sans face."
        })

    # 4.2 Composantes connexes disjointes (Fragments / Îlots)
    disjoint_components = []
    unvisited_faces = set(bm.faces)
    while unvisited_faces:
        root = unvisited_faces.pop()
        island = [root]
        queue = [root]
        while queue:
            curr = queue.pop()
            for e in curr.edges:
                for n_face in e.link_faces:
                    if n_face in unvisited_faces:
                        unvisited_faces.remove(n_face)
                        island.append(n_face)
                        queue.append(n_face)
        disjoint_components.append(island)

    comp_count = len(disjoint_components)
    if comp_count > 1:
        # Trier par taille de composante (nombre de faces)
        disjoint_components.sort(key=len, reverse=True)
        # Signaler les composantes mineures (petits fragments < 5% du nombre de faces du composant dominant)
        main_comp_size = len(disjoint_components[0])
        min_cutoff = max(
            THRESHOLD_SPECS["minor_component_ratio"]["min_faces"],
            int(main_comp_size * THRESHOLD_SPECS["minor_component_ratio"]["threshold"])
        )
        for idx_comp, comp in enumerate(disjoint_components[1:], start=2):
            if len(comp) < min_cutoff:
                isolated_count += 1
                ratio_pct = (len(comp) / max(1, main_comp_size)) * 100.0
                c_center = tuple(np.mean([f.calc_center_bounds() for f in comp], axis=0))
                defects.append({
                    "id": f"isolated_component_{idx_comp}",
                    "type": "ISOLATED_COMPONENT",
                    "category": "VIOLET",
                    "name": f"Petit composant séparé #{idx_comp} ({len(comp)} faces)",
                    "severity": "INFO",
                    "element_type": "FACE",
                    "indices": [f.index for f in comp],
                    "center": c_center,
                    "explanation": (
                        f"Ce morceau est physiquement disjoint du composant principal ({len(comp)} faces contre {main_comp_size}, soit {ratio_pct:.1f}%). "
                        "Il peut s'agir d'un boulon ou accessoire intentionnel, ou d'un débris de modélisation oublié."
                    ),
                    "recommendation": "Vérifier si cet élément fait partie du modèle ou doit être supprimé."
                })

    # -------------------------------------------------------------
    # 5. Inventaire objectif des valences de sommets
    # -------------------------------------------------------------
    valences = [len(v.link_edges) for v in bm.verts]
    valence_stats = {
        "poles_3_n": sum(1 for val in valences if val == 3),
        "regular_4": sum(1 for val in valences if val == 4),
        "poles_5_e": sum(1 for val in valences if val == 5),
        "poles_6_plus": sum(1 for val in valences if val >= 6)
    }

    bm.free()

    summary = {
        "ngons": ngon_count,
        "concave_ngons": concave_ngon_count,
        "triangles": tri_count,
        "suspect_triangles": suspect_triangles,
        "degeneracies": degenerate_count,
        "complex_poles": complex_pole_count,
        "isolated": isolated_count,
        "disjoint_components_total": comp_count
    }

    return {
        "valid": True,
        "object_name": obj.name,
        "target_mode": mode,
        "bounding_box_diagonal": round(bbox_diag, 5),
        "real_triangles": real_triangles,
        "total_faces": len(mesh.polygons),
        "total_vertices": len(mesh.vertices),
        "valence_stats": valence_stats,
        "summary": summary,
        "defects": defects
    }
