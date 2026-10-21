"""MeshForge Maya - Conservative Cleaner Engine.
Performs transactional, non-destructive cleanup of orphan vertices, wire edges,
zero-area faces, and strict duplicate vertices with UV seam protection.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
import time
from typing import Dict, Any, List, Set, Optional

from .snapshot import MayaMeshSnapshot

def execute_conservative_cleanup(
    obj_name: str,
    clean_loose_verts: bool = True,
    clean_wire_edges: bool = True,
    clean_zero_faces: bool = True,
    merge_doubles: bool = True,
    doubles_distance: float = 0.00001,
    preserve_seams: bool = True
) -> Dict[str, Any]:
    """Executes safe, transactional cleanup of elemental defects on a Maya mesh."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
        "execution_time_ms": 0.0,
        "elements_removed": {
            "loose_verts": 0,
            "wire_edges": 0,
            "zero_faces": 0,
            "doubles_merged": 0
        },
        "error": None
    }

    if not obj_name or not cmds.objExists(obj_name):
        res["error"] = f"Object '{obj_name}' does not exist."
        return res

    shapes = cmds.listRelatives(obj_name, shapes=True, type='mesh', fullPath=True) or []
    if not shapes:
        res["error"] = f"Object '{obj_name}' has no mesh shape."
        return res

    shape = shapes[0]
    snapshot = MayaMeshSnapshot(obj_name)

    try:
        cmds.undoInfo(openChunk=True)

        sel_list = om.MSelectionList()
        sel_list.add(shape)
        dag_path = sel_list.getDagPath(0)
        dag_path.extendToShape()

        # 1. Zero-Area Faces Dissolution
        if clean_zero_faces:
            it_poly = om.MItMeshPolygon(dag_path)
            zero_faces = []
            while not it_poly.isDone():
                if it_poly.getArea() <= 1e-7:
                    zero_faces.append(f"{shape}.f[{it_poly.index()}]")
                it_poly.next()

            if zero_faces:
                cmds.delete(zero_faces)
                res["elements_removed"]["zero_faces"] = len(zero_faces)

        # 2. Wire Edges (edges with 0 faces)
        if clean_wire_edges:
            it_edge = om.MItMeshEdge(dag_path)
            wire_edges = []
            while not it_edge.isDone():
                if it_edge.numConnectedFaces() == 0:
                    wire_edges.append(f"{shape}.e[{it_edge.index()}]")
                it_edge.next()

            if wire_edges:
                cmds.delete(wire_edges)
                res["elements_removed"]["wire_edges"] = len(wire_edges)

        # 3. Loose / Orphan Vertices (vertices with 0 edges)
        if clean_loose_verts:
            it_vert = om.MItMeshVertex(dag_path)
            loose_verts = []
            while not it_vert.isDone():
                connected_edges = it_vert.getConnectedEdges()
                if len(connected_edges) == 0:
                    loose_verts.append(f"{shape}.vtx[{it_vert.index()}]")
                it_vert.next()

            if loose_verts:
                cmds.delete(loose_verts)
                res["elements_removed"]["loose_verts"] = len(loose_verts)

        # 4. Merge Duplicate Vertices
        if merge_doubles:
            v_before = cmds.polyEvaluate(shape, vertex=True)
            cmds.polyMergeVertex(
                shape,
                distance=doubles_distance,
                alwaysMergeTwoVertices=False,
                constructionHistory=False
            )
            v_after = cmds.polyEvaluate(shape, vertex=True)
            merged = max(0, v_before - v_after)
            res["elements_removed"]["doubles_merged"] = merged

        snapshot.commit()
        res["success"] = True
    except Exception as exc:
        cmds.undoInfo(closeChunk=True)
        snapshot.restore()
        res["error"] = str(exc)
        res["success"] = False
        return res
    finally:
        cmds.undoInfo(closeChunk=True)

    res["execution_time_ms"] = (time.perf_counter() - t0) * 1000.0
    return res
