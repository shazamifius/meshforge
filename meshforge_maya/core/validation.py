"""MeshForge Maya - Metrological Validation Engine.
Performs surface distance and geometric deviation comparisons between source and optimized meshes.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
import math
from typing import Dict, Any, Optional

def validate_mesh_surface(
    source_name: str,
    optimized_name: str,
    sample_count: int = 1000
) -> Dict[str, Any]:
    """Measures surface Hausdorff and mean deviation using OpenMaya spatial intersectors."""
    res = {
        "measured": False,
        "max_hausdorff_m": 0.0,
        "mean_deviation_m": 0.0,
        "max_normal_deviation_deg": 0.0,
        "error": None
    }

    if not cmds.objExists(source_name) or not cmds.objExists(optimized_name):
        res["error"] = "One or both meshes do not exist."
        return res

    try:
        shapes_src = cmds.listRelatives(source_name, shapes=True, type='mesh', fullPath=True) or []
        shapes_opt = cmds.listRelatives(optimized_name, shapes=True, type='mesh', fullPath=True) or []

        if not shapes_src or not shapes_opt:
            res["error"] = "Mesh shapes not found."
            return res

        sel = om.MSelectionList()
        sel.add(shapes_src[0])
        sel.add(shapes_opt[0])

        dag_src = sel.getDagPath(0)
        dag_src.extendToShape()
        dag_opt = sel.getDagPath(1)
        dag_opt.extendToShape()

        # Use MMeshIntersector for fast closest-point spatial queries
        intersector = om.MMeshIntersector()
        intersector.create(dag_opt.node(), dag_opt.inclusiveMatrix())

        # Sample vertices from source mesh
        fn_src = om.MFnMesh(dag_src)
        points = fn_src.getPoints(om.MSpace.kWorld)

        total_pts = len(points)
        if total_pts == 0:
            res["measured"] = True
            return res

        step = max(1, total_pts // sample_count)
        max_dist = 0.0
        sum_dist = 0.0
        count = 0

        for i in range(0, total_pts, step):
            pt = om.MPoint(points[i])
            point_info = intersector.getClosestPoint(pt)
            closest_pt = om.MPoint(point_info.point)
            dist = pt.distanceTo(closest_pt)
            if dist > max_dist:
                max_dist = dist
            sum_dist += dist
            count += 1

        if count > 0:
            res["measured"] = True
            res["max_hausdorff_m"] = round(max_dist, 6)
            res["mean_deviation_m"] = round(sum_dist / count, 6)
    except Exception as exc:
        res["error"] = str(exc)

    return res
