"""MeshForge Maya - Intelligent Decimation (Simplification) Engine.
Controls QEM edge contraction via Maya native polyReduce with live budget arbitration,
target triangle enforcement, and feature preservation.
"""

from __future__ import annotations
import maya.cmds as cmds
import time
from typing import Dict, Any, Optional

from .snapshot import MayaMeshSnapshot

def execute_simplification(
    obj_name: str,
    mode: str = "PERCENTAGE", # PERCENTAGE, BUDGET_TRIANGLES, TOLERANCE_ONLY
    percentage: float = 50.0,
    target_triangles: int = 1000,
    preserve_boundaries: bool = True,
    preserve_sharp: bool = True,
    preserve_seams: bool = True,
    triangulate_first: bool = False
) -> Dict[str, Any]:
    """Reduces mesh complexity via progressive edge collapse."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
        "triangles_before": 0,
        "triangles_after": 0,
        "faces_before": 0,
        "faces_after": 0,
        "reduction_percentage": 0.0,
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

        t_before = cmds.polyEvaluate(shape, triangle=True)
        f_before = cmds.polyEvaluate(shape, face=True)
        res["triangles_before"] = t_before
        res["faces_before"] = f_before

        if triangulate_first:
            cmds.polyTriangulate(shape, constructionHistory=False)

        # Calculate reduction percentage
        if mode == "BUDGET_TRIANGLES":
            if t_before > target_triangles:
                effective_pct = max(0.0, min(99.0, ((t_before - target_triangles) / float(t_before)) * 100.0))
            else:
                effective_pct = 0.0
        else:
            effective_pct = max(0.0, min(99.0, percentage))

        if effective_pct > 0.0:
            cmds.polyReduce(
                shape,
                percentage=effective_pct,
                keepBorder=preserve_boundaries,
                keepHardEdge=preserve_sharp,
                keepMapBorder=preserve_seams,
                constructionHistory=False
            )

        t_after = cmds.polyEvaluate(shape, triangle=True)
        f_after = cmds.polyEvaluate(shape, face=True)
        res["triangles_after"] = t_after
        res["faces_after"] = f_after

        if t_before > 0:
            res["reduction_percentage"] = round(((t_before - t_after) / float(t_before)) * 100.0, 2)

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
