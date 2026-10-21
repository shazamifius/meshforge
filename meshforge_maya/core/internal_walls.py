"""MeshForge Maya - Internal Walls Detection and Removal Engine.
Identifies occluded internal dividing walls and safely removes them to restore watertight manifold consistency.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
import time
from typing import Dict, Any, List, Set, Tuple

from .snapshot import MayaMeshSnapshot

def detect_internal_walls(obj_name: str) -> Dict[str, Any]:
    """Detects internal divider faces connected to non-manifold edges."""
    res = {
        "valid": False,
        "strict_internal_faces": [],
        "healed_edges_count": 0,
        "world_center": (0.0, 0.0, 0.0),
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

    try:
        sel_list = om.MSelectionList()
        sel_list.add(shape)
        dag_path = sel_list.getDagPath(0)
        dag_path.extendToShape()

        # Find non-manifold edges (edges connected to 3 or more faces)
        it_edge = om.MItMeshEdge(dag_path)
        nm_edges: Set[int] = set()
        while not it_edge.isDone():
            if it_edge.numConnectedFaces() >= 3:
                nm_edges.add(it_edge.index())
            it_edge.next()

        if not nm_edges:
            res["valid"] = True
            return res

        # Check faces where every edge is a non-manifold edge
        it_poly = om.MItMeshPolygon(dag_path)
        strict_faces = []

        while not it_poly.isDone():
            connected_edges = it_poly.getConnectedEdges()
            if all(e in nm_edges for e in connected_edges):
                strict_faces.append(f"{shape}.f[{it_poly.index()}]")
            it_poly.next()

        res["strict_internal_faces"] = strict_faces
        res["healed_edges_count"] = len(nm_edges)
        res["valid"] = True
    except Exception as exc:
        res["error"] = str(exc)

    return res

def execute_remove_internal_walls(
    obj_name: str,
    remove_strict_only: bool = True,
    selected_only: bool = False
) -> Dict[str, Any]:
    """Removes strict internal occluded walls with transactional rollback."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
        "execution_time_ms": 0.0,
        "faces_removed": 0,
        "healed_edges": 0,
        "error": None
    }

    diag = detect_internal_walls(obj_name)
    if not diag.get("valid"):
        res["error"] = diag.get("error", "Failed to detect internal walls.")
        return res

    strict_faces = diag.get("strict_internal_faces", [])
    if not strict_faces:
        res["success"] = True
        res["execution_time_ms"] = (time.perf_counter() - t0) * 1000.0
        return res

    snapshot = MayaMeshSnapshot(obj_name)

    try:
        cmds.undoInfo(openChunk=True)
        cmds.delete(strict_faces)
        snapshot.commit()
        res["success"] = True
        res["faces_removed"] = len(strict_faces)
        res["healed_edges"] = diag.get("healed_edges_count", 0)
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
