"""MeshForge Maya - Transactional Snapshot & Rollback system.
Captures Maya DAG mesh states and guarantees safe rollback on error or invariant breach.
"""

from __future__ import annotations
import maya.cmds as cmds
import maya.api.OpenMaya as om
from typing import Optional, Dict, Any, List

class MayaMeshSnapshot:
    """Captures mesh topology, transform and component states for transactional rollback."""

    def __init__(self, node_name: str):
        self.node_name = node_name
        self.valid = False
        self.backup_node = None
        self.inventory: Dict[str, Any] = {}

        if not cmds.objExists(node_name):
            return

        # Record inventory
        v_count = cmds.polyEvaluate(node_name, vertex=True)
        e_count = cmds.polyEvaluate(node_name, edge=True)
        f_count = cmds.polyEvaluate(node_name, face=True)
        t_count = cmds.polyEvaluate(node_name, triangle=True)

        self.inventory = {
            "name": node_name,
            "vertices": v_count,
            "edges": e_count,
            "faces": f_count,
            "triangles": t_count,
            "visibility": cmds.getAttr(f"{node_name}.visibility") if cmds.attributeQuery("visibility", node=node_name, exists=True) else True
        }

        # Create hidden duplicate for guaranteed rollback
        try:
            backup = cmds.duplicate(node_name, name=f"__mf_backup_{node_name}")[0]
            cmds.setAttr(f"{backup}.visibility", False)
            # Intermediate object flag so it doesn't appear in render or outliner clutter
            shapes = cmds.listRelatives(backup, shapes=True, fullPath=True) or []
            for s in shapes:
                cmds.setAttr(f"{s}.intermediateObject", True)
            self.backup_node = backup
            self.valid = True
        except Exception:
            self.backup_node = None
            self.valid = False

    def restore(self) -> bool:
        """Restores the original mesh state from the backup duplicate."""
        if not self.valid or not self.backup_node or not cmds.objExists(self.backup_node):
            return False

        try:
            # If current node exists, replace shape or delete and rename backup
            if cmds.objExists(self.node_name):
                cmds.delete(self.node_name)
            
            # Make backup visible and restore original name
            shapes = cmds.listRelatives(self.backup_node, shapes=True, fullPath=True) or []
            for s in shapes:
                cmds.setAttr(f"{s}.intermediateObject", False)
            cmds.setAttr(f"{self.backup_node}.visibility", self.inventory.get("visibility", True))
            cmds.rename(self.backup_node, self.node_name)
            self.backup_node = None
            return True
        except Exception as e:
            return False

    def commit(self):
        """Discards backup duplicate upon successful transaction completion."""
        if self.backup_node and cmds.objExists(self.backup_node):
            try:
                cmds.delete(self.backup_node)
            except Exception:
                pass
            self.backup_node = None

    def __del__(self):
        self.commit()
