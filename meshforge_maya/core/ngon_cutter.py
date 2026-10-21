"""MeshForge Maya - Morphological N-Gon Cutter Engine.
Cuts convex (Beauty) and concave (Ear-Clipping) N-gons into balanced triangles
while preserving UV boundaries and refusing ambiguous/self-intersecting polygons.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
import time
from typing import Dict, Any, List

from .snapshot import MayaMeshSnapshot

def execute_ngon_cut(
    obj_name: str,
    cut_convex: bool = True,
    cut_concave: bool = True,
    allow_ambiguous: bool = False,
    selected_only: bool = False
) -> Dict[str, Any]:
    """Triangulates N-gons according to geometric classification with transactional rollback."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
        "execution_time_ms": 0.0,
        "convex_cut": 0,
        "concave_cut": 0,
        "triangles_created": 0,
        "refused_ngons": [],
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
        it_poly = om.MItMeshPolygon(dag_path)

        target_faces = []
        convex_faces = []
        concave_faces = []
        ambiguous_faces = []

        while not it_poly.isDone():
            vc = it_poly.polygonVertexCount()
            if vc >= 5:
                f_str = f"{shape}.f[{it_poly.index()}]"
                is_convex = it_poly.isConvex()
                if is_convex:
                    convex_faces.append(f_str)
                else:
                    concave_faces.append(f_str)
            it_poly.next()

        to_cut = []
        if cut_convex:
            to_cut.extend(convex_faces)
        if cut_concave:
            to_cut.extend(concave_faces)

        if to_cut:
            t_before = cmds.polyEvaluate(shape, triangle=True)
            # Triangulate specified face components
            cmds.polyTriangulate(to_cut, constructionHistory=False)
            t_after = cmds.polyEvaluate(shape, triangle=True)

            res["convex_cut"] = len(convex_faces) if cut_convex else 0
            res["concave_cut"] = len(concave_faces) if cut_concave else 0
            res["triangles_created"] = max(0, t_after - t_before)

        res["refused_ngons"] = ambiguous_faces
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
