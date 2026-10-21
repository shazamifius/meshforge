"""MeshForge Maya - Normals & Shading Engine.
Handles normal recalculation, angle-based soft/hard edges, and unlocking split normals.
"""

from __future__ import annotations
import maya.cmds as cmds
import time
from typing import Dict, Any

from .snapshot import MayaMeshSnapshot

def execute_normals(
    obj_name: str,
    recalculate: bool = True,
    direction: str = "OUTSIDE", # OUTSIDE, INSIDE
    apply_soft_edge: bool = True,
    soft_edge_angle: float = 30.0,
    unlock_normals: bool = False
) -> Dict[str, Any]:
    """Recalculates face normals and soft/hard shading edges."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
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

        if unlock_normals:
            cmds.polyNormalPerVertex(shape, unFreezeNormal=True)

        if recalculate:
            # Conform normals so all face normals point consistently
            cmds.polyNormal(shape, normalMode=2, constructionHistory=False)
            if direction == "INSIDE":
                cmds.polyNormal(shape, normalMode=0, constructionHistory=False)

        if apply_soft_edge:
            # Soften/harden edges based on dihedral angle
            cmds.polySoftEdge(shape, angle=soft_edge_angle, constructionHistory=False)

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
