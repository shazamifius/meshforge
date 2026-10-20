"""MeshForge - Modèle de diagnostic structuré et moteur de recommandation contextuel (UX2, UX3, UX4).
Sépare formellement :
1. Les faits mesurés (MeshFacts) : mesures géométriques et topologiques objectives indépendantes de l'objectif.
2. Les profils d'usage (ProfileRules) : interprétation contextuelle des faits selon l'usage visé :
   - GENERAL : Diagnostic général — « Je ne sais pas » (Neutre, seuls les défauts avérés sont signalés)
   - GAME_ASSET : Asset de jeu (Triangles, budget, silhouette, UVs)
   - DEFORMABLE_CHAR : Personnage déformable (Quads, boucles, pôles, déformation)
   - SCULPTED_ORGANIC : Modèle sculpté ou organique (Préservation de courbure, pas de décimation agressive)
   - MECHANICAL_CAD : Objet mécanique ou assemblage (Plans, chanfreins, parois internes)
3. Les constats structurés (DiagnosticFinding) :
   - Sévérité justifiée : DEFECT (défaut avéré), RISK (risque potentiel), OBSERVATION (simple mesure)
   - Catégorie normalisée (Géométrie, Topologie, Silhouette, UV/Matériaux, Normales, Densité, Déformation, Export)
   - Éléments sélectionnables et cadrables dans Blender (index, coordonnées 3D de centre)
   - Actions compatibles et motifs éventuels de refus
"""

from __future__ import annotations
import bpy
import bmesh
import math
import numpy as np
from typing import Dict, Any, List, Set, Tuple, Optional


# ---------------------------------------------------------------------------
# Catégories standardisées du diagnostic (Phase UX3)
# ---------------------------------------------------------------------------
CATEGORIES = {
    "GEOMETRY": {
        "id": "GEOMETRY",
        "name": "Géométrie & Dégénérescences",
        "icon": 'ERROR',
        "description": "Faces nulles, sommets orphelins, arêtes minuscules et intégrité numérique."
    },
    "TOPOLOGY": {
        "id": "TOPOLOGY",
        "name": "Topologie & Connectivité",
        "icon": 'MESH_DATA',
        "description": "N-gones, non-manifold, arêtes filaires, parois internes et composantes disjointes."
    },
    "SURFACE": {
        "id": "SURFACE",
        "name": "Silhouette & Qualité de surface",
        "icon": 'OUTLINER_OB_MESH',
        "description": "Triangles très étirés (aiguilles), planéité et courbure locale."
    },
    "UV_MATERIAL": {
        "id": "UV_MATERIAL",
        "name": "UV & Matériaux",
        "icon": 'UV',
        "description": "Coutures UV, discontinuités de texture et slots de matériaux."
    },
    "NORMALS": {
        "id": "NORMALS",
        "name": "Normales & Ombrage",
        "icon": 'NORMALS_FACE',
        "description": "Normales personnalisées (split normals), arêtes vives et lissage."
    },
    "DENSITY": {
        "id": "DENSITY",
        "name": "Densité polygonale & Statistiques",
        "icon": 'MOD_DECIM',
        "description": "Nombre de faces, ratio triangles/quads et budget de polygones."
    },
    "DEFORMATION": {
        "id": "DEFORMATION",
        "name": "Préparation à la déformation",
        "icon": 'OUTLINER_OB_ARMATURE',
        "description": "Boucles de quads pour l'animation, pôles complexes (valence >= 6) et rigging."
    },
    "EXPORT": {
        "id": "EXPORT",
        "name": "Préparation à l'export",
        "icon": 'EXPORT',
        "description": "Conformité pour moteurs de jeu et logiciels tiers (fermeture, manifold)."
    }
}

# ---------------------------------------------------------------------------
# Profils d'usage prédéfinis (Phase UX4)
# ---------------------------------------------------------------------------
PROFILES = {
    "GENERAL": {
        "id": "GENERAL",
        "name": "Diagnostic général — « Je ne sais pas »",
        "icon": 'HELP',
        "summary": "Analyse factuelle neutre. Seuls les défauts avérés sont signalés.",
        "description": (
            "Idéal si vous ne savez pas encore à quoi servira l'asset. "
            "Les N-gones ou triangles ne sont pas considérés comme des erreurs. "
            "Seuls les problèmes géométriques réels (faces nulles, éléments orphelins) sont signalés."
        )
    },
    "GAME_ASSET": {
        "id": "GAME_ASSET",
        "name": "Jeu vidéo & Temps réel",
        "icon": 'PLAY',
        "summary": "Moteur temps réel (Unity, Unreal, Godot). Triangles, budget et UVs.",
        "description": (
            "Priorité à la performance temps réel : absence totale de N-gones (découpe recommandée), "
            "budget de triangles maîtrisé, coordonnées UV rigoureusement préservées et zéro face nulle."
        )
    },
    "RENDER_ANIM": {
        "id": "RENDER_ANIM",
        "name": "Rendu & Animation",
        "icon": 'RESTRICT_RENDER_OFF',
        "summary": "Rendu haute qualité et subdivision propre. Quads réguliers prioritaires.",
        "description": (
            "Priorité à la qualité de subdivision et au lissage d'ombrage. "
            "Réduction des pôles complexes, élimination des plis et harmonisation des boucles de quads."
        )
    },
    "DEFORMABLE_CHAR": {
        "id": "DEFORMABLE_CHAR",
        "name": "Personnage déformable (Rigging)",
        "icon": 'OUTLINER_OB_ARMATURE',
        "summary": "Animation et rigging. Topologie en quadrilatères réguliers et boucles d'arêtes.",
        "description": (
            "Priorité à la déformation : géométrie pure quads, alignement des edge loops aux articulations, "
            "alerte sur les N-gones et triangles coupant les boucles, et surveillance des pôles à haute valence."
        )
    },
    "EXPORT_PREP": {
        "id": "EXPORT_PREP",
        "name": "Préparation export & Impression 3D",
        "icon": 'EXPORT',
        "summary": "Étanchéité manifold absolue, zéro paroi interne occluse, normales unifiées.",
        "description": (
            "Priorité à la fermeture volumique étanche (watertight). Élimination impérative de tout élément "
            "non-manifold, des trous involontaires, des parois internes et orientation uniforme vers l'extérieur."
        )
    },
    "MECHANICAL_CAD": {
        "id": "MECHANICAL_CAD",
        "name": "Objet mécanique ou CAO",
        "icon": 'TOOL_SETTINGS',
        "summary": "Pièces industrielles et hard-surface. Arêtes vives, faces planes et pièces multiples.",
        "description": (
            "Priorité aux cotes et surfaces planes : les N-gones plans réguliers sont acceptés. "
            "Élimination stricte des micro-arêtes booléennes, des parois internes et des doublons."
        )
    },
    "SCULPTED_ORGANIC": {
        "id": "SCULPTED_ORGANIC",
        "name": "Modèle sculpté ou organique",
        "icon": 'BRUSH_DATA',
        "summary": "Sculpt haute densité. Préservation de courbure, zéro décimation destructive.",
        "description": (
            "Priorité à la fidélité de surface : une forte densité polygonale est tout à fait normale. "
            "Aucune décimation agressive n'est recommandée par défaut pour éviter les balafres et ombres noires."
        )
    },
    "CUSTOM": {
        "id": "CUSTOM",
        "name": "Autre usage / Objectif personnalisé",
        "icon": 'PROPERTIES',
        "summary": "Diagnostic sur-mesure ajusté via les contraintes complémentaires.",
        "description": (
            "Analyse ouverte permettant de moduler les exigences topologiques à l'aide des contraintes complémentaires."
        )
    }
}

# Compatibilité descendante pour les anciens identifiants
PROFILE_ALIAS = {
    "HYBRID_CLEANUP": "GENERAL",
    "GAME_TRIANGLES": "GAME_ASSET",
    "DEFORMABLE_QUADS": "DEFORMABLE_CHAR",
    "3D_PRINTING": "EXPORT_PREP",
    "PRINT_3D": "EXPORT_PREP",
    "ANIMATION": "RENDER_ANIM",
}


class DiagnosticFinding:
    """Représentation structurée d'un constat géométrique ou topologique."""

    def __init__(
        self,
        finding_id: str,
        category: str,
        name: str,
        severity: str,  # 'DEFECT', 'RISK', 'OBSERVATION'
        count: int = 1,
        metric_value: Optional[float] = None,
        metric_unit: str = "",
        element_type: str = 'FACE',  # 'FACE', 'EDGE', 'VERT', 'OBJECT'
        indices: Optional[List[int]] = None,
        face_indices: Optional[List[int]] = None,
        center: Optional[Tuple[float, float, float]] = None,
        explanation: str = "",
        consequence: str = "",
        recommendation: str = "",
        compatible_action: Optional[str] = None,
        action_name: str = "",
        action_risk: str = "Risque Faible",
        relevant_profiles: Optional[List[str]] = None,
        refusal_reason: Optional[str] = None,
        manual_correction_steps: str = "",
        is_intentional: bool = False
    ):
        self.id = finding_id
        self.category = category
        self.name = name
        self.severity = severity
        self.count = count
        self.metric_value = metric_value
        self.metric_unit = metric_unit
        self.element_type = element_type
        self.indices = indices or []
        self.face_indices = face_indices or []
        self.center = center or (0.0, 0.0, 0.0)
        self.explanation = explanation
        self.consequence = consequence
        self.recommendation = recommendation
        self.compatible_action = compatible_action
        self.action_name = action_name
        self.action_risk = action_risk
        self.relevant_profiles = relevant_profiles or ["GENERAL", "GAME_ASSET", "DEFORMABLE_CHAR", "SCULPTED_ORGANIC", "MECHANICAL_CAD"]
        self.refusal_reason = refusal_reason
        self.manual_correction_steps = manual_correction_steps
        self.is_intentional = is_intentional

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "severity": self.severity,
            "count": self.count,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "element_type": self.element_type,
            "indices": self.indices,
            "face_indices": self.face_indices,
            "center": self.center,
            "explanation": self.explanation,
            "consequence": self.consequence,
            "recommendation": self.recommendation,
            "compatible_action": self.compatible_action,
            "action_name": self.action_name,
            "action_risk": self.action_risk,
            "relevant_profiles": self.relevant_profiles,
            "refusal_reason": self.refusal_reason,
            "manual_correction_steps": self.manual_correction_steps,
            "is_intentional": self.is_intentional
        }


def measure_mesh_facts(obj: bpy.types.Object, custom_micro_edge: Optional[float] = None) -> Dict[str, Any]:
    """Mesure objectivement et exhaustivement toutes les caractéristiques géométriques et topologiques
    du maillage, de façon 100% neutre et indépendante du profil utilisateur choisi.
    Ces faits sont calculés une seule fois et mis en cache.
    Optimisé pour les maillages de plusieurs millions de sommets (un seul BMesh, zéro redondance).
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {"valid": False, "error": "Objet invalide ou non-maillage."}

    mesh = obj.data
    mesh.calc_loop_triangles()
    real_triangles = len(mesh.loop_triangles) if hasattr(mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

    v_count = len(mesh.vertices)
    if v_count == 0:
        return {
            "valid": True,
            "is_empty": True,
            "object_name": obj.name,
            "vertex_count": 0,
            "edge_count": 0,
            "polygon_count": 0,
            "real_triangles": 0,
            "bbox_span": (0.0, 0.0, 0.0),
            "bbox_diameter": 0.0,
            "micro_edge_threshold": 0.0001,
            "intentional_finding_ids": [],
            "legacy_summary": {
                "ngons": 0, "concave_ngons": 0, "triangles": 0,
                "suspect_triangles": 0, "degeneracies": 0, "complex_poles": 0,
                "isolated": 0, "disjoint_components_total": 0
            },
            "legacy_defects": []
        }

    # Bbox instantanée via obj.bound_box (évite v.co en Python sur des millions de sommets)
    bb = obj.bound_box
    min_c = [min(bb[i][j] for i in range(8)) for j in range(3)]
    max_c = [max(bb[i][j] for i in range(8)) for j in range(3)]
    span = (max_c[0] - min_c[0], max_c[1] - min_c[1], max_c[2] - min_c[2])
    bbox_diameter = max(1e-6, float(math.sqrt(span[0]**2 + span[1]**2 + span[2]**2)))
    micro_edge_threshold = custom_micro_edge if custom_micro_edge is not None else max(1e-6, bbox_diameter * 1e-4)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 1. Analyse des faces par valence et géométrie
    tris = []
    quads = []
    ngons_convex = []
    ngons_concave = []
    ngons_ambiguous = []
    zero_area_faces = []
    needle_triangles = []

    for f in bm.faces:
        area = f.calc_area()
        if area <= 1e-7:
            zero_area_faces.append(f)
            continue

        nv = len(f.verts)
        if nv == 3:
            tris.append(f)
            edge_lens = [e.calc_length() for e in f.edges]
            max_l = max(edge_lens) if edge_lens else 1.0
            min_l = min(edge_lens) if edge_lens else 1.0
            aspect = max_l / max(1e-7, min_l)
            if aspect > 8.0:
                needle_triangles.append((f, aspect))
        elif nv == 4:
            quads.append(f)
        else:
            # Classification géométrique fine du N-gone
            try:
                from .ngon_cutter import classify_ngon
                diag_ng = classify_ngon(f)
                cat = diag_ng.get("category", "CONVEX")
            except Exception:
                cat = "CONVEX"

            if cat == 'AMBIGUOUS':
                ngons_ambiguous.append(f)
            elif cat == 'CONCAVE':
                ngons_concave.append(f)
            else:
                ngons_convex.append(f)

    # 2. Analyse des arêtes & capture seam/sharp
    wire_edges = []
    boundary_edges = []
    non_manifold_edges = []
    micro_edges = []
    has_seams = False
    has_sharp = False

    for e in bm.edges:
        if e.seam:
            has_seams = True
        if not e.smooth:
            has_sharp = True

        lf_len = len(e.link_faces)
        if lf_len == 0:
            wire_edges.append(e)
        elif lf_len == 1:
            boundary_edges.append(e)
        elif lf_len > 2:
            non_manifold_edges.append(e)

        if e.calc_length() <= micro_edge_threshold and not e.is_boundary:
            micro_edges.append(e)

    # 2.c Partition des arêtes de frontière en boucles connexes (Boundary Loops)
    boundary_loops = []
    if boundary_edges:
        vert_to_b_edges: Dict[bmesh.types.BMVert, List[bmesh.types.BMEdge]] = {}
        for be in boundary_edges:
            for bv in be.verts:
                vert_to_b_edges.setdefault(bv, []).append(be)

        remaining_edges = set(boundary_edges)
        loop_id = 0
        while remaining_edges:
            seed = remaining_edges.pop()
            comp = [seed]
            queue = [seed]
            while queue:
                curr = queue.pop()
                for bv in curr.verts:
                    for neighbor_e in vert_to_b_edges.get(bv, []):
                        if neighbor_e in remaining_edges:
                            remaining_edges.remove(neighbor_e)
                            comp.append(neighbor_e)
                            queue.append(neighbor_e)

            c_verts = set()
            for ce in comp:
                c_verts.update(ce.verts)
            c_center = tuple(np.mean([v.co for v in c_verts], axis=0)) if c_verts else (0.0, 0.0, 0.0)
            boundary_loops.append({
                "item_id": str(loop_id),
                "loop_id": loop_id,
                "edge_count": len(comp),
                "edge_indices": [ce.index for ce in comp],
                "indices": [ce.index for ce in comp],
                "vert_count": len(c_verts),
                "vert_indices": [cv.index for cv in c_verts],
                "center": c_center,
                "element_type": "EDGE"
            })
            loop_id += 1

    # 2.b Analyse des parois internes et jonctions en T si non-manifold présent
    strict_internal_faces = []
    t_junction_faces = []
    complex_junction_faces = []
    strict_wall_center = (0.0, 0.0, 0.0)
    if non_manifold_edges:
        try:
            from .internal_walls import classify_non_manifold_faces
            wall_diag = classify_non_manifold_faces(bm)
            strict_internal_faces = wall_diag.get("strict_internal_faces", [])
            t_junction_faces = wall_diag.get("t_junction_faces", [])
            complex_junction_faces = wall_diag.get("complex_junction_faces", [])
            strict_wall_center = wall_diag.get("strict_wall_center", (0.0, 0.0, 0.0))
        except Exception:
            pass

    # 3. Analyse des sommets et valences
    loose_verts = []
    poles_3_n = 0
    regular_4 = 0
    poles_5_e = 0
    poles_6_plus = []

    for v in bm.verts:
        val = len(v.link_edges)
        if val == 0:
            loose_verts.append(v)
        elif not v.is_boundary:
            if val == 3:
                poles_3_n += 1
            elif val == 4:
                regular_4 += 1
            elif val == 5:
                poles_5_e += 1
            elif val >= 6:
                poles_6_plus.append(v)

    # 4. Analyse des composantes connexes (BFS unique)
    components = []
    unvisited = set(bm.faces)
    while unvisited:
        start = unvisited.pop()
        comp = [start]
        queue = [start]
        while queue:
            curr = queue.pop()
            for edge in curr.edges:
                for linked in edge.link_faces:
                    if linked in unvisited:
                        unvisited.remove(linked)
                        comp.append(linked)
                        queue.append(linked)
        components.append(comp)

    minor_components_count = 0
    minor_components = []
    if len(components) > 1:
        components.sort(key=len, reverse=True)
        main_comp_size = len(components[0])
        min_cutoff = max(10, int(main_comp_size * 0.05))
        for comp in components[1:]:
            if len(comp) < min_cutoff:
                minor_components_count += 1
                minor_components.append(comp)

    # 5. Attributs externes
    uv_layer_names = [l.name for l in mesh.uv_layers]
    material_names = [m.name for m in mesh.materials if m]
    vertex_group_names = [vg.name for vg in obj.vertex_groups]
    has_custom_normals = bool(mesh.has_custom_normals)

    # 5.b Construction des listes d'items granulaires pour chaque anomalie
    tri_items = [{
        "item_id": str(f.index),
        "index": f.index,
        "element_type": "FACE",
        "indices": [f.index],
        "center": tuple(f.calc_center_bounds())
    } for f in tris]

    ngon_concave_items = [{
        "item_id": str(f.index),
        "index": f.index,
        "element_type": "FACE",
        "indices": [f.index],
        "center": tuple(f.calc_center_bounds()),
        "verts_count": len(f.verts)
    } for f in ngons_concave]

    ngon_convex_items = [{
        "item_id": str(f.index),
        "index": f.index,
        "element_type": "FACE",
        "indices": [f.index],
        "center": tuple(f.calc_center_bounds()),
        "verts_count": len(f.verts)
    } for f in ngons_convex]

    ngon_ambiguous_items = [{
        "item_id": str(f.index),
        "index": f.index,
        "element_type": "FACE",
        "indices": [f.index],
        "center": tuple(f.calc_center_bounds()),
        "verts_count": len(f.verts)
    } for f in ngons_ambiguous]

    zero_area_items = [{
        "item_id": str(f.index),
        "index": f.index,
        "element_type": "FACE",
        "indices": [f.index],
        "center": tuple(f.calc_center_bounds())
    } for f in zero_area_faces]

    micro_edge_items = [{
        "item_id": str(e.index),
        "index": e.index,
        "element_type": "EDGE",
        "indices": [e.index],
        "face_indices": [f.index for f in e.link_faces],
        "center": tuple((e.verts[0].co + e.verts[1].co) * 0.5),
        "length": e.calc_length()
    } for e in micro_edges]

    wire_edge_items = [{
        "item_id": str(e.index),
        "index": e.index,
        "element_type": "EDGE",
        "indices": [e.index],
        "center": tuple((e.verts[0].co + e.verts[1].co) * 0.5)
    } for e in wire_edges]

    loose_vert_items = [{
        "item_id": str(v.index),
        "index": v.index,
        "element_type": "VERT",
        "indices": [v.index],
        "center": tuple(v.co)
    } for v in loose_verts]

    pole_items = [{
        "item_id": str(v.index),
        "index": v.index,
        "element_type": "VERT",
        "indices": [v.index],
        "center": tuple(v.co),
        "valence": len(v.link_edges)
    } for v in poles_6_plus]

    needle_triangle_items = [{
        "item_id": str(f.index),
        "index": f.index,
        "element_type": "FACE",
        "indices": [f.index],
        "center": tuple(f.calc_center_bounds()),
        "aspect": asp
    } for f, asp in needle_triangles]

    internal_wall_items = []
    if strict_internal_faces:
        remaining_iw = set(strict_internal_faces)
        iw_id = 0
        while remaining_iw:
            seed = remaining_iw.pop()
            comp = [seed]
            queue = [seed]
            while queue:
                curr_idx = queue.pop()
                if curr_idx < len(bm.faces):
                    curr_f = bm.faces[curr_idx]
                    for e in curr_f.edges:
                        for lf in e.link_faces:
                            if lf.index in remaining_iw:
                                remaining_iw.remove(lf.index)
                                comp.append(lf.index)
                                queue.append(lf.index)
            c_center = tuple(np.mean([bm.faces[fi].calc_center_bounds() for fi in comp if fi < len(bm.faces)], axis=0)) if comp else strict_wall_center
            internal_wall_items.append({
                "item_id": str(iw_id),
                "index": iw_id,
                "element_type": "FACE",
                "indices": comp,
                "face_count": len(comp),
                "center": tuple(float(c) for c in c_center)
            })
            iw_id += 1

    t_junction_items = []
    if t_junction_faces:
        remaining_tj = set(t_junction_faces)
        tj_id = 0
        while remaining_tj:
            seed = remaining_tj.pop()
            comp = [seed]
            queue = [seed]
            while queue:
                curr_idx = queue.pop()
                if curr_idx < len(bm.faces):
                    curr_f = bm.faces[curr_idx]
                    for e in curr_f.edges:
                        for lf in e.link_faces:
                            if lf.index in remaining_tj:
                                remaining_tj.remove(lf.index)
                                comp.append(lf.index)
                                queue.append(lf.index)
            c_center = tuple(np.mean([bm.faces[fi].calc_center_bounds() for fi in comp if fi < len(bm.faces)], axis=0)) if comp else (0.0, 0.0, 0.0)
            t_junction_items.append({
                "item_id": str(tj_id),
                "index": tj_id,
                "element_type": "FACE",
                "indices": comp,
                "face_count": len(comp),
                "center": tuple(float(c) for c in c_center)
            })
            tj_id += 1

    non_manifold_items = [{
        "item_id": str(e.index),
        "index": e.index,
        "element_type": "EDGE",
        "indices": [e.index],
        "face_indices": [f.index for f in e.link_faces],
        "center": tuple(float(c) for c in (e.verts[0].co + e.verts[1].co) * 0.5),
        "link_faces": len(e.link_faces)
    } for e in non_manifold_edges]

    category_items_map = {
        "topo_ngons_concave": ngon_concave_items,
        "topo_ngons_convex": ngon_convex_items,
        "topo_ngons_ambiguous": ngon_ambiguous_items,
        "geom_zero_area_faces": zero_area_items,
        "geom_micro_edges": micro_edge_items,
        "topo_wire_edges": wire_edge_items,
        "geom_loose_verts": loose_vert_items,
        "deform_high_valence_poles": pole_items,
        "surface_needle_triangles": needle_triangle_items,
        "topo_internal_walls": internal_wall_items,
        "topo_t_junctions": t_junction_items,
        "topo_non_manifold": non_manifold_items,
        "topo_open_boundary": boundary_loops,
        "deform_tris_in_quads": tri_items
    }

    # 6. Intentional findings marqués sur l'objet et purge des validations périmées (P0)
    import json
    intentional_ids = list(obj.get("_mf_intentional_findings", [])) if hasattr(obj, "get") else []
    raw_reg = obj.get("_mf_intentional_registry", "{}") if hasattr(obj, "get") else "{}"
    if isinstance(raw_reg, str):
        try:
            registry = json.loads(raw_reg)
        except Exception:
            registry = {}
    elif isinstance(raw_reg, dict):
        registry = dict(raw_reg)
    else:
        registry = {}

    pruned_validations = []
    valid_intentional_ids = []
    updated_registry = dict(registry)

    for k in intentional_ids:
        if ":" in k:
            base_id, item_id = k.split(":", 1)
        else:
            base_id, item_id = k, None

        items = category_items_map.get(base_id)
        is_still_valid = False

        if items is not None:
            if item_id is not None:
                # Chercher l'item spécifique par item_id
                matching = [it for it in items if str(it.get("item_id")) == str(item_id)]
                if matching:
                    it = matching[0]
                    reg_entry = registry.get(k)
                    if reg_entry:
                        reg_center = reg_entry.get("center")
                        curr_center = it.get("center")
                        if reg_center and curr_center:
                            dist = math.sqrt(sum((float(a) - float(b))**2 for a, b in zip(reg_center, curr_center)))
                            if dist < 0.1:
                                is_still_valid = True
                            else:
                                is_still_valid = False  # Recréation ou déplacement
                        else:
                            is_still_valid = True
                    else:
                        is_still_valid = True
            else:
                # Clé globale sans suffixe (ex: topo_open_boundary) : valide s'il n'y a qu'1 seul item
                if len(items) == 1:
                    is_still_valid = True

        if is_still_valid:
            valid_intentional_ids.append(k)
        else:
            pruned_validations.append({
                "key": k,
                "reason": "Élément supprimé, modifié ou anomalie résolue"
            })
            updated_registry.pop(k, None)

    # Mise à jour des propriétés personnalisées de l'objet si modification
    if hasattr(obj, "__setitem__"):
        if len(valid_intentional_ids) != len(intentional_ids) or len(updated_registry) != len(registry):
            obj["_mf_intentional_findings"] = valid_intentional_ids
            clean_reg = {}
            for reg_k, reg_v in updated_registry.items():
                clean_reg[reg_k] = {
                    "base_id": str(reg_v.get("base_id", "")),
                    "item_id": str(reg_v.get("item_id", "")) if reg_v.get("item_id") is not None else None,
                    "center": [float(c) for c in reg_v.get("center", (0.0, 0.0, 0.0))],
                    "element_type": str(reg_v.get("element_type", "FACE")),
                    "indices": [int(i) for i in reg_v.get("indices", [])]
                }
            obj["_mf_intentional_registry"] = json.dumps(clean_reg)

    intentional_ids = valid_intentional_ids

    # Construction des centres utiles (protégés)
    c_zero = tuple(zero_area_faces[0].calc_center_bounds()) if zero_area_faces else (0.0, 0.0, 0.0)
    c_wire = tuple((wire_edges[0].verts[0].co + wire_edges[0].verts[1].co) * 0.5) if wire_edges else (0.0, 0.0, 0.0)
    c_nm = tuple((non_manifold_edges[0].verts[0].co + non_manifold_edges[0].verts[1].co) * 0.5) if non_manifold_edges else (0.0, 0.0, 0.0)
    c_micro = tuple((micro_edges[0].verts[0].co + micro_edges[0].verts[1].co) * 0.5) if micro_edges else (0.0, 0.0, 0.0)
    c_loose = tuple(loose_verts[0].co) if loose_verts else (0.0, 0.0, 0.0)
    c_p6 = tuple(poles_6_plus[0].co) if poles_6_plus else (0.0, 0.0, 0.0)
    c_ng_cv = tuple(ngons_convex[0].calc_center_bounds()) if ngons_convex else (0.0, 0.0, 0.0)
    c_ng_cc = tuple(ngons_concave[0].calc_center_bounds()) if ngons_concave else (0.0, 0.0, 0.0)
    c_ng_am = tuple(ngons_ambiguous[0].calc_center_bounds()) if ngons_ambiguous else (0.0, 0.0, 0.0)

    # Construction des legacy_defects pour affichage / inspection
    legacy_defects: List[Dict[str, Any]] = []
    for f in (ngons_concave[:30] + ngons_ambiguous[:30] + ngons_convex[:40]):
        is_cc = (f in ngons_concave)
        risk_desc = (
            "N-gone concave (angle rentrant supérieur à 180°) : la triangulation automatique par simple éventail risque de produire des triangles se chevauchant ou mal orientés."
            if is_cc else
            f"Face à {len(f.verts)} sommets convexes. Risque d'artefacts d'ombrage ou de tension lors de la déformation ou de la subdivision Catmull-Clark."
        )
        legacy_defects.append({
            "id": f"ngon_{f.index}",
            "type": "NGON",
            "category": "ORANGE",
            "name": f"N-gone ({len(f.verts)} côtés{' - Concave' if is_cc else ''})",
            "severity": "WARNING" if is_cc else "INFO",
            "element_type": "FACE",
            "indices": [f.index],
            "center": tuple(f.calc_center_bounds()),
            "explanation": "Une face possède plus de 4 côtés. " + risk_desc,
            "recommendation": "Découper la face pour former des quads réguliers (K ou Ctrl+T puis J)."
        })
    for f in zero_area_faces[:50]:
        legacy_defects.append({
            "id": f"zero_face_{f.index}",
            "type": "ZERO_AREA_FACE",
            "category": "RED",
            "name": "Face d'aire nulle (Dégénérée)",
            "severity": "ERROR",
            "element_type": "FACE",
            "indices": [f.index],
            "center": tuple(f.calc_center_bounds()),
            "explanation": "Face sans surface mesurable.",
            "recommendation": "Supprimer ou dissoudre cette face."
        })
    for e in micro_edges[:50]:
        mid = tuple((e.verts[0].co + e.verts[1].co) * 0.5)
        legacy_defects.append({
            "id": f"micro_edge_{e.index}",
            "type": "MICRO_EDGE",
            "category": "RED",
            "name": f"Arête minuscule ({e.calc_length()*1000:.3f} mm)",
            "severity": "WARNING",
            "element_type": "EDGE",
            "indices": [e.index],
            "face_indices": [f.index for f in e.link_faces],
            "center": mid,
            "explanation": "Arête exceptionnellement courte par rapport à l'échelle de l'objet.",
            "recommendation": "Fusionner les deux sommets."
        })
    for e in non_manifold_edges[:50]:
        mid = tuple((e.verts[0].co + e.verts[1].co) * 0.5)
        legacy_defects.append({
            "id": f"non_manifold_e_{e.index}",
            "type": "NON_MANIFOLD_EDGE",
            "category": "RED",
            "name": f"Arête non-manifold ({len(e.link_faces)} faces connectées)",
            "severity": "ERROR",
            "element_type": "EDGE",
            "indices": [e.index],
            "face_indices": [f.index for f in e.link_faces],
            "center": mid,
            "explanation": f"Arête partagée par {len(e.link_faces)} faces.",
            "recommendation": "Supprimer la face intérieure ou scinder les surfaces."
        })
    for f, asp in needle_triangles[:50]:
        legacy_defects.append({
            "id": f"tri_{f.index}",
            "type": "TRIANGLE_NEEDLE",
            "category": "BLUE",
            "name": f"Triangle très étiré (Ratio {asp:.1f}:1)",
            "severity": "INFO",
            "element_type": "FACE",
            "indices": [f.index],
            "center": tuple(f.calc_center_bounds()),
            "explanation": "Triangle extrêmement fin et allongé.",
            "recommendation": "Réorganiser les arêtes pour équilibrer la géométrie."
        })
    if loose_verts:
        legacy_defects.append({
            "id": "loose_verts_group",
            "type": "LOOSE_VERTS",
            "category": "VIOLET",
            "name": f"{len(loose_verts)} Sommet(s) orphelin(s) non connecté(s)",
            "severity": "WARNING",
            "element_type": "VERT",
            "indices": [v.index for v in loose_verts[:50]],
            "center": c_loose,
            "explanation": "Sommets flottant dans l'espace.",
            "recommendation": "Supprimer les sommets orphelins."
        })
    if wire_edges:
        legacy_defects.append({
            "id": "loose_edges_group",
            "type": "LOOSE_EDGES",
            "category": "VIOLET",
            "name": f"{len(wire_edges)} Arête(s) filaire(s) sans face",
            "severity": "WARNING",
            "element_type": "EDGE",
            "indices": [e.index for e in wire_edges[:50]],
            "center": c_wire,
            "explanation": "Arêtes filaires isolées.",
            "recommendation": "Supprimer les arêtes sans face."
        })
    for idx_comp, comp in enumerate(minor_components[:10], start=2):
        c_center = tuple(np.mean([f.calc_center_bounds() for f in comp], axis=0))
        legacy_defects.append({
            "id": f"isolated_component_{idx_comp}",
            "type": "ISOLATED_COMPONENT",
            "category": "VIOLET",
            "name": f"Petit composant séparé #{idx_comp} ({len(comp)} faces)",
            "severity": "INFO",
            "element_type": "FACE",
            "indices": [f.index for f in comp],
            "center": c_center,
            "explanation": f"Ce morceau est physiquement disjoint du composant principal ({len(comp)} faces).",
            "recommendation": "Vérifier si cet élément fait partie du modèle ou doit être supprimé."
        })

    facts = {
        "valid": True,
        "is_empty": False,
        "object_name": obj.name,
        "vertex_count": v_count,
        "edge_count": len(mesh.edges),
        "polygon_count": len(mesh.polygons),
        "real_triangles": real_triangles,
        "bbox_span": span,
        "bbox_diameter": bbox_diameter,
        "micro_edge_threshold": micro_edge_threshold,
        # Faces
        "tris_count": len(tris),
        "tris_indices": [f.index for f in tris[:50]],
        "quads_count": len(quads),
        "ngons_convex_count": len(ngons_convex),
        "ngons_concave_count": len(ngons_concave),
        "ngons_ambiguous_count": len(ngons_ambiguous),
        "total_ngons": len(ngons_convex) + len(ngons_concave) + len(ngons_ambiguous),
        "zero_area_faces_count": len(zero_area_faces),
        "zero_area_face_indices": [f.index for f in zero_area_faces[:50]],
        "zero_area_face_center": c_zero,
        "needle_triangles_count": len(needle_triangles),
        "needle_triangle_indices": [f.index for f, _ in needle_triangles[:50]],
        "needle_max_aspect": max([asp for _, asp in needle_triangles], default=1.0),
        # N-gones détails
        "ngon_convex_indices": [f.index for f in ngons_convex[:50]],
        "ngon_concave_indices": [f.index for f in ngons_concave[:50]],
        "ngon_ambiguous_indices": [f.index for f in ngons_ambiguous[:50]],
        "ngon_convex_center": c_ng_cv,
        "ngon_concave_center": c_ng_cc,
        "ngon_ambiguous_center": c_ng_am,
        # Arêtes
        "wire_edges_count": len(wire_edges),
        "wire_edge_indices": [e.index for e in wire_edges[:50]],
        "wire_edge_center": c_wire,
        "boundary_edges_count": len(boundary_edges),
        "is_open_mesh": len(boundary_edges) > 0,
        "non_manifold_edges_count": len(non_manifold_edges),
        "non_manifold_edge_indices": [e.index for e in non_manifold_edges[:50]],
        "non_manifold_edge_center": c_nm,
        "internal_walls_count": len(strict_internal_faces),
        "internal_wall_indices": strict_internal_faces,
        "internal_wall_center": strict_wall_center,
        "t_junctions_count": len(t_junction_faces),
        "t_junction_indices": t_junction_faces,
        "complex_junctions_count": len(complex_junction_faces),
        "micro_edges_count": len(micro_edges),
        "micro_edge_indices": [e.index for e in micro_edges[:50]],
        "micro_edge_center": c_micro,
        # Sommets
        "loose_verts_count": len(loose_verts),
        "loose_vert_indices": [v.index for v in loose_verts[:50]],
        "loose_vert_center": c_loose,
        "poles_valence_3_count": poles_3_n,
        "poles_valence_5_count": poles_5_e,
        "poles_valence_6_plus_count": len(poles_6_plus),
        "poles_6_plus_indices": [v.index for v in poles_6_plus[:50]],
        "poles_6_plus_center": c_p6,
        "valence_stats": {
            "poles_3_n": poles_3_n,
            "regular_4": regular_4,
            "poles_5_e": poles_5_e,
            "poles_6_plus": len(poles_6_plus)
        },
        # Composantes
        "components_count": len(components),
        "minor_components_count": minor_components_count,
        # Données
        "uv_layer_count": len(uv_layer_names),
        "uv_layer_names": uv_layer_names,
        "material_slot_count": len(material_names),
        "material_names": material_names,
        "vertex_group_count": len(vertex_group_names),
        "has_custom_normals": has_custom_normals,
        "has_seams": has_seams,
        "has_sharp": has_sharp,
        # Intentional & Validations
        "intentional_finding_ids": intentional_ids,
        "pruned_validations": pruned_validations,
        # Items granulaires
        "boundary_loops": boundary_loops,
        "ngon_concave_items": ngon_concave_items,
        "ngon_convex_items": ngon_convex_items,
        "ngon_ambiguous_items": ngon_ambiguous_items,
        "zero_area_items": zero_area_items,
        "micro_edge_items": micro_edge_items,
        "wire_edge_items": wire_edge_items,
        "loose_vert_items": loose_vert_items,
        "pole_items": pole_items,
        "needle_triangle_items": needle_triangle_items,
        "internal_wall_items": internal_wall_items,
        "t_junction_items": t_junction_items,
        "non_manifold_items": non_manifold_items,
        "tri_items": tri_items,
        "legacy_defects": legacy_defects
    }

    bm.free()
    return facts


def _is_intentional(base_id: str, item_id: str, total_count: int, intentional_ids: List[str]) -> bool:
    """Détermine si une anomalie spécifique est marquée comme intentionnelle.
    Si total_count == 1, accepte base_id ou f"{base_id}:{item_id}".
    Si total_count > 1, n'accepte QUE la clé granulaire ciblée f"{base_id}:{item_id}".
    """
    if f"{base_id}:{item_id}" in intentional_ids:
        return True
    if total_count == 1 and base_id in intentional_ids:
        return True
    return False


def _check_goal_compliance(
    base_id: str,
    default_name: str,
    default_severity: str,
    profile_id: str,
    strict_manifold: bool,
    quads_only: bool,
    base_explanation: str
) -> Tuple[str, str, str]:
    """Évalue la conformité d'une géométrie intentionnelle par rapport aux exigences du profil cible.
    Distingue la géométrie intentionnelle de la conformité à l'objectif :
    - Frontière ouverte ou non-manifold : reste un RISK sous EXPORT_PREP ou strict_manifold (non étanche).
    - N-gone : reste un RISK sous GAME_ASSET ou EXPORT_PREP ou quads_only (incompatible).
    - Triangle : reste un RISK sous quads_only.
    - Sinon : OBSERVATION neutre.
    Retourne (severity, name, explanation).
    """
    # 1. Étanchéité volumique (Impression 3D, export strict)
    if base_id in ("topo_open_boundary", "topo_non_manifold", "topo_internal_walls"):
        if strict_manifold or profile_id == "EXPORT_PREP":
            return (
                "RISK",
                f"[Intentionnel non conforme export] {default_name}",
                f"[Validé comme intentionnel par l'utilisateur mais NON ÉTANCHE pour l'export / impression 3D] {base_explanation} L'impression 3D exige une surface hermétiquement fermée (watertight)."
            )

    # 2. Topologie stricte quads / temps réel (N-gones)
    if base_id in ("topo_ngons_concave", "topo_ngons_convex", "topo_ngons_ambiguous"):
        if quads_only or profile_id in ("GAME_ASSET", "EXPORT_PREP"):
            return (
                "RISK",
                f"[Intentionnel non conforme temps réel/quads] {default_name}",
                f"[Validé comme intentionnel par l'utilisateur mais NON CONFORME à l'objectif {profile_id}] {base_explanation} Les N-gones sont incompatibles avec les contraintes strictes de ce profil."
            )
        if base_id == "topo_ngons_ambiguous":
            return (
                "RISK",
                f"[Intentionnel risqué] {default_name}",
                f"[Validé comme intentionnel par l'utilisateur mais GÉOMÉTRIQUEMENT RISQUÉ] {base_explanation} Risque de faces inversées ou d'artefacts d'ombrage."
            )

    # 3. Triangles en topologie quads
    if base_id == "deform_tris_in_quads":
        if quads_only:
            return (
                "RISK",
                f"[Intentionnel non conforme quads] {default_name}",
                f"[Validé intentionnel par l'utilisateur mais NON CONFORME 100% quads] {base_explanation}"
            )

    # 4. Conforme / Accepté dans ce profil
    return (
        "OBSERVATION",
        f"[Intentionnel] {default_name}",
        f"[Validé comme géométrie intentionnelle par l'utilisateur] {base_explanation}"
    )


def _get_category_items(facts: Dict[str, Any], base_id: str) -> List[Dict[str, Any]]:
    """Retourne la liste des items géométriques individuels pour un type d'anomalie."""
    mapping = {
        "topo_ngons_concave": facts.get("ngon_concave_items", []),
        "topo_ngons_convex": facts.get("ngon_convex_items", []),
        "topo_ngons_ambiguous": facts.get("ngon_ambiguous_items", []),
        "geom_zero_area_faces": facts.get("zero_area_items", []),
        "geom_micro_edges": facts.get("micro_edge_items", []),
        "topo_wire_edges": facts.get("wire_edge_items", []),
        "geom_loose_verts": facts.get("loose_vert_items", []),
        "deform_high_valence_poles": facts.get("pole_items", []),
        "surface_needle_triangles": facts.get("needle_triangle_items", []),
        "topo_internal_walls": facts.get("internal_wall_items", []),
        "topo_t_junctions": facts.get("t_junction_items", []),
        "topo_non_manifold": facts.get("non_manifold_items", []),
        "topo_open_boundary": facts.get("boundary_loops", []),
        "deform_tris_in_quads": facts.get("tri_items", [])
    }
    return mapping.get(base_id, [])


def _add_anomaly_findings(
    findings_list: List[DiagnosticFinding],
    base_id: str,
    category: str,
    default_name_singular: str,
    default_name_plural: str,
    default_severity: str,
    items: List[Dict[str, Any]],
    total_count: int,
    intentional_ids: List[str],
    profile_id: str,
    strict_manifold: bool,
    quads_only: bool,
    explanation: str,
    consequence: str,
    recommendation: str,
    compatible_action: Optional[str] = None,
    action_name: str = "",
    action_risk: str = "Risque Faible",
    manual_correction_steps: Optional[List[str]] = None,
    metric_value: Optional[float] = None,
    metric_unit: str = "",
    refusal_reason: Optional[str] = None
) -> None:
    """Ajoute des constats individuels ou synthétiques selon le nombre d'occurrences.
    Garantit une granularité rigoureuse (P0) :
    - Si 1 seule occurrence : ID = base_id (compatibilité 100%).
    - Si > 1 occurrences : ID = f"{base_id}:{item_id}" pour chaque élément.
    - Évalue la conformité à l'objectif sans greenwashing (ex: trou = RISK sous EXPORT_PREP).
    """
    if total_count <= 0:
        return

    # Si aucun item individuel n'est disponible (repli de sécurité)
    if not items:
        is_int = (base_id in intentional_ids)
        if is_int:
            sev, name, exp = _check_goal_compliance(
                base_id, f"{default_name_plural} ({total_count})", default_severity,
                profile_id, strict_manifold, quads_only, explanation
            )
            rec = "Géométrie conservée conformément au choix utilisateur." if sev == "OBSERVATION" else recommendation
        else:
            sev, name, exp, rec = default_severity, f"{default_name_plural} ({total_count})", explanation, recommendation

        findings_list.append(DiagnosticFinding(
            finding_id=base_id,
            category=category,
            name=name,
            severity=sev,
            count=total_count,
            metric_value=metric_value,
            metric_unit=metric_unit,
            explanation=exp,
            consequence=consequence,
            recommendation=rec,
            compatible_action=compatible_action if not is_int else None,
            action_name=action_name if not is_int else "",
            action_risk=action_risk if not is_int else "",
            manual_correction_steps=manual_correction_steps or [],
            refusal_reason=refusal_reason,
            is_intentional=is_int
        ))
        return

    # Cas A : Une seule occurrence (len(items) == 1) -> base_id direct
    if len(items) == 1:
        it = items[0]
        it_id = str(it.get("item_id", it.get("index", "0")))
        is_int = _is_intentional(base_id, it_id, 1, intentional_ids)

        if is_int:
            sev, name, exp = _check_goal_compliance(
                base_id, f"{default_name_plural} (1)", default_severity,
                profile_id, strict_manifold, quads_only, explanation
            )
            rec = "Géométrie conservée conformément au choix utilisateur." if sev == "OBSERVATION" else recommendation
        else:
            sev, name, exp, rec = default_severity, f"{default_name_plural} (1)", explanation, recommendation

        findings_list.append(DiagnosticFinding(
            finding_id=base_id,
            category=category,
            name=name,
            severity=sev,
            count=1,
            metric_value=it.get("length") or it.get("aspect") or metric_value,
            metric_unit=metric_unit,
            element_type=it.get("element_type", "OBJECT"),
            indices=it.get("indices", []),
            face_indices=it.get("face_indices", []),
            center=it.get("center"),
            explanation=exp,
            consequence=consequence,
            recommendation=rec,
            compatible_action=compatible_action if not is_int else None,
            action_name=action_name if not is_int else "",
            action_risk=action_risk if not is_int else "",
            manual_correction_steps=manual_correction_steps or [],
            refusal_reason=refusal_reason,
            is_intentional=is_int
        ))
        return

    # Cas B : Plusieurs occurrences distinctes (len(items) > 1) -> Granularité P0
    MAX_GRANULAR = 20
    for idx, it in enumerate(items):
        it_id = str(it.get("item_id", it.get("index", idx)))
        is_int = _is_intentional(base_id, it_id, len(items), intentional_ids)

        # Si au-delà du seuil et non marqué intentionnel, on reporte vers le résumé
        if idx >= MAX_GRANULAR and not is_int:
            continue

        elem_idx_label = it.get("index", it.get("loop_id", idx))
        elem_name = f"{default_name_singular} (#{elem_idx_label})"

        if is_int:
            sev, name, exp = _check_goal_compliance(
                base_id, elem_name, default_severity,
                profile_id, strict_manifold, quads_only, explanation
            )
            rec = "Géométrie conservée conformément au choix utilisateur." if sev == "OBSERVATION" else recommendation
        else:
            sev, name, exp, rec = default_severity, elem_name, explanation, recommendation

        findings_list.append(DiagnosticFinding(
            finding_id=f"{base_id}:{it_id}",
            category=category,
            name=name,
            severity=sev,
            count=1,
            metric_value=it.get("length") or it.get("aspect") or metric_value,
            metric_unit=metric_unit,
            element_type=it.get("element_type", "OBJECT"),
            indices=it.get("indices", []),
            face_indices=it.get("face_indices", []),
            center=it.get("center"),
            explanation=exp,
            consequence=consequence,
            recommendation=rec,
            compatible_action=compatible_action if not is_int else None,
            action_name=action_name if not is_int else "",
            action_risk=action_risk if not is_int else "",
            manual_correction_steps=manual_correction_steps or [],
            refusal_reason=refusal_reason,
            is_intentional=is_int
        ))

    # Résumé pour les éléments excédentaires non listés individuellement
    unlisted_items = [
        it for i, it in enumerate(items)
        if i >= MAX_GRANULAR and not _is_intentional(base_id, str(it.get("item_id", it.get("index", i))), len(items), intentional_ids)
    ]
    if unlisted_items:
        findings_list.append(DiagnosticFinding(
            finding_id=f"{base_id}:other",
            category=category,
            name=f"{default_name_plural} (et {len(unlisted_items)} autre(s) non listé(s))",
            severity=default_severity,
            count=len(unlisted_items),
            element_type=items[0].get("element_type", "OBJECT"),
            indices=[it.get("index") for it in unlisted_items if "index" in it],
            center=unlisted_items[0].get("center"),
            explanation=f"{len(unlisted_items)} autre(s) occurrence(s) au-delà des {MAX_GRANULAR} premières.",
            consequence=consequence,
            recommendation=recommendation,
            compatible_action=compatible_action,
            action_name=action_name,
            action_risk=action_risk,
            manual_correction_steps=manual_correction_steps or []
        ))


def evaluate_structured_diagnosis(
    facts: Dict[str, Any],
    profile_id: str = "GENERAL",
    strict_manifold: bool = False,
    quads_only: bool = False,
    intentional_finding_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Évalue instantanément les faits géométriques selon les règles de l'objectif choisi
    et des contraintes complémentaires (strict_manifold, quads_only).
    Produit la liste hiérarchisée des constats (DEFECT, RISK, OBSERVATION)
    et les recommandations réparties en 4 catégories sans recalcul géométrique lourd.
    Prend en compte les géométries validées comme intentionnelles par l'utilisateur.
    """
    if intentional_finding_ids is None:
        intentional_finding_ids = list(facts.get("intentional_finding_ids", []))

    # Résolution des alias de profil
    resolved_profile = PROFILE_ALIAS.get(profile_id, profile_id)
    if resolved_profile not in PROFILES:
        resolved_profile = "GENERAL"

    p_info = PROFILES[resolved_profile]

    if not facts.get("valid", False):
        return {
            "valid": False,
            "error": facts.get("error", "Faits géométriques indisponibles."),
            "profile": p_info,
            "findings": [],
            "recommended_actions": [],
            "recommendation_groups": {
                "conservative": [],
                "targeted": [],
                "risky": [],
                "observations": []
            },
            "summary_counts": {"defects": 0, "risks": 0, "observations": 0}
        }

    if facts.get("is_empty", False):
        return {
            "valid": True,
            "object_name": facts.get("object_name", ""),
            "profile": p_info,
            "findings": [
                DiagnosticFinding(
                    finding_id="empty_mesh",
                    category="GEOMETRY",
                    name="Maillage vide (0 sommet, 0 face)",
                    severity="DEFECT",
                    count=0,
                    explanation="Cet objet ne contient aucun sommet ni polygone.",
                    consequence="Impossible d'appliquer des opérations de modélisation.",
                    recommendation="Passez en mode Édition pour créer de la géométrie ou supprimez cet objet."
                ).to_dict()
            ],
            "recommended_actions": [],
            "recommendation_groups": {
                "conservative": [],
                "targeted": [],
                "risky": [],
                "observations": []
            },
            "summary_counts": {"defects": 1, "risks": 0, "observations": 0}
        }

    findings: List[DiagnosticFinding] = []
    recommended_actions: List[Dict[str, Any]] = []

    # =========================================================================
    # 1. GÉOMÉTRIE & DÉGÉNÉRESCENCES (Priorité absolue sur tous les profils)
    # =========================================================================

    # 1.1 Faces d'aire nulle
    _add_anomaly_findings(
        findings_list=findings,
        base_id="geom_zero_area_faces",
        category="GEOMETRY",
        default_name_singular="Face d'aire nulle",
        default_name_plural="Faces d'aire nulle",
        default_severity="DEFECT",
        items=facts.get("zero_area_items", []),
        total_count=facts["zero_area_faces_count"],
        intentional_ids=intentional_finding_ids,
        profile_id=resolved_profile,
        strict_manifold=strict_manifold,
        quads_only=quads_only,
        explanation="Faces plates ou repliées sans surface mesurable (aire <= 1e-7 m²).",
        consequence="Provoquent des divisions par zéro lors du calcul des normales, des NaN et des erreurs de rendu.",
        recommendation="Dissoudre ces faces dégénérées via le nettoyage conservateur.",
        compatible_action="meshforge.conservative_clean",
        action_name="Nettoyage conservateur sûr",
        action_risk="Risque Faible"
    )

    # 1.2 Sommets orphelins (Loose verts)
    _add_anomaly_findings(
        findings_list=findings,
        base_id="geom_loose_verts",
        category="GEOMETRY",
        default_name_singular="Sommet orphelin",
        default_name_plural="Sommets orphelins",
        default_severity="DEFECT",
        items=facts.get("loose_vert_items", []),
        total_count=facts["loose_verts_count"],
        intentional_ids=intentional_finding_ids,
        profile_id=resolved_profile,
        strict_manifold=strict_manifold,
        quads_only=quads_only,
        explanation="Sommets flottant dans l'espace sans arête ni face connectée.",
        consequence="Alourdissent inutilement les buffers GPU et faussent la boîte englobante.",
        recommendation="Supprimer les sommets orphelins.",
        compatible_action="meshforge.conservative_clean",
        action_name="Nettoyage conservateur sûr",
        action_risk="Risque Nul"
    )

    # 1.3 Arêtes minuscules
    sev_micro = "DEFECT" if resolved_profile == "MECHANICAL_CAD" else "RISK"
    _add_anomaly_findings(
        findings_list=findings,
        base_id="geom_micro_edges",
        category="GEOMETRY",
        default_name_singular="Arête minuscule",
        default_name_plural="Arêtes minuscules",
        default_severity=sev_micro,
        items=facts.get("micro_edge_items", []),
        total_count=facts["micro_edges_count"],
        intentional_ids=intentional_finding_ids,
        profile_id=resolved_profile,
        strict_manifold=strict_manifold,
        quads_only=quads_only,
        explanation=f"Arêtes exceptionnellement courtes par rapport à l'échelle de l'objet (seuil {facts['micro_edge_threshold']*1000:.2f} mm).",
        consequence="Souvent issues de booléens imprécis ou de doubles extrusions. Risquent de créer des aiguilles.",
        recommendation="Fusionner les sommets doublons si ce n'est pas un micro-chanfrein intentionnel.",
        compatible_action="meshforge.conservative_clean",
        action_name="Nettoyage conservateur sûr",
        action_risk="Risque Modéré",
        manual_correction_steps=[
            "Mode Édition (Tab) > Sélection sommets (1).",
            "Sélectionner les deux sommets de l'arête minuscule.",
            "Appuyer sur M > 'Au centre' pour fusionner manuellement sans affecter le reste."
        ],
        metric_value=facts["micro_edge_threshold"] * 1000.0,
        metric_unit="mm (seuil)"
    )

    # =========================================================================
    # 2. TOPOLOGIE & CONNECTIVITÉ
    # =========================================================================

    # 2.1 Arêtes filaires sans face
    sev_wire = "DEFECT" if (strict_manifold or resolved_profile in ("GAME_ASSET", "MECHANICAL_CAD", "EXPORT_PREP")) else "RISK"
    _add_anomaly_findings(
        findings_list=findings,
        base_id="topo_wire_edges",
        category="TOPOLOGY",
        default_name_singular="Arête filaire sans face",
        default_name_plural="Arêtes filaires sans face",
        default_severity=sev_wire,
        items=facts.get("wire_edge_items", []),
        total_count=facts["wire_edges_count"],
        intentional_ids=intentional_finding_ids,
        profile_id=resolved_profile,
        strict_manifold=strict_manifold,
        quads_only=quads_only,
        explanation="Segments d'arêtes isolés ne délimitant aucune face polygonale.",
        consequence="Invisibles en rendu de surface mais génèrent des erreurs d'export et d'occlusion.",
        recommendation="Supprimer les arêtes filaires.",
        compatible_action="meshforge.conservative_clean",
        action_name="Nettoyage conservateur sûr",
        action_risk="Risque Faible"
    )

    # 2.2 Parois internes mitoyennes et jonctions en T (D2.4)
    sev_iw = "DEFECT" if (strict_manifold or resolved_profile in ("GAME_ASSET", "MECHANICAL_CAD", "EXPORT_PREP")) else "RISK"
    _add_anomaly_findings(
        findings_list=findings,
        base_id="topo_internal_walls",
        category="TOPOLOGY",
        default_name_singular="Paroi interne mitoyenne",
        default_name_plural="Parois internes mitoyennes",
        default_severity=sev_iw,
        items=facts.get("internal_wall_items", []),
        total_count=facts.get("internal_walls_count", 0),
        intentional_ids=intentional_finding_ids,
        profile_id=resolved_profile,
        strict_manifold=strict_manifold,
        quads_only=quads_only,
        explanation=f"{facts.get('internal_walls_count', 0)} face(s) mitoyenne(s) occluses séparant des cellules fermées. Leur suppression guérit la non-manifoldité sans ouvrir de trou.",
        consequence="Rend l'objet non-étanche, interdit l'impression 3D, gaspille du budget polygonal et perturbe le baking.",
        recommendation="Supprimer les parois internes après confirmation.",
        compatible_action="meshforge.remove_internal_walls",
        action_name="Supprimer les parois internes",
        action_risk="Risque Contrôlé"
    )

    sev_tj = "RISK" if (strict_manifold or resolved_profile in ("MECHANICAL_CAD", "EXPORT_PREP")) else "OBSERVATION"
    _add_anomaly_findings(
        findings_list=findings,
        base_id="topo_t_junctions",
        category="TOPOLOGY",
        default_name_singular="Jonction de surface / Aileron",
        default_name_plural="Jonctions de surface / Ailerons",
        default_severity=sev_tj,
        items=facts.get("t_junction_items", []),
        total_count=facts.get("t_junctions_count", 0),
        intentional_ids=intentional_finding_ids,
        profile_id=resolved_profile,
        strict_manifold=strict_manifold,
        quads_only=quads_only,
        explanation="Surfaces rattachées formant une jonction en T (ex: aileron ou cloison ouverte). Surface potentiellement intentionnelle : aucune suppression automatique.",
        consequence="Arête partagée par 3 faces. Non-étanche pour l'impression 3D, mais peut être normale sur un décor ou un vêtement.",
        recommendation="Conserver si l'aileron est voulu, ou séparer les surfaces en mode Édition.",
        manual_correction_steps=[
            "Mode Édition (Tab) > Sélection faces (3).",
            "Survoler l'aileron ou cloison et appuyer sur L pour sélectionner l'îlot.",
            "Pour détacher dans un objet séparé : P > 'Sélection'.",
            "Pour supprimer la cloison surnuméraire : X > 'Faces'."
        ]
    )

    # 2.2b Arêtes non-manifold résiduelles
    if facts["non_manifold_edges_count"] > 0 and facts.get("internal_walls_count", 0) == 0:
        _add_anomaly_findings(
            findings_list=findings,
            base_id="topo_non_manifold",
            category="TOPOLOGY",
            default_name_singular="Arête non-manifold",
            default_name_plural="Arêtes non-manifold",
            default_severity="DEFECT",
            items=facts.get("non_manifold_items", []),
            total_count=facts["non_manifold_edges_count"],
            intentional_ids=intentional_finding_ids,
            profile_id=resolved_profile,
            strict_manifold=strict_manifold,
            quads_only=quads_only,
            explanation="Arêtes partagées par plus de 2 faces (jonction en T ou intersection complexe).",
            consequence="Rend l'objet non-étanche (non-watertight), interdit l'impression 3D et perturbe le baking.",
            recommendation="Inspecter en mode Édition ou scinder les surfaces.",
            manual_correction_steps=[
                "Mode Édition (Tab) > Sélection arêtes (2).",
                "Menu Sélectionner > Sélectionner par trait > Non-Manifold (Maj+Ctrl+Alt+M).",
                "Désactiver 'Frontière' pour cibler uniquement les jonctions internes.",
                "Dissoudre les arêtes intérieures excédentaires (X > 'Dissoudre les arêtes') ou scinder (V)."
            ]
        )

    # 2.3 Frontières ouvertes (Mesh ouvert / Tissu)
    if facts["is_open_mesh"]:
        sev_boundary = "DEFECT" if (strict_manifold or resolved_profile == "EXPORT_PREP") else ("RISK" if resolved_profile == "MECHANICAL_CAD" else "OBSERVATION")
        _add_anomaly_findings(
            findings_list=findings,
            base_id="topo_open_boundary",
            category="TOPOLOGY",
            default_name_singular="Boucle de frontière ouverte",
            default_name_plural="Frontière ouverte",
            default_severity=sev_boundary,
            items=facts.get("boundary_loops", []),
            total_count=len(facts.get("boundary_loops", [])),
            intentional_ids=intentional_finding_ids,
            profile_id=resolved_profile,
            strict_manifold=strict_manifold,
            quads_only=quads_only,
            explanation="Le maillage possède un ou plusieurs bords ouverts (surface non fermée).",
            consequence="Normal pour un plan, une nappe de tissu ou un vêtement. Inadapté si une pièce pleine est attendue.",
            recommendation="Vérifier si le modèle est censé être un volume fermé solide.",
            manual_correction_steps=[
                "Mode Édition (Tab) > Sélection arêtes (2).",
                "Menu Sélectionner > Sélectionner par trait > Non-Manifold (cocher uniquement 'Frontière').",
                "Pour boucher un trou simple : appuyer sur F pour créer une face.",
                "Pour boucher avec une grille régulière : menu Face > Grid Fill (Remplir en grille)."
            ]
        )

    # 2.4 N-gones (Convexes, Concaves, Ambigus) - INTERPRÉTATION STRICTEMENT SELON PROFIL & CONTRAINTES
    if facts["total_ngons"] > 0:
        # A. Cas ambigus (Bow-tie / Torsion extrême) : DEFECT partout !
        _add_anomaly_findings(
            findings_list=findings,
            base_id="topo_ngons_ambiguous",
            category="TOPOLOGY",
            default_name_singular="N-gone ambigu / auto-intersectant",
            default_name_plural="N-gones ambigus / auto-intersectants",
            default_severity="DEFECT",
            items=facts.get("ngon_ambiguous_items", []),
            total_count=facts["ngons_ambiguous_count"],
            intentional_ids=intentional_finding_ids,
            profile_id=resolved_profile,
            strict_manifold=strict_manifold,
            quads_only=quads_only,
            explanation="Polygones dont les arêtes se croisent en 8 (nœud papillon) ou fortement gauchis en selle.",
            consequence="Toute triangulation automatique produit des faces retournées et des traits noirs d'ombrage.",
            recommendation="Sélectionnés pour découpe manuelle au couteau (K en mode Édition).",
            refusal_reason="Refus automatique de découpe pour éviter la création de faces inversées.",
            manual_correction_steps=[
                "Mode Édition (Tab) > Sélection sommets (1).",
                "Activer le Couteau (K) et relier deux sommets opposés pour scinder le croisement en deux faces planes.",
                "Alternative : supprimer la face (X > 'Seulement les faces') et reconstruire les quads manuellement avec F."
            ]
        )

        # B. Cas concaves (Angles rentrants > 180°)
        sev_concave = "DEFECT" if (quads_only or resolved_profile in ("GAME_ASSET", "EXPORT_PREP")) else "RISK"
        _add_anomaly_findings(
            findings_list=findings,
            base_id="topo_ngons_concave",
            category="TOPOLOGY",
            default_name_singular="N-gone concave",
            default_name_plural="N-gones concaves",
            default_severity=sev_concave,
            items=facts.get("ngon_concave_items", []),
            total_count=facts["ngons_concave_count"],
            intentional_ids=intentional_finding_ids,
            profile_id=resolved_profile,
            strict_manifold=strict_manifold,
            quads_only=quads_only,
            explanation="Faces à plus de 4 côtés comportant des angles rentrants (concavité).",
            consequence="La triangulation naïve en éventail chevaucherait la surface. Nécessite un Ear-Clipping orienté.",
            recommendation="Découper les N-gones (Ear-Clipping sécurisé).",
            compatible_action="meshforge.cut_ngons",
            action_name="Découper les N-gones",
            action_risk="Risque Contrôlé"
        )

        # C. Cas convexes réguliers
        if facts["ngons_convex_count"] > 0:
            if quads_only or resolved_profile in ("GAME_ASSET", "EXPORT_PREP"):
                sev_cv = "DEFECT"
                exp_cv = "La topologie requise interdit les N-gones (triangulation ou quads obligatoires)."
                rec_cv = "Découper les N-gones en polygones élémentaires."
                act_cv = "meshforge.cut_ngons"
            elif resolved_profile == "DEFORMABLE_CHAR":
                sev_cv = "RISK"
                exp_cv = "Les N-gones interrompent les boucles de quads (edge loops) nécessaires aux déformations d'articulation."
                rec_cv = "Convertir en quads pour préserver la fluidité de déformation."
                act_cv = "meshforge.cut_ngons"
            elif resolved_profile == "RENDER_ANIM":
                sev_cv = "RISK"
                exp_cv = "Les N-gones peuvent créer des étirements ou des plis sous subdivision de surface."
                rec_cv = "Découper les N-gones pour un lissage régulier."
                act_cv = "meshforge.cut_ngons"
            elif resolved_profile == "MECHANICAL_CAD":
                sev_cv = "OBSERVATION"
                exp_cv = "Face plane régulière à plus de 4 sommets. Courant et toléré sur les surfaces d'appui plates en CAD."
                rec_cv = "Conservation possible si la face reste parfaitement plane."
                act_cv = None
            else:  # GENERAL, SCULPTED_ORGANIC, CUSTOM
                sev_cv = "OBSERVATION"
                exp_cv = f"Face convexe à plus de 4 sommets. Ne pose pas de problème immédiat hors contrainte stricte."
                rec_cv = "Découpe recommandée si vous prévoyez une subdivision ou un export temps réel."
                act_cv = "meshforge.cut_ngons"

            _add_anomaly_findings(
                findings_list=findings,
                base_id="topo_ngons_convex",
                category="TOPOLOGY",
                default_name_singular="N-gone convexe",
                default_name_plural="N-gones convexes",
                default_severity=sev_cv,
                items=facts.get("ngon_convex_items", []),
                total_count=facts["ngons_convex_count"],
                intentional_ids=intentional_finding_ids,
                profile_id=resolved_profile,
                strict_manifold=strict_manifold,
                quads_only=quads_only,
                explanation=exp_cv,
                consequence="Comportement variable selon l'usage final de l'objet.",
                recommendation=rec_cv,
                compatible_action=act_cv,
                action_name="Découper les N-gones" if act_cv else "",
                action_risk="Risque Contrôlé" if act_cv else ""
            )

    # =========================================================================
    # 3. SILHOUETTE & QUALITÉ DE SURFACE
    # =========================================================================

    # 3.1 Triangles très étirés (Needles / Aiguilles)
    sev_needle = "RISK" if resolved_profile in ("GAME_ASSET", "SCULPTED_ORGANIC") else "OBSERVATION"
    _add_anomaly_findings(
        findings_list=findings,
        base_id="surface_needle_triangles",
        category="SURFACE",
        default_name_singular="Triangle très étiré",
        default_name_plural="Triangles très étirés",
        default_severity=sev_needle,
        items=facts.get("needle_triangle_items", []),
        total_count=facts["needle_triangles_count"],
        intentional_ids=intentional_finding_ids,
        profile_id=resolved_profile,
        strict_manifold=strict_manifold,
        quads_only=quads_only,
        explanation=f"Triangles présentant un ratio de côtés supérieur à 8:1 (max mesuré {facts['needle_max_aspect']:.1f}:1).",
        consequence="Dégradent le Smooth Shading et provoquent des balafres noires (artefact du Normal Terminator).",
        recommendation="Équilibrer les arêtes ou éviter la décimation native non contrainte.",
        manual_correction_steps=[
            "Mode Édition (Tab) > Sélection arêtes (2).",
            "Sélectionner l'arête courte opposée au sommet aigu.",
            "Dissoudre l'arête (Ctrl+X) ou faire Ctrl+E > 'Tourner l'arête dans le sens horaire' (Edge Flip)."
        ],
        metric_value=facts["needle_max_aspect"],
        metric_unit=":1 (ratio max)"
    )

    # =========================================================================
    # 4. PRÉPARATION À LA DÉFORMATION & GÉOMÉTRIE QUADS
    # =========================================================================

    if quads_only or resolved_profile in ("DEFORMABLE_CHAR", "RENDER_ANIM"):
        # 4.1 Triangles au milieu de quads
        sev_tri = "DEFECT" if quads_only else "RISK"
        _add_anomaly_findings(
            findings_list=findings,
            base_id="deform_tris_in_quads",
            category="DEFORMATION",
            default_name_singular="Triangle en zone déformable",
            default_name_plural="Triangles dans un maillage quad",
            default_severity=sev_tri,
            items=facts.get("tri_items", []),
            total_count=facts["tris_count"],
            intentional_ids=intentional_finding_ids,
            profile_id=resolved_profile,
            strict_manifold=strict_manifold,
            quads_only=quads_only,
            explanation=f"Le maillage contient {facts['tris_count']} triangle(s) au milieu de {facts['quads_count']} quad(s).",
            consequence="Un triangle interrompt la trajectoire d'une boucle d'arêtes (Edge Loop) et peut créer un pli rigide au pliage.",
            recommendation="Fusionner les paires de triangles coplanaires en quads réguliers (Quadrangulation ciblée).",
            compatible_action="meshforge.quadrangulate",
            action_name="Quadrangulation ciblée",
            action_risk="Risque Faible"
        )

        # 4.2 Pôles à haute valence (valence >= 6)
        _add_anomaly_findings(
            findings_list=findings,
            base_id="deform_high_valence_poles",
            category="DEFORMATION",
            default_name_singular="Pôle complexe valence >= 6",
            default_name_plural="Pôles complexes valence >= 6",
            default_severity="RISK",
            items=facts.get("pole_items", []),
            total_count=facts["poles_valence_6_plus_count"],
            intentional_ids=intentional_finding_ids,
            profile_id=resolved_profile,
            strict_manifold=strict_manifold,
            quads_only=quads_only,
            explanation=f"{facts['poles_valence_6_plus_count']} sommet(s) intérieur(s) connectent 6 arêtes ou plus.",
            consequence="Les pôles à haute valence provoquent des plis en étoile et des déformations chaotiques sous l'influence des os.",
            recommendation="Rediriger les arêtes pour scinder les pôles en valences 4 ou 5.",
            manual_correction_steps=[
                "Mode Édition (Tab) > Sélection sommets (1).",
                "Cadrer sur le pôle complexe.",
                "Utiliser le Couteau (K) ou glissement de sommets (G deux fois) pour scinder le pôle en valences 4 ou 5."
            ]
        )

    # =========================================================================
    # 5. DENSITÉ POLYGONALE & STATISTIQUES
    # =========================================================================

    tris_real = facts["real_triangles"]
    if resolved_profile == "GAME_ASSET" and tris_real > 100000:
        findings.append(DiagnosticFinding(
            finding_id="density_high_for_game",
            category="DENSITY",
            name=f"Densité élevée pour un asset de jeu ({tris_real:,} tris)",
            severity="RISK",
            count=tris_real,
            metric_value=float(tris_real),
            metric_unit="triangles",
            element_type="OBJECT",
            explanation=f"L'objet totalise {tris_real:,} triangles, ce qui est élevé pour un prop de jeu standard.",
            consequence="Risque de baisse de framerate si l'asset est dupliqué ou utilisé sans système de LODs.",
            recommendation="Une simplification contrôlée ou la génération de LODs est recommandée."
        ))
    elif resolved_profile == "SCULPTED_ORGANIC":
        findings.append(DiagnosticFinding(
            finding_id="density_sculpt_info",
            category="DENSITY",
            name=f"Densité de sculpture ({tris_real:,} triangles)",
            severity="OBSERVATION",
            count=tris_real,
            metric_value=float(tris_real),
            metric_unit="triangles",
            element_type="OBJECT",
            explanation=f"Densité de {tris_real:,} triangles adaptée à la restitution des détails sculptés fins.",
            consequence="Ne nécessite pas de décimation sauf pour l'export vers un moteur temps réel.",
            recommendation="Préférez une retopologie dédiée plutôt qu'un modificateur Decimate destructif."
        ))
    else:
        findings.append(DiagnosticFinding(
            finding_id="density_general_stats",
            category="DENSITY",
            name=f"Statistiques globales : {facts['polygon_count']:,} faces ({tris_real:,} tris)",
            severity="OBSERVATION",
            count=facts["polygon_count"],
            element_type="OBJECT",
            explanation=f"Répartition : {facts['quads_count']:,} quads ({facts['quads_count']/max(1, facts['polygon_count'])*100:.1f}%), {facts['tris_count']:,} triangles, {facts['total_ngons']:,} N-gones.",
            consequence="Données objectives pour évaluer la structure du maillage.",
            recommendation=""
        ))

    # =========================================================================
    # 6. UV ET MATÉRIAUX
    # =========================================================================

    if facts["uv_layer_count"] == 0:
        sev = "DEFECT" if resolved_profile == "GAME_ASSET" else "OBSERVATION"
        findings.append(DiagnosticFinding(
            finding_id="uv_missing",
            category="UV_MATERIAL",
            name="Aucun dépliage UV détecté",
            severity=sev,
            count=0,
            element_type="OBJECT",
            explanation="L'objet ne possède aucune carte UV (UVMap).",
            consequence="Impossible d'appliquer des textures 2D, du baking ou d'exporter vers un moteur de jeu.",
            recommendation="Déplier le maillage (U > Déplier ou Dépliage intelligent UV).",
            manual_correction_steps=[
                "Mode Édition (Tab) > Tout sélectionner (A).",
                "Menu UV (Touche U) > 'Déplier' ou 'Dépliage intelligent UV' (Smart UV Project)."
            ]
        ))
    else:
        findings.append(DiagnosticFinding(
            finding_id="uv_present",
            category="UV_MATERIAL",
            name=f"{facts['uv_layer_count']} couche(s) UV présente(s) ({', '.join(facts['uv_layer_names'])})",
            severity="OBSERVATION",
            count=facts["uv_layer_count"],
            element_type="OBJECT",
            explanation="Les coordonnées UV sont bien enregistrées et protégées par les opérateurs MeshForge.",
            consequence="Préservation garantie lors du nettoyage conservateur et des découpes.",
            recommendation=""
        ))

    # =========================================================================
    # 6.b TRAITEMENT DES VALIDATIONS RÉINITIALISÉES (P0)
    # =========================================================================
    pruned = facts.get("pruned_validations", [])
    if pruned:
        findings.append(DiagnosticFinding(
            finding_id="audit_pruned_validations",
            category="TOPOLOGY",
            name=f"Validations réinitialisées ({len(pruned)})",
            severity="OBSERVATION",
            count=len(pruned),
            element_type="OBJECT",
            explanation=f"{len(pruned)} anomalie(s) précédemment marquée(s) intentionnelle(s) ont été réinitialisées suite à la modification ou suppression de leur géométrie.",
            consequence="Garantit qu'aucune validation n'est conservée de façon silencieuse ou erronée.",
            recommendation="Si la nouvelle géométrie reste délibérée, re-marquez l'anomalie correspondante."
        ))

    # =========================================================================
    # 7. SÉLECTION ET PRIORISATION DES RECOMMANDATIONS (Les 4 Catégories UX)
    # =========================================================================

    rec_conservative = []
    rec_targeted = []
    rec_risky = []
    rec_observations = []
    recommended_actions = []

    # 7.1 Catégorie 1 : Corrections conservatrices recommandées (items actifs non intentionnels)
    active_zero = [it for it in facts.get("zero_area_items", []) if not _is_intentional("geom_zero_area_faces", str(it.get("item_id", it.get("index", "0"))), len(facts.get("zero_area_items", [])), intentional_finding_ids)]
    active_loose = [it for it in facts.get("loose_vert_items", []) if not _is_intentional("geom_loose_verts", str(it.get("item_id", it.get("index", "0"))), len(facts.get("loose_vert_items", [])), intentional_finding_ids)]
    active_wire = [it for it in facts.get("wire_edge_items", []) if not _is_intentional("topo_wire_edges", str(it.get("item_id", it.get("index", "0"))), len(facts.get("wire_edge_items", [])), intentional_finding_ids)]
    active_micro = [it for it in facts.get("micro_edge_items", []) if not _is_intentional("geom_micro_edges", str(it.get("item_id", it.get("index", "0"))), len(facts.get("micro_edge_items", [])), intentional_finding_ids)]
    active_walls = [it for it in facts.get("internal_wall_items", []) if not _is_intentional("topo_internal_walls", str(it.get("item_id", it.get("index", "0"))), len(facts.get("internal_wall_items", [])), intentional_finding_ids)]

    has_conservative_clean_needs = (
        len(active_zero) > 0 or
        len(active_loose) > 0 or
        len(active_wire) > 0 or
        (len(active_micro) > 0 and resolved_profile == "MECHANICAL_CAD")
    )
    if has_conservative_clean_needs:
        reasons = []
        if len(active_loose) > 0:
            reasons.append(f"{len(active_loose)} sommet(s) orphelin(s)")
        if len(active_zero) > 0:
            reasons.append(f"{len(active_zero)} face(s) d'aire nulle")
        if len(active_wire) > 0:
            reasons.append(f"{len(active_wire)} arête(s) sans face")
        if len(active_micro) > 0 and resolved_profile == "MECHANICAL_CAD":
            reasons.append(f"{len(active_micro)} arête(s) minuscules")

        f_focus_id = "geom_zero_area_faces"
        if len(active_zero) > 0:
            f_focus_id = "geom_zero_area_faces" if len(facts.get("zero_area_items", [])) == 1 else f"geom_zero_area_faces:{active_zero[0]['item_id']}"
        elif len(active_loose) > 0:
            f_focus_id = "geom_loose_verts" if len(facts.get("loose_vert_items", [])) == 1 else f"geom_loose_verts:{active_loose[0]['item_id']}"
        elif len(active_wire) > 0:
            f_focus_id = "topo_wire_edges" if len(facts.get("wire_edge_items", [])) == 1 else f"topo_wire_edges:{active_wire[0]['item_id']}"

        rec_c = {
            "id": "rec_conservative_clean",
            "title": "Nettoyage conservateur des dégénérescences",
            "problem": f"Présence de résidus géométriques : {', '.join(reasons)}",
            "zone": "Éléments orphelins isolés et faces d'aire nulle",
            "effect": "Supprime les résidus et fusionne les doublons sans altérer les surfaces utiles",
            "data_impact": "Préservation totale des UVs, coutures (seams), arêtes vives et vertex groups",
            "reversibility": "Réversible (Ctrl+Z) / Rollback automatique en cas d'erreur",
            "confidence": "100% Sûr (Risque Faible)",
            "operator": "meshforge.conservative_clean",
            "operator_text": "Nettoyer les dégénérescences",
            "operator_icon": "BRUSH_DATA",
            "focus_id": f_focus_id
        }
        rec_conservative.append(rec_c)
        recommended_actions.append({
            "id": "conservative_clean",
            "operator": "meshforge.conservative_clean",
            "label": "Nettoyage conservateur sûr",
            "icon": 'BRUSH_DATA',
            "risk_badge": "[Risque Faible]",
            "risk_level": "LOW",
            "justification": f"Résout : {', '.join(reasons)}.",
            "data_impact": "Supprime uniquement les anomalies isolées. Ne modifie pas la forme de l'objet.",
            "safety_note": "Transaction réversible : rollback automatique en cas d'erreur."
        })

    if len(active_walls) > 0:
        f_iw_id = "topo_internal_walls" if len(facts.get("internal_wall_items", [])) == 1 else f"topo_internal_walls:{active_walls[0]['item_id']}"
        rec_iw = {
            "id": "rec_internal_walls",
            "title": "Suppression des parois internes mitoyennes",
            "problem": f"{len(active_walls)} face(s) mitoyenne(s) occluse(s) séparant des cellules fermées",
            "zone": "Cloisons internes mitoyennes non visibles de l'extérieur",
            "effect": "Supprime les parois intérieures pour restaurer un volume manifold étanche sans trou",
            "data_impact": "Coque extérieure intacte. UVs, coutures et matériaux strictement préservés",
            "reversibility": "Réversible (Ctrl+Z) / Rollback si ouverture de bord involontaire",
            "confidence": "Élevé (Cellules fermées et occlusions démontrées)",
            "operator": "meshforge.remove_internal_walls",
            "operator_text": f"Supprimer les parois internes ({len(active_walls)})",
            "operator_icon": "X",
            "focus_id": f_iw_id
        }
        rec_conservative.append(rec_iw)
        recommended_actions.append({
            "id": "remove_internal_walls",
            "operator": "meshforge.remove_internal_walls",
            "label": f"Supprimer les parois internes ({len(active_walls)} faces)",
            "icon": 'X',
            "risk_badge": "[Risque Contrôlé]",
            "risk_level": "CONTROLLED",
            "justification": f"Élimine {len(active_walls)} face(s) mitoyenne(s) occluses pour restaurer un volume fermé manifold.",
            "data_impact": "Supprime les faces intérieures sans ouvrir de trou dans la coque externe.",
            "safety_note": "Confirmation explicite requise. Rollback automatique si déviation."
        })

    # 7.2 Catégorie 2 : Optimisations ciblées pour l'objectif (items actifs)
    active_concave = [it for it in facts.get("ngon_concave_items", []) if not _is_intentional("topo_ngons_concave", str(it.get("item_id", it.get("index", "0"))), len(facts.get("ngon_concave_items", [])), intentional_finding_ids)]
    active_convex = [it for it in facts.get("ngon_convex_items", []) if not _is_intentional("topo_ngons_convex", str(it.get("item_id", it.get("index", "0"))), len(facts.get("ngon_convex_items", [])), intentional_finding_ids)]
    active_ngons_total = len(active_concave) + len(active_convex)

    need_cut_ngons = (
        (active_ngons_total > 0) and (
            quads_only or
            len(active_concave) > 0 or
            resolved_profile in ("GAME_ASSET", "DEFORMABLE_CHAR", "EXPORT_PREP", "RENDER_ANIM")
        )
    )
    if need_cut_ngons:
        reasons_ngon = []
        if len(active_concave) > 0:
            reasons_ngon.append(f"{len(active_concave)} concave(s)")
        if len(active_convex) > 0:
            reasons_ngon.append(f"{len(active_convex)} convexe(s)")

        if len(active_concave) > 0:
            f_ng_focus = "topo_ngons_concave" if len(facts.get("ngon_concave_items", [])) == 1 else f"topo_ngons_concave:{active_concave[0]['item_id']}"
        else:
            f_ng_focus = "topo_ngons_convex" if len(facts.get("ngon_convex_items", [])) == 1 else f"topo_ngons_convex:{active_convex[0]['item_id']}"

        rec_ngon = {
            "id": "rec_cut_ngons",
            "title": "Découpe sécurisée des N-gones",
            "problem": f"{active_ngons_total} N-gone(s) détecté(s) ({', '.join(reasons_ngon)})",
            "zone": "Faces à plus de 4 sommets",
            "effect": "Découpe en polygones gérables via Ear-clipping sécurisé et Beauty triangulation",
            "data_impact": "Coordonnées UV interpolées sans étirement, coutures et matériaux préservés",
            "reversibility": "Réversible (Ctrl+Z)",
            "confidence": "Très élevé (Cas ambigus exclus pour découpe manuelle)",
            "operator": "meshforge.cut_ngons",
            "operator_text": f"Découper les {active_ngons_total} N-gones",
            "operator_icon": "MOD_TRIANGULATE",
            "focus_id": f_ng_focus
        }
        rec_targeted.append(rec_ngon)
        recommended_actions.append({
            "id": "cut_ngons",
            "operator": "meshforge.cut_ngons",
            "label": f"Découper les N-gones ({active_ngons_total})",
            "icon": 'MOD_TRIANGULATE',
            "risk_badge": "[Risque Contrôlé]",
            "risk_level": "CONTROLLED",
            "justification": f"Résout : {active_ngons_total} N-gones pour l'objectif {p_info['name']}.",
            "data_impact": "Triangulation Beauty / Ear-Clipping. Préserve les UVs et matériaux.",
            "safety_note": f"Les cas ambigus ({facts['ngons_ambiguous_count']}) sont refusés et isolés pour découpe manuelle."
        })

    active_tris = [it for it in facts.get("tri_items", []) if not _is_intentional("deform_tris_in_quads", str(it.get("item_id", it.get("index", "0"))), len(facts.get("tri_items", [])), intentional_finding_ids)]
    need_quadrangulate = (
        (len(active_tris) >= 2) and (
            quads_only or
            resolved_profile in ("DEFORMABLE_CHAR", "RENDER_ANIM", "HARD_SURFACE", "GENERAL")
        )
    )
    if need_quadrangulate:
        f_tri_focus = "deform_tris_in_quads" if len(facts.get("tri_items", [])) == 1 else f"deform_tris_in_quads:{active_tris[0]['item_id']}"
        rec_quad = {
            "id": "rec_quadrangulate",
            "title": "Quadrangulation ciblée (Tris -> Quads)",
            "problem": f"{len(active_tris)} triangle(s) au milieu de {facts['quads_count']} quad(s)",
            "zone": "Paires de triangles adjacents coplanaires",
            "effect": "Reconstitue des quads réguliers pour fluidifier la déformation et le lissage",
            "data_impact": "Aire préservée, respect strict des coutures UV, arêtes vives et matériaux",
            "reversibility": "Réversible (Ctrl+Z) / Rollback si altération géométrique",
            "confidence": "Élevé (Tolérance angulaire stricte de planéité)",
            "operator": "meshforge.quadrangulate",
            "operator_text": f"Quadranguler les triangles ({len(active_tris)} tris)",
            "operator_icon": "SNAP_FACE",
            "focus_id": f_tri_focus
        }
        rec_targeted.append(rec_quad)
        recommended_actions.append({
            "id": "quadrangulate",
            "operator": "meshforge.quadrangulate",
            "label": f"Quadranguler les triangles coplanaires ({len(active_tris)} tris)",
            "icon": 'SNAP_FACE',
            "risk_badge": "[Risque Faible]",
            "risk_level": "LOW",
            "justification": f"Fusionne les paires de triangles coplanaires ({len(active_tris)} triangles détectés) en quads réguliers.",
            "data_impact": "Préserve strictement les coutures UV, arêtes vives, matériaux et l'aire du maillage.",
            "safety_note": "Transaction réversible : rollback automatique en cas de déviation géométrique."
        })

    # 7.3 Catégorie 3 : Actions à risque à examiner individuellement (avec étapes manuelles)
    raw_rec_risky = []
    active_ambiguous = [it for it in facts.get("ngon_ambiguous_items", []) if not _is_intentional("topo_ngons_ambiguous", str(it.get("item_id", it.get("index", "0"))), len(facts.get("ngon_ambiguous_items", [])), intentional_finding_ids)]
    if len(active_ambiguous) > 0:
        f_amb_focus = "topo_ngons_ambiguous" if len(facts.get("ngon_ambiguous_items", [])) == 1 else f"topo_ngons_ambiguous:{active_ambiguous[0]['item_id']}"
        raw_rec_risky.append({
            "id": "rec_risky_ngons_ambiguous",
            "title": "N-gones ambigus / auto-intersectants",
            "problem": f"{len(active_ambiguous)} face(s) en nœud papillon ou à forte torsion de planéité",
            "zone": "Polygones auto-intersectants ou en selle",
            "effect": "La découpe automatique risquerait d'inverser des normales. Découpe manuelle conseillée (K au couteau)",
            "data_impact": "Aucune altération automatique appliquée",
            "reversibility": "Sans objet (opération refusée par précaution)",
            "confidence": "Refus préventif de sécurité",
            "operator": None,
            "focus_id": f_amb_focus,
            "manual_correction_steps": [
                "Mode Édition (Tab) > Sélection sommets (1).",
                "Outil Couteau (K) : couper entre deux sommets opposés pour séparer le croisement.",
                "Alternative : X > 'Seulement les faces' puis recréer des faces quads avec F."
            ]
        })

    active_tj = [it for it in facts.get("t_junction_items", []) if not _is_intentional("topo_t_junctions", str(it.get("item_id", it.get("index", "0"))), len(facts.get("t_junction_items", [])), intentional_finding_ids)]
    if len(active_tj) > 0:
        f_tj_focus = "topo_t_junctions" if len(facts.get("t_junction_items", [])) == 1 else f"topo_t_junctions:{active_tj[0]['item_id']}"
        raw_rec_risky.append({
            "id": "rec_risky_t_junctions",
            "title": "Jonctions de surface / Ailerons rattachés",
            "problem": f"{len(active_tj)} face(s) formant une jonction en T (arêtes à 3 faces)",
            "zone": "Cloisons ouvertes ou ailerons rattachés à la coque",
            "effect": "Surface potentiellement intentionnelle (décor, vêtement, aileron). Ne jamais supprimer sans inspection",
            "data_impact": "Surfaces utiles visibles",
            "reversibility": "Non altéré sans action utilisateur",
            "confidence": "Nécessite arbitrage visuel humain",
            "operator": None,
            "focus_id": f_tj_focus,
            "manual_correction_steps": [
                "Mode Édition (Tab) > Sélection faces (3).",
                "Survoler l'aileron et appuyer sur L pour sélectionner l'îlot mitoyen.",
                "Pour séparer en objet distinct : P > 'Sélection'.",
                "Pour supprimer la cloison surnuméraire : X > 'Faces'."
            ]
        })

    active_nm = [it for it in facts.get("non_manifold_items", []) if not _is_intentional("topo_non_manifold", str(it.get("item_id", it.get("index", "0"))), len(facts.get("non_manifold_items", [])), intentional_finding_ids)]
    if len(active_nm) > 0 and len(active_walls) == 0:
        f_nm_focus = "topo_non_manifold" if len(facts.get("non_manifold_items", [])) == 1 else f"topo_non_manifold:{active_nm[0]['item_id']}"
        raw_rec_risky.append({
            "id": "rec_risky_non_manifold",
            "title": "Arêtes non-manifold complexes",
            "problem": f"{len(active_nm)} arête(s) connectée(s) à 3 faces ou plus sans cellule fermée",
            "zone": "Lignes de jonction non conformes",
            "effect": "Rend le maillage non-étanche (non-watertight). Inspection recommandée avant export ou impression",
            "data_impact": "Connectivité de surface",
            "reversibility": "Non altéré automatiquement",
            "confidence": "À vérifier manuellement",
            "operator": None,
            "focus_id": f_nm_focus,
            "manual_correction_steps": [
                "Mode Édition (Tab) > Sélection arêtes (2).",
                "Menu Sélectionner > Sélectionner par trait > Non-Manifold (Maj+Ctrl+Alt+M).",
                "Désactiver 'Frontière' pour cibler uniquement les jonctions internes.",
                "Dissoudre les arêtes intérieures (X > 'Dissoudre les arêtes') ou scinder (V)."
            ]
        })

    rec_risky.extend(raw_rec_risky)

    # Éléments intentionnels non conformes avec sévérité RISK (points de vigilance sous objectif strict)
    for f in findings:
        if getattr(f, "is_intentional", False) and getattr(f, "severity", "") == "RISK":
            rec_risky.append({
                "id": f"rec_risky_intentional_{f.id.replace(':', '_')}",
                "title": f.name,
                "problem": f.explanation,
                "zone": "Géométrie validée intentionnelle mais non conforme à l'objectif actif",
                "effect": "Attention : cette géométrie voulue empêche la conformité stricte de l'asset (ex: étanchéité ou topologie).",
                "data_impact": "Préservé conformément à votre choix",
                "reversibility": "Réversible (Désélectionner le marquage intentionnel)",
                "confidence": "Vigilance requise",
                "operator": None,
                "focus_id": f.id,
                "is_intentional": True
            })

    # 7.4 Catégorie 4 : Observations sans action requise
    # Éléments intentionnels conformes (severity OBSERVATION)
    for f in findings:
        if getattr(f, "is_intentional", False) and getattr(f, "severity", "") == "OBSERVATION":
            rec_observations.append({
                "id": f"obs_intentional_{f.id.replace(':', '_')}",
                "title": f.name,
                "problem": f.explanation,
                "zone": "Géométrie validée intentionnelle",
                "effect": "Conservé tel quel. Exclu du calcul des erreurs.",
                "data_impact": "Non altéré",
                "reversibility": "Réversible (Désélectionner le marquage intentionnel)",
                "confidence": "Validé intentionnel",
                "is_intentional": True,
                "focus_id": f.id
            })

    # Validations réinitialisées / purgées
    if pruned:
        rec_observations.append({
            "id": "obs_pruned_validations",
            "title": "Validations réinitialisées après modification",
            "problem": f"{len(pruned)} validation(s) intentionnelle(s) réinitialisées (géométrie modifiée ou résolue)",
            "zone": "Éléments précédemment validés",
            "effect": "Nettoyage automatique du cache pour éviter toute validation obsolète ou silencieuse",
            "data_impact": "Sécurité garantie : aucune validation douteuse n'est conservée",
            "reversibility": "Re-valider si la nouvelle géométrie est intentionnelle",
            "confidence": "Contrôlé",
            "is_intentional": False
        })

    quad_ratio = (facts['quads_count'] / max(1, facts['polygon_count'])) * 100.0
    rec_observations.append({
        "id": "obs_quads",
        "title": "Structure polygonale",
        "problem": f"{facts['quads_count']:,} quads ({quad_ratio:.1f}%), {facts['tris_count']:,} triangles, {facts['total_ngons']:,} N-gones",
        "zone": "Ensemble du maillage",
        "effect": "Topologie actuelle inventoriée. Aucune altération requise",
        "data_impact": "Aucun impact",
        "reversibility": "Sans objet",
        "confidence": "Informatif"
    })

    if facts["uv_layer_count"] > 0:
        rec_observations.append({
            "id": "obs_uvs",
            "title": "Coordonnées de texture UV",
            "problem": f"{facts['uv_layer_count']} couche(s) UV active(s) ({', '.join(facts['uv_layer_names'])})",
            "zone": "Attributs UV de l'objet",
            "effect": "Préservation active garantie sur tous les opérateurs MeshForge",
            "data_impact": "Protégé",
            "reversibility": "Sans objet",
            "confidence": "Conforme"
        })
    else:
        rec_observations.append({
            "id": "obs_uvs_none",
            "title": "Couches de texture UV",
            "problem": "Aucune couche UV détectée",
            "zone": "Attributs d'objet",
            "effect": "Un dépliage sera nécessaire avant texturage ou baking",
            "data_impact": "Information",
            "reversibility": "Sans objet",
            "confidence": "Informatif"
        })

    if resolved_profile == "MECHANICAL_CAD" and facts["ngons_convex_count"] > 0 and not quads_only:
        rec_observations.append({
            "id": "obs_cad_ngons",
            "title": "N-gones plans en CAO",
            "problem": f"{facts['ngons_convex_count']} N-gone(s) convexe(s) plan(s)",
            "zone": "Surfaces d'appui planes",
            "effect": "Faces planes standard en modélisation industrielle / hard-surface : conservation recommandée",
            "data_impact": "Non modifié",
            "reversibility": "Sans objet",
            "confidence": "Conforme CAO"
        })

    if resolved_profile == "SCULPTED_ORGANIC":
        rec_observations.append({
            "id": "obs_sculpt_density",
            "title": "Densité de sculpture préservée",
            "problem": f"{facts['real_triangles']:,} triangles réels",
            "zone": "Courbures organiques fines",
            "effect": "La haute densité restitue les micro-détails sculptés. Aucune décimation automatique par défaut",
            "data_impact": "Non altéré",
            "reversibility": "Sans objet",
            "confidence": "Conforme sculpture"
        })

    # Compteurs par sévérité (exclut formellement les constats marqués intentionnels)
    defects_count = sum(1 for f in findings if f.severity == "DEFECT")
    risks_count = sum(1 for f in findings if f.severity == "RISK")
    obs_count = sum(1 for f in findings if f.severity == "OBSERVATION")

    health_status = "HEALTHY"
    if defects_count > 0:
        health_status = "CRITICAL"
    elif risks_count > 0:
        health_status = "WARNING"

    return {
        "valid": True,
        "object_name": facts.get("object_name", ""),
        "profile": p_info,
        "profile_id": resolved_profile,
        "health": {
            "status": health_status,
            "defects_count": defects_count,
            "risks_count": risks_count,
            "observations_count": obs_count,
            "total_findings": len(findings)
        },
        "summary_counts": {
            "defects": defects_count,
            "risks": risks_count,
            "observations": obs_count,
            "total_findings": len(findings)
        },
        "findings": [f.to_dict() for f in findings],
        "recommended_actions": recommended_actions,
        "recommendation_groups": {
            "conservative": rec_conservative,
            "targeted": rec_targeted,
            "risky": rec_risky,
            "observations": rec_observations
        }
    }
