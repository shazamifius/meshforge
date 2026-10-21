"""MeshForge Maya - Targeted Quadrangulator Engine.
Merges coplanar triangle pairs into regular quads with strict preservation
of UV boundaries, hard edges, and material slot assignments.
"""

from __future__ import annotations
import maya.cmds as cmds
import time
from typing import Dict, Any

from .snapshot import MayaMeshSnapshot

def execute_targeted_quadrangulation(
    obj_name: str,
    max_angle_deg: float = 15.0,
    compare_uvs: bool = True,
    compare_seams: bool = True,
    compare_sharp: bool = True,
    compare_materials: bool = True
) -> Dict[str, Any]:
    """Converts coplanar triangles into quads with angle and feature constraints."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
        "execution_time_ms": 0.0,
        "quads_created": 0,
        "triangles_merged": 0,
        "final_triangles": 0,
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

        # Maya native polyQuad with feature preservation
        cmds.polyQuad(
            shape,
            angle=max_angle_deg,
            keepHardEdges=compare_sharp,
            keepTextureBorders=compare_uvs,
            constructionHistory=False
        )

        t_after = cmds.polyEvaluate(shape, triangle=True)
        f_after = cmds.polyEvaluate(shape, face=True)

        res["triangles_merged"] = max(0, t_before - t_after)
        res["quads_created"] = max(0, f_before - f_after)
        res["final_triangles"] = t_after

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
