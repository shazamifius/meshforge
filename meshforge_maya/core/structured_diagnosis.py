"""MeshForge Maya - Structured Diagnosis and Recommendation Engine.
Evaluates mesh facts against the 8 asset target profiles and generates explainable recommendations.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
from typing import Dict, Any, List, Optional, Set, Tuple

# Categories matching MeshForge standard
CATEGORIES = {
    "GEOMETRY": {
        "id": "GEOMETRY",
        "name": "Geometry & Degeneracies",
        "description": "Zero-area faces, orphan vertices, tiny edges, and numerical integrity."
    },
    "TOPOLOGY": {
        "id": "TOPOLOGY",
        "name": "Topology & Connectivity",
        "description": "N-gons, non-manifold geometry, wire edges, internal walls, and disjoint shells."
    },
    "SURFACE": {
        "id": "SURFACE",
        "name": "Silhouette & Surface Quality",
        "description": "Sliver triangles, planarity, and local curvature."
    },
    "UV_MATERIAL": {
        "id": "UV_MATERIAL",
        "name": "UV & Materials",
        "description": "UV seams, texture borders, multiple material sets."
    },
    "NORMALS": {
        "id": "NORMALS",
        "name": "Normals & Shading",
        "description": "Hard edges, split normals, and shading continuity."
    },
    "DENSITY": {
        "id": "DENSITY",
        "name": "Density & Budget",
        "description": "Polygon count, triangle/quad ratios, and budget compliance."
    },
    "DEFORMATION": {
        "id": "DEFORMATION",
        "name": "Deformation Readiness",
        "description": "Quad loops for rigging, high-valence poles (>= 6), and blendshape safety."
    },
    "EXPORT": {
        "id": "EXPORT",
        "name": "Export & 3D Print Preparation",
        "description": "Watertightness, manifold compliance, and outer normal orientation."
    }
}

# The 8 Standard Profiles
PROFILES = {
    "GENERAL": {
        "id": "GENERAL",
        "name": "1. General Diagnostic — « I don't know »",
        "summary": "Neutral factual analysis. Only actual mathematical defects are flagged.",
        "description": "Ideal when the target use is not yet determined. N-gons or triangles are not flagged as defects."
    },
    "GAME_ASSET": {
        "id": "GAME_ASSET",
        "name": "2. Video Game & Real-Time",
        "summary": "Real-time engines (Unreal, Unity, Godot). Triangles, budget, and preserved UVs.",
        "description": "Zero N-gons allowed. Triangle budget strictly managed. UV borders rigorously preserved."
    },
    "RENDER_ANIM": {
        "id": "RENDER_ANIM",
        "name": "3. Render & Animation",
        "summary": "High quality sub-d rendering and clean shading. Quad-dominant topology.",
        "description": "Smooth subdivision surfaces. Flags pinching triangles and non-planar n-gons."
    },
    "DEFORMABLE_CHAR": {
        "id": "DEFORMABLE_CHAR",
        "name": "4. Deformable Character (Rigging)",
        "summary": "Animation and rigging. Clean quad loops along articulation joints.",
        "description": "Flags poles with valence >= 6, triangles interrupting quad loops, and blendshape risks."
    },
    "EXPORT_PREP": {
        "id": "EXPORT_PREP",
        "name": "5. Export Prep & 3D Printing",
        "summary": "Absolute watertight manifold closure. Zero internal walls. Outward normals.",
        "description": "Every boundary edge and non-manifold element is treated as a critical defect."
    },
    "MECHANICAL_CAD": {
        "id": "MECHANICAL_CAD",
        "name": "6. Mechanical or CAD Object",
        "summary": "Hard-surface and industrial parts. Planar n-gons allowed. Sharp edges and chamfers.",
        "description": "Preserves planar n-gons. Eliminates boolean micro-edges and internal divider walls."
    },
    "SCULPTED_ORGANIC": {
        "id": "SCULPTED_ORGANIC",
        "name": "7. Sculpted or Organic Model",
        "summary": "High-density sculpt. Strict curvature preservation. No aggressive flattening.",
        "description": "Recognizes dense triangle meshes as normal. Strictly avoids planar distortion."
    },
    "CUSTOM": {
        "id": "CUSTOM",
        "name": "8. Custom / Other Usage",
        "summary": "Custom combination with user constraints.",
        "description": "Configurable profile combined with strict manifold or quads-only constraints."
    }
}

class DiagnosticFinding:
    """Represents a structured geometric finding with 3D components and fix actions."""

    def __init__(
        self,
        finding_id: str,
        name: str,
        category: str,
        severity: str, # DEFECT, RISK, OBSERVATION
        explanation: str,
        consequence: str,
        recommendation: str,
        components: Optional[List[str]] = None,
        operator: Optional[str] = None,
        operator_text: Optional[str] = None,
        centroid: Optional[Tuple[float, float, float]] = None,
        manual_steps: Optional[List[str]] = None,
        is_intentional: bool = False
    ):
        self.id = finding_id
        self.name = name
        self.category = category
        self.severity = severity
        self.explanation = explanation
        self.consequence = consequence
        self.recommendation = recommendation
        if isinstance(components, (list, tuple, set)):
            self.components = list(components)
        else:
            self.components = []
        self.operator = operator
        self.operator_text = operator_text
        self.centroid = centroid or (0.0, 0.0, 0.0)
        self.manual_steps = manual_steps or []
        self.is_intentional = is_intentional

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "severity": self.severity,
            "explanation": self.explanation,
            "consequence": self.consequence,
            "recommendation": self.recommendation,
            "components_count": len(self.components),
            "components": self.components[:200], # preview sample
            "operator": self.operator,
            "operator_text": self.operator_text,
            "centroid": self.centroid,
            "manual_steps": self.manual_steps,
            "is_intentional": self.is_intentional
        }

def evaluate_mesh_diagnosis(
    obj_name: str,
    stats: Dict[str, Any],
    profile_id: str = "GENERAL",
    strict_manifold: bool = False,
    quads_only: bool = False,
    intentional_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Evaluates mesh statistics against a chosen profile and returns findings and recommendations."""
    intentional_set = set(intentional_ids or [])
    findings: List[DiagnosticFinding] = []

    # 1. Non-Manifold Edges & Vertices
    nm_edges = stats.get("non_manifold_edges_count", 0)
    nm_verts = stats.get("non_manifold_verts_count", 0)
    nm_comps = stats.get("non_manifold_edges_components", []) + stats.get("non_manifold_verts_components", [])

    if nm_edges > 0 or nm_verts > 0:
        is_int = ("topo_non_manifold" in intentional_set)
        sev = "RISK" if (is_int and not strict_manifold) else "DEFECT"
        findings.append(DiagnosticFinding(
            finding_id="topo_non_manifold",
            name=f"Non-Manifold Geometry ({nm_edges} edges, {nm_verts} vertices)",
            category="TOPOLOGY",
            severity=sev,
            explanation=f"Mesh has {nm_edges} non-manifold edges (shared by 3+ faces) or {nm_verts} non-manifold vertices.",
            consequence="Causes lighting artifacts, subdivision tearing, and crashes game physics engines or 3D slicers.",
            recommendation="Clean non-manifold elements or delete internal divider walls.",
            components=nm_comps,
            operator="remove_internal_walls",
            operator_text="Supprimer les parois internes",
            manual_steps=[
                "Select object, run 'Inspect Internal Walls' to check for internal divider faces.",
                "Or use Mesh > Cleanup > Non-manifold geometry in Maya."
            ],
            is_intentional=is_int
        ))

    # 2. Zero-Area Faces
    zero_faces = stats.get("zero_area_faces_count", 0)
    zero_comps = stats.get("zero_area_faces_components", [])
    if zero_faces > 0:
        is_int = ("geom_zero_faces" in intentional_set)
        findings.append(DiagnosticFinding(
            finding_id="geom_zero_faces",
            name=f"Zero-Area Faces ({zero_faces} faces)",
            category="GEOMETRY",
            severity="DEFECT",
            explanation=f"Detected {zero_faces} degenerate faces with near-zero surface area (<= 1e-7 m²).",
            consequence="Creates baking seams, raytracing NaN artifacts, and normal calculation division by zero.",
            recommendation="Execute Conservative Cleanup to safely dissolve zero-area faces.",
            components=zero_comps,
            operator="conservative_clean",
            operator_text="Nettoyer les dégénérescences",
            is_intentional=is_int
        ))

    # 3. Open Boundaries (Cloth vs Watertight)
    open_edges = stats.get("open_boundary_edges_count", 0)
    open_comps = stats.get("open_boundary_edges_components", [])
    if open_edges > 0:
        is_int = ("topo_open_boundary" in intentional_set)
        if profile_id == "EXPORT_PREP" or strict_manifold:
            sev = "DEFECT"
            conseq = "Model is not watertight (STL export and 3D printing require closed volumes)."
            rec = "Fill holes or extrude thickness before export."
        elif profile_id in ("SCULPTED_ORGANIC", "GENERAL"):
            sev = "OBSERVATION" if is_int else "RISK"
            conseq = "Mesh surface is open (normal for cloth, sheets, or terrain, but unexpected for solid objects)."
            rec = "Verify if openings are intentional (e.g. collar, sleeve hems) and mark as intentional if desired."
        else:
            sev = "OBSERVATION" if is_int else "RISK"
            conseq = "Open perimeter borders detected."
            rec = "Verify boundary loops."

        findings.append(DiagnosticFinding(
            finding_id="topo_open_boundary",
            name=f"Open Boundary Edges ({open_edges} border edges)",
            category="TOPOLOGY",
            severity=sev,
            explanation=f"Mesh has {open_edges} border edges with only 1 connected face.",
            consequence=conseq,
            recommendation=rec,
            components=open_comps,
            is_intentional=is_int
        ))

    # 4. N-Gons (5+ vertices)
    ngons = stats.get("ngons_count", 0)
    ngon_comps = stats.get("ngons_components", [])
    if ngons > 0:
        is_int = ("topo_ngons" in intentional_set)
        if profile_id == "GAME_ASSET":
            sev = "RISK" if is_int else "DEFECT"
            conseq = "Game engines triangulate n-gons arbitrarily at runtime, risking unpredictable shading and deformation."
            rec = "Execute Cut N-Gons to create balanced, predictable triangles."
        elif profile_id in ("RENDER_ANIM", "DEFORMABLE_CHAR") or quads_only:
            sev = "DEFECT" if quads_only else "RISK"
            conseq = "N-gons disrupt quad edge flow and cause pinching under subdivision surfaces."
            rec = "Convert N-gons into clean quads or beauty triangles."
        elif profile_id == "MECHANICAL_CAD":
            sev = "OBSERVATION"
            conseq = "Planar n-gons on CAD hard-surface models are acceptable."
            rec = "Keep planar n-gons if shading remains flat."
        else:
            sev = "OBSERVATION" if is_int else "RISK"
            conseq = "Faces with 5 or more vertices detected."
            rec = "Review n-gons or cut into triangles."

        findings.append(DiagnosticFinding(
            finding_id="topo_ngons",
            name=f"N-Gons ({ngons} faces with 5+ vertices)",
            category="TOPOLOGY",
            severity=sev,
            explanation=f"Found {ngons} polygons containing 5 or more vertices.",
            consequence=conseq,
            recommendation=rec,
            components=ngon_comps,
            operator="cut_ngons",
            operator_text="Découper les N-Gones",
            is_intentional=is_int
        ))

    # 5. Triangles in Quad-Only or Rigged Profiles
    tris = stats.get("tris_count", 0)
    tri_comps = stats.get("tris_components", [])
    if tris > 0 and (quads_only or profile_id == "DEFORMABLE_CHAR"):
        is_int = ("topo_triangles" in intentional_set)
        sev = "DEFECT" if quads_only else "RISK"
        findings.append(DiagnosticFinding(
            finding_id="topo_triangles",
            name=f"Triangles in Quad Workflow ({tris} tris)",
            category="TOPOLOGY",
            severity=sev,
            explanation=f"Detected {tris} triangular faces on a model requiring quad-dominant topology.",
            consequence="Triangles interrupt continuous quad loops needed for character rigging and clean joint bending.",
            recommendation="Run Quadrangulate (Tris -> Quads) to merge coplanar triangle pairs.",
            components=tri_comps,
            operator="quadrangulate",
            operator_text="Quadranguler les triangles",
            is_intentional=is_int
        ))

    # 6. Internal Walls
    iw_comps = stats.get("internal_walls_components", [])
    if iw_comps:
        findings.append(DiagnosticFinding(
            finding_id="topo_internal_walls",
            name=f"Internal Occluded Divider Walls ({len(iw_comps)} faces)",
            category="TOPOLOGY",
            severity="DEFECT" if profile_id == "EXPORT_PREP" else "RISK",
            explanation=f"Detected {len(iw_comps)} internal occluded divider faces inside closed geometry.",
            consequence="Causes non-manifold edges, disrupts boolean unions, and produces slicing errors in 3D printing.",
            recommendation="Inspect and delete occluded divider walls.",
            components=iw_comps,
            operator="remove_internal_walls",
            operator_text="Supprimer les parois internes"
        ))

    # 7. BlendShapes (Shape Keys) Notice
    if stats.get("has_blendshapes", False):
        findings.append(DiagnosticFinding(
            finding_id="deform_blendshapes",
            name=f"BlendShape Deformers ({len(stats['blendshape_nodes'])} nodes)",
            category="DEFORMATION",
            severity="RISK",
            explanation="Mesh is connected to BlendShape animation nodes.",
            consequence="Modifying mesh vertex indices will break blendshape morph targets on this object.",
            recommendation="Always decimate using a static duplicate copy with disconnected blendshape history.",
            manual_steps=[
                "Enable 'Create static copy without BlendShapes' before decimating.",
                "Original object with blendshapes will remain 100% intact."
            ]
        ))

    # 8. Disjoint Shells
    shells = stats.get("disjoint_shells_count", 1)
    if shells > 1:
        findings.append(DiagnosticFinding(
            finding_id="topo_disjoint_shells",
            name=f"Disjoint Mesh Shells ({shells} shells)",
            category="TOPOLOGY",
            severity="OBSERVATION",
            explanation=f"The mesh geometry is split into {shells} separate disconnected geometric islands.",
            consequence="Multiple floating components exist within a single transform.",
            recommendation="Verify if floating shells are deliberate (e.g. bolts, buttons, separate panels)."
        ))

    # Health status calculation
    defects = [f for f in findings if f.severity == "DEFECT"]
    risks = [f for f in findings if f.severity == "RISK"]
    obs = [f for f in findings if f.severity == "OBSERVATION"]

    if defects:
        status = "CRITICAL"
    elif risks:
        status = "RISKS"
    else:
        status = "HEALTHY"

    # Group Recommendations into the 4 Clean Categories
    rec_conservative = []
    rec_targeted = []
    rec_risky = []
    rec_observations = []

    # Category 1: Conservative Repairs (Safe)
    if zero_faces > 0:
        rec_conservative.append({
            "title": "Clean Zero-Area Faces",
            "confidence": "Safe",
            "problem": f"{zero_faces} degenerate zero-area faces detected.",
            "zone": "Entire mesh",
            "effect": "Dissolves corrupt faces without altering valid geometry.",
            "data_impact": "Zero attribute loss.",
            "reversibility": "100% Reversible via Snapshot.",
            "components": zero_comps,
            "operator": "conservative_clean",
            "operator_text": "Nettoyer les dégénérescences"
        })

    # Category 2: Targeted Optimizations
    if ngons > 0 and profile_id in ("GAME_ASSET", "RENDER_ANIM", "DEFORMABLE_CHAR"):
        rec_targeted.append({
            "title": "Cut N-Gons into Balanced Triangles",
            "confidence": "Recommended",
            "problem": f"{ngons} N-gons incompatible with {profile_id}.",
            "zone": "N-gon faces",
            "effect": "Triangulates convex and concave polygons while preserving UV boundaries.",
            "data_impact": "Preserves UVs and material assignments.",
            "reversibility": "Reversible via Snapshot.",
            "components": ngon_comps,
            "operator": "cut_ngons",
            "operator_text": "Découper les N-Gones"
        })
    if tris > 0 and (quads_only or profile_id == "DEFORMABLE_CHAR"):
        rec_targeted.append({
            "title": "Quadrangulate Triangles (Tris -> Quads)",
            "confidence": "Recommended",
            "problem": f"{tris} triangles disrupting quad flow.",
            "zone": "Coplanar triangle pairs",
            "effect": "Merges coplanar triangles into quads respecting seams and hard edges.",
            "data_impact": "Preserves UV borders.",
            "reversibility": "Reversible via Snapshot.",
            "components": tri_comps,
            "operator": "quadrangulate",
            "operator_text": "Quadranguler les triangles"
        })

    # Category 3: Risky Actions
    if iw_comps or nm_edges > 0:
        rec_risky.append({
            "title": "Remove Internal Occluded Walls",
            "confidence": "Review Required",
            "problem": f"{len(iw_comps) or nm_edges} internal occluded faces / non-manifold edges.",
            "zone": "Internal partitions",
            "effect": "Removes occluded divider faces to heal manifold edges.",
            "data_impact": "Verify that faces are truly internal before deleting.",
            "reversibility": "Reversible via Snapshot.",
            "components": iw_comps or nm_comps,
            "operator": "remove_internal_walls",
            "operator_text": "Supprimer les parois internes"
        })

    # Category 4: Observations
    for f in obs:
        rec_observations.append({
            "title": f.name,
            "problem": f.explanation,
            "confidence": "Informational",
            "focus_id": f.id,
            "components": f.components,
            "is_intentional": f.is_intentional
        })

    return {
        "valid": True,
        "object_name": obj_name,
        "profile_id": profile_id,
        "health": {
            "status": status,
            "defects_count": len(defects),
            "risks_count": len(risks),
            "observations_count": len(obs),
            "total_findings": len(findings)
        },
        "findings": [f.to_dict() for f in findings],
        "findings_objects": findings,
        "recommendation_groups": {
            "conservative": rec_conservative,
            "targeted": rec_targeted,
            "risky": rec_risky,
            "observations": rec_observations
        }
    }
