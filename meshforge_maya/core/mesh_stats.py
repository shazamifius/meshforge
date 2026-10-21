"""MeshForge Maya - Mesh Statistics and Telemetry Engine.
Computes precise vertex, edge, polygon, triangle, UV, and component metrics.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
from typing import Dict, Any, List, Optional, Tuple

def get_selected_mesh() -> Optional[str]:
    """Returns the transform node of the first active selected mesh."""
    selection = cmds.ls(selection=True, long=True) or []
    for item in selection:
        if cmds.objectType(item) == 'transform':
            shapes = cmds.listRelatives(item, shapes=True, type='mesh', fullPath=True) or []
            if shapes:
                return item
        elif cmds.objectType(item) == 'mesh':
            parent = cmds.listRelatives(item, parent=True, fullPath=True)
            if parent:
                return parent[0]
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
        "bounding_box": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        "error": None
    }

    if not obj_name or not cmds.objExists(obj_name):
        stats["error"] = f"Object '{obj_name}' does not exist."
        return stats

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

        nm_verts = cmds.polyInfo(shape, nonManifoldVertices=True) or []
        stats["non_manifold_verts_count"] = len(nm_verts)

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

        while not it_poly.isDone():
            vc = it_poly.polygonVertexCount()
            if vc == 3:
                tris += 1
            elif vc == 4:
                quads += 1
            else:
                ngons += 1

            area = it_poly.getArea()
            if area <= 1e-7:
                zero_faces += 1

            it_poly.next()

        stats["tris_count"] = tris
        stats["quads_count"] = quads
        stats["ngons_count"] = ngons
        stats["zero_area_faces_count"] = zero_faces

        # Boundary edges (edges connected to exactly 1 face)
        it_edge = om.MItMeshEdge(dag_path)
        boundary_edges = 0
        while not it_edge.isDone():
            if it_edge.numConnectedFaces() == 1:
                boundary_edges += 1
            it_edge.next()

        stats["open_boundary_edges_count"] = boundary_edges
        stats["is_watertight"] = (boundary_edges == 0 and stats["non_manifold_edges_count"] == 0)

        stats["valid"] = True
    except Exception as exc:
        stats["error"] = str(exc)

    return stats
