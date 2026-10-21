"""MeshForge for Autodesk Maya.
Advanced 3D Mesh Analysis, Repair, Cleanup, and Intelligent Simplification.
"""

__version__ = "0.2.0"
__author__ = "shazamifius"

def show():
    """Launch and display the MeshForge Maya UI."""
    from .ui.main_window import show_meshforge_window
    return show_meshforge_window()
