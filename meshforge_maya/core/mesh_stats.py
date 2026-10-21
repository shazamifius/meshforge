"""MeshForge Maya - Mesh Statistics and Telemetry Engine.
Computes precise vertex, edge, polygon, triangle, UV, and component metrics.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
from typing import Dict, Any, List, Optional, Tuple

def get_selected_mesh() -> Optional[str]:
    """Returns the transform node of the active selected mesh or component."""
    sel = cmds.ls(selection=True, long=True) or []
    if not sel:
        # In component mode (Faces/Edges/Verts), Maya keeps the object in hilite
        sel = cmds.ls(hilite=True, long=True) or []
    if not sel:
        return None

    first = sel[0]
    # Strip any component index (e.g. pCylinder5.f[2430] -> pCylinder5)
    node = first.split('.')[0]
    if not cmds.objExists(node):
        return None

    if cmds.objectType(node) == 'mesh':
        parents = cmds.listRelatives(node, parent=True, fullPath=True)
        return parents[0] if parents else node
    elif cmds.objectType(node) == 'transform':
        shapes = cmds.listRelatives(node, shapes=True, type='mesh', fullPath=True) or []
        if shapes:
            return node
    return None

def get_mesh_statistics(obj_name: str) -> Dict[str, Any]:
    """Gathers comprehensive topological, volumetric, and attribute statistics for a Maya mesh."""
    stats: Dict[str, Any] = {
        "valid": False,
        "object_name": obj_name,
        "vertices": 0,
        "edges": 0,
        "faces": 0,
        "triangles": 0,
        "uv_sets_count": 0,
        "uv_sets": [],
        "materials_count": 0,
        "materials": [],
        "has_blendshapes": False,
        "blendshape_nodes": [],
        "has_skincluster": False,
        "non_manifold_edges_count": 0,
        "non_manifold_verts_count": 0,
        "open_boundary_edges_count": 0,
        "is_watertight": False,
        "zero_area_faces_count": 0,
        "ngons_count": 0,
        "tris_count": 0,
        "quads_count": 0,
        "disjoint_shells_count": 1,
        "internal_walls_count": 0,
        "non_manifold_edges_components": [],
        "non_manifold_verts_components": [],
        "open_boundary_edges_components": [],
        "zero_area_faces_components": [],
        "ngons_components": [],
        "tris_components": [],
        "quads_components": [],
        "internal_walls_components": [],
        "bounding_box": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        "error": None
    }

    if not obj_name or not cmds.objExists(obj_name):
        stats["error"] = f"Object '{obj_name}' does not exist."
        return stats

    # Normalize transform name
    if cmds.objectType(obj_name) == 'mesh':
        parents = cmds.listRelatives(obj_name, parent=True, fullPath=True) or []
        obj_name = parents[0] if parents else obj_name

    shapes = cmds.listRelatives(obj_name, shapes=True, type='mesh', fullPath=True) or []
    if not shapes:
        stats["error"] = f"Object '{obj_name}' has no mesh shape node."
        return stats

    shape = shapes[0]

    try:
        # 1. Basic Component Counts
        stats["vertices"] = cmds.polyEvaluate(shape, vertex=True)
        stats["edges"] = cmds.polyEvaluate(shape, edge=True)
        stats["faces"] = cmds.polyEvaluate(shape, face=True)
        stats["triangles"] = cmds.polyEvaluate(shape, triangle=True)
        stats["uv_sets"] = cmds.polyUVSet(shape, query=True, allUVSets=True) or []
        stats["uv_sets_count"] = len(stats["uv_sets"])

        # Disjoint shells (islands)
        stats["disjoint_shells_count"] = cmds.polyEvaluate(shape, shell=True)

        # Bounding box
        bb = cmds.xform(obj_name, query=True, boundingBox=True, worldSpace=True) or [0]*6
        stats["bounding_box"] = tuple(round(c, 4) for c in bb)

        # 2. Shading Materials
        shading_engines = cmds.listConnections(shape, type='shadingEngine') or []
        materials = set()
        for se in shading_engines:
            mats = cmds.ls(cmds.listConnections(f"{se}.surfaceShader"), materials=True) or []
            materials.update(mats)
        stats["materials"] = list(materials)
        stats["materials_count"] = len(materials)

        # 3. Deformers & BlendShapes
        history = cmds.listHistory(shape, pruneDagObjects=True) or []
        blendshapes = cmds.ls(history, type='blendShape') or []
        stats["has_blendshapes"] = len(blendshapes) > 0
        stats["blendshape_nodes"] = blendshapes

        skins = cmds.ls(history, type='skinCluster') or []
        stats["has_skincluster"] = len(skins) > 0

        # Non-manifold checks via native cmds.polyInfo
        nm_edges = cmds.polyInfo(shape, nonManifoldEdges=True) or []
        stats["non_manifold_edges_count"] = len(nm_edges)
        stats["non_manifold_edges_components"] = nm_edges

        nm_verts = cmds.polyInfo(shape, nonManifoldVertices=True) or []
        stats["non_manifold_verts_count"] = len(nm_verts)
        stats["non_manifold_verts_components"] = nm_verts

        # 4. OpenMaya 2.0 In-Depth Topology Analysis
        sel_list = om.MSelectionList()
        sel_list.add(shape)
        dag_path = sel_list.getDagPath(0)
        dag_path.extendToShape()

        # Open boundaries, N-gons, Quads, Tris, Zero-Area faces
        it_poly = om.MItMeshPolygon(dag_path)
        tris = 0
        quads = 0
        ngons = 0
        zero_faces = 0

        tris_comps: List[str] = []
        quads_comps: List[str] = []
        ngons_comps: List[str] = []
        zero_faces_comps: List[str] = []

        while not it_poly.isDone():
            idx = it_poly.index()
            comp_name = f"{obj_name}.f[{idx}]"
            vc = it_poly.polygonVertexCount()
            if vc == 3:
                tris += 1
                tris_comps.append(comp_name)
            elif vc == 4:
                quads += 1
                quads_comps.append(comp_name)
            else:
                ngons += 1
                ngons_comps.append(comp_name)

            area = it_poly.getArea()
            if area <= 1e-7:
                zero_faces += 1
                zero_faces_comps.append(comp_name)

            it_poly.next()

        stats["tris_count"] = tris
        stats["quads_count"] = quads
        stats["ngons_count"] = ngons
        stats["zero_area_faces_count"] = zero_faces

        stats["tris_components"] = tris_comps
        stats["quads_components"] = quads_comps
        stats["ngons_components"] = ngons_comps
        stats["zero_area_faces_components"] = zero_faces_comps

        # Boundary edges (edges connected to exactly 1 face)
        it_edge = om.MItMeshEdge(dag_path)
        boundary_edges = 0
        boundary_comps: List[str] = []

        while not it_edge.isDone():
            if it_edge.onBoundary():
                boundary_edges += 1
                boundary_comps.append(f"{obj_name}.e[{it_edge.index()}]")
            it_edge.next()

        stats["open_boundary_edges_count"] = boundary_edges
        stats["open_boundary_edges_components"] = boundary_comps
        stats["is_watertight"] = (boundary_edges == 0 and stats["non_manifold_edges_count"] == 0)

        # Internal occluded walls
        from .internal_walls import detect_internal_walls
        try:
            iw = detect_internal_walls(obj_name)
            faces = iw.get("strict_internal_faces", []) if isinstance(iw, dict) else (list(iw) if isinstance(iw, (list, tuple)) else [])
            stats["internal_walls_components"] = faces
            stats["internal_walls_count"] = len(faces)
        except Exception:
            stats["internal_walls_components"] = []
            stats["internal_walls_count"] = 0

        stats["valid"] = True
    except Exception as exc:
        stats["error"] = str(exc)
        stats["valid"] = False

    return stats
