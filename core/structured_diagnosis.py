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
        "name": "Asset de jeu",
        "icon": 'PLAY',
        "summary": "Moteur temps réel (Unity, Unreal, Godot). Triangles, budget et UVs.",
        "description": (
            "Priorité à la performance temps réel : absence totale de N-gones (découpe recommandée), "
            "budget de triangles maîtrisé, coordonnées UV rigoureusement préservées et zéro face nulle."
        )
    },
    "DEFORMABLE_CHAR": {
        "id": "DEFORMABLE_CHAR",
        "name": "Personnage déformable",
        "icon": 'OUTLINER_OB_ARMATURE',
        "summary": "Animation et rigging. Topologie en quadrilatères réguliers et boucles d'arêtes.",
        "description": (
            "Priorité à la déformation : géométrie pure quads, alignement des edge loops aux articulations, "
            "alerte sur les N-gones et triangles coupant les boucles, et surveillance des pôles à haute valence."
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
    "MECHANICAL_CAD": {
        "id": "MECHANICAL_CAD",
        "name": "Objet mécanique ou assemblage",
        "icon": 'TOOL_SETTINGS',
        "summary": "Pièces industrielles et hard-surface. Arêtes vives, faces planes et pièces multiples.",
        "description": (
            "Priorité aux cotes et surfaces planes : les N-gones plans réguliers sont acceptés. "
            "Élimination stricte des micro-arêtes booléennes, des parois internes et des doublons."
        )
    }
}

# Compatibilité descendante pour les anciens identifiants
PROFILE_ALIAS = {
    "HYBRID_CLEANUP": "GENERAL",
    "GAME_TRIANGLES": "GAME_ASSET",
    "DEFORMABLE_QUADS": "DEFORMABLE_CHAR"
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
        refusal_reason: Optional[str] = None
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
            "refusal_reason": self.refusal_reason
        }


def measure_mesh_facts(obj: bpy.types.Object) -> Dict[str, Any]:
    """Mesure objectivement et exhaustivement toutes les caractéristiques géométriques et topologiques
    du maillage, de façon 100% neutre et indépendante du profil utilisateur choisi.
    Ces faits sont calculés une seule fois et mis en cache.
    """
    if not obj or obj.type != 'MESH' or not obj.data:
        return {"valid": False, "error": "Objet invalide ou non-maillage."}

    mesh = obj.data
    mesh.calc_loop_triangles()
    real_triangles = len(mesh.loop_triangles) if hasattr(mesh, "loop_triangles") else sum(max(0, len(p.vertices) - 2) for p in mesh.polygons)

    v_coords = np.array([v.co for v in mesh.vertices], dtype=np.float64)
    if len(v_coords) == 0:
        return {
            "valid": True,
            "is_empty": True,
            "object_name": obj.name,
            "vertex_count": 0,
            "edge_count": 0,
            "polygon_count": 0,
            "real_triangles": 0,
            "bbox_span": (0.0, 0.0, 0.0),
            "bbox_diameter": 0.0
        }

    local_min = np.min(v_coords, axis=0)
    local_max = np.max(v_coords, axis=0)
    span = local_max - local_min
    bbox_diameter = max(1e-6, float(np.linalg.norm(span)))
    micro_edge_threshold = max(1e-6, bbox_diameter * 1e-4)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # 1. Analyse des faces par valence
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

        v_count = len(f.verts)
        if v_count == 3:
            tris.append(f)
            # Calcul du rapport d'aspect
            edge_lens = [e.calc_length() for e in f.edges]
            max_l = max(edge_lens) if edge_lens else 1.0
            min_l = min(edge_lens) if edge_lens else 1.0
            aspect = max_l / max(1e-7, min_l)
            if aspect > 8.0:
                needle_triangles.append((f, aspect))
        elif v_count == 4:
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

    # 2. Analyse des arêtes
    wire_edges = [e for e in bm.edges if not e.link_faces]
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    non_manifold_edges = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
    micro_edges = [e for e in bm.edges if e.calc_length() <= micro_edge_threshold and not e.is_boundary]

    # 2.b Analyse des parois internes et jonctions en T (D2.4)
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

    # 3. Analyse des sommets
    loose_verts = [v for v in bm.verts if not v.link_edges]
    poles_valence_3 = []
    poles_valence_5 = []
    poles_valence_6_plus = []

    for v in bm.verts:
        val = len(v.link_edges)
        if not v.is_boundary:
            if val == 3:
                poles_valence_3.append(v)
            elif val == 5:
                poles_valence_5.append(v)
            elif val >= 6:
                poles_valence_6_plus.append(v)

    # 4. Analyse des composantes connexes (îlots)
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

    # 5. Attributs externes (UVs, matériaux, groupes)
    uv_layer_names = [l.name for l in mesh.uv_layers]
    material_names = [m.name for m in mesh.materials if m]
    vertex_group_names = [vg.name for vg in obj.vertex_groups]
    has_custom_normals = bool(mesh.has_custom_normals)
    has_seams = any(e.use_seam for e in mesh.edges)
    has_sharp = any(e.use_edge_sharp for e in mesh.edges)

    facts = {
        "valid": True,
        "is_empty": False,
        "object_name": obj.name,
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "polygon_count": len(mesh.polygons),
        "real_triangles": real_triangles,
        "bbox_span": tuple(span),
        "bbox_diameter": bbox_diameter,
        "micro_edge_threshold": micro_edge_threshold,
        # Faces
        "tris_count": len(tris),
        "quads_count": len(quads),
        "ngons_convex_count": len(ngons_convex),
        "ngons_concave_count": len(ngons_concave),
        "ngons_ambiguous_count": len(ngons_ambiguous),
        "total_ngons": len(ngons_convex) + len(ngons_concave) + len(ngons_ambiguous),
        "zero_area_faces_count": len(zero_area_faces),
        "zero_area_face_indices": [f.index for f in zero_area_faces],
        "zero_area_face_center": tuple(zero_area_faces[0].calc_center_bounds()) if zero_area_faces else (0, 0, 0),
        "needle_triangles_count": len(needle_triangles),
        "needle_triangle_indices": [f.index for f, _ in needle_triangles[:50]],
        "needle_max_aspect": max([asp for _, asp in needle_triangles], default=1.0),
        # N-gones détails
        "ngon_convex_indices": [f.index for f in ngons_convex[:50]],
        "ngon_concave_indices": [f.index for f in ngons_concave[:50]],
        "ngon_ambiguous_indices": [f.index for f in ngons_ambiguous[:50]],
        "ngon_convex_center": tuple(ngons_convex[0].calc_center_bounds()) if ngons_convex else (0, 0, 0),
        "ngon_concave_center": tuple(ngons_concave[0].calc_center_bounds()) if ngons_concave else (0, 0, 0),
        "ngon_ambiguous_center": tuple(ngons_ambiguous[0].calc_center_bounds()) if ngons_ambiguous else (0, 0, 0),
        # Arêtes
        "wire_edges_count": len(wire_edges),
        "wire_edge_indices": [e.index for e in wire_edges[:50]],
        "wire_edge_center": tuple((wire_edges[0].verts[0].co + wire_edges[0].verts[1].co) * 0.5) if wire_edges else (0, 0, 0),
        "boundary_edges_count": len(boundary_edges),
        "is_open_mesh": len(boundary_edges) > 0,
        "non_manifold_edges_count": len(non_manifold_edges),
        "non_manifold_edge_indices": [e.index for e in non_manifold_edges[:50]],
        "non_manifold_edge_center": tuple((non_manifold_edges[0].verts[0].co + non_manifold_edges[0].verts[1].co) * 0.5) if non_manifold_edges else (0, 0, 0),
        "internal_walls_count": len(strict_internal_faces),
        "internal_wall_indices": strict_internal_faces,
        "internal_wall_center": strict_wall_center,
        "t_junctions_count": len(t_junction_faces),
        "t_junction_indices": t_junction_faces,
        "complex_junctions_count": len(complex_junction_faces),
        "micro_edges_count": len(micro_edges),
        "micro_edge_indices": [e.index for e in micro_edges[:50]],
        "micro_edge_center": tuple((micro_edges[0].verts[0].co + micro_edges[0].verts[1].co) * 0.5) if micro_edges else (0, 0, 0),
        # Sommets
        "loose_verts_count": len(loose_verts),
        "loose_vert_indices": [v.index for v in loose_verts[:50]],
        "loose_vert_center": tuple(loose_verts[0].co) if loose_verts else (0, 0, 0),
        "poles_valence_3_count": len(poles_valence_3),
        "poles_valence_5_count": len(poles_valence_5),
        "poles_valence_6_plus_count": len(poles_valence_6_plus),
        "poles_6_plus_indices": [v.index for v in poles_valence_6_plus[:50]],
        "poles_6_plus_center": tuple(poles_valence_6_plus[0].co) if poles_valence_6_plus else (0, 0, 0),
        # Composantes
        "components_count": len(components),
        "minor_components_count": sum(1 for c in components if len(c) < max(len(comp) for comp in components) * 0.05) if components else 0,
        # Données
        "uv_layer_count": len(uv_layer_names),
        "uv_layer_names": uv_layer_names,
        "material_slot_count": len(material_names),
        "material_names": material_names,
        "vertex_group_count": len(vertex_group_names),
        "has_custom_normals": has_custom_normals,
        "has_seams": has_seams,
        "has_sharp": has_sharp
    }

    bm.free()
    return facts


def evaluate_structured_diagnosis(
    facts: Dict[str, Any],
    profile_id: str = "GENERAL"
) -> Dict[str, Any]:
    """Évalue instantanément les faits géométriques selon les règles du profil choisi.
    Produit la liste hiérarchisée des constats (DEFECT, RISK, OBSERVATION)
    et les recommandations ciblées sans recalcul géométrique lourd.
    """
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
            "summary_counts": {"defects": 1, "risks": 0, "observations": 0}
        }

    findings: List[DiagnosticFinding] = []
    recommended_actions: List[Dict[str, Any]] = []

    # =========================================================================
    # 1. GÉOMÉTRIE & DÉGÉNÉRESCENCES (Priorité absolue sur tous les profils)
    # =========================================================================

    # 1.1 Faces d'aire nulle
    if facts["zero_area_faces_count"] > 0:
        findings.append(DiagnosticFinding(
            finding_id="geom_zero_area_faces",
            category="GEOMETRY",
            name=f"Faces d'aire nulle ({facts['zero_area_faces_count']})",
            severity="DEFECT",
            count=facts["zero_area_faces_count"],
            element_type="FACE",
            indices=facts["zero_area_face_indices"],
            center=facts["zero_area_face_center"],
            explanation="Faces plates ou repliées sans surface mesurable (aire <= 1e-7 m²).",
            consequence="Provoquent des divisions par zéro lors du calcul des normales, des NaN et des erreurs de rendu.",
            recommendation="Dissoudre ces faces dégénérées via le nettoyage conservateur.",
            compatible_action="meshforge.conservative_clean",
            action_name="Nettoyage conservateur sûr",
            action_risk="Risque Faible"
        ))

    # 1.2 Sommets orphelins (Loose verts)
    if facts["loose_verts_count"] > 0:
        findings.append(DiagnosticFinding(
            finding_id="geom_loose_verts",
            category="GEOMETRY",
            name=f"Sommets orphelins ({facts['loose_verts_count']})",
            severity="DEFECT",
            count=facts["loose_verts_count"],
            element_type="VERT",
            indices=facts["loose_vert_indices"],
            center=facts["loose_vert_center"],
            explanation="Sommets flottant dans l'espace sans arête ni face connectée.",
            consequence="Alourdissent inutilement les buffers GPU et faussent la boîte englobante.",
            recommendation="Supprimer les sommets orphelins.",
            compatible_action="meshforge.conservative_clean",
            action_name="Nettoyage conservateur sûr",
            action_risk="Risque Nul"
        ))

    # 1.3 Arêtes minuscules
    if facts["micro_edges_count"] > 0:
        # Sévérité selon le profil : DEFECT en mécanique/CAD, RISK sur les autres
        sev = "DEFECT" if resolved_profile == "MECHANICAL_CAD" else "RISK"
        findings.append(DiagnosticFinding(
            finding_id="geom_micro_edges",
            category="GEOMETRY",
            name=f"Arêtes minuscules ({facts['micro_edges_count']})",
            severity=sev,
            count=facts["micro_edges_count"],
            metric_value=facts["micro_edge_threshold"] * 1000.0,
            metric_unit="mm (seuil)",
            element_type="EDGE",
            indices=facts["micro_edge_indices"],
            center=facts["micro_edge_center"],
            explanation=f"Arêtes exceptionnellement courtes par rapport à l'échelle de l'objet (seuil {facts['micro_edge_threshold']*1000:.2f} mm).",
            consequence="Souvent issues de booléens imprécis ou de doubles extrusions. Risquent de créer des aiguilles.",
            recommendation="Fusionner les sommets doublons si ce n'est pas un micro-chanfrein intentionnel.",
            compatible_action="meshforge.conservative_clean",
            action_name="Nettoyage conservateur sûr",
            action_risk="Risque Modéré"
        ))

    # =========================================================================
    # 2. TOPOLOGIE & CONNECTIVITÉ
    # =========================================================================

    # 2.1 Arêtes filaires sans face
    if facts["wire_edges_count"] > 0:
        findings.append(DiagnosticFinding(
            finding_id="topo_wire_edges",
            category="TOPOLOGY",
            name=f"Arêtes filaires sans face ({facts['wire_edges_count']})",
            severity="DEFECT" if resolved_profile in ("GAME_ASSET", "MECHANICAL_CAD") else "RISK",
            count=facts["wire_edges_count"],
            element_type="EDGE",
            indices=facts["wire_edge_indices"],
            center=facts["wire_edge_center"],
            explanation="Segments d'arêtes isolés ne délimitant aucune face polygonale.",
            consequence="Invisibles en rendu de surface mais génèrent des erreurs d'export et d'occlusion.",
            recommendation="Supprimer les arêtes filaires.",
            compatible_action="meshforge.conservative_clean",
            action_name="Nettoyage conservateur sûr",
            action_risk="Risque Faible"
        ))

    # 2.2 Parois internes mitoyennes et jonctions en T (D2.4)
    if facts.get("internal_walls_count", 0) > 0:
        findings.append(DiagnosticFinding(
            finding_id="topo_internal_walls",
            category="TOPOLOGY",
            name=f"Parois internes mitoyennes ({facts['internal_walls_count']} faces)",
            severity="DEFECT" if resolved_profile in ("GAME_ASSET", "MECHANICAL_CAD") else "RISK",
            count=facts["internal_walls_count"],
            element_type="FACE",
            indices=facts["internal_wall_indices"],
            center=facts.get("internal_wall_center"),
            explanation=f"{facts['internal_walls_count']} face(s) mitoyenne(s) occluses séparant des cellules fermées. Leur suppression guérit la non-manifoldité sans ouvrir de trou.",
            consequence="Rend l'objet non-étanche, interdit l'impression 3D, gaspille du budget polygonal et perturbe le baking.",
            recommendation="Supprimer les parois internes après confirmation.",
            compatible_action="meshforge.remove_internal_walls",
            action_name="Supprimer les parois internes",
            action_risk="Risque Contrôlé"
        ))

    if facts.get("t_junctions_count", 0) > 0:
        findings.append(DiagnosticFinding(
            finding_id="topo_t_junctions",
            category="TOPOLOGY",
            name=f"Jonctions de surface / Ailerons ({facts['t_junctions_count']} faces)",
            severity="RISK" if resolved_profile == "MECHANICAL_CAD" else "OBSERVATION",
            count=facts["t_junctions_count"],
            element_type="FACE",
            indices=facts["t_junction_indices"],
            explanation="Surfaces rattachées formant une jonction en T (ex: aileron ou cloison ouverte). Surface potentiellement intentionnelle : aucune suppression automatique.",
            consequence="Arête partagée par 3 faces. Non-étanche pour l'impression 3D, mais peut être normale sur un décor ou un vêtement.",
            recommendation="Conserver si l'aileron est voulu, ou séparer les surfaces en mode Édition."
        ))

    # 2.2b Arêtes non-manifold résiduelles
    if facts["non_manifold_edges_count"] > 0 and facts.get("internal_walls_count", 0) == 0:
        findings.append(DiagnosticFinding(
            finding_id="topo_non_manifold",
            category="TOPOLOGY",
            name=f"Arêtes non-manifold ({facts['non_manifold_edges_count']})",
            severity="DEFECT",
            count=facts["non_manifold_edges_count"],
            element_type="EDGE",
            indices=facts["non_manifold_edge_indices"],
            center=facts["non_manifold_edge_center"],
            explanation="Arêtes partagées par plus de 2 faces (jonction en T ou intersection complexe).",
            consequence="Rend l'objet non-étanche (non-watertight), interdit l'impression 3D et perturbe le baking.",
            recommendation="Inspecter en mode Édition ou scinder les surfaces."
        ))

    # 2.3 Frontières ouvertes (Mesh ouvert / Tissu)
    if facts["is_open_mesh"]:
        # Pour un asset mécanique c'est un risque, pour un tissu ou vêtement c'est une observation normale
        sev = "RISK" if resolved_profile == "MECHANICAL_CAD" else "OBSERVATION"
        findings.append(DiagnosticFinding(
            finding_id="topo_open_boundary",
            category="TOPOLOGY",
            name=f"Frontière ouverte ({facts['boundary_edges_count']} arêtes de bord)",
            severity=sev,
            count=facts["boundary_edges_count"],
            element_type="EDGE",
            explanation="Le maillage possède un ou plusieurs bords ouverts (surface non fermée).",
            consequence="Normal pour un plan, une nappe de tissu ou un vêtement. Inadapté si une pièce pleine est attendue.",
            recommendation="Vérifier si le modèle est censé être un volume fermé solide."
        ))

    # 2.4 N-gones (Convexes, Concaves, Ambigus) - INTERPRÉTATION STRICTEMENT SELON PROFIL
    if facts["total_ngons"] > 0:
        # A. Cas ambigus (Bow-tie / Torsion extrême) : DEFECT partout !
        if facts["ngons_ambiguous_count"] > 0:
            findings.append(DiagnosticFinding(
                finding_id="topo_ngons_ambiguous",
                category="TOPOLOGY",
                name=f"N-gones ambigus / auto-intersectants ({facts['ngons_ambiguous_count']})",
                severity="DEFECT",
                count=facts["ngons_ambiguous_count"],
                element_type="FACE",
                indices=facts["ngon_ambiguous_indices"],
                center=facts["ngon_ambiguous_center"],
                explanation="Polygones dont les arêtes se croisent en 8 (nœud papillon) ou fortement gauchis en selle.",
                consequence="Toute triangulation automatique produit des faces retournées et des traits noirs d'ombrage.",
                recommendation="Sélectionnés pour découpe manuelle au couteau (K en mode Édition).",
                refusal_reason="Refus automatique de découpe pour éviter la création de faces inversées."
            ))

        # B. Cas concaves (Angles rentrants > 180°)
        if facts["ngons_concave_count"] > 0:
            sev = "DEFECT" if resolved_profile == "GAME_ASSET" else ("RISK" if resolved_profile == "DEFORMABLE_CHAR" else "WARNING")
            findings.append(DiagnosticFinding(
                finding_id="topo_ngons_concave",
                category="TOPOLOGY",
                name=f"N-gones concaves ({facts['ngons_concave_count']})",
                severity="RISK" if resolved_profile != "GAME_ASSET" else "DEFECT",
                count=facts["ngons_concave_count"],
                element_type="FACE",
                indices=facts["ngon_concave_indices"],
                center=facts["ngon_concave_center"],
                explanation="Faces à plus de 4 côtés comportant des angles rentrants (concavité).",
                consequence="La triangulation naïve en éventail chevaucherait la surface. Nécessite un Ear-Clipping orienté.",
                recommendation="Découper les N-gones (Ear-Clipping sécurisé).",
                compatible_action="meshforge.cut_ngons",
                action_name="Découper les N-gones",
                action_risk="Risque Contrôlé"
            ))

        # C. Cas convexes réguliers
        if facts["ngons_convex_count"] > 0:
            if resolved_profile == "GAME_ASSET":
                sev = "DEFECT"
                exp = "Les moteurs de jeu (Unity, Unreal) exigent une triangulation ou des quads. Les N-gones sont à proscrire."
                rec = "Découper les N-gones en triangles équilibrés (Beauty)."
                act = "meshforge.cut_ngons"
            elif resolved_profile == "DEFORMABLE_CHAR":
                sev = "RISK"
                exp = "Les N-gones interrompent les boucles de quads (edge loops) nécessaires aux déformations d'articulation."
                rec = "Convertir en quads pour préserver la fluidité de déformation."
                act = "meshforge.cut_ngons"
            elif resolved_profile == "MECHANICAL_CAD":
                sev = "OBSERVATION"
                exp = "Face plane régulière à plus de 4 sommets. Courant et toléré sur les surfaces d'appui plates en CAD."
                rec = "Conservation possible si la face reste parfaitement plane."
                act = None
            else:  # GENERAL & SCULPTED_ORGANIC
                sev = "OBSERVATION"
                exp = f"Face convexe à plus de 4 sommets. Ne pose pas de problème immédiat hors animation ou export temps réel."
                rec = "Découpe recommandée uniquement si vous prévoyez une subdivision ou un export jeu."
                act = "meshforge.cut_ngons"

            findings.append(DiagnosticFinding(
                finding_id="topo_ngons_convex",
                category="TOPOLOGY",
                name=f"N-gones convexes ({facts['ngons_convex_count']})",
                severity=sev,
                count=facts["ngons_convex_count"],
                element_type="FACE",
                indices=facts["ngon_convex_indices"],
                center=facts["ngon_convex_center"],
                explanation=exp,
                consequence="Comportement variable selon l'usage final de l'objet.",
                recommendation=rec,
                compatible_action=act,
                action_name="Découper les N-gones" if act else "",
                action_risk="Risque Contrôlé" if act else ""
            ))

    # =========================================================================
    # 3. SILHOUETTE & QUALITÉ DE SURFACE
    # =========================================================================

    # 3.1 Triangles très étirés (Needles / Aiguilles)
    if facts["needle_triangles_count"] > 0:
        sev = "RISK" if resolved_profile in ("GAME_ASSET", "SCULPTED_ORGANIC") else "OBSERVATION"
        findings.append(DiagnosticFinding(
            finding_id="surface_needle_triangles",
            category="SURFACE",
            name=f"Triangles très étirés ({facts['needle_triangles_count']})",
            severity=sev,
            count=facts["needle_triangles_count"],
            metric_value=facts["needle_max_aspect"],
            metric_unit=":1 (ratio max)",
            element_type="FACE",
            indices=facts["needle_triangle_indices"],
            explanation=f"Triangles présentant un ratio de côtés supérieur à 8:1 (max mesuré {facts['needle_max_aspect']:.1f}:1).",
            consequence="Dégradent le Smooth Shading et provoquent des balafres noires (artefact du Normal Terminator).",
            recommendation="Équilibrer les arêtes ou éviter la décimation native non contrainte."
        ))

    # =========================================================================
    # 4. PRÉPARATION À LA DÉFORMATION (Animation / Rigging)
    # =========================================================================

    if resolved_profile == "DEFORMABLE_CHAR":
        # 4.1 Triangles isolés au milieu de quads
        if facts["tris_count"] > 0:
            findings.append(DiagnosticFinding(
                finding_id="deform_tris_in_quads",
                category="DEFORMATION",
                name=f"Triangles dans un maillage quad ({facts['tris_count']})",
                severity="RISK",
                count=facts["tris_count"],
                element_type="FACE",
                explanation=f"Le maillage contient {facts['tris_count']} triangle(s) au milieu de {facts['quads_count']} quad(s).",
                consequence="Un triangle interrompt la trajectoire d'une boucle d'arêtes (Edge Loop) et peut créer un pli rigide au pliage.",
                recommendation="Fusionner les paires de triangles coplanaires en quads réguliers (Quadrangulation ciblée).",
                compatible_action="meshforge.quadrangulate",
                action_name="Quadrangulation ciblée",
                action_risk="Risque Faible"
            ))

        # 4.2 Pôles à haute valence (valence >= 6)
        if facts["poles_valence_6_plus_count"] > 0:
            findings.append(DiagnosticFinding(
                finding_id="deform_high_valence_poles",
                category="DEFORMATION",
                name=f"Pôles complexes valence >= 6 ({facts['poles_valence_6_plus_count']})",
                severity="RISK",
                count=facts["poles_valence_6_plus_count"],
                element_type="VERT",
                indices=facts["poles_6_plus_indices"],
                center=facts["poles_6_plus_center"],
                explanation=f"{facts['poles_valence_6_plus_count']} sommet(s) intérieur(s) connectent 6 arêtes ou plus.",
                consequence="Les pôles à haute valence provoquent des plis en étoile et des déformations chaotiques sous l'influence des os.",
                recommendation="Rediriger les arêtes pour scinder les pôles en valences 4 ou 5."
            ))

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
            explanation="L'objet ne possède aucune couche de coordonnées de texture UV.",
            consequence="Impossible d'appliquer des textures 2D peintes ou de faire un baking de normales.",
            recommendation="Effectuer un dépliage UV (U dans la vue 3D)."
        ))
    else:
        findings.append(DiagnosticFinding(
            finding_id="uv_present_info",
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
    # 7. SÉLECTION ET PRIORISATION DES ACTIONS RECOMMANDÉES (Phase UX5)
    # =========================================================================

    # Règle d'or de MeshForge : Maximum 2 actions prioritaires sur l'écran d'accueil,
    # avec explication du risque et justification formelle.

    # Action 1 : Nettoyage conservateur sûr (si orphelins, faces nulles, arêtes filaires)
    has_conservative_clean_needs = (
        facts["zero_area_faces_count"] > 0 or
        facts["loose_verts_count"] > 0 or
        facts["wire_edges_count"] > 0 or
        (facts["micro_edges_count"] > 0 and resolved_profile == "MECHANICAL_CAD")
    )
    if has_conservative_clean_needs:
        reasons = []
        if facts["zero_area_faces_count"] > 0:
            reasons.append(f"{facts['zero_area_faces_count']} face(s) d'aire nulle")
        if facts["loose_verts_count"] > 0:
            reasons.append(f"{facts['loose_verts_count']} sommet(s) orphelin(s)")
        if facts["wire_edges_count"] > 0:
            reasons.append(f"{facts['wire_edges_count']} arête(s) filaire(s)")

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

    # Action 2 : Découpe des N-gones (uniquement si justifiée pour le profil)
    should_cut_ngons = (
        (facts["ngons_concave_count"] > 0) or
        (facts["ngons_convex_count"] > 0 and resolved_profile in ("GAME_ASSET", "DEFORMABLE_CHAR"))
    )
    if should_cut_ngons:
        reasons = []
        if facts["ngons_concave_count"] > 0:
            reasons.append(f"{facts['ngons_concave_count']} N-gone(s) concave(s)")
        if facts["ngons_convex_count"] > 0 and resolved_profile in ("GAME_ASSET", "DEFORMABLE_CHAR"):
            reasons.append(f"{facts['ngons_convex_count']} N-gone(s) pour profil {p_info['name']}")

        recommended_actions.append({
            "id": "cut_ngons",
            "operator": "meshforge.cut_ngons",
            "label": f"Découper les N-gones ({facts['total_ngons']})",
            "icon": 'MOD_TRIANGULATE',
            "risk_badge": "[Risque Contrôlé]",
            "risk_level": "CONTROLLED",
            "justification": f"Résout : {', '.join(reasons)}.",
            "data_impact": "Triangulation Beauty / Ear-Clipping. Préserve les UVs et matériaux.",
            "safety_note": f"Les cas ambigus ({facts['ngons_ambiguous_count']}) sont refusés et isolés pour découpe manuelle."
        })

    # Action 3 : Quadrangulation ciblée (si paires de triangles coplanaires et profil adapté)
    should_quadrangulate = (
        facts["tris_count"] >= 2 and
        resolved_profile in ("DEFORMABLE_CHAR", "HARD_SURFACE", "GENERAL") and
        len(recommended_actions) < 3
    )
    if should_quadrangulate:
        recommended_actions.append({
            "id": "quadrangulate",
            "operator": "meshforge.quadrangulate",
            "label": f"Quadranguler les triangles coplanaires ({facts['tris_count']} tris)",
            "icon": 'SNAP_FACE',
            "risk_badge": "[Risque Faible]",
            "risk_level": "LOW",
            "justification": f"Fusionne les paires de triangles coplanaires ({facts['tris_count']} triangles détectés) en quads réguliers.",
            "data_impact": "Préserve strictement les coutures UV, arêtes vives, matériaux et l'aire du maillage.",
            "safety_note": "Transaction réversible : rollback automatique en cas de déviation géométrique."
        })

    # Action 4 : Suppression des parois internes mitoyennes (D2.4)
    if facts.get("internal_walls_count", 0) > 0 and len(recommended_actions) < 3:
        recommended_actions.append({
            "id": "remove_internal_walls",
            "operator": "meshforge.remove_internal_walls",
            "label": f"Supprimer les parois internes ({facts['internal_walls_count']} faces)",
            "icon": 'X',
            "risk_badge": "[Risque Contrôlé]",
            "risk_level": "CONTROLLED",
            "justification": f"Élimine {facts['internal_walls_count']} face(s) mitoyenne(s) occluses pour restaurer un volume fermé manifold.",
            "data_impact": "Supprime les faces intérieures sans ouvrir de trou dans la coque externe.",
            "safety_note": "Confirmation explicite requise. Rollback automatique si déviation."
        })

    # Compteurs par sévérité
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
        "recommended_actions": recommended_actions
    }
