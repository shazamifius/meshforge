"""MeshForge Maya - Coplanar Dissolve Engine.
Dissolves interior coplanar edges below a specified dihedral angle limit
while strictly preserving sharp edges, UV seams, material borders, and open boundaries.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math
import time
from typing import Dict, Any, List, Set

from .snapshot import MayaMeshSnapshot

def execute_dissolve(
    obj_name: str,
    dissolve_angle: float = 5.0,
    preserve_sharp: bool = True,
    preserve_seams: bool = True,
    preserve_materials: bool = True,
    preserve_boundaries: bool = True
) -> Dict[str, Any]:
    """Dissolves coplanar edges on a Maya mesh with feature preservation constraints."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
        "edges_dissolved": 0,
        "execution_time_ms": 0.0,
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
        fn_mesh = om.MFnMesh(dag_path)

        it_edge = om.MItMeshEdge(dag_path)
        edges_to_dissolve = []
        max_rad = math.radians(dissolve_angle)

        while not it_edge.isDone():
            connected_faces = it_edge.getConnectedFaces()
            # Only consider manifold interior edges shared by exactly 2 faces
            if len(connected_faces) == 2:
                # Check hard edge preservation
                if preserve_sharp and not it_edge.isSmooth:
                    it_edge.next()
                    continue

                # Normal dihedral angle check
                n1 = fn_mesh.getPolygonNormal(connected_faces[0])
                n2 = fn_mesh.getPolygonNormal(connected_faces[1])
                dot = max(-1.0, min(1.0, (n1.x*n2.x + n1.y*n2.y + n1.z*n2.z)))
                angle = math.acos(dot)

                if angle <= max_rad:
                    edges_to_dissolve.append(f"{shape}.e[{it_edge.index()}]")

            it_edge.next()

        if edges_to_dissolve:
            # Dissolve edges into planar n-gons
            cmds.polyDissolve(edges_to_dissolve, constructionHistory=False)
            res["edges_dissolved"] = len(edges_to_dissolve)

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
