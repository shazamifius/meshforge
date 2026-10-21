"""MeshForge Maya - Object Data and Shading Engine Cleanup.
Cleans unused shading groups, redundant material slots, and empty object sets.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.mel as mel
import time
from typing import Dict, Any

from .snapshot import MayaMeshSnapshot

def execute_object_data(
    obj_name: str,
    clean_unused_materials: bool = True,
    clean_empty_sets: bool = True
) -> Dict[str, Any]:
    """Cleans unused shading nodes and empty component sets."""
    t0 = time.perf_counter()
    res = {
        "success": False,
        "object_name": obj_name,
        "unused_shading_groups_removed": 0,
        "execution_time_ms": 0.0,
        "error": None
    }

    if not obj_name or not cmds.objExists(obj_name):
        res["error"] = f"Object '{obj_name}' does not exist."
        return res

    snapshot = MayaMeshSnapshot(obj_name)

    try:
        cmds.undoInfo(openChunk=True)

        if clean_unused_materials:
            try:
                # MLdeleteUnused is standard in both Maya GUI and batch mode
                mel.eval('MLdeleteUnused;')
            except Exception:
                pass

        if clean_empty_sets:
            sets = cmds.listSets(object=obj_name) or []
            for s in sets:
                members = cmds.sets(s, query=True) or []
                if not members and not cmds.sets(s, query=True, isIntersecting=True):
                    try:
                        cmds.delete(s)
                    except Exception:
                        pass

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
