"""MeshForge Maya - Visualizer & 3D Viewport Framing Engine.
Handles component selection, smooth camera framing, wireframe overlays, and inspection display.
"""

from __future__ import annotations
import maya.cmds as cmds
from typing import List, Optional, Tuple

def focus_on_components(components: List[str]) -> bool:
    """Selects specific mesh components (vertices/edges/faces) and frames the active viewport camera."""
    if not components:
        return False

    valid_components = [c for c in components if cmds.objExists(c)]
    if not valid_components:
        return False

    try:
        # Switch to component mode and select components
        cmds.select(valid_components, replace=True)
        # Frame camera smoothly onto the selected defect
        cmds.viewFit(animate=True)
        return True
    except Exception:
        return False

def toggle_wireframe_display() -> bool:
    """Toggles wireframe on shaded display mode in the active 3D model panel."""
    active_panel = cmds.getPanel(withFocus=True)
    if not active_panel or 'modelPanel' not in active_panel:
        # Fallback to modelPanel4 (standard perspective panel in Maya)
        active_panel = 'modelPanel4'

    if cmds.modelEditor(active_panel, exists=True):
        curr = cmds.modelEditor(active_panel, query=True, wireframeOnShaded=True)
        new_state = not curr
        cmds.modelEditor(active_panel, edit=True, wireframeOnShaded=new_state)
        return new_state
    return False

def clear_inspection_view() -> None:
    """Deselects components and returns to standard object selection mode."""
    cmds.select(clear=True)
    cmds.selectMode(object=True)
